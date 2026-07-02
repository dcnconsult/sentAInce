"""Optional torch.compile-fused kinetic step for the v0.41 GPU path.

The per-step physics expressed in pure torch ops and wrapped in ``torch.compile``
so TorchDynamo/Inductor fuses the C-TAWE quintic, the heavy-ball momentum update,
and the kinematic step into a single kernel (PTX on CUDA), erasing Python-loop
overhead and intermediate allocations for the polynomial powers.

Environment reality (honest ledger): this machine has **no CUDA/MPS**, and the CPU
Inductor backend needs a C++ compiler (``cl.exe``) that is **not installed**, so
``torch.compile`` cannot actually fuse here. ``make_fused_step`` therefore probes
the compile, and on any failure **falls back to the eager torch step**, recording
which path is active in ``.compiled``. The fused path is numerically
eager-equivalent; the fusion/GPU speedup is architected but **unverified in this
environment**.

torch is imported lazily so it stays an optional dependency.
"""
from __future__ import annotations

from .phi6_solver import RESTORING_CLIP

__all__ = ["make_fused_step", "eager_torch_step"]


def eager_torch_step(U, V, raw_field, mask, lo, hi, gamma, momentum, dt, clip_state, restoring_clip):
    """Pure-torch one-step C-TAWE phi^6 heavy-ball update (the fusion target)."""
    import torch

    if hi > lo:
        conf = torch.clamp((raw_field.abs() - lo) / (hi - lo), 0.0, 1.0)
        gated = raw_field * conf
    else:
        gated = raw_field
    gated = gated * mask
    u_c = torch.clamp(U, -restoring_clip, restoring_clip)
    u2 = u_c * u_c
    grad = u_c - (u_c * u2) * (2.5 - 1.5 * u2)
    force = gated - gamma * grad
    v_next = momentum * V + dt * force
    u_next = torch.clamp(U + v_next, -clip_state, clip_state)
    return u_next, v_next


_CACHE: dict = {}


def make_fused_step(cfg, mode: str = "reduce-overhead", dynamic: bool = True):
    """Return a ``step_fn`` compatible with ``phi6_kinetic_settle_v041``.

    Tries ``torch.compile(eager_torch_step, mode=mode, dynamic=dynamic)`` and probes
    it once; on any failure falls back to eager. The returned callable carries a
    ``.compiled`` bool flag. ``dynamic=True`` lets one compiled kernel serve the
    varying batch sizes produced by row-compaction.
    """
    import torch

    key = (mode, dynamic)
    cached = _CACHE.get(key)
    if cached is None:
        impl = eager_torch_step
        compiled = False
        try:
            candidate = torch.compile(eager_torch_step, mode=mode, dynamic=dynamic)
            probe = torch.zeros(2, 3, dtype=torch.float32)
            candidate(
                probe, probe, probe, torch.ones_like(probe),
                cfg.confidence_low, cfg.confidence_high, cfg.gamma,
                cfg.momentum, cfg.dt, cfg.clip_state, RESTORING_CLIP,
            )
            impl, compiled = candidate, True
        except Exception:
            impl, compiled = eager_torch_step, False
        _CACHE[key] = (impl, compiled)
    impl, compiled = _CACHE[key]

    def step(U, V, raw_field, mask, _cfg, _be):
        m = mask if mask is not None else torch.ones_like(raw_field)
        return impl(
            U, V, raw_field, m,
            cfg.confidence_low, cfg.confidence_high, cfg.gamma,
            cfg.momentum, cfg.dt, cfg.clip_state, RESTORING_CLIP,
        )

    step.compiled = compiled  # type: ignore[attr-defined]
    return step
