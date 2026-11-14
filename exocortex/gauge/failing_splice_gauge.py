"""Failing-Splice Gauge — how often does a spliced route fail, and does the memory keep offering it? (avenue 2)

τ decay is clocked by SUCCESSFUL deposits in a class (plus one pass per sleep), and a failure deposits
nothing, so a recommended route that starts failing is never weakened by its failures. The audit records THAT
a splice was injected but not WHICH route, so this gauge replays each store's colony in file order,
reconstructs every turn's dominant route, and measures: how often the agent follows it, how often the route
command then fails (vs the same verbs off-route), and how long the contradicted route keeps being spliced.

Frozen protocol: ``results/failing_splice_v1/PREREG.md``. Read-only, pure stdlib, deterministic (fixed
seed), fail-open on malformed rows. Emits numbers only — never command text, class labels or paths. The
replay is an approximation of the live colony (PREREG §3); a run over a live repo is a labeled demonstration.

  python -m exocortex.gauge.failing_splice_gauge --audit A.jsonl --label A [--working-from A=EPOCH] --json
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import statistics
from datetime import datetime
from pathlib import Path

from exocortex.colony import verb_node

DECAY, DEPOSIT, PRUNE, CAP = 0.9, 1.0, 0.05, 32   # PREREG §3 (the shipped thermodynamics)
MIN_DEPOSITS_TO_SPLICE, MAX_PATH = 2, 6
EVALUABLE_FOLLOWED = 30                            # PREREG §5
X_PASS, X_FAIL = 0.10, 0.05
BOOT_N, BOOT_SEED = 1000, 20261026
_CMD = ("bash:", "ps:")
_CONS = ("PostToolUse", "PostToolUseFailure")


class ReplayColony:
    """The live ``Colony`` dynamics at weight 1.0 (PREREG §3): decay-all, reinforce the path, prune, cap at sleep."""

    def __init__(self):
        self.tau: dict = {}
        self.deposits = 0

    def deposit(self, es: list) -> None:
        if not es:
            return
        for k in list(self.tau):
            self.tau[k] *= DECAY
        for a, b in es:
            if a != b:
                self.tau[(a, b)] = self.tau.get((a, b), 0.0) + DEPOSIT
        self.tau = {k: w for k, w in self.tau.items() if w >= PRUNE}
        self.deposits += 1

    def consolidate(self) -> None:
        for k in list(self.tau):
            self.tau[k] *= DECAY
        self.tau = {k: w for k, w in self.tau.items() if w >= PRUNE}
        if len(self.tau) > CAP:
            self.tau = dict(sorted(self.tau.items(), key=lambda kv: -kv[1])[:CAP])

    def dominant_path(self) -> list:
        """``Colony.dominant_path``: greedy widest walk from the strongest edge's source."""
        if not self.tau:
            return []
        cur = max(self.tau, key=lambda e: self.tau[e])[0]
        path = [cur]
        while len(path) < MAX_PATH:
            outs = [(b, w) for (a, b), w in self.tau.items() if a == cur and b not in path]
            if not outs:
                break
            cur = max(outs, key=lambda x: x[1])[0]
            path.append(cur)
        return path


def _epoch(r: dict):
    try:
        return datetime.fromisoformat(str(r.get("ts"))).timestamp()
    except Exception:
        return None


