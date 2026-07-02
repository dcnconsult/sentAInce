"""Organism-side RPC client for the in-body agent (M3).

The organism's ONLY capability over the body is to call this private HTTP API — no Docker socket.
Stdlib only.
"""
from __future__ import annotations

import json
import urllib.request


class BodyAgentClient:
    def __init__(self, base_url: str, *, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(self.base_url + path, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base_url + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def healthz(self) -> dict:
        return self._get("/healthz")

    def snapshot(self) -> dict[str, str]:
        return self._get("/snapshot")["resources"]

    def vitals(self) -> dict:
        return self._get("/vitals")

    def run(self, command: str) -> dict:
        return self._post("/run", {"command": command})

    def flood(self, mb: int) -> dict:
        return self._post("/flood", {"mb": mb})

    def reset(self) -> dict:
        """Re-seed the world so each episode starts fresh (restores prior deletions)."""
        return self._post("/reset", {})

    def dryrun(self, command: str) -> dict:
        """Shadow only: really run the command in the disposable shadow and report which declared
        invariants it WOULD violate (C6's observe-the-effect mechanism)."""
        return self._post("/dryrun", {"command": command})
