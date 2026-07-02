"""Offline ELIGIBILITY-TRACE gauge (organ 3D) — does a scalar-γ credit trace beat uniform deposit? (STATS)

The decisive cheap experiment before wiring 3D: in the live colony EVERY edge of a trail-segment gets the
SAME credit when the consequence (exit 0) fires (uniform deposit). 3D proposes a within-segment eligibility
trace — credit ∝ recency-to-consequence (`w·γ^Δ`, Δ = steps before the exit 0) — so the "ah-ha" step that
immediately preceded success crystallizes while the flailing prefix fades. This gauge tests three things,
exactly per the 3D directives:

  1. SEGMENT-LENGTH REALITY CHECK (`measure_real_segments`) — does the target topology (N≥4 "flail-then-
     succeed" segments) actually exist in the recorded audit, or are real segments 1–2 edges (P-C)? If the
     wild has no long segments, the math can't earn its keep → park 3D (the P-D precedent).
  2. SYNTHETIC A/B (`run_ab`) — an 8-edge flail-then-succeed segment; Arm A = uniform, Arm B = γ-trace.
  3. THE EVICTION HORIZON (the falsifiable metric) — with the 0.05 circadian prune floor, does Arm B drive
     the flail prefix beneath the floor far sooner than Arm A, while keeping the solution edge crystallized?

Mirrors `exocortex.colony` mechanics (decay-all → add → prune≥floor; DECAY=0.9, floor=0.05) so the gauge
predicts the LIVE organ. Self-contained, numpy-free — the same fail-open discipline as the hook (the whole
point of option A over the HDC/numpy form). STATS ONLY: the numbers gate the build, no verdict baked in.

  python -m exocortex.gauge.eligibility_gauge                       # synthetic A/B + sweep
  python -m exocortex.gauge.eligibility_gauge --real exocortex/results   # + real segment-length scan
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
from pathlib import Path

WEIGHT_MIN = 0.1   # the colony's floor on a session-quality deposit weight (a maximally-flailing session)

# ── colony thermodynamics (mirror of exocortex.colony / the Genome) ───────────────────────────────
DECAY = 0.9          # τ multiplier per deposit (stigmergic evaporation)
PRUNE_FLOOR = 0.05   # the slime-mold eviction floor (Genome thermodynamics.prune_floor)
DEPOSIT = 1.0        # full-weight pheromone
GAMMA = 0.80         # the eligibility decay (γ) — directive default


def eligibility(length: int, gamma: float) -> list:
    """Per-edge credit multiplier by distance from the exit-0 tail. Edge index 0 = oldest (deepest flail),
    index length-1 = the solution edge immediately before exit 0 (Δ=0 → full credit)."""
    return [gamma ** (length - 1 - i) for i in range(length)]


def eviction_horizon(v0: float, floor: float = PRUNE_FLOOR, decay: float = DECAY) -> int:
    """Deposits-until-eviction: how many decay cycles a one-off edge starting at ``v0`` survives before it
    falls below the prune floor (it is a flail one-off → only decays, never re-deposited). Closed form of
    the colony's decay+prune loop."""
    if v0 < floor:
        return 0
    return int(math.floor(math.log(floor / v0) / math.log(decay))) + 1


