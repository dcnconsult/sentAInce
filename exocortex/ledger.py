"""The Suggestion Ledger — the human as a body (ADR-010 · ENHANCEMENTS §G6).

ADR-010 concentrates authority to *act* in the frozen gate + the body, and notes that when a suggestion
needs a *human* decision (a §G1 hand-off, a design recommendation, a Tuner rec) the **human is the body**:
the consequence is *taken-and-it-worked* — the human analog of `exit 0`. This module is the append-only,
hash-chained record of that loop.

The load-bearing law (ADR-001): **credit attaches only to a verified-good OUTCOME, never to the selection.**
Taking a suggestion is *retrieval*; rewarding the choice would reimport popularity-as-utility. So `credit` is
not a stored, writable field — it is *derived* by folding the event log: a suggestion is credited iff a later
`outcome` event records `outcome == "good"`. You cannot write credit directly; only a real outcome earns it.

Design — event-sourced and append-only, like the audit trail (never mutate a past row):
  - a `suggestion` event : {id, source, suggestion, options, rationale, selection, selected_at}
  - an `outcome` event   : {id, outcome in good|bad|reverted|unknown, evidence, at}
  - `state()` folds events by id into the current view (+ the derived `credited` flag).

Each line is hash-chained (`hash = SHA256(payload || prev_hash)`, reusing `exocortex.integrity`) so the
ledger doubles as the G1 responsibility ledger — any silent edit to a past decision snaps the chain. Stdlib
only; fail-open on write (a logging error never raises into the caller). The ledger lives at
`~/.exocortex/suggestion_ledger.jsonl` (override `EXOCORTEX_SUGGESTION_LEDGER`), global across repos/sessions
like the Tuner journal — these are cross-session human decisions, not per-repo hook state.

This is the v1 data layer for §G6. It is NOT wired into any hook (dormant-by-default, ADR-003): rows are
written by whoever presents the suggestion (the assistant via `record_suggestion`, or a future
`AskUserQuestion` capture). Gauge-first (ADR-002): `summary()` is the instrument for "does uptake correlate
with a good outcome?" — measure before wiring any credit back into the colony/wiki.
"""
from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

SELECTIONS = ("take", "modify", "decline", "defer")
OUTCOMES = ("good", "bad", "reverted", "unknown")
SOURCES = ("assistant", "tuner", "G1-escalate", "dream", "other")  # advisory only, not enforced


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ledger_path(path=None) -> Path:
    """Resolve the ledger file: explicit arg > ``EXOCORTEX_SUGGESTION_LEDGER`` > ~/.exocortex/…jsonl."""
    if path is not None:
        return Path(path)
    env = os.environ.get("EXOCORTEX_SUGGESTION_LEDGER")
    return Path(env) if env else Path.home() / ".exocortex" / "suggestion_ledger.jsonl"


# ----------------------------------------------------------------- append (hash-chained, fail-open)
def append_event(event: dict, *, path=None) -> dict:
    """Append one event as a hash-chained JSONL line. Fail-open: a write/hash error is swallowed so the
    caller (often a live assistant turn) never crashes. Returns the event with chain fields stamped."""
    p = ledger_path(path)
    event.setdefault("ts", _now())
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            from .integrity import chain_hash, tail_hash
            event["prev"] = tail_hash(p)
            event["hash"] = chain_hash(event, event["prev"])
        except Exception:
            event.pop("prev", None)
            event.pop("hash", None)  # fail-open -> write unchained rather than drop
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")
    except Exception:
        pass
    return event


def record_suggestion(*, suggestion: str, selection: str, source: str = "assistant",
                      options=None, rationale: str = "", id: str | None = None, path=None) -> str:
    """Log a suggestion that was offered and the human's selection; return the suggestion id. Recording a
    selection deposits NO credit (ADR-001) — credit is earned only by a later good `outcome`."""
    if selection not in SELECTIONS:
        raise ValueError(f"selection must be one of {SELECTIONS}, got {selection!r}")
    sid = id or f"sug-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6]}"
    append_event({
        "event": "suggestion", "id": sid, "source": source,
        "suggestion": suggestion, "options": list(options or SELECTIONS),
        "rationale": rationale, "selection": selection, "selected_at": _now(),
    }, path=path)
    return sid


def record_outcome(id: str, outcome: str, *, evidence: str = "", path=None) -> dict:
    """Log the (deferred) outcome of a previously-recorded suggestion. Only ``outcome == "good"`` causes the
    suggestion to be credited by `state()` — never the selection."""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")
    return append_event({"event": "outcome", "id": id, "outcome": outcome,
                         "evidence": evidence, "at": _now()}, path=path)


