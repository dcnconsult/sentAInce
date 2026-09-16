"""Verb-keying gauge (R0 / DQ-1) — the PREREG §3 keying and the §4 replay on synthetic audits."""
import json

import pytest

from exocortex.gauge import verb_keying_gauge as G


@pytest.mark.parametrize("cmd,verb", [
    ("pytest -q", "pytest"),
    ("cd repo && pytest -q", "pytest"),
    ("cd a; cd b && git status", "git"),
    ("PYTHONIOENCODING=utf-8 python x.py", "python"),
    ("A=1 B=2 sudo time make all", "make"),
    ("timeout 30 python -m pytest", "python"),
    ("grep foo x.txt | head -3", "grep"),
    ("cd somewhere", "cd"),                     # all-navigation falls back to the first verb
    ("export X=1 && source env.sh", "export"),
    ("", "?"),
])
def test_working_verb(cmd, verb):
    assert G.working_verb(cmd) == verb


def test_first_keying_is_the_shipped_one():
    assert G.node("Bash", "cd repo && pytest", "first") == "bash:cd"
    assert G.node("Bash", "cd repo && pytest", "working") == "bash:pytest"
    assert G.node("Read", "/x/test_a.py", "working") == "Read:test"


def _audit(tmp_path, rows):
    p = tmp_path / "audit.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def _turn(s, cls, cmd, outcome):
    ev = "PostToolUse" if outcome == "ok" else "PostToolUseFailure"
    return [{"session": s, "event": "UserPromptSubmit", "reason": f"class={cls}"},
            {"session": s, "event": "PreToolUse", "tool": "Bash", "command": cmd},
            {"session": s, "event": ev, "tool": "Bash", "command": cmd, "outcome": outcome}]


def test_replay_segments_and_rerooting(tmp_path):
    rows = (_turn("s", "c", "cd r && pytest", "ok")
            + [{"session": "s", "event": "PreToolUse", "tool": "Bash", "command": "cd r && git push"},
               {"session": "s", "event": "PostToolUse", "tool": "Bash", "command": "cd r && git push",
                "outcome": "ok"}])
    segs = G.segments(G._read(_audit(tmp_path, rows)), "working")
    assert segs[0] == ("c", "ok", [("cue:c", "bash:pytest")])
    assert segs[1] == ("c", "ok", [("cue:c", "bash:pytest"), ("bash:pytest", "bash:git")])  # re-rooted chain
    first = G.segments(G._read(_audit(tmp_path, rows)), "first")
    assert first[1][2] == [("cue:c", "bash:cd")]          # cd→cd self-edge dropped: the route vanishes


def test_first_keying_collapses_pass_and_fail(tmp_path):
    """The DQ-1 mechanism: a passing pytest and a failing make both key as bash:cd under `first`, so the
    fail edge is indistinguishable from the pass edge; `working` keeps them apart."""
    rows = _turn("a", "c", "cd r && pytest", "ok") + _turn("b", "c", "cd r && make", "fail")
    res = G.run(_audit(tmp_path, rows))
    assert res["first"]["M3_pass_fail_jaccard"] == 1.0
    assert res["working"]["M3_pass_fail_jaccard"] == 0.0
    assert res["first"]["M2_frequency_clutter"] == 0.0
    assert res["working"]["M2_frequency_clutter"] == 0.5
    assert res["first"]["M1_nav_env_share"] == 1.0 and res["working"]["M1_nav_env_share"] == 0.0
    for k in G.KEYINGS:
        assert res[k]["check_consequence_clutter"] == 0.0     # structural under the consequence policy


def test_verdict_rule():
    good = {"first": {"M1_nav_env_share": 0.4, "M2_frequency_clutter": 0.1, "M3_pass_fail_jaccard": 0.5,
                      "check_consequence_clutter": 0.0},
            "working": {"M1_nav_env_share": 0.05, "M2_frequency_clutter": 0.2, "M3_pass_fail_jaccard": 0.3,
                        "check_consequence_clutter": 0.0}}
    bad = {"first": good["first"],
           "working": {**good["working"], "M2_frequency_clutter": 0.01, "M3_pass_fail_jaccard": 0.9}}
    assert G.verdict({"A": good, "B": good})["disposition"] == "+1"
    assert G.verdict({"A": bad, "B": bad})["disposition"] == "-1"
    assert G.verdict({"A": good, "B": bad})["disposition"] == "0"
    assert G.verdict({"A": good})["disposition"] == "0"        # one repo can never promote
    void = {"first": {**good["first"], "check_consequence_clutter": 0.1}, "working": good["working"]}
    assert G.verdict({"A": void, "B": good})["disposition"] == "VOID"


def test_soak_readout_counts_only_post_flip_edges(tmp_path):
    (tmp_path / "colony_c.json").write_text(json.dumps({
        "label": "c", "deposits": 4,
        "tau": {"cue:c\tbash:cd": 2.0, "cue:c\tbash:pytest": 1.0, "Read:src\tEdit:src": 1.0},
        "meta": {"cue:c\tbash:cd": {"ts": 100.0}, "cue:c\tbash:pytest": {"ts": 300.0},
                 "Read:src\tEdit:src": {"ts": 300.0}}}), encoding="utf-8")
    r = G.soak(tmp_path, since=200.0)
    assert r["S1_new_edges"] == 2 and r["S1_new_nav_env_share"] == 0.0
    assert r["S2_classes_with_new_edges"] == 1 and r["S2_top_new_edge_is_nav"] == 0
    assert r["S5_nav_env_edge_share"] == round(1 / 3, 4) and r["S5_nav_env_tau_share"] == 0.5
    assert G.is_nav_env_node("ps:cd") and G.is_nav_env_node("bash:A=1") and not G.is_nav_env_node("Edit:src")


def test_chain_breaks_from_sees_a_break_after_an_earlier_one(tmp_path, monkeypatch):
    """S4 control: verify_audit stops at the FIRST break; the window check must still see a later one."""
    from exocortex import audit
    p = tmp_path / "audit.jsonl"
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(p))
    monkeypatch.setenv("EXOCORTEX_AUDIT_CHAIN", "1")
    for i in range(6):
        audit.append({"event": "PreToolUse", "n": i})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert G.chain_breaks_from(p, 1)["ok"] is True                     # positive control
    del lines[1]                                                       # historic break (link) at line 2
    rec = json.loads(lines[3]); rec["n"] = 99; lines[3] = json.dumps(rec)   # later edit (self-hash) at line 4
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert G.chain_breaks_from(p, 1)["breaks"][0] == {"line": 2, "kind": "link"}
    late = G.chain_breaks_from(p, 3)                                   # window after the historic break
    assert late["ok"] is False and late["breaks"][0] == {"line": 4, "kind": "self-hash"}
