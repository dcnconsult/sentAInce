"""Gentle energy exchange / abstain / wait — the basin-mediated interaction protocol.

Implements the whitepaper's emergent object: listen for key-aligned harmonic
basins, allow gentle energy exchange, and measure only after the ensemble has
settled. The decision loop returns one of ``correct / basin / wait / abstain``
plus a work estimate. "Gentle energy exchange" is realized on the shared engine:
``decide`` runs the core_physics phi^6 kinetic governor with the phase-closure
coupling confidence as the governor ``mask`` — compatible nodes are held by the
1/216 dimple while wolf/wrong-key nodes, denied interaction field, coast down the
separatrix toward the 0-well (abstain).

Claim boundary: deterministic emulator and control policy only. No acoustic,
clinical, thermodynamic, quantum, or universal-subsystem claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from core_physics import (
    SEPARATRIX,
    KineticGovernorConfig,
    RelaxationResult,
    active_overlap,
    basin_match_rate,
    phi6_kinetic_governor_relax,
    phi6_kinetic_settle_v041,
)

from . import circle_of_fifths as cof
from . import phase_closure


class Decision(str, Enum):
    CORRECT = "correct"   # settled into the target basin -> safe to measure
    BASIN = "basin"       # settled into a nearby basin -> report basin, do not force
    WAIT = "wait"         # aligned but not settled -> allow more gentle transfer
    ABSTAIN = "abstain"   # wolf/wrong-key intrusion or no safe basin -> do not couple


# --- Resonant energy-transfer policy catalog (whitepaper section 5.2) -----------
@dataclass(frozen=True)
class ResonantPolicy:
    name: str
    measure_rate: float
    efficiency: float
    work_per_voice: float
    unsafe_wolf: float
    unsafe_key: float

    @property
    def is_safe(self) -> bool:
        return self.unsafe_wolf == 0.0 and self.unsafe_key == 0.0


RESONANT_POLICIES: dict[str, ResonantPolicy] = {
    "force_snap_then_measure": ResonantPolicy("force_snap_then_measure", 1.000, 0.825, 4.338, 0.125, 0.125),
    "wolf_guarded_resonance": ResonantPolicy("wolf_guarded_resonance", 0.750, 0.663, 1.627, 0.0, 0.0),
    "duet_quartet_choir_balance": ResonantPolicy("duet_quartet_choir_balance", 0.750, 0.661, 1.686, 0.0, 0.0),
    "resonant_memory_transfer": ResonantPolicy("resonant_memory_transfer", 0.750, 0.659, 1.816, 0.0, 0.0),
    "continuous_transfer": ResonantPolicy("continuous_transfer", 0.750, 0.659, 2.169, 0.0, 0.0),
    "key_window_transfer": ResonantPolicy("key_window_transfer", 0.576, 0.513, 1.135, 0.0, 0.0),
    "hold_listen": ResonantPolicy("hold_listen", 0.379, 0.355, 0.135, 0.0, 0.0),
}


def recommend_policy(allow_unsafe: bool = False) -> ResonantPolicy:
    """Pick a transfer policy. By default the safest high-measure resonant policy.

    Forced snapping maximizes measure rate but spends more work and forces some
    wolf/wrong-key cases (unsafe > 0); resonant policies give up some measure
    rate to keep coupling safe. Default excludes any unsafe policy.
    """
    candidates = RESONANT_POLICIES.values()
    if not allow_unsafe:
        candidates = [p for p in candidates if p.is_safe]
    return max(candidates, key=lambda p: (p.measure_rate, p.efficiency))


# --- Directional wolf guard (whitepaper section 5.1) ----------------------------
@dataclass(frozen=True)
class CoachResult:
    regime: str
    action: str        # raise | lower | shift_fifth | abstain
    abstain: bool
    unsafe_force: bool


def directional_energy_coach(regime: str) -> CoachResult:
    """The directional_energy_coach policy outcome per regime.

    flat -> raise pitch; sharp -> lower pitch; fifth_neighbor_shift -> shift a
    fifth; wolf_chord -> abstain (the coach refuses; only force_exact would be
    unsafe). Matches the whitepaper 5.1 safety table (wolf abstain, no unsafe
    force under this policy).
    """
    table = {
        "flat": CoachResult("flat", "raise", False, False),
        "sharp": CoachResult("sharp", "lower", False, False),
        "fifth_neighbor_shift": CoachResult("fifth_neighbor_shift", "shift_fifth", False, False),
        "wolf_chord": CoachResult("wolf_chord", "abstain", True, False),
    }
    if regime not in table:
        raise ValueError(f"unknown regime {regime!r}")
    return table[regime]


# --- The decision loop ----------------------------------------------------------
@dataclass(frozen=True)
class ProtocolConfig:
    wolf_abstain_fraction: float = 1.0 / 3.0  # abstain if this fraction or more are wolves
    exact_basin_match: float = 0.95           # decoded basin-match -> CORRECT
    near_basin_overlap: float = 0.60          # active overlap -> BASIN (nearby), else abstain
    settle_velocity: float = 1e-3             # final |v| below this counts as settled
    governor: KineticGovernorConfig = KineticGovernorConfig()


@dataclass(frozen=True)
class ProtocolDecision:
    decision: Decision
    active_overlap: float
    basin_match_rate: float
    settled: bool
    work_estimate: int       # field evaluations spent (the honest cost)
    wolf_fraction: float
    phase_order: float
    relaxation: RelaxationResult | None
    notes: str = ""


def gentle_exchange(
    weights: np.ndarray,
    cue: np.ndarray,
    target: np.ndarray,
    coupling_mask: np.ndarray,
    config: KineticGovernorConfig | None = None,
) -> RelaxationResult:
    """Low-work energy transfer: settle ``cue`` under the phi^6 governor, gated by
    the per-node coupling confidence. Wolf/wrong-key nodes (mask ~ 0) receive no
    interaction field and decay to the 0-well; compatible nodes are gently pulled
    into alignment by the 1/216 dimple."""
    cfg = config or KineticGovernorConfig()
    return phi6_kinetic_governor_relax(weights, cue, target, config=cfg, mask=coupling_mask, method="gentle_exchange")


def _result_from_settle(settle, target: np.ndarray, method: str) -> RelaxationResult:
    """Adapt a single-cue v0.41 SettleState into the protocol's RelaxationResult."""
    state = np.asarray(settle.state)[0]
    u = np.asarray(settle.u_cont)[0]
    steps = int(np.asarray(settle.steps).reshape(-1)[0])
    bm = basin_match_rate(state, target)
    return RelaxationResult(
        method=method,
        active_overlap=active_overlap(state, target),
        basin_match_rate=bm,
        exact_state_match_rate=bm,
        steps=steps,
        field_evaluations=steps,
        mean_abs_state=float(np.mean(np.abs(u))),
        final_delta=float(np.asarray(settle.final_delta).reshape(-1)[0]),
        threshold=SEPARATRIX,
        notes=method,
    )


