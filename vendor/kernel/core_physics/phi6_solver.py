"""Lane-0 phi^6 calculus for C-TAWE + the v0.40 batched kinetic settle kernel.

The Lane-0 functions are mathematical facts about the C-TAWE quintic and its
biased scalar phi^6 potential. They are written as pure arithmetic (no forced
dtype) so they evaluate identically on Python floats (the exact dimple ledger),
NumPy arrays (FP32 or FP64), and torch tensors.

``phi6_kinetic_settle`` is the v0.40 generalization of the v0.39 single-cue
``phi6_kinetic_governor_relax`` inner loop to a ``(B, N)`` batch. Rows are
independent (each row's field depends only on its own state and the shared
weight matrix), so the batch is processed by one BLAS GEMM per step and a
converged row is *frozen* (no further write-back) — which reproduces the
single-cue early-out exactly, per row.

Claim boundary: this module intentionally claims no native cyclic Z3 physics,
quantum behavior, or thermodynamic validation. It is a deterministic emulator.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from .backend import NUMPY, Backend

SEPARATRIX = math.sqrt(2.0 / 3.0)
ACTIVE_DIMPLE_DEPTH = 1.0 / 216.0
ZERO_TO_ACTIVE_BARRIER = 28.0 / 216.0
ACTIVE_WELL_ENERGY = 27.0 / 216.0
SEPARATRIX_ENERGY = 28.0 / 216.0

# Polynomial restoring-force clip: keeps the phi^6 gradient in its well region.
# Distinct, on purpose, from the integrated-state clip (KineticGovernorConfig.clip_state).
RESTORING_CLIP = 1.15


def ctawe_polynomial(u):
    """P(u) = 2.5u^3 - 1.5u^5, factored for FMA-friendly evaluation. dtype-preserving."""
    u2 = u * u
    return (u * u2) * (2.5 - 1.5 * u2)


def phi6_grad(u):
    """Gradient V'(u) = u - P(u). dtype-preserving (FP32/FP64/torch/scalar)."""
    return u - ctawe_polynomial(u)


def phi6_potential(u):
    """V(u) = 1/2 u^2 - 5/8 u^4 + 1/4 u^6. dtype-preserving."""
    u2 = u * u
    u4 = u2 * u2
    u6 = u4 * u2
    return 0.5 * u2 - 0.625 * u4 + 0.25 * u6


def phi6_second_derivative(u):
    """V''(u) = 1 - 7.5u^2 + 7.5u^4. dtype-preserving."""
    u2 = u * u
    return 1.0 - 7.5 * u2 + 7.5 * u2 * u2


def alignment_confidence(raw_field, low: float, high: float, be: Backend = NUMPY):
    """Smooth branchless confidence gate based on field margin -> [0, 1].

    A TAM proxy for the outer-loop hazard/consensus gate. In the harmonic
    protocol this slot is where fifths alignment, wolf/wrong-key refusal, and
    rank/phinary witnesses feed a confidence multiplier in [0, 1]. It asserts no
    acoustic validity. ``kinetic_governor`` re-exports this as the public gate.
    """
    if high <= low:
        f = be.asarray(raw_field, be.dtype_of(raw_field, be.float64))
        return f * 0.0 + 1.0
    return be.clip((be.abs(raw_field) - low) / (high - low), 0.0, 1.0)


@dataclass(frozen=True)
class DimpleLedger:
    potential_zero: float
    potential_active: float
    potential_separatrix: float
    zero_to_active_barrier: float
    active_to_zero_barrier: float
    separatrix: float
    active_states_are_stationary_local_minima: bool
    scalar_potential_classification: str

    def as_dict(self) -> dict:
        return asdict(self)


def dimple_ledger() -> DimpleLedger:
    """Return the exact dimple/barrier ledger used by the audit (FP64, exact)."""
    v0 = float(phi6_potential(0.0))
    v1 = float(phi6_potential(1.0))
    vs = float(phi6_potential(SEPARATRIX))
    return DimpleLedger(
        potential_zero=v0,
        potential_active=v1,
        potential_separatrix=vs,
        zero_to_active_barrier=vs - v0,
        active_to_zero_barrier=vs - v1,
        separatrix=SEPARATRIX,
        active_states_are_stationary_local_minima=bool(
            abs(float(phi6_grad(1.0))) < 1e-12
            and abs(float(phi6_grad(-1.0))) < 1e-12
            and float(phi6_second_derivative(1.0)) > 0.0
            and float(phi6_second_derivative(-1.0)) > 0.0
        ),
        scalar_potential_classification=(
            "biased scalar phi^6 tri-stable ternary potential, not strict cyclic Z3 Hamiltonian"
        ),
    )


