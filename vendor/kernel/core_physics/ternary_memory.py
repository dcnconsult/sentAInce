"""Ternary associative-memory primitives shared by both projects.

Ported verbatim from the v0.39 audit package (only the ``phi6_potential`` import
was repointed to ``phi6_solver``). These NumPy/FP64 primitives back the v0.39
regression audit and the snap baselines; the FP32/torch path lives in
``phi6_solver.phi6_kinetic_settle``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np

from .phi6_solver import SEPARATRIX

TERNARY_VALUES = np.array([-1.0, 0.0, 1.0], dtype=float)


@dataclass(frozen=True)
class RelaxationResult:
    method: str
    active_overlap: float
    basin_match_rate: float
    exact_state_match_rate: float
    steps: int
    field_evaluations: int
    mean_abs_state: float
    final_delta: float
    threshold: float | None = None
    notes: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def generate_ternary_patterns(n_nodes: int, n_patterns: int, seed: int, p_zero: float = 1.0 / 3.0) -> np.ndarray:
    if n_nodes <= 0 or n_patterns <= 0:
        raise ValueError("n_nodes and n_patterns must be positive")
    if not 0.0 <= p_zero <= 1.0:
        raise ValueError("p_zero must be in [0,1]")
    rng = np.random.default_rng(seed)
    p_active = (1.0 - p_zero) / 2.0
    return rng.choice([-1.0, 0.0, 1.0], size=(n_patterns, n_nodes), p=[p_active, p_zero, p_active]).astype(float)


def hebbian_weights(patterns: np.ndarray) -> np.ndarray:
    patterns = np.asarray(patterns, dtype=float)
    if patterns.ndim != 2:
        raise ValueError("patterns must have shape (K,N)")
    n = patterns.shape[1]
    weights = patterns.T @ patterns / float(n)
    np.fill_diagonal(weights, 0.0)
    return weights


def corrupt_ternary_pattern(target: np.ndarray, corruption: float, seed: int) -> np.ndarray:
    target = np.asarray(target, dtype=float)
    if not 0.0 <= corruption <= 1.0:
        raise ValueError("corruption must be in [0,1]")
    rng = np.random.default_rng(seed + 100_000)
    cue = target.copy()
    n_flip = int(round(corruption * cue.size))
    if n_flip == 0:
        return cue
    indices = rng.choice(cue.size, n_flip, replace=False)
    for idx in indices:
        cue[idx] = rng.choice(TERNARY_VALUES[TERNARY_VALUES != cue[idx]])
    return cue


def hard_ternary_slicer(x: np.ndarray, threshold: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return np.where(x > threshold, 1.0, np.where(x < -threshold, -1.0, 0.0)).astype(float)


def phi6_basin_slicer(x: np.ndarray, separatrix: float = SEPARATRIX) -> np.ndarray:
    return hard_ternary_slicer(np.asarray(x, dtype=float), separatrix)


def active_overlap(state: np.ndarray, target: np.ndarray) -> float:
    state = np.asarray(state, dtype=float)
    target = np.asarray(target, dtype=float)
    denom = float(np.dot(target, target))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(state, target) / denom)


def basin_match_rate(state: np.ndarray, target: np.ndarray) -> float:
    return float(np.mean(np.asarray(state, dtype=float) == np.asarray(target, dtype=float)))


def one_pass_snap(weights: np.ndarray, cue: np.ndarray, target: np.ndarray, threshold: float) -> RelaxationResult:
    state = hard_ternary_slicer(weights @ np.asarray(cue, dtype=float), threshold)
    return RelaxationResult(
        method="one_pass_snap",
        active_overlap=active_overlap(state, target),
        basin_match_rate=basin_match_rate(state, target),
        exact_state_match_rate=basin_match_rate(state, target),
        steps=1,
        field_evaluations=1,
        mean_abs_state=float(np.mean(np.abs(state))),
        final_delta=0.0,
        threshold=threshold,
        notes="one dense field evaluation followed by threshold snap",
    )


def snap_relax(
    weights: np.ndarray,
    cue: np.ndarray,
    target: np.ndarray,
    threshold: float,
    max_steps: int = 32,
) -> RelaxationResult:
    state = np.asarray(cue, dtype=float).copy()
    final_delta = 0.0
    for step in range(1, max_steps + 1):
        nxt = hard_ternary_slicer(weights @ state, threshold)
        final_delta = float(np.max(np.abs(nxt - state)))
        state = nxt
        if final_delta == 0.0:
            break
    return RelaxationResult(
        method="snap_threshold",
        active_overlap=active_overlap(state, target),
        basin_match_rate=basin_match_rate(state, target),
        exact_state_match_rate=basin_match_rate(state, target),
        steps=step,
        field_evaluations=step,
        mean_abs_state=float(np.mean(np.abs(state))),
        final_delta=final_delta,
        threshold=threshold,
        notes="iterated hard ternary threshold relaxation",
    )


def snap_threshold_sweep_best(
    weights: np.ndarray,
    cue: np.ndarray,
    target: np.ndarray,
    thresholds: Iterable[float],
    max_steps: int = 32,
) -> RelaxationResult:
    results = [snap_relax(weights, cue, target, thr, max_steps=max_steps) for thr in thresholds]
    best = max(results, key=lambda r: (r.active_overlap, r.basin_match_rate, -r.steps))
    return RelaxationResult(**{**best.as_dict(), "method": "snap_threshold_sweep_best"})