# ── synthetic flail-then-succeed segment ──────────────────────────────────────────────────────────
def run_ab(length: int = 8, tail_len: int = 2, gamma: float = GAMMA, weight: float = 1.0) -> dict:
    """One flail-then-succeed segment of ``length`` edges: the last ``tail_len`` are the SOLUTION (the clean
    route into exit 0, which recurs across sessions); the rest are FLAIL (one-off wandering). Deposit it
    under Arm A (uniform) vs Arm B (γ-trace), then apply ONE circadian consolidation (decay+prune), and
    also report each edge's standalone eviction horizon (deposits-to-floor if never re-deposited)."""
    elig = eligibility(length, gamma)
    add_uniform = [weight * DEPOSIT] * length
    add_trace = [weight * DEPOSIT * e for e in elig]
    solution_idx = set(range(length - tail_len, length))   # the clean tail

    def after_consolidate(adds: list) -> list:
        tau = {i: a for i, a in enumerate(adds)}           # the single deposit (no prior edges to decay)
        tau = {i: w * DECAY for i, w in tau.items()}       # the consolidation decay pass
        return [tau[i] if tau[i] >= PRUNE_FLOOR else 0.0 for i in range(length)]   # prune sub-floor

    tau_a, tau_b = after_consolidate(add_uniform), after_consolidate(add_trace)
    flail = [i for i in range(length) if i not in solution_idx]
    return {
        "length": length, "tail_len": tail_len, "gamma": gamma, "weight": weight,
        "tau_uniform": [round(x, 4) for x in tau_a],
        "tau_trace": [round(x, 4) for x in tau_b],
        "flail_survivors_uniform": sum(1 for i in flail if tau_a[i] > 0),
        "flail_survivors_trace": sum(1 for i in flail if tau_b[i] > 0),
        "solution_tau_uniform": round(min(tau_a[i] for i in solution_idx), 4),
        "solution_tau_trace": round(min(tau_b[i] for i in solution_idx), 4),
        # eviction horizon (deposits-to-floor) for the DEEPEST flail edge (index 0) — never re-deposited
        "deep_flail_horizon_uniform": eviction_horizon(add_uniform[0]),
        "deep_flail_horizon_trace": eviction_horizon(add_trace[0]),
    }


def run_multisession(length: int = 8, tail_len: int = 2, gamma: float = GAMMA, weight: float = 1.0,
                     sessions: int = 12, arm: str = "trace") -> dict:
    """The realistic dynamic: ``sessions`` successful flail-then-succeed runs. The SOLUTION tail is re-walked
    every session (recurs → reinforced); each session's FLAIL prefix is fresh one-off edges (unique keys).
    Deposit each session's segment (decay-all → add → prune≥floor), then a final consolidation. Reports the
    signal-to-noise the colony ends up with: solution crystallization vs lingering flail clutter."""
    elig = eligibility(length, gamma)
    tau: dict = {}
    sol_keys = [f"sol_{j}" for j in range(tail_len)]        # stable solution edges (recur)
    for s in range(sessions):
        # segment keys: fresh flail prefix + the stable solution tail (tail occupies the last positions)
        keys = [f"flail_{s}_{i}" for i in range(length - tail_len)] + sol_keys
        adds = [weight * DEPOSIT] * length if arm == "uniform" else [weight * DEPOSIT * e for e in elig]
        for k in list(tau):
            tau[k] *= DECAY
        for k, a in zip(keys, adds):
            tau[k] = tau.get(k, 0.0) + a
        for k in [k for k, w in tau.items() if w < PRUNE_FLOOR]:
            del tau[k]
    for k in list(tau):                                     # final circadian consolidation
        tau[k] *= DECAY
    for k in [k for k, w in tau.items() if w < PRUNE_FLOOR]:
        del tau[k]
    sol_tau = min((tau.get(k, 0.0) for k in sol_keys), default=0.0)
    flail_keys = [k for k in tau if k.startswith("flail_")]
    max_flail = max((tau[k] for k in flail_keys), default=0.0)
    return {
        "arm": arm, "length": length, "sessions": sessions,
        "solution_tau": round(sol_tau, 4),
        "flail_survivors": len(flail_keys),                # lingering one-off clutter (want LOW)
        "max_flail_tau": round(max_flail, 4),
        "snr": round(sol_tau / max_flail, 2) if max_flail > 0 else float("inf"),   # solution : worst clutter
        "memory_size": len(tau),
    }


