"""v0.53 phase-router: a content-addressed, self-referential Z3 phase memory (the comma <-> TAM bridge).

v0.52 made a voice walk the circle-of-fifths basins, kicking to a *fixed* next fifth. This makes the kick
**target** an associative recall: states are M-dim Z3 patterns, transitions ``s -> s'`` are stored with the
freqOS HDC primitives, the Pythagorean comma is the **clock** (when to step), and the stored bundle is the
**router** (where to step). Feeding the memory's own accumulated holonomy back as routing context closes a
**self-referential** loop -- past kicks influence future basin choice.

Headline falsifiable claim: a *context-dependent* router navigates a trajectory that **revisits** a state
(same state, two successors, disambiguated by history) that a **stateless** lookup cannot (it bundles both
successors onto one key -> recall is a superposition -> ~0.5 accuracy). Two context schemes are compared:
holonomy-as-context (self-referential) and previous-state context, vs the stateless baseline. The routing
capacity knee ``T_c/M`` is reported against the established static wall ``K_c ~= 0.40*M``.

Reuses ``tam`` (HDC bind/bundle/permute + cleanup) and ``comma_holonomy`` (the clock) unchanged; emulator
telemetry only -- no acoustic / tuning / quantum / zeta claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from harmonic_basin.comma_holonomy import RRFGovernorConfig, comma_walk, pythagorean_comma_cents

from .gue_routing import _cross
from .tam import OMEGA, bind, bundle, permute, random_patterns


# --------------------------------------------------------------- HDC sequence memory
def inv(x: np.ndarray) -> np.ndarray:
    """Z3 bind inverse: ``(3 - x) % 3`` (binding by ``inv(x)`` undoes binding by ``x``)."""
    return ((3 - np.asarray(x, dtype=np.int64)) % 3).astype(np.int8)


def key(context: np.ndarray, source: np.ndarray) -> np.ndarray:
    """Context-keyed source: ``bind(context, permute(source, 1))`` (permute breaks the bind symmetry)."""
    return bind(context, permute(np.asarray(source), 1))


def encode_transition(context: np.ndarray, source: np.ndarray, successor: np.ndarray) -> np.ndarray:
    """One transition vector: the context-keyed source bound to the successor."""
    return bind(key(context, source), successor)


def build_router(contexts: np.ndarray, sources: np.ndarray, successors: np.ndarray) -> np.ndarray:
    """Bundle all transition vectors into one router hypervector (M,)."""
    trans = np.stack([encode_transition(contexts[i], sources[i], successors[i]) for i in range(len(sources))])
    return bundle(trans)


def recall_successor(router: np.ndarray, context: np.ndarray, source: np.ndarray, enc_codebook: np.ndarray):
    """Unbind the key from the router and clean up to the nearest codebook state.

    Returns ``(index, confidence, runner_up)`` -- nearest-codebook (one-shot HDC cleanup) with the top and
    second overlap magnitudes, so the safety metric can tell a confident wrong route from a no-basin miss.
    """
    m = enc_codebook.shape[1]
    noisy = bind(router, inv(key(context, source)))
    ov = np.abs((OMEGA ** noisy.astype(np.int64)) @ np.conjugate(enc_codebook).T) / m  # (n_states,)
    order = np.argsort(ov)[::-1]
    return int(order[0]), float(ov[order[0]]), float(ov[order[1]])


# --------------------------------------------------------------- context schemes
def comma_count(holonomy: float) -> int:
    """Integer comma loops accrued: ``floor(|holonomy| / pythagorean_comma)`` -- the self-referential counter."""
    return int(abs(holonomy) // pythagorean_comma_cents())


def build_contexts(traj: list[int], loop: list[int], scheme: str, codebook: np.ndarray, c0: np.ndarray) -> np.ndarray:
    """Per-transition context (M,) for each scheme. Guard G1: holonomy ctx uses only the loop count."""
    m = codebook.shape[1]
    n = len(traj) - 1
    ctx = np.zeros((n, m), dtype=np.int8)
    for i in range(n):
        if scheme == "stateless":
            pass  # zeros
        elif scheme == "prev_state":
            ctx[i] = codebook[traj[i - 1]] if i > 0 else 0
        elif scheme == "holonomy":
            ctx[i] = permute(c0, loop[i])  # base context advanced once per comma loop
        else:
            raise ValueError("scheme must be stateless | prev_state | holonomy")
    return ctx


# --------------------------------------------------------------- the revisit-disambiguation test
def figure_eight(n_states: int, rng: np.random.Generator, arm_len: int = 4):
    """A trajectory that revisits a pivot X with two different successors: [X,A,P..,X,B,Q..].

    Returns ``(traj, loop, pivot_positions, succ_indices)``: ``loop[i]`` is the comma-loop index of
    transition ``i`` (0 for the first pass through X, 1 for the second).
    """
    idx = rng.choice(n_states, size=3 + 2 * arm_len, replace=False)
    x, a, b = int(idx[0]), int(idx[1]), int(idx[2])
    p, q = idx[3:3 + arm_len].tolist(), idx[3 + arm_len:].tolist()
    traj = [x, a, *p, x, b, *q]
    p2 = 2 + arm_len  # position of the second X (its transition routes to B)
    loop = [0] * p2 + [1] * (len(traj) - p2)
    return traj, loop, (0, p2), (a, b)


def revisit_accuracy(m: int, n_states: int, scheme: str, rng: np.random.Generator, arm_len: int = 4):
    """Route every transition of a figure-8 under ``scheme``; return pivot/non-pivot accuracy + margin.

    ``pivot_acc`` averages the two X-source routings (the revisit); ``nonpivot_acc`` the rest;
    ``pre_margin`` is the pre-cleanup overlap (correct - wrong successor) at the pivots (guard G5).
    """
    s = random_patterns(n_states, m, rng)
    enc_s = OMEGA ** s.astype(np.int64)
    c0 = random_patterns(1, m, rng)[0]
    traj, loop, pivots, _succ = figure_eight(n_states, rng, arm_len)
    ctx = build_contexts(traj, loop, scheme, s, c0)
    sources = s[traj[:-1]]
    successors = s[traj[1:]]
    router = build_router(ctx, sources, successors)

    correct, pivot_correct, pre_margins = [], [], []
    for i in range(len(traj) - 1):
        idx_hat, _conf, _run = recall_successor(router, ctx[i], sources[i], enc_s)
        hit = idx_hat == traj[i + 1]
        correct.append(hit)
        if i in pivots:
            pivot_correct.append(hit)
            noisy = bind(router, inv(key(ctx[i], sources[i])))
            ov = np.abs((OMEGA ** noisy.astype(np.int64)) @ np.conjugate(enc_s).T) / m
            other = pivots[1] if i == pivots[0] else pivots[0]
            wrong = traj[other + 1]  # the other pivot's successor (what stateless confuses it with)
            pre_margins.append(float(ov[traj[i + 1]] - ov[wrong]))
    nonpivot = [c for j, c in enumerate(correct) if j not in pivots]
    return {
        "pivot_acc": float(np.mean(pivot_correct)),
        "nonpivot_acc": float(np.mean(nonpivot)) if nonpivot else float("nan"),
        "pre_margin": float(np.mean(pre_margins)),
    }


# --------------------------------------------------------------- routing capacity (bridge to 0.40*M)
@dataclass(frozen=True)
class RoutingCurve:
    m: int
    t_values: np.ndarray
    accuracy: np.ndarray
    accuracy_std: np.ndarray
    wrong_route: np.ndarray  # confident-but-wrong (hallucination) rate per load
    no_basin: np.ndarray  # graceful (sub-threshold) rate per load

    @property
    def alpha(self) -> np.ndarray:
        return self.t_values.astype(float) / self.m

    @property
    def t_c(self) -> float:
        return _cross(self.alpha, self.accuracy, 0.5) * self.m

    @property
    def t_c_over_m(self) -> float:
        return self.t_c / self.m


def _store_and_route(m: int, t: int, rng: np.random.Generator, margin: float):
    """Store ``t`` random transitions (holonomy-keyed) in one router; route them all back. Returns rates.

    Accuracy is argmax-correct (HDC cleanup = nearest codebook state). A *failure* is a **wrong_route**
    (hallucination) only if the recall committed -- top overlap exceeds the runner-up by ``margin``;
    otherwise it is **no_basin** (ambiguous, the graceful mode HDC overload degrades into).
    """
    n_states = max(2 * t, 8)  # n_states >= max(T): each transition a distinct pair (guard G3)
    s = random_patterns(n_states, m, rng)
    enc_s = OMEGA ** s.astype(np.int64)
    c0 = random_patterns(1, m, rng)[0]
    src_idx = rng.integers(0, n_states, size=t)
    dst_idx = rng.integers(0, n_states, size=t)
    ctx = np.stack([permute(c0, j) for j in range(t)])  # a distinct holonomy-style context per transition
    router = build_router(ctx, s[src_idx], s[dst_idx])
    correct = wrong = nob = 0
    for j in range(t):
        idx_hat, conf, run = recall_successor(router, ctx[j], s[src_idx[j]], enc_s)
        if idx_hat == dst_idx[j]:
            correct += 1
        elif conf - run > margin:
            wrong += 1  # confidently routed to a different stored state (hallucination)
        else:
            nob += 1  # ambiguous: did not commit (graceful)
    return correct / t, wrong / t, nob / t


def routing_capacity(m: int, t_values, seed: int, *, n_trials: int = 5, margin: float = 0.03) -> RoutingCurve:
    """Routing accuracy vs the number of stored transitions; the derail knee bridges to K_c ~= 0.40*M."""
    tv = np.array(sorted({int(t) for t in t_values if int(t) >= 1}), dtype=np.int64)
    streams = np.random.SeedSequence(seed).spawn(tv.size * n_trials)
    acc, std, wr, nb = (np.empty(tv.size) for _ in range(4))
    for i, t in enumerate(tv):
        trials = np.array([_store_and_route(m, int(t), np.random.default_rng(streams[i * n_trials + k]), margin)
                           for k in range(n_trials)])
        acc[i], std[i] = trials[:, 0].mean(), trials[:, 0].std()
        wr[i], nb[i] = trials[:, 1].mean(), trials[:, 2].mean()
    return RoutingCurve(m, tv, acc, std, wr, nb)


# --------------------------------------------------------------- the comma clock + controls
@dataclass
class RoutedTrace:
    steps: list = field(default_factory=list)  # (step, holonomy, comma_count, s_before, s_hat, correct, conf)

    def routing_accuracy(self) -> float:
        rs = [r for r in (self.steps or []) if r[5] is not None]
        return float(np.mean([r[5] for r in rs])) if rs else float("nan")

    def n_kicks(self) -> int:
        return len(self.steps or [])


def comma_routed_walk(traj: list[int], m: int, cfg: RRFGovernorConfig, seed: int = 0,
                      temperament: str = "just", shuffle: bool = False) -> RoutedTrace:
    """Run the comma clock; on each UNLOCK kick, route to the associatively-recalled next state.

    The stored trajectory's transitions (holonomy-keyed) are the router; the comma walk is the clock.
    ``temperament='et'`` (control) yields no comma -> no kicks -> no routing. ``shuffle`` (control)
    permutes the successor map -> navigation collapses.
    """
    rng = np.random.default_rng(seed)
    s = random_patterns(len(traj), m, rng)  # one state code per trajectory position (distinct)
    enc_s = OMEGA ** s.astype(np.int64)
    c0 = random_patterns(1, m, rng)[0]
    succ_order = rng.permutation(len(traj) - 1) if shuffle else np.arange(len(traj) - 1)
    ctx = np.stack([permute(c0, k) for k in range(len(traj) - 1)])
    sources = s[np.arange(len(traj) - 1)]
    successors = s[1:][succ_order]  # shuffle breaks source->successor association
    router = build_router(ctx, sources, successors)

    walk = comma_walk(len(traj) * 24, cfg, temperament=temperament)  # plenty of fifths to drive the kicks
    out = RoutedTrace(steps=[])
    pos, n_trans = 0, len(sources)
    for st in walk.steps:
        if not st.kicked or pos >= n_trans:
            continue
        cc = comma_count(st.raw_holonomy)
        idx_hat, conf, _run = recall_successor(router, permute(c0, pos), s[pos], enc_s)
        correct = bool(idx_hat == pos + 1)  # the trajectory's true successor of position pos
        out.steps.append((st.step, st.raw_holonomy, cc, pos, idx_hat, correct, conf))
        pos = idx_hat if (0 <= idx_hat < n_trans) else pos + 1  # follow the recalled route (the walk)
    return out


def random_router(m: int, t: int, rng: np.random.Generator) -> np.ndarray:
    """Control: a router bundled from purely random transition vectors (no stored map)."""
    return bundle(random_patterns(t, m, rng))


# --------------------------------------------------------------- verdict
def phase_router_verdict(revisit: dict, capacity: RoutingCurve, controls: dict) -> dict:
    """CONFIRMED iff context beats stateless on revisits, safety holds, and controls show no navigation."""
    floor = revisit["stateless"]["mean"] + 2 * revisit["stateless"]["std"]
    ctx_beats = revisit["holonomy"]["mean"] > floor and revisit["prev_state"]["mean"] > floor
    below_knee = capacity.t_values <= (capacity.t_c if not np.isnan(capacity.t_c) else capacity.t_values[-1])
    # safe = failures are graceful: wrong_route (hallucination) stays low AND below no_basin (ambiguity)
    wr, nb = capacity.wrong_route[below_knee], capacity.no_basin[below_knee]
    safe = bool(below_knee.any() and np.nanmax(wr) < 0.15 and np.all(wr <= nb + 1e-9))
    controls_absent = all(v < 0.6 for v in controls.values())  # ET/shuffle/random -> no coherent navigation
    confirmed = bool(ctx_beats and safe and controls_absent)
    return {
        "verdict": "CONFIRMED" if confirmed else "NOT CONFIRMED",
        "context_beats_stateless": bool(ctx_beats),
        "wrong_route_safe": bool(safe),
        "controls_absent": bool(controls_absent),
        "t_c_over_m": capacity.t_c_over_m,
        "bridge": ("inherit" if 0.35 <= capacity.t_c_over_m <= 0.45
                   else "below" if capacity.t_c_over_m < 0.35 else "beat (audit)"),
    }
