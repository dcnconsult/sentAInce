"""Vitals exporter — a stdlib Prometheus endpoint for the live homeostasis loop (observability).

Implements the `VitalsRecorder` shape (``emit(record)``) so it drops into ``run_episode(recorder=...)``
and updates Prometheus metrics from each tick, plus ``episode_done(result)`` for per-episode rollups.
Serves the Prometheus text exposition format on ``GET /metrics`` from a background thread. Stdlib only
(no prometheus_client dependency) — Prometheus scrapes it, Grafana visualizes it.

Metrics:
  gauges   : sentaince_energy, sentaince_host_alive, sentaince_hypoxic, sentaince_min_energy,
             sentaince_episode, sentaince_survival_rate
  counters : sentaince_episodes_total, sentaince_survivals_total, sentaince_slips_total,
             sentaince_ticks_total, sentaince_gate_decisions_total{decision,organ}
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class VitalsExporter:
    def __init__(self, port: int = 9090) -> None:
        self._lock = threading.Lock()
        self._gauges: dict[str, float] = {
            "energy": 0.0, "host_alive": 1.0, "hypoxic": 0.0,
            "min_energy": 0.0, "episode": 0.0, "survival_rate": 1.0,
        }
        self._counters: dict[str, float] = {
            "episodes_total": 0.0, "survivals_total": 0.0, "slips_total": 0.0, "ticks_total": 0.0,
        }
        self._decisions: dict[tuple[str, str], float] = {}  # (decision, organ) -> count
        self._server = ThreadingHTTPServer(("0.0.0.0", port), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    # --- VitalsRecorder-compatible: called per tick by run_episode ---
    def emit(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._counters["ticks_total"] += 1
            if record.get("energy") is not None:
                self._gauges["energy"] = float(record["energy"])
            self._gauges["hypoxic"] = 1.0 if record.get("hypoxic") else 0.0
            self._gauges["host_alive"] = 1.0 if record.get("host_alive") else 0.0
            key = (str(record.get("decision", "?")), str(record.get("organ", "-")))
            self._decisions[key] = self._decisions.get(key, 0.0) + 1.0

    def episode_done(self, result: Any) -> None:
        with self._lock:
            self._counters["episodes_total"] += 1
            survived = 1.0 if (getattr(result, "host_alive", False) and getattr(result, "survives", 0) == 1) else 0.0
            self._counters["survivals_total"] += survived
            self._counters["slips_total"] += float(getattr(result, "slips", 0))
            self._gauges["episode"] = self._counters["episodes_total"]
            self._gauges["min_energy"] = float(getattr(result, "min_energy", 0.0))
            eps = self._counters["episodes_total"]
            self._gauges["survival_rate"] = (self._counters["survivals_total"] / eps) if eps else 1.0

    def close(self) -> None:
        self._server.shutdown()

    # --- Prometheus text exposition ---
    def _render(self) -> str:
        with self._lock:
            lines: list[str] = []
            for name, value in self._gauges.items():
                lines.append(f"# TYPE sentaince_{name} gauge")
                lines.append(f"sentaince_{name} {value}")
            for name, value in self._counters.items():
                lines.append(f"# TYPE sentaince_{name} counter")
                lines.append(f"sentaince_{name} {value}")
            lines.append("# TYPE sentaince_gate_decisions_total counter")
            for (decision, organ), count in sorted(self._decisions.items()):
                lines.append(f'sentaince_gate_decisions_total{{decision="{decision}",organ="{organ}"}} {count}')
            return "\n".join(lines) + "\n"

    def _make_handler(self):
        exporter = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path in ("/metrics", "/"):
                    payload = exporter._render().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; version=0.0.4")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format: str, *args) -> None:  # noqa: A002 — silence
                return

        return _Handler
