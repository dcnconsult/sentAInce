"""Bridge-validity gauge — Ticket 2's gate (NEXT_PHASE_PLAN §3B / §6C). DO BEFORE building any bridge.

The Hippocampus proposal: in sleep, synthesize a shortcut edge ``A→D`` from HDC geometry (a chord over the
colony's transition memory) WITHOUT walking it. §3B is skeptical — *geometric proximity ≠ executable
validity, and a synthesized edge has no consequence backing.* This gauge quantifies that on the REAL colony
data before a line of bridge code is written. It answers two separable questions:

  1. PAYOFF CEILING (cheap, decisive): over the per-class colony graphs, how many routes are even long
     enough to shortcut? A bridge ``A→D`` that skips an ``A→…→D`` path of length L saves L-1 steps; if
     routes are median-2 (P-C / cross-model), there is almost nothing to bridge regardless of geometry.
  2. GEOMETRIC FIDELITY: build the vendored ``phase_router`` (random Z3 codebook) from each class's
     transitions and synthesize 2-hop chords (``recall_successor`` twice). Does the chord land on a REAL
     2-hop route (precision), and does the HDC 0-well abstain (a confidence floor) raise it?

HONEST SCOPE (the load-bearing caveat): with a random codebook the router RECALLS stored transitions — it
does not GENERALISE to novel edges — so high precision here means "the substrate faithfully recalls routes",
NOT "geometry invents valid new shortcuts." And executable validity of a *direct* ``A→D`` (do the skipped
steps matter?) is NOT derivable offline — only walking it with the body settles that. So a passing gauge
licenses *suggest-then-verify* (§3B option A, body-in-the-loop), never autonomous crystallization. STATS
ONLY — the numbers gate the build.
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _cand in (_ROOT / "vendor" / "kernel", _ROOT / "vendor" / "kernel" / "src"):
    if (_cand / "freqos").is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

_SEP = "\t"


# ------------------------------------------------------------------- colony graph
def load_colonies(state_dir: str) -> dict:
    """label -> list[(src, dst)] from every colony_*.json under ``state_dir``."""
    out: dict = {}
    for f in glob.glob(str(Path(state_dir) / "colony_*.json")):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        edges = []
        for k in (d.get("tau") or {}):
            a, _, b = k.partition(_SEP)
            if a and b:
                edges.append((a, b))
        if edges:
            out[d.get("label") or Path(f).stem] = edges
    return out


def _adj(edges: list) -> dict:
    g: dict = collections.defaultdict(set)
    for a, b in edges:
        g[a].add(b)
    return g


# ------------------------------------------------------------------- payoff ceiling
def _simple_path_lengths(adj: dict, maxlen: int = 6) -> collections.Counter:
    """Counter of simple-directed-path lengths (in EDGES, ≥1) — the population a bridge could shortcut."""
    lengths: collections.Counter = collections.Counter()

    def dfs(node, visited, depth):
        if depth >= maxlen:
            return
        for nxt in adj.get(node, ()):
            if nxt in visited:
                continue
            lengths[depth + 1] += 1
            dfs(nxt, visited | {nxt}, depth + 1)

    for start in adj:
        dfs(start, {start}, 0)
    return lengths


def payoff(colonies: dict) -> dict:
    agg = collections.Counter()
    per = []
    bridge_candidates = 0   # (A,D) reachable in ≥2 edges with NO direct edge → a genuine shortcut target
    for label, edges in colonies.items():
        adj = _adj(edges)
        lens = _simple_path_lengths(adj)
        agg.update(lens)
        # 2-hop reachable pairs without a direct edge
        bc = 0
        for a in adj:
            two = {d for b in adj[a] for d in adj.get(b, ()) if d != a and d != b}
            bc += len(two - adj[a])
        bridge_candidates += bc
        per.append({"class": label, "nodes": len({x for e in edges for x in e}),
                    "edges": len(edges), "max_path": max(lens) if lens else 0, "bridge_candidates": bc})
    total_paths = sum(agg.values())
    ge2 = sum(c for L, c in agg.items() if L >= 2)
    ge3 = sum(c for L, c in agg.items() if L >= 3)
    return {"per_class": per, "path_len_hist": dict(sorted(agg.items())),
            "total_paths": total_paths, "frac_ge2": round(ge2 / total_paths, 3) if total_paths else 0.0,
            "frac_ge3": round(ge3 / total_paths, 3) if total_paths else 0.0,
            "bridge_candidates": bridge_candidates}


# ------------------------------------------------------------------- HDC geometric fidelity
def hdc_bridge_test(colonies: dict, m: int = 2048, abstain: float = 0.10, seed: int = 7) -> dict:
    import numpy as np

    from freqos.phase_router import build_router, recall_successor
    from freqos.tam import random_patterns

    rng = np.random.default_rng(seed)
    one_hit = one_tot = 0
    cand = valid = cand_ab = valid_ab = 0
    confs = []
    for edges in colonies.values():
        nodes = sorted({x for e in edges for x in e})
        if len(nodes) < 3:
            continue
        idx = {n: i for i, n in enumerate(nodes)}
        adj = {idx[a]: set() for a in nodes}
        for a, b in edges:
            adj[idx[a]].add(idx[b])
        if not any(any(adj.get(b, set()) - {a, b} for b in adj[a]) for a in adj):
            continue   # no 2-hop route in this class → nothing to test

        codebook = random_patterns(len(nodes), m, rng)
        trans = [(idx[a], idx[b]) for a, b in edges]
        ctx = np.zeros((len(trans), m), dtype=np.int8)             # stateless context
        src = codebook[[a for a, _ in trans]]
        dst = codebook[[b for _, b in trans]]
        router = build_router(ctx, src, dst)
        z = np.zeros(m, dtype=np.int8)

        def recall(i):
            return recall_successor(router, z, codebook[i], codebook)   # (idx, conf, runner)

        for a in adj:
            if not adj[a]:
                continue
            b_hat, cb, _ = recall(a)
            one_tot += 1
            one_hit += int(b_hat in adj[a])                         # 1-hop recall fidelity
            d_hat, cd, _ = recall(b_hat)
            confs.append(min(cb, cd))
            if d_hat == a or d_hat == b_hat:
                continue                                            # not a forward 2-hop chord
            cand += 1
            is_real = (b_hat in adj[a]) and (d_hat in adj.get(b_hat, set()))   # a REAL 2-hop route?
            valid += int(is_real)
            if min(cb, cd) >= abstain:                             # HDC 0-well abstain gate
                cand_ab += 1
                valid_ab += int(is_real)

    return {"m": m, "abstain": abstain,
            "one_hop_fidelity": round(one_hit / one_tot, 3) if one_tot else None,
            "bridges_proposed": cand, "bridge_precision": round(valid / cand, 3) if cand else None,
            "bridges_after_abstain": cand_ab,
            "bridge_precision_abstained": round(valid_ab / cand_ab, 3) if cand_ab else None,
            "conf_median": round(float(__import__("numpy").median(confs)), 3) if confs else None}


def run(state_dir: str, m: int = 2048, abstain: float = 0.10) -> dict:
    colonies = load_colonies(state_dir)
    return {"state_dir": state_dir, "n_classes": len(colonies),
            "payoff": payoff(colonies), "hdc": hdc_bridge_test(colonies, m, abstain)}


def _print(res: dict) -> None:
    p, h = res["payoff"], res["hdc"]
    print(f"Bridge-validity gauge — {res['n_classes']} colony classes @ {res['state_dir']}")
    print("\n[1] PAYOFF CEILING (is there anything to shortcut?)")
    print(f"  simple-path length hist (edges→count): {p['path_len_hist']}")
    print(f"  paths ≥2 edges: {p['frac_ge2']:.0%}   ≥3 edges: {p['frac_ge3']:.0%}   "
          f"bridge candidates (≥2-hop, no direct edge): {p['bridge_candidates']}")
    longies = [c for c in p["per_class"] if c["max_path"] >= 3]
    print(f"  classes with a ≥3-edge route: {len(longies)}/{len(p['per_class'])}"
          + (f"  e.g. {[c['class'] for c in longies[:4]]}" if longies else ""))
    print("  CAVEAT: these are TOPOLOGICAL simple paths — inflated by graph cycles (recurring verb-nodes "
          "like\n  Edit:src/bash:cd). The real prize cap is the DEPOSIT-WINDOW segment length (median 2, "
          "cross-model;\n  see eligibility_gauge seg_len) — a bridge over a cyclic path is not a meaningful route.")
    print("\n[2] HDC GEOMETRIC FIDELITY (does the chord land on a real route?)")
    print(f"  1-hop recall fidelity: {h['one_hop_fidelity']}   (router faithfully recalls stored transitions)")
    print(f"  2-hop chords proposed: {h['bridges_proposed']}   precision: {h['bridge_precision']}   "
          f"conf_median: {h['conf_median']}")
    print(f"  after 0-well abstain (conf≥{h['abstain']}): proposed {h['bridges_after_abstain']}   "
          f"precision: {h['bridge_precision_abstained']}")
    print("\n[verdict — stats only] Geometry can at best RECALL real routes (random codebook → no "
          "generalisation),\n  and executable validity of a direct A→D is NOT offline-decidable — only the "
          "body settles it.\n  Couple that with the payoff ceiling above: build suggest-then-verify (§3B-A, "
          "body-in-the-loop)\n  if routes are long enough; NEVER autonomous crystallization.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Bridge-validity gauge (Ticket 2 gate) — offline, over colony data")
    ap.add_argument("--state-dir", default=str(_ROOT / ".claude" / "exocortex"),
                    help="dir of colony_*.json (default: live .claude/exocortex)")
    ap.add_argument("--m", type=int, default=2048, help="HDC dimension (phase_router capacity ~0.40*m)")
    ap.add_argument("--abstain", type=float, default=0.10, help="0-well abstain confidence floor")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    res = run(args.state_dir, args.m, args.abstain)
    _print(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
