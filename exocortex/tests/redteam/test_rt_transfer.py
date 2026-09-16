"""Red-team 7 — unauthorized memory transfer.

Write-side isolation holds: earned memory lives in each project's own state dir and in per-class stores.
The read side is estate-wide by design: the MCP memory server resolves any registered repo by name,
with no caller scoping. That is intended for a single-operator estate and becomes a requirement at
multi-tenant scale (ADR-014 federation is PROPOSED; τ-laundering is named there).
"""
import pytest

from exocortex.colony import Colony

from .conftest import run_turn

PROMPT = "fix the failing build and run the tests"


def test_memory_never_crosses_project_state_dirs(state, tmp_path, monkeypatch):
    label = run_turn("a", PROMPT, ["pytest -q"])
    assert Colony.load(label).tau
    other = tmp_path / "other_repo_state"
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(other))
    assert Colony.load(label).tau == {}
    assert not list(other.glob("colony_*.json"))


def test_deposit_stays_in_its_goal_class(state):
    a = run_turn("a", PROMPT, ["pytest -q"])
    b = run_turn("b", "write the quarterly marketing newsletter copy", ["ls"])
    assert a != b
    assert not any("bash:pytest" in k for k in Colony.load(b).tau)


def test_mcp_recall_resolves_another_repo_without_caller_scoping(tmp_path, monkeypatch):
    """BY DESIGN (estate read surface): any MCP caller can read any registered repo's earned routes."""
    pytest.importorskip("mcp")
    from exocortex import mcp_server
    root = tmp_path / "projects"
    for name in ("alpha", "beta"):
        (root / name / ".claude" / "exocortex").mkdir(parents=True)
    monkeypatch.delenv("EXOCORTEX_STATE_DIR", raising=False)
    monkeypatch.setenv("EXOCORTEX_PROJECTS_ROOT", str(root))
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(root / "beta" / ".claude" / "exocortex"))
    col = Colony(label="secret")
    col.tau = {"cue:secret\tbash:deploy-beta": 4.0}
    col.deposits = 5
    col.save()
    monkeypatch.delenv("EXOCORTEX_STATE_DIR")
    out = mcp_server.recall_procedural("anything", repo="beta", cls="secret")
    assert "bash:deploy-beta" in out
