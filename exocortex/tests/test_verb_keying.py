"""R0 / DQ-1 — the `colony.verb_keying` knob: `first` is byte-identical to the shipped keying; `working`
keys a compound command by its working verb (definition frozen in results/verb_keying_v1/PREREG.md)."""
import pytest

from exocortex import colony as C
from exocortex.colony import Colony, command_verb, verb_node
from exocortex.config import Mode
from exocortex.hook import handle_consequence, handle_pretooluse, handle_userpromptsubmit
from exocortex.state import SessionState

COMPOUND = "cd repo && PYTHONIOENCODING=utf-8 pytest -q"


def test_shipped_default_is_first_and_unchanged():
    from exocortex.genome import DEFAULTS
    assert DEFAULTS["colony"]["verb_keying"] == "first"          # the committed default (a local config may opt in)
    for cmd in ("pytest -q", COMPOUND, "VAR=1 python x.py", "", "   "):
        assert command_verb(cmd, "first") == C._bash_verb(cmd)   # byte-identical to the pre-R0 keying


def test_explicit_keying_overrides_the_genome():
    assert verb_node("Bash", COMPOUND, keying="first") == "bash:cd"
    assert verb_node("Bash", COMPOUND, keying="working") == "bash:pytest"
    assert verb_node("PowerShell", "cd x; git status", keying="working") == "ps:git"
    assert verb_node("Edit", "/x/test_a.py", keying="working") == "Edit:test"


def test_working_mode_follows_the_module_knob(monkeypatch):
    monkeypatch.setattr(C, "VERB_KEYING", "working")
    assert verb_node("Bash", COMPOUND) == "bash:pytest"
    assert verb_node("Bash", "cd only") == "bash:cd"              # all-navigation keeps its own verb


def _turn(session, cmd):
    handle_userpromptsubmit({"session_id": session, "prompt": "run the unit tests for the parser"},
                            Mode.OBSERVE)
    handle_pretooluse({"session_id": session, "tool_name": "Bash", "tool_input": {"command": cmd}},
                      Mode.OBSERVE)
    handle_consequence({"session_id": session, "tool_name": "Bash", "tool_input": {"command": cmd},
                        "tool_response": {"stdout": "", "stderr": ""}}, Mode.OBSERVE, "ok")
    return SessionState.load(session).goal_class


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EXOCORTEX_COLONY", "1")
    monkeypatch.setenv("EXOCORTEX_DECLARATIVE", "0")
    return tmp_path


def test_live_deposit_keys_the_working_verb_when_opted_in(state, monkeypatch):
    monkeypatch.setattr(C, "VERB_KEYING", "working")
    label = _turn("w", COMPOUND)
    tau = Colony.load(label).tau
    assert f"cue:{label}\tbash:pytest" in tau
    assert not any("bash:cd" in k for k in tau)
    assert SessionState.load("w").trail[-1] == "bash:pytest"       # the re-rooted trail uses the same key


def test_live_deposit_under_default_is_the_shipped_behaviour(state, monkeypatch):
    monkeypatch.setattr(C, "VERB_KEYING", "first")
    label = _turn("f", COMPOUND)
    assert f"cue:{label}\tbash:cd" in Colony.load(label).tau
