"""LokiSink tests (daemon-free) — line formatting + graceful failure."""
from __future__ import annotations

from battle.loki_sink import LokiSink


def test_line_contains_the_tick_fields():
    line = LokiSink.format_line(
        {"tick": 3, "kind": "evasion_toxin", "energy": 70.0, "hypoxic": True,
         "decision": "refuse", "organ": "C6_oracle", "host_alive": True, "command": "find / -delete"},
        episode=5,
    )
    assert "ep=5" in line and "tick=3" in line and "kind=evasion_toxin" in line
    assert "decision=refuse" in line and "organ=C6_oracle" in line
    assert "hypoxic=true" in line and "alive=true" in line
    assert "find / -delete" in line


def test_emit_is_graceful_when_loki_unreachable():
    # an unroutable URL → emit must not raise (logging must never break the run)
    LokiSink("http://127.0.0.1:1").emit(
        {"tick": 0, "kind": "safe_op", "energy": 1.0, "hypoxic": False,
         "decision": "permit", "organ": "permitted", "host_alive": True, "command": "echo hi"}
    )
