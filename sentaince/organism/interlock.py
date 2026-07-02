"""The interlock — the enforcing gate (the v0.86 "topological scar", made real).

Pattern reused from the frozen kernel's topology audit (``effective_adjacency`` in
``circle_of_fifths_rc2/src/freqos/topology_audit.py``): forbid a transition by masking its
edge weight to zero. Here the transition is ``(host-state -> action)``. A lethal action
carries a scar ``sigma <= 0``; the effective adjacency collapses its edge to zero, so the
gate refuses execution **structurally**. The proposer cannot argue past a zero in a NumPy
array.

This lives on a code path separate from the proposer and executor by design: the scar caps
safety regardless of what the generative organelle proposes (see ORGANISM_INTERNALS.md §8 —
the storage-separated scar must stay separate from the dynamics).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .action_graph import Action, Risk

# Scar value per risk class. Lethal edges get sigma <= 0 → zeroed by effective_adjacency.
_SIGMA: dict[Risk, float] = {Risk.BENIGN: 1.0, Risk.LETHAL: -1.0}


@dataclass(frozen=True)
class Verdict:
    permitted: bool
    reason: str
    capacity: float


def effective_adjacency(base_weight: npt.ArrayLike, sigma: npt.ArrayLike) -> np.ndarray:
    """Edge capacity after the scar: ``base * max(sigma, 0)``.

    A non-positive sigma collapses the edge to 0 (the transition is forbidden). Vectorized
    so the gate is a literal NumPy operation, not a cooperative if-statement.
    """
    base = np.asarray(base_weight, dtype=np.float64)
    scar = np.maximum(np.asarray(sigma, dtype=np.float64), 0.0)
    return base * scar


class Interlock:
    """Host-side gate. Permits an action iff its scarred edge capacity is strictly > 0."""

    def __init__(self, base_weight: float = 1.0) -> None:
        self._base = np.float64(base_weight)

    def gate(self, action: Action) -> Verdict:
        sigma = np.float64(_SIGMA[action.risk])
        capacity = float(effective_adjacency(self._base, sigma))
        if capacity > 0.0:
            return Verdict(
                permitted=True,
                reason=f"permitted ({action.risk.value}, capacity={capacity:.3f})",
                capacity=capacity,
            )
        return Verdict(
            permitted=False,
            reason=(
                f"AutonomicInterlock: refused {action.risk.value} edge "
                f"`{action.command}` (capacity={capacity:.3f})"
            ),
            capacity=capacity,
        )
