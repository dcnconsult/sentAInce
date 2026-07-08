"""guide-accrue#18 outcome A/B — arm logger + audit harvest (the first outcome-grade instrument).

Pre-registration: ``results/guide_accrue_ab_v1/PREREG.md`` (metric definitions there are binding; this
module implements them verbatim). Read-only over ``audit.jsonl``; the only thing it ever writes is the
arm-declaration log ``ab_arms.jsonl`` in the gitignored state dir — never τ, never any organism store.

    python -m exocortex.gauge.ab_outcome_gauge log-arm ON  --task P1a [--state-dir DIR]
    python -m exocortex.gauge.ab_outcome_gauge harvest --since 2026-07-08 [--state-dir DIR]
                                                       [--cls guide-accrue#18] [--json]

Stdlib-only, numpy-free; out of the 99-lock (its tests live beside the other gauge tests).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from itertools import combinations
from math import comb
from pathlib import Path
from statistics import median

ORIENTATION_VERBS = {"cd", "ls", "pwd", "cat", "dir"}          # PREREG §7 — the flail signature
CONTAMINATION_MARKS = (".claude/exocortex", "colony_", "recall_for_prompt", "recall_notes",
                       "recall_procedural")                     # PREREG C2 — store-read detector
ARM_JOIN_WINDOW_S = 30 * 60                                     # PREREG §7 — latest log-arm ≤ 30 min before
PERM_EXACT_LIMIT = 200_000                                      # PREREG §9
PERM_MC_DRAWS = 20_000
PERM_SEED = 20260708


def _state_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    from exocortex.config import state_dir
    return state_dir()


def _parse_ts(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ----------------------------------------------------------------------------- arm log
def arms_path(state_dir: Path) -> Path:
    return state_dir / "ab_arms.jsonl"


def log_arm(state_dir: Path, arm: str, task: str = "", now: datetime | None = None) -> dict:
    arm = arm.upper()
    if arm not in ("ON", "OFF"):
        raise SystemExit("arm must be ON or OFF")
    entry = {"ts": (now or datetime.now(timezone.utc)).isoformat(), "arm": arm, "task": task}
    p = arms_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def load_arms(state_dir: Path) -> list[dict]:
    p = arms_path(state_dir)
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if _parse_ts(e.get("ts", "")) and e.get("arm") in ("ON", "OFF"):
                    out.append(e)
            except Exception:
                continue
    return sorted(out, key=lambda e: e["ts"])


# ----------------------------------------------------------------------------- harvest
def _sessions(audit_path: Path, since: datetime | None) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    if not audit_path.exists():
        return by
    for line in audit_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        ts = _parse_ts(r.get("ts", ""))
        if ts is None or (since and ts < since):
            continue
        r["_ts"] = ts
        by.setdefault(str(r.get("session", "")), []).append(r)
    for recs in by.values():
        recs.sort(key=lambda r: r["_ts"])
    return by


def _cls_of(recs: list[dict]) -> str:
    for r in recs:
        if r.get("event") == "UserPromptSubmit":
            reason = str(r.get("reason", ""))
            if reason.startswith("class="):
                return reason[6:]
            return ""
    return ""


def _verb(command_key: str) -> str:
    return (command_key or "").split()[0] if (command_key or "").split() else ""


def session_metrics(sid: str, recs: list[dict]) -> dict:
    pre = [r for r in recs if r.get("event") == "PreToolUse"]
    contaminated = any(m in str(r.get("command", "")) for r in pre for m in CONTAMINATION_MARKS)
    return {
        "session": sid,
        "start": recs[0]["_ts"].isoformat(),
        "cls": _cls_of(recs),
        "total_steps": len(pre),                                                   # PRIMARY
        "orientation_reads": sum(1 for r in pre if _verb(r.get("command_key", "")) in ORIENTATION_VERBS),
        "failures": sum(1 for r in recs if r.get("event") == "PostToolUseFailure"),
        "ok": sum(1 for r in recs if r.get("event") == "PostToolUse"),
        "duration_s": round((recs[-1]["_ts"] - recs[0]["_ts"]).total_seconds(), 1),
        "contaminated": contaminated,
    }


def join_arms(sessions: list[dict], arms: list[dict]) -> None:
    """Assign each session the LATEST arm entry ≤30 min before its start (PREREG C4/§7); a log-arm entry
    may back at most one session — a second match is flagged ambiguous (both sessions excluded E3)."""
    claimed: dict[int, str] = {}
    for s in sorted(sessions, key=lambda x: x["start"]):
        t0 = _parse_ts(s["start"])
        best = None
        for i, e in enumerate(arms):
            et = _parse_ts(e["ts"])
            if et and et <= t0 and (t0 - et).total_seconds() <= ARM_JOIN_WINDOW_S:
                best = i
        if best is None:
            s["arm"], s["task"] = "", ""
        elif best in claimed:
            s["arm"], s["task"] = "AMBIGUOUS", arms[best].get("task", "")
        else:
            claimed[best] = s["session"]
            s["arm"], s["task"] = arms[best]["arm"], arms[best].get("task", "")


def apply_exclusions(sessions: list[dict], target_cls: str) -> tuple[list[dict], list[dict]]:
    included, excluded = [], []
    for s in sessions:
        why = []
        if s["cls"] != target_cls:
            why.append("E1 wrong class (%s)" % (s["cls"] or "none"))
        if s["contaminated"]:
            why.append("E2 store-read contamination")
        if s["arm"] not in ("ON", "OFF"):
            why.append("E3 no/ambiguous arm")
        if s["total_steps"] == 0:
            why.append("E4 zero steps")
        (excluded if why else included).append({**s, "excluded": why} if why else s)
    return included, excluded


def permutation_p(on: list[float], off: list[float]) -> tuple[float, str]:
    """One-sided (ON < OFF) permutation test on the difference of medians (PREREG §9)."""
    if not on or not off:
        return 1.0, "insufficient"
    pool, n_on = on + off, len(on)
    observed = median(on) - median(off)
    idx = range(len(pool))
    total = comb(len(pool), n_on)
    hits = draws = 0
    if total <= PERM_EXACT_LIMIT:
        for pick in combinations(idx, n_on):
            pset = set(pick)
            a = [pool[i] for i in pset]
            b = [pool[i] for i in idx if i not in pset]
            draws += 1
            if median(a) - median(b) <= observed:
                hits += 1
        return hits / draws, "exact(%d)" % draws
    rng = random.Random(PERM_SEED)
    for _ in range(PERM_MC_DRAWS):
        pick = rng.sample(list(idx), n_on)
        pset = set(pick)
        a = [pool[i] for i in pset]
        b = [pool[i] for i in idx if i not in pset]
        draws += 1
        if median(a) - median(b) <= observed:
            hits += 1
    return hits / draws, "mc(%d,seed=%d)" % (draws, PERM_SEED)


def harvest(state_dir: Path, since: datetime | None, target_cls: str) -> dict:
    by = _sessions(state_dir / "audit.jsonl", since)
    sessions = [session_metrics(sid, recs) for sid, recs in by.items() if recs]
    join_arms(sessions, load_arms(state_dir))
    included, excluded = apply_exclusions(sessions, target_cls)
    arms: dict[str, list[dict]] = {"ON": [], "OFF": []}
    for s in included:
        arms[s["arm"]].append(s)
    agg = {}
    for arm, ss in arms.items():
        if ss:
            agg[arm] = {
                "n": len(ss),
                "median_total_steps": median(s["total_steps"] for s in ss),
                "median_orientation": median(s["orientation_reads"] for s in ss),
                "median_failures": median(s["failures"] for s in ss),
                "median_duration_s": median(s["duration_s"] for s in ss),
            }
    p, method = permutation_p([float(s["total_steps"]) for s in arms["ON"]],
                              [float(s["total_steps"]) for s in arms["OFF"]])
    return {"target_cls": target_cls, "included": included, "excluded": excluded,
            "aggregate": agg, "primary_one_sided_p": p, "p_method": method}


def _print_report(rep: dict) -> None:
    print(f"guide-accrue A/B harvest — class {rep['target_cls']}")
    for arm in ("ON", "OFF"):
        a = rep["aggregate"].get(arm)
        print(f"  {arm:3s}: " + (f"n={a['n']}  steps~{a['median_total_steps']}  "
                                 f"orient~{a['median_orientation']}  fails~{a['median_failures']}  "
                                 f"dur~{a['median_duration_s']}s" if a else "n=0"))
    print(f"  primary (ON<OFF, total_steps): p={rep['primary_one_sided_p']:.4f} [{rep['p_method']}]")
    print(f"  included {len(rep['included'])} · excluded {len(rep['excluded'])}")
    for s in rep["included"]:
        print(f"    [{s['arm']:3s}] {s.get('task') or '-':5s} steps={s['total_steps']:3d} "
              f"orient={s['orientation_reads']:2d} fails={s['failures']} dur={s['duration_s']}s  {s['session'][:12]}")
    for s in rep["excluded"]:
        print(f"    [EXCL] {s['session'][:12]}  {'; '.join(s['excluded'])}")
    print("  (numbers are the measurement; the PREREG §9 rule renders the disposition — not this tool)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="exocortex.gauge.ab_outcome_gauge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("log-arm"); pl.add_argument("arm", choices=["ON", "OFF", "on", "off"])
    pl.add_argument("--task", default=""); pl.add_argument("--state-dir", default=None)
    ph = sub.add_parser("harvest"); ph.add_argument("--state-dir", default=None)
    ph.add_argument("--since", default=""); ph.add_argument("--cls", default="guide-accrue#18")
    ph.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    sd = _state_dir(a.state_dir)
    if a.cmd == "log-arm":
        e = log_arm(sd, a.arm, a.task)
        print(f"logged arm={e['arm']} task={e['task'] or '-'} at {e['ts']} → {arms_path(sd)}")
        return 0
    since = _parse_ts(a.since + ("T00:00:00+00:00" if a.since and "T" not in a.since else "")) if a.since else None
    rep = harvest(sd, since, a.cls)
    if a.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        _print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
