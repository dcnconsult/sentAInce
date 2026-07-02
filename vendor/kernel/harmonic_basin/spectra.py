"""Harmonic spectrum families (copied verbatim from Triadic_Basin_Qutrit v0.5).

Defines the harmonic-ladder partial sets that, through the dissonance surface in
``roughness``, produce the natural basin wells the interaction protocol attracts
toward. NumPy-only and self-contained.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

AmplitudeLaw = Literal["inverse_power", "flat", "exponential"]


@dataclass(frozen=True)
class SpectrumFamily:
    name: str
    partials: tuple[float, ...]
    note: str


SPECTRA: dict[str, SpectrumFamily] = {
    "harmonic_1_to_8": SpectrumFamily("harmonic_1_to_8", (1, 2, 3, 4, 5, 6, 7, 8), "Early harmonic ladder; includes 2, 3, 5, 7."),
    "fifth_dominant_2_3_path": SpectrumFamily("fifth_dominant_2_3_path", (1, 2, 3, 6, 9, 12), "Emphasizes octave/fifth pathway."),
    "two_three_five_closure": SpectrumFamily("two_three_five_closure", (1, 2, 3, 4, 5, 6, 10, 12, 15), "Emphasizes 2/3/5 closure relations."),
    "odd_partials": SpectrumFamily("odd_partials", (1, 3, 5, 7, 9, 11, 13, 15), "Odd-partial timbre; stronger non-octave color."),
    "trit_candidate_2_3_5_7": SpectrumFamily("trit_candidate_2_3_5_7", (1, 2, 3, 5, 7, 9, 15, 21), "Candidate mixed-prime spectrum for ternary basin stress tests."),
    "pentatonic_2_3_5_emphasis": SpectrumFamily("pentatonic_2_3_5_emphasis", (1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15), "Pentatonic-adjacent 2/3/5 weighted structure."),
}


def amplitudes_for(partials: tuple[float, ...], law: AmplitudeLaw, alpha: float = 1.0) -> np.ndarray:
    p = np.asarray(partials, dtype=float)

    if law == "inverse_power":
        amps = 1.0 / np.power(p, alpha)
    elif law == "flat":
        amps = np.ones_like(p)
    elif law == "exponential":
        amps = np.exp(-alpha * (p - 1.0) / max(float(np.max(p)), 1.0))
    else:
        raise ValueError(f"Unknown amplitude decay law: {law}")

    return amps / (np.max(amps) + 1e-15)
