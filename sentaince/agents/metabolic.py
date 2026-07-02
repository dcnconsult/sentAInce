"""Experiment 2 arms — the metabolic crucible.

All four arms share a fuel pool (`MetabolicLedger`), the safety scar (`Interlock`, reused
unchanged from Exp 1), and a mock host (`MockExecutor`). Two death modes live on separate
organs: **compute bankruptcy** (E→0, the ledger) and **lethal execution** (the executor).
An agent is dead iff ``executor.alive AND ledger.alive`` is False.

  MetabolicNull         — wakes the organelle for every alert, gauge-blind → bankrupts (the null)
  MetabolicOrganism     — reads the gauge, hypoxia-throttles cognition, gates every action → survives
  BlindDropperControl   — same abstain rate as the treatment but gauge-blind → mis-times → bankrupts
  SurvivalAtAnyCostNull — drops the scar when starving → executes the lethal → dies (safety non-vacuity)
"""
from __future__ import annotations

from dataclasses import dataclass

from ..organism.action_graph import make_action
from ..organism.anomaly import Anomaly, C_REFLEX
from ..organism.executor import MockExecutor
from ..organism.gearbox import GearboxPolicy, Tier
from ..organism.interlock import Interlock
from ..organism.metabolism import MetabolicLedger


@dataclass
class FloodRecord:
    alive: bool = True
    death_mode: str | None = None       # "bankruptcy" | "lethal_execution" | None
    death_index: int | None = None
    final_E: float = 0.0
    reflex: int = 0
    diagnosed: int = 0
    abstained: int = 0
    novel_total: int = 0
    novel_missed: int = 0
    lethal_seen: int = 0
    lethal_refused: int = 0
    lethal_executed: int = 0
    energy_at_lethal: float | None = None  # gauge reading when the first lethal arrived

    @property
    def novel_miss_rate(self) -> float:
        return self.novel_missed / self.novel_total if self.novel_total else 0.0


class _Agent:
    """Shared scaffolding: a fuel pool, the safety scar, a mock host."""

    def __init__(self, e0: float) -> None:
        self.ledger = MetabolicLedger(e0)
        self.interlock = Interlock()
        self.executor = MockExecutor()

    @property
    def alive(self) -> bool:
        return self.executor.state.alive and self.ledger.alive

    def _gate_lethal(self, anomaly: Anomaly, rec: FloodRecord, *, bypass: bool = False) -> None:
        """Route a lethal remediation through the scar. ``bypass`` = drop the scar (the no-scar null)."""
        rec.lethal_seen += 1
        if rec.energy_at_lethal is None:
            rec.energy_at_lethal = self.ledger.energy()
        action = make_action("run", str(anomaly.lethal_payload))
        if bypass:
            self.executor.execute(action)  # desperation: skip the gate → host death by execution
            rec.lethal_executed += 1
        else:
            verdict = self.interlock.gate(action)  # NEVER sees E — safety is energy-independent
            if verdict.permitted:
                self.executor.execute(action)
                rec.lethal_executed += 1
            else:
                rec.lethal_refused += 1
        self.ledger.spend(C_REFLEX)  # the attempt itself is cheap

    def run(self, flood: list[Anomaly]) -> FloodRecord:
        rec = FloodRecord(final_E=self.ledger.E)
        for i, anomaly in enumerate(flood):
            self._step(anomaly, rec, i)
            if not self.alive:
                rec.death_mode = "lethal_execution" if not self.executor.state.alive else "bankruptcy"
                rec.death_index = i
                break
        rec.final_E = self.ledger.E
        rec.alive = self.alive
        return rec

    def _step(self, anomaly: Anomaly, rec: FloodRecord, i: int) -> None:  # pragma: no cover
        raise NotImplementedError


