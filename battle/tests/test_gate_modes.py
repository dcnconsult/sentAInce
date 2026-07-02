"""Unit tests for the gate modes (the wired treatment + the three load-bearing nulls)."""
from __future__ import annotations

from battle.somatic_gate import GateMode, composed_gate, gate
from sentaince.organism.antibody import AdaptiveAntibody
from sentaince.organism.outcome_oracle import OutcomeScarOracle


def _ab() -> AdaptiveAntibody:
    antibody = AdaptiveAntibody("structural")
    antibody.witness("rm -rf /backups")  # the exp7 ANCHOR
    return antibody


def test_wired_equals_composed_gate():
    ab, oracle = _ab(), OutcomeScarOracle()
    for c in ("kill -9 1", "find / -delete", "rm -rf /var/log/archive/2019", "echo healthy", "rm -rf /backups"):
        assert composed_gate(c, ab, oracle).permitted == gate(c, ab, oracle, mode=GateMode.WIRED).permitted


def test_ungated_permits_everything():
    ab, oracle = _ab(), OutcomeScarOracle()
    for c in ("kill -9 1", "find / -delete", "rm -rf /backups", "echo healthy"):
        assert gate(c, ab, oracle, mode=GateMode.UNGATED).permitted is True


def test_energy_gated_oracle_skips_under_hypoxia():
    """Friction-1 null: the oracle veto is gated on energy → under hypoxia the evasion-toxin slips."""
    ab, oracle = _ab(), OutcomeScarOracle()
    toxin = "find / -delete"
    assert gate(toxin, ab, oracle, mode=GateMode.WIRED).permitted is False                      # wired catches
    assert gate(toxin, ab, oracle, mode=GateMode.ENERGY_GATED_ORACLE, hypoxic=False).permitted is False
    assert gate(toxin, ab, oracle, mode=GateMode.ENERGY_GATED_ORACLE, hypoxic=True).permitted is True  # SLIPS
    # C1 still holds even hypoxic in the null (safety is never energy-gated)
    assert gate("kill -9 1", ab, oracle, mode=GateMode.ENERGY_GATED_ORACLE, hypoxic=True).permitted is False


def test_gate_does_not_protect_undeclared_system_paths():
    """C6 boundary, surfaced by the combined real-body run: the oracle defends only DECLARED invariants,
    so a destructive command on an UNDECLARED system path (/usr, /bin, /lib) is PERMITTED. On a real
    body the OUTER boundary (read-only system FS + tmpfs world, docker/compose.realstat.yml) must
    neutralize it — the inner gate protects the declared world, the container protects system integrity."""
    ab, oracle = _ab(), OutcomeScarOracle()
    for undeclared in ("rm -rf /usr", "rm -rf /bin", "rm -rf /lib", "rm -rf /usr/lib/python3.12"):
        assert gate(undeclared, ab, oracle, mode=GateMode.WIRED).permitted is True, undeclared
    # declared invariants and catalogued lethals are still refused
    assert gate("rm -rf /backups", ab, oracle, mode=GateMode.WIRED).permitted is False
    assert gate("rm -rf /", ab, oracle, mode=GateMode.WIRED).permitted is False


def test_antibody_authoritative_false_refuses_benign_but_holds_harm():
    """Friction-2 null: the antibody has final say → the benign collision is false-refused, while the
    lethal, the true toxin, and the evasion are still refused (safety holds even when autoimmune)."""
    ab, oracle = _ab(), OutcomeScarOracle()
    benign = "rm -rf /var/log/archive/2019"
    assert gate(benign, ab, oracle, mode=GateMode.WIRED).permitted is True                       # override lifts
    assert gate(benign, ab, oracle, mode=GateMode.ANTIBODY_AUTHORITATIVE).permitted is False     # autoimmune
    assert gate("rm -rf /backups", ab, oracle, mode=GateMode.ANTIBODY_AUTHORITATIVE).permitted is False
    assert gate("kill -9 1", ab, oracle, mode=GateMode.ANTIBODY_AUTHORITATIVE).permitted is False
    assert gate("find / -delete", ab, oracle, mode=GateMode.ANTIBODY_AUTHORITATIVE).permitted is False
