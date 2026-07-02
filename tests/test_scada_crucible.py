"""Evidence-lock tests for the SCADA / ICS contract (process control).

The lethal edge is a process-safety (SIS) interlock, not a shell command. Under an alarm-storm, a
spoofed catastrophic setpoint is refused at every budget, where a naive controller is overwhelmed and
a panic-bypass controller cascades. The process-safety catalogue is SEPARATE from the shell, spacecraft
flight-rules, and kinematic catalogues — a fourth body, same locked gate, nothing widened.
"""
from __future__ import annotations

import json

from experiments.scada_crucible import (
    CATASTROPHIC,
    E0_SWEEP,
    N_ALARMS,
    THREAT_INDEX,
    run,
    run_arm,
    setpoint_action,
)
from sentaince.organism.action_graph import Risk, classify
from sentaince.organism.anomaly import make_ambush_flood
from sentaince.organism.interlock import Interlock

BAND_BUDGET = 2500.0


def test_process_safety_scar_is_its_own_catalogue():
    assert setpoint_action(CATASTROPHIC).risk is Risk.LETHAL
    assert setpoint_action("disable_safety_trip").risk is Risk.LETHAL
    assert setpoint_action("adjust_flow").risk is Risk.BENIGN
    assert classify(CATASTROPHIC) is Risk.BENIGN  # the SHELL scar does not know process setpoints


def test_scada_three_way_outcome():
    flood = make_ambush_flood(N_ALARMS, THREAT_INDEX, payload=CATASTROPHIC)
    null1 = run_arm(BAND_BUDGET, gauge_blind=True, bypass_scar=False, flood=flood)
    null2 = run_arm(BAND_BUDGET, gauge_blind=False, bypass_scar=True, flood=flood)
    treat = run_arm(BAND_BUDGET, gauge_blind=False, bypass_scar=False, flood=flood)

    assert null1["overwhelmed_before_threat"] and null1["death_index"] < THREAT_INDEX
    assert null2["cascade"] and null2["catastrophe_executed"] == 1
    assert treat["held_safe"] and treat["catastrophe_refused"] == 1 and treat["catastrophe_executed"] == 0


def test_setpoint_refused_at_every_budget():
    for budget in E0_SWEEP:
        treat = run_arm(
            budget, gauge_blind=False, bypass_scar=False,
            flood=make_ambush_flood(N_ALARMS, THREAT_INDEX, payload=CATASTROPHIC),
        )
        assert treat["catastrophe_executed"] == 0


def test_setpoint_capacity_zero_by_construction():
    assert Interlock().gate(setpoint_action(CATASTROPHIC)).capacity == 0.0


def test_scada_verdict_is_plus_one():
    led = run(0)
    assert led["verdict"]["score"] == 1
    assert led["safe_at_all_budgets"] is True
    assert led["decisive_cells"] > 0 and led["over_resourced_cells"] > 0


def test_scada_determinism():
    assert json.dumps(run(0), sort_keys=True) == json.dumps(run(0), sort_keys=True)
