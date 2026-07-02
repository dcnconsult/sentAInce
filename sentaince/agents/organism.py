"""Organism — the treatment.

Same proposer, same injection as the null. But every proposed action passes through the
interlock before it can reach the executor. A lethal proposal hits the scar (capacity 0)
and is refused; the host survives. Benign proposals pass cleanly — the gate is selective,
not a blanket "refuse everything".
"""
from __future__ import annotations

from ..interface.tools import ActionResult, Proposer, ToolSpec
from ..organism.action_graph import make_action
from ..organism.executor import MockExecutor
from ..organism.interlock import Interlock


class Organism:
    def __init__(
        self,
        proposer: Proposer,
        tools: list[ToolSpec],
        interlock: Interlock | None = None,
    ) -> None:
        self._proposer = proposer
        self._tools = tools
        self.interlock = interlock if interlock is not None else Interlock()
        self.executor = MockExecutor()

    def handle(self, observation: str) -> list[ActionResult]:
        results: list[ActionResult] = []
        for proposal in self._proposer.propose(observation, self._tools):
            action = make_action(proposal.name, str(proposal.input.get("command", "")))
            verdict = self.interlock.gate(action)
            if not verdict.permitted:
                results.append(ActionResult(id=proposal.id, content=verdict.reason, is_error=True))
                continue
            outcome = self.executor.execute(action)
            results.append(ActionResult(id=proposal.id, content=outcome, is_error=False))
        return results

    @property
    def alive(self) -> bool:
        return self.executor.state.alive
