"""Credit-hygiene gauge (W5 credit-pollution · W4 failure-ledger) — offline, read-only, stdlib."""
import json

from exocortex.gauge import credit_hygiene_gauge as g

SEP = g._SEP


def test_credit_hygiene_reclaims_routing_noise():
    colonies = [("c1", {
        f"cue:c1{SEP}bash:pytest": 1.0,   # real transition — kept
        f"bash:pytest{SEP}Edit:src": 1.0,  # real transition — kept
        f"Edit:src{SEP}Edit:src": 2.0,     # SELF-edge — reclaim
        f"bash:cd{SEP}bash:cd": 0.5,       # self AND orient — reclaim (counted once)
        f"bash:ls{SEP}bash:cat": 0.5,      # orient-pair — reclaim
    })]
    c = g.credit_hygiene(colonies)
    assert c["edges"] == 5 and c["tau_mass"] == 5.0
    assert c["self_edges"] == 2 and c["self_mass"] == 2.5      # Edit→Edit + cd→cd
    assert c["orient_edges"] == 2 and c["orient_mass"] == 1.0  # cd→cd + ls→cat
    assert c["reclaim_edges"] == 3 and c["reclaim_mass"] == 3.0   # union de-dups cd→cd
    assert c["reclaim_frac_mass"] == 0.6


def test_failure_recurrence_and_plasticity():
    recs = [
        {"event": "PostToolUseFailure", "command_key": "pytest -q", "strategy_lock": 1},
        {"event": "PostToolUseFailure", "command_key": "pytest -q", "strategy_lock": 2},  # exact repeat
        {"event": "PostToolUse", "command_key": "pytest -q"},                              # …then succeeds
        {"event": "PostToolUseFailure", "command_key": "npm test", "strategy_lock": 1},    # fails, never ok
        {"event": "PostToolUse", "command_key": "git status"},                             # unrelated ok
    ]
    f = g.failure_recurrence(recs)
    assert f["failures"] == 3 and f["consequences"] == 5
    assert f["distinct_fail_keys"] == 2 and f["repeated_fail_keys"] == 1
    assert f["recurrence_rate_exact"] == 0.5
    assert f["fail_keys_later_succeeded"] == 1 and f["plasticity_rate"] == 0.5   # high → never σ-scar
    assert f["max_fail_streak"] == 2
    assert f["verb_distinct_fail"] == 2 and f["verb_repeated_fail"] == 1 and f["recurrence_rate_verb"] == 0.5


def test_run_over_state_dir_and_verdict(tmp_path):
    sd = tmp_path / "MyRepo" / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (sd / "colony_c1.json").write_text(json.dumps({"label": "c1", "deposits": 5, "tau": {
        f"cue:c1{SEP}bash:pytest": 1.0, f"Edit:src{SEP}Edit:src": 1.0}}), encoding="utf-8")
    (sd / "audit.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"event": "PostToolUseFailure", "command_key": "pytest -q", "strategy_lock": 1},
        {"event": "PostToolUse", "command_key": "pytest -q"}]), encoding="utf-8")

    res = g.run([str(sd)])
    assert res["per_repo"][0]["repo"] == "MyRepo"
    assert res["aggregate"]["credit"]["reclaim_edges"] == 1            # the Edit→Edit self-edge
    assert res["aggregate"]["failure"]["plasticity_rate"] == 1.0       # the failed key also succeeded
    assert set(res["verdict"]) == {"W5_credit_filter", "W4_failure_ledger"}