def _kinetic_step(U, V, raw_field, mask, cfg, be: Backend = NUMPY):
    """One heavy-ball phi^6 update: (U, V, raw_field) -> (U_next, V_next).

    The validated v0.39 inner physics: branchless confidence gate on the raw
    field, optional external coupling ``mask``, phi^6 restoring force under the
    +-1.15 polynomial clip, heavy-ball momentum, and the +-clip_state integrated
    clip. Shared by the v0.40 reference loop and the v0.41 compacting/dual-mode
    loop; this is exactly the body a torch.compile fusion targets.
    """
    lo, hi = cfg.confidence_low, cfg.confidence_high
    if hi > lo:
        conf = be.clip((be.abs(raw_field) - lo) / (hi - lo), 0.0, 1.0)
        gated = raw_field * conf
    else:
        gated = raw_field
    if mask is not None:
        gated = gated * mask
    Uc = be.clip(U, -RESTORING_CLIP, RESTORING_CLIP)
    force = gated - cfg.gamma * phi6_grad(Uc)
    Vn = cfg.momentum * V + cfg.dt * force
    Un = be.clip(U + Vn, -cfg.clip_state, cfg.clip_state)
    return Un, Vn


@dataclass
class SettleState:
    """Raw per-row output of the batched kernel (arrays live on the chosen backend)."""

    state: Any        # decoded ternary state, shape (B, N)
    u_cont: Any       # final continuous state, shape (B, N)
    steps: Any        # per-row convergence step (int), shape (B,)
    final_delta: Any  # per-row final max|v|, shape (B,)


def phi6_kinetic_settle(weights, cue, cfg, mask=None, be: Backend = NUMPY, dtype=None) -> SettleState:
    """Batched heavy-ball phi^6 settle. ``cue`` is (B, N); ``weights`` is (N, N).

    Mirrors v0.39 ``phi6_kinetic_governor_relax`` per row: heavy-ball momentum,
    branchless confidence gate, optional external ``mask`` (the wolf/wrong-key or
    TAM coupling gate), decoded-state hysteresis, and a hard max-step cap. The
    two distinct clips of v0.39 are preserved: the polynomial restoring force
    sees ``clip(U, +-1.15)`` while the integrated state is clipped to
    ``+-cfg.clip_state``. Default dtype is FP32.
    """
    fdt = dtype if dtype is not None else be.dtype_of(cue, be.float32)
    U = be.copy(be.asarray(cue, fdt))
    Wt = be.transpose2d(be.asarray(weights, fdt))
    B = U.shape[0]
    V = be.zeros_like(U)
    m = be.asarray(mask, fdt) if mask is not None else None

    running = be.ones_bool(B)
    steps = be.full_int(B, cfg.max_steps)
    final_delta = be.zeros_row(B, fdt)
    stable = be.zeros_row(B, fdt)
    prev_decoded = None

    vtol, ticks = cfg.velocity_tol, cfg.stable_ticks

    for step in range(1, cfg.max_steps + 1):
        field = be.matmul(U, Wt)                       # (B, N) batched SGEMM
        Un, Vn = _kinetic_step(U, V, field, m, cfg, be)

        run_col = be.col(running)                      # freeze converged rows
        V = be.where(run_col, Vn, V)
        U = be.where(run_col, Un, U)

        delta = be.max_rows(be.abs(V))                 # (B,)
        final_delta = be.where(running, delta, final_delta)

        decoded = be.ternary_slice(U, SEPARATRIX)
        if prev_decoded is None:
            prev_decoded = be.copy(decoded)            # v0.39: no increment on the first step
        else:
            eq = be.rows_all_equal(decoded, prev_decoded)
            stable = be.where(eq, stable + 1.0, be.zeros_row(B, fdt))
            prev_decoded = be.where(be.col(eq), prev_decoded, decoded)

        converged = running & (step > 5) & ((delta < vtol) | (stable >= ticks))
        steps = be.where_int(converged, step, steps)
        running = running & (~converged)
        if not be.any(running):
            break

    state = be.ternary_slice(U, SEPARATRIX)
    return SettleState(state=state, u_cont=U, steps=steps, final_delta=final_delta)


