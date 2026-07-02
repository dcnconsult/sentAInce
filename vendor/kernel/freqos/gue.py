"""Engine-free GUE / Riemann-zero statistics primitives for the v0.49 routing gate.

Pure numpy + stdlib. These reproduce the descriptive Montgomery-Odlyzko fact -- the nearest-neighbour
spacings of the Riemann zeros follow the GUE (Gaussian Unitary Ensemble) level-repulsion law, not
Poisson -- which motivates "level repulsion" as a packing principle for the Z3 TAM (see
``gue_routing.py`` and ``docs/V049_GUE_ROUTING_GATE.md``). No number-theoretic or physical claim; the
zero data is bundled (``configs/riemann_zeros_sample.txt``, Odlyzko). The ``unfold_zeros`` formula
mirrors v0.48 ``harmonic_basin.riemann_ingest`` (re-implemented self-contained on this branch).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

TWO_PI = 2.0 * np.pi
PHI = (1.0 + np.sqrt(5.0)) / 2.0  # golden ratio: maximally irrational, low-discrepancy
_SAMPLE_PATH = Path(__file__).resolve().parents[2] / "configs" / "riemann_zeros_sample.txt"


# --------------------------------------------------------------- Riemann zeros
def load_zeros(n: int | None = None, *, path: str | Path | None = None) -> np.ndarray:
    """First ``n`` imaginary parts ``gamma_n`` (ascending) from the bundled sample or ``path``.

    Format-tolerant: one value per line, or whitespace columns (take the last float); '#'/blank
    lines skipped. ``n=None`` returns all available.
    """
    src = Path(path) if path is not None else _SAMPLE_PATH
    vals = []
    for line in src.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            vals.append(float(s.split()[-1]))
        except ValueError:
            continue
    gamma = np.asarray(vals, dtype=float)
    if gamma.size == 0:
        raise ValueError(f"no zeros parsed from {src}")
    return gamma[:n] if n is not None else gamma


def unfold_zeros(gamma: np.ndarray) -> np.ndarray:
    """Smooth-unfold ``gamma_n`` to mean spacing ~= 1 via the Riemann-von Mangoldt main term.

    ``N_smooth(g) = (g/2pi)(ln(g/2pi) - 1) + 7/8``. A standard, claim-free primitive.
    """
    x = np.asarray(gamma, dtype=float) / TWO_PI
    return x * (np.log(np.clip(x, 1e-12, None)) - 1.0) + 7.0 / 8.0


# --------------------------------------------------------------- spacing laws
def wigner_surmise_gue(s: np.ndarray) -> np.ndarray:
    """GUE nearest-neighbour spacing density ``p(s) = (32/pi^2) s^2 exp(-4 s^2/pi)`` (p(0)=0)."""
    s = np.asarray(s, dtype=float)
    return (32.0 / np.pi**2) * s**2 * np.exp(-4.0 * s**2 / np.pi)


def poisson_spacing(s: np.ndarray) -> np.ndarray:
    """Poisson (uncorrelated) nearest-neighbour spacing density ``p(s) = exp(-s)`` (p(0)=1)."""
    return np.exp(-np.asarray(s, dtype=float))


def nn_spacings_unfolded(values: np.ndarray) -> np.ndarray:
    """Nearest-neighbour spacings of a 1-D set, normalized to unit mean (empirical unfold)."""
    s = np.diff(np.sort(np.asarray(values, dtype=float)))
    m = s.mean()
    return s / m if m > 0 else s


def spacing_discrepancy(spacings: np.ndarray, model: str) -> float:
    """Max-CDF-gap (KS-like) distance between the empirical spacing CDF and a reference law.

    ``model`` in {"gue", "poisson"}. Pure numpy; integrates the reference density on a fine grid.
    """
    s = np.sort(np.asarray(spacings, dtype=float))
    if s.size == 0:
        return float("nan")
    grid = np.linspace(0.0, max(5.0, float(s[-1]) + 1.0), 4000)
    pdf = wigner_surmise_gue(grid) if model == "gue" else poisson_spacing(grid)
    cdf = np.cumsum(pdf) * (grid[1] - grid[0])
    cdf = cdf / cdf[-1]  # normalize the numeric integral to 1
    model_cdf = np.interp(s, grid, cdf)
    emp_cdf = np.arange(1, s.size + 1) / s.size
    return float(np.max(np.abs(emp_cdf - model_cdf)))


# --------------------------------------------------------------- support / significance helpers
def marginal_uniformity(patterns: np.ndarray) -> tuple[float, float]:
    """(max, mean) absolute per-column deviation from 1/3 of the {0,1,2} symbol frequencies.

    A matched-support check: ~0 means every coordinate keeps the uniform Z3 marginal, so any
    capacity shift is attributable to *joint* (pairwise) structure, not single-site statistics.
    """
    p = np.asarray(patterns, dtype=np.int64)
    counts = np.stack([(p == v).mean(axis=0) for v in (0, 1, 2)])  # (3, M)
    dev = np.abs(counts - 1.0 / 3.0)
    return float(dev.max()), float(dev.mean())


def zscore_separation(deltas: np.ndarray) -> tuple[float, float, float]:
    """(mean, std, z) of a per-seed delta sample; ``z = mean / (std/sqrt(n))`` (nan if n<2 or std=0)."""
    d = np.asarray(deltas, dtype=float)
    d = d[~np.isnan(d)]
    if d.size < 2:
        return (float(d.mean()) if d.size else float("nan"), float("nan"), float("nan"))
    mean, std = float(d.mean()), float(d.std(ddof=1))
    z = float("nan") if std == 0.0 else mean / (std / np.sqrt(d.size))
    return mean, std, z
