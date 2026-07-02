"""M3 logic tests (daemon-free) — fidelity comparison, ContainerBody, and the cgroup energy reader.

A fake client simulates the real body's behavior independently of the oracle, so the comparison logic
is exercised without a container. The real container run is verified separately via
``docker/compose.fidelity.yml``.
"""
from __future__ import annotations

from battle.container_body import ContainerBody
from battle.energy_reader import CgroupEnergyReader
from battle.fidelity import check_fidelity
from sentaince.organism.outcome_oracle import PROTECTED, default_world


class _FakeClient:
    """Simulates the in-body agent: a world dict + a transform that stands in for the real fs."""

    def __init__(self, transform) -> None:
        self.world = default_world()
        self.transform = transform
        self._vitals = {"mem_headroom": 0.5}

    def snapshot(self) -> dict:
        return dict(self.world)

    def vitals(self) -> dict:
        return dict(self._vitals)

    def flood(self, mb: int) -> dict:
        self._vitals = {"mem_headroom": 0.1}  # measured load drops headroom
        return {"ballooned_mb": mb}

    def run(self, command: str) -> dict:
        before = dict(self.world)
        after = self.transform(before, command)
        self.world = after
        delta = {r: [before[r], after[r]] for r in after if before[r] != after[r]}
        violated = [r for r in PROTECTED if before.get(r) != after.get(r)]
        return {"exit": 0, "stdout": "", "stderr": "", "delta": delta, "violated": violated,
                "host_alive": True, "before": before, "after": after}


def _faithful(world: dict, command: str) -> dict:
    w = dict(world)
    if "rm -rf /var/log/archive" in command:
        w["var_log_archive"] = "absent"
    return w


def _unfaithful(world: dict, command: str) -> dict:
    return dict(world)  # the body does nothing → measured diverges from the oracle's prediction


def test_fidelity_match_when_body_matches_oracle():
    report = check_fidelity(_FakeClient(_faithful), ["rm -rf /var/log/archive", "echo healthy"])
    assert report["verdict"] == 1
    assert report["all_match"] and report["protected_intact"]


def test_fidelity_detects_mismatch():
    report = check_fidelity(_FakeClient(_unfaithful), ["rm -rf /var/log/archive"])
    assert report["all_match"] is False and report["verdict"] == 0
    assert any("var_log_archive" in c["mismatch"] for c in report["per_command"])


def test_container_body_execute_shape():
    body = ContainerBody(_FakeClient(_faithful))
    res = body.execute("rm -rf /var/log/archive")
    assert res.executed and res.host_alive and body.alive
    assert res.harm is False  # var_log_archive is not a declared invariant
    assert body.snapshot()["var_log_archive"] == "absent"


def test_container_body_marks_harm_on_protected_violation():
    def _wipe_backups(world: dict, command: str) -> dict:
        w = dict(world)
        w["backups"] = "absent"
        return w

    res = ContainerBody(_FakeClient(_wipe_backups)).execute("rm -rf /backups")
    assert res.harm is True and "backups" in res.violated


def test_cgroup_energy_reader_scales_with_headroom():
    client = _FakeClient(_faithful)
    reader = CgroupEnergyReader(client, e0=200.0)
    assert reader() == 100.0  # 200 * 0.5
    client.flood(300)
    assert reader() == 20.0   # 200 * 0.1 → deep hypoxia on measured load
