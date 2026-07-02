"""core_physics — the shared C-TAWE phi^6 kinetic governor engine.

The Lane-0 mathematical tool at the root of the SyncQutrit architecture: a
batched continuous-ternary ODE settle with heavy-ball momentum, a branchless
confidence gate, and decoded-state hysteresis. Both outer projects
(``harmonic_basin``, ``freqos``) apply their own topology to this engine.

Claim boundary: deterministic emulator and implementation ledger only. No native
ternary hardware, strict cyclic Z3 Hamiltonian, quantum, thermodynamic,
clinical, or universal-subsystem claim.
"""
from __future__ import annotations

from .backend import NUMPY, Backend, NumpyBackend, TorchBackend, get_backend
from .fused import eager_torch_step, make_fused_step
from .kinetic_governor import KineticGovernorConfig, phi6_kinetic_governor_relax
from .phi6_solver import (
    ACTIVE_DIMPLE_DEPTH,
    ACTIVE_WELL_ENERGY,
    RESTORING_CLIP,
    SEPARATRIX,
    SEPARATRIX_ENERGY,
    ZERO_TO_ACTIVE_BARRIER,
    DimpleLedger,
    SettleState,
    alignment_confidence,
    ctawe_polynomial,
    dimple_ledger,
    phi6_grad,
    phi6_kinetic_settle,
    phi6_kinetic_settle_v041,
    phi6_potential,
    phi6_second_derivative,
)
from .ternary_memory import (
    RelaxationResult,
    active_overlap,
    basin_match_rate,
    corrupt_ternary_pattern,
    generate_ternary_patterns,
    hard_ternary_slicer,
    hebbian_weights,
    one_pass_snap,
    phi6_basin_slicer,
    snap_relax,
    snap_threshold_sweep_best,
)

__version__ = "1.0.1"

__all__ = [
    # backend
    "Backend",
    "NumpyBackend",
    "TorchBackend",
    "NUMPY",
    "get_backend",
    "make_fused_step",
    "eager_torch_step",
    # phi6 lane-0 + kernel
    "SEPARATRIX",
    "ACTIVE_DIMPLE_DEPTH",
    "ACTIVE_WELL_ENERGY",
    "SEPARATRIX_ENERGY",
    "ZERO_TO_ACTIVE_BARRIER",
    "RESTORING_CLIP",
    "ctawe_polynomial",
    "phi6_grad",
    "phi6_potential",
    "phi6_second_derivative",
    "alignment_confidence",
    "dimple_ledger",
    "DimpleLedger",
    "phi6_kinetic_settle",
    "phi6_kinetic_settle_v041",
    "SettleState",
    # governor
    "KineticGovernorConfig",
    "phi6_kinetic_governor_relax",
    # ternary memory primitives + baselines
    "RelaxationResult",
    "generate_ternary_patterns",
    "hebbian_weights",
    "corrupt_ternary_pattern",
    "hard_ternary_slicer",
    "phi6_basin_slicer",
    "active_overlap",
    "basin_match_rate",
    "one_pass_snap",
    "snap_relax",
    "snap_threshold_sweep_best",
]
