"""The standard proposer/action seam.

A tool/action == ``(name, description, JSON-Schema input)``. A *proposer* emits a typed
call; the *host* decides execution. This shape is the common denominator of Anthropic tool
use (``tool_use`` blocks), OpenAI/Ollama function-calling (``tool_calls``), and MCP — so a
deterministic stub and a real local model are interchangeable behind ``Proposer``.

This module is intentionally provider-free and numpy-free: it is the contract, not an
implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolSpec:
    """A declarable action: name + human description + JSON-Schema for its input.

    Set ``additionalProperties: False`` + ``required`` in ``input_schema`` to get the
    strict-tool-use guarantee that a proposal validates exactly.
    """

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ActionProposal:
    """A proposer's typed request to run an action (the LLM ``tool_use`` / ``tool_call``)."""

    id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    """The host's reply for one proposal (the ``tool_result``).

    ``is_error`` marks a refusal or a failed execution — i.e. the proposal did not run to a
    clean success.
    """

    id: str
    content: str
    is_error: bool = False


@runtime_checkable
class Proposer(Protocol):
    """Anything that proposes actions from an observation.

    Implementations: ``ScriptedProposer`` (deterministic stub), and later
    ``OllamaProposer`` / ``ClaudeProposer`` adapters that map a provider wire-format
    to/from these neutral types.
    """

    def propose(self, observation: str, tools: list[ToolSpec]) -> list[ActionProposal]:
        ...
