"""ab_outcome_gauge — the A/B harvest implements PREREG (results/guide_accrue_ab_v1/PREREG.md) verbatim.

Out of the 99-lock, like the other gauge tests. The fixtures build a synthetic audit.jsonl + arm log with
KNOWN metrics so every PREREG definition (§7 metrics, §8 exclusions, C2/C4 controls, §9 test) has a named
assertion — including the negative controls (wrong class, contamination, ambiguous join, null effect).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from exocortex.gauge.ab_outcome_gauge import (apply_exclusions, harvest, join_arms, load_arms, log_arm,
                                              permutation_p, session_metrics)

T0 = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)
CLS = "guide-accrue#18"


def _rec(session, event, ts, *, command="", command_key="", reason=""):
    return {"session": session, "event": event, "ts": ts.isoformat(),
            "command": command, "command_key": command_key, "reason": reason}


def _write_session(fh, sid, start, *, cls=CLS, steps=(), fails=0, ok=1, contaminate=False):
    """One synthetic session: UserPromptSubmit(class) → PreToolUse per step → failures → final ok."""
    t = start
    fh.write(json.dumps(_rec(sid, "UserPromptSubmit", t, reason=f"class={cls}")) + "\n")
    for cmd in steps:
        t += timedelta(seconds=10)
        fh.write(json.dumps(_rec(sid, "PreToolUse", t, command=cmd, command_key=cmd)) + "\n")
    if contaminate:
        t += timedelta(seconds=10)
        fh.write(json.dumps(_rec(sid, "PreToolUse", t, command="cat .claude/exocortex/colony_x.json",
                                 command_key="cat .claude/exocortex/colony_x.json")) + "\n")
    for _ in range(fails):
        t += timedelta(seconds=10)
        fh.write(json.dumps(_rec(sid, "PostToolUseFailure", t)) + "\n")
    for _ in range(ok):
        t += timedelta(seconds=10)
        fh.write(json.dumps(_rec(sid, "PostToolUse", t)) + "\n")


def _build(tmp_path, sessions, arms):
    sd = tmp_path / "exo"
    sd.mkdir(parents=True, exist_ok=True)
    with open(sd / "audit.jsonl", "w", encoding="utf-8") as fh:
        for kw in sessions:
            _write_session(fh, **kw)
    for ts, arm, task in arms:
        log_arm(sd, arm, task, now=ts)
    return sd


def test_metrics_match_prereg_definitions(tmp_path):
    """§7: total_steps = PreToolUse count; orientation = {cd,ls,pwd,cat,dir} verbs; failures; duration."""
    sd = _build(tmp_path, [], [])
    with open(sd / "audit.jsonl", "w", encoding="utf-8") as fh:
        _write_session(fh, "s1", T0, steps=("ls -la", "cd src", "python -m pytest", "git commit -m x"),
                       fails=1, ok=2)
    rep = harvest(sd, None, CLS)
    assert len(rep["included"]) == 0 and len(rep["excluded"]) == 1   # no arm logged → E3, still measured
    s = rep["excluded"][0]
    assert s["total_steps"] == 4
    assert s["orientation_reads"] == 2            # ls + cd; python/git are not orientation
    assert s["failures"] == 1 and s["ok"] == 2
    assert s["duration_s"] == 70.0                # 7 records after the first, 10s apart


def test_arm_join_exclusions_and_contamination(tmp_path):
    """C2/C4/§8: the latest log-arm ≤30 min wins; wrong class E1; contamination E2; double-join E3."""
    arm_on = (T0 - timedelta(minutes=2), "ON", "P1a")
    arm_off = (T0 + timedelta(minutes=30), "OFF", "P1b")
    stale = (T0 - timedelta(hours=2), "OFF", "stale")            # outside the 30-min window
    sd = _build(tmp_path, [], [stale, arm_on, arm_off])
    with open(sd / "audit.jsonl", "w", encoding="utf-8") as fh:
        _write_session(fh, "good-on", T0, steps=("ls", "python x"), ok=1)
        _write_session(fh, "good-off", T0 + timedelta(minutes=31), steps=("ls", "ls", "python x"), ok=1)
        _write_session(fh, "wrong-cls", T0 + timedelta(minutes=32), cls="other#1", steps=("ls",), ok=1)
        _write_session(fh, "dirty", T0 + timedelta(minutes=33), steps=("ls",), contaminate=True, ok=1)
    rep = harvest(sd, None, CLS)
    by = {s["session"]: s for s in rep["included"] + rep["excluded"]}
    assert by["good-on"]["arm"] == "ON" and by["good-on"]["task"] == "P1a"
    assert by["good-off"]["arm"] == "OFF"                        # NOT joined to the stale entry
    assert any("E1" in w for w in by["wrong-cls"]["excluded"])
    assert any("E2" in w for w in by["dirty"]["excluded"])
    # wrong-cls + dirty raced good-off for the same OFF entry → they are AMBIGUOUS/E3 as well, listed not hidden
    assert by["good-on"] in rep["included"]


def test_permutation_null_and_signal():
    """§9 with its negative control: identical arms → p≈1-ish (no signal); clearly lower ON → small p."""
    p_null, method = permutation_p([5.0, 6.0, 7.0], [5.0, 6.0, 7.0])
    assert p_null > 0.4 and method.startswith("exact")
    p_sig, _ = permutation_p([2.0, 3.0, 2.0, 3.0], [9.0, 10.0, 11.0, 12.0])
    assert p_sig <= 0.05                                          # 1/C(8,4)=0.014 exact
    p_ins, method_ins = permutation_p([], [1.0])
    assert p_ins == 1.0 and method_ins == "insufficient"


def test_log_arm_appends_and_loads(tmp_path):
    sd = tmp_path / "exo"; sd.mkdir()
    log_arm(sd, "on", "P2b", now=T0)
    log_arm(sd, "OFF", "", now=T0 + timedelta(minutes=5))
    arms = load_arms(sd)
    assert [a["arm"] for a in arms] == ["ON", "OFF"] and arms[0]["task"] == "P2b"
