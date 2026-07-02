"""Offline D'Ambrogio VoI-alignment gauge (D4) — does the colony's emergent explore/exploit match the
paper's 4-parameter value-of-information model, and how big is the directed-exploration (β4) GAP? (STATS)

Gauge-first (ADR-002): measure the prize BEFORE any β4 organ is wired. Reads ``colony_*.json`` (final τ +
deposit counts + F3 provenance) and ``audit.jsonl`` (the goal-class visit SEQUENCE) — READ-ONLY,
self-contained, pure-stdlib, fail-open. The verdict is a thin threshold the numbers drive; expect a
NULL / UNDERPOWERED read on single-dev flagship traffic (the same data-gate that shrank eligibility /
uncertainty / nonstationarity) → **retire-trigger = a population / multi-model soak**.

Alignment (D'Ambrogio et al. 2026; ../../Paper4_DAmbrogio_SentAInce_Alignment.md):
  β1 attentional inertia   ⟺ colony ``DEPOSIT`` weight        (baseline stickiness to a proven path)
  β2 information satiation  ⟺ colony evaporation ``DECAY``     (β2 = -ln DECAY; multiplicative diminishing returns)
  β1..β3 already implicit; **β4 directed exploration ~ log(2·Nᵤ)/Nₐ is the GAP** — no active under-exploration bonus.

HONEST CATCH (stated in the readout): the goal-class is chosen by the user's PROMPT, not the organism, so the
switch/stay sequence measures the *human+agent's task-selection*, not a colony policy. The β4 metric therefore
tests whether observed switching has a VoI-directed structure a colony bonus could *align with* — confounded
by task novelty (a brand-new task is under-explored by definition). The "seen-only" DEI isolates the cleaner
signal (revisits to already-seen-but-under-explored classes).

  python -m exocortex.gauge.dambrogio_gauge                     # auto-scan sibling repos' state dirs
  python -m exocortex.gauge.dambrogio_gauge --state DIR [...]   # explicit .claude/exocortex dir(s)
  python -m exocortex.gauge.dambrogio_gauge --json              # machine-readable (for the results file / CI)
  python -m exocortex.gauge.dambrogio_gauge --pysr              # Tier-2 (independent SR rediscovery) — stub
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

try:
    from exocortex.colony import DECAY, DEPOSIT   # colony constants ⟺ β2, β1
except Exception:
    DECAY, DEPOSIT = 0.9, 1.0                     # documented defaults (fail-open)

_REPO_ROOT = Path(__file__).resolve().parents[2]   # gauge -> exocortex -> repo root
_CLASS_RE = re.compile(r"class=([^\s]+)")

# power thresholds — below these the gauge ABSTAINS (a 4-param VoI read needs a real population)
MIN_CLASSES = 8
MIN_SWITCHES = 20        # switches to ALREADY-SEEN classes (the β4-relevant decisions)
DEI_MARGIN = 0.10        # directed-exploration index must beat 0.5 by this to count as a signal
RHO_CONSISTENT = 0.30    # deposits↔τ Spearman ρ to call vectors 1–3 empirically consistent


# ------------------------------------------------------------------ IO (read-only, fail-open)
def load_jsonl(path) -> list:
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


def load_colonies(state_dir) -> dict:
    """{label: {deposits, edges, tau_max, models[]}} from ``colony_*.json`` (no Colony import; raw JSON)."""
    out: dict = {}
    for cf in sorted(Path(state_dir).glob("colony_*.json")):
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            continue
        label = d.get("label") or cf.stem[len("colony_"):]
        tau = d.get("tau", {}) or {}
        meta = d.get("meta", {}) or {}
        models = sorted({str(m.get("model")) for m in meta.values()
                         if isinstance(m, dict) and m.get("model")})
        out[label] = {"deposits": int(d.get("deposits", 0)), "edges": len(tau),
                      "tau_max": max(tau.values()) if tau else 0.0, "models": models}
    return out


def extract_sequence(records: list) -> list:
    """The ordered goal-class visit sequence from UserPromptSubmit audit records (reason='class=<label>')."""
    seq = []
    for r in records:
        if r.get("event") == "UserPromptSubmit":
            m = _CLASS_RE.search(str(r.get("reason", "")))
            if m:
                seq.append(m.group(1))
    return seq


# ------------------------------------------------------------------ stats (pure python)
def _spearman(xs: list, ys: list):
    n = len(xs)
    if n < 3:
        return None

    def ranks(vs):
        order = sorted(range(n), key=lambda i: vs[i])
        rk = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (sum((rx[i] - mx) ** 2 for i in range(n)) * sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    return round(num / den, 3) if den else None


def directed_exploration_index(seq: list) -> dict:
    """β4 probe. Walk the visit sequence; at each SWITCH, percentile-rank the switched-to class's PRIOR
    visit-count among all seen classes (0 = the least-explored, 1 = the most). DEI = mean percentile.
    DEI < 0.5 ⇒ switches favour UNDER-explored classes (directed exploration; a β4 bonus has a target).
    'seen' variant counts only switches to already-visited classes (isolates revisit-direction from raw novelty)."""
    visits: dict = {}
    all_pcts, seen_pcts = [], []
    prev = None
    for c in seq:
        if prev is not None and c != prev and visits:
            counts = list(visits.values())
            v = visits.get(c, 0)
            below = sum(1 for x in counts if x < v)
            equal = sum(1 for x in counts if x == v)
            pct = (below + 0.5 * equal) / len(counts)
            all_pcts.append(pct)
            if v >= 1:
                seen_pcts.append(pct)
        visits[c] = visits.get(c, 0) + 1
        prev = c
    return {"n_switches": len(all_pcts),
            "dei_all": round(sum(all_pcts) / len(all_pcts), 3) if all_pcts else None,
            "n_switches_seen": len(seen_pcts),
            "dei_seen": round(sum(seen_pcts) / len(seen_pcts), 3) if seen_pcts else None}


# ------------------------------------------------------------------ analysis + verdict
def analyze(colonies: dict, seq: list) -> dict:
    classes = list(colonies.keys())
    deps = {c: colonies[c]["deposits"] for c in classes}
    total = sum(deps.values())
    pts = [[deps[c], round(colonies[c]["tau_max"], 3)] for c in classes if deps[c] > 0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    model_set = sorted({m for c in classes for m in colonies[c]["models"]})
    return {
        "n_classes": len(classes),
        "total_deposits": total,
        "n_turns": len(seq),
        "beta1_deposit": DEPOSIT,                                  # β1 ⟺ DEPOSIT (analytic)
        "beta2_satiation": round(-math.log(DECAY), 4) if 0 < DECAY < 1 else None,   # β2 = -ln DECAY
        "dep_tau_spearman": _spearman(xs, ys),                     # vectors 1–3 empirical consistency (τ rises w/ Nₐ)
        "dep_tau_points": pts,                                      # raw (Nₐ, τ) pairs → pooled ρ at aggregate
        "dei": directed_exploration_index(seq),                    # β4 probe
        "models_seen": model_set, "n_models": len(model_set),
        "multi_model_classes": sum(1 for c in classes if len(colonies[c]["models"]) >= 2),
        "top_classes": [[c, deps[c], round(colonies[c]["tau_max"], 2), colonies[c]["models"]]
                        for c in sorted(classes, key=lambda c: -deps[c])[:8]],
    }


def _aggregate(per_repo: list) -> dict:
    if not per_repo:
        return {"n_classes": 0, "total_deposits": 0, "n_turns": 0, "dep_tau_spearman": None,
                "dei": {"n_switches": 0, "dei_all": None, "n_switches_seen": 0, "dei_seen": None},
                "models_seen": [], "n_models": 0, "multi_model_classes": 0}

    def _wmean(key_v, key_n):
        pairs = [(r["dei"][key_v], r["dei"][key_n]) for r in per_repo if r["dei"][key_v] is not None]
        n = sum(k for _, k in pairs)
        return (round(sum(v * k for v, k in pairs) / n, 3) if n else None, n)

    dei_all, n_all = _wmean("dei_all", "n_switches")
    dei_seen, n_seen = _wmean("dei_seen", "n_switches_seen")
    pts = [p for r in per_repo for p in r.get("dep_tau_points", [])]   # POOL raw (Nₐ,τ) pairs, not mean-of-ρ
    return {
        "n_classes": sum(r["n_classes"] for r in per_repo),
        "total_deposits": sum(r["total_deposits"] for r in per_repo),
        "n_turns": sum(r["n_turns"] for r in per_repo),
        "dep_tau_spearman": _spearman([p[0] for p in pts], [p[1] for p in pts]),
        "dei": {"n_switches": n_all, "dei_all": dei_all, "n_switches_seen": n_seen, "dei_seen": dei_seen},
        "models_seen": sorted({m for r in per_repo for m in r["models_seen"]}),
        "n_models": len({m for r in per_repo for m in r["models_seen"]}),
        "multi_model_classes": sum(r["multi_model_classes"] for r in per_repo),
    }


def verdict(m: dict) -> dict:
    d = m["dei"]
    powered = m["n_classes"] >= MIN_CLASSES and (d["n_switches_seen"] or 0) >= MIN_SWITCHES
    dei_seen = d["dei_seen"]
    beta4 = bool(powered and dei_seen is not None and dei_seen < 0.5 - DEI_MARGIN)
    vectors = (m["dep_tau_spearman"] or 0.0) >= RHO_CONSISTENT
    if not powered:
        overall = "PARK — UNDERPOWERED (retire-trigger: population / multi-model soak)"
    elif beta4:
        overall = "β4 SIGNAL — build D1 dormant on the G5 explore lane (re-confirm on population data)"
    else:
        overall = "PARK — no directed-exploration signal (DEI≈0.5: switching is not under-exploration-directed)"
    return {"powered": powered, "vectors_1_3_consistent": vectors, "beta4_signal": beta4,
            "dei_seen": dei_seen, "overall": overall}


# ------------------------------------------------------------------ discovery + run
def discover(scan_root) -> list:
    out = []
    root = Path(scan_root)
    if root.is_dir():
        for child in sorted(root.iterdir()):
            sd = child / ".claude" / "exocortex"
            if sd.is_dir() and (any(sd.glob("colony_*.json")) or (sd / "audit.jsonl").is_file()):
                out.append(sd)
    return out


def run(state_dirs: list | None = None, scan_root=None) -> dict:
    dirs = [Path(d) for d in (state_dirs or [])]
    if not dirs:
        dirs = discover(scan_root or _REPO_ROOT.parent)
    per_repo = []
    for sd in dirs:
        colonies = load_colonies(sd)
        seq = extract_sequence(load_jsonl(sd / "audit.jsonl"))
        if not colonies and not seq:
            continue
        a = analyze(colonies, seq)
        a["repo"] = sd.parents[1].name
        a["state_dir"] = str(sd)
        per_repo.append(a)
    agg = _aggregate(per_repo)
    return {"per_repo": per_repo, "aggregate": agg, "verdict": verdict(agg),
            "constants": {"DECAY": DECAY, "DEPOSIT": DEPOSIT},
            "thresholds": {"MIN_CLASSES": MIN_CLASSES, "MIN_SWITCHES": MIN_SWITCHES, "DEI_MARGIN": DEI_MARGIN}}


def _fmt(res: dict) -> str:
    L = ["D'AMBROGIO VoI GAUGE  (β1 inertia · β2 satiation · β4 directed-exploration GAP)",
         f"  constants: DECAY={res['constants']['DECAY']} (β2≈{round(-math.log(res['constants']['DECAY']),4)}) "
         f"DEPOSIT={res['constants']['DEPOSIT']} (β1)", ""]
    for r in res["per_repo"]:
        di = r["dei"]
        L.append(f"  [{r['repo']}] classes={r['n_classes']} deposits={r['total_deposits']} turns={r['n_turns']} "
                 f"dep↔τ ρ={r['dep_tau_spearman']} | switches(seen)={di['n_switches_seen']} DEI_seen={di['dei_seen']} "
                 f"| models={r['n_models']} multi={r['multi_model_classes']}")
    a = res["aggregate"]
    di = a["dei"]
    L += ["", f"AGGREGATE: classes={a['n_classes']} deposits={a['total_deposits']} turns={a['n_turns']} "
              f"models={a['models_seen']}",
          f"  Q1 vectors 1–3:  β1={DEPOSIT} (DEPOSIT) · β2={round(-math.log(DECAY),4)} (-ln DECAY) · "
          f"dep↔τ Spearman ρ={a['dep_tau_spearman']}",
          f"  Q2 β4 gap:       DEI_seen={di['dei_seen']} (switches_seen={di['n_switches_seen']}; "
          f"<{round(0.5-DEI_MARGIN,2)} ⇒ under-exploration-directed) · DEI_all={di['dei_all']}",
          f"  Q3 power:        classes≥{MIN_CLASSES}? switches_seen≥{MIN_SWITCHES}?",
          f"  Q4 diversity:    {a['n_models']} models, {a['multi_model_classes']} multi-model classes", "",
          "VERDICT:"]
    v = res["verdict"]
    L += [f"  powered={v['powered']}  vectors_1_3_consistent={v['vectors_1_3_consistent']}  "
          f"beta4_signal={v['beta4_signal']}",
          f"  => {v['overall']}",
          "  NOTE: class selection is prompt-driven (user), not a colony policy — DEI tests whether observed",
          "        switching has VoI-directed structure a β4 bonus could align with (confounded by task novelty)."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="D'Ambrogio VoI-alignment gauge (D4) — β4 directed-exploration gap")
    ap.add_argument("--state", action="append", default=[], help="explicit .claude/exocortex dir (repeatable)")
    ap.add_argument("--scan-root", default=None, help="dir to scan for */.claude/exocortex")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--pysr", action="store_true", help="Tier-2 independent symbolic-regression rediscovery (stub)")
    args = ap.parse_args(argv)
    if args.pysr:
        print("[--pysr] Tier-2 stub: independent SR rediscovery needs the PySR/Julia backend "
              "(github.com/simonedambrogio/HybridModellingProject) — not wired here; Tier-1 fit below.\n")
    res = run(args.state or None, Path(args.scan_root) if args.scan_root else None)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