def replay(records, working_from: float | None = None) -> list:
    """PREREG §3: one dict per prompt-turn — its class, whether it was spliced, the spliced dominant path, its
    command nodes, the turn's consequences ``(node, ok)`` in order, and the class deposit count at the prompt."""
    cols: dict = collections.defaultdict(ReplayColony)
    cls_of: dict = collections.defaultdict(lambda: "_default")
    trails: dict = {}
    current: dict = {}
    turns: list = []
    for r in records:
        s = str(r.get("session", r.get("session_id", "")))
        ev = r.get("event")
        ts = _epoch(r)
        keying = "working" if (working_from is not None and ts is not None and ts >= working_from) else "first"
        if ev == "UserPromptSubmit":
            m = re.match(r"class=(.+)", str(r.get("reason") or ""))
            cls = m.group(1) if m else "_default"
            cls_of[s] = cls
            trails[s] = [f"cue:{cls}"]
            col = cols[cls]
            path = col.dominant_path() if col.deposits >= MIN_DEPOSITS_TO_SPLICE else []
            cmd = {n for n in path if n.startswith(_CMD)}
            spliced = bool(r.get("injected")) and len(path) >= 2 and bool(cmd)
            t = {"session": s, "cls": cls, "spliced": spliced, "path": tuple(path) if spliced else None,
                 "cmd": cmd if spliced else set(), "cons": [], "deposits_at_prompt": col.deposits}
            turns.append(t)
            current[s] = t
        elif ev == "PreToolUse" and r.get("tool"):
            trails.setdefault(s, [f"cue:{cls_of[s]}"]).append(
                verb_node(str(r["tool"]), str(r.get("command") or ""), keying=keying))
        elif ev in _CONS and r.get("tool") in ("Bash", "PowerShell"):
            ok = ev == "PostToolUse" and r.get("outcome", "ok") == "ok"
            node = verb_node(str(r["tool"]), str(r.get("command") or ""), keying=keying)
            cue = f"cue:{cls_of[s]}"
            trail = trails.get(s, [cue])
            if ok:
                cols[cls_of[s]].deposit([(a, b) for a, b in zip(trail, trail[1:]) if a != b])
                trails[s] = [cue, node]
            else:
                trails[s] = [cue]
            if s in current:
                current[s]["cons"].append((node, ok))
        elif ev in ("PreCompact", "CircadianSleep"):
            for c in cols.values():
                c.consolidate()
    return turns


def samples(turns: list) -> tuple:
    """Route samples ``(session, verb, contradicted)`` for followed turns, and off-route samples
    ``(session, verb, failed)`` — the first consequence of each verb in a turn where it is not a route command."""
    route, off = [], []
    for t in turns:
        first: dict = {}
        for node, ok in t["cons"]:
            first.setdefault(node, ok)
        rc = next(((n, ok) for n, ok in t["cons"] if n in t["cmd"]), None)
        if t["spliced"] and rc is not None:
            t["followed"], t["contradicted"] = True, not rc[1]
            route.append((t["session"], rc[0], int(not rc[1])))
        else:
            t["followed"], t["contradicted"] = False, False
        for node, ok in first.items():
            if node not in t["cmd"]:
                off.append((t["session"], node, int(not ok)))
    return route, off


def excess(route: list, off: list) -> tuple:
    """PREREG §4 E: verb-stratified (route-failure − off-route-failure), weighted by followed turns per verb."""
    rv, ov = collections.defaultdict(list), collections.defaultdict(list)
    for _, v, x in route:
        rv[v].append(x)
    for _, v, x in off:
        ov[v].append(x)
    num = den = dropped = 0
    for v, xs in rv.items():
        if not ov.get(v):
            dropped += len(xs)
            continue
        num += len(xs) * (sum(xs) / len(xs) - sum(ov[v]) / len(ov[v]))
        den += len(xs)
    return (num / den if den else None), dropped


def bootstrap_ci(route: list, off: list, n: int = BOOT_N, seed: int = BOOT_SEED) -> tuple:
    by_r, by_o = collections.defaultdict(list), collections.defaultdict(list)
    for x in route:
        by_r[x[0]].append(x)
    for x in off:
        by_o[x[0]].append(x)
    sessions = sorted(set(by_r) | set(by_o))
    if not sessions:
        return None, None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        pick = rng.choices(sessions, k=len(sessions))
        v, _ = excess([x for s in pick for x in by_r[s]], [x for s in pick for x in by_o[s]])
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None
    vals.sort()
    return vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]


