"""Failing-splice gauge (avenue 2) — offline, read-only, stdlib. Controls for PREREG §3–§5."""
import json
import random

import pytest

from exocortex import colony as C
from exocortex.gauge import failing_splice_gauge as g


def test_replay_colony_matches_the_live_colony(monkeypatch):
    # The replay is only as good as its mirror: same stream → same τ and the same dominant path.
    monkeypatch.setattr(C, "PROV_MODE", "off")
    rng = random.Random(7)
    nodes = ["cue:c", "bash:pytest", "bash:git", "Edit:src", "Read:other", "bash:make"]
    live, mirror = C.Colony(label="x"), g.ReplayColony()
    for step in range(120):
        if step % 17 == 16:
            live.consolidate()
            mirror.consolidate()
            continue
        path = [rng.choice(nodes) for _ in range(rng.randint(2, 5))]
        es = list(zip(path, path[1:]))
        live.deposit(es, weight=1.0)
        mirror.deposit(es)
    assert {tuple(k.split(C._SEP)): round(v, 9) for k, v in live.tau.items()} == \
           {k: round(v, 9) for k, v in mirror.tau.items()}
    assert live.dominant_path() == mirror.dominant_path()


def _p(s, cls, injected=True):
    return {"event": "UserPromptSubmit", "session": s, "reason": f"class={cls}", "injected": injected}


def _pre(s, cmd):
    return {"event": "PreToolUse", "session": s, "tool": "Bash", "command": cmd}


def _post(s, cmd, ok=True):
    return {"event": "PostToolUse" if ok else "PostToolUseFailure", "session": s, "tool": "Bash",
            "command": cmd, "outcome": "ok" if ok else "fail"}


def _turn(s, cls, cmds, oks=None, injected=True):
    oks = oks or [True] * len(cmds)
    out = [_p(s, cls, injected)]
    for c, ok in zip(cmds, oks):
        out += [_pre(s, c), _post(s, c, ok)]
    return out


def _learn(s="s0", cls="c", n=3):
    return [r for _ in range(n) for r in _turn(s, cls, ["make", "pytest"])]


def test_a_turn_is_spliced_only_with_injection_repetition_and_a_command_node():
    recs = (_turn("a", "c", ["make"]) + _turn("a", "c", ["make"])            # deposits 0, then 1 → no splice
            + _turn("a", "c", ["make"]) + _turn("a", "c", ["make"], injected=False))
    turns = g.replay(recs)
    assert [t["spliced"] for t in turns] == [False, False, True, False]
    assert "bash:make" in turns[2]["cmd"]


def test_follow_contradiction_and_off_route_base():
    recs = _learn() + _turn("s1", "c", ["ls", "make"], oks=[False, False])    # off-route ls fails, route make fails
    turns = g.replay(recs)
    route, off = g.samples(turns)
    last = turns[-1]
    assert last["spliced"] and last["followed"] and last["contradicted"]
    assert ("s1", "bash:make", 1) in route
    assert ("s1", "bash:ls", 1) in off and ("s1", "bash:make", 1) not in off


def test_excess_is_verb_stratified_and_drops_unmatched_strata():
    route = [("s", "bash:make", 1), ("s", "bash:make", 0), ("s", "bash:rare", 1)]
    off = [("t", "bash:make", 0), ("t", "bash:make", 0)]
    E, dropped = g.excess(route, off)
    assert E == pytest.approx(0.5) and dropped == 1


def test_persistence_counts_later_splices_of_the_same_path():
    recs = (_learn() + _turn("s1", "c", ["make"], oks=[False])   # contradiction: nothing deposits, path stays
            + _turn("s2", "c", ["ls"]) + _turn("s3", "c", ["ls"]))
    turns = g.replay(recs)
    g.samples(turns)
    p = g.persistence(turns)
    assert p["contradictions"] == 1
    assert p["P_median"] >= 1


def _m(followed, X, lo, hi, P):
    return {"followed": followed, "X_contradiction_rate": X, "E_ci95": [lo, hi], "P_median": P}


def test_verdict_rule():
    ok = _m(40, 0.2, 0.01, 0.2, 3)
    assert g.verdict({"a": ok, "b": ok})["disposition"] == 1
    assert g.verdict({"a": ok, "b": _m(10, 0.2, 0.01, 0.2, 3)})["disposition"] == 0        # 1 evaluable
    assert g.verdict({"a": _m(40, 0.02, -0.1, 0.1, 3), "b": _m(40, 0.3, -0.2, -0.01, 3)})["disposition"] == -1
    assert g.verdict({"a": ok, "b": _m(40, 0.2, -0.05, 0.2, 3)})["disposition"] == 0


def test_cli_emits_numbers_without_classes_or_commands(tmp_path, capsys):
    audit = tmp_path / "audit.jsonl"
    recs = _learn(cls="SECRETCLASS") + _turn("s1", "SECRETCLASS", ["make --token=XYZ"])
    audit.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert g.main(["--audit", str(audit), "--label", "a", "--json", "--working-from", "a=0"]) == 0
    out = capsys.readouterr().out
    assert "SECRETCLASS" not in out and "XYZ" not in out
    assert json.loads(out)["stores"]["a"]["N_spliced"] >= 1
