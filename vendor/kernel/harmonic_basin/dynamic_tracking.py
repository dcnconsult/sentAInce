"""v0.43 dynamic phase tracking: the C-TAWE phi^6 governor as an analog PLL.

Transitions the emulator from a *settling* solver (converge to a static point) to a
*driven streaming* solver (evolve through time). A time-varying intrinsic trajectory
(a glissando) drives one oscillator; the shared ``core_physics._kinetic_step`` is
reused **unchanged** -- the state U and momentum V are piped forward t -> t+dt with a
tracking field recomputed each tick:

    raw_field(t) = k_track * (r(t) - U),   r(t) = cents_to_ctawe(intrinsic_cents(t))

The phi^6 wells (+-1 closure, 0 abstain) plus heavy-ball momentum make this a
phase-locked loop with hysteresis: the +-1 dimple drags the output to stay locked as
the intrinsic pitch drifts past the +-window separatrix, until kinetic tension snaps
it loose (tear-out); the 0-well holds a released voice until the drift crosses inward
(capture). ``tear_out > capture`` == dynamic hysteresis == topological memory == a
branchless debounce.

Claim boundary: deterministic emulator only. "PLL" / "hysteresis" are
dynamical-systems descriptions of this emulator, not a physical oscillator, analog
circuit, tuning, or biological claim.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core_physics import NUMPY, KineticGovernorConfig
from core_physics.phi6_solver import SEPARATRIX, _kinetic_step

from .analog_ingest import DEFAULT_WINDOW_CENTS, cents_to_ctawe, ctawe_to_cents


def _pll_config(base: KineticGovernorConfig | None = None) -> KineticGovernorConfig:
    """A governor config with the confidence gate disabled (hi<=lo).

    The branchless confidence gate is for ensemble field-margins; a single-voice PLL
    feeds its tracking field directly. Momentum / friction / clips are kept.
    """
    b = base or KineticGovernorConfig()
    return KineticGovernorConfig(
        dt=b.dt, gamma=b.gamma, momentum=b.momentum, max_steps=b.max_steps,
        velocity_tol=b.velocity_tol, stable_ticks=b.stable_ticks, clip_state=b.clip_state,
        confidence_low=0.0, confidence_high=0.0,
    )


@dataclass
class TrackingTrace:
    time_step: np.ndarray          # (T,)
    intrinsic_cents: np.ndarray    # (T,) the driving glissando
    coupled_cents_out: np.ndarray  # (T,) the locked output deviation
    kinetic_energy: np.ndarray     # (T,) 0.5 * V^2
    u: np.ndarray                  # (T,) continuous phi^6 state
    decoded: np.ndarray            # (T,) {-1, 0, +1}

    def as_rows(self) -> list[tuple]:
        return [
            (int(self.time_step[i]), float(self.intrinsic_cents[i]),
             float(self.coupled_cents_out[i]), float(self.kinetic_energy[i]))
            for i in range(self.time_step.size)
        ]


def track_glissando(
    intrinsic_cents,
    u0: float = 1.0,
    v0: float = 0.0,
    k_track: float = 0.6,
    window: float = DEFAULT_WINDOW_CENTS,
    config: KineticGovernorConfig | None = None,
    be=NUMPY,
) -> TrackingTrace:
    """Drive one oscillator along an intrinsic cents trajectory, one kinetic step per tick."""
    cfg = _pll_config(config)
    c = np.asarray(intrinsic_cents, dtype=float).reshape(-1)
    t_n = c.size
    U = np.array([float(u0)], dtype=float)
    V = np.array([float(v0)], dtype=float)

    out_u = np.empty(t_n)
    out_cents = np.empty(t_n)
    out_ke = np.empty(t_n)
    for t in range(t_n):
        r = float(cents_to_ctawe(c[t], window))
        raw_field = k_track * (r - U)
        U, V = _kinetic_step(U, V, raw_field, None, cfg, be)
        out_u[t] = float(U[0])
        out_ke[t] = 0.5 * float(V[0]) ** 2
        out_cents[t] = float(ctawe_to_cents(np.array([out_u[t]]), window)[0])

    decoded = np.where(out_u > SEPARATRIX, 1.0, np.where(out_u < -SEPARATRIX, -1.0, 0.0))
    return TrackingTrace(np.arange(t_n), c, out_cents, out_ke, out_u, decoded)


def tear_out_threshold(
    k_track: float = 0.6, window: float = DEFAULT_WINDOW_CENTS, steps: int = 600,
    max_cents: float = 60.0, config: KineticGovernorConfig | None = None,
) -> float:
    """Outward drift from locked (0c, u=+1): the intrinsic cents where lock breaks (-> 0-well)."""
    c = np.linspace(0.0, max_cents, steps)
    tr = track_glissando(c, u0=1.0, k_track=k_track, window=window, config=config)
    broke = np.where(tr.decoded != 1.0)[0]
    return float(tr.intrinsic_cents[broke[0]]) if broke.size else float("inf")


def capture_threshold(
    k_track: float = 0.6, window: float = DEFAULT_WINDOW_CENTS, steps: int = 600,
    start_cents: float = 60.0, config: KineticGovernorConfig | None = None,
) -> float:
    """Inward drift from released (start_cents, u=0): the intrinsic cents where lock captures (-> +1)."""
    c = np.linspace(start_cents, 0.0, steps)
    tr = track_glissando(c, u0=0.0, k_track=k_track, window=window, config=config)
    cap = np.where(tr.decoded == 1.0)[0]
    return float(tr.intrinsic_cents[cap[0]]) if cap.size else float("-inf")


@dataclass
class HysteresisResult:
    tear_out_cents: float
    capture_cents: float
    margin_cents: float       # tear_out - capture; > 0 == hysteresis (topological memory)
    has_hysteresis: bool


def measure_hysteresis(
    k_track: float = 0.6, window: float = DEFAULT_WINDOW_CENTS, steps: int = 600,
    span_cents: float = 60.0, config: KineticGovernorConfig | None = None,
) -> HysteresisResult:
    """Measure the dynamic lock-in margin: tear-out (outward) vs capture (inward)."""
    tear = tear_out_threshold(k_track, window, steps, span_cents, config)
    cap = capture_threshold(k_track, window, steps, span_cents, config)
    margin = tear - cap
    return HysteresisResult(tear, cap, margin, bool(margin > 0.0))
