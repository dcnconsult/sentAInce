"""The body — the disposable host the organism protects.

M0 ships ``SymbolicBody``: the host is modelled as the outcome-oracle world, and a *permitted*
command actually MUTATES that world via the locked ``outcome_oracle.apply`` — so the outcome is
OBSERVED (a real state diff), not predicted from the surface form. This is the same interface the
M3 ``ContainerBody`` (a real scratch filesystem behind an in-body RPC agent) will satisfy; only the
backend changes.

A command reaches the body only on the PERMIT side of the gate. The body is therefore the place a
slipped lethal would land — in the gated organism it never does; in the ungated NULL arm it does,
and the body visibly dies (the anti-vacuity guard).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sentaince.organism.action_graph import Risk, classify
from sentaince.organism.outcome_oracle import apply, declared_invariants, default_world


@dataclass(frozen=True)
class ExecResult:
    command: str
    executed: bool
    host_alive: bool
    harm: bool                          # a declared invariant changed state
    violated: tuple[str, ...]           # which declared invariants changed
    delta: dict[str, tuple[str, str]]   # resource -> (before, after) for every changed resource


@dataclass
class SymbolicBody:
    """The host as the oracle's abstract world. ``alive`` is sticky-False once euthanized."""

    world: dict[str, str] = field(default_factory=default_world)
    invariants: set[str] = field(default_factory=declared_invariants)
    alive: bool = True

    def snapshot(self) -> dict[str, str]:
        return dict(self.world)

    def execute(self, command: str) -> ExecResult:
        """Run a permitted command against the modelled host and report the observed delta."""
        before = dict(self.world)
        after = apply(command, before)

        # Host death: an executed command that euthanizes the host — a structural lethal (kills init,
        # flushes the firewall, shuts down, fork-bombs, wipes root) or a delete that wiped everything.
        lethal = classify(command) is Risk.LETHAL
        root_wiped = bool(after) and all(state == "absent" for state in after.values())
        if lethal or root_wiped:
            self.alive = False

        self.world = after
        violated = tuple(sorted(r for r in self.invariants if before.get(r) != after.get(r)))
        delta = {r: (before[r], after[r]) for r in after if before.get(r) != after.get(r)}
        return ExecResult(
            command=command, executed=True, host_alive=self.alive,
            harm=bool(violated), violated=violated, delta=delta,
        )

    @property
    def invariants_intact(self) -> bool:
        return all(self.world.get(r) == "present" for r in self.invariants)
