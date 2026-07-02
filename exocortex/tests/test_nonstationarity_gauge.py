"""Non-stationarity gauge (F3 provenance · recency/version decay) — offline, read-only, stdlib."""
import json

from exocortex.gauge import nonstationarity_gauge as g

SEP = g._SEP


def _rec(event, key, ts, **kw):
    return {"event": event, "command_key": key, "ts": ts, "session": kw.get("session", "s1"), **kw}


def test_provenance_coverage_is_zero_on_a_pre_f3_store():
    # No record carries a model-id; no colony edge carries a per-deposit timestamp → the instrument is absent.
    recs = [_rec("PostToolUse", "pytest -q", "2026-06-01T00:00:00+00:00"),
            _rec("PostToolUse", "git status", "2026-06-02T00:00:00+00:00")]
    cols = [("c1", {f"cue:c1{SEP}bash:pytest": 1.0, f"bash:pytest{SEP}Edit:src": 1.0}, {})]
    p = g.provenance(recs, cols)
    assert p["consequences"] == 2 and p["model_coverage"] == 0.0
    assert p["edges"] == 2 and p["edge_ts_coverage"] == 0.0


def test_provenance_counts_a_stamped_store():
    # the colony meta lane IS the F3 instrument: ts and model coverage are counted independently over edges.
    cols = [("c1", {f"a{SEP}b": 1.0, f"b{SEP}c": 1.0, f"c{SEP}d": 1.0},
             {f"a{SEP}b": {"ts": 1717200000.0, "model": "claude-opus-4-8"},   # ts + model
              f"b{SEP}c": {"ts": 1717200001.0}})]                              # ts only (model not yet sourced)
    p = g.provenance([], cols)
    assert p["edges"] == 3
    assert p["edge_ts_coverage"] == round(2 / 3, 3)     # a→b and b→c carry a timestamp
    assert p["model_coverage"] == round(1 / 3, 3)       # only a→b carries a model-id


def test_temporal_span_and_recency():
    recs = [_rec("PostToolUse", "x", f"2026-06-{d:02d}T00:00:00+00:00") for d in range(1, 11)]  # 10 days, daily
    t = g.temporal(recs)
    assert t["span_days"] == 9.0 and t["sessions"] == 1
    # last quartile of a 9-day span starts at day 7.75 → ts on days 8, 9, 10 → 3/10.
    assert t["recent_quartile_frac"] == 0.3


def test_stationarity_detects_drift_and_churn():
    # early half is all `pytest`; late half is all `docker` → disjoint mix: TV=1.0, churn=1.0.
    early = [_rec("PostToolUse", "pytest -q", f"2026-06-01T00:00:{s:02d}+00:00") for s in range(4)]
    late = [_rec("PostToolUse", "docker build", f"2026-06-02T00:00:{s:02d}+00:00") for s in range(4)]
    s = g.stationarity(early + late)
    assert s["keyed_consequences"] == 8
    assert s["drift_tv"] == 1.0 and s["verb_churn"] == 1.0
    assert s["n_born"] == 1 and s["n_died"] == 1   # docker born, pytest died


def test_stationarity_stable_skeleton_has_no_drift():
    recs = [_rec("PostToolUse", "pytest -q", f"2026-06-01T00:00:{s:02d}+00:00") for s in range(10)]
    s = g.stationarity(recs)
    assert s["drift_tv"] == 0.0 and s["verb_churn"] == 0.0


