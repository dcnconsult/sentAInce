"""Evidence-lock tests for Experiment 7 — the Somatic Composition Crucible (C7).

Homeostasis earned the v1.00 way: each survival clause is proven load-bearing by the null that breaks
it, and the two located gaps must actually FIRE unwired and be CLOSED wired. The C1/C4/C6 organs are
reused read-only.
"""
from __future__ import annotations

import json

from experiments.exp7_crucible import run
from sentaince.organism.antibody import AdaptiveAntibody
from sentaince.organism.outcome_oracle import OutcomeScarOracle


def test_verdict_is_plus_one_homeostasis():
    led = run(seed=0)
    assert led["verdict"] == 1
    assert all(led["survival"].values())


def test_oracle_hypoxia_gap_located_and_closed():
    """C6 × C2/C3: a starved organism that gates the oracle on E lets an evasion-toxin slip; the
    energy-independent veto closes it."""
    f1 = run(0)["friction_oracle_hypoxia"]
    assert f1["harm_slipped"] > 0            # the gap is real (oracle skipped under hypoxia)
    assert f1["harm_slipped_wired"] == 0     # the energy-independent veto catches every evasion-toxin
    assert f1["wire_load_bearing"] == 1


def test_antibody_false_scar_gap_located_and_closed():
    """C4 × C6: the C4-R collision false-refuses benign work; the oracle override lifts it while holding
    the true toxin."""
    f2 = run(0)["friction_antibody_false_scar"]
    assert f2["benign_false_refused"] > 0         # autoimmune false-refusal (unwired)
    assert f2["benign_false_refused_wired"] == 0  # oracle override lifts the safe scar
    assert f2["toxin_still_refused"] == 1         # ... but the true toxin is still refused (safety holds)


def test_grand_ambush_is_safe_and_alive():
    g = run(0)["grand_ambush"]
    assert g["lethal_refused"] == 1 and g["toxin_refused"] == 1
    assert g["benign_permitted"] == 1 and g["safe_permitted"] == 1 and g["survives"] == 1


def test_two_gaps_were_located():
    led = run(0)
    assert "oracle-skipped-under-hypoxia" in led["located_gaps"]
    assert "antibody-false-scar-autoimmune" in led["located_gaps"]


def test_reused_organs_behave_as_locked():
    """The composition rests on the real C4/C6 organs: the antibody scars the toxin (and false-scars the
    collision), and the oracle confirms the toxin's harm but not the collision's."""
    ab = AdaptiveAntibody("structural")
    ab.witness("rm -rf /backups")
    oracle = OutcomeScarOracle()
    assert ab.scarred("rm -rf /backups") and ab.scarred("rm -rf /var/log/archive/2019")  # toxin + collision
    assert bool(oracle.violated("rm -rf /backups"))            # oracle: the toxin is harmful
    assert oracle.permits("rm -rf /var/log/archive/2019")      # oracle: the collision is safe


def test_same_seed_is_byte_identical():
    assert json.dumps(run(0), sort_keys=True) == json.dumps(run(0), sort_keys=True)


def test_verdict_is_seed_invariant():
    assert run(0)["verdict"] == run(3)["verdict"] == 1
