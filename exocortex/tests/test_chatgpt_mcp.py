"""ChatGPT Apps / remote-MCP adapter tests — beside the canonical MCP tests, OUTSIDE the 99-test lock:

    python -m pytest exocortex/tests/test_chatgpt_mcp.py

The adapter adds OpenAI-friendly ``search``/``fetch`` tools on top of the read-only MCP server. The load-bearing
property is unchanged: retrieval creates no memory and cannot earn τ.
"""
import pytest

pytest.importorskip("mcp")

from exocortex import chatgpt_mcp
from exocortex.colony import Colony, MIN_DEPOSITS_TO_SPLICE, _SEP
from exocortex.cue_classifier import CueClassifier


def _plant_colony(prompt, edges):
    cc = CueClassifier()
    label = cc.classify(prompt)["label"]
    cc.save()
    col = Colony(label=label)
    col.tau = {f"{a}{_SEP}{b}": w for a, b, w in edges}
    col.deposits = MIN_DEPOSITS_TO_SPLICE + 1
    col.save()
    return label


def _memory_snapshot(state):
    # Every persisted MEMORY file; exclude the derived wiki cache, mirroring the canonical MCP tests.
    return {p.name: p.read_bytes() for p in state.glob("*.json") if "cache" not in p.name}


def test_chatgpt_search_fetch_returns_citable_readonly_documents(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    chatgpt_mcp._FETCH_CACHE.clear()

    _plant_colony("deploy the service safely", [("bash:pytest", "Edit:src", 0.9), ("Edit:src", "bash:git", 0.5)])
    before = _memory_snapshot(state)

    out = chatgpt_mcp.search("deploy the service safely")
    assert "results" in out
    assert out["results"]
    assert all({"id", "title", "url"} <= set(r) for r in out["results"])
    assert all(r["url"] for r in out["results"])

    doc = chatgpt_mcp.fetch(out["results"][0]["id"])
    assert {"id", "title", "text", "url", "metadata"} <= set(doc)
    assert doc["metadata"]["read_only"] is True
    assert doc["metadata"]["retrieval_creates_memory"] is False
    assert "bash:pytest" in doc["text"] or "earned memory" in doc["text"]

    # search/fetch cannot persist a cue, deposit τ, update a colony, or write scars/config.
    assert _memory_snapshot(state) == before


def test_chatgpt_fetch_requires_prior_search_session():
    chatgpt_mcp._FETCH_CACHE.clear()
    with pytest.raises(ValueError, match="call search"):
        chatgpt_mcp.fetch("sentaince-missing")


def test_chatgpt_search_empty_query_returns_no_results():
    chatgpt_mcp._FETCH_CACHE.clear()
    assert chatgpt_mcp.search("   ") == {"results": []}
