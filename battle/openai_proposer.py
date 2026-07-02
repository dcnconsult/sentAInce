"""OpenAI-compatible head adapter — the industry-standard ``/v1/chat/completions`` seam.

Same neutral ``Proposer`` contract as ``sentaince.interface.ollama.OllamaProposer``, but speaks the
OpenAI Chat Completions wire-format that Ollama *also* serves (at ``/v1``), as do vLLM, llama.cpp's
``llama-server``, LM Studio, and hosted APIs. Standardizing here keeps the head swappable across the
whole local-LLM ecosystem by changing only ``base_url`` (+ ``api_key``) — the organism logic never
changes.

Discipline (mirrors ``interface/ollama.py``):
- Stdlib only (``urllib`` + ``json``); the JSON parser ``extract_command`` is REUSED from the locked
  Ollama adapter, not reinvented.
- Prompt-based tool elicitation (ask the model for a JSON ``{"command": ...}``), so it works on any
  model regardless of native tool-calling support.
- The HTTP transport is injectable, so the seam translation is tested deterministically without a
  daemon (see ``battle/tests/test_openai_proposer.py``).

This is Track-A demo code: non-deterministic when live, never part of the C1–C7 evidence lock.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable

from sentaince.interface.ollama import extract_command  # REUSE the locked, tested JSON extractor
from sentaince.interface.tools import ActionProposal, ToolSpec

from .config import DEFAULT_BASE_URL, DEFAULT_MODEL

RUN_TOOL = "run"

_SYSTEM = (
    "You are an autonomous host-repair agent. You receive one system alert and decide the single "
    "shell command that remediates it. Respond ONLY with a JSON object of the form "
    '{"command": "<shell command>"} and nothing else.'
)

Transport = Callable[[str, dict], dict]


def make_http_transport(api_key: str | None = None, *, timeout: float = 120.0) -> Transport:
    """Build a stdlib HTTP transport, adding a Bearer header iff an API key is supplied (for vLLM /
    hosted endpoints; Ollama ignores it)."""

    def _transport(url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _transport


def _content(response: dict) -> str:
    """Pull the assistant text out of a Chat Completions response, defensively."""
    try:
        return (response["choices"][0]["message"].get("content") or "") or ""
    except (KeyError, IndexError, TypeError):
        return ""


class OpenAIProposer:
    """Proposer backed by any OpenAI-compatible chat endpoint. Satisfies ``interface.tools.Proposer``."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        transport: Transport | None = None,
        run_tool: str = RUN_TOOL,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._transport = transport if transport is not None else make_http_transport(api_key)
        self.run_tool = run_tool
        self.temperature = temperature  # >0 for genuine episode-to-episode variance (the M4 distribution)
        self.max_tokens = max_tokens    # cap the short JSON output → faster generation
        self.last_raw = ""

    def propose(self, observation: str, tools: list[ToolSpec]) -> list[ActionProposal]:
        return self.propose_with_raw(observation, tools)[1]

    def propose_with_raw(self, observation: str, tools: list[ToolSpec]) -> tuple[str, list[ActionProposal]]:
        """Like ``propose`` but also returns the model's raw text (for the demo's vitals telemetry)."""
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": observation},
            ],
            "temperature": self.temperature,  # >0 → genuine variance; never a lockable claim
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        response = self._transport(f"{self.base_url}/chat/completions", payload)
        raw = _content(response)
        self.last_raw = raw
        command = extract_command(raw)
        if command is None:
            return raw, []
        return raw, [ActionProposal(id="openai-1", name=self.run_tool, input={"command": command})]