def sweep(gammas: list, lengths: list, sessions: int = 12) -> list:
    """The P-C caveat made falsifiable: the γ-trace's benefit should VANISH at short lengths (γ^0 vs γ^1 ≈
    no discrimination) and grow with length. Reports, per (length, γ), the deep-flail eviction-horizon ratio
    (uniform/trace) and the multi-session clutter reduction (uniform survivors → trace survivors)."""
    rows = []
    for L in lengths:
        tl = min(2, L - 1)                                  # always leave ≥1 flail edge to discriminate
        for g in gammas:
            ab = run_ab(length=L, tail_len=tl, gamma=g)
            u = run_multisession(length=L, tail_len=tl, gamma=g, sessions=sessions, arm="uniform")
            t = run_multisession(length=L, tail_len=tl, gamma=g, sessions=sessions, arm="trace")
            ratio = (ab["deep_flail_horizon_uniform"] / ab["deep_flail_horizon_trace"]
                     if ab["deep_flail_horizon_trace"] else float("inf"))
            rows.append({"length": L, "gamma": g,
                         "horizon_uniform": ab["deep_flail_horizon_uniform"],
                         "horizon_trace": ab["deep_flail_horizon_trace"],
                         "horizon_ratio": round(ratio, 2),
                         "flail_surv_uniform": u["flail_survivors"],
                         "flail_surv_trace": t["flail_survivors"],
                         "snr_uniform": u["snr"], "snr_trace": t["snr"]})
    return rows


