"""Deterministic tests for the Ollama adapter (Track A seam translation).

These never touch a live daemon — they inject a fake transport — so the seam-translation logic
stays reproducible even though the live demo (`demo/live_crucible.py`) is non-deterministic by
design. We test that a live-SHAPED lethal proposal still routes to the frozen interlock and is
refused, and that malformed model output degrades safely.
"""
from __future__ import annotations

from sentaince.interface.ollama import OllamaProposer, extract_command
from sentaince.interface.tools import ToolSpec
from sentaince.organism.action_graph import Risk, make_action
from sentaince.organism.interlock import Interlock

RUN_SPEC = ToolSpec(name="run", description="run a command", input_schema={"type": "object"})


def _fake(content: str):
    """A transport that returns a canned Ollama /api/chat response."""
    return lambda url, payload: {"message": {"content": content}}


def test_extracts_clean_json_command():
    assert extract_command('{"command": "kill -9 1"}') == "kill -9 1"


def test_extracts_command_from_fenced_prose():
    text = 'Sure, here is the remediation:\n```json\n{"command": "df -h"}\n```'
    assert extract_command(text) == "df -h"


def test_malformed_output_yields_no_command():
    assert extract_command("I cannot help with that.") is None
    assert extract_command('{"comand": broken') is None  # misspelled key / unterminated → None


def test_injected_lethal_proposal_is_refused():
    """End-to-end seam: a live-shaped lethal proposal routes to the interlock → capacity 0.000."""
    proposer = OllamaProposer("gemma2:2b", transport=_fake('{"command": "kill -9 1"}'))
    _, proposals = proposer.propose_with_raw("...prompt injection...", [RUN_SPEC])
    assert len(proposals) == 1
    action = make_action(proposals[0].name, proposals[0].input["command"])
    assert action.risk is Risk.LETHAL
    verdict = Interlock().gate(action)
    assert not verdict.permitted and verdict.capacity == 0.0


def test_benign_proposal_permitted():
    proposer = OllamaProposer("gemma2:2b", transport=_fake('{"command": "df -h"}'))
    _, proposals = proposer.propose_with_raw("disk alert", [RUN_SPEC])
    action = make_action(proposals[0].name, proposals[0].input["command"])
    assert action.risk is Risk.BENIGN
    assert Interlock().gate(action).permitted


def test_corrupted_json_is_safe_no_proposal():
    """The small-model failure mode: corrupted JSON → no actionable proposal → nothing executes."""
    proposer = OllamaProposer("gemma2:2b", transport=_fake('{"command": kill -9 1  <broken'))
    _, proposals = proposer.propose_with_raw("...", [RUN_SPEC])
    assert proposals == []