# ----------------------------------------------------------------- read / fold
def load_events(path=None) -> list:
    """All events, in append order. Malformed lines are skipped (fail-open)."""
    p = ledger_path(path)
    out: list = []
    if not p.exists():
        return out
    try:
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def is_credited(row: dict) -> bool:
    """THE LAW IN CODE (ADR-001): a suggestion is credited iff a real outcome says it WORKED. A selection —
    even 'take' — never credits; decline/defer/bad/reverted/unknown/no-outcome never credit."""
    return row.get("outcome") == "good"


def state(path=None) -> dict:
    """Fold the event log into the current view keyed by suggestion id. Each row carries the suggestion
    fields, the latest outcome (if any), and the DERIVED `credited` flag (never stored, never writable)."""
    rows: dict = {}
    for ev in load_events(path):
        sid = ev.get("id")
        if not sid:
            continue
        row = rows.setdefault(sid, {"id": sid})
        if ev.get("event") == "suggestion":
            for k in ("source", "suggestion", "options", "rationale", "selection", "selected_at"):
                if k in ev:
                    row[k] = ev[k]
        elif ev.get("event") == "outcome":
            row["outcome"] = ev.get("outcome")
            row["outcome_evidence"] = ev.get("evidence", "")
            row["outcome_at"] = ev.get("at")
    for row in rows.values():
        row["credited"] = is_credited(row)
    return rows


def summary(path=None) -> dict:
    """The gauge-first instrument (ADR-002): uptake and outcome rates — does taking a suggestion correlate
    with a good outcome, or is selection noise? Measure before wiring any credit back into the colony."""
    rows = list(state(path).values())
    total = len(rows)
    taken = sum(1 for r in rows if r.get("selection") == "take")
    with_outcome = [r for r in rows if r.get("outcome")]
    good = sum(1 for r in rows if r.get("outcome") == "good")
    return {
        "total": total,
        "by_selection": {s: sum(1 for r in rows if r.get("selection") == s) for s in SELECTIONS},
        "by_outcome": {o: sum(1 for r in rows if r.get("outcome") == o) for o in OUTCOMES},
        "uptake_rate": round(taken / total, 3) if total else None,
        "good_rate": round(good / len(with_outcome), 3) if with_outcome else None,
        "credited": sum(1 for r in rows if r.get("credited")),
        "pending_outcome": total - len(with_outcome),
    }


def verify(path=None) -> dict:
    """Chain integrity of the ledger (the G1 responsibility-ledger property). Reuses the audit verifier."""
    try:
        from .integrity import verify_audit
        return verify_audit(ledger_path(path))
    except Exception as e:  # pragma: no cover - import guard
        return {"ok": False, "message": f"verify unavailable: {e}"}


# ----------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Exocortex Suggestion Ledger — the human as a body (§G6)")
    ap.add_argument("--path", default=None, help="ledger path (default ~/.exocortex/suggestion_ledger.jsonl)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--summary", action="store_true", help="print uptake/outcome stats (default)")
    g.add_argument("--list", action="store_true", help="print the folded per-suggestion state")
    g.add_argument("--verify", action="store_true", help="check the hash-chain integrity")
    g.add_argument("--record", action="store_true", help="append a suggestion event")
    g.add_argument("--outcome", nargs=2, metavar=("ID", "OUTCOME"), help="append an outcome event")
    ap.add_argument("--source", default="assistant")
    ap.add_argument("--suggestion", default="")
    ap.add_argument("--selection", default="take", choices=SELECTIONS)
    ap.add_argument("--rationale", default="")
    ap.add_argument("--evidence", default="")
    args = ap.parse_args(argv)

    if args.record:
        print(record_suggestion(suggestion=args.suggestion, selection=args.selection,
                                source=args.source, rationale=args.rationale, path=args.path))
        return 0
    if args.outcome:
        sid, outcome = args.outcome
        if outcome not in OUTCOMES:
            print(f"outcome must be one of {OUTCOMES}")
            return 2
        record_outcome(sid, outcome, evidence=args.evidence, path=args.path)
        print(f"outcome recorded for {sid}: {outcome}")
        return 0
    if args.list:
        print(json.dumps(state(args.path), indent=2))
        return 0
    if args.verify:
        print(json.dumps(verify(args.path), indent=2))
        return 0
    print(json.dumps(summary(args.path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
