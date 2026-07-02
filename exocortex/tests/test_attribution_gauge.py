"""Attribution-precision gauge + its testbed (exporter) surface — Ticket 1 / #2.

The gauge gates the flag-flip: it must report HONEST precision/recall over labeled ground truth, and the
exporter must surface it (+ the live credit rate) to Prometheus/Grafana.
"""

import json

from exocortex import audit
from exocortex.gauge import attribution_gauge as ag


def test_gauge_precision_rises_recall_falls_with_min_overlap():
    rows = ag.sweep((1, 2, 3))
    precisions = [r["precision"] for r in rows]
    recalls = [r["recall"] for r in rows]
    assert precisions == sorted(precisions), "precision must be non-decreasing in min_overlap"
    assert recalls == sorted(recalls, reverse=True), "recall must be non-increasing in min_overlap"


def test_gauge_mo1_full_recall_but_coincidental_false_credits():
    r1 = ag._score(1)
    assert r1["recall"] == 1.0, "every used note echoes ≥1 salient token by construction"
    assert r1["precision"] < 1.0, "min_overlap=1 must expose coincidental echo (the precision stressor)"
    offenders = [p["name"] for p in r1["per_scenario"] if p["fp"]]
    assert "coincidental_git" in offenders and "deploy_common_token" in offenders


def test_gauge_mo2_perfect_precision():
    r2 = ag._score(2)
    assert r2["precision"] == 1.0, "no distractor shares 2 distinctive tokens with the action"
    assert r2["fp"] == 0
    assert r2["recall"] < 1.0, "the precision gain costs recall (single-token used notes are missed)"


def test_gauge_recommendation_is_precision_first():
    res = ag.run(precision_target=0.9)
    rec = res["recommended"]
    assert rec["target_met"] is True
    assert rec["min_overlap"] == 2, "precision-first gate should land on min_overlap=2"
    assert rec["precision"] >= 0.9


def test_audit_wiki_fields_only_when_present():
    bare = audit.record(session="s", event="PostToolUse", mode="observe")
    assert "wiki_injected" not in bare and "wiki_used" not in bare
    stamped = audit.record(session="s", event="PostToolUse", mode="observe", wiki_injected=3, wiki_used=1)
    assert stamped["wiki_injected"] == 3 and stamped["wiki_used"] == 1


def test_exporter_surfaces_attribution_metrics(tmp_path):
    import re

    from exocortex.genome import load_genome
    from exocortex.testbed.exporter.metrics import collect

    def metric_value(text, name):
        """Value of a metric sample by name, ignoring labels (per-repo series carry repo="<name>")."""
        m = re.search(rf"^{re.escape(name)}(?:\{{[^}}]*\}})? (.+)$", text, re.MULTILINE)
        return m.group(1) if m else None

    state = tmp_path / "state"
    state.mkdir()
    # a planted gauge result (what `python -m exocortex.gauge.attribution_gauge --json` would write)
    (state / "attribution_gauge.json").write_text(json.dumps(ag.run()), encoding="utf-8")
    # live consequences carrying wiki attribution telemetry → credit rate 3/5 = 0.6
    (state / "audit.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"event": "PostToolUse", "outcome": "ok", "seg_len": 1, "wiki_injected": 3, "wiki_used": 1},
        {"event": "PostToolUse", "outcome": "ok", "seg_len": 2, "wiki_injected": 2, "wiki_used": 2},
    ]), encoding="utf-8")

    text = collect(state, load_genome())
    # global synthetic gauge — repo-independent, so no repo label
    assert 'exocortex_attribution_precision{min_overlap="2"} 1.0' in text
    assert "exocortex_attribution_recommended_min_overlap 2" in text
    # per-repo series carry a repo="<name>" label (multi-repo exporter) — assert label-agnostically
    assert metric_value(text, "exocortex_wiki_credit_rate") == "0.6"   # used/injected = 3/5
    assert metric_value(text, "exocortex_wiki_used_total") == "3"


def test_exporter_auto_computes_gauge_without_planted_json(tmp_path):
    """The compose wiring: the exporter computes the gauge in-process, so precision metrics are served
    even with NO planted attribution_gauge.json (no cron / extra service needed)."""
    from exocortex.genome import load_genome
    from exocortex.testbed.exporter.metrics import collect

    state = tmp_path / "state"
    state.mkdir()                                              # deliberately empty — no planted JSON
    text = collect(state, load_genome())
    assert "exocortex_attribution_gauge_source 1" in text
    assert 'exocortex_attribution_precision{min_overlap="2"} 1.0' in text


# --------------------------------------------------------------- Layer-2 harness (sim path)
def test_layer2_harness_sim_reproduces_precision_contrast():
    """The planted-token harness, run with the deterministic actor, must reproduce the gauge's contrast:
    min_overlap=1 false-credits the coincidental (echo) distractor; min_overlap=2 does not."""
    from exocortex.testbed import attribution_run as ar

    tasks = ar.plant()[:3]
    r1 = ar.aggregate([ar.run_sim(t, explore=8, min_overlap=1) for t in tasks])
    r2 = ar.aggregate([ar.run_sim(t, explore=8, min_overlap=2) for t in tasks])
    assert r1["completion_rate"] == 1.0 and r2["completion_rate"] == 1.0
    assert r1["fp"] > 0, "min_overlap=1 should coincidentally false-credit the shared-token distractor"
    assert r2["fp"] == 0 and r2["precision"] == 1.0, "min_overlap=2 should be precision-clean"
    assert r2["recall"] == 1.0, "multi-token solution commands are still caught at min_overlap=2"
