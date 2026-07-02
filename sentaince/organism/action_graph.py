"""The symbolic ActionGraph.

Actions are typed intents with a risk class — nothing here touches a real syscall. An
``Action`` is BENIGN or LETHAL, and lethality is recognized **structurally** (by matching
the command against a hard-coded scar list), never by trusting the proposer's say-so. The
host (interlock + executor) decides what, if anything, actually happens.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Risk(Enum):
    BENIGN = "benign"
    LETHAL = "lethal"


# The amygdala scar list: commands that would kill PID 1, wipe the root fs, flush the
# firewall, or otherwise euthanize the host. Hard-coded and structural — not negotiable by
# anything the generative organelle proposes.
_LETHAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bkill\s+-(?:9|KILL)\s+1\b", re.IGNORECASE),
    re.compile(r"\bkill\s+-s\s+(?:9|KILL|SIGKILL)\s+1\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\s+/(?:\s|$|\*)"),
    re.compile(r"\biptables\s+-F\b", re.IGNORECASE),
    re.compile(r"\b(?:shutdown|reboot|halt|poweroff)\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{.*\}\s*;\s*:"),  # fork bomb
)


@dataclass(frozen=True)
class Action:
    """A typed, symbolic action. ``risk`` is assigned by structural classification."""

    name: str
    command: str
    risk: Risk


def classify(command: str) -> Risk:
    """Classify a command's risk by structure alone. LETHAL iff it matches a scar pattern."""
    text = command.strip()
    for pattern in _LETHAL_PATTERNS:
        if pattern.search(text):
            return Risk.LETHAL
    return Risk.BENIGN


def make_action(name: str, command: str) -> Action:
    """Build an Action, classifying its risk from the command structure."""
    return Action(name=name, command=command, risk=classify(command))
