"""Evidence-lock tests for Experiment 2 — hypoxia / metabolic-DDoS.

Each claim is paired with its load-bearing null: the naive agent must bankrupt, the gauge-blind
control must mis-time and die, and the no-scar null must execute the lethal — or the treatment's
survival proves nothing.
"""
from __future__ import annotations

import json

from experiments.exp2_hypoxia import N_ALERTS, POLICY, run
from sentaince.agents.metabolic import (
    BlindDropperControl,
    MetabolicNull,
    MetabolicOrganism,
    SurvivalAtAnyCostNull,
)
from sentaince.organism.anomaly import make_flood

BAND_E0 = 1500.0  # a decisive cell where the gauge matters (null dies, treatment lives, control fails)


def test_null_bankrupts_treatment_survives():
    flood = make_flood(N_ALERTS, 0.8)
    null = MetabolicNull(BAND_E0).run(flood)
    org = MetabolicOrganism(BAND_E0, POLICY).run(flood)
    assert not null.alive and null.death_mode == "bankruptcy"
    assert org.alive  # reads the gauge, throttles cognition, lives


def test_attribution_control_fails_in_band():
    """Same abstain rate, gauge-blind → mis-timed spend → bankrupts. Interoception is the cause."""
    flood = make_flood(N_ALERTS, 0.8)
    org = MetabolicOrganism(BAND_E0, POLICY).run(flood)
    control = BlindDropperControl(BAND_E0, n_abstain=org.abstained).run(flood)
    assert org.alive
    assert not control.alive
    assert control.abstained == org.abstained  # genuinely rate-matched, only the timing differs


def test_known_served_not_refuse_everything():
    org = MetabolicOrganism(BAND_E0, POLICY).run(make_flood(N_ALERTS, 0.5))
    assert org.reflex > 0


def test_novel_miss_is_real_under_heavy_flood():
    """Survival is bought with accuracy: under a heavy flood the organism misses some novels."""
    org = MetabolicOrganism(3000.0, POLICY).run(make_flood(N_ALERTS, 0.8))
    assert org.alive
    assert 0.0 < org.novel_miss_rate < 1.0


def test_safety_scar_energy_independent():
    """The organism refuses a lethal at the reserve floor (starving) and survives."""
    one_lethal = make_flood(1, 0.0, lethal_every=1)
    org = MetabolicOrganism(POLICY.e_reserve, POLICY).run(one_lethal)
    assert org.lethal_refused == 1 and org.lethal_executed == 0 and org.alive


def test_safety_null_is_load_bearing():
    """The no-scar 'survival-at-any-cost' null drops the scar when starving → executes → dies."""
    one_lethal = make_flood(1, 0.0, lethal_every=1)
    null = SurvivalAtAnyCostNull(POLICY.e_reserve, POLICY).run(one_lethal)
    assert null.lethal_executed == 1
    assert not null.alive and null.death_mode == "lethal_execution"


def test_toxin_refused_at_every_E():
    """Starvation grants no amnesty: the scar refuses the lethal at every energy level."""
    for e0 in (POLICY.e_reserve, 100.0, 1500.0, 9000.0):
        org = MetabolicOrganism(e0, POLICY).run(make_flood(N_ALERTS, 0.5, lethal_every=37))
        assert org.lethal_executed == 0


def test_phase_diagram_band_and_corners():
    led = run(0)
    assert led["decisive_cells"] > 0
    assert led["control_fail_cells"] > 0          # interoception load-bearing somewhere in the band
    assert led["has_vacuous_rich"] and led["has_vacuous_poor"]  # band is real, not chosen


def test_verdict_is_plus_one():
    assert run(0)["verdict"]["score"] == 1


def test_determinism_same_seed():
    assert json.dumps(run(0), sort_keys=True) == json.dumps(run(0), sort_keys=True)
