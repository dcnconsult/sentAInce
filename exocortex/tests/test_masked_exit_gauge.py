"""Masked-exit gauge (R1a / rt-tool-1) — offline, read-only, stdlib. Controls for PREREG §3–§5."""
import json

import pytest

from exocortex.gauge import masked_exit_gauge as g


def _p(cls, s="s1"):
    return {"event": "UserPromptSubmit", "session": s, "reason": f"class={cls}"}


def _c(cmd, out="", ok=True, tool="Bash", s="s1", agent=""):
    return {"event": "PostToolUse" if ok else "PostToolUseFailure", "session": s, "agent_id": agent,
            "tool": tool, "command": cmd, "outcome": "ok" if ok else "fail", "output": out}


@pytest.mark.parametrize("cmd", ["grep x f || true", "rm a 2>/dev/null || :", "ls x || echo none",
                                 "make || exit 0", 'pytest -q; echo "exit: $?"', "foo; true",
                                 "(cd x && make) || true", "a || true; b"])
def test_masking_forms_are_recognized(cmd):
    assert g.is_masked(cmd)


@pytest.mark.parametrize("cmd", ["a || b", "true && pytest", "echo hi", "pytest -q | tail -5",
                                 "git commit -m 'true'", "x ||truex"])
def test_unmasked_forms_are_not(cmd):
    assert not g.is_masked(cmd)


def test_population_excludes_signatures_failures_and_non_bash():
    recs = [_p("c"), _c("pytest || true", out="1 failed, 2 passed in 0.1s"),   # signature → not ok today
            _c("make || true", ok=False),                                       # a real failure
            _c("Get-Item x -ErrorAction SilentlyContinue", tool="PowerShell"),  # descriptive lane only
            _c("ls || true")]
    rows, ps = g.population(recs)
    assert len(rows) == 1 and rows[0]["verb"] == "ls" and rows[0]["silent"] and rows[0]["masked"]
    assert ps == {"ps_ok_rows": 1, "ps_mask_idiom_rows": 1}


def test_silent_requires_empty_output_and_masked_does_not():
    rows, _ = g.population([_p("c"), _c("grep x f || true", out="f:1:x"), _c("grep y f || true")])
    assert [r["silent"] for r in rows] == [False, True]
    assert [r["masked"] for r in rows] == [True, True]


def test_retry_is_the_next_consequence_in_the_same_stream_only():
    recs = [_p("c"), _c("grep a f || true"), _c("grep b f"),     # retry: same verb next
            _c("ls x || true"), _p("c"), _c("ls x"),             # a new prompt ends the stream → no retry
            _c("cat y || true", agent="A"), _c("cat z", agent="B")]   # other agent's stream → no retry
    rows, _ = g.population(recs)
    retry = {(r["verb"], r["masked"]): r["retry"] for r in rows}
    assert retry[("grep", True)] == 1
    assert retry[("ls", True)] == 0
    assert retry[("cat", True)] == 0


def test_retry_excess_is_verb_stratified_and_drops_unmatched_strata():
    rows = ([{"session": "s", "cls": "c", "verb": "grep", "silent": True, "masked": True, "retry": 1}] * 2
            + [{"session": "s", "cls": "c", "verb": "grep", "silent": False, "masked": False, "retry": 0}] * 2
            + [{"session": "s", "cls": "c", "verb": "rm", "silent": True, "masked": True, "retry": 0}])
    R, dropped = g.retry_excess(rows, "silent")
    assert R == pytest.approx(1.0) and dropped == 1     # rm has no kept stratum


def test_loss_and_starvation():
    rows = ([{"session": "s", "cls": "a", "verb": "x", "silent": True, "masked": True, "retry": 0}] * 4
            + [{"session": "s", "cls": "a", "verb": "x", "silent": False, "masked": False, "retry": 0}] * 2
            + [{"session": "t", "cls": "b", "verb": "x", "silent": False, "masked": False, "retry": 0}] * 4)
    m = g.measure(rows, "silent", boot=10)
    assert m["L_loss_share"] == 0.4 and m["C_starved_classes"] == 1   # class a: 4/6 withheld, ≥5 rows


def test_bootstrap_is_deterministic():
    rows = [{"session": f"s{i}", "cls": "c", "verb": "v", "silent": i % 3 == 0, "masked": i % 3 == 0,
             "retry": i % 2} for i in range(30)]
    assert g.bootstrap_ci(rows, "silent", n=50) == g.bootstrap_ci(rows, "silent", n=50)


def _res(L, C, hi):
    return {"silent": {"L_loss_share": L, "C_starved_classes": C, "R_ci95": [None, hi]}}


def test_verdict_rule():
    assert g.verdict({"a": _res(0.01, 0, 0.1), "b": _res(0.05, 0, 0.0)}, "silent")["disposition"] == 1
    assert g.verdict({"a": _res(0.01, 0, 0.1), "b": _res(0.07, 0, 0.1)}, "silent")["disposition"] == 0
    assert g.verdict({"a": _res(0.01, 1, 0.1), "b": _res(0.01, 0, 0.1)}, "silent")["disposition"] == 0
    assert g.verdict({"a": _res(0.11, 0, 0.1), "b": _res(0.01, 0, 0.1)}, "silent")["disposition"] == -1
    assert g.verdict({"a": _res(0.01, 0, -0.1), "b": _res(0.01, 0, -0.2)}, "silent")["disposition"] == -1
    assert g.verdict({"a": _res(0.01, 0, -0.1), "b": _res(0.01, 0, 0.2)}, "silent")["disposition"] == 0


def test_cli_emits_aggregates_without_command_text(tmp_path, capsys):
    secret = "grep TOKEN_abc123 f || true"
    audit = tmp_path / "a" / ".claude" / "exocortex" / "audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.write_text("\n".join(json.dumps(r) for r in [_p("c"), _c(secret), _c("grep x f")]) + "\n")
    assert g.main(["--audit", str(audit), "--json"]) == 0
    out = capsys.readouterr().out
    assert "TOKEN_abc123" not in out and json.loads(out)["stores"]["a"]["silent"]["withheld"] == 1