def phi6_kinetic_settle_v041(
    cue,
    weights=None,
    lut_field=None,
    cfg=None,
    mask=None,
    be: Backend = NUMPY,
    dtype=None,
    step_fn=None,
) -> SettleState:
    """v0.41 unified settle: dual-mode field + row-compaction.

    Exactly one field mode:

    * **dense** -- ``weights`` (N, N): field = ``U @ W.T`` recomputed each step
      (O(N^2) crosstalk; the freqOS TAM lane, dynamic learned basins).
    * **lut** -- ``lut_field`` (B, N) or (N,): a precomputed resonant pull toward
      the *known* basin target; no matmul (O(N); the harmonic_basin lane, whose
      circle-of-fifths basins are static geometric invariants).

    Row-compaction: a row is dropped from the active set the step it converges
    (same v0.39 early-out: ``it>5`` and ``|v|<velocity_tol`` or decoded-state
    stable for ``stable_ticks``), so the dense GEMM shrinks and trailing-edge
    compute is eliminated. This reproduces the v0.40 freeze semantics exactly,
    per row. ``step_fn`` overrides the per-step physics (default ``_kinetic_step``;
    pass a torch.compile-fused step for the GPU path). Default dtype is FP32.
    """
    if (weights is None) == (lut_field is None):
        raise ValueError("provide exactly one of weights (dense) or lut_field (LUT)")
    if cfg is None:
        from .kinetic_governor import KineticGovernorConfig  # local import breaks the cycle

        cfg = KineticGovernorConfig()
    step = step_fn or _kinetic_step

    fdt = dtype if dtype is not None else be.dtype_of(cue, be.float32)
    U = be.copy(be.asarray(cue, fdt))
    B = U.shape[0]
    V = be.zeros_like(U)
    m_full = be.asarray(mask, fdt) if mask is not None else None

    dense = weights is not None
    Wt = be.transpose2d(be.asarray(weights, fdt)) if dense else None
    # Materialize (B, N) so a (N,) pull broadcasts across the batch.
    lut_full = None if dense else (be.zeros_like(U) + be.asarray(lut_field, fdt))

    steps = be.full_int(B, cfg.max_steps)
    final_delta = be.zeros_row(B, fdt)
    stable = be.zeros_row(B, fdt)
    prev_decoded = None
    active = be.arange_int(B)
    vtol, ticks = cfg.velocity_tol, cfg.stable_ticks

    for it in range(1, cfg.max_steps + 1):
        if active.shape[0] == 0:
            break
        idx = active
        U_a = be.gather(U, idx)
        V_a = be.gather(V, idx)
        field_a = be.matmul(U_a, Wt) if dense else be.gather(lut_full, idx)
        mask_a = be.gather(m_full, idx) if m_full is not None else None

        Un_a, Vn_a = step(U_a, V_a, field_a, mask_a, cfg, be)
        U = be.scatter_(U, idx, Un_a)
        V = be.scatter_(V, idx, Vn_a)

        delta_a = be.max_rows(be.abs(Vn_a))
        final_delta = be.scatter_(final_delta, idx, delta_a)

        decoded_a = be.ternary_slice(Un_a, SEPARATRIX)
        if prev_decoded is None:
            prev_decoded = be.ternary_slice(U, SEPARATRIX)
            stable_a = be.zeros_row(idx.shape[0], fdt)
        else:
            prev_a = be.gather(prev_decoded, idx)
            eq_a = be.rows_all_equal(decoded_a, prev_a)
            stable_a = be.where(eq_a, be.gather(stable, idx) + 1.0, be.zeros_row(idx.shape[0], fdt))
            prev_decoded = be.scatter_(prev_decoded, idx, be.where(be.col(eq_a), prev_a, decoded_a))
        stable = be.scatter_(stable, idx, stable_a)

        conv_a = (it > 5) & ((delta_a < vtol) | (stable_a >= ticks))
        steps = be.scatter_(steps, be.mask_select(idx, conv_a), it)
        active = be.mask_select(active, ~conv_a)

    state = be.ternary_slice(U, SEPARATRIX)
    return SettleState(state=state, u_cont=U, steps=steps, final_delta=final_delta)
