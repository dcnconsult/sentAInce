"""Exporter metric-collection tests (the testbed's Prometheus surface). OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_exporter_metrics.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.testbed.exporter import metrics as M                     # noqa: E402


def _mkstate(tmp_path: Path, colony: dict) -> Path:
    sd = tmp_path / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (sd / f"colony_{colony['label']}.json").write_text(json.dumps(colony), encoding="utf-8")
    (sd / "audit.jsonl").write_text("", encoding="utf-8")
    return sd


def test_consolidations_metric_surfaces_the_sleep_counter(tmp_path):
    """Q1 observability reaches the dashboard: a store stamped by the circadian sleep exports
    ``exocortex_colony_consolidations`` (per class) + the repo's last-consolidated epoch — the
    'Sleep' row of the story skin reads these."""
    sd = _mkstate(tmp_path, {"label": "q1", "tau": {"a\tb": 1.0}, "deposits": 3,
                             "consolidations": 2, "last_consolidated": 1750000000.0})
    p = M.Prom({"repo": "t"})
    M.collect_repo(p, sd, {})
    text = "\n".join(p.lines)
    assert 'exocortex_colony_consolidations{repo="t",class="q1"} 2' in text
    assert 'exocortex_colony_last_consolidated_timestamp{repo="t"} 1750000000' in text


def test_never_consolidated_store_exports_zero(tmp_path):
    """Pre-Q1 stores (no consolidations field) read as 0 — no crash, no missing series."""
    sd = _mkstate(tmp_path, {"label": "old", "tau": {"a\tb": 1.0}, "deposits": 1})
    p = M.Prom({"repo": "t"})
    M.collect_repo(p, sd, {})
    text = "\n".join(p.lines)
    assert 'exocortex_colony_consolidations{repo="t",class="old"} 0' in text
    assert 'exocortex_colony_last_consolidated_timestamp{repo="t"} 0' in text


# ----------------------------------------------------------------------------- gauge-board TTL memo (2026-10-12)
def _repos_for(tmp_path: Path) -> list:
    sd = _mkstate(tmp_path, {"label": "c", "tau": {}, "deposits": 0})
    return [{"name": "r1", "state_dir": sd, "genome": {}}]


def test_gauges_are_computed_once_within_the_ttl(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(M, "_compute_gauges", lambda repos: calls.append(1) or {"per_repo": {}, "signals": {}})
    monkeypatch.setenv("EXOCORTEX_EXPORTER_GAUGE_TTL_S", "300")
    M._GAUGE_CACHE.clear()
    repos = _repos_for(tmp_path)
    first = M.render(repos)
    (key, (ts, res)), = M._GAUGE_CACHE.items()
    M._GAUGE_CACHE[key] = (ts - 42.0, res)              # age the entry: still inside the 300 s TTL
    second = M.render(repos)
    assert len(calls) == 1
    assert "exocortex_gauge_board_age_seconds 0.0" in first
    assert "exocortex_gauge_board_age_seconds 42." in second       # labelled as cached, not live


def test_ttl_zero_recomputes_every_scrape(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(M, "_compute_gauges", lambda repos: calls.append(1) or {"per_repo": {}, "signals": {}})
    monkeypatch.setenv("EXOCORTEX_EXPORTER_GAUGE_TTL_S", "0")
    M._GAUGE_CACHE.clear()
    repos = _repos_for(tmp_path)
    M.render(repos)
    M.render(repos)
    assert len(calls) == 2 and M._GAUGE_CACHE == {}


def test_a_different_repo_set_is_never_served_from_cache(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(M, "_compute_gauges", lambda repos: calls.append(1) or {"per_repo": {}, "signals": {}})
    monkeypatch.setenv("EXOCORTEX_EXPORTER_GAUGE_TTL_S", "300")
    M._GAUGE_CACHE.clear()
    M.render(_repos_for(tmp_path / "a"))
    M.render(_repos_for(tmp_path / "b"))
    assert len(calls) == 2


def test_a_malformed_ttl_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("EXOCORTEX_EXPORTER_GAUGE_TTL_S", "five minutes")
    assert M._gauge_ttl_s() == M._GAUGE_TTL_DEFAULT_S