def persistence(turns: list) -> dict:
    """PREREG §4 P: after each contradiction, later spliced turns in the class still splicing the same path."""
    by_cls = collections.defaultdict(list)
    for t in turns:
        if t["spliced"]:
            by_cls[t["cls"]].append(t)
    ps, deposited_before_next = [], []
    for seq in by_cls.values():
        for i, t in enumerate(seq):
            if not t.get("contradicted"):
                continue
            p = 0
            for u in seq[i + 1:]:
                if u["path"] != t["path"]:
                    break
                p += 1
            ps.append(p)
            if i + 1 < len(seq):
                deposited_before_next.append(int(seq[i + 1]["deposits_at_prompt"] > t["deposits_at_prompt"]))
    return {"contradictions": len(ps), "P_median": statistics.median(ps) if ps else None,
            "P_share_ge2": round(sum(1 for p in ps if p >= 2) / len(ps), 4) if ps else None,
            "deposit_before_next_share": (round(sum(deposited_before_next) / len(deposited_before_next), 4)
                                          if deposited_before_next else None)}


def measure(turns: list, boot: int = BOOT_N) -> dict:
    route, off = samples(turns)
    n = sum(1 for t in turns if t["spliced"])
    followed = sum(1 for t in turns if t["followed"])
    contradicted = sum(1 for t in turns if t["contradicted"])
    E, dropped = excess(route, off)
    lo, hi = bootstrap_ci(route, off, n=boot)
    return {"turns": len(turns), "N_spliced": n, "followed": followed,
            "F_follow_rate": round(followed / n, 4) if n else None,
            "X_contradiction_rate": round(contradicted / followed, 4) if followed else None,
            "E_excess": None if E is None else round(E, 4),
            "E_ci95": [None if lo is None else round(lo, 4), None if hi is None else round(hi, 4)],
            "E_dropped_followed": dropped,
            "off_route_failure_rate": round(sum(x for _, _, x in off) / len(off), 4) if off else None,
            **persistence(turns)}


def verdict(per_store: dict) -> dict:
    """PREREG §5."""
    ev = {k: m for k, m in per_store.items() if m["followed"] >= EVALUABLE_FOLLOWED}
    if len(ev) < 2:
        return {"disposition": 0, "evaluable": len(ev)}
    plus = [k for k, m in ev.items()
            if m["X_contradiction_rate"] >= X_PASS and m["E_ci95"][0] is not None and m["E_ci95"][0] > 0
            and m["P_median"] is not None and m["P_median"] >= 2]
    minus = all(m["X_contradiction_rate"] < X_FAIL or (m["E_ci95"][1] is not None and m["E_ci95"][1] <= 0)
                for m in ev.values())
    disp = 1 if len(plus) >= 2 else (-1 if minus else 0)
    return {"disposition": disp, "evaluable": len(ev), "passing": len(plus)}


def _read(path: Path) -> list:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if isinstance(r, dict):
                rows.append(r)
    return rows


def run(audit: Path, working_from: float | None = None, boot: int = BOOT_N) -> dict:
    return measure(replay(_read(audit), working_from), boot=boot)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Failing-Splice Gauge — contradicted, persisting splices (avenue 2)")
    ap.add_argument("--audit", action="append", default=[], help="audit.jsonl (repeatable)")
    ap.add_argument("--label", action="append", default=[], help="label per --audit")
    ap.add_argument("--working-from", action="append", default=[],
                    help="LABEL=EPOCH: the store ran working-verb keying from EPOCH on")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    labels = a.label + [f"store{i}" for i in range(len(a.label), len(a.audit))]
    wf = dict(x.split("=", 1) for x in a.working_from)
    per_store = {lab: run(Path(p), float(wf[lab]) if lab in wf else None) for lab, p in zip(labels, a.audit)}
    out = {"stores": per_store, "verdict": verdict(per_store)}
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for lab, m in per_store.items():
            print(lab, json.dumps(m))
        print("verdict", out["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