# ── Directive 1: real segment-length reality check ────────────────────────────────────────────────
def measure_real_segments(results_root: str) -> dict:
    """Reconstruct colony SEGMENTS from recorded audit JSONL and report the length distribution. A segment
    = the tool-steps (PreToolUse) the live trail accumulates between Bash consequences (it re-roots at each
    Bash PostToolUse). Skips files that aren't hook-audit JSONL (e.g. the demo host-ops command batches).
    The honest question: do N≥4 flail-then-succeed segments exist in the wild, or only short probes?"""
    files = glob.glob(os.path.join(results_root, "**", "*.jsonl"), recursive=True)
    seg_lengths: list = []
    sessions_seen, files_used, files_skipped = set(), 0, 0
    for f in files:
        try:
            recs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        except Exception:
            files_skipped += 1
            continue
        if not recs or not isinstance(recs[0], dict) or "event" not in recs[0]:
            files_skipped += 1            # not a hook-audit file (e.g. {"commands":[...]} demo batches)
            continue
        files_used += 1
        # walk per session in file order (ts-ordered as written); segment = PreToolUse run between Bash
        # PostToolUse consequences (success OR failure both close a segment in the live trail).
        cur: dict = {}
        for r in recs:
            sess = r.get("session", "?")
            sessions_seen.add(sess)
            ev, tool = r.get("event"), r.get("tool")
            if ev == "PreToolUse" and tool:
                cur[sess] = cur.get(sess, 0) + 1
            elif ev in ("PostToolUse", "PostToolUseFailure") and tool == "Bash":
                seg_lengths.append(cur.get(sess, 0) + 1)   # +1 for the closing Bash node
                cur[sess] = 0
        for sess, n in cur.items():                        # trailing open segment (no closing Bash)
            if n > 0:
                seg_lengths.append(n)
    seg_lengths.sort()
    n = len(seg_lengths)
    return {
        "results_root": results_root,
        "files_used": files_used, "files_skipped": files_skipped,
        "sessions": len(sessions_seen), "segments": n,
        "len_max": seg_lengths[-1] if n else 0,
        "len_mean": round(sum(seg_lengths) / n, 2) if n else 0.0,
        "len_median": seg_lengths[n // 2] if n else 0,
        "ge4_count": sum(1 for x in seg_lengths if x >= 4),
        "ge4_frac": round(sum(1 for x in seg_lengths if x >= 4) / n, 3) if n else 0.0,
        "histogram": {str(k): seg_lengths.count(k) for k in sorted(set(seg_lengths))},
        "note": "A segment ≥4 is where a γ-trace can discriminate; below that, trace ≈ uniform (P-C).",
    }


# ── reporting ─────────────────────────────────────────────────────────────────────────────────────
def _print_ab(ab: dict) -> None:
    print(f"A/B — {ab['length']}-edge flail-then-succeed segment (tail={ab['tail_len']} solution edges), "
          f"γ={ab['gamma']}, w={ab['weight']}; per-edge τ AFTER one consolidation (oldest→solution):")
    print(f"  uniform: {ab['tau_uniform']}")
    print(f"  γ-trace: {ab['tau_trace']}")
    print(f"  flail survivors above floor:  uniform={ab['flail_survivors_uniform']}  "
          f"trace={ab['flail_survivors_trace']}   (solution τ kept: uniform="
          f"{ab['solution_tau_uniform']} trace={ab['solution_tau_trace']})")
    print(f"  deepest-flail eviction horizon (deposits-to-floor):  uniform="
          f"{ab['deep_flail_horizon_uniform']}  trace={ab['deep_flail_horizon_trace']}  "
          f"→ trace evaporates the panic ~{ab['deep_flail_horizon_uniform'] / max(1, ab['deep_flail_horizon_trace']):.1f}× sooner")


def _print_sweep(rows: list) -> None:
    print("\nP-C caveat sweep — benefit vs segment length (horizon ratio + multi-session clutter survivors):")
    print(f"  {'len':>3} {'γ':>4} {'horiz_u':>7} {'horiz_t':>7} {'ratio':>5} "
          f"{'surv_u':>6} {'surv_t':>6} {'snr_u':>6} {'snr_t':>6}")
    for r in rows:
        print(f"  {r['length']:>3} {r['gamma']:>4} {r['horizon_uniform']:>7} {r['horizon_trace']:>7} "
              f"{r['horizon_ratio']:>5} {r['flail_surv_uniform']:>6} {r['flail_surv_trace']:>6} "
              f"{str(r['snr_uniform']):>6} {str(r['snr_trace']):>6}")
    print("  read: at len=2 (P-C short) trace≈uniform; the gap should open as length grows.")


def _print_real(real: dict) -> None:
    print(f"\nDirective 1 — REAL segment lengths from {real['results_root']}:")
    print(f"  hook-audit files used={real['files_used']} (skipped non-audit={real['files_skipped']}); "
          f"sessions={real['sessions']}; segments={real['segments']}")
    print(f"  length: max={real['len_max']} mean={real['len_mean']} median={real['len_median']}  "
          f"| N≥4: {real['ge4_count']} ({real['ge4_frac']*100:.0f}%)")
    print(f"  histogram (len→count): {real['histogram']}")
    print("  read: if N≥4 is ~0%, the flail-then-succeed topology is absent in this corpus → park 3D.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Eligibility-trace gauge (organ 3D) — γ-trace vs uniform (offline)")
    ap.add_argument("--length", type=int, default=8)
    ap.add_argument("--gamma", type=float, default=GAMMA)
    ap.add_argument("--sessions", type=int, default=12)
    ap.add_argument("--real", default=None, help="scan this results dir for real segment lengths (Directive 1)")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    ab = run_ab(length=args.length, gamma=args.gamma)                       # clean session (full weight)
    ab_flail = run_ab(length=args.length, gamma=args.gamma, weight=WEIGHT_MIN)   # maximally-flailing session
    sw = sweep(gammas=[0.7, 0.8, 0.9, 1.0], lengths=[2, 4, 8, 16], sessions=args.sessions)
    print("CLEAN session (deposit weight w=1.0):")
    _print_ab(ab)
    print(f"\nFLAILING session (deposit weight w={WEIGHT_MIN} — flail-then-succeed IS low-weight by "
          "construction: low success-rate → low _deposit_weight):")
    _print_ab(ab_flail)
    _print_sweep(sw)
    out = {"ab_clean": ab, "ab_flail": ab_flail, "sweep": sw}
    if args.real:
        real = measure_real_segments(args.real)
        _print_real(real)
        out["real"] = real
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
