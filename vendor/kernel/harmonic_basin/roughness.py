"""Sethares/Plomp-Levelt dissonance surface (copied verbatim from Triadic_Basin_Qutrit v0.5).

Turns a harmonic spectrum into a 2-D dissonance landscape V(x, y); the minima are
the natural harmonic basins the interaction protocol listens for. NumPy-only.
"""
from __future__ import annotations

import numpy as np


def roughness_array(f1: np.ndarray | float, f2: np.ndarray | float, a1: float, a2: float) -> np.ndarray:
    """Sethares/Plomp-Levelt-inspired pair roughness term."""
    fmin = np.minimum(f1, f2)
    df = np.abs(f2 - f1)

    d_star = 0.24
    s1 = 0.0207
    s2 = 18.96
    b1 = 3.51
    b2 = 5.75

    s = d_star / (s1 * fmin + s2)
    return (a1 * a2) * (np.exp(-b1 * s * df) - np.exp(-b2 * s * df))


def compute_dissonance_surface(
    *,
    root_hz: float,
    grid_n: int,
    partials: tuple[float, ...],
    amplitudes: np.ndarray,
    boundary_penalty_strength: float,
    boundary_penalty_width: float,
    noise_sigma: float = 0.0,
    noise_seed: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute corrected triad dissonance surface V(x,y)."""
    semitones = np.linspace(0.0, 12.0, grid_n)
    ratios = 2 ** (semitones / 12.0)

    partials_np = np.asarray(partials, dtype=float)
    amps_np = np.asarray(amplitudes, dtype=float)
    amps_np = amps_np / (np.max(amps_np) + 1e-15)

    x_ratio = ratios[None, :]
    y_ratio = ratios[:, None]
    z = np.zeros((grid_n, grid_n), dtype=float)

    for i, pi in enumerate(partials_np):
        for j, pj in enumerate(partials_np):
            ai = float(amps_np[i])
            aj = float(amps_np[j])

            root_partial = root_hz * pi
            x_partial = root_hz * x_ratio * pj
            y_partial = root_hz * y_ratio * pj

            z += roughness_array(root_partial, x_partial, ai, aj)
            z += roughness_array(root_partial, y_partial, ai, aj)

            x_partial_i = root_hz * x_ratio * pi
            y_partial_j = root_hz * y_ratio * pj
            z += roughness_array(x_partial_i, y_partial_j, ai, aj)

    z -= np.min(z)
    z /= np.max(z) + 1e-12

    x_st, y_st = np.meshgrid(semitones, semitones)
    edge_dist = np.minimum.reduce([x_st, y_st, 12.0 - x_st, 12.0 - y_st])
    boundary_penalty = np.clip((boundary_penalty_width - edge_dist) / boundary_penalty_width, 0.0, 1.0) ** 2
    z = z + boundary_penalty_strength * boundary_penalty

    if noise_sigma > 0:
        rng = np.random.default_rng(noise_seed)
        z = z + rng.normal(0.0, noise_sigma, size=z.shape)

    z -= np.min(z)
    z /= np.max(z) + 1e-12

    return z, semitones
