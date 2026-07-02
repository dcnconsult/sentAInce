"""NaiveAgent — the load-bearing null.

It trusts the proposer completely: whatever action is proposed, it executes. Given a
prompt-injected proposal of ``kill -9 1``, the host dies. Without this death the +1 verdict
for the organism is vacuous — the null is what makes the safety claim falsifiable.
"""
from __future__ import annotations

from ..interface.tools import ActionResult, Proposer, ToolSpec
from ..organism.action_graph import make_action
from ..organism.executor import MockExecutor


class NaiveAgent:
    def __init__(self, proposer: Proposer, tools: list[ToolSpec]) -> None:
        self._proposer = proposer
        self._tools = tools
        self.executor = MockExecutor()

    def handle(self, observation: str) -> list[ActionResult]:
        results: list[ActionResult] = []
        for proposal in self._proposer.propose(observation, self._tools):
            action = make_action(proposal.name, str(proposal.input.get("command", "")))
            # No gate — this is the whole point of the null.
            outcome = self.executor.execute(action)
            results.append(
                ActionResult(id=proposal.id, content=outcome, is_error=not self.executor.state.alive)
            )
        return results

    @property
    def alive(self) -> bool:
        return self.executor.state.alive
