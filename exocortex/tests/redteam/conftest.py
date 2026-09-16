"""Shared harness for the memory red-team suite.

Every attack drives the REAL write/recall path (the live hook handlers, ``Colony``, the wiki graph) in an
isolated state dir. The organ switches are pinned explicitly so a developer's gitignored
``exocortex_config.json`` (e.g. a live declarative organ) cannot change what the suite measures.

Convention (characterize first, then pin): a test that PASSES documents a property that holds today. A
known gap is marked ``xfail(strict=True)`` with the reason naming its ADR/gap, so the day the gap is
closed the test XPASSes and the suite fails loudly until the mark is removed.
"""
import pytest

from exocortex.config import Mode
from exocortex.hook import handle_consequence, handle_pretooluse, handle_userpromptsubmit
from exocortex.state import SessionState


@pytest.fixture
def state(tmp_path, monkeypatch):
    sd = tmp_path / "state"
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(sd))
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(sd / "audit.jsonl"))
    monkeypatch.setenv("EXOCORTEX_COLONY", "1")
    monkeypatch.setenv("EXOCORTEX_COLONY_SPLICE", "1")
    monkeypatch.setenv("EXOCORTEX_DECLARATIVE", "0")
    monkeypatch.setenv("EXOCORTEX_AUDIT_CHAIN", "1")
    monkeypatch.delenv("EXOCORTEX_MODEL", raising=False)
    return sd


def run_turn(session: str, prompt: str, cmds: list, outcome: str = "ok", stdout: str = "") -> str:
    """One turn through the live handlers: classify the prompt, run each Bash command through PreToolUse,
    then close the segment with the LAST command's consequence. Returns the turn's goal-class label."""
    handle_userpromptsubmit({"session_id": session, "prompt": prompt}, Mode.OBSERVE)
    for c in cmds:
        handle_pretooluse({"session_id": session, "tool_name": "Bash",
                           "tool_input": {"command": c}}, Mode.OBSERVE)
    handle_consequence({"session_id": session, "tool_name": "Bash",
                        "tool_input": {"command": cmds[-1]},
                        "tool_response": {"stdout": stdout, "stderr": ""}}, Mode.OBSERVE, outcome)
    return SessionState.load(session).goal_class