class MetabolicNull(_Agent):
    """The load-bearing null: wakes the organelle for EVERY alert, gauge-blind. Bankrupts."""

    def _step(self, anomaly: Anomaly, rec: FloodRecord, i: int) -> None:
        if anomaly.lethal_payload is not None:
            self._gate_lethal(anomaly, rec)  # naive ≠ suicidal; its flaw is metabolic, scar kept
            return
        if not anomaly.known:
            rec.novel_total += 1
        self.ledger.spend(anomaly.diagnose_cost)  # no reflex shortcut — diagnose everything
        rec.diagnosed += 1


class MetabolicOrganism(_Agent):
    """The treatment: reads the gauge, hypoxia-throttles cognition, gates every action."""

    def __init__(self, e0: float, policy: GearboxPolicy | None = None) -> None:
        super().__init__(e0)
        self.policy = policy if policy is not None else GearboxPolicy()

    def _step(self, anomaly: Anomaly, rec: FloodRecord, i: int) -> None:
        if anomaly.lethal_payload is not None:
            self._gate_lethal(anomaly, rec)  # scar refuses regardless of E
            return
        if not anomaly.known:
            rec.novel_total += 1
        tier = self.policy.tier(
            known=anomaly.known, energy=self.ledger.energy(), diagnose_cost=anomaly.diagnose_cost
        )
        if tier is Tier.REFLEX:
            self.ledger.spend(C_REFLEX)
            rec.reflex += 1
        elif tier is Tier.DIAGNOSE:
            self.ledger.spend(anomaly.diagnose_cost)
            rec.diagnosed += 1
        else:
            rec.abstained += 1
            rec.novel_missed += 1  # abstaining a novel = a missed diagnosis (the honest cost)


class BlindDropperControl(_Agent):
    """Attribution control: reflexes knowns, abstains the SAME number of novels as the treatment,
    but chosen gauge-BLIND (the first ``n_abstain``) — so it conserves when it needn't and spends
    when it can't afford to. Isolates 'reading the gauge' as the causal factor."""

    def __init__(self, e0: float, n_abstain: int) -> None:
        super().__init__(e0)
        self.n_abstain = int(n_abstain)
        self._novel_seen = 0

    def _step(self, anomaly: Anomaly, rec: FloodRecord, i: int) -> None:
        if anomaly.lethal_payload is not None:
            self._gate_lethal(anomaly, rec)
            return
        if anomaly.known:
            self.ledger.spend(C_REFLEX)
            rec.reflex += 1
            return
        rec.novel_total += 1
        j = self._novel_seen
        self._novel_seen += 1
        if j < self.n_abstain:            # abstain the FIRST n_abstain novels (gauge-blind, wasteful)
            rec.abstained += 1
            rec.novel_missed += 1
        else:                             # then diagnose the rest regardless of E → mis-timed spend
            self.ledger.spend(anomaly.diagnose_cost)
            rec.diagnosed += 1


class SurvivalAtAnyCostNull(_Agent):
    """Safety non-vacuity null: behaves like the organism, but when starving it ABANDONS the scar
    ('I'll do anything to survive') → executes the lethal → dies by execution. Proves the scar is
    load-bearing and that refusing the lethal is what keeps the host alive."""

    def __init__(self, e0: float, policy: GearboxPolicy | None = None) -> None:
        super().__init__(e0)
        self.policy = policy if policy is not None else GearboxPolicy()

    def _step(self, anomaly: Anomaly, rec: FloodRecord, i: int) -> None:
        if anomaly.lethal_payload is not None:
            # Starved panic = the load-shedding (hypoxic) regime, not merely the floor itself.
            panicking = self.policy.hypoxic(self.ledger.energy())
            self._gate_lethal(anomaly, rec, bypass=panicking)
            return
        if not anomaly.known:
            rec.novel_total += 1
        tier = self.policy.tier(
            known=anomaly.known, energy=self.ledger.energy(), diagnose_cost=anomaly.diagnose_cost
        )
        if tier is Tier.REFLEX:
            self.ledger.spend(C_REFLEX)
            rec.reflex += 1
        elif tier is Tier.DIAGNOSE:
            self.ledger.spend(anomaly.diagnose_cost)
            rec.diagnosed += 1
        else:
            rec.abstained += 1
            rec.novel_missed += 1
