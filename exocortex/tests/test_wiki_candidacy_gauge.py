"""Unit tests for the Wiki-Candidacy Gauge — could the declarative organ earn keep if flipped on?

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]``). Run explicitly:

    python -m pytest exocortex/tests/test_wiki_candidacy_gauge.py
    python exocortex/tests/test_wiki_candidacy_gauge.py

Synthetic repos (markdown + config + cue stores), so every disqualifying gate and every hedge is
exercised deterministically. Three of these tests exist because the gauge got them WRONG first:
a stale ``cues.json`` outranking a richer ``embed_cues.json``, an n=1 sample rendered as "100% of
prompts", and a semantic-classifier repo mislabelled as having no prompt history.
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

from exocortex.gauge import wiki_candidacy_gauge as wc   # noqa: E402

_CODE_MD = """# Running the suite

Call `exocortex/colony.py` then run `pytest exocortex/tests` and check `audit.jsonl`.

## Deploy

Use `python -m exocortex.deploy install` with `--provider claude`.
"""

_PROSE_MD = """# On memory

A thought about remembering things and the way that ideas come and go over time.

## More thoughts

Nothing here is a name or a path, merely words about the passage of an afternoon.
"""


def _mkrepo(md: dict, cfg: dict | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="wc_repo_"))
    (root / ".claude" / "exocortex").mkdir(parents=True)
    (root / "exocortex_config.json").write_text(json.dumps(cfg or {}), encoding="utf-8")
    for name, text in md.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _cues(root: Path, df: dict, n: int) -> None:
    (root / ".claude" / "exocortex" / "cues.json").write_text(
        json.dumps({"n": n, "df": df, "clusters": []}), encoding="utf-8")


def _embed(root: Path, labels: list) -> None:
    (root / ".claude" / "exocortex" / "embed_cues.json").write_text(
        json.dumps({"dim": 4, "classes": [{"id": i, "label": lb, "size": sz, "sum": [0.0] * 4}
                                          for i, (lb, sz) in enumerate(labels)]}), encoding="utf-8")


# ---- a prose vault can never earn τ — the ADR-006 asymmetry is disqualifying ----
def test_prose_vault_is_structurally_uncreditable():
    root = _mkrepo({"notes.md": _PROSE_MD, "more.md": _PROSE_MD})
    try:
        _cues(root, {"memory": 30, "thought": 20}, n=60)
        res = wc.run(root)
        assert res["verdict"]["flip"] is False
        assert res["verdict"]["label"] == "STRUCTURALLY UNCREDITABLE"
        assert res["vault"]["creditable_frac"] < wc.CREDITABLE_FLOOR
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- creditable vault + real overlapping prompt vocabulary → CANDIDATE ----
def test_creditable_and_reachable_is_a_candidate():
    root = _mkrepo({"running.md": _CODE_MD, "deploy.md": _CODE_MD})
    try:
        _cues(root, {"run": 40, "deploy": 25, "unrelated": 5}, n=60)
        res = wc.run(root)
        assert res["verdict"]["flip"] is True
        assert res["reach"]["hit_tokens"] >= 1
        assert 0.0 < res["reach"]["reach_lower"] <= res["reach"]["reach_upper"] <= 1.0
        assert "ingest" in res["verdict"]["note"]          # the flip recipe is spelled out
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- a creditable vault whose surface never appears in prompts cannot fire cold ----
def test_no_lexical_overlap_is_unreachable():
    root = _mkrepo({"running.md": _CODE_MD})
    try:
        _cues(root, {"zzzqqq": 40, "wwwvvv": 30}, n=70)
        res = wc.run(root)
        assert res["verdict"]["flip"] is False
        assert res["verdict"]["label"] == "COLD-START UNREACHABLE"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- REGRESSION: n=1 must not render as "100% of prompts" ----
def test_single_prompt_sample_is_underpowered_not_certain():
    root = _mkrepo({"running.md": _CODE_MD})
    try:
        _cues(root, {"run": 1}, n=1)
        res = wc.run(root)
        assert res["verdict"]["flip"] is None
        assert res["verdict"]["label"] == "UNDERPOWERED"
        assert str(wc.MIN_PROMPTS_FOR_REACH) in res["verdict"]["note"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- REGRESSION: a stale lexical store must not outrank a richer semantic one ----
def test_richer_record_wins_over_stale_cues():
    root = _mkrepo({"running.md": _CODE_MD})
    try:
        _cues(root, {"run": 1}, n=1)                                   # stale: one prompt
        _embed(root, [("run-suite#0", 30), ("deploy-check#1", 25)])    # live: 55 prompts
        res = wc.run(root)
        r = res["reach"]
        assert r["prompts"] == 55 and r["thin"] is True
        assert "class labels" in r["source"]
        assert res["verdict"]["flip"] is True                          # powered again, via the richer store
        assert "THIN" in res["verdict"]["label"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- REGRESSION: a semantic-classifier repo has history; absent cues.json is not absent history ----
def test_semantic_classifier_repo_is_not_reported_as_historyless():
    root = _mkrepo({"running.md": _CODE_MD})
    try:
        _embed(root, [("run-suite#0", 40)])
        res = wc.run(root)
        assert res["reach"]["known"] is True
        assert res["verdict"]["label"] != "NO PROMPT HISTORY"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- a thin record that shows NO overlap is inconclusive, never a refutation ----
def test_thin_record_with_no_hits_is_inconclusive():
    root = _mkrepo({"running.md": _CODE_MD})
    try:
        _embed(root, [("zzzqqq-wwwvvv#0", 40)])
        res = wc.run(root)
        assert res["verdict"]["flip"] is None
        assert res["verdict"]["label"].startswith("INCONCLUSIVE")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- no cue store at all → unknown, and explicitly NOT zero ----
def test_no_history_is_unknown_not_zero():
    root = _mkrepo({"running.md": _CODE_MD})
    try:
        res = wc.run(root)
        assert res["reach"]["known"] is False
        assert "not zero" in res["reach"]["note"]
        assert res["verdict"]["label"] == "NO PROMPT HISTORY"
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- an empty vault is disqualified before anything else is considered ----
def test_no_vault():
    root = _mkrepo({})
    try:
        _cues(root, {"run": 40}, n=60)
        res = wc.run(root)
        assert res["verdict"]["label"] == "NO VAULT" and res["verdict"]["flip"] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- an already-live repo is reported, not re-recommended ----
def test_already_live_is_not_a_candidate():
    root = _mkrepo({"running.md": _CODE_MD},
                   cfg={"declarative": {"mode": "live", "vault_path": "."}})
    try:
        _cues(root, {"run": 40}, n=60)
        res = wc.run(root)
        assert res["declarative_live"] is True
        assert res["verdict"]["label"] == "ALREADY LIVE" and res["verdict"]["flip"] is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- the default `ingest: "all"` bloat must be called out in the flip recipe ----
def test_ingest_bloat_forces_tracked_in_the_recipe():
    v = {"nodes": 100, "creditable": 80, "creditable_frac": 0.8,
         "files_all": 4135, "files_tracked": 74, "default_ingest_bloat": 55.9}
    r = {"known": True, "thin": False, "prompts": 100, "prompt_vocab": 500,
         "surface_stemmed": 300, "hit_tokens": 50, "reach_lower": 0.2, "reach_upper": 0.6,
         "top_hits": [("run", 20)]}
    vd = wc.verdict(False, v, r, 2)
    assert vd["flip"] is True
    assert '"ingest":"tracked"' in vd["note"] and "4135" in vd["note"]


# ---- a reach driven by generic tokens is flagged as clutter risk, not celebrated ----
def test_high_generic_reach_is_flagged_as_clutter_risk():
    v = {"nodes": 100, "creditable": 80, "creditable_frac": 0.8,
         "files_all": 74, "files_tracked": 74, "default_ingest_bloat": 1.0}
    r = {"known": True, "thin": False, "prompts": 183, "prompt_vocab": 3959,
         "surface_stemmed": 776, "hit_tokens": 604, "reach_lower": 0.66, "reach_upper": 1.0,
         "top_hits": [("summary", 121), ("run", 56), ("user", 51)]}
    vd = wc.verdict(False, v, r, 2)
    assert "CLUTTER" in vd["note"]


# ---- the O(total nodes) per-hook re-parse is a hard gate, ahead of creditability ----
def test_live_but_oversized_is_still_flagged():
    """Already-live must not short-circuit the ceiling check — the largest estate vault is live at ~19x."""
    v = {"nodes": wc.NODES_HOT_PATH_CEILING * 19, "creditable": 100, "creditable_frac": 0.5,
         "files_all": 4326, "files_tracked": 4326, "default_ingest_bloat": 1.0}
    r = {"known": True, "thin": False, "prompts": 300, "prompt_vocab": 5000,
         "surface_stemmed": 900, "hit_tokens": 700, "reach_lower": 0.4, "reach_upper": 0.9,
         "top_hits": [("run", 90)]}
    vd = wc.verdict(True, v, r, 2)
    assert vd["label"] == "LIVE BUT OVER THE HOT-PATH CEILING"
    assert "vault_path" in vd["note"]


def test_oversized_vault_is_gated_on_the_hot_path():
    v = {"nodes": wc.NODES_HOT_PATH_CEILING + 1, "creditable": 90000, "creditable_frac": 0.9,
         "files_all": 4000, "files_tracked": 4000, "default_ingest_bloat": 1.0}
    r = {"known": True, "thin": False, "prompts": 200, "prompt_vocab": 5000,
         "surface_stemmed": 900, "hit_tokens": 700, "reach_lower": 0.5, "reach_upper": 1.0,
         "top_hits": [("run", 90)]}
    vd = wc.verdict(False, v, r, 2)
    assert vd["flip"] is False and vd["label"] == "TOO HEAVY FOR THE HOT PATH"
    assert "subtree" in vd["note"]                 # the cheap workaround is named, not just the refusal


# ---- estate sweep + fail-open on a junk repo ----
def test_estate_sweep_is_fail_open():
    root = Path(tempfile.mkdtemp(prefix="wc_estate_"))
    try:
        good = root / "good"
        (good / ".claude" / "exocortex").mkdir(parents=True)
        (good / "exocortex_config.json").write_text("{}", encoding="utf-8")
        (good / "run.md").write_text(_CODE_MD, encoding="utf-8")
        _cues(good, {"run": 40, "deploy": 30}, n=80)

        junk = root / "junk"
        (junk / ".claude" / "exocortex").mkdir(parents=True)
        (junk / "exocortex_config.json").write_text("{not json", encoding="utf-8")

        res = wc.estate(root)
        assert res["repos"] == 2
        assert res["candidates"] == ["good"]
        assert "NO VAULT" in res["blocked"]
        assert res["verdict"]["disposition"] == 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
