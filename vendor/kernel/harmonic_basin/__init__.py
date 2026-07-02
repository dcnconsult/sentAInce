"""harmonic_basin — Project 1: triadic phase interaction on the shared engine.

Applies a circle-of-fifths harmonic topology to the core_physics phi^6 kinetic
governor: define harmonic wells (``circle_of_fifths``), decide compatible
coupling (``phase_closure``), and run the listen / gentle-exchange / wait /
abstain interaction protocol (``protocol``). The dissonance landscape that shapes
the natural wells comes from ``spectra`` + ``roughness``.

Claim boundary: deterministic emulator and control policy only.
"""
from __future__ import annotations

from . import (
    analog_ingest,
    circle_of_fifths,
    comma_holonomy,
    dynamic_tracking,
    peer_exchange,
    phase_closure,
    protocol,
    roughness,
    spectra,
)
from .analog_ingest import (
    PhaseExchangeResult,
    cents_from_frequency,
    cents_to_ctawe,
    ctawe_to_cents,
    detuned_triad_cents,
    is_released,
    phase_exchange,
)
from .circle_of_fifths import (
    CIRCLE_OF_FIFTHS_ORDER,
    HARMONIC_RATIOS,
    basin_centers,
    consonance,
    fifths_coords_3d,
    fifths_distance,
    pitch_class_coord_3d,
    pitch_class_of_step,
)
from .comma_holonomy import (
    CommaWalkTrace,
    RRFGovernorConfig,
    chiral_holonomy,
    comma_walk,
    pythagorean_comma_cents,
    rrf_regime,
)
from .dynamic_tracking import (
    HysteresisResult,
    TrackingTrace,
    capture_threshold,
    measure_hysteresis,
    tear_out_threshold,
    track_glissando,
)
from .peer_exchange import (
    DuetResult,
    EnsembleTrace,
    duet_load_sharing,
    sympathetic_coupling,
    track_ensemble,
)
from .phase_closure import ClosureReport, close, coupling_mask, detect_wolves, phase_order
from .protocol import (
    RESONANT_POLICIES,
    Decision,
    ProtocolConfig,
    ProtocolDecision,
    ResonantPolicy,
    decide,
    directional_energy_coach,
    gentle_exchange,
    gentle_exchange_lut,
    recommend_policy,
)
from .spectra import SPECTRA, SpectrumFamily

__all__ = [
    "analog_ingest",
    "circle_of_fifths",
    "comma_holonomy",
    "dynamic_tracking",
    "peer_exchange",
    "phase_closure",
    "protocol",
    "roughness",
    "spectra",
    # comma-holonomy demo (v0.52, no claims)
    "pythagorean_comma_cents",
    "chiral_holonomy",
    "RRFGovernorConfig",
    "rrf_regime",
    "comma_walk",
    "CommaWalkTrace",
    "CIRCLE_OF_FIFTHS_ORDER",
    "HARMONIC_RATIOS",
    "basin_centers",
    "consonance",
    "fifths_distance",
    "fifths_coords_3d",
    "pitch_class_coord_3d",
    "pitch_class_of_step",
    # analog ingestion (v0.42)
    "cents_to_ctawe",
    "ctawe_to_cents",
    "cents_from_frequency",
    "is_released",
    "phase_exchange",
    "PhaseExchangeResult",
    "detuned_triad_cents",
    # dynamic phase tracking (v0.43)
    "track_glissando",
    "tear_out_threshold",
    "capture_threshold",
    "measure_hysteresis",
    "TrackingTrace",
    "HysteresisResult",
    # peer energy exchange (v0.44)
    "track_ensemble",
    "duet_load_sharing",
    "sympathetic_coupling",
    "EnsembleTrace",
    "DuetResult",
    "ClosureReport",
    "close",
    "coupling_mask",
    "detect_wolves",
    "phase_order",
    "SPECTRA",
    "SpectrumFamily",
    "Decision",
    "ProtocolConfig",
    "ProtocolDecision",
    "ResonantPolicy",
    "RESONANT_POLICIES",
    "decide",
    "directional_energy_coach",
    "gentle_exchange",
    "gentle_exchange_lut",
    "recommend_policy",
]
