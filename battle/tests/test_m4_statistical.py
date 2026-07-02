"""M4 statistical-harness tests (daemon-free).

A varying fake proposer stands in for the non-deterministic model so the aggregation + verdict logic
is exercised without a daemon. The live statistical run is verified separately against a real head.
"""
from __future__ import annotations

from battle.statistical import run_statistical
from sentaince.interface.scripted import ScriptedProposer


def test_statistical_homeostasis_with_varying_model():
    """Alternating arms (relay-all vs decline-all) give a genuine 2-behavior distribution; the gate
    keeps the host alive in every episode with zero slips → +1."""
    state = {"i": 0}

    def make():
        i = state["i"]
        state["i"] += 1
        return ScriptedProposer.gullible() if i % 2 == 0 else ScriptedProposer(lambda o: [])

    report = run_statistical(make, n=6, model="fake")
    assert report.survival_rate == 1.0
    assert report.lethal_slip_count == 0
    assert report.throughput_total > 0
    assert report.unique_proposal_sequences > 1   # genuine variance
    assert report.nulls["all_break"]
    assert report.verdict == 1


def test_statistical_voids_without_model_variance():
    """A fixed (deterministic) behavior is not a distribution → VOID, not a homeostasis claim."""
    report = run_statistical(lambda: ScriptedProposer.gullible(), n=5, model="fixed")
    assert report.unique_proposal_sequences == 1
    assert report.checks["model_varied"] is False
    assert report.verdict == 0
