"""HDC Episodic Memory-Palace gauge — does the FreqOS VSA solve the colony's cross-contamination + give
JIT next-step recall? STATS ONLY (offline mechanism-gate, like the granularity sweep), run against the
REAL frozen kernel (`freqos.phase_router` + `freqos.tam`), not a mirror.

The idea (the user's mnemonic→HDC mapping): instead of per-class colony files, encode every goal-class's
converged ROUTE as transitions in ONE bundled router — context = bind(room_vec, permute(c0, step)) (the
"loci" + the sequence Π), so `recall_successor(router, room⊕step, current_node)` returns the NEXT node and
other rooms' routes cancel by HDC orthogonality. This gauge MEASURES three claims, honestly:

  A · Separation — context(room)-keyed routing recovers a class's own next-step where a STATELESS bundle
      cross-contaminates (a shared source-node with divergent successors across classes → superposition).
  B · Sequence/JIT — the permutation Π disambiguates a node REVISITED at two positions within a route.
  C · Capacity — accuracy vs load T/M (transitions per dimension): the honest cliff. The kernel is blunt
      that recall degrades above capacity — "cancels to exactly zero" is aspirational; here is the number.

No model, no hook wiring. Reads nothing; writes `<out>/palace_gauge.json` (or stdout). Descriptive only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# --- locate the frozen kernel (read-only), like sentaince.organism.learned_signature ---
_ROOT = Path(__file__).resolve().parents[2]
for _cand in (_ROOT / "vendor" / "kernel", _ROOT / "vendor" / "kernel" / "src"):
    if (_cand / "freqos").is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))
from freqos.phase_router import build_router, recall_successor   # noqa: E402  (frozen kernel, read-only)
from freqos.tam import OMEGA, bind, permute, random_patterns      # noqa: E402


# A small library of realistic per-class procedural ROUTES (verb-altitude node sequences), with DELIBERATE
# overlaps: feature & bugfix share the edit→test skeleton; pytest is a shared source with DIVERGENT
# successors (commit on the green path vs re-edit), the cross-class confusion a stateless bundle blurs.
ROUTES = {
    "feature":  ["cue:feature", "Read:src", "Edit:src", "bash:pytest", "bash:git"],
    "bugfix":   ["cue:bugfix", "Read:src", "Edit:src", "bash:pytest", "Edit:src", "bash:pytest"],
    "deploy":   ["cue:deploy", "Edit:other", "bash:docker", "bash:kubectl", "bash:curl"],
    "search":   ["cue:search", "Grep:other", "Read:src", "Read:test"],
    "vcs":      ["cue:vcs", "bash:git", "bash:git", "bash:pytest"],
}


def _codebook(labels, m, rng):
    cb = random_patterns(len(labels), m, rng)
    return cb, (OMEGA ** cb.astype(np.int64)), {lab: i for i, lab in enumerate(labels)}


def _palace(routes: dict, m: int, rng, use_room: bool, margin: float = 0.03) -> dict:
    """Store every route's transitions in ONE router (room+step context if use_room) and route them all
    back. Returns accuracy + the hallucination(wrong)/graceful(no_basin) split + load."""
    labels = sorted({n for r in routes.values() for n in r})
    cb, enc, ix = _codebook(labels, m, rng)
    rooms = random_patterns(len(routes), m, rng)
    c0 = random_patterns(1, m, rng)[0]

    contexts, srcs, succs, true_idx, probes = [], [], [], [], []
    for ci, route in enumerate(routes.values()):
        for step in range(len(route) - 1):
            ctx = bind(rooms[ci], permute(c0, step)) if use_room else permute(c0, step)
            contexts.append(ctx); srcs.append(cb[ix[route[step]]]); succs.append(cb[ix[route[step + 1]]])
            true_idx.append(ix[route[step + 1]]); probes.append((ctx, route[step]))
    router = build_router(np.array(contexts), np.array(srcs), np.array(succs))

    correct = wrong = nob = 0
    for (ctx, s_lab), tsi in zip(probes, true_idx):
        hat, conf, run = recall_successor(router, ctx, cb[ix[s_lab]], enc)
        if hat == tsi:
            correct += 1
        elif conf - run > margin:
            wrong += 1          # confident wrong = hallucination
        else:
            nob += 1            # ambiguous, did not commit = graceful
    t = len(true_idx)
    return {"T": t, "T_over_M": round(t / m, 3), "accuracy": round(correct / t, 3),
            "wrong_route": round(wrong / t, 3), "no_basin": round(nob / t, 3)}


def _capacity(m: int, reps_list, seed: int = 0) -> list:
    """Sweep load by replicating the route library R times (distinct rooms) → T grows; accuracy vs T/M."""
    out = []
    for reps in reps_list:
        routes = {f"{k}#{r}": v for r in range(reps) for k, v in ROUTES.items()}
        res = _palace(routes, m, np.random.default_rng(seed), use_room=True)
        res["n_classes"] = len(routes)
        out.append(res)
    return out


def gauge(m: int = 1024, seed: int = 0) -> dict:
    rng = lambda: np.random.default_rng(seed)   # noqa: E731  (fresh, deterministic per call)
    room = _palace(ROUTES, m, rng(), use_room=True)
    flat = _palace(ROUTES, m, rng(), use_room=False)
    return {
        "M": m, "n_classes": len(ROUTES),
        "separation": {"room_context": room, "stateless": flat,
                       "delta_accuracy": round(room["accuracy"] - flat["accuracy"], 3)},
        "capacity": _capacity(m, [1, 2, 4, 8, 16, 32], seed),
        "note": "STATS ONLY — offline HDC palace gauge over the frozen kernel; no verdict. "
                "Separation = room-context vs stateless next-step accuracy; capacity = accuracy vs T/M.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="HDC memory-palace gauge (offline, frozen kernel)")
    ap.add_argument("--m", type=int, default=1024, help="HDC dimension")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="", help="optional dir to write palace_gauge.json")
    args = ap.parse_args()
    st = gauge(args.m, args.seed)
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "palace_gauge.json").write_text(json.dumps(st, indent=2), encoding="utf-8")
    sep = st["separation"]
    print(f"M={st['M']}  classes={st['n_classes']}")
    print(f"SEPARATION  room-context acc={sep['room_context']['accuracy']}  "
          f"stateless acc={sep['stateless']['accuracy']}  Δ={sep['delta_accuracy']}")
    print(f"  room: {sep['room_context']}\n  flat: {sep['stateless']}")
    print("CAPACITY (accuracy vs load):")
    print(f"  {'classes':>7} {'T':>5} {'T/M':>6} {'acc':>6} {'wrong':>6} {'nobasin':>7}")
    for r in st["capacity"]:
        print(f"  {r['n_classes']:>7} {r['T']:>5} {r['T_over_M']:>6} {r['accuracy']:>6} "
              f"{r['wrong_route']:>6} {r['no_basin']:>7}")


if __name__ == "__main__":
    main()
