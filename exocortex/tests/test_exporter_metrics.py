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
