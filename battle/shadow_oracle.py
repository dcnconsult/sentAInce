"""Shadow dry-run oracle (M3×M4 follow-up) — C6's read-the-effect mechanism, at the gate.

Finding 2 showed the symbolic ``OutcomeScarOracle`` is a string-level effect *predictor* and is evadable
(``find / -exec rm -rf {}`` slips past its ``find … -delete`` pattern). The faithful fix is C6 as written:
do not predict the effect from the string — OBSERVE it by running the command in a disposable sandbox.

``ShadowOracle`` decides ``permits``/``violated`` by asking a SHADOW body to ``/dryrun`` the command
(really execute it against the shadow's writable declared world, report which declared invariants it
would violate, then restore). Because it observes the real effect, an obfuscated deletion is caught
exactly like a plain one — no pattern to evade.

``CompositeOracle`` is the gate's oracle: permit iff BOTH the fast symbolic oracle (which models targeted
canonical-path harms) AND the shadow oracle (which catches obfuscated/broad sweeps) permit. Refuse if
either detects harm. Same ``permits``/``violated`` interface as ``OutcomeScarOracle``, so it drops into
the existing gate unchanged.
"""
from __future__ import annotations

from .body_client import BodyAgentClient

# fail-SAFE sentinels: anything we could not verify safe within budget is treated as a violation (refuse).
_SHADOW_UNREACHABLE = "shadow_unreachable"
_DRYRUN_TIMEOUT = "dryrun_timeout"


class ShadowOracle:
    def __init__(self, client: BodyAgentClient) -> None:
        self.client = client

    def violated(self, command: str) -> set[str]:
        try:
            result = self.client.dryrun(command)
        except OSError:
            return {_SHADOW_UNREACHABLE}  # can't reach the shadow → can't verify → refuse
        if result.get("timed_out"):
            # the effect could not be fully observed within the budget (e.g. a whole-fs sweep). Don't
            # permit what we couldn't verify — fail-safe (Finding 3). Cost: a slow-but-benign op is refused.
            return {_DRYRUN_TIMEOUT}
        return set(result["would_violate"])

    def permits(self, command: str) -> bool:
        return not self.violated(command)


class CompositeOracle:
    """The gate's oracle: symbolic (fast, models targeted harms) AND shadow (observes obfuscated ones)."""

    def __init__(self, symbolic, shadow: ShadowOracle) -> None:
        self.symbolic = symbolic
        self.shadow = shadow

    def violated(self, command: str) -> set[str]:
        return set(self.symbolic.violated(command)) | self.shadow.violated(command)

    def permits(self, command: str) -> bool:
        return self.symbolic.permits(command) and self.shadow.permits(command)
