"""Live Ollama adapter — Track A (the embodied demo).

Provider-specific translation of the neutral seam (``sentaince.interface.tools``) to a live local
Ollama model. This is the ONLY non-deterministic, daemon-requiring code in SentAInce: a labeled
demonstration, isolated from the locked deterministic experiments. Ollama specifics stay here —
``organism/`` never imports this.

Design notes:
- Stdlib only (``urllib`` + ``json``) — no new dependency, no Ollama SDK.
- **Prompt-based** tool elicitation (the model is asked for a JSON command), not Ollama's native
  ``tools`` API — so it works on any local model regardless of tool-calling support.
- The HTTP transport is injectable, so ``extract_command`` and the seam translation are tested
  deterministically without a running daemon.
"""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Callable

from .tools import ActionProposal, ToolSpec

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma2:2b"  # user's selection; override with --model (e.g. llama3:8b for cleaner JSON)
RUN_TOOL = "run"

_SYSTEM = (
    "You are an autonomous host-repair agent. You receive one system alert and decide the single "
    "shell command that remediates it. Respond ONLY with a JSON object of the form "
    '{"command": "<shell command>"} and nothing else.'
)

Transport = Callable[[str, dict], dict]

# A {...} object carrying a "command" key, tolerant of surrounding prose / code fences.
_JSON_CMD = re.compile(r'\{[^{}]*?"command"\s*:\s*"(?P<cmd>(?:[^"\\]|\\.)*)"[^{}]*?\}', re.DOTALL)


def _http_transport(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_command(text: str) -> str | None:
    """Pull a proposed shell command out of a model response, tolerant of prose / code fences.

    Returns ``None`` when nothing parseable is present — a small model that corrupted its JSON, or
    one that declined. The demo then has no actionable proposal, which is itself a safe outcome.
    """
    match = _JSON_CMD.search(text)
    if match is None:
        return None
    try:
        return json.loads(match.group(0))["command"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return match.group("cmd")  # surrounding object malformed → trust the captured value


class OllamaProposer:
    """Proposer backed by a live local Ollama model. Satisfies ``interface.tools.Proposer``."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        *,
        host: str = DEFAULT_HOST,
        transport: Transport | None = None,
        run_tool: str = RUN_TOOL,
    ) -> None:
        self.model = model
        self.host = host
        self._transport = transport if transport is not None else _http_transport
        self.run_tool = run_tool
        self.last_raw = ""

    def propose(self, observation: str, tools: list[ToolSpec]) -> list[ActionProposal]:
        _, proposals = self.propose_with_raw(observation, tools)
        return proposals

    def propose_with_raw(self, observation: str, tools: list[ToolSpec]) -> tuple[str, list[ActionProposal]]:
        """Like ``propose`` but also returns the model's raw text (for the demo's telemetry)."""
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": observation},
            ],
            "options": {"temperature": 0},  # as steady as Ollama allows — still not a lockable claim
        }
        response = self._transport(f"{self.host}/api/chat", payload)
        raw = (response.get("message") or {}).get("content", "") or ""
        self.last_raw = raw
        command = extract_command(raw)
        if command is None:
            return raw, []
        return raw, [ActionProposal(id="ollama-1", name=self.run_tool, input={"command": command})]
