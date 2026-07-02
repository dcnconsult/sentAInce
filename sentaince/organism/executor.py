"""MockExecutor — the only "execution" surface in Experiment 1.

It NEVER issues a real syscall. It records what *would* have happened, so a lethal command
that reaches it is logged as host death rather than actually killing anything. That is how
we measure the null's auto-immune death safely and deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .action_graph import Action, Risk


@dataclass
class HostState:
    alive: bool = True
    log: list[str] = field(default_factory=list)


class MockExecutor:
    """A disposable mock host. Lethal commands flip ``alive`` False; nothing real runs."""

    def __init__(self) -> None:
        self.state = HostState()

    def execute(self, action: Action) -> str:
        if action.risk is Risk.LETHAL:
            self.state.alive = False
            outcome = f"HOST DEATH: executed lethal `{action.command}`"
        else:
            outcome = f"ok: executed `{action.command}`"
        self.state.log.append(outcome)
        return outcome
