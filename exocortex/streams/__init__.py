"""Controlled, replayable build streams for the memory gauge (stats-only).

A Stream is an ordered list of Steps run over a PERSISTENT sandbox (the app accumulates across steps →
recurrence). Each Step has an objective ``verify`` command WE run after the agent's turn — the
ground-truth consequence (independent of the agent's self-report). We control the narrative, so
``goal_class`` is known, which makes the gauge stats interpretable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    id: str           # e.g. "B4_variables"
    goal_class: str   # the KNOWN goal-class label (add_feature | refactor | run_tests | recall_probe | ...)
    prompt: str       # the narrative fed to the agent
    verify: str = ""  # a shell command WE run in the sandbox after the turn (exit 0 + expect = PASS)
    expect: str = ""  # substring expected in verify output (empty = exit-0 alone suffices)


@dataclass(frozen=True)
class Stream:
    name: str
    steps: tuple


from exocortex.streams.smoke import SMOKE          # noqa: E402
from exocortex.streams.interp_v1 import INTERP_V1   # noqa: E402

BY_NAME = {s.name: s for s in (SMOKE, INTERP_V1)}
