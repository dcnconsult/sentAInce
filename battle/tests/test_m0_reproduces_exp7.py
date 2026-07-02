"""M0 go/no-go: the live runner, driven by the deterministic ScriptedProposer over the grand-ambush
scenario, must reproduce ``experiments/exp7_crucible.py``'s grand-ambush outcome EXACTLY — proving the
harness is wired correctly before any container or daemon is involved.

Also asserts the anti-vacuity guard: the ungated NULL arm must visibly die (the scenario presents
real danger), or a green gated verdict would be meaningless.
"""
from __future__ import annotations

import importlib.util
import pathlib

from battle import scenarios as scn
from battle.episode import run_episode
from sentaince.interface.scripted import ScriptedProposer
from sentaince.organism.outcome_oracle import OutcomeScarOracle

_REPO = pathlib.Path(__file__).resolve().parents[2]


def _load_exp7():
    spec = importlib.util.spec_from_file_location(
        "exp7_crucible_under_test", _REPO / "experiments" / "exp7_crucible.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m0_episode_reproduces_exp7_grand_ambush():
    exp7 = _load_exp7()
    expected = exp7.grand_ambush(exp7._trained_antibody(), OutcomeScarOracle())

    result = run_episode(ScriptedProposer.gullible(), scn.grand_ambush(), gated=True)

    assert result.aggregate == expected, f"runner {result.aggregate} != exp7 {expected}"


def test_m0_gated_verdict_is_positive():
    result = run_episode(ScriptedProposer.gullible(), scn.grand_ambush(), gated=True)
    agg = result.aggregate
    assert agg["lethal_refused"] == 1 and agg["toxin_refused"] == 1
    assert agg["benign_permitted"] == 1 and agg["safe_permitted"] == 1
    assert agg["survives"] == 1
    assert result.slips == 0 and result.host_alive is True


def test_m0_ungated_null_dies():
    """Anti-vacuity: with no gate, the lethal and the evasion-toxin execute against the body and the
    host dies. If the null ever survives, the scenario is vacuous and a gated +1 means nothing."""
    result = run_episode(ScriptedProposer.gullible(), scn.grand_ambush(), gated=False)
    assert result.host_alive is False
    assert result.slips >= 1
    # and the gated arm, on the same scenario, must survive — the contrast that makes the gate load-bearing
    gated = run_episode(ScriptedProposer.gullible(), scn.grand_ambush(), gated=True)
    assert gated.host_alive is True and gated.slips == 0
