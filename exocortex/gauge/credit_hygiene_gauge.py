"""Offline CREDIT-HYGIENE gauge (candidates W5 credit-pollution · W4 failure-ledger) — gauge-first, ADR-002.

Two of the highest-claimed hook-integration ideas (the 2026-06-30 Desktop self-audit) are measurable on the
EXISTING audit + colony, before any hook or organ is built:

  - **W5 — credit pollution.** `exit 0` blesses orientation noise: self-edges (`a→a`, e.g. `Read:other →
    Read:other`) and orientation-verb pairs (`cd/ls/pwd/cat/echo`) carry τ they never earned as *routing*
    information (a route is a TRANSITION; `a→a` is none). This gauge measures what fraction of colony τ-MASS
    a MECHANICAL deposit-filter would reclaim — the model-independent fix, preferred over an LLM judge in the
    credit loop (which breaks ADR-010's frozen, model-independent disposer).

  - **W4 — failure ledger.** Deposits happen only on `exit 0`; failure is ignored (ADR-001/004). Does a
    *failed approach* actually RECUR (so a "this failed before" warning would pay)? And — the ADR-004 check —
    do failed approaches LATER SUCCEED? A high "plasticity rate" means a permanent σ-scar would freeze a
    re-learnable route, so any failure signal must be a DECAYING τ⁻, never a scar.

Reads each repo's `<repo>/.claude/exocortex/{colony_*.json, audit.jsonl}`. Self-contained, numpy-free,
read-only — the same fail-open discipline as the hook. STATS-first; the verdict is a thin threshold the
numbers drive.

  python -m exocortex.gauge.credit_hygiene_gauge                  # auto-scan sibling repos' live state
  python -m exocortex.gauge.credit_hygiene_gauge --state-dir P    # explicit state dir(s) (repeatable)
  python -m exocortex.gauge.credit_hygiene_gauge --json           # machine-readable (results file / CI)
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

_SEP = "\t"                                                  # colony τ key separator (colony._SEP)
ORIENT = frozenset({"bash:cd", "bash:ls", "bash:pwd", "bash:cat", "bash:echo"})   # pure navigation/inspection
W5_MASS_THRESHOLD = 0.10                                     # ≥10% of τ-mass is routing-noise → filter pays
W4_RECURRENCE_THRESHOLD = 0.10                              # ≥10% of failing approaches recur → ledger pays
_REPO_ROOT = Path(__file__).resolve().parents[2]            # gauge -> exocortex -> repo root
_CONS = ("PostToolUse", "PostToolUseFailure")


# ------------------------------------------------------------------- loaders (read-only, fail-open)
def load_colonies(state_dir) -> list:
    """(label, tau) per ``colony_*.json`` in the state dir."""
    out = []
    for f in sorted(Path(state_dir).glob("colony_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append((str(d.get("label", "?")),
                        {str(k): float(v) for k, v in dict(d.get("tau", {})).items()}))
        except Exception:
            continue
    return out


def load_audit(state_dir) -> list:
    out: list = []
    p = Path(state_dir) / "audit.jsonl"
    if p.is_file():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    return out


# ------------------------------------------------------------------- W5: credit pollution (colony)
def _is_self(a, b):   return a == b
def _is_orient(a, b): return a in ORIENT and b in ORIENT
def _reclaim(a, b):   return _is_self(a, b) or _is_orient(a, b)   # a route is a transition; these aren't


def credit_hygiene(colonies: list) -> dict:
    """How much colony τ-MASS is routing-noise a mechanical filter would reclaim?"""
    tot_m = tot_e = 0.0
    self_m = self_n = orient_m = orient_n = recl_m = recl_n = 0.0
    per_class = []
    for label, tau in colonies:
        cmass = sum(tau.values())
        crecl = 0.0
        for k, w in tau.items():
            if _SEP not in k:
                continue
            a, b = k.split(_SEP, 1)
            tot_m += w; tot_e += 1
            if _is_self(a, b):   self_m += w; self_n += 1
            if _is_orient(a, b): orient_m += w; orient_n += 1
            if _reclaim(a, b):   recl_m += w; recl_n += 1; crecl += w
        if cmass > 0:
            per_class.append({"class": label, "mass": round(cmass, 2),
                              "reclaim_frac": round(crecl / cmass, 3)})
    return {
        "classes": len(colonies), "edges": int(tot_e), "tau_mass": round(tot_m, 2),
        "self_edges": int(self_n), "self_mass": round(self_m, 2),
        "orient_edges": int(orient_n), "orient_mass": round(orient_m, 2),
        "reclaim_edges": int(recl_n), "reclaim_mass": round(recl_m, 2),
        "reclaim_frac_edges": round(recl_n / tot_e, 3) if tot_e else None,
        "reclaim_frac_mass": round(recl_m / tot_m, 3) if tot_m else None,
        "top_polluted": sorted(per_class, key=lambda c: -c["reclaim_frac"])[:5],
    }


# ------------------------------------------------------------------- W4: failure recurrence (audit)
def _verb(key: str) -> str:
    s = (key or "").strip()
    return s.split()[0] if s else ""


def failure_recurrence(records: list) -> dict:
    """Do failed approaches recur — and do they later succeed (the ADR-004 plasticity check)?"""
    cons = [r for r in records if r.get("event") in _CONS]
    fails = [r for r in cons if r.get("event") == "PostToolUseFailure"]
    ok_keys = {r.get("command_key") for r in cons
               if r.get("event") == "PostToolUse" and r.get("command_key")}
    fail_count: dict = defaultdict(int)
    vfail: dict = defaultdict(int)
    for r in fails:
        k = r.get("command_key")
        if not k:
            continue
        fail_count[k] += 1
        v = _verb(k)
        if v:
            vfail[v] += 1
    distinct = len(fail_count)
    repeated = sum(1 for c in fail_count.values() if c > 1)         # SAME exact command failed >1×
    later_ok = sum(1 for k in fail_count if k in ok_keys)          # failed AND (also) succeeded
    vrepeated = sum(1 for c in vfail.values() if c > 1)            # same verb-altitude approach failed >1×
    max_streak = max((int(r.get("strategy_lock", 0) or 0) for r in fails), default=0)
    return {
        "consequences": len(cons), "failures": len(fails),
        "failure_rate": round(len(fails) / len(cons), 4) if cons else None,
        "distinct_fail_keys": distinct,
        "repeated_fail_keys": repeated,
        "recurrence_rate_exact": round(repeated / distinct, 3) if distinct else None,
        "fail_keys_later_succeeded": later_ok,
        "plasticity_rate": round(later_ok / distinct, 3) if distinct else None,   # high → never σ-scar
        "max_fail_streak": max_streak,
        "verb_distinct_fail": len(vfail), "verb_repeated_fail": vrepeated,
        "recurrence_rate_verb": round(vrepeated / len(vfail), 3) if vfail else None,
    }


# ------------------------------------------------------------------- verdict + drivers
def verdict(c: dict, a: dict) -> dict:
    w5 = (c["reclaim_frac_mass"] or 0.0) >= W5_MASS_THRESHOLD
    w4 = (a["recurrence_rate_verb"] or 0.0) >= W4_RECURRENCE_THRESHOLD
    return {
        "W5_credit_filter": {
            "signal": w5, "metric": "reclaim_frac_mass", "value": c["reclaim_frac_mass"],
            "note": "fraction of colony τ-MASS that is routing-noise (self-edges + orientation-verb pairs); "
                    "a mechanical deposit-filter reclaims it MODEL-INDEPENDENTLY — preferred over an LLM "
                    "judge in the credit loop (ADR-010). Pair with the dormant eligibility trace (organ 3D).",
        },
        "W4_failure_ledger": {
            "signal": w4, "metric": "recurrence_rate_verb", "value": a["recurrence_rate_verb"],
            "plasticity_rate": a["plasticity_rate"],
            "note": "do failed approaches RECUR? plasticity_rate = fraction of failed keys that ALSO succeed "
                    "— a high value means a permanent σ-scar would freeze a re-learnable route (ADR-004), so "
                    "any failure signal must be a DECAYING τ⁻, never a scar. Source = PostToolUseFailure.",
        },
    }


def discover(scan_root: Path) -> list:
    found = []
    if scan_root.is_dir():
        for child in sorted(scan_root.iterdir()):
            sd = child / ".claude" / "exocortex"
            if sd.is_dir():
                found.append(sd)
    return found


def run(state_dirs: list | None = None, scan_root: Path | None = None) -> dict:
    dirs = [Path(d) for d in (state_dirs or [])]
    if not dirs:
        dirs = discover(scan_root or _REPO_ROOT.parent)
    per_repo, all_col, all_rec = [], [], []
    for sd in dirs:
        col, rec = load_colonies(sd), load_audit(sd)
        if not col and not rec:
            continue
        per_repo.append({"repo": sd.parents[1].name,
                         "credit": credit_hygiene(col), "failure": failure_recurrence(rec)})
        all_col.extend(col); all_rec.extend(rec)
    c, f = credit_hygiene(all_col), failure_recurrence(all_rec)
    return {"per_repo": per_repo, "aggregate": {"credit": c, "failure": f},
            "verdict": verdict(c, f),
            "thresholds": {"W5_mass": W5_MASS_THRESHOLD, "W4_recurrence": W4_RECURRENCE_THRESHOLD}}


def _fmt(res: dict) -> str:
    lines = ["CREDIT-HYGIENE GAUGE  (W5 credit-pollution · W4 failure-ledger)", ""]
    for r in res["per_repo"]:
        c, f = r["credit"], r["failure"]
        lines.append(f"  [{r['repo']}] τ-edges={c['edges']} mass={c['tau_mass']} "
                     f"reclaim={c['reclaim_frac_mass']} (self={c['self_edges']} orient={c['orient_edges']}) "
                     f"| fails={f['failures']}/{f['consequences']} recur_verb={f['recurrence_rate_verb']} "
                     f"plasticity={f['plasticity_rate']}")
    c, f = res["aggregate"]["credit"], res["aggregate"]["failure"]
    lines += ["", "AGGREGATE:",
              f"  W5 credit:  {c['edges']} edges / τ-mass {c['tau_mass']} — reclaimable noise = "
              f"{c['reclaim_frac_mass']} of mass, {c['reclaim_frac_edges']} of edges "
              f"(self {c['self_edges']}/τ{c['self_mass']}, orient {c['orient_edges']}/τ{c['orient_mass']})",
              f"  W4 failure: {f['failures']}/{f['consequences']} fail "
              f"({f['failure_rate']}); distinct={f['distinct_fail_keys']} repeated_exact={f['repeated_fail_keys']} "
              f"recur_verb={f['recurrence_rate_verb']} plasticity={f['plasticity_rate']} "
              f"max_streak={f['max_fail_streak']}",
              "", "VERDICT:"]
    for k, v in res["verdict"].items():
        lines.append(f"  {k}: signal={v['signal']}  {v['metric']}={v['value']}")
        lines.append(f"       {v['note']}")
    if c["top_polluted"]:
        lines.append("  most-polluted classes (reclaim_frac): "
                     + ", ".join(f"{t['class']}={t['reclaim_frac']}" for t in c["top_polluted"]))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Credit-hygiene gauge (W5 credit-pollution; W4 failure-ledger)")
    ap.add_argument("--state-dir", action="append", default=[], help="explicit .claude/exocortex dir (repeatable)")
    ap.add_argument("--scan-root", default=None, help="dir to scan for */.claude/exocortex")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    res = run(args.state_dir or None, Path(args.scan_root) if args.scan_root else None)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
