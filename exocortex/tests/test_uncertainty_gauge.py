"""Tests for the uncertainty/veto-signal gauge (G1/F2 candidates; F1 latent).

Asserts the rate maths and the numbers-driven verdict: null on the flagship shape (all 'attempt', no veto),
signal only when abstains / vetoes-near-memory actually occur.
"""
from exocortex.gauge import uncertainty_gauge as ug


def test_analyze_rates():
    recs = [
        {"event": "PreToolUse", "epistemic_decision": "attempt", "somatic_permitted": True, "session": "s1"},
        {"event": "PreToolUse", "epistemic_decision": "abstain", "somatic_permitted": True, "session": "s1"},
        {"event": "PreToolUse", "epistemic_decision": "attempt", "somatic_permitted": False,
         "somatic_organ": "C1_interlock", "session": "s1"},
        {"event": "PostToolUse", "outcome": "ok", "wiki_injected": 3, "wiki_used": 1, "session": "s1"},
        {"event": "PreToolUse", "epistemic_decision": "attempt", "somatic_permitted": True, "session": "s2"},
    ]
    m = ug.analyze(recs)
    assert m["pre_total"] == 4
    assert m["assessed"] == 4
    assert m["abstain"] == 1 and m["abstain_rate"] == 0.25
    assert m["vetoes"] == 1 and m["veto_rate"] == 0.25
    assert m["veto_organs"] == ["C1_interlock"]
    assert m["injected_consequences"] == 1
    assert m["veto_near_memory"] == 1  # the veto's session (s1) had an injected-note consequence


def test_verdict_null_on_flagship_shape():
    # all "attempt", no veto, no abstain — the real flagship shape this gauge measured
    recs = [{"event": "PreToolUse", "epistemic_decision": "attempt", "somatic_permitted": True, "session": "s"}
            for _ in range(50)]
    v = ug.verdict(ug.analyze(recs))
    assert v["G1_handoff"]["signal"] is False
    assert v["F2_veto_demotion"]["signal"] is False
    assert v["F1_safety_pin"]["signal"] is False


def test_verdict_signal_when_events_occur():
    recs = [{"event": "PreToolUse", "epistemic_decision": "abstain" if i < 10 else "attempt",
             "somatic_permitted": True, "session": "x"} for i in range(100)]
    for i in range(5):  # 5 vetoes, each in a session that also injected a note → F2 near-memory
        s = f"v{i}"
        recs.append({"event": "PreToolUse", "epistemic_decision": "attempt", "somatic_permitted": False,
                     "somatic_organ": "C1_interlock", "session": s})
        recs.append({"event": "PostToolUse", "outcome": "ok", "wiki_injected": 2, "wiki_used": 1, "session": s})
    v = ug.verdict(ug.analyze(recs))
    assert v["G1_handoff"]["signal"] is True
    assert v["F2_veto_demotion"]["signal"] is True


def test_load_fail_open(tmp_path):
    assert ug.load(tmp_path / "nope.jsonl") == []
    p = tmp_path / "a.jsonl"
    p.write_text('{"event":"PreToolUse"}\nnot json\n\n', encoding="utf-8")
    assert len(ug.load(p)) == 1
