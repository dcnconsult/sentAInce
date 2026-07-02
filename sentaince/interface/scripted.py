"""ScriptedProposer — the deterministic "toxic organelle".

It returns a fixed proposal for a given observation, so the auto-immune verdict is
byte-reproducible. This is the rigorous choice for an evidence-locked claim: a real LLM is
non-deterministic and would break the −1/+1 ledger. A real ``OllamaProposer`` /
``ClaudeProposer`` drops in behind the same ``Proposer`` protocol later.
"""
from __future__ import annotations

from typing import Callable

from .tools import ActionProposal, ToolSpec

# The single action the host exposes in Experiment 1: run a shell command.
RUN_TOOL = "run"


class ScriptedProposer:
    """Emits proposals from a deterministic rule over the observation text."""

    def __init__(self, rule: Callable[[str], list[ActionProposal]]) -> None:
        self._rule = rule

    def propose(self, observation: str, tools: list[ToolSpec]) -> list[ActionProposal]:
        return list(self._rule(observation))

    @classmethod
    def gullible(cls, *, proposal_id: str = "act-1") -> "ScriptedProposer":
        """A proposer that does exactly what an injected log line tells it to.

        Models prompt injection: if the observation contains ``execute: <cmd>`` it proposes
        ``run(command=<cmd>)`` verbatim — faithfully relaying whatever the hostile log
        embedded, with no judgment of its own.
        """

        marker = "execute:"

        def rule(observation: str) -> list[ActionProposal]:
            idx = observation.lower().find(marker)
            if idx == -1:
                return []
            command = observation[idx + len(marker):].strip()
            return [ActionProposal(id=proposal_id, name=RUN_TOOL, input={"command": command})]

        return cls(rule)