def gentle_exchange_lut(
    cue: np.ndarray,
    target: np.ndarray,
    coupling_mask: np.ndarray | None = None,
    config: KineticGovernorConfig | None = None,
    gain: float = 1.0,
) -> RelaxationResult:
    """O(N) gentle exchange via LUT mode -- no Hebbian weight matrix, no O(N^2) field.

    The circle-of-fifths basins are static geometric invariants, so instead of
    recalling the basin from a dense ``W @ U`` crosstalk field, the lane looks up
    the known target and lets the phi^6 potential govern the local slide. Drops the
    Harmonic Basin protocol's interaction cost from O(N^2) to O(N) per step.
    """
    cfg = config or KineticGovernorConfig()
    lut = cof.resonant_pull(target, gain)
    mask = None if coupling_mask is None else np.atleast_2d(np.asarray(coupling_mask, dtype=float))
    settle = phi6_kinetic_settle_v041(
        np.atleast_2d(np.asarray(cue, dtype=float)),
        lut_field=np.asarray(lut, dtype=float),
        cfg=cfg,
        mask=mask,
    )
    return _result_from_settle(settle, np.asarray(target, dtype=float), "gentle_exchange_lut")


def decide(
    weights: np.ndarray | None,
    cue: np.ndarray,
    target: np.ndarray,
    pitch_classes: np.ndarray,
    key: int,
    config: ProtocolConfig | None = None,
    field_mode: str = "dense",
) -> ProtocolDecision:
    """Run the full basin-mediated interaction decision loop.

    observe -> closure (alignment, phase order, balance) -> if wolf/wrong-key
    intrusion abstain; else gentle transfer; then if settled into the target
    basin measure (correct), if into a nearby basin report basin, else if still
    moving wait, else abstain.
    """
    cfg = config or ProtocolConfig()
    report = phase_closure.close(pitch_classes, key)

    if report.wolf_fraction >= cfg.wolf_abstain_fraction:
        return ProtocolDecision(
            decision=Decision.ABSTAIN,
            active_overlap=0.0,
            basin_match_rate=0.0,
            settled=False,
            work_estimate=0,
            wolf_fraction=report.wolf_fraction,
            phase_order=report.phase_order,
            relaxation=None,
            notes="wolf/wrong-key intrusion above abstain fraction: do not couple",
        )

    if field_mode == "lut":
        result = gentle_exchange_lut(cue, target, report.coupling_mask, cfg.governor)
    elif field_mode == "dense":
        if weights is None:
            raise ValueError("dense field_mode requires weights")
        result = gentle_exchange(weights, cue, target, report.coupling_mask, cfg.governor)
    else:
        raise ValueError(f"unknown field_mode {field_mode!r}; expected 'dense' or 'lut'")
    settled = (result.steps < cfg.governor.max_steps) or (result.final_delta < cfg.settle_velocity)

    if not settled:
        decision, notes = Decision.WAIT, "aligned but not settled; allow more gentle transfer"
    elif result.basin_match_rate >= cfg.exact_basin_match:
        decision, notes = Decision.CORRECT, "settled into the target basin; safe to measure"
    elif result.active_overlap >= cfg.near_basin_overlap:
        decision, notes = Decision.BASIN, "settled into a nearby basin; report basin, do not force"
    else:
        decision, notes = Decision.ABSTAIN, "settled but no safe basin reached"

    return ProtocolDecision(
        decision=decision,
        active_overlap=result.active_overlap,
        basin_match_rate=result.basin_match_rate,
        settled=settled,
        work_estimate=result.field_evaluations,
        wolf_fraction=report.wolf_fraction,
        phase_order=report.phase_order,
        relaxation=result,
        notes=notes,
    )
