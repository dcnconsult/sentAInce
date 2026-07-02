"""Offline ENDOCRINE gauge — does an allostatic prune/CAP destabilize the colony? (STATS, no wiring)

The decisive cheap experiment the NEXT_PHASE_PLAN demands before building organ 3A: replay a colony
under three prune/CAP laws across synthetic ENERGY trajectories and measure whether making the Genome
constants *alive* evicts the recurring skeleton or destabilizes convergence.

Design (the only honest comparison): the deposit STREAM, the per-deposit weights, and the energy
TRAJECTORY are held IDENTICAL across all three regimes. The ONLY thing that varies is how each step's
``(prune_floor, cap)`` is derived from the metabolic read — so every difference in the outcome is
*purely* the allostatic law, nothing else.

  · static       — the current Genome constants (prune=0.05, cap=32). The control.
  · tier-stepped — plan option (A): discrete (prune, cap) per existing tier SATED/STARVING/HYPOXIA.
  · continuous   — plan option (B): a leaky-integrator hormone (cortisol) low-pass-filters the noisy
                   energy read; prune/cap are smooth functions of the hormone. The proposal's "ODE",
                   in its *stable* form — fast to rise, slow to clear (biological hysteresis), so it
                   sheds exploration under SUSTAINED stress but does NOT thrash on a single dip.

deposit()/consolidate() faithfully mirror ``exocortex.colony`` (decay-all → reinforce → prune≥floor;
sleep = decay → prune → cap to top-CAP) so the gauge predicts the LIVE organ. Stress source = the
internal-pool energy proxy (the chosen grounding) — a thrash gauge, not yet a cgroup read.

The decisive stats (the plan's "build (A) only if stable"):
  · good_edge_survival_min  — the WORST fraction of the recurring skeleton retained at any step. The
                              destabilization risk made a number: a law that dips here evicts real reflexes.
  · skeleton_flaps          — count of skeleton edges evicted then re-deposited (memory churn / jitter).
  · clutter_frac (final)    — fraction of one-off junk left in memory (the anti-clutter law must hold).
  · memory_tail_cv          — coefficient of variation of memory size over the last third (convergence).

STATS ONLY — no pass/fail verdict baked in; the numbers decide which law (if any) ships. Run:
  python -m exocortex.gauge.endocrine_gauge            # default trajectory + seed, prints the table
  python -m exocortex.gauge.endocrine_gauge --json out.json --seed 7
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

# ── colony thermodynamics (mirror of exocortex.colony / the Genome) ───────────────────────────────
DECAY = 0.9        # τ multiplier per deposit (stigmergic evaporation)
DEPOSIT = 1.0      # full-weight pheromone for a focused deposit
CONSOLIDATE_EVERY = 10   # tasks between circadian "sleeps" (CAP is applied at consolidate, like PreCompact)

# ── the current static Genome constants (the control regime) ──────────────────────────────────────
STATIC_PRUNE, STATIC_CAP = 0.05, 32

# ── tier thresholds (mirror exocortex.config.EnergyRegime, normalized energy e = E/e0 ∈ [0,1]) ─────
SATED_FRAC, HYPOXIA_FRAC = 0.5, 0.2

# ── allostatic envelope — the (prune, cap) endpoints the hormone interpolates between ──────────────
# Hypoxia → HIGH prune + LOW cap = tunnel-vision (shed exploration); sated → LOW prune + HIGH cap = dream.
PRUNE_LO, PRUNE_HI = 0.03, 0.12   # NB PRUNE_HI > weight_min(0.1): under sustained hypoxia even a
#                                   min-weight deposit is evicted next cycle — intended tunnel-vision,
#                                   measured here, not assumed.
CAP_LO, CAP_HI = 16, 40

# ── the hormone ODE: cortisol as a leaky integrator  dC/dt = α·stress − β·C  (Euler, per deposit) ──
# α > β ⇒ rises fast, clears slow (real cortisol). This is the smoothing that answers the plan's
# "a fluctuating floor could destabilize convergence" — the floor follows C, not the jittery raw E.
ALPHA, BETA = 0.45, 0.25

# ── tier-stepped table: tier → (prune, cap) ───────────────────────────────────────────────────────
TIER_TABLE = {"SATED": (PRUNE_LO, CAP_HI), "STARVING": (STATIC_PRUNE, STATIC_CAP),
              "HYPOXIA": (PRUNE_HI, CAP_LO)}

# ── the recurring procedural skeleton (the "true" routes that SHOULD converge) ────────────────────
# COMMON routes recur every few tasks → reinforced often → never in danger under ANY prune (the easy
# case). The RARE route recurs sparsely (every RARE_EVERY tasks): between deposits it decays toward the
# floor, so a prune SPIKE during a long hypoxia stretch can evict it before its next reinforcement.
# THAT is where the allostatic eviction risk actually lives — so we track it separately.
COMMON_TEMPLATES = [
    ["cue:build", "bash:python", "Edit:src", "bash:pytest", "bash:git"],
    ["cue:build", "Read:src", "Edit:src", "bash:pytest"],
    ["cue:debug", "bash:rg", "Read:src", "Edit:src", "bash:pytest", "bash:git"],
]
RARE_TEMPLATE = ["cue:deploy", "bash:docker", "bash:git"]   # a real-but-MARGINAL route
RARE_EVERY = 20                                              # deposited only every N tasks — sparse
#   enough that during a long hypoxia stretch it decays toward the floor before its next reinforcement,
#   so a high-enough prune spike CAN evict it. This is the exploration/reflex boundary: the route the
#   endocrine system is *deciding* whether to keep. (gap 9 was never at risk → an untestable null.)
CLUTTER_PROB = 0.5                                           # P(a task lays one one-off junk edge)


def _edges(path: list) -> list:
    return list(zip(path, path[1:]))


COMMON_EDGES = {e for t in COMMON_TEMPLATES for e in _edges(t)}
RARE_EDGES = set(_edges(RARE_TEMPLATE))
SKELETON = COMMON_EDGES | RARE_EDGES   # all edges that recur → the "true" memory that must survive

# energy_trajectory phases by fraction of the run (kept in sync with energy_trajectory below)
PHASES = (("sated", 0.0, 0.25), ("dip", 0.25, 0.50), ("thrash", 0.50, 0.75), ("recovery", 0.75, 1.0))


def _phase(i: int, n: int) -> str:
    f = i / max(1, n - 1)
    for name, lo, hi in PHASES:
        if lo <= f < hi or (name == "recovery" and f >= hi - 1e-9):
            return name
    return "recovery"


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _stress(e: float) -> float:
    """Instantaneous metabolic stress from the normalized energy read: 0 when sated (e≥0.5), →1 empty."""
    return _clamp01((SATED_FRAC - e) / SATED_FRAC)


def _tier(e: float) -> str:
    if e >= SATED_FRAC:
        return "SATED"
    if e < HYPOXIA_FRAC:
        return "HYPOXIA"
    return "STARVING"


# ── colony mechanics (faithful mirror of exocortex.colony.Colony) ─────────────────────────────────
def _deposit(tau: dict, edges: list, weight: float, prune: float) -> None:
    """decay-all → reinforce the path → prune the dust (keep w ≥ prune). The allostatic ``prune``
    varies per call — THAT is the organ under test."""
    if not edges:
        return
    add = max(0.0, weight) * DEPOSIT
    for k in list(tau):
        tau[k] *= DECAY
    for e in edges:
        tau[e] = tau.get(e, 0.0) + add
    for k in [k for k, w in tau.items() if w < prune]:
        del tau[k]


def _consolidate(tau: dict, prune: float, cap: int) -> None:
    """The circadian sleep: decay once → prune sub-floor → cap to the strongest ``cap`` edges."""
    for k in list(tau):
        tau[k] *= DECAY
    for k in [k for k, w in tau.items() if w < prune]:
        del tau[k]
    if len(tau) > cap:
        keep = dict(sorted(tau.items(), key=lambda kv: -kv[1])[:cap])
        tau.clear()
        tau.update(keep)


# ── synthetic world ───────────────────────────────────────────────────────────────────────────────
def energy_trajectory(n: int) -> list:
    """A normalized-energy path with the four phases that stress each law differently:
    sated plateau → starvation dip (into hypoxia) → thrash burst (noisy oscillation) → recovery."""
    rng = random.Random(0xE0E0)
    e = []
    for i in range(n):
        f = i / max(1, n - 1)
        if f < 0.25:                       # sated plateau
            v = 0.70
        elif f < 0.50:                     # starvation dip → deep hypoxia
            v = 0.70 - (f - 0.25) / 0.25 * 0.55     # 0.70 → 0.15
        elif f < 0.75:                     # thrash burst — noisy around the hypoxia/starving line
            v = 0.28 + 0.12 * math.sin(i * 1.7) + rng.uniform(-0.08, 0.08)
        else:                              # recovery
            v = 0.15 + (f - 0.75) / 0.25 * 0.50     # 0.15 → 0.65
        e.append(_clamp01(v))
    return e


def deposit_stream(n: int, seed: int) -> list:
    """``n`` tasks. Each task deposits a COMMON template's edges, the RARE route every ``RARE_EVERY``
    tasks, and (with prob ``CLUTTER_PROB``) one one-off junk edge that never recurs → must be pruned.
    Thrash-phase tasks lay weaker pheromone (the live session-quality discount). The stream is IDENTICAL
    across regimes — only the prune/cap law differs, so any outcome difference is purely the law."""
    rng = random.Random(seed)
    stream = []
    for i in range(n):
        f = i / max(1, n - 1)
        tmpl = COMMON_TEMPLATES[i % len(COMMON_TEMPLATES)]
        edges = list(_edges(tmpl))
        if i % RARE_EVERY == 0:
            edges += list(RARE_EDGES)
        if rng.random() < CLUTTER_PROB:
            edges.append((rng.choice(tmpl), f"junk:oneoff_{i}"))
        weight = 0.35 if 0.50 <= f < 0.75 else 1.0             # weaker deposits during the thrash burst
        stream.append((edges, weight))
    return stream


# ── the three laws ────────────────────────────────────────────────────────────────────────────────
def _law(regime: str, e: float, cortisol: float,
         prune_hi: float = PRUNE_HI, cap_lo: int = CAP_LO) -> tuple:
    if regime == "static":
        return STATIC_PRUNE, STATIC_CAP
    if regime == "tier":
        prune, cap = TIER_TABLE[_tier(e)]
        hypoxic = _tier(e) == "HYPOXIA"
        return (prune_hi if hypoxic else prune), (cap_lo if hypoxic else cap)
    # continuous: prune/cap are smooth functions of the SMOOTHED hormone, not raw energy
    prune = PRUNE_LO + cortisol * (prune_hi - PRUNE_LO)
    cap = round(CAP_HI - cortisol * (CAP_HI - cap_lo))
    return prune, cap


def _survival(mem: set, subset: set) -> float:
    return len(mem & subset) / len(subset) if subset else 1.0


def run_regime(regime: str, stream: list, energy: list,
               prune_hi: float = PRUNE_HI, cap_lo: int = CAP_LO) -> dict:
    """Replay the shared stream under one prune/cap law; track the decisive time-series. ``prune_hi`` /
    ``cap_lo`` override the hypoxia prune ceiling / cap floor (the continuous law's endpoints AND the tier
    HYPOXIA values) so the sweeps can find where real-route survival breaks."""
    tau: dict = {}
    cortisol = 0.0
    prev_common: set = set()
    n = len(stream)
    warmup = max(len(COMMON_TEMPLATES), RARE_EVERY) + 1   # skip the cold-start ramp for the min stats
    common_flaps = 0
    common_surv, rare_surv, mem_series = [], [], []
    clutter_by_phase: dict = {p[0]: [] for p in PHASES}
    prune_series, cap_series = [], []
    for i, (edges, weight) in enumerate(stream):
        e = energy[i]
        cortisol = _clamp01(cortisol + ALPHA * _stress(e) - BETA * cortisol)
        prune, cap = _law(regime, e, cortisol, prune_hi, cap_lo)
        _deposit(tau, edges, weight, prune)
        if (i + 1) % CONSOLIDATE_EVERY == 0:
            _consolidate(tau, prune, cap)
        mem = set(tau)
        cur_common = mem & COMMON_EDGES
        if i >= warmup:
            common_flaps += len(prev_common - cur_common)   # converged common edges evicted (jitter)
        prev_common = cur_common
        common_surv.append(_survival(mem, COMMON_EDGES))
        rare_surv.append(_survival(mem, RARE_EDGES))
        clut = {k for k in mem if k not in SKELETON}
        clutter_by_phase[_phase(i, n)].append(len(clut) / max(1, len(mem)))
        mem_series.append(len(mem))
        prune_series.append(round(prune, 4))
        cap_series.append(cap)

    post = slice(warmup, None)
    tail = mem_series[n * 2 // 3:]                           # convergence over the last third
    mean_tail = sum(tail) / len(tail) if tail else 0.0
    cv_tail = (math.sqrt(sum((x - mean_tail) ** 2 for x in tail) / len(tail)) / mean_tail) \
        if mean_tail else 0.0
    ph = {name: round(sum(v) / len(v), 3) if v else 0.0 for name, v in clutter_by_phase.items()}
    return {
        "regime": regime,
        "common_surv_min": round(min(common_surv[post]), 3),   # safety bar: converged routes never lost
        "common_flaps": common_flaps,
        "rare_surv_min": round(min(rare_surv[post]), 3),       # the real eviction risk under stress
        "rare_surv_final": round(rare_surv[-1], 3),
        "clutter_sated": ph["sated"],                          # thesis: keep exploration when sated …
        "clutter_hypoxia": round((ph["dip"] + ph["thrash"]) / 2, 3),   # … shed it under stress
        "memory_final": len(set(tau)),
        "memory_tail_cv": round(cv_tail, 3),
        "prune_range": [min(prune_series), max(prune_series)],
        "cap_range": [min(cap_series), max(cap_series)],
        "common_surv_series": [round(s, 2) for s in common_surv],
        "rare_surv_series": [round(s, 2) for s in rare_surv],
    }


def sweep_prune_hi(n: int, seed: int, ceilings: list) -> list:
    """Find the SAFE envelope for the hypoxia prune ceiling: as PRUNE_HI rises it sheds clutter harder
    (good) but eventually starts evicting the rare-but-real route during the hypoxia stretch (the cost).
    The knee is the recommended ceiling for the Genome."""
    energy = energy_trajectory(n)
    stream = deposit_stream(n, seed)
    rows = []
    for c in ceilings:
        r = run_regime("tier", stream, energy, prune_hi=c)   # the SHIPPING regime — prune_hi applies
        rows.append({"prune_hi": c, "rare_surv_min": r["rare_surv_min"],   # fully throughout hypoxia
                     "rare_surv_final": r["rare_surv_final"], "clutter_hypoxia": r["clutter_hypoxia"],
                     "common_surv_min": r["common_surv_min"]})
    return rows


def sweep_cap_lo(n: int, seed: int, caps: list) -> list:
    """Find the SAFE floor for the hypoxia CAP — the STRONGER behavioural lever. As CAP_LO drops the
    memory leans out hard (sheds clutter), but once it falls below the true skeleton size the
    consolidation sleep evicts REAL routes (the weakest first: the rare route, then common edges). The
    knee is at the skeleton size — keep CAP_LO above it."""
    energy = energy_trajectory(n)
    stream = deposit_stream(n, seed)
    rows = []
    for c in caps:
        r = run_regime("tier", stream, energy, cap_lo=c)     # the SHIPPING regime — cap_lo applies
        rows.append({"cap_lo": c, "common_surv_min": r["common_surv_min"],   # fully throughout hypoxia
                     "rare_surv_min": r["rare_surv_min"], "clutter_hypoxia": r["clutter_hypoxia"],
                     "memory_final": r["memory_final"]})
    return rows


def run(n: int = 60, seed: int = 1) -> dict:
    energy = energy_trajectory(n)
    stream = deposit_stream(n, seed)
    regimes = [run_regime(r, stream, energy) for r in ("static", "tier", "continuous")]
    return {
        "n_tasks": n, "seed": seed,
        "common_edges": len(COMMON_EDGES), "rare_edges": len(RARE_EDGES),
        "skeleton_edges": len(SKELETON),
        "energy_phases": "sated→starvation-dip→thrash-burst→recovery",
        "hormone": {"alpha": ALPHA, "beta": BETA},
        "regimes": regimes,
        "prune_hi_sweep": sweep_prune_hi(n, seed, [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]),
        "cap_lo_sweep": sweep_cap_lo(n, seed, [6, 8, 10, 12, 16, 20, 24, 32, 40]),
        "note": "STATS ONLY — common_surv_min/common_flaps = safety; clutter_sated vs _hypoxia = the "
                "mechanism; the prune/CAP sweeps' knees = the safe Genome envelopes (CAP is the stronger lever).",
    }


def _print(res: dict) -> None:
    print(f"endocrine gauge · {res['n_tasks']} tasks · seed {res['seed']} · "
          f"{res['common_edges']} common + {res['rare_edges']} rare edges · {res['energy_phases']}")
    print(f"hormone: cortisol leaky-integrator α={res['hormone']['alpha']} β={res['hormone']['beta']}\n")
    hdr = ("regime", "cmn_min", "flaps", "rare_min", "rare_fin", "clut_sat", "clut_hyp",
           "mem", "tail_cv", "prune", "cap")
    print(" ".join(f"{h:>8}" if i else f"{h:11}" for i, h in enumerate(hdr)))
    for r in res["regimes"]:
        pr = f"{r['prune_range'][0]:.2f}-{r['prune_range'][1]:.2f}"
        cp = f"{r['cap_range'][0]}-{r['cap_range'][1]}"
        print(f"{r['regime']:11} {r['common_surv_min']:>8} {r['common_flaps']:>8} "
              f"{r['rare_surv_min']:>8} {r['rare_surv_final']:>8} {r['clutter_sated']:>8} "
              f"{r['clutter_hypoxia']:>8} {r['memory_final']:>8} {r['memory_tail_cv']:>8} "
              f"{pr:>8} {cp:>8}")
    static = next((r for r in res["regimes"] if r["regime"] == "static"), None)
    print("\nsafety bar: cmn_min ≈ 1.0 + flaps 0 = the converged skeleton is never lost.")
    if static:
        print(f"mechanism (between-REGIME, in the stress phase): static clut_hyp={static['clutter_hypoxia']}"
              " vs allostatic below it = the floor sheds extra clutter under stress (modest; DECAY"
              " already does most of the work).")
    print("\nPRUNE_HI sweep (tier/shipping) — find the knee where the rare-but-real route starts dying:")
    print(f"  {'prune_hi':>8} {'rare_min':>8} {'rare_fin':>8} {'clut_hyp':>8} {'cmn_min':>8}")
    for s in res["prune_hi_sweep"]:
        print(f"  {s['prune_hi']:>8} {s['rare_surv_min']:>8} {s['rare_surv_final']:>8} "
              f"{s['clutter_hypoxia']:>8} {s['common_surv_min']:>8}")
    print("  read: rise prune_hi to shed more clutter; stop before rare_min drops below 1.0.")

    print(f"\nCAP_LO sweep (tier/shipping) — the STRONGER lever; knee at the skeleton size "
          f"({res['skeleton_edges']} edges):")
    print(f"  {'cap_lo':>8} {'rare_min':>8} {'cmn_min':>8} {'clut_hyp':>8} {'mem':>8}")
    for s in res["cap_lo_sweep"]:
        print(f"  {s['cap_lo']:>8} {s['rare_surv_min']:>8} {s['common_surv_min']:>8} "
              f"{s['clutter_hypoxia']:>8} {s['memory_final']:>8}")
    print("  read: drop cap_lo to lean out memory; stop BEFORE it falls under the skeleton size "
          "(rare dies first, then common).")
    print("\n  static = control · tier = plan (A) · continuous = the hormone ODE (plan B).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Endocrine gauge — allostatic prune/CAP stability (offline)")
    ap.add_argument("--tasks", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--json", default=None, help="also write the full result (with series) to this path")
    args = ap.parse_args()
    res = run(args.tasks, args.seed)
    _print(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
