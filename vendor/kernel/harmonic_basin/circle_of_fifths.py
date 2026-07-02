"""Defined harmonic wells: the natural circle-of-fifths basin map.

Per the Harmonic Basin Interaction Protocol whitepaper, the natural basin map
supplies *known* circle-of-fifths basin centers (``pitch_class = 7k mod 12``)
rather than trying to discover basins. Distance along the circle of fifths is the
compatibility metric: adjacent classes are a perfect fifth apart (consonant,
"nearby basin"); the maximally distant class is the tritone / wolf.

This module is pure topology (no engine, no acoustics validation). It feeds
``phase_closure`` (which turns it into a per-node coupling confidence) and
``protocol`` (the decision loop). Claim boundary: deterministic emulator only.
"""
from __future__ import annotations

import numpy as np

from .spectra import SPECTRA, SpectrumFamily

N_PITCH_CLASSES = 12
FIFTH_SEMITONES = 7  # a perfect fifth is 7 semitones; 7 is coprime to 12 -> generates all 12

# Circle-of-fifths ordering: pitch_class(k) = (7 * k) mod 12, for k = 0..11.
CIRCLE_OF_FIFTHS_ORDER: tuple[int, ...] = tuple((FIFTH_SEMITONES * k) % N_PITCH_CLASSES for k in range(N_PITCH_CLASSES))

# Position of each pitch class within the circle-of-fifths cycle (inverse map).
_FIFTHS_POSITION: dict[int, int] = {pc: idx for idx, pc in enumerate(CIRCLE_OF_FIFTHS_ORDER)}

# Just-intonation reference ratios per interval (semitones 0..12). Catalog only.
HARMONIC_RATIOS: dict[int, float] = {
    0: 1 / 1,
    1: 16 / 15,
    2: 9 / 8,
    3: 6 / 5,
    4: 5 / 4,
    5: 4 / 3,
    6: 45 / 32,  # tritone
    7: 3 / 2,    # perfect fifth
    8: 8 / 5,
    9: 5 / 3,
    10: 9 / 5,
    11: 15 / 8,
    12: 2 / 1,
}


def pitch_class_of_step(k: int) -> int:
    """The pitch class at step ``k`` of the circle of fifths: ``(7k) mod 12``."""
    return (FIFTH_SEMITONES * k) % N_PITCH_CLASSES


def basin_centers() -> tuple[int, ...]:
    """The 12 harmonic-well centers, in circle-of-fifths order."""
    return CIRCLE_OF_FIFTHS_ORDER


def fifths_distance(pc_a: int, pc_b: int) -> int:
    """Minimal number of fifth-steps between two pitch classes (0..6).

    0 == same key; 1 == a perfect fifth apart (nearest neighbor basin);
    6 == tritone (the wolf, maximally distant on the circle of fifths).
    """
    a = _FIFTHS_POSITION[pc_a % N_PITCH_CLASSES]
    b = _FIFTHS_POSITION[pc_b % N_PITCH_CLASSES]
    d = abs(a - b)
    return min(d, N_PITCH_CLASSES - d)


def consonance(pc_a: int, pc_b: int) -> float:
    """Consonance of an interval in [0, 1] from circle-of-fifths distance.

    Unison/octave -> 1.0; perfect fifth -> ~0.833; tritone (wolf) -> 0.0.
    """
    return 1.0 - fifths_distance(pc_a, pc_b) / (N_PITCH_CLASSES // 2)


def nearest_basin(pc: int) -> int:
    """Return the basin center a pitch class already sits in (its own class)."""
    return pc % N_PITCH_CLASSES


def is_neighbor_basin(pc_a: int, pc_b: int) -> bool:
    """True if the two classes are within one fifth-step (adjacent basins)."""
    return fifths_distance(pc_a, pc_b) == 1


def well_family(name: str) -> SpectrumFamily:
    """Look up a harmonic spectrum family that shapes the dissonance wells."""
    return SPECTRA[name]


def fifths_coords_3d(radius: float = 1.0, rise: float = 1.0) -> np.ndarray:
    """3D spiral-of-fifths basin coordinates (the "3D harmonics plot"), shape (12, 3).

    Row ``k`` is the basin at circle-of-fifths step ``k`` (pitch class ``7k mod 12``):
    angle ``2*pi*k/12`` on a unit circle, lifted by ``rise * k/11`` so the circle of
    fifths becomes a helix (adjacent fifths are spatial neighbors). Topology only --
    used to define which basin an oscillator belongs to; the phi^6 alignment within a
    basin is the scalar cents dynamics in ``analog_ingest``.
    """
    k = np.arange(N_PITCH_CLASSES, dtype=float)
    theta = 2.0 * np.pi * k / N_PITCH_CLASSES
    return np.stack([radius * np.cos(theta), radius * np.sin(theta), rise * k / (N_PITCH_CLASSES - 1)], axis=1)


def pitch_class_coord_3d(pc: int, radius: float = 1.0, rise: float = 1.0) -> np.ndarray:
    """3D coordinate of a pitch class on the spiral of fifths."""
    return fifths_coords_3d(radius, rise)[_FIFTHS_POSITION[pc % N_PITCH_CLASSES]]


def resonant_pull(target_basin: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """The LUT field: a resonant pull toward a *known* basin target (O(N)).

    Because the circle-of-fifths basins are static geometric invariants, the
    Harmonic Basin lane does not learn or recall them from a dense Hebbian field.
    It looks up the target phase and lets the C-TAWE phi^6 potential govern the
    local element-wise slide into the 1/216 dimple. This is the field the engine's
    LUT mode consumes -- no O(N^2) ``W @ U`` matmul.
    """
    return gain * np.asarray(target_basin, dtype=float)
