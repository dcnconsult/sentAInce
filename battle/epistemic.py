"""The epistemic pre-filter (M5 / Phase 2) — the action-side twin of the RAG control plane.

This is the "should I even attempt this?" gate that sits ABOVE the somatic "is it safe to execute?"
gate. It is the faithful action-side application of two LOCKED laws from the symmetric epistemic engine
(`circle_of_fifths_rag`):

  * v1.06 Decisions-as-Gauges — the decision is expected-cost: ``verify iff (1 − p_eff)·stake >
    verify_cost`` with ``p_eff = confidence · (1 − pressure·discount)`` (confidence × risk × context).
  * v1.07 RAG-as-Context + abstain — cue-retrieve the relevant grounded prior; when the proposal is
    NOT grounded (retrieval confidence below threshold), ABSTAIN rather than act on a spurious match.

Why it composes with — and is not redundant to — the somatic gate: the two brakes catch DIFFERENT
failure classes. An ungrounded/injected action (e.g. an exfil `curl … | sh`) changes no declared local
invariant, so the somatic outcome-oracle is blind to it (C6's stated boundary) — but the epistemic gate
ABSTAINS it as ungrounded. Conversely a grounded operational verb that is somatically LETHAL
(`iptables -F`) sails through the epistemic gate but is refused by the somatic floor. Failure of the
epistemic gate = acting on hallucination; failure of the somatic gate = host death.

Self-contained + deterministic; imports nothing from `circle_of_fifths_rag` (its laws are applied, its
product layer is not vendored). A labeled DEMONSTRATION, never part of the C1–C7 evidence lock.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# the agent's grounded operational vocabulary (verbs it has legitimate grounds to run)
GROUNDED_VERBS = frozenset({
    "echo", "df", "ls", "cat", "grep", "head", "tail", "uptime", "free", "ps", "stat", "du",
    "journalctl", "systemctl", "iptables", "rm", "find", "truncate",
})
# routine locations the agent is grounded to operate on (low-stake, fully in-distribution)
ROUTINE_ROOTS = ("/var/log", "/tmp", "/var/cache", "/var/spool")


class Decision(Enum):
    ATTEMPT = "attempt"    # grounded + confident → forward to the somatic gate
    VERIFY = "verify"      # grounded but the expected cost of being wrong is high → escalate (don't act)
    ABSTAIN = "abstain"    # ungrounded → refuse to act on a spurious / injected instruction


@dataclass(frozen=True)
class EpistemicVerdict:
    command: str
    decision: Decision
    grounded: bool
    confidence: float
    stake: float
    reason: str


def _verb(command: str) -> str:
    tokens = command.strip().split()
    if not tokens:
        return ""
    head = tokens[1] if (tokens[0] == "sudo" and len(tokens) > 1) else tokens[0]
    return head.split(".")[0]


def _paths(command: str) -> list[str]:
    return [t for t in command.strip().split()[1:] if t.startswith(("/", "./", "../", "~/"))]


def ground_score(command: str) -> float:
    """v1.07 cue-retrieval: how well the proposal matches the grounded operational distribution.

    1.0 = a grounded verb on a routine target (or no target); 0.6 = a grounded verb on an unusual /
    sensitive target (in-distribution verb, out-of-distribution object); 0.0 = an ungrounded verb
    (novel / injected / hallucinated)."""
    if _verb(command) not in GROUNDED_VERBS:
        return 0.0
    paths = _paths(command)
    if not paths:
        return 1.0
    routine = all(any(p == r or p.startswith(r + "/") for r in ROUTINE_ROOTS) for p in paths)
    return 1.0 if routine else 0.6


def _stake(command: str) -> float:
    """Coarse reversibility cost if the attempt is wrong — NOT somatic lethality (that is the somatic
    gate's job). State-changing verbs cost more than read-only ones."""
    return 8.0 if _verb(command) in {"rm", "find", "truncate", "iptables", "systemctl"} else 1.0


@dataclass(frozen=True)
class EpistemicPreFilter:
    abstain_threshold: float = 0.5   # v1.07: ground_score below this → ABSTAIN
    verify_cost: float = 2.0         # v1.06: the cost of escalating to verification
    pressure_discount: float = 0.6   # v1.06 gauge-3: how much context-pressure discounts confidence

    def decide(self, command: str, *, context_pressure: float = 0.0) -> EpistemicVerdict:
        score = ground_score(command)
        if score < self.abstain_threshold:
            return EpistemicVerdict(command, Decision.ABSTAIN, False, score, _stake(command),
                                    f"ABSTAIN: ungrounded (score {score:.2f} < {self.abstain_threshold})")
        p_eff = score * (1.0 - self.pressure_discount * context_pressure)
        stake = _stake(command)
        if (1.0 - p_eff) * stake > self.verify_cost:
            return EpistemicVerdict(command, Decision.VERIFY, True, p_eff, stake,
                                    f"VERIFY: grounded but (1-{p_eff:.2f})·{stake:g} > {self.verify_cost}")
        return EpistemicVerdict(command, Decision.ATTEMPT, True, p_eff, stake,
                                f"ATTEMPT: grounded & confident (p_eff {p_eff:.2f}, stake {stake:g})")
