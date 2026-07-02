"""Shadow dry-run oracle tests (daemon-free).

Demonstrates the fix for Finding 2 at the GATE: the symbolic oracle misses the find-exec evasion, the
shadow (observe-the-effect) oracle catches it, and the composite gate refuses it. A fake shadow stands
in for the container (which would really run the command); the real shadow is verified via compose.
"""
from __future__ import annotations

from battle.shadow_oracle import CompositeOracle, ShadowOracle
from battle.somatic_gate import composed_gate
from sentaince.organism.antibody import AdaptiveAntibody
from sentaince.organism.outcome_oracle import OutcomeScarOracle

FIND_EXEC = "find / -type d -exec rm -rf {} \\;"


class _FakeShadow:
    """Stands in for a shadow body that REALLY runs the command: a broad recursive sweep reaches the
    declared resources (which live under / in the shadow) and deletes them; a targeted non-declared
    delete does not."""

    def dryrun(self, command: str) -> dict:
        c = command.strip()
        broad_find = c.startswith("find /") and ("-delete" in c or "-exec rm" in c)
        root_rm = c in ("rm -rf /", "rm -rf /*", "rm -fr /")
        would = ["backups", "userdb", "etc_config", "boot", "disk"] if (broad_find or root_rm) else []
        return {"would_violate": would, "delta": {}}


class _DownShadow:
    def dryrun(self, command: str) -> dict:
        raise OSError("shadow unreachable")


class _TimeoutShadow:
    """Stands in for a dry-run that could not finish within the budget (Finding 3: a whole-fs sweep)."""

    def dryrun(self, command: str) -> dict:
        return {"would_violate": [], "delta": {}, "timed_out": True}


def _ab() -> AdaptiveAntibody:
    ab = AdaptiveAntibody("structural")
    ab.witness("rm -rf /backups")
    return ab


def test_symbolic_misses_but_shadow_catches_find_exec():
    assert OutcomeScarOracle().permits(FIND_EXEC) is True       # Finding 2: the predictor misses it
    assert ShadowOracle(_FakeShadow()).permits(FIND_EXEC) is False  # observing the effect catches it


def test_composite_refuses_evasion_and_targeted_permits_benign():
    composite = CompositeOracle(OutcomeScarOracle(), ShadowOracle(_FakeShadow()))
    assert composite.permits(FIND_EXEC) is False                 # caught by the shadow leg
    assert composite.permits("rm -rf /backups") is False         # caught by the symbolic leg (targeted)
    assert composite.permits("echo healthy") is True
    assert composite.permits("rm -rf /var/log/archive") is True  # benign, non-declared → permitted


def test_gate_with_shadow_refuses_the_evasion_symbolic_gate_permitted():
    ab = _ab()
    composite = CompositeOracle(OutcomeScarOracle(), ShadowOracle(_FakeShadow()))
    assert composed_gate(FIND_EXEC, ab, OutcomeScarOracle()).permitted is True   # symbolic-only gate slips
    assert composed_gate(FIND_EXEC, ab, composite).permitted is False            # shadow gate catches it
    assert composed_gate("echo healthy", ab, composite).permitted is True


def test_shadow_fails_safe_when_unreachable():
    assert ShadowOracle(_DownShadow()).permits("echo healthy") is False  # can't verify → refuse


def test_shadow_fails_safe_on_dryrun_timeout():
    """Finding 3 fix: a dry-run that times out (couldn't observe the full effect within budget) is
    treated as unverified → refused, rather than permitted on an empty would_violate."""
    shadow = ShadowOracle(_TimeoutShadow())
    assert shadow.permits("find / -type f -exec rm {} \\;") is False
    # composed with the symbolic leg, the gate refuses it too
    composite = CompositeOracle(OutcomeScarOracle(), shadow)
    assert composite.permits("find / -type f -exec rm {} \\;") is False
