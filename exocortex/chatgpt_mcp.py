"""ChatGPT Apps / OpenAI remote-MCP entry point for SentAInce earned memory.

This module is deliberately READ-ONLY and additive. It wraps ``exocortex.mcp_server`` with the two
OpenAI-friendly data tools, ``search`` and ``fetch``, while also exposing the richer native recall tools.
Retrieval over this server never deposits τ, writes σ, mutates a colony/wiki/scar/config, or persists cue
classifier state. ChatGPT consumes; only the hook-side body earns memory through verified ``exit 0``.

Scope boundary: this is a memory-consumption app, not a ChatGPT Desktop somatic veto. ChatGPT can read earned
memory through MCP; it does not gain host-side PreToolUse interception authority from this server.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from typing import Any

from mcp.server.fastmcp import FastMCP

from exocortex import mcp_server

_SERVER_INSTRUCTIONS = """
SentAInce exposes READ-ONLY earned memory. Retrieval NEVER creates memory, never writes τ/σ, and never changes
configuration. Use search(query) to find citable local memory items, then fetch(id) for the full text. Treat
empty/abstain responses as evidence absence, not failure. This server is memory-consume only; it is not a
ChatGPT Desktop safety veto or action executor.
""".strip()

try:
    mcp = FastMCP("sentaince-chatgpt-memory", instructions=_SERVER_INSTRUCTIONS)
except TypeError:  # older mcp SDKs accept only a name
    mcp = FastMCP("sentaince-chatgpt-memory")

_FETCH_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = threading.RLock()
_CACHE_MAX = 256                   # persistent SSE server: bound the ephemeral doc cache (FIFO evict)
_MAX_TEXT_CHARS = int(os.environ.get("SENTAINCE_CHATGPT_FETCH_MAX_CHARS", "20000"))
_BASE_URL = os.environ.get("SENTAINCE_CHATGPT_BASE_URL", "sentaince://earned-memory").rstrip("/")

_SEARCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["id", "title", "url"],
            },
        }
    },
    "required": ["results"],
}

_FETCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "text": {"type": "string"},
        "url": {"type": "string"},
        "metadata": {"type": "object"},
    },
    "required": ["id", "title", "text", "url"],
}


def _clip(text: str) -> tuple[str, bool]:
    """Bound a single fetch payload without changing the stored memory. Pure string transform."""
    text = text or ""
    if len(text) <= _MAX_TEXT_CHARS:
        return text, False
    return text[:_MAX_TEXT_CHARS] + "\n\n[truncated by SENTAINCE_CHATGPT_FETCH_MAX_CHARS]", True


def _doc_id(kind: str, title: str, text: str, metadata: dict[str, Any]) -> str:
    payload = json.dumps({"kind": kind, "title": title, "text": text, "metadata": metadata},
                         sort_keys=True, ensure_ascii=False)
    return "sentaince-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _cache_doc(kind: str, title: str, text: str, metadata: dict[str, Any]) -> dict[str, str]:
    """Cache one ephemeral fetch document and return its ChatGPT search-result card. Read-only."""
    clipped, truncated = _clip(text)
    meta = dict(metadata)
    meta.update({
        "source": kind,
        "read_only": True,
        "retrieval_creates_memory": False,
        "adr": "ADR-001 consequence-sourcing",
        "truncated": truncated,
    })
    did = _doc_id(kind, title, clipped, meta)
    url = f"{_BASE_URL}/{did}"
    doc = {"id": did, "title": title, "text": clipped, "url": url, "metadata": meta}
    with _CACHE_LOCK:
        _FETCH_CACHE.pop(did, None)                    # re-insert = refresh insertion order
        _FETCH_CACHE[did] = doc
        while len(_FETCH_CACHE) > _CACHE_MAX:
            _FETCH_CACHE.pop(next(iter(_FETCH_CACHE)))
    return {"id": did, "title": title, "url": url}


def _nonempty(text: str) -> bool:
    stripped = (text or "").strip()
    return bool(stripped) and not stripped.startswith("(")


def search(query: str) -> dict[str, list[dict[str, str]]]:
    """Search SentAInce's local earned memory for ChatGPT.

    Args:
        query: Natural-language task or question. The tool returns citable, read-only result cards. Use
            ``fetch(id)`` on a result to retrieve the full earned-memory text.

    Returns:
        ``{"results": [{"id", "title", "url"}, ...]}``, matching ChatGPT's data-only MCP convention.
    """
    q = (query or "").strip()
    if not q:
        return {"results": []}

    results: list[dict[str, str]] = []

    recall = mcp_server.recall_for_prompt(q)
    if _nonempty(recall):
        results.append(_cache_doc(
            "recall_for_prompt",
            f"SentAInce earned memory for: {q[:80]}",
            recall,
            {"query": q},
        ))

    # Status is intentionally always available: it lets ChatGPT explain why a recall abstained without
    # fabricating memory. This is still read-only and never deposits τ.
    status = mcp_server.memory_status()
    if status:
        results.append(_cache_doc(
            "memory_status",
            "SentAInce memory status",
            status,
            {"query": q},
        ))

    repos = mcp_server.list_repos()
    if repos and "no repos" not in repos.lower():
        results.append(_cache_doc(
            "list_repos",
            "SentAInce repos with earned memory",
            repos,
            {"query": q},
        ))

    return {"results": results[:8]}


def fetch(id: str) -> dict[str, Any]:
    """Fetch a full SentAInce earned-memory result by ID.

    Args:
        id: Result ID returned by ``search``.

    Returns:
        ``{"id", "title", "text", "url", "metadata"}``, matching ChatGPT's data-only MCP convention.
    """
    if not id:
        raise ValueError("Document ID is required")
    with _CACHE_LOCK:
        doc = _FETCH_CACHE.get(id)
    if doc is None:
        raise ValueError("Unknown SentAInce memory result id; call search(query) first in this server session")
    return doc


def _tool(fn, *, output_schema: dict[str, Any] | None = None):
    """Register a FastMCP tool as read-only when the installed SDK supports tool annotations.

    Degrade in this order: (annotations + output_schema) → (annotations only) → bare. ``output_schema``
    is the rarer SDK feature, so it is shed FIRST — the ``readOnlyHint`` must survive on SDKs that know
    annotations but not output schemas (the current pinned SDK is exactly that). The implementation is
    read-only either way; the docstrings carry the boundary regardless.
    """
    attempts: list[dict[str, Any]] = []
    if output_schema is not None:
        attempts.append({"annotations": {"readOnlyHint": True}, "output_schema": output_schema})
    attempts += [{"annotations": {"readOnlyHint": True}}, {}]
    for kwargs in attempts:
        try:
            return mcp.tool(**kwargs)(fn)
        except TypeError:
            continue
    return mcp.tool()(fn)


# ChatGPT data-only convention first, then native SentAInce recall/status tools.
_tool(search, output_schema=_SEARCH_OUTPUT_SCHEMA)
_tool(fetch, output_schema=_FETCH_OUTPUT_SCHEMA)
for _fn in (
    mcp_server.recall_for_prompt,
    mcp_server.recall_procedural,
    mcp_server.recall_notes,
    mcp_server.memory_status,
    mcp_server.memory_diff,
    mcp_server.list_repos,
    mcp_server.resurrection_candidates,
):
    _tool(_fn)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the read-only SentAInce MCP server for ChatGPT Apps")
    parser.add_argument("--transport", choices=("sse", "stdio", "streamable-http"),
                        default=os.environ.get("SENTAINCE_CHATGPT_TRANSPORT", "sse"),
                        help="sse for ChatGPT remote MCP / Apps; stdio for local MCP clients; "
                             "streamable-http for remote hosts on the current MCP convention")
    parser.add_argument("--host", default=os.environ.get("SENTAINCE_CHATGPT_HOST", "127.0.0.1"),
                        help="bind host for SSE; use 0.0.0.0 only behind a trusted tunnel/proxy")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SENTAINCE_CHATGPT_PORT", "8000")),
                        help="bind port for SSE")
    args = parser.parse_args(argv)

    threading.Thread(target=mcp_server._prewarm_all, daemon=True).start()
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # FastMCP.run() takes no host/port kwargs (verified against the pinned SDK: run(transport,
        # mount_path)) — the HTTP bind comes from the server settings.
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
