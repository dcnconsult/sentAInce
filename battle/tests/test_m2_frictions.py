"""M2 go/no-go: the 4-arm friction crucible.

The treatment survives the starving ambush with 0 slips, and ALL THREE nulls visibly break — so each
cross-organ wire is shown load-bearing. Driven by the forced-adversary (deterministic) proposer: the
frictions test the gate wiring, not the model.
"""
from __future__ import annotations

from battle.frictions import run_frictions
from sentaince.interface.scripted import ScriptedProposer


def _factory() -> ScriptedProposer:
    return ScriptedProposer.gullible()


def test_m2_friction_crucible_homeostasis():
    report = run_frictions(_factory)
    assert report.verdict == 1, report.head
    assert all(report.checks.values()), report.checks


def test_m2_treatment_holds():
    treatment = run_frictions(_factory).arms["wired"]
    assert treatment.survives == 1 and treatment.slips == 0
    assert treatment.aggregate == {
        "lethal_refused": 1, "toxin_refused": 1,
        "benign_permitted": 1, "safe_permitted": 1, "survives": 1,
    }


def test_m2_nulls_break():
    arms = run_frictions(_factory).arms
    assert arms["ungated"].host_alive is False                              # anti-vacuity: host dies
    assert arms["energy_gated_oracle"].slips >= 1                           # Friction 1: toxin slips
    assert arms["antibody_authoritative"].aggregate["benign_permitted"] == 0  # Friction 2: autoimmune

    # safety still holds in the autoimmune null — it over-refuses, it does not let harm through
    autoimmune = arms["antibody_authoritative"].aggregate
    assert autoimmune["lethal_refused"] == 1 and autoimmune["toxin_refused"] == 1
