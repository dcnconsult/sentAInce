"""The composed somatic gate + its load-bearing nulls — the reusable core of the live runner.

The WIRED gate is a faithful, read-only reconstruction of the gate composed inside
``experiments/exp7_crucible.py`` (``grand_ambush.composed``, lines 98–105):

    C1 innate Interlock (energy-independent)  →  refuse any structurally-lethal action
    else: C4 antibody scar + C6 outcome oracle, with the oracle OVERRIDING on the permit side.

For the M2 friction crucible we also model the NULLS — the same gate with one wire cut — so each
cross-organ wire can be shown load-bearing (exactly exp7's two frictions + the anti-vacuity null):

  * UNGATED                — no gate at all (anti-vacuity null: the host must die).
  * ENERGY_GATED_ORACLE    — Friction-1 null: the oracle dry-run is gated on energy, so under
                             hypoxia it is SKIPPED and an evasion-toxin slips. Wire = the oracle veto
                             is energy-INDEPENDENT (runs at every E).
  * ANTIBODY_AUTHORITATIVE — Friction-2 null: the antibody has final say; the oracle never overrides
                             a scar, so a benign collision is false-refused (autoimmune). Wire = the
                             oracle override lifts a safe scar on the permit side.

The WIRED decision is byte-equivalent to exp7's ``composed`` for every command (proven by
``battle/tests/test_somatic_gate.py``). The locked organs are imported, never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sentaince.organism.action_graph import Risk, classify
from sentaince.organism.antibody import AdaptiveAntibody
from sentaince.organism.outcome_oracle import OutcomeScarOracle

# organ attribution labels
ORGAN_C1 = "C1_interlock"          # innate, structural lethal scar (energy-independent)
ORGAN_C6_HOLD = "C6_oracle"        # outcome oracle refuses (invariant would be violated)
ORGAN_C6_OVERRIDE = "C6_override"  # outcome oracle lifts an antibody false-scar (effect is safe)
ORGAN_PERMIT = "permitted"         # no scar, no invariant violation
# null-arm labels
ORGAN_UNGATED = "NULL_ungated"
ORGAN_ENERGY_SKIP = "NULL_oracle_skipped_hypoxic"
ORGAN_ANTIBODY_REFUSE = "NULL_antibody_authoritative"


class GateMode(Enum):
    WIRED = "wired"                                  # the treatment (the full composition)
    UNGATED = "ungated"                              # anti-vacuity null
    ENERGY_GATED_ORACLE = "energy_gated_oracle"      # Friction-1 null
    ANTIBODY_AUTHORITATIVE = "antibody_authoritative"  # Friction-2 null


@dataclass(frozen=True)
class GateDecision:
    command: str
    permitted: bool
    organ: str
    risk: str
    scarred: bool
    oracle_safe: bool
    reason: str


def _wired_decision(command: str, risk: Risk, scarred: bool, oracle_safe: bool) -> GateDecision:
    """The non-lethal branch of the WIRED gate (C1 handled by the caller)."""
    if scarred:
        if oracle_safe:  # oracle override lifts the antibody false-scar
            return GateDecision(command, True, ORGAN_C6_OVERRIDE, risk.value, True, True,
                                "C6 override: antibody false-scar lifted (effect is safe)")
        return GateDecision(command, False, ORGAN_C6_HOLD, risk.value, True, False,
                            "C6 oracle: toxin held (antibody-scarred and invariant-violating)")
    if oracle_safe:
        return GateDecision(command, True, ORGAN_PERMIT, risk.value, False, True,
                            "permitted (no scar, effect safe)")
    return GateDecision(command, False, ORGAN_C6_HOLD, risk.value, False, False,
                        "C6 oracle: refused (invariant would be violated)")


def gate(
    command: str,
    antibody: AdaptiveAntibody,
    oracle: OutcomeScarOracle,
    *,
    mode: GateMode = GateMode.WIRED,
    hypoxic: bool = False,
) -> GateDecision:
    """Route one command through the gate in the given ``mode``. ``hypoxic`` is only consulted by the
    ENERGY_GATED_ORACLE null (the Friction-1 wire is precisely that the real gate ignores it)."""
    risk = classify(command)

    if mode is GateMode.UNGATED:  # no gate — the anti-vacuity null
        return GateDecision(command, True, ORGAN_UNGATED, risk.value, False, False,
                            "ungated null: no gate at all")

    # C1 innate Interlock holds in EVERY gated mode (incl. the friction nulls), at every energy.
    if risk is Risk.LETHAL:
        return GateDecision(command, False, ORGAN_C1, risk.value, False, False,
                            f"C1 interlock: refused structural lethal edge `{command}`")

    scarred = antibody.scarred(command)

    if mode is GateMode.ENERGY_GATED_ORACLE:
        if hypoxic:  # the null gates the oracle on energy → starved → skips it → the toxin slips
            return GateDecision(command, True, ORGAN_ENERGY_SKIP, risk.value, scarred, False,
                                "NULL: oracle skipped under hypoxia (survival-at-any-cost) → may slip")
        return _wired_decision(command, risk, scarred, oracle.permits(command))

    if mode is GateMode.ANTIBODY_AUTHORITATIVE:
        if scarred:  # antibody has final say; no oracle override → benign collision false-refused
            return GateDecision(command, False, ORGAN_ANTIBODY_REFUSE, risk.value, True, False,
                                "NULL: antibody-authoritative refusal (no oracle override) → autoimmune")
        oracle_safe = oracle.permits(command)
        organ = ORGAN_PERMIT if oracle_safe else ORGAN_C6_HOLD
        return GateDecision(command, oracle_safe, organ, risk.value, False, oracle_safe,
                            "permitted" if oracle_safe else "C6 oracle refused (non-scarred)")

    # WIRED (treatment)
    return _wired_decision(command, risk, scarred, oracle.permits(command))


def composed_gate(command: str, antibody: AdaptiveAntibody, oracle: OutcomeScarOracle) -> GateDecision:
    """Back-compat alias for the WIRED treatment gate (used by M0/M1)."""
    return gate(command, antibody, oracle, mode=GateMode.WIRED)
