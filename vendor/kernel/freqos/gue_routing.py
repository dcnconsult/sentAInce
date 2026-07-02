"""v0.49 GUE-routing capacity gate -- does level-repelled Z3 packing push K_c past the baseline?

Tests whether choosing the K stored Z3 patterns with **low pairwise coherence** ("level-repelled"
packing, the principle behind GUE level repulsion / low-coherence codebooks) raises the associative
capacity ``K_c`` above the i.i.d. random baseline (~89 at M=256, v0.46) -- or whether capacity is a
hard thermodynamic wall of the M-dimensional substrate, untouched by packing.

The honest prior is NULL: v0.47 showed the collapse past K_c is collective/catastrophic and
per-pattern coherence did not predict which patterns collapse. So a trustworthy null is the goal,
guarded by a **positive control** (deliberately MAXIMIZE coherence -- must harm if coherence matters)
and matched-support nulls. Two arms run side by side: Arm 1 (coherence-repulsion, load-bearing) and
Arm 2 (literal Odlyzko zero-spacing, exploratory/arbitrary). Reuses the unchanged ``tam`` recall and
``capacity.default_loads``; ``capacity.py`` is untouched. Emulator telemetry only -- no thermodynamic,
native-ternary, quantum, or number-theoretic claim. See ``docs/V049_GUE_ROUTING_GATE.md``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .capacity import default_loads
from .gue import PHI, load_zeros, nn_spacings_unfolded, spacing_discrepancy, unfold_zeros, zscore_separation
from .tam import OMEGA, TAM, corrupt, random_patterns


# --------------------------------------------------------------- pattern providers
def _encode(patterns: np.ndarray) -> np.ndarray:
    """Cube-root encode Z3 patterns -> complex, the exact geometry the engine recalls with."""
    return OMEGA ** np.asarray(patterns, dtype=np.int64)


def baseline_provider(k: int, m: int, rng: np.random.Generator) -> np.ndarray:
    """i.i.d. uniform Z3 patterns -- the v0.46 method (Poisson-like coherence)."""
    return random_patterns(k, m, rng)


def repel_provider(
    k: int, m: int, rng: np.random.Generator, *, pool_factor: int = 8, maximize: bool = False
) -> np.ndarray:
    """Farthest-first greedy selection of K patterns minimizing max pairwise coherence ("repelled").

    Draw a random pool of ``pool_factor*k`` patterns; greedily add the candidate whose maximum
    coherence to the already-selected set is smallest (``maximize=True`` flips to the *clustered*
    positive control). Preserves the per-column uniform Z3 marginal (gauge-invariant selection).
    """
    pool = random_patterns(pool_factor * k, m, rng)
    e = _encode(pool)  # (N, M)
    n = pool.shape[0]
    if n < k:
        raise ValueError("pool smaller than k")
    chosen = np.empty(k, dtype=np.int64)
    chosen_mask = np.zeros(n, dtype=bool)
    s0 = int(rng.integers(0, n))
    chosen[0] = s0
    chosen_mask[s0] = True
    cmax = np.abs(e @ np.conjugate(e[s0])) / m  # max coherence to the selected set
    sentinel = -np.inf if maximize else np.inf
    pick = np.argmax if maximize else np.argmin
    for t in range(1, k):
        work = np.where(chosen_mask, sentinel, cmax)
        j = int(pick(work))
        chosen[t] = j
        chosen_mask[j] = True
        cmax = np.maximum(cmax, np.abs(e @ np.conjugate(e[j])) / m)
    return pool[chosen]


def cluster_provider(k: int, m: int, rng: np.random.Generator, *, pool_factor: int = 8) -> np.ndarray:
    """Positive control: greedily MAXIMIZE max pairwise coherence (deliberately clustered packing)."""
    return repel_provider(k, m, rng, pool_factor=pool_factor, maximize=True)


_BETA_MULT = {"golden": PHI, "primes": np.sqrt(2.0)}


def _zero_positions(n: int) -> np.ndarray:
    """``n`` monotone unfolded positions from the bundled zeros; tile the spacing sequence if needed."""
    t0 = unfold_zeros(load_zeros())
    if t0.size >= n:
        return t0[:n]
    s = np.diff(t0)  # GUE-distributed spacings
    s_tiled = np.tile(s, int(np.ceil((n - 1) / s.size)))[: n - 1]
    return np.concatenate([[t0[0]], t0[0] + np.cumsum(s_tiled)])


def zero_routing_provider(
    k: int, m: int, rng: np.random.Generator, *, gamma: np.ndarray | None = None, beta: str = "golden"
) -> np.ndarray:
    """Arm 2 (exploratory): a zero-spacing-driven low-discrepancy Z3 lattice.

    Take ``k*m`` monotone unfolded zero positions ``t_n`` (the real zero-*spacing* sequence tiled if
    ``k*m`` exceeds the bundled count) as a **block of m positions per pattern** (full per-pattern
    entropy -- not one scalar per pattern, which would collapse the patterns onto a 1-D manifold), and
    digitize with a per-component Weyl frequency ``(i+1)*mult`` (which breaks the residual global-rotation
    structure): ``xi_k[i] = floor(3 * frac(t_{k*m+i} * (i+1) * mult))``. Yields genuinely high-dimensional
    patterns with coherence comparable to random, while the GUE spacing rides in the ``t_n``. Uniform per
    column (matched support). **Arbitrary, declared, no number-theoretic meaning** -- a fair control vs
    the generic Arm-1 repulsion. (``gamma`` overrides the bundled zeros.)
    """
    mult = _BETA_MULT.get(beta)
    if mult is None:
        raise ValueError("beta must be 'golden' or 'primes'")
    need = k * m
    t = (unfold_zeros(np.asarray(gamma, dtype=float))[:need] if gamma is not None else _zero_positions(need))
    freq = (np.arange(m) + 1.0) * mult  # per-component frequency breaks the global-rotation collapse
    xi = np.floor(3.0 * np.mod(t.reshape(k, m) * freq, 1.0)).astype(np.int64)
    return np.clip(xi, 0, 2).astype(np.int8)


def column_shuffle(patterns: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Independently permute each column across patterns: preserves marginals, destroys joint structure."""
    p = np.asarray(patterns).copy()
    for i in range(p.shape[1]):
        p[:, i] = p[rng.permutation(p.shape[0]), i]
    return p


