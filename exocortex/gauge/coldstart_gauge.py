"""Offline COLD-START gauge (Cursor first-turn miss) — how often does the unreliable first
``beforeSubmitPrompt`` / ``sessionStart`` (Cursor beta) cost a deposit? (STATS)

Sizes the prize of the parked lazy-init fix (arc Task #4 / limitation L9) BEFORE building it (gauge-first,
ADR-002). On Cursor the FIRST ``beforeSubmitPrompt`` of a session sometimes doesn't fire → that turn's
``handle_userpromptsubmit`` never runs → ``goal_class`` stays ``_default`` and the trail is empty → the first
exit-0 consequence deposits nothing (``seg_len 0``), and any deposits before the first prompt bind to
``_default``. It is BOUNDED to the first prompt (the 2nd+ prompts' ``beforeSubmitPrompt`` fire and re-seed).

Measured per session from ``audit.jsonl`` (chronological append order), read-only, pure-stdlib, fail-open:
  - **cold-start session** = a PreToolUse/consequence appears BEFORE the session's first UserPromptSubmit
    (or the session has tool activity but no UserPromptSubmit at all);
  - **lost deposit** = an exit-0 consequence before the first UserPromptSubmit with ``seg_len`` 0/absent
    (the deposit the empty trail skipped);
  - **sessionStart miss** = a session with tool activity but no SessionStart record.

Claude Code fires UserPromptSubmit reliably → its repos read ~0; the signal lives in the CURSOR repos.

  python -m exocortex.gauge.coldstart_gauge                    # auto-scan sibling repos' live audits
  python -m exocortex.gauge.coldstart_gauge --audit P [...]     # explicit audit.jsonl path(s)
  python -m exocortex.gauge.coldstart_gauge --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOL_EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure")
_CONS_EVENTS = ("PostToolUse", "PostToolUseFailure")

# Flip-trigger thresholds for building the lazy-init fix (Task #4). Below → park (L9, document only).
COLD_START_THRESHOLD = 0.10     # ≥10% of tool-using sessions cold-start
MIN_LOST_DEPOSITS = 3           # AND at least this many deposits actually lost (material, not one-off)


def load(path) -> list:
    out: list = []
    p = Path(path)
    if not p.is_file():
        return out
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def analyze(records: list) -> dict:
    """Per-session cold-start accounting over one audit's records (already in chronological append order)."""
    sessions: dict = {}
    for r in records:
        sessions.setdefault(r.get("session") or "?", []).append(r)

    n_sessions = cold = no_start = lost = default_cons = ok_cons = 0
    for recs in sessions.values():
        evs = [r.get("event") for r in recs]
        if not any(e in _TOOL_EVENTS for e in evs):
            continue                                  # a prompt-only / setup session — not at risk
        n_sessions += 1
        if "SessionStart" not in evs:
            no_start += 1
        first_ups = next((i for i, e in enumerate(evs) if e == "UserPromptSubmit"), None)
        first_tool = next((i for i, e in enumerate(evs) if e in _TOOL_EVENTS), None)
        for r in recs:                                # denominator: all exit-0 consequences
            if r.get("event") in _CONS_EVENTS and r.get("outcome") == "ok":
                ok_cons += 1
        is_cold = (first_ups is None) or (first_tool is not None and first_tool < first_ups)
        if not is_cold:
            continue
        cold += 1
        cutoff = first_ups if first_ups is not None else len(recs)
        for r in recs[:cutoff]:                       # consequences before the first prompt fired
            if r.get("event") in _CONS_EVENTS and r.get("outcome") == "ok":
                default_cons += 1                     # would bind to _default (class misattribution)
                sl = r.get("seg_len")
                if not (isinstance(sl, int) and sl > 0):
                    lost += 1                          # empty trail → deposit skipped entirely
    return {
        "sessions": n_sessions,
        "cold_start_sessions": cold,
        "sessionstart_miss": no_start,
        "lost_deposits": lost,
        "default_class_consequences": default_cons,
        "ok_consequences": ok_cons,
        "cold_start_rate": round(cold / n_sessions, 3) if n_sessions else None,
        "sessionstart_miss_rate": round(no_start / n_sessions, 3) if n_sessions else None,
        "lost_deposit_rate": round(lost / ok_cons, 3) if ok_cons else None,
    }


def verdict(m: dict) -> dict:
    build = ((m["cold_start_rate"] or 0.0) >= COLD_START_THRESHOLD and m["lost_deposits"] >= MIN_LOST_DEPOSITS)
    return {
        "lazy_init": {
            "signal": build, "metric": "cold_start_rate", "value": m["cold_start_rate"],
            "lost_deposits": m["lost_deposits"],
            "note": "Task #4 / L9 — build the transcript-recovery lazy-init only if the first-turn miss "
                    "materially loses deposits; else document. Cursor-specific (Claude fires UserPromptSubmit "
                    "reliably → ~0). Sized on the multi-model Cursor soak.",
        },
    }


def discover(scan_root: Path) -> list:
    found = []
    if scan_root.is_dir():
        for child in sorted(scan_root.iterdir()):
            a = child / ".claude" / "exocortex" / "audit.jsonl"
            if a.is_file():
                found.append(a)
    return found


def run(audit_paths: list | None = None, scan_root: Path | None = None) -> dict:
    paths = [Path(p) for p in (audit_paths or [])]
    if not paths:
        paths = discover(scan_root or _REPO_ROOT.parent)
    per_repo, pooled = [], []
    for p in paths:
        recs = load(p)
        if not recs:
            continue
        per_repo.append({"repo": p.parents[2].name, **analyze(recs)})
        pooled.extend(recs)
    agg = analyze(pooled)
    return {"per_repo": per_repo, "aggregate": agg, "verdict": verdict(agg),
            "thresholds": {"cold_start_rate": COLD_START_THRESHOLD, "min_lost_deposits": MIN_LOST_DEPOSITS}}


def _fmt(res: dict) -> str:
    L = ["COLD-START GAUGE  (Cursor first-turn beforeSubmitPrompt/sessionStart miss → lost deposit)", ""]
    for r in res["per_repo"]:
        L.append(f"  [{r['repo']}] sessions={r['sessions']} cold={r['cold_start_sessions']} "
                 f"(rate={r['cold_start_rate']}) ss_miss={r['sessionstart_miss']} lost_deposits={r['lost_deposits']} "
                 f"default_cons={r['default_class_consequences']}")
    a = res["aggregate"]
    L += ["", f"AGGREGATE: sessions={a['sessions']} cold_start={a['cold_start_sessions']} "
              f"(rate={a['cold_start_rate']}) · sessionStart_miss={a['sessionstart_miss']} "
              f"(rate={a['sessionstart_miss_rate']})",
          f"  lost_deposits={a['lost_deposits']} (of {a['ok_consequences']} exit-0 cons; "
          f"rate={a['lost_deposit_rate']}) · default-class cons={a['default_class_consequences']}",
          "", "VERDICT:"]
    v = res["verdict"]["lazy_init"]
    L += [f"  lazy_init (Task #4): signal={v['signal']}  cold_start_rate={v['value']}  lost_deposits={v['lost_deposits']}",
          f"       {v['note']}"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cold-start gauge (Cursor first-turn miss → lost deposit; Task #4)")
    ap.add_argument("--audit", action="append", default=[], help="explicit audit.jsonl path (repeatable)")
    ap.add_argument("--scan-root", default=None, help="dir to scan for */.claude/exocortex/audit.jsonl")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    res = run(args.audit or None, Path(args.scan_root) if args.scan_root else None)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