def test_stationarity_by_class_removes_cross_class_confound():
    # Two classes, each INTERNALLY stable, but the operator switches A→B over time. Pooled drift is maximal
    # (A's verbs early, B's verbs late); within-class drift is ~0 (each class's own mix never changes).
    recs = [_rec("UserPromptSubmit", "", "2026-06-01T00:00:00+00:00", reason="class=A", session="s1")]
    recs += [_rec("PostToolUse", "pytest -q", f"2026-06-01T00:00:{s + 1:02d}+00:00", session="s1") for s in range(8)]
    recs += [_rec("UserPromptSubmit", "", "2026-06-02T00:00:00+00:00", reason="class=B", session="s2")]
    recs += [_rec("PostToolUse", "docker build", f"2026-06-02T00:00:{s + 1:02d}+00:00", session="s2") for s in range(8)]
    pooled = g.stationarity(recs)
    bycls = g.stationarity_by_class(recs)
    assert pooled["drift_tv"] == 1.0                      # pooled: A-verbs early, B-verbs late → max (confounded)
    assert bycls["classes_measured"] == 2
    assert bycls["mean_within_class_drift"] == 0.0        # each class internally stable → no real route rot
    assert bycls["null_drift"] == 0.0 and bycls["mean_excess_drift"] == 0.0
    assert {c["class"] for c in bycls["top"]} == {"A", "B"}   # carry-forward join attributes verbs to classes


def test_within_class_drift_detects_real_route_rot():
    # one class whose OWN verb mix shifts over its lifetime → genuine within-class non-stationarity
    recs = [_rec("UserPromptSubmit", "", "2026-06-01T00:00:00+00:00", reason="class=C", session="s1")]
    recs += [_rec("PostToolUse", "make build", f"2026-06-01T00:00:{s + 1:02d}+00:00", session="s1") for s in range(4)]
    recs += [_rec("PostToolUse", "bazel test", f"2026-06-01T00:01:{s + 1:02d}+00:00", session="s1") for s in range(4)]
    bycls = g.stationarity_by_class(recs)
    assert bycls["classes_measured"] == 1 and bycls["mean_within_class_drift"] == 1.0   # make→bazel within class C
    assert bycls["mean_excess_drift"] > 0.0              # the real shift exceeds the shuffle null


def test_null_catches_small_sample_tv_bias():
    # 8 verbs each appearing ONCE → any 4/4 split is disjoint → observed TV looks MAXIMAL (1.0), but the
    # shuffle null is ALSO 1.0, so excess is 0: no real temporal structure, only small-sample sampling bias.
    recs = [_rec("UserPromptSubmit", "", "2026-06-01T00:00:00+00:00", reason="class=N", session="s1")]
    verbs = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"]
    recs += [_rec("PostToolUse", f"{v} run", f"2026-06-01T00:00:{i + 1:02d}+00:00", session="s1")
             for i, v in enumerate(verbs)]
    bycls = g.stationarity_by_class(recs)
    assert bycls["mean_within_class_drift"] == 1.0       # observed split looks maximal…
    assert bycls["null_drift"] == 1.0                    # …but the shuffle null is identical (8 distinct, 4+4)
    assert bycls["mean_excess_drift"] == 0.0             # → zero real signal: pure small-sample artifact


def test_run_over_state_dir_and_verdict(tmp_path):
    sd = tmp_path / "MyRepo" / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (sd / "colony_c1.json").write_text(json.dumps(
        {"label": "c1", "deposits": 5, "tau": {f"cue:c1{SEP}bash:pytest": 1.0}}), encoding="utf-8")
    (sd / "audit.jsonl").write_text("\n".join(json.dumps(r) for r in (
        [_rec("PostToolUse", "pytest -q", f"2026-06-01T00:00:{s:02d}+00:00") for s in range(4)]
        + [_rec("PostToolUse", "docker build", f"2026-06-02T00:00:{s:02d}+00:00") for s in range(4)])),
        encoding="utf-8")
    res = g.run([str(sd)])
    assert res["per_repo"][0]["repo"] == "MyRepo"
    assert res["aggregate"]["provenance"]["model_coverage"] == 0.0     # instrument absent
    assert res["verdict"]["F3_nonstationarity"]["signal"] is True      # disjoint early/late mix → drift
    assert res["verdict"]["F3_nonstationarity"]["instrument_absent"] is True
