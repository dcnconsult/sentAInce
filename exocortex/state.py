"""Per-session Exocortex state: the interoceptive energy ledger + the strategy-lock history.

Persisted as one JSON per Claude Code session under ``config.state_dir()``. Reuses the locked
``MetabolicLedger`` (v1.02) for the energy debit; the strategy-lock counter is the consequence
signal (a command-key that keeps FAILING with no intervening success).
"""
from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from sentaince.organism.metabolism import MetabolicLedger

from .config import ENERGY, STRATEGY_LOCK_THRESHOLD, state_dir
from .fsutil import atomic_write_text, load_store_json

_HISTORY_CAP = 80
_TRAIL_CAP = 24   # the colony's per-session decision-trail: nodes since the last Bash consequence
_ENV_ASSIGN = re.compile(r"^\w+=")


def command_key(command: str) -> str:
    """A coarse 'intent' key for strategy-lock: verb + first non-flag token, values stripped, and
    leading ``VAR=value`` env assignments / ``sudo`` skipped (so ``PIPELINE_TOKEN=go python run.py``
    and ``python run.py`` share a key). ``git push origin main`` → ``git push``."""
    toks = command.strip().split()
    i = 0
    while i < len(toks) and _ENV_ASSIGN.match(toks[i]):
        i += 1
    if i < len(toks) and toks[i] == "sudo":
        i += 1
    if i >= len(toks):
        return ""
    verb = toks[i]
    for t in toks[i + 1:]:
        if not t.startswith("-"):
            return f"{verb} {t}"
    return verb


