"""Offline colony + descriptive stats over a stream's P0 audit — STATS ONLY, no verdict.

Reconstructs each step's decision-PATH from the audit, runs a **consequence-sourced** ant-colony per
goal-class (deposit pheromone on `exit 0` / verify-PASS paths, decay, prune), and emits TIME-SERIES:
convergence (pheromone entropy ↓), segment-reuse, post-refactor staleness, clutter ratio. The colony
here is a faithful minimal mirror of `circle_of_fifths_rag/src/rag/stigmergic_network.py` (v0.78/v0.80);
the graduation build swaps in the locked module. Reads `<out>/steps.jsonl` + `<out>/audit/*.jsonl`;
writes `<out>/gauge_stats.json`. Descriptive data only — the null/strategy is designed FROM the shapes.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import math
import os
import random
import re
from pathlib import Path

DECAY, PRUNE, DEPOSIT = 0.9, 1e-3, 1.0   # v0.78/v0.80 stigmergy constants (mirror)

# Path-node GRANULARITY (the #1 data-surfaced refinement): the `fine` keying embeds the random
# sandbox temp path + full arg noise in each bash node, so full paths never repeat (entropy rises
# even as sub-segments recur). The sweep re-asks the convergence question at coarser altitudes:
#   fine — original: tool + command_key / basename (path- and arg-specific)
#   verb — bash → its executable verb (find/python3/pytest); file tools → src|test|other
#   tool — just the tool name (Bash/Read/Edit/Write) — "what KIND of step is this"
GRANULARITIES = ("fine", "verb", "tool")
_VERB = re.compile(r"^\s*([A-Za-z0-9_./-]+)")


def _bash_verb(cmd: str) -> str:
    m = _VERB.match(cmd or "")
    return os.path.basename(m.group(1)) if m else "?"


def _file_cat(path: str) -> str:
    b = os.path.basename(str(path or "")).lower()
    if not b:
        return "other"
    if "test" in b:
        return "test"
    return "src" if b.endswith(".py") else "other"


def _node(rec: dict, gran: str = "fine") -> str:
    tool = rec.get("tool")
    if gran == "tool":
        return tool or "?"
    if gran == "verb":
        if tool == "Bash":
            return f"bash:{_bash_verb(str(rec.get('command', '')))}"
        return f"{tool}:{_file_cat(str(rec.get('command') or ''))}"
    if tool == "Bash":
        return f"bash:{rec.get('command_key') or str(rec.get('command', ''))[:24]}"
    return f"{tool}:{os.path.basename(str(rec.get('command', '')))}"


def _path(audit: list, gran: str = "fine") -> list:
    return [_node(r, gran) for r in audit if r.get("event") == "PreToolUse" and r.get("tool")]


def _edges(path: list) -> list:
    return list(zip(path, path[1:]))


def _entropy(tau: dict) -> float:
    tot = sum(tau.values())
    if tot <= 0:
        return 0.0
    return -sum((w / tot) * math.log2(w / tot) for w in tau.values() if w > 0)


class _Colony:
    """Consequence-sourced pheromone over decision-edges (mirror of rag.stigmergic_network)."""

    def __init__(self):
        self.tau: dict = {}

    def deposit(self, edges: list) -> None:
        for e in list(self.tau):
            self.tau[e] *= DECAY
        for e in edges:
            self.tau[e] = self.tau.get(e, 0.0) + DEPOSIT
        self.tau = {e: w for e, w in self.tau.items() if w >= PRUNE}


def _run_policy(steps: list, audits: dict, policy: str, seed: int = 0, gran: str = "fine") -> dict:
    """Run ONE colony over all steps under a deposit policy and measure how much FAIL-ONLY clutter
    ends up in the memory. consequence = deposit only on verify-PASS (the law); frequency = deposit on
    every step (the clutter null); shuffle = deposit on a random subset the size of #PASS (the
    randomization null). The discriminating stat is `clutter_frac` — fail-only edges in the memory."""
    col = _Colony()
    pass_edges, fail_edges = set(), set()
    pass_idx = [s["idx"] for s in steps if s["step_verify"] == "PASS"]
    shuffle_set = set(random.Random(seed).sample([s["idx"] for s in steps], k=len(pass_idx))) \
        if pass_idx else set()
    for s in sorted(steps, key=lambda r: r["idx"]):
        edges = _edges(_path(audits.get(s["idx"], []), gran))
        (pass_edges if s["step_verify"] == "PASS" else fail_edges).update(edges)
        deposit = (policy == "frequency"
                   or (policy == "consequence" and s["step_verify"] == "PASS")
                   or (policy == "shuffle" and s["idx"] in shuffle_set))
        if deposit:
            col.deposit(edges)
    memory = set(col.tau)
    clutter = memory & (fail_edges - pass_edges)     # fail-only edges that polluted the memory
    return {"policy": policy, "memory_size": len(memory), "clutter_edges": len(clutter),
            "clutter_frac": round(len(clutter) / max(1, len(memory)), 3),
            "entropy": round(_entropy(col.tau), 3)}


def _load(out_dir: Path):
    steps = [json.loads(l) for l in open(out_dir / "steps.jsonl", encoding="utf-8") if l.strip()]
    audits: dict[int, list] = {}
    for f in glob.glob(str(out_dir / "audit" / "*.jsonl")):
        idx = int(os.path.basename(f).split("_")[0])
        audits[idx] = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    return steps, audits


def analyze(out_dir: Path, gran: str = "fine", write: bool = True) -> dict:
    steps, audits = _load(out_dir)

    colonies: dict = collections.defaultdict(_Colony)
    seen_edges: dict = collections.defaultdict(set)
    all_nodes, all_edges, pass_edges = set(), set(), set()
    refactor_idx = next((s["idx"] for s in steps if s["goal_class"] == "refactor"), None)
    high_tau_pre: set = set()   # add_feature edges that were high-τ before the refactor

    series = []
    for s in sorted(steps, key=lambda r: r["idx"]):
        gc, idx = s["goal_class"], s["idx"]
        path = _path(audits.get(idx, []), gran)
        edges = _edges(path)
        reuse = (sum(1 for e in edges if e in seen_edges[gc]) / len(edges)) if edges else None
        all_nodes.update(path)
        for e in edges:
            seen_edges[gc].add(e)
            all_edges.add(e)
        if s["step_verify"] == "PASS":
            colonies[gc].deposit(edges)
            pass_edges.update(edges)
        if refactor_idx is not None and idx == refactor_idx:
            high_tau_pre = {e for e, w in colonies["add_feature"].tau.items() if w >= 1.0}
        series.append({
            "idx": idx, "step_id": s["step_id"], "goal_class": gc, "verify": s["step_verify"],
            "path_len": len(path), "edges": len(edges),
            "segment_reuse": round(reuse, 3) if reuse is not None else None,
            "tau_entropy": round(_entropy(colonies[gc].tau), 3),
            "tau_edges": len(colonies[gc].tau),
        })

    # --- descriptive summaries (no verdict) ---
    af = [r for r in series if r["goal_class"] == "add_feature"]
    conv = {"entropy_first": af[0]["tau_entropy"] if af else None,
            "entropy_last": af[-1]["tau_entropy"] if af else None,
            "tau_edges_last": af[-1]["tau_edges"] if af else None,
            "reuse_trend": [r["segment_reuse"] for r in af]}
    # staleness: post-refactor add_feature paths — how many pre-refactor high-τ edges reappear
    post = [r for r in series if r["goal_class"] == "add_feature" and refactor_idx is not None
            and r["idx"] > refactor_idx]
    post_edges = {e for r in post for e in _edges(_path(audits.get(r["idx"], []), gran))}
    stale = {"high_tau_pre_count": len(high_tau_pre),
             "reused_post_refactor": len(high_tau_pre & post_edges),
             "stale_dropped": len(high_tau_pre - post_edges)} if refactor_idx is not None else None
    recall = [{"step_id": r["step_id"], "segment_reuse": r["segment_reuse"]}
              for r in series if r["goal_class"] == "recall_probe"]

    stats = {
        "stream": steps[0]["stream"] if steps else "?",
        "granularity": gran,
        "n_steps": len(steps),
        "verify_pass": sum(1 for s in steps if s["step_verify"] == "PASS"),
        "distinct_nodes": len(all_nodes),
        "distinct_edges": len(all_edges),
        "convergence_add_feature": conv,
        "clutter_ratio": round(len(all_edges) / max(1, len(pass_edges)), 3),
        "deposit_policy_null": [_run_policy(steps, audits, p, gran=gran)
                                for p in ("consequence", "frequency", "shuffle")],
        "staleness_post_refactor": stale,
        "recall_probes": recall,
        "series": series,
        "note": "STATS ONLY — descriptive time-series; no verdict. Design the null from the shapes.",
    }
    if write:
        name = "gauge_stats.json" if gran == "fine" else f"gauge_stats_{gran}.json"
        (out_dir / name).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return stats


def sweep(out_dir: Path, write: bool = True) -> dict:
    """Re-ask convergence at every GRANULARITY (offline; reuses the same audit). The shape we want to
    read: does coarsening collapse the drifting fine-grained full-paths onto a STABLE optimum —
    segment-reuse → 1.0, add_feature tau_edges plateaus, entropy stops climbing — while the
    consequence-vs-frequency clutter separation survives? That altitude is what a build phase keys on."""
    rows = []
    for g in GRANULARITIES:
        st = analyze(out_dir, gran=g, write=False)
        af_reuse = [r for r in st["convergence_add_feature"]["reuse_trend"] if r is not None]
        null = {p["policy"]: p for p in st["deposit_policy_null"]}
        rows.append({
            "granularity": g,
            "distinct_nodes": st["distinct_nodes"],
            "distinct_edges": st["distinct_edges"],
            "af_entropy_first": st["convergence_add_feature"]["entropy_first"],
            "af_entropy_last": st["convergence_add_feature"]["entropy_last"],
            "af_tau_edges_last": st["convergence_add_feature"]["tau_edges_last"],
            "af_reuse_mean": round(sum(af_reuse) / len(af_reuse), 3) if af_reuse else None,
            "af_reuse_last": af_reuse[-1] if af_reuse else None,
            "consequence_clutter": null["consequence"]["clutter_frac"],
            "frequency_clutter": null["frequency"]["clutter_frac"],
            "staleness": st["staleness_post_refactor"],
        })
    out = {"stream": rows[0] and analyze(out_dir, gran="fine", write=False)["stream"],
           "n_steps": len(_load(out_dir)[0]),
           "granularity_sweep": rows,
           "note": "STATS ONLY — convergence altitude sweep; no verdict."}
    if write:
        (out_dir / "gauge_granularity.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Memory gauge — offline stats over a stream audit")
    ap.add_argument("--out", required=True, help="the stream run dir (with steps.jsonl + audit/)")
    ap.add_argument("--granularity", default="fine", choices=GRANULARITIES,
                    help="path-node altitude (default fine = original)")
    ap.add_argument("--sweep", action="store_true",
                    help="re-analyze at every granularity and write gauge_granularity.json")
    args = ap.parse_args()
    out_dir = Path(args.out).resolve()

    if args.sweep:
        sw = sweep(out_dir)
        hdr = ("gran", "nodes", "edges", "ent0", "entN", "tauN", "reuseμ", "reuseN", "conseq", "freq")
        print(f"{hdr[0]:5} {hdr[1]:>5} {hdr[2]:>5} {hdr[3]:>5} {hdr[4]:>5} {hdr[5]:>5} "
              f"{hdr[6]:>6} {hdr[7]:>6} {hdr[8]:>6} {hdr[9]:>5}")
        for r in sw["granularity_sweep"]:
            print(f"{r['granularity']:5} {r['distinct_nodes']:>5} {r['distinct_edges']:>5} "
                  f"{r['af_entropy_first']:>5} {r['af_entropy_last']:>5} {r['af_tau_edges_last']:>5} "
                  f"{str(r['af_reuse_mean']):>6} {str(r['af_reuse_last']):>6} "
                  f"{r['consequence_clutter']:>6} {r['frequency_clutter']:>5}")
        return

    st = analyze(out_dir, gran=args.granularity)
    print(json.dumps({k: v for k, v in st.items() if k != "series"}, indent=2))
    print("\nper-step:")
    for r in st["series"]:
        print(f"  [{r['idx']:02d} {r['step_id']:14} {r['goal_class']:12}] verify={r['verify']} "
              f"path={r['path_len']} reuse={r['segment_reuse']} entropy={r['tau_entropy']} "
              f"tau_edges={r['tau_edges']}")


if __name__ == "__main__":
    main()
