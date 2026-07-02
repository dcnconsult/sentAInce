"""Analog ingestion: continuous acoustic cents <-> the C-TAWE phi^6 domain.

Maps real continuous pitch deviations (cents) into the topological domain of the
continuous phi^6 solver and runs the O(N) LUT phase-exchange. The phi^6 triple-well
acts as the thermodynamic-exchange *emulator* for acoustic alignment:

    0 cents            -> |u| = 1            perfect phase closure (the +-1 dimple)
    +-window cents     -> |u| = sqrt(2/3)    the separatrix / edge of the coupling window
    |cents| > window   -> |u| < sqrt(2/3)    the 0-well basin: release / abstain

``sign(u)`` carries the sharp(+) / flat(-) polarity. Compatible oscillators (within
the window) feel the LUT pull, coast over the separatrix, and slide into closure;
incompatible ones (wolf / extreme detune) are starved of field energy (coupling
mask -> 0), decelerate under friction, and slide into the 0-well -- the Wolf Guard,
with no binary branch.

Claim boundary: deterministic emulator only. No acoustic, clinical, psychoacoustic,
thermodynamic, quantum, or universal-subsystem claim. ``cents`` is an abstract
deviation coordinate; this is not a tuning or vocal-coaching tool.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core_physics import KineticGovernorConfig, phi6_kinetic_settle_v041
from core_physics.phi6_solver import SEPARATRIX

OCTAVE_CENTS = 1200.0
SEMITONE_CENTS = 100.0
DEFAULT_WINDOW_CENTS = 25.0


def _decay_k(window: float) -> float:
    """Decay rate so that |u| = SEPARATRIX exactly at |cents| = window."""
    if window <= 0.0:
        raise ValueError("window must be positive")
    return -math.log(SEPARATRIX) / window


def cents_to_ctawe(cents, window: float = DEFAULT_WINDOW_CENTS) -> np.ndarray:
    """Map a (signed) cents deviation to a phi^6 coordinate u in [-1, 1].

    Injective, not a bijection onto [-1, 1]: the true domain is (deviation
    magnitude, polarity). With the convention ``sign(0) = +`` (zero cents has no
    intrinsic sharp/flat side -> the +1 dimple), the image is (-1, 0) u (0, 1]
    and the map is discontinuous at 0. ``ctawe_to_cents`` inverts it on that image.
    """
    c = np.asarray(cents, dtype=float)
    mag = np.exp(-_decay_k(window) * np.abs(c))
    sign = np.where(c >= 0.0, 1.0, -1.0)
    return sign * mag


def ctawe_to_cents(u, window: float = DEFAULT_WINDOW_CENTS) -> np.ndarray:
    """Inverse of :func:`cents_to_ctawe`. |u|->0 maps to a large (released) deviation."""
    u = np.asarray(u, dtype=float)
    mag = np.clip(np.abs(u), 1e-12, 1.0)
    cents_mag = -np.log(mag) / _decay_k(window)
    sign = np.where(u >= 0.0, 1.0, -1.0)
    return sign * cents_mag


def is_released(u) -> np.ndarray:
    """True where a state sits in the 0-well basin (|u| < separatrix): abstain."""
    return np.abs(np.asarray(u, dtype=float)) < SEPARATRIX


def cents_from_frequency(freq_hz, target_hz) -> np.ndarray:
    """Cents deviation of a frequency from a target: 1200*log2(f/target)."""
    return OCTAVE_CENTS * np.log2(np.asarray(freq_hz, dtype=float) / np.asarray(target_hz, dtype=float))


@dataclass
class PhaseExchangeResult:
    initial_cents: np.ndarray   # (N,) signed cents in
    final_cents: np.ndarray     # (N,) signed cents out (large magnitude where released)
    decoded: np.ndarray         # (N,) ternary {-1, 0, +1}: +-1 = closed polarity, 0 = abstain
    closed: np.ndarray          # (N,) bool: achieved phase closure
    released: np.ndarray        # (N,) bool: abstained into the 0-well
    steps: int                  # macro steps to settle
    final_velocity: float       # residual max|v| (-> 0 == kinetic energy dissipated)

    def as_dict(self) -> dict:
        return {
            "initial_cents": self.initial_cents.tolist(),
            "final_cents": self.final_cents.tolist(),
            "decoded": self.decoded.tolist(),
            "closed": self.closed.tolist(),
            "released": self.released.tolist(),
            "steps": self.steps,
            "final_velocity": self.final_velocity,
        }


def phase_exchange(
    initial_cents,
    window: float = DEFAULT_WINDOW_CENTS,
    gain: float = 1.0,
    config: KineticGovernorConfig | None = None,
) -> PhaseExchangeResult:
    """Drop a cloud of detuned oscillators into the phi^6 LUT lane and let it settle.

    ``initial_cents`` is one oscillator per node. Compatible oscillators
    (``|cents| <= window``) are pulled into the +-1 closure dimple; incompatible
    ones are masked off (no coupling) and coast to the 0-well (abstain). Runs the
    O(N) LUT lane -- no Hebbian weight matrix.
    """
    cfg = config or KineticGovernorConfig()
    c = np.asarray(initial_cents, dtype=float).reshape(-1)
    u0 = cents_to_ctawe(c, window)
    polarity = np.where(c >= 0.0, 1.0, -1.0)            # nearest active well
    lut = polarity * gain                               # resonant pull toward closure
    mask = (np.abs(c) <= window).astype(float)          # compatibility gate (wolf -> 0)

    settle = phi6_kinetic_settle_v041(
        u0[None, :], lut_field=lut[None, :], mask=mask[None, :], cfg=cfg, dtype=np.float64
    )
    u_final = np.asarray(settle.u_cont)[0]
    decoded = np.asarray(settle.state)[0]
    closed = decoded != 0.0
    released = decoded == 0.0
    released_cents = np.where(u_final >= 0.0, 1.0, -1.0) * np.inf  # released -> +-inf deviation
    final_cents = np.where(released, released_cents, ctawe_to_cents(u_final, window))
    return PhaseExchangeResult(
        initial_cents=c,
        final_cents=final_cents,
        decoded=decoded,
        closed=closed,
        released=released,
        steps=int(np.asarray(settle.steps).reshape(-1).max()),
        final_velocity=float(np.asarray(settle.final_delta).reshape(-1).max()),
    )


def detuned_triad_cents(
    detune_cents,
    ratios: tuple[float, ...] = (1.0, 5.0 / 4.0, 3.0 / 2.0, 2.0),
    base_hz: float = 261.63,
) -> np.ndarray:
    """Build a just-intonation major-triad-plus-octave quartet, detune each voice by
    ``detune_cents``, and return each voice's cents deviation from its target.

    Exercises the frequency<->cents path end to end (with the basin centers as the
    0-cent references the result equals ``detune_cents``). Convenience for the demo.
    """
    ratios_a = np.asarray(ratios, dtype=float)
    detune = np.asarray(detune_cents, dtype=float)
    targets = base_hz * ratios_a
    actual = targets * 2.0 ** (detune / OCTAVE_CENTS)
    return cents_from_frequency(actual, targets)
