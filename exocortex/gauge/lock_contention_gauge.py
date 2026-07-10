"""Offline LOCK-CONTENTION gauge (ADR-020 W4) — gauge-first, ADR-002.

The write-integrity arc (W1 atomic replace · W2 torn-store quarantine · W3 colony lock) closes the
corruption class the cursor_testbed Codex probe demonstrated (torn rows + chain forks under subagent
fan-out). What it deliberately does NOT decide is whether the FAIL-OPEN lock timeout (2 s,
``integrity.append_lock``) is ever actually hit at flagship fan-out — the one residual unlocked
window. That question sizes the parked single-writer daemon, and it is measurable on the EXISTING
audit store before any daemon is built:

  - **fail-open rate** — consequence rows carrying ``lock_failopen`` (omit-when-zero: absent = clean
    acquisition). Rate 0 → W1–W3 close the whole exposure; the daemon stays PARKED.
  - **store integrity** — torn/unparseable audit lines (the pre-W1 tearing signature) and the hash
    chain via ``integrity.verify_audit``.
  - **quarantine incidents** — ``StoreQuarantine`` rows (W2 fired) + ``*.corrupt-*`` files on disk.

Read-only, self-contained, numpy-free — the same fail-open discipline as the hook. STATS-first; the
verdict is a thin threshold the numbers drive.

  python -m exocortex.gauge.lock_contention_gauge                  # this repo's live state dir
  python -m exocortex.gauge.lock_contention_gauge --state-dir P    # explicit state dir(s) (repeatable)
  python -m exocortex.gauge.lock_contention_gauge --json           # machine-readable (results file / CI)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]            # gauge -> exocortex -> repo root
_CONS = ("PostToolUse", "PostToolUseFailure")
FAILOPEN_RATE_THRESHOLD = 0.01   # ≥1% of consequence rows fail-open → contention is real → size the daemon


def gauge_state_dir(state_dir) -> dict:
    """All stats for one ``.claude/exocortex`` state dir. Read-only, fail-open."""
    sd = Path(state_dir)
    audit = sd / "audit.jsonl"
    total_lines = parse_fail = cons_rows = failopen_rows = failopen_sum = quarantine_rows = 0
    if audit.exists():
        for line in audit.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            total_lines += 1
            try:
                row = json.loads(line)
            except Exception:
                parse_fail += 1                             # the pre-W1 tearing signature
                continue
            ev = str(row.get("event", ""))
            if ev in _CONS:
                cons_rows += 1
                lf = int(row.get("lock_failopen", 0) or 0)
                if lf:
                    failopen_rows += 1
                    failopen_sum += lf
            elif ev == "StoreQuarantine":
                quarantine_rows += 1
    chain = {"ok": None, "records": 0, "chained": 0, "message": "verify unavailable"}
    try:
        from exocortex.integrity import verify_audit
        v = verify_audit(audit)
        chain = {"ok": bool(v.get("ok", False)), "records": int(v.get("records", 0)),
                 "chained": int(v.get("chained", 0)), "message": str(v.get("message", ""))}
        if "first_break" in v:
            chain["first_break"] = v["first_break"]
    except Exception:
        pass
    corrupt_files = sorted(p.name for p in sd.glob("*.corrupt-*"))
    rate = (failopen_rows / cons_rows) if cons_rows else 0.0
    try:                                       # banked artifacts must be portable: never leak an
        shown = str(sd.resolve().relative_to(_REPO_ROOT.resolve()))   # absolute machine-local path
    except ValueError:
        shown = sd.name
    return {
        "state_dir": shown,
        "audit_lines": total_lines, "torn_lines": parse_fail,
        "consequence_rows": cons_rows,
        "lock_failopen_rows": failopen_rows, "lock_failopen_sum": failopen_sum,
        "lock_failopen_rate": round(rate, 5),
        "quarantine_rows": quarantine_rows, "corrupt_files": corrupt_files,
        "chain": chain,
    }


def verdict(stats: list[dict]) -> dict:
    """Thin threshold over the numbers (REASONING_DISCIPLINE: the stats drive it, not the narrative)."""
    cons = sum(s["consequence_rows"] for s in stats)
    fo = sum(s["lock_failopen_rows"] for s in stats)
    torn = sum(s["torn_lines"] for s in stats)
    rate = (fo / cons) if cons else 0.0
    if cons == 0:
        line = "0 — no consequence rows observed yet; re-run after live traffic"
    elif rate >= FAILOPEN_RATE_THRESHOLD:
        line = (f"-1 for W1-W3-only — fail-open rate {rate:.2%} ≥ {FAILOPEN_RATE_THRESHOLD:.0%}: "
                "contention is real at this traffic; size the single-writer daemon")
    else:
        line = (f"+1 for W1-W3 sufficiency at observed traffic — fail-open rate {rate:.2%} "
                f"< {FAILOPEN_RATE_THRESHOLD:.0%}; the single-writer daemon stays PARKED")
    return {"consequence_rows": cons, "lock_failopen_rows": fo, "torn_lines": torn,
            "failopen_rate": round(rate, 5), "verdict": line}


def main() -> int:
    ap = argparse.ArgumentParser(description="ADR-020 W4 lock-contention gauge (read-only)")
    ap.add_argument("--state-dir", action="append", default=[],
                    help="explicit .claude/exocortex dir (repeatable); default: this repo's")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    dirs = args.state_dir or [str(_REPO_ROOT / ".claude" / "exocortex")]
    stats = [gauge_state_dir(d) for d in dirs]
    out = {"gauge": "lock_contention_v1", "per_state_dir": stats, "summary": verdict(stats)}
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for s in stats:
            print(f"[{s['state_dir']}]")
            print(f"  audit lines {s['audit_lines']} · torn {s['torn_lines']} · "
                  f"consequences {s['consequence_rows']} · fail-open rows {s['lock_failopen_rows']} "
                  f"(rate {s['lock_failopen_rate']:.2%})")
            print(f"  quarantine rows {s['quarantine_rows']} · corrupt files {len(s['corrupt_files'])} · "
                  f"chain ok={s['chain'].get('ok')} chained={s['chain'].get('chained')} "
                  f"({s['chain'].get('message', '')})")
        print("verdict:", out["summary"]["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
