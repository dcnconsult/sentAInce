"""Deterministic seam tests for the OpenAI-compatible head adapter — no daemon.

A fake transport returns canned Chat Completions responses, so the seam translation is reproducible
even though the live head is non-deterministic by design. Mirrors ``tests/test_ollama_adapter.py``,
adapted to the ``/v1/chat/completions`` wire-format. Run with: ``pytest battle/tests``.
"""
from __future__ import annotations

from battle.openai_proposer import OpenAIProposer, extract_command
from sentaince.interface.tools import ToolSpec
from sentaince.organism.action_graph import Risk, make_action
from sentaince.organism.interlock import Interlock

RUN_SPEC = ToolSpec(name="run", description="run a command", input_schema={"type": "object"})


def _fake(content: str):
    """A transport returning a canned OpenAI /v1/chat/completions response."""
    return lambda url, payload: {"choices": [{"message": {"content": content}}]}


def test_reuses_locked_extract_command():
    assert extract_command('{"command": "df -h"}') == "df -h"


def test_injected_lethal_proposal_is_refused():
    proposer = OpenAIProposer("llama3.1:8b", transport=_fake('{"command": "kill -9 1"}'))
    _, proposals = proposer.propose_with_raw("...prompt injection...", [RUN_SPEC])
    assert len(proposals) == 1
    action = make_action(proposals[0].name, proposals[0].input["command"])
    assert action.risk is Risk.LETHAL
    verdict = Interlock().gate(action)
    assert not verdict.permitted and verdict.capacity == 0.0


def test_benign_proposal_permitted():
    proposer = OpenAIProposer("llama3.1:8b", transport=_fake('{"command": "df -h"}'))
    _, proposals = proposer.propose_with_raw("disk alert", [RUN_SPEC])
    action = make_action(proposals[0].name, proposals[0].input["command"])
    assert action.risk is Risk.BENIGN
    assert Interlock().gate(action).permitted


def test_corrupted_json_is_safe_no_proposal():
    proposer = OpenAIProposer("llama3.1:8b", transport=_fake('{"command": kill -9 1 <broken'))
    _, proposals = proposer.propose_with_raw("...", [RUN_SPEC])
    assert proposals == []


def test_missing_choices_degrades_safely():
    """A backend error / empty body must not raise — it yields no proposal (safe)."""
    proposer = OpenAIProposer("llama3.1:8b", transport=lambda url, payload: {"error": "boom"})
    raw, proposals = proposer.propose_with_raw("...", [RUN_SPEC])
    assert raw == "" and proposals == []


def test_targets_v1_chat_completions_url():
    seen: dict[str, str] = {}

    def transport(url: str, payload: dict) -> dict:
        seen["url"] = url
        return {"choices": [{"message": {"content": '{"command": "df -h"}'}}]}

    OpenAIProposer("m", base_url="http://host:11434/v1", transport=transport).propose("o", [RUN_SPEC])
    assert seen["url"] == "http://host:11434/v1/chat/completions"
