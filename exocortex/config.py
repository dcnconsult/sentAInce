"""Exocortex configuration — modes, paths, the energy regime, and the dev-toolchain grounding.

Everything safety- or memory-critical lives off the model in the substrate; this module is the
knob board. Stage is selected by ``EXOCORTEX_MODE`` (observe|somatic|epistemic|full).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from enum import Enum


class Mode(Enum):
    OBSERVE = "observe"      # Stage 0: log everything, NEVER veto/inject (the baseline / "the bar")
    UNGATED = "ungated"      # anti-vacuity null: REMOVE the gate (a gate-refused command executes)
    SOMATIC = "somatic"      # Stage 1: + PreToolUse hard veto on lethal/destructive
    EPISTEMIC = "epistemic"  # Stage 2: + interoceptive injection (no hard veto beyond the failsafe)
    FULL = "full"            # Stage 3: both halves


def mode() -> Mode:
    env = os.environ.get("EXOCORTEX_MODE")
    if env is None:                       # no explicit mode → take the Genome's somatic_gate.mode
        from .genome import GENOME
        env = GENOME["somatic_gate"]["mode"]
    try:
        return Mode(str(env).strip().lower())
    except ValueError:
        return Mode.OBSERVE


def provider() -> str:
    """Which host drives the hooks: ``claude`` (default) or ``cursor``. Sourced from ``EXOCORTEX_PROVIDER``
    (the deploy bakes ``--provider`` into the hook command); the adapter additionally auto-detects Cursor
    from the payload shape. Used only by the I/O shim — the organs are provider-agnostic."""
    return (os.environ.get("EXOCORTEX_PROVIDER") or "claude").strip().lower()


def colony_enabled() -> bool:
    """The verb-altitude pheromone colony (consequence-sourced procedural memory) accrues + splices
    independently of the somatic/epistemic Mode — it is the third (memory) subsystem. On by default;
    set ``EXOCORTEX_COLONY=0`` to keep a pure baseline run free of any deposits/splice."""
    return os.environ.get("EXOCORTEX_COLONY", "1") != "0"


def embed_enabled() -> bool:
    """Use the semantic EMBEDDING cue-classifier (MiniLM) vs the lexical one. The Genome default is
    ``epistemic_classifier.mode = "semantic"`` → ON (it proved superior). ``EXOCORTEX_EMBED`` (0/1)
    overrides the genome. When unavailable (no sentence-transformers) the hook fails open to lexical."""
    env = os.environ.get("EXOCORTEX_EMBED")
    if env is not None:
        return env == "1"
    from .genome import GENOME
    return GENOME["epistemic_classifier"]["mode"] == "semantic"


def colony_splice_enabled() -> bool:
    """The colony's *injection* half (the UserPromptSubmit splice), gated separately from deposit so an
    OBSERVE-ONLY accrual run (``EXOCORTEX_COLONY_SPLICE=0``) can measure what natural work deposits
    without injected memory nudging the agent's tool choices (a self-confirming-colony confound)."""
    return os.environ.get("EXOCORTEX_COLONY_SPLICE", "1") != "0"


def declarative_enabled() -> bool:
    """The live declarative wiki organ (Ticket 1). Ships DORMANT — touches the wiki only when the Genome
    ``declarative.mode == "live"``. ``EXOCORTEX_DECLARATIVE`` (0/1) overrides the genome. When off, the
    hook behaves exactly as the verified procedural baseline (no wiki load / splice / deposit)."""
    env = os.environ.get("EXOCORTEX_DECLARATIVE")
    if env is not None:
        return env == "1"
    from .genome import GENOME
    return str(GENOME.get("declarative", {}).get("mode", "off")).lower() == "live"


def declarative_vault() -> str:
    """The Markdown vault path for the wiki organ. ``EXOCORTEX_WIKI_VAULT`` overrides the Genome
    ``declarative.vault_path``. Empty → dormant even if ``mode == "live"`` (nothing to digest)."""
    from .genome import GENOME
    return os.environ.get("EXOCORTEX_WIKI_VAULT") or str(GENOME.get("declarative", {}).get("vault_path", "")) or ""


def declarative_ingest() -> str:
    """Which Markdown files the wiki organ ingests (T4 inclusion boundary): ``all`` | ``tracked``.
      - ``all`` (default, the verified baseline): every ``*.md`` under the vault.
      - ``tracked``: only git-tracked ``*.md`` — respects the vault's ``.gitignore`` AND excludes untracked
        junk / submodule noise; falls open to ``all`` if the vault is not a git repo / git is unavailable.
    The committed default stays ``all`` (ADR-003: ``main`` stays conservative); a real large vault flips to
    ``tracked`` as a local, gitignored activation. ``EXOCORTEX_WIKI_INGEST`` overrides the Genome."""
    env = os.environ.get("EXOCORTEX_WIKI_INGEST")
    if env is not None:
        return env.strip().lower()
    from .genome import GENOME
    return str(GENOME.get("declarative", {}).get("ingest", "all")).strip().lower()


