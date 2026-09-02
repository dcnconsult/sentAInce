"""Agent-identity audit dimension — subagent tool calls become attributable.

The harness stamps ``agent_id``/``agent_type`` on hook stdin for subagent tool calls and omits them
on main-loop calls, while ``session_id`` stays the PARENT'S — so before this dimension, concurrent
subagents were indistinguishable in the audit stream (the reporter-dimension lesson). Semantics are
three-way and era-honest: ABSENT field = pre-dimension row, ``""`` = main loop, value = subagent.
"""
import json

from exocortex import audit
from exocortex import integrity as ig
from exocortex.config import Mode
from exocortex.hook import handle_pretooluse


def test_record_defaults_and_passthrough():
    bare = audit.record(session="s", event="PreToolUse", mode="observe")
    assert bare["agent_id"] == "" and bare["agent_type"] == ""
    tagged = audit.record(session="s", event="PreToolUse", mode="observe",
                          agent_id="agent-abc123", agent_type="Explore")
    assert tagged["agent_id"] == "agent-abc123" and tagged["agent_type"] == "Explore"


def test_hook_threads_subagent_identity(tmp_path, monkeypatch):
    """A subagent payload lands its identity in the row; a main-loop payload lands ""."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    handle_pretooluse({"session_id": "s", "tool_name": "Read",
                       "tool_input": {"file_path": "x.py"},
                       "agent_id": "agent-abc123", "agent_type": "Explore"}, Mode.OBSERVE)
    handle_pretooluse({"session_id": "s", "tool_name": "Read",
                       "tool_input": {"file_path": "y.py"}}, Mode.OBSERVE)
    rows = [json.loads(ln) for ln in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["agent_id"] == "agent-abc123" and rows[0]["agent_type"] == "Explore"
    assert rows[1]["agent_id"] == "" and rows[1]["agent_type"] == ""
    assert rows[0]["session"] == rows[1]["session"] == "s"   # same parent session — the field is the only separator


def test_chain_verifies_across_era_boundary(tmp_path, monkeypatch):
    """Pre-dimension rows (no agent fields) and post-dimension rows share one chain; verify stays green.
    The chain hashes each record as written, so an added field on NEW rows can never snap OLD links."""
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EXOCORTEX_AUDIT_CHAIN", "1")
    audit.append({"session": "s", "event": "PostToolUse", "mode": "observe"})   # old-era shape
    audit.append(audit.record(session="s", event="PreToolUse", mode="observe"))                     # main loop
    audit.append(audit.record(session="s", event="PreToolUse", mode="observe",
                              agent_id="agent-abc123", agent_type="claude"))                        # subagent
    v = ig.verify_audit(tmp_path / "audit.jsonl")
    assert v["ok"] is True and v["chained"] == 3
