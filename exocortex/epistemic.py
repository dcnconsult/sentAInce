"""The epistemic pre-filter — re-grounded for the coding domain.

Applies the SAME two locked laws as ``battle.epistemic`` (v1.06 expected-cost gauge + v1.07
abstain-on-novelty) but re-grounds them on the DEV toolchain (``config.GROUNDED_DEV_VERBS``): the
locked module's vocabulary is host-ops (df/systemctl/iptables) and would abstain on git/python. The
law is domain-agnostic; the grounding is domain-specific — exactly what "the epistemic gate *applies*
the RAG laws" means.

ABSTAIN is focused on the exfil / injected-execution class the somatic outcome-oracle is BLIND to
(``curl … | sh``, ``/dev/tcp`` reverse shells) — the M5 complementary catch. VERIFY fires when a
grounded-but-high-stake action's expected cost of error exceeds the verify cost.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .config import (GROUNDED_DEV_VERBS, HIGH_STAKE_VERBS, HIGH_STAKE_FRAGMENTS, EXFIL_PATTERNS)


class Decision(Enum):
    ATTEMPT = "attempt"    # grounded + confident → forward to the somatic gate
    VERIFY = "verify"      # grounded but expected cost of being wrong is high → ask (human-in-loop)
    ABSTAIN = "abstain"    # ungrounded (exfil/injected) → do not act on a spurious instruction


@dataclass(frozen=True)
class EpistemicVerdict:
    command: str
    decision: Decision
    grounded: bool
    confidence: float
    stake: float
    reason: str


def _verb(command: str) -> str:
    toks = command.strip().split()
    if not toks:
        return ""
    head = toks[1] if (toks[0] == "sudo" and len(toks) > 1) else toks[0]
    return head.split("/")[-1]


def is_exfil(command: str) -> bool:
    return any(p.search(command) for p in EXFIL_PATTERNS)


def ground_score(command: str) -> float:
    """v1.07 cue-retrieval, dev-grounded: 1.0 = a known dev verb; 0.6 = an unknown verb (novel but
    plausibly legitimate project tooling — NOT abstained, only verified if also high-stake); 0.0 =
    an exfil / injected-execution pattern (ungrounded by construction → ABSTAIN). Only the exfil
    class is denied outright; unknown project commands are allowed to attempt."""
    if is_exfil(command):
        return 0.0
    return 1.0 if _verb(command) in GROUNDED_DEV_VERBS else 0.6


def _stake(command: str) -> float:
    if _verb(command) in HIGH_STAKE_VERBS or any(f in command for f in HIGH_STAKE_FRAGMENTS):
        return 8.0
    return 1.0


def assess(command: str, *, context_pressure: float = 0.0,
           abstain_threshold: float = 0.5, verify_cost: float = 2.0,
           pressure_discount: float = 0.6) -> EpistemicVerdict:
    """v1.06 expected-cost over the dev grounding: ABSTAIN if ungrounded; else VERIFY iff
    ``(1 − p_eff)·stake > verify_cost`` with ``p_eff = score·(1 − pressure_discount·pressure)``."""
    score = ground_score(command)
    stake = _stake(command)
    if score < abstain_threshold:
        why = "exfil / injected-execution pattern" if is_exfil(command) else f"unknown verb `{_verb(command)}`"
        return EpistemicVerdict(command, Decision.ABSTAIN, False, score, stake,
                                f"ABSTAIN: ungrounded ({why}); somatic-oracle is blind to this class")
    p_eff = score * (1.0 - pressure_discount * context_pressure)
    if (1.0 - p_eff) * stake > verify_cost:
        return EpistemicVerdict(command, Decision.VERIFY, True, p_eff, stake,
                                f"VERIFY: grounded but high-stake ((1-{p_eff:.2f})·{stake:g} > {verify_cost})")
    return EpistemicVerdict(command, Decision.ATTEMPT, True, p_eff, stake,
                            f"ATTEMPT: grounded & confident (p_eff {p_eff:.2f}, stake {stake:g})")
