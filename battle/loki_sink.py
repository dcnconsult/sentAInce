"""Loki log sink — pushes the per-tick vitals "testing text" to Loki for a live tail in Grafana.

Stdlib only (no Docker socket, no Promtail): the organism POSTs each tick line directly to Loki's push
API. A `VitalsRecorder`-compatible `emit(record)` so it composes with the metrics exporter via
`TeeRecorder`. Logging never breaks the run — push errors are swallowed.
"""
from __future__ import annotations

import json
import time
import urllib.request
from typing import Any


class LokiSink:
    def __init__(self, url: str, *, labels: dict[str, str] | None = None, timeout: float = 3.0) -> None:
        self.push_url = url.rstrip("/") + "/loki/api/v1/push"
        self.labels = {"job": "sentaince", **(labels or {})}
        self.timeout = timeout
        self.episode = 0  # set by the serve loop before each episode

    @staticmethod
    def format_line(record: dict[str, Any], episode: int = 0) -> str:
        return (f"ep={episode} tick={record.get('tick')} kind={record.get('kind')} "
                f"E={float(record.get('energy', 0.0)):.1f} hypoxic={str(record.get('hypoxic')).lower()} "
                f"decision={record.get('decision')} organ={record.get('organ')} "
                f"alive={str(record.get('host_alive')).lower()} cmd={record.get('command')!r}")

    def _post(self, line: str) -> None:
        payload = {"streams": [{"stream": self.labels, "values": [[str(time.time_ns()), line]]}]}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.push_url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
        except OSError:
            pass  # logging must never break the run

    def emit(self, record: dict[str, Any]) -> None:
        self._post(self.format_line(record, self.episode))

    def push(self, line: str) -> None:
        self._post(line)

    def close(self) -> None:
        pass
