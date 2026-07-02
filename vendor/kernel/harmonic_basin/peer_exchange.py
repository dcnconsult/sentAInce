"""v0.44 peer energy exchange: weak peer-to-peer coupling alongside the LUT pull.

Composite driving field, fed to the shared ``core_physics._kinetic_step`` (unchanged):

    raw_field(t) = k_lut * (r(t) - U)  +  k_peer * sum_j W_ij * a_j * (U_j - U_i)

The LUT term keeps each voice tracking its known circle-of-fifths basin (the dominant
global topology). The *weak* peer term is an **activity-gated graph-Laplacian** (a
deliberate refinement of the memo's raw ``k_peer * W_peer @ U``, which has no consensus
equilibrium -- it over-drives locked voices into the clip and never severs). The
diffusive form ``a_j*(U_j - U_i)`` pulls voices toward each other (zero at consensus,
no over-drive), and the genuinely smooth (C1) activity weight
``a_j = smoothstep(clip((|U_j|-separatrix)/(1-separatrix), 0, 1))`` -- Hermite
``3t^2 - 2t^3`` with zero derivative at both joins -- makes a released voice (one that
has fallen below the separatrix into the abstain well) stop coupling, with no
derivative shock, so the bond severs naturally.
A stable voice donates energy to hold a struggling neighbour in closure
past its isolated tear-out (sympathetic load-sharing); when the neighbour finally
tears out, its peer field collapses and the stable voice relaxes back to true
alignment (the Wolf Guard severing the bond). Multi-body phase exchange via branchless
phi^6 continuum math -- no engine change.

Claim boundary: deterministic emulator only. "entanglement", "thermodynamic exchange",
"sympathetic resonance" are evocative descriptions of coupled-oscillator dynamics in
this emulator -- not physical entanglement, a thermodynamic law, or an acoustic claim.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core_physics import NUMPY, KineticGovernorConfig
from core_physics.phi6_solver import SEPARATRIX, _kinetic_step

from .analog_ingest import DEFAULT_WINDOW_CENTS, cents_to_ctawe, ctawe_to_cents
from .dynamic_tracking import _pll_config


def sympathetic_coupling(n: int) -> np.ndarray:
    """All-to-all unit peer coupling with zero self-interaction (W_peer)."""
    return np.ones((n, n)) - np.eye(n)


@dataclass
class EnsembleTrace:
    time_step: np.ndarray       # (T,)
    intrinsic_cents: np.ndarray  # (T, N) per-voice driving glissando
    u: np.ndarray               # (T, N) continuous phi^6 state
    coupled_cents: np.ndarray   # (T, N) per-voice output deviation
    kinetic_energy: np.ndarray  # (T, N) 0.5 * V^2
    decoded: np.ndarray         # (T, N) {-1, 0, +1}


def track_ensemble(
    intrinsic_cents,
    u0,
    k_lut: float = 0.6,
    k_peer: float = 0.15,
    w_peer: np.ndarray | None = None,
    window: float = DEFAULT_WINDOW_CENTS,
    config: KineticGovernorConfig | None = None,
    be=NUMPY,
) -> EnsembleTrace:
    """Drive an N-voice ensemble with per-voice intrinsic glissandi + peer coupling."""
    cfg = _pll_config(config)
    c = np.atleast_2d(np.asarray(intrinsic_cents, dtype=float))  # (T, N)
    t_n, n = c.shape
    U = np.asarray(u0, dtype=float).reshape(n).copy()
    V = np.zeros(n)
    w = sympathetic_coupling(n) if w_peer is None else np.asarray(w_peer, dtype=float)

    u_hist = np.empty((t_n, n))
    ke = np.empty((t_n, n))
    cents = np.empty((t_n, n))
    for t in range(t_n):
        r = cents_to_ctawe(c[t], window)
        s = np.clip((np.abs(U) - SEPARATRIX) / (1.0 - SEPARATRIX), 0.0, 1.0)
        a = s * s * (3.0 - 2.0 * s)                          # Hermite smoothstep: C1, 0-deriv at joins
        wa = w * a                                           # W_ij * a_j
        peer = k_peer * (wa @ U - (wa @ np.ones(n)) * U)     # k_peer * sum_j W_ij a_j (U_j - U_i)
        raw_field = k_lut * (r - U) + peer
        U, V = _kinetic_step(U, V, raw_field, None, cfg, be)
        u_hist[t] = U
        ke[t] = 0.5 * V * V
        cents[t] = ctawe_to_cents(U, window)

    decoded = np.where(u_hist > SEPARATRIX, 1.0, np.where(u_hist < -SEPARATRIX, -1.0, 0.0))
    return EnsembleTrace(np.arange(t_n), c, u_hist, cents, ke, decoded)


@dataclass
class DuetResult:
    trace: EnsembleTrace
    voice_a_max_bend_cents: float          # how sharp the stable voice bent (sympathetic)
    voice_b_tear_out_cents: float          # B intrinsic where it snapped, WITH peer help
    voice_b_tear_out_isolated_cents: float  # B tear-out with k_peer = 0
    load_sharing_gain_cents: float         # with-peer minus isolated (>0 == load pooled)
    voice_a_returns_to_zero: bool          # A relaxed back to ~0c after B snapped
    voice_a_final_cents: float


def duet_load_sharing(
    span_cents: float = 50.0,
    steps: int = 1000,
    k_lut: float = 0.6,
    k_peer: float = 0.3,
    window: float = DEFAULT_WINDOW_CENTS,
    config: KineticGovernorConfig | None = None,
) -> DuetResult:
    """Voice A held at 0c, Voice B dragged outward: measure sympathetic load-sharing.

    A donates energy to hold B in closure past B's isolated tear-out; when B finally
    snaps to the 0-well its peer field collapses and A relaxes back to 0c.
    """
    c_b = np.linspace(0.0, span_cents, steps)
    c_a = np.zeros(steps)
    intrinsic = np.stack([c_a, c_b], axis=1)  # (T, 2): voice A = col 0, voice B = col 1

    tr = track_ensemble(intrinsic, u0=[1.0, 1.0], k_lut=k_lut, k_peer=k_peer, window=window, config=config)
    tr0 = track_ensemble(intrinsic, u0=[1.0, 1.0], k_lut=k_lut, k_peer=0.0, window=window, config=config)

    a_locked = tr.decoded[:, 0] == 1.0
    a_bend = float(np.max(np.abs(tr.coupled_cents[a_locked, 0]))) if a_locked.any() else float("nan")

    def _tear(trace):
        broke = np.where(trace.decoded[:, 1] != 1.0)[0]
        return float(trace.intrinsic_cents[broke[0], 1]) if broke.size else float("inf")

    b_tear = _tear(tr)
    b_tear0 = _tear(tr0)
    a_final = float(tr.coupled_cents[-1, 0])
    a_returns = bool(tr.decoded[-1, 0] == 1.0 and abs(a_final) < 1.0)

    return DuetResult(
        trace=tr,
        voice_a_max_bend_cents=a_bend,
        voice_b_tear_out_cents=b_tear,
        voice_b_tear_out_isolated_cents=b_tear0,
        load_sharing_gain_cents=b_tear - b_tear0,
        voice_a_returns_to_zero=a_returns,
        voice_a_final_cents=a_final,
    )
