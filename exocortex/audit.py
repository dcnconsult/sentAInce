"""The audit trail — one append-only JSONL record per hook event.

Adapted from ``circle_of_fifths_rag/docs/HOST_INTEGRATION_BRIDGE_SPEC_v2.md`` §5: one schema for
both the Stage-0 baseline (observe-only) and later active runs, so the same record measures the
naked failure rates AND the treatment. ``answer_correct`` / ``was_confident_wrong`` are scored
post-hoc by ``score.py`` against the scenario's planted ground truth.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .config import state_dir


def _audit_path() -> str:
    return os.environ.get("EXOCORTEX_AUDIT", str(state_dir() / "audit.jsonl"))


def append(record: dict) -> None:
    """Append one record (best-effort; a hook must never crash the agent). When the epigenetic ledger is
    enabled (``integrity.audit_chain``), each record is hash-chained — ``hash = SHA256(payload ‖ prev_hash)``
    — so any silent edit to a past record snaps the chain (ADR-009). Fail-open: a hashing error writes the
    record unchained rather than dropping it.

    The whole read-tail→hash→append section runs under an advisory file lock (D7: two concurrent hook
    processes both read the same tail and forked the chain). The lock itself is fail-open — see
    ``integrity.append_lock``."""
    try:
        record.setdefault("ts", datetime.now(timezone.utc).isoformat())
        path = _audit_path()
        from .integrity import append_lock
        with append_lock(path):
            try:
                from .config import audit_chain_enabled
                if audit_chain_enabled():
                    from .integrity import chain_hash, tail_hash
                    record["prev"] = tail_hash(path)
                    record["hash"] = chain_hash(record, record["prev"])
            except Exception:
                record.pop("prev", None)
                record.pop("hash", None)        # fail-open → write unchained
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        pass


def record(*, session: str, event: str, mode: str, tool: str = "", command: str = "",
           command_key: str = "", signature: str = "",
           somatic_permitted: bool | None = None, somatic_organ: str = "",
           epistemic_decision: str = "", action: str = "",
           energy: float | None = None, tier: str = "", strategy_lock: int = 0,
           injected: bool = False, outcome: str = "", reason: str = "", output: str = "",
           seg_len: int = 0, wiki_injected: int = 0, wiki_used: int = 0) -> dict:
    """Build a flat audit record (the compliance + functional fields, spec §5). ``output`` is a
    truncated snippet of the observed stdout/stderr — lets judges verify ACTUAL execution vs a claim.
    ``seg_len`` = #edges in the colony segment a Bash consequence deposited (organ 3D telemetry: the live
    flail-then-succeed length distribution that decides when to flip ``eligibility_trace.mode`` on)."""
    return {
        "session": session, "event": event, "mode": mode, "tool": tool,
        "command": command, "command_key": command_key, "signature": signature,
        "somatic_permitted": somatic_permitted, "somatic_organ": somatic_organ,
        "epistemic_decision": epistemic_decision, "action": action,
        "energy": energy, "tier": tier, "strategy_lock": strategy_lock,
        "injected": injected, "outcome": outcome, "reason": reason, "output": output,
        "seg_len": seg_len,
        # declarative wiki attribution telemetry (only stamped when the organ ran this consequence) —
        # lets a planted-token testbed run score real precision, and Grafana plot the live credit rate.
        **({"wiki_injected": wiki_injected, "wiki_used": wiki_used} if (wiki_injected or wiki_used) else {}),
    }
