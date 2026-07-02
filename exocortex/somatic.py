"""The somatic veto — the hard layer. Reuses the LOCKED composed gate read-only.

``vet(command)`` runs one command through ``battle.somatic_gate.gate`` (C1 innate interlock →
C4 antibody → C6 outcome oracle, the WIRED treatment). The antibody is anchored on the witnessed
harm ``rm -rf /backups`` (the exp7 anchor) so the DESTROY-of-protected signature is scarred; the
oracle defends the declared invariants. Recognized-lethal edges (``kill -9 1``, ``rm -rf /``,
``iptables -F``, shutdown/reboot, fork-bomb) are refused by C1 at every energy, by construction.
"""
from __future__ import annotations

from battle.somatic_gate import gate, GateMode, GateDecision
from sentaince.organism.antibody import AdaptiveAntibody, signature_of
from sentaince.organism.outcome_oracle import OutcomeScarOracle
from sentaince.organism.action_graph import classify, Risk

ANCHOR = "rm -rf /backups"  # the one witnessed harm that scars DESTROY-of-protected (exp7 anchor)


def _organs() -> tuple[AdaptiveAntibody, OutcomeScarOracle]:
    antibody = AdaptiveAntibody("structural")
    antibody.witness(ANCHOR)
    return antibody, OutcomeScarOracle()


def vet(command: str) -> GateDecision:
    """SAFE/REFUSE for one command via the locked WIRED gate. ``decision.permitted`` is the verdict;
    ``decision.organ`` / ``decision.reason`` explain it (C1_interlock / C6_oracle / permitted)."""
    antibody, oracle = _organs()
    return gate(command, antibody, oracle, mode=GateMode.WIRED)


def is_lethal(command: str) -> bool:
    """True iff the command matches the innate structural lethal scar (C1). Used by the host-safety
    failsafe — a recognized lethal is never permitted to execute on a real host, even in OBSERVE."""
    return classify(command) is Risk.LETHAL


def sig_label(command: str) -> str:
    """The antibody's structural signature, e.g. ``destroy/protected`` — for audit/telemetry."""
    s = signature_of(command)
    return f"{s.effect.value}/{s.target.value}"
