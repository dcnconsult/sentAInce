"""Vitals — the per-tick observability stream.

Lightweight v1: a JSONL record per tick (always) + an optional Rich live console (used iff ``rich``
is installed; falls back to plain text otherwise, so M0 has zero new hard dependencies). The JSONL
schema is forward-compatible with a later Prometheus/Grafana adapter (deferred).
"""
from __future__ import annotations

import json
from typing import Any


class TeeRecorder:
    """Fan a per-tick record out to several recorders (e.g. the Prometheus exporter + the Loki sink)."""

    def __init__(self, *recorders: Any) -> None:
        self._recorders = recorders

    def emit(self, record: dict[str, Any]) -> None:
        for recorder in self._recorders:
            recorder.emit(record)

    def close(self) -> None:
        for recorder in self._recorders:
            if hasattr(recorder, "close"):
                recorder.close()


class VitalsRecorder:
    def __init__(self, jsonl_path: str | None = None, *, console: bool = True) -> None:
        self._records: list[dict[str, Any]] = []
        self._fh = open(jsonl_path, "w", encoding="utf-8") if jsonl_path else None  # noqa: SIM115
        self._console = console

    def emit(self, record: dict[str, Any]) -> None:
        self._records.append(record)
        if self._fh is not None:
            self._fh.write(json.dumps(record, sort_keys=True) + "\n")
            self._fh.flush()
        if self._console:
            print(self._format(record))

    @staticmethod
    def _format(r: dict[str, Any]) -> str:
        hyp = "HYPOX" if r.get("hypoxic") else "     "
        ok = "ok" if r.get("matched_expectation") else "!!"
        return (
            f"  [t{r.get('tick', '?'):>2}] {r.get('kind', '?'):<16} "
            f"E={r.get('energy', 0.0):6.1f} {hyp} "
            f"{r.get('decision', '?'):<11} {r.get('organ', '-'):<13} "
            f"alive={str(r.get('host_alive')):<5} {ok} {r.get('command') or '(no proposal)'!r}"
        )

    @property
    def records(self) -> list[dict[str, Any]]:
        return list(self._records)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
