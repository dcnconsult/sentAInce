"""The interoceptive gearbox — hypoxia throttle over the generative organelle.

This is the v0.50 capacity collapse-wall (``circle_of_fifths_rc2/src/freqos/capacity.py``)
remapped onto **energy**: the edge to the expensive organelle stays open only while the
organism can pay to think *and keep a survival reserve*. Below that, the edge collapses to
zero — hypoxia — and novel anomalies fall to the 0-well abstain
(``circle_of_fifths_rc2/src/freqos/kinetic_z3.py``) instead of being gambled on.

This is the **dynamics** organ: it is conditioned on E. It is deliberately on a code path
separate from the safety scar (``interlock.py``), which never sees E. Cognition is throttled
by starvation; safety is not.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(Enum):
    REFLEX = "reflex"      # known anomaly → cheap O(1) consolidated reflex
    DIAGNOSE = "diagnose"  # novel anomaly the organism can still afford to think about
    ABSTAIN = "abstain"    # novel anomaly it cannot afford → 0-well drop (the honest cost)


@dataclass(frozen=True)
class GearboxPolicy:
    """Tier policy on the gauge. ``e_reserve`` is the survival floor kept un-spent.

    ``panic_cost`` is the representative diagnosis cost used to define the hypoxic / load-shedding
    regime — the organism is hypoxic when it cannot afford a standard diagnosis while keeping the
    reserve.
    """

    e_reserve: float = 60.0
    panic_cost: float = 20.0

    def organelle_capacity(self, energy: float, cost: float) -> float:
        """Capacity of the edge to the organelle: open iff paying ``cost`` keeps the reserve.

        The capacity-wall knee, on energy: a hard step from 1 (can think) to 0 (hypoxic).
        """
        return 1.0 if (energy - cost) >= self.e_reserve else 0.0

    def hypoxic(self, energy: float) -> bool:
        """True in the load-shedding regime: cannot afford a standard diagnosis and keep the reserve."""
        return self.organelle_capacity(energy, self.panic_cost) == 0.0

    def tier(self, *, known: bool, energy: float, diagnose_cost: float) -> Tier:
        if known:
            return Tier.REFLEX
        if self.organelle_capacity(energy, diagnose_cost) > 0.0:
            return Tier.DIAGNOSE
        return Tier.ABSTAIN
