"""Associative-memory capacity sweep for the dense Z3 TAM — the v0.46 reporting gate.

This is the falsifiable translation of the recurring question *"how many independent
memories can the Z3 statevector hold in simultaneous closure before the basins undergo
forced phase-transition?"* In sober terms: at what stored load does the dense Potts-Hopfield
field stop being able to cue-recall its own patterns, because the Hebbian crosstalk merges /
destabilises the attractor basins (the classic memory / spin-glass capacity transition).

It does NOT touch the production physics. It only *measures* the emulator: it sweeps the
number of stored patterns ``K`` at fixed neuron count ``M``, recalls a sample of corrupted
cues with :func:`freqos.tam.success_rate`, and records the cued-recall success vs the
load ``alpha = K / M``. From that curve it reads:

* ``alpha_c`` — the load at which mean success crosses 0.5 (the capacity knee), and ``k_c = alpha_c * M``;
* ``transition_width`` — the load span over which success falls 0.9 -> 0.1. A *narrow* width is
  a sharp, cliff-like collapse (the "forced phase-transition" reading); a *broad* width is a
  gradual crossover. This is the load-space analogue of the v0.45 settle-time ``cliff_w``.

Honest scope (extends ``docs/CLAIM_BOUNDARY.md``): this is finite-size emulator telemetry, not
a proof of a thermodynamic phase transition. ``alpha_c`` is a measured operating limit at the
swept ``(M, corruption, threshold, sweeps)``, expected to drift with ``M`` (finite-size
rounding of the transition). No native-ternary, quantum, or physical-spin-glass claim is made.
The Z3-vs-binary contrast is the fair same-task comparator (phasor-network theory predicts a
modest Potts edge), not a hardware win.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .tam import success_rate


@dataclass(frozen=True)
class CapacityCurve:
    """One load sweep: cued-recall success vs stored load for a single ``(M, kind)`` cell."""

    m: int
    kind: str  # "z3" or "binary"
    p: int
    corrupt_frac: float
    threshold: float
    max_sweeps: int
    n_probe: int
    n_trials: int
    k_values: np.ndarray  # (L,) stored-pattern counts swept
    success: np.ndarray  # (L,) mean cued-recall success, trial-averaged
    success_std: np.ndarray  # (L,) std across trials (transition is where this peaks)
    sweeps: np.ndarray  # (L,) mean field-settle sweeps to convergence

    @property
    def alpha(self) -> np.ndarray:
        """Load axis ``alpha = K / M`` (the order parameter's control variable)."""
        return self.k_values.astype(float) / self.m

    def _cross(self, level: float) -> float:
        """Load (in alpha units) where the descending success curve last crosses ``level``.

        Uses the *rightmost* downward bracket ``success[i-1] >= level > success[i]`` so a
        transient noise dip at light load can't be mistaken for the collapse; linear
        interpolation within that bracket. ``nan`` if the curve never falls below ``level``
        across the swept grid (capacity lies beyond ``alpha_max``) or starts below it.
        """
        a, s = self.alpha, self.success
        cross = float("nan")
        for i in range(1, len(s)):
            if s[i] < level <= s[i - 1]:
                frac = (s[i - 1] - level) / (s[i - 1] - s[i])
                cross = float(a[i - 1] + frac * (a[i] - a[i - 1]))  # keep the last (rightmost)
        return cross

    @property
    def alpha_c(self) -> float:
        """Capacity knee: load where mean success crosses 0.5."""
        return self._cross(0.5)

    @property
    def k_c(self) -> float:
        """Capacity in stored-pattern count: ``alpha_c * M`` (nan if off-grid)."""
        return self.alpha_c * self.m

    @property
    def transition_width(self) -> float:
        """Load span of the 0.9 -> 0.1 success fall — sharpness of the basin collapse.

        Narrow => cliff-like ("forced phase-transition"); broad => gradual crossover.
        ``nan`` if either shoulder is off the swept grid.
        """
        hi, lo = self._cross(0.9), self._cross(0.1)
        return float(lo - hi)


@dataclass
class CapacityReport:
    """A family of capacity curves swept over several ``M`` (and/or ``kind``)."""

    curves: list[CapacityCurve] = field(default_factory=list)

    def by_kind(self, kind: str) -> list[CapacityCurve]:
        return [c for c in self.curves if c.kind == kind]


def capacity_sweep(
    m: int,
    loads: np.ndarray | list[int],
    kind: str = "z3",
    *,
    p: int = 2,
    corrupt_frac: float = 0.30,
    threshold: float = 0.9,
    max_sweeps: int = 64,
    n_probe: int = 64,
    n_trials: int = 5,
    seed: int = 0,
) -> CapacityCurve:
    """Sweep stored load ``K`` over ``loads`` for an ``M``-neuron TAM; return a capacity curve.

    For each ``K`` the success rate is averaged over ``n_trials`` independent pattern draws
    (each draw probes ``n_probe`` corrupted cues), so the trial std flags the transition region.
    """
    if kind not in ("z3", "binary"):
        raise ValueError("kind must be 'z3' or 'binary'")
    k_values = np.asarray(sorted(int(k) for k in loads), dtype=np.int64)
    if k_values.size == 0 or k_values[0] < 1:
        raise ValueError("loads must be >= 1 positive integers")

    succ = np.empty(k_values.size)
    sstd = np.empty(k_values.size)
    swps = np.empty(k_values.size)
    # one independent RNG stream per (load, trial) — reproducible, non-overlapping
    ss = np.random.SeedSequence(seed)
    streams = ss.spawn(k_values.size * n_trials)
    for i, k in enumerate(k_values):
        trial_succ = np.empty(n_trials)
        trial_swps = np.empty(n_trials)
        for t in range(n_trials):
            rng = np.random.default_rng(streams[i * n_trials + t])
            s, sw = success_rate(
                m=m, k=int(k), kind=kind, p=p, corrupt_frac=corrupt_frac,
                n_probe=n_probe, rng=rng, max_sweeps=max_sweeps,
            )
            trial_succ[t] = s
            trial_swps[t] = sw
        succ[i] = float(trial_succ.mean())
        sstd[i] = float(trial_succ.std())
        swps[i] = float(trial_swps.mean())

    return CapacityCurve(
        m=m, kind=kind, p=p, corrupt_frac=corrupt_frac, threshold=threshold,
        max_sweeps=max_sweeps, n_probe=n_probe, n_trials=n_trials,
        k_values=k_values, success=succ, success_std=sstd, sweeps=swps,
    )


def default_loads(m: int, alpha_max: float = 0.45, n_points: int = 16) -> list[int]:
    """A load grid up to ``alpha_max * M`` (binary Hopfield's alpha_c ~ 0.138 sits well inside)."""
    hi = max(2, int(round(alpha_max * m)))
    grid = np.unique(np.rint(np.linspace(1, hi, n_points)).astype(int))
    return [int(k) for k in grid if k >= 1]


def run_report(
    m_values: list[int],
    kinds: tuple[str, ...] = ("z3", "binary"),
    *,
    alpha_max: float = 0.45,
    n_points: int = 16,
    **sweep_kwargs,
) -> CapacityReport:
    """Sweep every ``(M, kind)`` cell and bundle the curves into a :class:`CapacityReport`."""
    report = CapacityReport()
    for m in m_values:
        loads = default_loads(m, alpha_max=alpha_max, n_points=n_points)
        for kind in kinds:
            report.curves.append(capacity_sweep(m, loads, kind=kind, **sweep_kwargs))
    return report
