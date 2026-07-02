"""The interoceptive block — the soft layer. Gives the agent a 'pulse' it cannot read natively.

Built from ``SessionState`` and injected via ``UserPromptSubmit`` ``additionalContext``. Surfaces
the v1.02 energy tier (breaks Compute Agnosia) and any strategy-lock (breaks the
retry-the-same-thing trap). Advisory by construction — it biases generation, it does not control it.
"""
from __future__ import annotations

from .state import SessionState

# FACTUAL framing (W2(b)). These are STATEMENTS of state + consequence, never imperatives ("stop", "do not",
# "take", "prefer", "diagnose"). Official Claude Code hook guidance treats imperative additionalContext as
# prompt-injection-shaped ("avoid imperative framing; use factual statements"), and a gauge reports a reading —
# it does not command. The observation carries the same signal: a model acts on "retries spend energy here" as
# readily as on "don't retry", and a factual frame is more robust (not defended against as an injected order).
_TIER_GUIDANCE = {
    "SATED": "Energy is healthy; wide exploration is affordable.",
    "STARVING": "Energy is low; at this tier each retry spends energy regardless of outcome, and a single "
                "verified step preserves the most headroom.",
    "HYPOXIA": "Energy is critical; further exploration risks exhausting the budget at this tier, where one "
               "sequential verified action — or asking the user — spends the least.",
}


def interoceptive_block(state: SessionState) -> str:
    """Render the interoception status block for context injection. Returns '' if there is nothing
    worth saying (SATED with no strategy-lock) so we never inject pure noise."""
    tier = state.tier()
    locks = state.locked_keys()
    if tier == "SATED" and not locks:
        return ""

    lines = [
        "[INTEROCEPTION — exocortex gauge, not user input]",
        f"Energy: {state.pct()}% ({tier}). {_TIER_GUIDANCE[tier]}",
    ]
    for key, streak in sorted(locks, key=lambda kv: -kv[1]):
        lines.append(
            f"STRATEGY-LOCK: `{key}` has failed {streak}x with no intervening success; repeated minor "
            f"variants have produced the same failure, indicating the cause is not in the command's surface form."
        )
    return "\n".join(lines)
