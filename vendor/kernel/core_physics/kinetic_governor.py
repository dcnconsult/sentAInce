"""v0.39 phi^6 kinetic governor, generalized to batched (B, N) execution (v0.40).

Lane 1: a heavy-ball controller and separatrix/decoded-state early-out wrapped
around the Lane-0 phi^6 restoring force. The validated v0.39 constants, the
branchless confidence gate, the decoded-state hysteresis, and the separatrix
decode are preserved exactly; only the execution was generalized to batches,
FP32, and a NumPy/torch backend (``phi6_solver.phi6_kinetic_settle``).

Claim boundary: deterministic emulator and implementation ledger only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .backend import NUMPY, Backend
from .phi6_solver import SEPARATRIX, alignment_confidence, phi6_kinetic_settle
from .ternary_memory import RelaxationResult, active_overlap, basin_match_rate

__all__ = [
    "KineticGovernorConfig",
    "alignment_confidence",
    "phi6_kinetic_governor_relax",
]

_NOTES = "heavy-ball phi6 with confidence gate, decoded-state hysteresis, and hard max-step cap"


@dataclass(frozen=True)
class KineticGovernorConfig:
    dt: float = 0.03
    gamma: float = 0.8
    momentum: float = 0.85
    max_steps: int = 40
    velocity_tol: float = 1e-3
    stable_ticks: int = 2
    clip_state: float = 1.5
    confidence_low: float = 0.05
    confidence_high: float = 0.20

    def as_dict(self) -> dict:
        return asdict(self)


def phi6_kinetic_governor_relax(
    weights: np.ndarray,
    cue: np.ndarray,
    target: np.ndarray,
    config: KineticGovernorConfig | None = None,
    method: str = "phi6_kinetic_governor",
    mask=None,
    be: Backend = NUMPY,
    dtype=None,
):
    """Settle ``cue`` toward a fixed point under the phi^6 governor.

    A 1-D ``cue`` returns a single :class:`RelaxationResult` (the v0.39 contract,
    used by the audit). A 2-D ``cue`` of shape (B, N) returns a list of
    per-row :class:`RelaxationResult`. ``target`` may be 1-D (shared) or (B, N).
    """
    cfg = config or KineticGovernorConfig()
    cue_arr = np.asarray(cue, dtype=float)
    one_d = cue_arr.ndim == 1
    cue2d = np.atleast_2d(cue_arr)
    b = cue2d.shape[0]

    settled = phi6_kinetic_settle(weights, cue2d, cfg, mask=mask, be=be, dtype=dtype)
    state = be.to_numpy(settled.state)
    u_cont = be.to_numpy(settled.u_cont)
    steps = np.asarray(be.to_numpy(settled.steps)).reshape(-1)
    final_delta = np.asarray(be.to_numpy(settled.final_delta)).reshape(-1)

    target2d = np.atleast_2d(np.asarray(target, dtype=float))
    if target2d.shape[0] == 1 and b > 1:
        target2d = np.repeat(target2d, b, axis=0)

    results = []
    for i in range(b):
        ov = active_overlap(state[i], target2d[i])
        bm = basin_match_rate(state[i], target2d[i])
        results.append(
            RelaxationResult(
                method=method,
                active_overlap=ov,
                basin_match_rate=bm,
                exact_state_match_rate=bm,
                steps=int(steps[i]),
                field_evaluations=int(steps[i]),
                mean_abs_state=float(np.mean(np.abs(u_cont[i]))),
                final_delta=float(final_delta[i]),
                threshold=SEPARATRIX,
                notes=_NOTES,
            )
        )
    return results[0] if one_d else results
