"""Class-Consolidation Gauge — would merging near-duplicate goal-classes feed the starved tail? (STATS)

The Desktop longitudinal audit's fragmentation finding: deposits are the scarce resource and the
classifier scatters them — 68 classes, the top-10 holding most of the mass, ~58 classes starved below the
convergence threshold, with paraphrase variants observably minting fresh empty classes. The proposed fix
is a periodic **class-merge pass** (cluster class centroids, merge τ-graphs, pool deposits). That is an
ORGANISM CHANGE, so per ADR-002 this gauge measures the prize offline first, on the real colony files:

  * candidate merges — cosine over the embed-classifier's stored class centroids (``embed_cues.json``;
    the same MiniLM space the live classifier assigns in). Embedding-based ⇒ model-DEPENDENT but
    judge-FREE (no LLM verdict anywhere) — flagged per ADR-010.
  * at each merge threshold: how many additional classes clear ``MIN_DEPOSITS_TO_SPLICE`` (the abstention
    bar — the real prize: starved memory becoming servable), the deposits-per-class distribution, and
    whether the merged τ-graph's dominant route DEEPENS (pooled evidence converging) or stays flat.
  * a conservatism stat: merges joining two classes that BOTH already converged (both ≥ bar) are flagged —
    those risk muddling two distinct reflexes into one (the failure mode to avoid).

Read-only, pure-stdlib, deterministic (no RNG — threshold sweep over sorted pairs), fail-open. A run over
a live repo is a labeled demonstration, never evidence. Verdict gates whether the merge pass is BUILT.

  python -m exocortex.gauge.consolidation_gauge --state-dir .claude/exocortex
  python -m exocortex.gauge.consolidation_gauge --state-dir .claude/exocortex --thresholds 0.6,0.7,0.8
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

_SEP = "\t"
DEFAULT_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90)
DEFAULT_SPLICE_BAR = 3          # colony MIN_DEPOSITS_TO_SPLICE genome default; overridden by repo config
MIN_NEW_SERVABLE = 3            # verdict bar: a merge pass must make ≥ this many starved classes servable


def _safe(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(label or "_default")) or "_default"


# ------------------------------------------------------------------ loading (fail-open)
def _json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def load_classes(state_dir: Path) -> dict:
    """label -> {tau, deposits, vec|None}. Colonies from ``colony_*.json``; a similarity vector per class
    joined via ``_safe(label)`` from whichever cue store exists: the embed classifier's dense centroid
    (``embed_cues.json``, mean = sum/size) or the lexical classifier's sparse TF vector (``cues.json``
    ``tf_sum`` — the SAME raw-TF cosine space the live classifier assigns in, so a simulated merge is
    exactly 'what the classifier would have said had it seen the cues together')."""
    sd = Path(state_dir)
    vecs: dict = {}
    for c in (_json_file(sd / "embed_cues.json").get("classes", []) or []):
        try:
            s, n = c.get("sum"), max(1, int(c.get("size", 1)))
            if isinstance(s, list) and s:
                vecs[_safe(str(c.get("label", "")))] = [x / n for x in s]
        except Exception:
            continue
    for c in (_json_file(sd / "cues.json").get("clusters", []) or []):
        try:
            tf = c.get("tf_sum")
            key = _safe(str(c.get("label", "")))
            if isinstance(tf, dict) and tf and key not in vecs:      # embed wins when both exist
                vecs[key] = {str(k): float(v) for k, v in tf.items()}
        except Exception:
            continue
    out: dict = {}
    for f in sorted(sd.glob("colony_*.json")):
        d = _json_file(f)
        if not d:
            continue
        label = str(d.get("label", f.stem[len("colony_"):]))
        out[label] = {"tau": {str(k): float(v) for k, v in dict(d.get("tau", {}) or {}).items()},
                      "deposits": int(d.get("deposits", 0) or 0),
                      "vec": vecs.get(_safe(label))}
    return out


def splice_bar(state_dir: Path) -> int:
    root = Path(state_dir).parent.parent
    th = (_json_file(root / "exocortex_config.json").get("thermodynamics", {}) or {})
    try:
        return int(th.get("min_deposits_to_splice", DEFAULT_SPLICE_BAR))
    except Exception:
        return DEFAULT_SPLICE_BAR


# ------------------------------------------------------------------ merge simulation
def _cos(a, b) -> float:
    """Cosine over a dense list (embed centroid) or sparse dict (lexical TF) pair — scale-invariant."""
    if isinstance(a, dict) and isinstance(b, dict):
        num = sum(v * b.get(k, 0.0) for k, v in a.items())
        da = math.sqrt(sum(v * v for v in a.values()))
        db = math.sqrt(sum(v * v for v in b.values()))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(y * y for y in b))
    else:
        return 0.0
    return num / (da * db) if da and db else 0.0


def _dominant_depth(tau: dict, max_len: int = 8) -> int:
    """Length (nodes) of the greedy widest path — mirror of ``Colony.dominant_path`` (read-only copy of
    the walk, on a plain dict so we never construct live colonies here)."""
    if not tau:
        return 0
    w = {tuple(k.split(_SEP)): v for k, v in tau.items() if len(k.split(_SEP)) == 2}
    if not w:
        return 0
    cur = max(w, key=lambda e: w[e])[0]
    path = [cur]
    while len(path) < max_len:
        outs = [(b, wt) for (a, b), wt in w.items() if a == cur and b not in path]
        if not outs:
            break
        cur = max(outs, key=lambda x: x[1])[0]
        path.append(cur)
    return len(path)


def _components(labels: list, sims: dict, threshold: float) -> list:
    """Union-find over the ≥threshold similarity graph (deterministic: sorted labels/pairs)."""
    parent = {l: l for l in labels}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for (a, b), s in sorted(sims.items()):
        if s >= threshold:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    groups: dict = {}
    for l in labels:
        groups.setdefault(find(l), []).append(l)
    return sorted(groups.values(), key=lambda g: (-len(g), g[0]))


def simulate(classes: dict, threshold: float, bar: int) -> dict:
    """Merge all ≥threshold centroid-similar classes; measure the tail-feeding + route effects."""
    with_c = sorted(l for l, c in classes.items() if c["vec"])
    sims = {}
    for i, a in enumerate(with_c):
        for b in with_c[i + 1:]:
            sims[(a, b)] = _cos(classes[a]["vec"], classes[b]["vec"])
    groups = _components(with_c, sims, threshold)
    merged_groups = [g for g in groups if len(g) >= 2]

    served_before = sum(1 for c in classes.values() if c["deposits"] >= bar)
    newly_servable = 0
    both_converged_merges = 0
    depth_gains = []
    for g in merged_groups:
        deps = [classes[l]["deposits"] for l in g]
        pooled = sum(deps)
        newly_servable += sum(1 for d in deps if d < bar) if pooled >= bar else 0
        if sum(1 for d in deps if d >= bar) >= 2:
            both_converged_merges += 1
        merged_tau: dict = {}
        for l in g:
            for k, w in classes[l]["tau"].items():
                merged_tau[k] = merged_tau.get(k, 0.0) + w
        depth_gains.append(_dominant_depth(merged_tau) - max(_dominant_depth(classes[l]["tau"]) for l in g))
    return {
        "threshold": threshold, "classes_with_vector": len(with_c),
        "n_classes_after": len(groups) + (len(classes) - len(with_c)),
        "merged_groups": len(merged_groups),
        "largest_group": max((len(g) for g in merged_groups), default=1),
        "served_before": served_before, "newly_servable_members": newly_servable,
        "both_converged_merges": both_converged_merges,
        "depth_gain_median": sorted(depth_gains)[len(depth_gains) // 2] if depth_gains else 0,
        "example_merges": [g for g in merged_groups[:4]],
    }


# ------------------------------------------------------------------ run + verdict
def run(state_dir, thresholds=DEFAULT_THRESHOLDS) -> dict:
    sd = Path(state_dir)
    classes = load_classes(sd)
    bar = splice_bar(sd)
    deps = sorted((c["deposits"] for c in classes.values()), reverse=True)
    frag = {
        "classes": len(classes), "deposits_total": sum(deps),
        "top10_deposits": sum(deps[:10]), "starved_below_bar": sum(1 for d in deps if d < bar),
        "splice_bar": bar, "median_deposits": deps[len(deps) // 2] if deps else 0,
        "no_vector": sum(1 for c in classes.values() if not c["vec"]),
    }
    sweep = [simulate(classes, t, bar) for t in thresholds]
    # verdict at the most conservative threshold that still feeds the tail without muddling converged pairs
    best = None
    for s in sorted(sweep, key=lambda s: -s["threshold"]):
        if s["newly_servable_members"] >= MIN_NEW_SERVABLE and s["both_converged_merges"] == 0:
            best = s
            break
    if best is not None:
        v = {"signal": True, "threshold": best["threshold"],
             "note": f"BUILD-candidate — at cos≥{best['threshold']} a merge pass makes "
                     f"{best['newly_servable_members']} starved classes servable, merges no two already-"
                     f"converged classes, and median route depth changes by {best['depth_gain_median']}. "
                     f"Flag: embedding-based ⇒ model-dependent (ADR-010: judge-free but not model-free); "
                     f"any build ships as a PreCompact-time PROPOSER (suggest-then-verify), never auto."}
    else:
        v = {"signal": False, "threshold": None,
             "note": f"PARK — no threshold feeds ≥{MIN_NEW_SERVABLE} starved classes without merging "
                     f"already-converged pairs; fragmentation is real but a centroid merge pass is not "
                     f"the lever at this traffic (paraphrase variants may not be centroid-near)."}
    return {"state_dir": str(sd), "repo": sd.parent.parent.name, "fragmentation": frag,
            "sweep": sweep, "verdict": v,
            "thresholds": {"MIN_NEW_SERVABLE": MIN_NEW_SERVABLE, "splice_bar": bar}}


def _fmt(res: dict) -> str:
    f = res["fragmentation"]
    L = ["CLASS-CONSOLIDATION GAUGE  (would a centroid merge pass feed the starved tail?)",
         f"  repo={res['repo']}  classes={f['classes']}  deposits={f['deposits_total']} "
         f"(top-10 hold {f['top10_deposits']})",
         f"  starved (<{f['splice_bar']} deposits = splice-abstain): {f['starved_below_bar']}   "
         f"median deposits/class: {f['median_deposits']}   no-vector: {f['no_vector']}", "",
         "  threshold sweep (merge classes with cue-vector cos ≥ t):",
         "    t     classes→after  groups  largest  newly-servable  converged-muddles  depth-gain(med)"]
    for s in res["sweep"]:
        L.append(f"    {s['threshold']:.2f}  {f['classes']:>4}→{s['n_classes_after']:<5}  "
                 f"{s['merged_groups']:^6}  {s['largest_group']:^7}  {s['newly_servable_members']:^14}  "
                 f"{s['both_converged_merges']:^17}  {s['depth_gain_median']:^5}")
    ex = next((s["example_merges"] for s in res["sweep"] if s["example_merges"]), [])
    if ex:
        L.append("  example merge groups (lowest threshold that produced any):")
        for g in ex:
            L.append("    · " + "  +  ".join(g))
    v = res["verdict"]
    L += ["", "VERDICT:", f"  signal={v['signal']}  threshold={v['threshold']}", f"  => {v['note']}",
          "  NOTE: read-only simulation; nothing was merged. Live = demonstration, never evidence."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Class-Consolidation Gauge — offline merge-pass sizing (ADR-002)")
    ap.add_argument("--state-dir", required=True, help="the repo's .claude/exocortex directory")
    ap.add_argument("--thresholds", default=None, help="comma list, e.g. 0.6,0.7,0.8")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    ths = tuple(float(t) for t in args.thresholds.split(",")) if args.thresholds else DEFAULT_THRESHOLDS
    res = run(args.state_dir, ths)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