@dataclass
class SessionState:
    session_id: str
    energy: float = ENERGY.e0
    history: list = field(default_factory=list)   # recent [key, outcome] pairs ("ok"|"fail")
    trail: list = field(default_factory=list)     # the colony's decision-trail (verb-nodes) since the
    #                                               last Bash consequence; segment-scoped, capped
    resplice: bool = True                          # inject the colony's consolidated memory on the next
    #                                               UserPromptSubmit (set on SessionStart + PreCompact)
    goal_class: str = "_default"                   # the cue-classifier's label for the current turn —
    #                                               keys the per-class colony + the trail's cue: root
    last_spliced_class: str = ""                   # the class whose memory was last spliced (so a task
    #                                               switch re-splices, but the same task doesn't repeat)
    classified_generation: str = ""                # Cursor: the generation_id whose prompt seeded goal_class
    #                                               — lazy-init recovers the class when beforeSubmitPrompt missed
    session_deposits: int = 0                      # colony deposits made THIS session — drives the
    #                                               session-quality discount (later deposits weigh less)
    # ---- declarative wiki (Ticket 1; only touched when declarative_enabled) ----
    injected_exons: list = field(default_factory=list)   # wiki exon NodeIds injected THIS turn (the
    #                                               attribution surface — only these can be credited)
    action_buffer: list = field(default_factory=list)    # raw tool-input strings THIS segment (commands/
    #                                               edits) — scanned for used-note echo, reset per consequence
    wiki_active: list = field(default_factory=list)      # notes used at the last consequence — the
    #                                               proposer's spreading-activation seed for the next turn
    # ---- write-integrity flags (ADR-020; never persisted — save() builds its dict explicitly) ----
    _load_degraded: bool = field(default=False, repr=False)   # W2: store unreadable at load → save() refuses
    _lock_failopen: bool = field(default=False, repr=False)   # W4: locked() couldn't acquire → telemetry

    # ---- colony decision-trail (consequence-segmented) ----
    def push_node(self, node: str) -> None:
        """Append a verb-node to the current segment (any tool). The segment runs until the next Bash
        consequence resets it (deposit on success / drop on failure) — so each segment is one unit of
        work culminating in a verified command."""
        self.trail.append(node)
        del self.trail[:-_TRAIL_CAP]

    def reset_trail(self) -> None:
        self.trail = []

    # ---- energy (v1.02) ----
    def debit(self, outcome: str) -> None:
        ledger = MetabolicLedger(e0=self.energy)
        ledger.spend(ENERGY.cost_failure if outcome == "fail" else ENERGY.cost_action)
        self.energy = ledger.E

    def tier(self) -> str:
        if self.energy >= ENERGY.sated_frac * ENERGY.e0:
            return "SATED"
        if self.energy < ENERGY.hypoxia_frac * ENERGY.e0:
            return "HYPOXIA"
        return "STARVING"

    def pct(self) -> int:
        return max(0, round(100 * self.energy / ENERGY.e0))

    # ---- strategy-lock (consequence) ----
    def record(self, key: str, outcome: str) -> None:
        self.history.append([key, outcome])
        del self.history[:-_HISTORY_CAP]

    def consecutive_failures(self, key: str) -> int:
        """Trailing consecutive failures of ``key`` since its last success (or start)."""
        n = 0
        for k, outcome in reversed(self.history):
            if k != key:
                continue
            if outcome == "fail":
                n += 1
            else:
                break
        return n

    def locked_keys(self) -> list[tuple[str, int]]:
        """Keys currently at/above the strategy-lock threshold, with their streaks."""
        seen: dict[str, int] = {}
        for key, _ in self.history:
            if key not in seen:
                seen[key] = self.consecutive_failures(key)
        return [(k, c) for k, c in seen.items() if c >= STRATEGY_LOCK_THRESHOLD]

    # ---- persistence ----
    def _path(self) -> Path:
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in self.session_id) or "session"
        return state_dir() / f"state_{safe}.json"

    @classmethod
    @contextlib.contextmanager
    def locked(cls, session_id: str, timeout: float = 2.0):
        """Exclusive load-modify-save critical section for this session's state file.

        BUG_SESSIONSTATE_RACE (2026-07-08): concurrent PreToolUse hook processes raced the unlocked
        ``load() → mutate → save()`` — last-write-wins silently dropped a trail node, and the next
        deposit laid a fused τ edge the session never walked (confirmed by the Compaction Audit
        replay gate, 1/205 deposits). Same discipline as the audit chain's ``integrity.append_lock``
        (sidecar ``<path>.lock``): hold the lock across the WHOLE read-modify-write, FAIL-OPEN on
        timeout — a rare lost node under pathological contention beats a wedged hook.

        Usage: ``with SessionState.locked(sid) as st: …mutate…; st.save()`` — the caller still
        decides whether to save (early returns inside the block leave the file untouched)."""
        from .integrity import append_lock
        path = cls(session_id=session_id)._path()
        with append_lock(path, timeout=timeout) as got:
            st = cls.load(session_id)
            st._lock_failopen = not got     # W4: surfaced into the consequence audit row
            yield st

    def save(self) -> None:
        if self._load_degraded:
            return   # ADR-020 W2: never write back over a store we failed to read
        atomic_write_text(self._path(), json.dumps({   # ADR-020 W1: a reader never sees a torn store
            "session_id": self.session_id, "energy": self.energy, "history": self.history,
            "trail": self.trail, "resplice": self.resplice,
            "goal_class": self.goal_class, "last_spliced_class": self.last_spliced_class,
            "classified_generation": self.classified_generation,
            "session_deposits": self.session_deposits,
            "injected_exons": self.injected_exons, "action_buffer": self.action_buffer,
            "wiki_active": self.wiki_active,
        }))

    @classmethod
    def load(cls, session_id: str) -> "SessionState":
        st = cls(session_id=session_id)
        d, degraded = load_store_json(st._path())   # ADR-020 W2: unreadable → quarantined + audited
        st._load_degraded = degraded
        if isinstance(d, dict):
            try:
                st.energy = float(d.get("energy", ENERGY.e0))
                st.history = list(d.get("history", []))
                st.trail = list(d.get("trail", []))
                st.resplice = bool(d.get("resplice", False))
                st.goal_class = str(d.get("goal_class", "_default"))
                st.last_spliced_class = str(d.get("last_spliced_class", ""))
                st.classified_generation = str(d.get("classified_generation", ""))
                st.session_deposits = int(d.get("session_deposits", 0))
                st.injected_exons = list(d.get("injected_exons", []))
                st.action_buffer = list(d.get("action_buffer", []))
                st.wiki_active = list(d.get("wiki_active", []))
            except Exception:
                st._load_degraded = True   # partially parsed → refuse write-back (same law as a torn read)
        return st
