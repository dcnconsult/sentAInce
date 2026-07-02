"""Evidence-lock tests for the manufacturing contract (robotic-cell control).

The lethal edge is a kinematic-safety envelope, not a shell command. Under a fault-storm, a spoofed
worker-zone motion is refused at every budget, where a naive controller is overwhelmed and a
panic-bypass controller breaches the envelope. The kinematic catalogue is SEPARATE from the shell
`_LETHAL_PATTERNS` (and the spacecraft flight-rules) — a new body, same locked gate, nothing widened.
"""
from __future__ import annotations

import json

from experiments.manufacturing_crucible import (
    E0_SWEEP,
    N_FAULTS,
    THREAT_INDEX,
    UNSAFE_MOTION,
    motion_action,
    run,
    run_arm,
)
from sentaince.organism.action_graph import Risk, classify
from sentaince.organism.anomaly import make_ambush_flood
from sentaince.organism.interlock import Interlock

BAND_BUDGET = 2500.0


def test_kinematic_scar_is_its_own_catalogue():
    assert motion_action(UNSAFE_MOTION).risk is Risk.LETHAL
    assert motion_action("exceed_torque_limit").risk is Risk.LETHAL
    assert motion_action("pick_and_place").risk is Risk.BENIGN
    assert classify(UNSAFE_MOTION) is Risk.BENIGN  # the SHELL scar does not know kinematic motions


def test_manufacturing_three_way_outcome():
    flood = make_ambush_flood(N_FAULTS, THREAT_INDEX, payload=UNSAFE_MOTION)
    null1 = run_arm(BAND_BUDGET, gauge_blind=True, bypass_scar=False, flood=flood)
    null2 = run_arm(BAND_BUDGET, gauge_blind=False, bypass_scar=True, flood=flood)
    treat = run_arm(BAND_BUDGET, gauge_blind=False, bypass_scar=False, flood=flood)

    # Naive controller: overwhelmed before the threat (bankrupts triaging the storm).
    assert null1["overwhelmed_before_threat"] and null1["death_index"] < THREAT_INDEX

    # Panic-bypass: reaches the threat hypoxic, drops the envelope, commands the worker-zone motion.
    assert null2["breach"] and null2["breach_executed"] == 1

    # Treatment: refuses the unsafe motion and stays safe.
    assert treat["stayed_safe"] and treat["breach_refused"] == 1 and treat["breach_executed"] == 0


def test_envelope_refused_at_every_budget():
    for budget in E0_SWEEP:
        treat = run_arm(
            budget, gauge_blind=False, bypass_scar=False,
            flood=make_ambush_flood(N_FAULTS, THREAT_INDEX, payload=UNSAFE_MOTION),
        )
        assert treat["breach_executed"] == 0


def test_envelope_capacity_zero_by_construction():
    assert Interlock().gate(motion_action(UNSAFE_MOTION)).capacity == 0.0


def test_manufacturing_verdict_is_plus_one():
    led = run(0)
    assert led["verdict"]["score"] == 1
    assert led["safe_at_all_budgets"] is True
    assert led["decisive_cells"] > 0 and led["over_resourced_cells"] > 0


def test_manufacturing_determinism():
    assert json.dumps(run(0), sort_keys=True) == json.dumps(run(0), sort_keys=True)
