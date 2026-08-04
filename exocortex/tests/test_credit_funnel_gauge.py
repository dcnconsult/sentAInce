"""Unit tests for the Credit-Funnel Gauge — where declarative crediting dies, per repo.

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]``). Run explicitly:

    python -m pytest exocortex/tests/test_credit_funnel_gauge.py
    python exocortex/tests/test_credit_funnel_gauge.py

Synthetic ``<root>/.claude/exocortex`` state dirs (audit.jsonl + colonies + wiki_cache + config), so every
funnel stage and verdict branch is exercised deterministically.
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

from exocortex.gauge import credit_funnel_gauge as cf   # noqa: E402


def _mkrepo(mode="live", vault="V") -> Path:
    root = Path(tempfile.mkdtemp(prefix="cf_repo_"))
    sd = root / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (root / "exocortex_config.json").write_text(json.dumps(
        {"declarative": {"mode": mode, "vault_path": str(root / vault), "ingest": "all"}}), encoding="utf-8")
    return root


def _audit(sd: Path, rows: list) -> None:
    (sd / "audit.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def _cons(injected=0, used=0) -> dict:
    r: dict = {"event": "PostToolUse", "tool": "Bash", "outcome": "ok"}
    if injected:
        r["wiki_injected"] = injected
    if used:
        r["wiki_used"] = used
    return r


def _cache(sd: Path, texts: list) -> None:
    nodes = [{"id": f"docs/n{i}.md#h{i}", "text": t, "heading_path": [f"H{i}"], "span": [0, 1],
              "links": [], "content_hash": str(i)} for i, t in enumerate(texts)]
    (sd / "wiki_cache.json").write_text(json.dumps({"signature": "s", "nodes": nodes}), encoding="utf-8")


# ---- stage-1 death: consequences but nothing ever spliced → INJECTION + cold-start diagnosis ----
def test_dies_at_injection_cold_start():
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        _audit(sd, [{"event": "UserPromptSubmit"}] + [_cons() for _ in range(5)])
        _cache(sd, ["run `pytest exocortex/tests` then `git add .`"] * 4)   # creditable vault
        res = cf.run(sd)
        v = res["verdict"]
        assert v["dies_at"].startswith("STAGE 1")
        assert "COLD-START" in v["note"]
        assert "proposer" in v["note"]                    # creditable vault → blocker named as proposer
        assert "BOOTSTRAP-DEAD" in res["proposer_liveness"]["structural_spreading"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- stage-2 death: spliced but never echoed → ECHO/USE ----
def test_dies_at_echo():
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        _audit(sd, [_cons(injected=3) for _ in range(4)])
        _cache(sd, ["pure prose with no salient tokens at all"] * 3)
        res = cf.run(sd)
        assert res["verdict"]["dies_at"].startswith("STAGE 2")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- full funnel: injected + used + note-anchored colony → FUNNEL LIVE ----
def test_funnel_live():
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        _audit(sd, [_cons(injected=3, used=1) for _ in range(4)])
        _cache(sd, ["`exocortex/colony.py` deposit"] * 2)
        (sd / "colony_x_1.json").write_text(json.dumps(
            {"label": "x#1", "deposits": 5, "tau": {"cue:x#1\tdocs/n0.md#h0": 1.5}}), encoding="utf-8")
        res = cf.run(sd)
        assert res["verdict"]["dies_at"].startswith("NONE")
        assert res["verdict"]["signal"] is True
        assert res["colony"]["note_anchored_classes"] == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- stage-0: organ not live → CONFIG (nothing downstream is blamed) ----
def test_config_off():
    root = _mkrepo(mode="off")
    sd = root / ".claude" / "exocortex"
    try:
        _audit(sd, [_cons() for _ in range(3)])
        res = cf.run(sd)
        assert res["verdict"]["dies_at"].startswith("STAGE 0")
        assert res["verdict"]["signal"] is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- vault census: prose-only nodes are structurally uncreditable (the ADR-006 asymmetry) ----
def test_vault_census_salience():
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        _cache(sd, ["`a/b.py` and `c-flag` here",         # 2+ salient → creditable at 2
                    "only plain english prose here",       # 0 salient
                    "one `path/x.py` token"])              # 1 salient
        v = cf.vault_census(sd, 2)
        assert v["nodes"] == 3
        assert v["creditable_at_min"] == 1
        assert v["creditable_at_1"] == 2
        assert v["lexical_vocab_size"] > 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- fail-open: an empty/missing state dir reports NO DATA, never crashes ----
def test_missing_everything():
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        res = cf.run(sd)
        assert res["verdict"]["dies_at"] in ("NO DATA",)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_multi_note_tail_counts_only_injected_segments():
    """The ≥2-note tail is the Hippocampus-bridge trigger and the number CLAIMS binds, so pin its
    DENOMINATOR: injected segments, not all consequences. A segment that was never injected cannot
    credit a note, and counting it would silently deflate the tail."""
    def cons(injected: int, used: int) -> dict:
        r = {"event": "PostToolUse", "tool": "Bash", "outcome": "ok"}
        if injected:
            r["wiki_injected"] = injected
        if used:
            r["wiki_used"] = used
        return r

    records = [
        cons(3, 2),      # injected, credits 2  -> in tail, ≥2
        cons(3, 4),      # injected, credits 4  -> in tail, ≥2
        cons(3, 1),      # injected, credits 1  -> in tail, not ≥2
        cons(3, 0),      # injected, credits 0  -> in tail, not ≥2
        cons(0, 0),      # NOT injected         -> excluded from the tail denominator entirely
    ]
    f = cf.audit_funnel(records)
    assert f["consequences"] == 5, f
    assert f["tail_n"] == 4, f            # the un-injected consequence is not in the denominator
    assert f["tail_ge2"] == 2, f
    assert f["tail_ge2_frac"] == 0.5, f
    assert f["tail_histogram"] == {"0": 1, "1": 1, "2": 1, "4": 1}, f


def test_multi_note_tail_is_zero_safe_on_an_empty_store():
    f = cf.audit_funnel([])
    assert f["tail_n"] == 0 and f["tail_ge2"] == 0 and f["tail_ge2_frac"] == 0.0, f


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} credit-funnel gauge tests passed")