def build_providers(pool_factor: int = 8, beta: str = "golden") -> dict:
    """Registry name -> provider(k, m, rng). column-shuffle wraps a repelled set then shuffles."""
    def repel(k, m, rng):
        return repel_provider(k, m, rng, pool_factor=pool_factor)

    def cluster(k, m, rng):
        return cluster_provider(k, m, rng, pool_factor=pool_factor)

    def zero_routing(k, m, rng):
        return zero_routing_provider(k, m, rng, beta=beta)

    def shuffle_repel(k, m, rng):
        return column_shuffle(repel_provider(k, m, rng, pool_factor=pool_factor), rng)

    return {
        "baseline": baseline_provider,
        "repel": repel,
        "zero-routing": zero_routing,
        "cluster": cluster,
        "column-shuffle": shuffle_repel,
    }


ARM_PROVIDERS = build_providers()


# --------------------------------------------------------------- coherence diagnostics
def coherence_matrix(patterns: np.ndarray) -> np.ndarray:
    """Pairwise coherence ``|<enc a, enc b>|/M`` (K x K, diag ~1) -- the v0.47 frustration Gram."""
    e = _encode(patterns)
    return np.abs(e @ np.conjugate(e).T) / e.shape[1]


def _off_diagonal(patterns: np.ndarray) -> np.ndarray:
    g = coherence_matrix(patterns)
    return g[np.triu_indices(g.shape[0], k=1)]


def coherence_stats(patterns: np.ndarray) -> dict:
    """Off-diagonal coherence summary: max (the repel target), mean, 99th-pct danger tail, median."""
    o = _off_diagonal(patterns)
    return {
        "c_max": float(o.max()),
        "c_mean": float(o.mean()),
        "c_p99": float(np.percentile(o, 99)),
        "c_p50": float(np.percentile(o, 50)),
    }


def coherence_spacing_fit(patterns: np.ndarray) -> dict:
    """NN-spacing of the coherence spectrum vs GUE vs Poisson (ties the arm to the level-repulsion picture).

    ``frac_small`` = fraction of unit-mean spacings below 0.5 (low = repelled/GUE-like, high = clustered).
    """
    sp = nn_spacings_unfolded(_off_diagonal(patterns))
    return {
        "gue_discrepancy": spacing_discrepancy(sp, "gue"),
        "poisson_discrepancy": spacing_discrepancy(sp, "poisson"),
        "frac_small": float(np.mean(sp < 0.5)),
    }


