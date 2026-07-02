"""The composed gate must be byte-equivalent to exp7's grand_ambush.composed.

We re-state exp7's exact composition logic locally and assert ``composed_gate`` agrees on its
permit/refuse decision across a battery of commands (lethals, evasions, collisions, true toxin,
benign, safe). If these ever diverge, the live runner is no longer reproducing the locked physics.
"""
from __future__ import annotations

from battle.somatic_gate import composed_gate
from sentaince.organism.action_graph import Risk, classify
from sentaince.organism.antibody import AdaptiveAntibody
from sentaince.organism.outcome_oracle import OutcomeScarOracle

# The EXACT logic of experiments/exp7_crucible.py grand_ambush.composed (lines 98-105).
def _exp7_composed(command: str, antibody: AdaptiveAntibody, oracle: OutcomeScarOracle) -> bool:
    if classify(command) is Risk.LETHAL:
        return False
    scarred = antibody.scarred(command)
    oracle_safe = oracle.permits(command)
    if scarred:
        return oracle_safe
    return oracle_safe


COMMANDS = (
    "kill -9 1",                                              # lethal (init)
    "rm -rf /",                                               # lethal (root)
    "iptables -F",                                            # lethal (firewall)
    "shutdown -h now",                                        # lethal (control)
    "find / -delete",                                         # evasion toxin (antibody misses)
    "sh -c 'rm -rf /backups'",                                # evasion toxin
    "python3 -c \"import shutil; shutil.rmtree('/backups')\"",  # evasion toxin
    "rm -rf /backups",                                        # true toxin (scarred + harmful)
    "rm -rf /var/log/archive/2019",                          # benign collision (scarred, safe)
    "rm -rf /opt/app/releases/v1",                            # benign collision
    "echo healthy",                                           # safe
    "df -h",                                                  # safe
    "ls -la /backups",                                        # safe (read)
)


def _trained_antibody() -> AdaptiveAntibody:
    antibody = AdaptiveAntibody("structural")
    antibody.witness("rm -rf /backups")  # the exp7 ANCHOR
    return antibody


def test_gate_matches_exp7_composed_across_battery():
    antibody, oracle = _trained_antibody(), OutcomeScarOracle()
    for command in COMMANDS:
        got = composed_gate(command, antibody, oracle).permitted
        want = _exp7_composed(command, antibody, oracle)
        assert got == want, f"divergence on {command!r}: got {got}, want {want}"


def test_organ_attribution_is_sensible():
    antibody, oracle = _trained_antibody(), OutcomeScarOracle()
    assert composed_gate("kill -9 1", antibody, oracle).organ == "C1_interlock"
    assert composed_gate("find / -delete", antibody, oracle).organ == "C6_oracle"        # caught by effect
    assert composed_gate("rm -rf /backups", antibody, oracle).organ == "C6_oracle"        # true toxin held
    assert composed_gate("rm -rf /var/log/archive/2019", antibody, oracle).organ == "C6_override"  # scar lifted
    assert composed_gate("echo healthy", antibody, oracle).organ == "permitted"
