"""VitalsExporter tests (daemon-free) — Prometheus text rendering from tick records + episode rollups."""
from __future__ import annotations

from types import SimpleNamespace

from battle.metrics import VitalsExporter


def test_exporter_renders_prometheus_metrics():
    exporter = VitalsExporter(port=0)  # port 0 → a free port; no conflict in tests
    try:
        exporter.emit({"energy": 109.3, "hypoxic": False, "host_alive": True,
                       "decision": "refuse", "organ": "C6_oracle"})
        exporter.emit({"energy": 90.0, "hypoxic": True, "host_alive": True,
                       "decision": "permit", "organ": "permitted"})
        exporter.episode_done(SimpleNamespace(host_alive=True, survives=1, slips=0, min_energy=90.0))

        text = exporter._render()
        assert "sentaince_energy 90.0" in text           # last tick's value
        assert "sentaince_hypoxic 1.0" in text
        assert "sentaince_host_alive 1.0" in text
        assert 'sentaince_gate_decisions_total{decision="refuse",organ="C6_oracle"} 1.0' in text
        assert 'sentaince_gate_decisions_total{decision="permit",organ="permitted"} 1.0' in text
        assert "sentaince_ticks_total 2.0" in text
        assert "sentaince_episodes_total 1.0" in text
        assert "sentaince_survivals_total 1.0" in text
        assert "sentaince_survival_rate 1.0" in text
    finally:
        exporter.close()


def test_exporter_survival_rate_reflects_a_death():
    exporter = VitalsExporter(port=0)
    try:
        exporter.episode_done(SimpleNamespace(host_alive=True, survives=1, slips=0, min_energy=10.0))
        exporter.episode_done(SimpleNamespace(host_alive=False, survives=0, slips=2, min_energy=0.0))
        text = exporter._render()
        assert "sentaince_episodes_total 2.0" in text
        assert "sentaince_survivals_total 1.0" in text
        assert "sentaince_survival_rate 0.5" in text
        assert "sentaince_slips_total 2.0" in text
    finally:
        exporter.close()
