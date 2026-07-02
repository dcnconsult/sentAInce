"""Unit tests for the Class-Consolidation Gauge — offline merge-pass sizing (ADR-002).

OUT of the deterministic 99-lock. Run explicitly:

    python -m pytest exocortex/tests/test_consolidation_gauge.py
    python exocortex/tests/test_consolidation_gauge.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.gauge import consolidation_gauge as cg   # noqa: E402


def _mkstate(clusters: list, colonies: list) -> Path:
    root = Path(tempfile.mkdtemp(prefix="cg_repo_"))
    sd = root / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (sd / "cues.json").write_text(json.dumps({"n": 10, "df": {}, "clusters": clusters}), encoding="utf-8")
    for c in colonies:
        (sd / f"colony_{cg._safe(c['label'])}.json").write_text(json.dumps(c), encoding="utf-8")
    return root


def _cluster(label: str, tf: dict) -> dict:
    return {"id": 0, "label": label, "size": 1, "tf_sum": tf}


# ---- cosine handles sparse dicts and dense lists; mismatched types → 0 ----
def test_cos():
    assert abs(cg._cos({"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 1.0}) - 1.0) < 1e-9
    assert cg._cos({"a": 1.0}, {"b": 1.0}) == 0.0
    assert abs(cg._cos([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert cg._cos({"a": 1.0}, [1.0]) == 0.0


# ---- two near-duplicate STARVED classes pool over the splice bar → newly servable, BUILD-candidate ----
def test_merge_feeds_starved_tail():
    tf = {"run": 3.0, "battle": 2.0, "test": 2.0}
    root = _mkstate(
        [_cluster("run-battle#1", tf), _cluster("battle-run#2", dict(tf)), _cluster("battle-test#3", dict(tf)),
         _cluster("docs-write#4", {"write": 3.0, "doc": 2.0})],
        [{"label": "run-battle#1", "deposits": 2, "tau": {"a\tb": 1.0, "b\tc": 0.8}},
         {"label": "battle-run#2", "deposits": 2, "tau": {"b\tc": 0.5, "c\td": 0.4}},
         {"label": "battle-test#3", "deposits": 1, "tau": {"c\td": 0.3}},
         {"label": "docs-write#4", "deposits": 9, "tau": {"x\ty": 2.0}}])
    try:
        res = cg.run(root / ".claude" / "exocortex", thresholds=(0.9,))
        s = res["sweep"][0]
        assert s["merged_groups"] == 1
        assert s["newly_servable_members"] == 3        # all three starved members clear the pooled bar (5 ≥ 3)
        assert s["both_converged_merges"] == 0
        assert res["verdict"]["signal"] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- merging two ALREADY-CONVERGED classes is flagged as a muddle and blocks the BUILD verdict ----
def test_converged_muddle_blocks():
    tf = {"deploy": 3.0, "install": 2.0}
    root = _mkstate(
        [_cluster("deploy#1", tf), _cluster("install#2", dict(tf))],
        [{"label": "deploy#1", "deposits": 8, "tau": {"a\tb": 2.0}},
         {"label": "install#2", "deposits": 7, "tau": {"c\td": 2.0}}])
    try:
        res = cg.run(root / ".claude" / "exocortex", thresholds=(0.9,))
        assert res["sweep"][0]["both_converged_merges"] == 1
        assert res["verdict"]["signal"] is False       # a muddling merge is never a BUILD
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- dissimilar classes never merge at any threshold → PARK ----
def test_no_merge_park():
    root = _mkstate(
        [_cluster("alpha#1", {"alpha": 3.0}), _cluster("beta#2", {"beta": 3.0})],
        [{"label": "alpha#1", "deposits": 1, "tau": {}},
         {"label": "beta#2", "deposits": 1, "tau": {}}])
    try:
        res = cg.run(root / ".claude" / "exocortex", thresholds=(0.5, 0.9))
        assert all(s["merged_groups"] == 0 for s in res["sweep"])
        assert res["verdict"]["signal"] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- merged τ pools weights; dominant-route depth measured on the union ----
def test_dominant_depth_on_merge():
    assert cg._dominant_depth({"a\tb": 1.0, "b\tc": 0.5}) == 3
    assert cg._dominant_depth({}) == 0


# ---- determinism: same state → byte-identical result ----
def test_determinism():
    tf = {"x": 1.0, "y": 2.0}
    root = _mkstate([_cluster("x#1", tf), _cluster("y#2", dict(tf))],
                    [{"label": "x#1", "deposits": 1, "tau": {"a\tb": 1.0}},
                     {"label": "y#2", "deposits": 2, "tau": {"b\tc": 1.0}}])
    try:
        sd = root / ".claude" / "exocortex"
        assert json.dumps(cg.run(sd), sort_keys=True) == json.dumps(cg.run(sd), sort_keys=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- fail-open: empty state dir → coherent empty result ----
def test_empty_state():
    root = Path(tempfile.mkdtemp(prefix="cg_empty_"))
    sd = root / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    try:
        res = cg.run(sd)
        assert res["fragmentation"]["classes"] == 0
        assert res["verdict"]["signal"] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} consolidation gauge tests passed")
