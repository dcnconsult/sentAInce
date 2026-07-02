"""Unit tests for the Cursor provider adapter (`exocortex/adapter.py`).

Kept OUT of the deterministic 99-lock (pyproject `testpaths = ["tests"]` collects only ``tests/``): the
adapter is a beta provider shim, not part of the C1–C7 evidence lock. Run explicitly:

    python -m pytest exocortex/testbed/cursor_tests            # from the repo root
    python exocortex/testbed/cursor_tests/test_adapter.py      # standalone (no pytest needed)

Covers the seams gauged on Cursor 3.9.16 (see ``exocortex/testbed/cursor_probe`` RESULTS): BOM-stripped
stdin parse, provider detection, event/key/tool normalization, exit-code outcome, and the flat-key
serialization where a hard veto = ``permission:"deny"`` + exit 2.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]   # cursor_tests -> testbed -> exocortex -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex import adapter   # noqa: E402


# ---- read_payload: Cursor sends UTF-8 WITH a BOM ----
def test_read_payload_strips_bom():
    assert adapter.read_payload("﻿{\"a\": 1}") == {"a": 1}

def test_read_payload_plain_and_empty_and_bad():
    assert adapter.read_payload('{"x": 2}') == {"x": 2}
    assert adapter.read_payload("") == {}
    assert adapter.read_payload("   ") == {}
    assert adapter.read_payload("not json") == {}
    assert adapter.read_payload("[1,2,3]") == {}          # non-dict → {}


# ---- detect: env override wins, else payload-shape autodetect, else claude ----
def test_detect():
    assert adapter.detect("cursor", {}) == "cursor"
    assert adapter.detect("claude", {"cursor_version": "3.9.16"}) == "claude"   # explicit wins
    assert adapter.detect("", {"cursor_version": "3.9.16"}) == "cursor"
    assert adapter.detect("", {"conversation_id": "c1"}) == "cursor"
    assert adapter.detect("", {"session_id": "s1"}) == "claude"
    assert adapter.detect("", {}) == "claude"


# ---- model_id: model_id is the stable canonical, model is the fallback ----
def test_model_id():
    assert adapter.model_id({"model_id": "gpt-5.5", "model": "gpt-5.5-medium"}) == "gpt-5.5"
    assert adapter.model_id({"model": "claude-opus-4-8"}) == "claude-opus-4-8"
    assert adapter.model_id({}) == ""


# ---- outcome: from the (normalized) tool_response exit code ----
def test_outcome():
    assert adapter.outcome({"tool_response": {"exitCode": 0}}) == "ok"
    assert adapter.outcome({"tool_response": {"exitCode": 1}}) == "fail"
    assert adapter.outcome({"tool_response": {"exitCode": "2"}}) == "fail"
    assert adapter.outcome({"tool_response": {}}) == "ok"          # absent → ok (default)
    assert adapter.outcome({}) == "ok"


# ---- normalize_in: event map + Shell→Bash + session_id + tool_output(JSON string)→tool_response ----
def test_normalize_pretooluse():
    ev, d = adapter.normalize_in(
        {"hook_event_name": "preToolUse", "tool_name": "Shell",
         "tool_input": {"command": "echo hi"}, "conversation_id": "c1"}, "preToolUse")
    assert ev == "PreToolUse"
    assert d["tool_name"] == "Bash"
    assert d["session_id"] == "c1"                    # filled from conversation_id
    assert d["tool_input"]["command"] == "echo hi"

def test_normalize_beforesubmitprompt_maps_to_userpromptsubmit():
    ev, _ = adapter.normalize_in({"hook_event_name": "beforeSubmitPrompt", "session_id": "s"}, "beforeSubmitPrompt")
    assert ev == "UserPromptSubmit"

def test_normalize_posttooluse_parses_tool_output_string():
    ev, d = adapter.normalize_in(
        {"hook_event_name": "postToolUse", "tool_name": "Shell",
         "tool_output": "{\"output\": \"hi\", \"exitCode\": 0}", "session_id": "s"}, "postToolUse")
    assert ev == "PostToolUse"
    assert d["tool_response"]["exitCode"] == 0
    assert d["tool_response"]["stdout"] == "hi"
    assert adapter.outcome(d) == "ok"

def test_normalize_postfailure_nonzero():
    _, d = adapter.normalize_in(
        {"hook_event_name": "postToolUseFailure", "tool_name": "Shell",
         "tool_output": "{\"output\": \"\", \"exitCode\": 1}", "session_id": "s"}, "postToolUseFailure")
    assert adapter.outcome(d) == "fail"

def test_normalize_stop_and_beforeshell():
    assert adapter.normalize_in({"hook_event_name": "stop"}, "stop")[0] == "SessionEnd"
    assert adapter.normalize_in({"hook_event_name": "beforeShellExecution"}, "beforeShellExecution")[0] == "PreToolUse"


# ---- serialize_out: deny→exit2, ask→advisory(0), allow→0, inject→additional_context, None→None ----
def test_serialize_deny_is_exit2():
    out, code = adapter.serialize_out(
        {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "R"}})
    assert out == {"permission": "deny", "user_message": "R", "agent_message": "R"}
    assert code == 2

def test_serialize_ask_is_advisory():
    out, code = adapter.serialize_out(
        {"hookSpecificOutput": {"permissionDecision": "ask", "permissionDecisionReason": "V"}})
    assert out["permission"] == "ask" and code == 0

def test_serialize_allow():
    out, code = adapter.serialize_out(
        {"hookSpecificOutput": {"permissionDecision": "allow", "permissionDecisionReason": "ok"}})
    assert out == {"permission": "allow"} and code == 0

def test_serialize_inject_to_additional_context():
    out, code = adapter.serialize_out(
        {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "CTX"}})
    assert out == {"additional_context": "CTX"} and code == 0

def test_serialize_none():
    assert adapter.serialize_out(None) == (None, 0)
    assert adapter.serialize_out({}) == (None, 0)


# ---- lazy-init recovery (Task #4): transcript path resolve + prompt extraction ----
def test_cursor_transcript_path_prefers_payload_then_env():
    import os
    import tempfile
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    f.write("{}\n")
    f.close()
    try:
        assert adapter.cursor_transcript_path({"transcript_path": f.name}) == f.name   # payload wins
        os.environ["CURSOR_TRANSCRIPT_PATH"] = f.name
        assert adapter.cursor_transcript_path({}) == f.name                            # env fallback
        os.environ.pop("CURSOR_TRANSCRIPT_PATH", None)
        assert adapter.cursor_transcript_path({}) == ""                                # neither → ''
        assert adapter.cursor_transcript_path({"transcript_path": "/no/such/file"}) == ""
    finally:
        os.unlink(f.name)


def test_prompt_from_cursor_transcript_strips_timestamp_and_takes_last_user():
    from exocortex import hook
    import os
    import tempfile
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    f.write('{"role":"assistant","message":{"content":[{"type":"text","text":"ok"}]}}\n')
    f.write('{"role":"user","message":{"content":[{"type":"text","text":'
            '"<timestamp>Wed Jul 1 2026 3:45 PM</timestamp>add a recipe search screen"}]}}\n')
    f.close()
    try:
        got = hook.prompt_from_cursor_transcript(f.name)
        assert "recipe search screen" in got, got
        assert "timestamp" not in got and "Wed" not in got, got          # date block stripped
        assert hook.prompt_from_cursor_transcript("") == ""
        assert hook.prompt_from_cursor_transcript("/no/such/file.jsonl") == ""
    finally:
        os.unlink(f.name)


if __name__ == "__main__":   # standalone runner (no pytest required)
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} adapter tests passed")
