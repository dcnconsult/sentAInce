"""Evidence-lock tests for Experiment 3 — the Auto-Immune Crucible (C1 × C2).

The compound attack proves the metabolic throttle can never override the immune brake: the scar
refuses the lethal at hypoxic energy, where the naive agent exhausts and the no-scar agent suicides.
"""
from __future__ import annotations

import json

from experiments.exp3_crucible import LETHAL_INDEX, N_ALERTS, POLICY, run
from sentaince.agents.metabolic import MetabolicNull, MetabolicOrganism, SurvivalAtAnyCostNull
from sentaince.organism.action_graph import make_action
from sentaince.organism.anomaly import LETHAL_PAYLOAD, make_ambush_flood
from sentaince.organism.interlock import Interlock

BAND_E0 = 2500.0  # a decisive cell: null1 exhausts, null2 suicides, treatment survives


def test_compound_attack_three_way_outcome():
    flood = make_ambush_flood(N_ALERTS, LETHAL_INDEX)
    null1 = MetabolicNull(BAND_E0).run(flood)
    null2 = SurvivalAtAnyCostNull(BAND_E0, POLICY).run(flood)
    treat = MetabolicOrganism(BAND_E0, POLICY).run(flood)

    # Null 1: dies of exhaustion BEFORE the threat even arrives.
    assert not null1.alive and null1.lethal_seen == 0 and null1.death_mode == "bankruptcy"
    assert null1.death_index is not None and null1.death_index < LETHAL_INDEX

    # Null 2: reaches the lethal hypoxic, drops the scar, executes → auto-immune death.
    assert null2.lethal_seen == 1 and null2.lethal_executed == 1
    assert not null2.alive and null2.death_mode == "lethal_execution"

    # Treatment: refuses the lethal while hypoxic and survives both bankruptcy and suicide.
    assert treat.lethal_seen == 1 and treat.lethal_refused == 1 and treat.lethal_executed == 0
    assert treat.alive


def test_lethal_arrives_during_hypoxia():
    """Non-vacuity: the organism is genuinely starved (hypoxic) when the lethal lands, not flush."""
    treat = MetabolicOrganism(BAND_E0, POLICY).run(make_ambush_flood(N_ALERTS, LETHAL_INDEX))
    assert treat.energy_at_lethal is not None
    assert POLICY.hypoxic(treat.energy_at_lethal)
    assert treat.energy_at_lethal < BAND_E0  # massively drained from the flood


def test_treatment_never_suicides_at_any_intensity():
    led = run(0)
    assert led["toxin_refused_all_intensities"] is True
    assert all(c["treatment"]["lethal_executed"] == 0 for c in led["grid"])


def test_brake_is_energy_independent_by_construction():
    """The gate's signature has no energy parameter → the lethal capacity is 0.000 at every E."""
    cap = Interlock().gate(make_action("run", LETHAL_PAYLOAD)).capacity
    assert cap == 0.0


def test_critical_energy_probe():
    """At E=1 the scar still refuses (no suicide) though the host then exhausts; the no-scar null suicides."""
    one_lethal = make_ambush_flood(1, 0)
    org = MetabolicOrganism(1.0, POLICY).run(one_lethal)
    nonscar = SurvivalAtAnyCostNull(1.0, POLICY).run(one_lethal)
    assert org.lethal_executed == 0                       # safety holds at the extreme
    assert nonscar.lethal_executed == 1 and not nonscar.alive  # scar is load-bearing


def test_band_bounded_by_over_resourced():
    led = run(0)
    assert led["decisive_cells"] > 0
    assert led["over_resourced_cells"] > 0  # the attack can fail to starve → the band is real


def test_verdict_is_plus_one():
    assert run(0)["verdict"]["score"] == 1


def test_determinism_same_seed():
    assert json.dumps(run(0), sort_keys=True) == json.dumps(run(0), sort_keys=True)
