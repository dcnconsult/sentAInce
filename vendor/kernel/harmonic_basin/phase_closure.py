"""Compatible interaction logic: the same-key permitted-coupling manifold.

Turns the circle-of-fifths topology into the quantities the protocol needs:

* per-node **coupling confidence** in [0, 1] -> fed to the shared kinetic
  governor as its ``mask``. Compatible (same-key) nodes pass field energy;
  wolf / wrong-key nodes are zeroed ("do not couple"), so in the governor they
  receive no interaction field, friction decays their momentum, and they coast
  down the separatrix to the 0-well (abstain).
* **phase order** (a Kuramoto-style coherence in [0, 1]) -> the "measure only
  after stable resonance" readiness signal at the phase level.
* directional **balance** (flat vs sharp) -> drives the directional energy coach.

Claim boundary: deterministic emulator only; asserts no acoustic validity.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import circle_of_fifths as cof

# Below this consonance the interval is treated as wrong-key / wolf and not coupled.
# consonance 1/3 corresponds to a circle-of-fifths distance of 4 (outside the
# diatonic neighborhood); the tritone (distance 6) sits at consonance 0.
DEFAULT_WOLF_THRESHOLD = 1.0 / 3.0 + 1e-9


def _consonance_by_pc(key: int) -> np.ndarray:
    """12-vector: consonance of each pitch class against ``key``."""
    return np.array([cof.consonance(pc, key) for pc in range(cof.N_PITCH_CLASSES)], dtype=float)


def alignment_to_key(pitch_classes: np.ndarray, key: int) -> np.ndarray:
    """Per-node consonance to the key basin, in [0, 1]."""
    pcs = np.asarray(pitch_classes, dtype=int) % cof.N_PITCH_CLASSES
    return _consonance_by_pc(key)[pcs]


def detect_wolves(pitch_classes: np.ndarray, key: int, wolf_threshold: float = DEFAULT_WOLF_THRESHOLD) -> np.ndarray:
    """Boolean per-node mask of wolf / wrong-key intrusions."""
    return alignment_to_key(pitch_classes, key) < wolf_threshold


def coupling_mask(pitch_classes: np.ndarray, key: int, wolf_threshold: float = DEFAULT_WOLF_THRESHOLD) -> np.ndarray:
    """Per-node coupling confidence in [0, 1]; wolves are hard-zeroed (no coupling)."""
    align = alignment_to_key(pitch_classes, key)
    return np.where(align >= wolf_threshold, align, 0.0)


def phase_order(pitch_classes: np.ndarray, weights: np.ndarray | None = None) -> float:
    """Kuramoto-style coherence R in [0, 1] over pitch-class phases.

    R = |sum_i w_i e^{i 2pi pc_i / 12}| / sum_i w_i. R -> 1 when the ensemble is
    phase-coherent (a settled, measurable resonance); R -> 0 when scattered.
    """
    pcs = np.asarray(pitch_classes, dtype=float)
    theta = 2.0 * np.pi * pcs / cof.N_PITCH_CLASSES
    if weights is None:
        w = np.ones_like(theta)
    else:
        w = np.asarray(weights, dtype=float)
    denom = float(np.sum(w))
    if denom <= 0.0:
        return 0.0
    z = np.sum(w * np.exp(1j * theta)) / denom
    return float(np.abs(z))


def directional_balance(pitch_classes: np.ndarray, key: int) -> float:
    """Mean signed semitone deviation from the key in [-6, 6].

    > 0 means the ensemble sits sharp of the key (coach nudges downward);
    < 0 means flat (coach nudges upward). Uses the shortest signed direction.
    """
    pcs = np.asarray(pitch_classes, dtype=int) % cof.N_PITCH_CLASSES
    raw = (pcs - (key % cof.N_PITCH_CLASSES)) % cof.N_PITCH_CLASSES
    signed = np.where(raw > cof.N_PITCH_CLASSES // 2, raw - cof.N_PITCH_CLASSES, raw)
    return float(np.mean(signed)) if signed.size else 0.0


@dataclass(frozen=True)
class ClosureReport:
    key: int
    mean_alignment: float
    coupling_mask: np.ndarray
    wolf_mask: np.ndarray
    wolf_fraction: float
    phase_order: float
    balance: float

    def has_wolf(self) -> bool:
        return bool(np.any(self.wolf_mask))


def close(
    pitch_classes: np.ndarray,
    key: int,
    weights: np.ndarray | None = None,
    wolf_threshold: float = DEFAULT_WOLF_THRESHOLD,
) -> ClosureReport:
    """Full phase-closure report for an ensemble against a target key basin."""
    align = alignment_to_key(pitch_classes, key)
    mask = np.where(align >= wolf_threshold, align, 0.0)
    wolves = align < wolf_threshold
    return ClosureReport(
        key=int(key) % cof.N_PITCH_CLASSES,
        mean_alignment=float(np.mean(align)) if align.size else 0.0,
        coupling_mask=mask,
        wolf_mask=wolves,
        wolf_fraction=float(np.mean(wolves)) if wolves.size else 0.0,
        phase_order=phase_order(pitch_classes, weights=align if weights is None else weights),
        balance=directional_balance(pitch_classes, key),
    )