def integrity_mode() -> str:
    """The cryptographic immune system's posture (ADR-009): ``off`` | ``warn`` | ``enforce``. Ships ``off``;
    ``enforce`` is the production apoptosis (fail-closed on a frozen-DNA mismatch). ``EXOCORTEX_INTEGRITY``
    overrides the Genome."""
    env = os.environ.get("EXOCORTEX_INTEGRITY")
    if env is not None:
        return env.lower()
    from .genome import GENOME
    return str(GENOME.get("integrity", {}).get("mode", "off")).lower()


def audit_chain_enabled() -> bool:
    """Hash-chain new audit records (the epigenetic ledger). On by default (cheap, fail-open);
    ``EXOCORTEX_AUDIT_CHAIN=0`` disables."""
    env = os.environ.get("EXOCORTEX_AUDIT_CHAIN")
    if env is not None:
        return env != "0"
    from .genome import GENOME
    return bool(GENOME.get("integrity", {}).get("audit_chain", True))


def bridge_enabled() -> bool:
    """The Hippocampus bridge organ (Ticket 2). Ships DORMANT — active only when the Genome
    ``declarative.bridge.mode == "suggest"``. ``EXOCORTEX_BRIDGE`` (0/1) overrides. Off → no synthesis,
    no provisional offers; the declarative organ behaves exactly as Ticket 1."""
    env = os.environ.get("EXOCORTEX_BRIDGE")
    if env is not None:
        return env == "1"
    from .genome import GENOME
    return str(GENOME.get("declarative", {}).get("bridge", {}).get("mode", "off")).lower() == "suggest"


def lethal_failsafe() -> bool:
    """Even in OBSERVE, never let a *recognized-lethal* command EXECUTE on a real host — a
    ``kill -9 1`` / ``rm -rf /`` cannot be safely 'observed' un-vetoed. The lethal scenario's
    baseline is therefore the ATTEMPT (recorded at PreToolUse, then blocked). Off only for
    in-container runs (``EXOCORTEX_LETHAL_FAILSAFE=0``)."""
    return os.environ.get("EXOCORTEX_LETHAL_FAILSAFE", "1") != "0"


@dataclass(frozen=True)
class EnergyRegime:
    """v1.02 metabolism, remapped to a Claude Code session. Fuel drains as commands complete;
    failures drain more (thrashing burns the battery). Tiers are v1.02's fractions of e0."""

    e0: float = 100.0
    cost_action: float = 1.0     # a command that completed
    cost_failure: float = 6.0    # a command that FAILED (compute-agnosia inducer)
    sated_frac: float = 0.5      # E >= 0.5 e0  -> SATED (wide exploration ok)
    hypoxia_frac: float = 0.2    # E <  0.2 e0  -> HYPOXIA (sequential reflexes only)


ENERGY = EnergyRegime()

STRATEGY_LOCK_THRESHOLD = 3   # N same-key failures with no intervening success → locked

# The agent's grounded DEV toolchain — v1.07 re-grounding for coding (the locked battle.epistemic
# vocabulary is host-ops: df/systemctl/iptables; reusing it verbatim would abstain on git/python).
GROUNDED_DEV_VERBS = frozenset({
    "git", "python", "python3", "pip", "pip3", "pytest", "node", "npm", "npx", "pnpm", "yarn",
    "ls", "cd", "cat", "grep", "rg", "find", "head", "tail", "echo", "mkdir", "touch", "mv", "cp",
    "make", "cargo", "go", "ruff", "black", "mypy", "docker", "sed", "awk", "wc", "diff", "sort",
    "jq", "curl", "wget", "tar", "unzip", "chmod", "ln", "pwd", "which", "env", "export", "test",
    "rm",  # a common dev op — grounded so it ATTEMPTs; the SOMATIC gate backstops dangerous deletes
})

# High-reversibility-cost verbs (v1.06 stake) — being wrong here is expensive.
HIGH_STAKE_VERBS = frozenset({"rm", "dd", "mkfs", "shred", "wipefs", "truncate", "kill", "pkill",
                              "killall", "iptables", "shutdown", "reboot", "fdisk", "parted"})
HIGH_STAKE_FRAGMENTS = ("--force", "--hard", "force-push", " push ", " reset ", " clean ", " prune ")

# Exfil / injected-execution signatures the somatic oracle is BLIND to (the M5 epistemic catch:
# they change no declared local invariant, so the outcome-oracle permits them — the epistemic gate
# abstains them as ungrounded).
EXFIL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\|\s*(?:ba)?sh\b"),                          # ... | sh   /  ... | bash
    re.compile(r"\b(?:bash|sh)\s+-c\b.*\b(?:curl|wget|nc)\b"),
    re.compile(r"/dev/tcp/"),                                  # reverse shell
    re.compile(r"\bbase64\b.*-d\b.*\|\s*(?:ba)?sh\b"),
    re.compile(r"\bnc\b.*-e\b"),                               # netcat exec
)


def state_dir() -> Path:
    root = os.environ.get("EXOCORTEX_STATE_DIR") or os.path.join(
        os.environ.get("CLAUDE_PROJECT_DIR", "."), ".claude", "exocortex")
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    return p
