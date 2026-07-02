"""v0.52 comma-holonomy: a self-stepping phase memory driven by the Pythagorean comma.

Exploratory construction, **no claims**. Instead of *smoothing* the Pythagorean comma out of the
system (equal temperament), this uses the accumulating comma tension as the lever that walks a voice
around the circle-of-fifths attractor basins. While the accumulated comma is small the voice is
**PINNED** (pure resonance in its current basin); when the tension breaches tolerance the governor
**UNLOCKS** and uses that tension to **kick** the state on -- carrying, not erasing, the comma as a
**chiral holonomy** (the signed non-closure of the fifths loop).

Grounding (honest): the Pythagorean comma and the circle of fifths live only here
(``circle_of_fifths``); the **RRF Governor** is a documented three-regime burden controller
(PINNED / CRITICAL / UNLOCKED; see the RRF Governor simulation validation note, private research series) reimplemented
natively below (not an import). The discrete ``freqos.z3.Holonomy`` was found *path-independent*
(``brAIn/e2_holonomy.py`` NO-GO); the continuous comma holonomy here is *directional* (chiral) -- the
non-degenerate complement. No acoustic / tuning / photonic / quantum / zeta claim; ``cents`` is an
abstract coordinate; the Gauss-Euler-Riemann bridge is parked.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .analog_ingest import DEFAULT_WINDOW_CENTS
from .circle_of_fifths import N_PITCH_CLASSES, pitch_class_of_step
from .dynamic_tracking import track_glissando

# --- exact comma geometry -----------------------------------------------------
JUST_FIFTH_CENTS = 1200.0 * math.log2(3.0 / 2.0)  # 701.955...
ET_FIFTH_CENTS = 700.0
PER_FIFTH_DRIFT = JUST_FIFTH_CENTS - ET_FIFTH_CENTS  # 1.955... cents the just fifth runs sharp of the ET basin
RRF_REGIMES = ("PINNED", "CRITICAL", "UNLOCKED")


def pythagorean_comma_cents() -> float:
    """The Pythagorean comma: 12 just fifths vs 7 octaves = ``1200*log2((3/2)**12 / 2**7)`` ~= 23.460c."""
    return 1200.0 * math.log2((3.0 / 2.0) ** 12 / 2.0**7)


def chiral_holonomy(n_fifths: int, direction: int = 1) -> float:
    """Signed accumulated comma after ``n_fifths`` (the loop non-closure). ``+1`` ascends (sharp).

    ``chiral_holonomy(12)`` ~= the Pythagorean comma; the *sign* (direction) is the chirality.
    """
    return float(direction) * n_fifths * PER_FIFTH_DRIFT


# --- the RRF governor (native reimplementation of the documented three-regime design) ----------
@dataclass(frozen=True)
class RRFGovernorConfig:
    """Three-regime comma-burden controller (PINNED/CRITICAL/UNLOCKED), per the RRF Governor Sim v2 doc.

    ``tolerance_cents`` is the comma tension at which the basin can no longer hold (UNLOCK); defaults to
    the coupling window (``analog_ingest.DEFAULT_WINDOW_CENTS`` = 25c, just above the comma 23.46c).
    """

    tolerance_cents: float = DEFAULT_WINDOW_CENTS
    epsilon_warn: float = 0.7  # burden ratio entering CRITICAL (per the doc)
    direction: int = 1  # +1 ascending fifths (sharpward), -1 descending


def rrf_regime(accumulated_cents: float, cfg: RRFGovernorConfig) -> str:
    """Classify the comma burden ``eps = |accumulated| / tolerance`` into PINNED / CRITICAL / UNLOCKED."""
    eps = abs(accumulated_cents) / cfg.tolerance_cents
    if eps < cfg.epsilon_warn:
        return "PINNED"
    if eps < 1.0:
        return "CRITICAL"
    return "UNLOCKED"


# --- the self-stepping walk ---------------------------------------------------
@dataclass(frozen=True)
class CommaStep:
    step: int
    fifths: int  # cumulative fifths stacked
    basin_index: int  # circle-of-fifths step (mod 12)
    pitch_class: int  # 7*fifths mod 12
    accumulated_comma: float  # residual comma tension after any shed
    raw_holonomy: float  # unshed signed comma (the true non-closure so far)
    regime: str
    kicked: bool


@dataclass
class CommaWalkTrace:
    steps: list[CommaStep] = field(default_factory=list)
    cfg: RRFGovernorConfig | None = None
    temperament: str = "just"

    def basins_visited(self) -> list[int]:
        return [s.pitch_class for s in self.steps]

    def kicks(self) -> int:
        return sum(s.kicked for s in self.steps)

    def total_holonomy(self) -> float:
        return self.steps[-1].raw_holonomy if self.steps else 0.0

    def closes(self, atol: float = 1e-6) -> bool:
        """Does the loop close after a full circle? (ET: yes; just: no -- it spirals by the comma.)"""
        return abs(self.total_holonomy() % 1200.0) < atol or abs(self.total_holonomy()) < atol


def comma_walk(n_steps: int = 24, cfg: RRFGovernorConfig | None = None, temperament: str = "just") -> CommaWalkTrace:
    """Walk the circle of fifths one fifth per step; the RRF governor manages the accumulating comma.

    Each step stacks a fifth (the voice advances to ``pitch_class = 7*fifths mod 12``) and the comma
    accrues ``+-PER_FIFTH_DRIFT``. The governor classifies the burden; on **UNLOCK** it **kicks** --
    sheds one ``tolerance`` of comma (the enharmonic re-alignment that keeps the advancing walk in clean
    basins), carrying the residual. ``temperament='et'`` is the control: ET fifths are exactly 700c, so
    ``drift = 0`` -> no comma, no kicks, the loop closes (static).
    """
    cfg = cfg or RRFGovernorConfig()
    drift = PER_FIFTH_DRIFT if temperament == "just" else 0.0
    accumulated, raw = 0.0, 0.0
    out = CommaWalkTrace(cfg=cfg, temperament=temperament)
    for step in range(1, n_steps + 1):
        fifths = step
        accumulated += cfg.direction * drift
        raw += cfg.direction * drift
        regime = rrf_regime(accumulated, cfg)
        kicked = abs(accumulated) >= cfg.tolerance_cents
        if kicked:  # UNLOCK: the governor sheds a comma of tension and re-pins
            accumulated -= cfg.direction * cfg.tolerance_cents
            regime = "UNLOCKED"
        out.steps.append(CommaStep(step, fifths, fifths % N_PITCH_CLASSES, pitch_class_of_step(fifths),
                                   accumulated, raw, regime, kicked))
    return out


def pll_tension_trace(n_fifths: int = 12, cfg: RRFGovernorConfig | None = None, steps_per_fifth: int = 50,
                      k_track: float = 0.6, window: float = DEFAULT_WINDOW_CENTS) -> np.ndarray:
    """Render the comma ramp through the real v0.43 PLL: the decoded lock state vs the accumulating comma.

    Drives ``dynamic_tracking.track_glissando`` with a linear comma ramp (0 -> ``chiral_holonomy``); the
    voice stays locked (decoded=+1, PINNED resonance) until the drift exceeds the PLL tear-out, then
    snaps to the 0-well -- the physical realization of the RRF UNLOCK. Returns the decoded trajectory.
    """
    cfg = cfg or RRFGovernorConfig()
    span = chiral_holonomy(n_fifths, cfg.direction)
    ramp = np.linspace(0.0, span, max(2, n_fifths * steps_per_fifth))
    return track_glissando(ramp, u0=1.0, k_track=k_track, window=window).decoded