# --------------------------------------------------------------- capacity with a custom provider
def success_rate_patterns(
    provider, m: int, k: int, rng: np.random.Generator, *,
    p: int = 2, corrupt_frac: float = 0.30, threshold: float = 0.9, n_probe: int = 64, max_sweeps: int = 64,
) -> tuple[float, float]:
    """Faithful clone of ``tam.success_rate`` (z3) with an injected pattern provider."""
    pats = np.asarray(provider(k, m, rng), dtype=np.int8)
    if pats.shape != (k, m):
        raise ValueError(f"provider returned {pats.shape}, expected {(k, m)}")
    tam = TAM("z3")
    tam.store(pats)
    idx = rng.integers(0, k, size=n_probe)
    cues = corrupt(pats[idx], corrupt_frac, rng)
    res = tam.recall(cues, p=p, max_sweeps=max_sweeps, target=idx, threshold=threshold)
    return float(np.mean(res.success)), float(np.mean(res.sweeps))


def _cross(alpha: np.ndarray, success: np.ndarray, level: float) -> float:
    """Rightmost downward crossing of ``level`` in alpha-units (the v0.46 capacity-knee rule)."""
    cross = float("nan")
    for i in range(1, len(success)):
        if success[i] < level <= success[i - 1]:
            frac = (success[i - 1] - level) / (success[i - 1] - success[i])
            cross = float(alpha[i - 1] + frac * (alpha[i] - alpha[i - 1]))
    return cross


@dataclass(frozen=True)
class ProviderCurve:
    """A capacity sweep for one (arm, M) under a custom provider."""

    arm: str
    m: int
    k_values: np.ndarray
    success: np.ndarray
    success_std: np.ndarray
    sweeps: np.ndarray

    @property
    def alpha(self) -> np.ndarray:
        return self.k_values.astype(float) / self.m

    @property
    def k_c(self) -> float:
        return _cross(self.alpha, self.success, 0.5) * self.m


def capacity_with_provider(
    provider, m: int, loads, seed: int, *, arm: str = "",
    p: int = 2, corrupt_frac: float = 0.30, threshold: float = 0.9,
    n_probe: int = 64, n_trials: int = 5, max_sweeps: int = 64,
) -> ProviderCurve:
    """Sweep stored load K for one provider; locate K_c via the rightmost 0.5 success crossing."""
    k_values = np.array(sorted({int(x) for x in loads}), dtype=np.int64)
    streams = np.random.SeedSequence(seed).spawn(k_values.size * n_trials)
    succ = np.empty(k_values.size)
    sstd = np.empty(k_values.size)
    swps = np.empty(k_values.size)
    for i, k in enumerate(k_values):
        trials = np.array([
            success_rate_patterns(
                provider, m, int(k), np.random.default_rng(streams[i * n_trials + t]),
                p=p, corrupt_frac=corrupt_frac, threshold=threshold, n_probe=n_probe, max_sweeps=max_sweeps,
            )
            for t in range(n_trials)
        ])
        succ[i], sstd[i], swps[i] = trials[:, 0].mean(), trials[:, 0].std(), trials[:, 1].mean()
    return ProviderCurve(arm, m, k_values, succ, sstd, swps)


def delta_kc(arm_kcs: np.ndarray, baseline_kcs: np.ndarray) -> dict:
    """Per-seed Delta K_c (arm - baseline) with mean +/- std and z-separation (gue.zscore_separation)."""
    deltas = np.asarray(arm_kcs, dtype=float) - np.asarray(baseline_kcs, dtype=float)
    mean, std, z = zscore_separation(deltas)
    return {"delta_mean": mean, "delta_std": std, "z": z, "deltas": deltas}


def refinement_loads(kc: float, factors=(0.7, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2, 1.3)) -> list[int]:
    """A dense load grid around a known K_c knee (added to the coarse default_loads grid)."""
    return [max(2, int(round(f * kc))) for f in factors]


def combined_loads(m: int, kc_anchor: float, *, alpha_max: float = 0.6, n_points: int = 18) -> list[int]:
    """Coarse default_loads(M) brackets the collapse; refinement around kc_anchor gives Delta-K_c resolution."""
    coarse = default_loads(m, alpha_max=alpha_max, n_points=n_points)
    return sorted({*coarse, *refinement_loads(kc_anchor)})
