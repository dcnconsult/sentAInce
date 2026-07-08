"""Stage A harness — snapshot/thaw fidelity, oracles, telemetry parsing, and a token-free dry run.

No test launches ``claude``; the end-to-end loop is exercised via ``--agent-cmd`` (a fake agent that
edits the verify file and exits 0). Out of the 99-lock, beside the other testbed/gauge tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from exocortex.testbed.ab_stage_a import (_sign_flip_p, _usage_from_stream, check_oracle,
                                          file_touches, report, run_battery, snapshot, thaw)


@pytest.fixture()
def source_repo(tmp_path):
    """A miniature git repo with one organ file + activation config — the snapshot subject."""
    src = tmp_path / "src"
    (src / ".claude" / "exocortex").mkdir(parents=True)
    (src / "docs").mkdir()
    (src / "docs" / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")
    (src / "README.md").write_text("readme\n", encoding="utf-8")
    (src / ".claude" / "exocortex" / "colony_guide-accrue#18.json").write_text('{"edges": {}}', encoding="utf-8")
    (src / ".claude" / "exocortex" / "cues.json").write_text('{"n": 1}', encoding="utf-8")
    (src / ".claude" / "exocortex" / "state_old.json").write_text("{}", encoding="utf-8")   # must NOT travel
    (src / "exocortex_config.json").write_text(
        '{"declarative": {"mode": "live", "vault_path": "C:/somewhere/original"}}', encoding="utf-8")
    def git(*a):
        subprocess.run(["git", *a], cwd=str(src), capture_output=True, text=True)
    git("init", "-q")
    git("add", "README.md", "docs/GUIDE.md")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed")
    return src


TASK = {"id": "T1", "pair": 1, "verify_file": "docs/GUIDE.md", "verify_regex": "planted marker",
        "scope": ["docs/GUIDE.md"],
        "prompt": "add the planted marker to docs/GUIDE.md"}


def test_snapshot_carries_organs_not_sessions(source_repo, tmp_path):
    out = tmp_path / "snap"
    m = snapshot(source_repo, out)
    assert m["tracked_files"] == 2 and "cues.json" in m["organs"]
    assert (out / "docs" / "GUIDE.md").exists()
    assert (out / ".claude" / "exocortex" / "colony_guide-accrue#18.json").exists()
    assert not (out / ".claude" / "exocortex" / "state_old.json").exists()      # session state never travels
    assert (out / "exocortex_config.json").exists()
    assert not (out / ".claude" / "settings.local.json").exists()               # machine-local, re-derived


def test_thaw_rederives_paths_and_installs_hooks(source_repo, tmp_path):
    snap = tmp_path / "snap"; snapshot(source_repo, snap)
    trial = tmp_path / "trial"
    thaw(snap, trial)
    cfg = json.loads((trial / "exocortex_config.json").read_text(encoding="utf-8"))
    assert cfg["declarative"]["vault_path"] == str(trial)                       # no absolute-path leakage
    settings = json.loads((trial / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert "hooks" in settings and "PreToolUse" in settings["hooks"]            # the permission authority
    assert (trial / ".git").is_dir()
    # organ churn is excluded from the measurable git surface
    assert ".claude/" in (trial / ".git" / "info" / "exclude").read_text(encoding="utf-8")


def test_oracle_and_touch_metrics(source_repo, tmp_path):
    snap = tmp_path / "snap"; snapshot(source_repo, snap)
    trial = tmp_path / "trial"; thaw(snap, trial)
    assert check_oracle(trial, TASK) is False
    (trial / "docs" / "GUIDE.md").write_text("# Guide\nthe planted marker\n", encoding="utf-8")
    (trial / "stray.txt").write_text("out of scope\n", encoding="utf-8")
    assert check_oracle(trial, TASK) is True
    ft = file_touches(trial, TASK)
    assert "docs/GUIDE.md" in [f.replace("\\", "/") for f in ft["files_changed"]]
    assert ft["n_out_of_scope"] == 1 and ft["out_of_scope"] == ["stray.txt"]


def test_usage_parser_reads_result_record_and_message_fallback():
    stream = "\n".join([
        json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 10, "output_tokens": 5}}}),
        json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 7, "output_tokens": 3,
                                                               "cache_read_input_tokens": 100}}}),
        json.dumps({"type": "result", "num_turns": 4, "duration_ms": 1234, "total_cost_usd": 0.05,
                    "usage": {"input_tokens": 17, "output_tokens": 8}}),
    ])
    u = _usage_from_stream(stream)
    assert u["input_tokens"] == 17 and u["output_tokens"] == 8                  # result record wins
    assert u["num_turns"] == 4 and u["duration_ms"] == 1234
    assert u["cache_read_tokens"] == 100                                        # fallback sum fills the gap
    u2 = _usage_from_stream(stream.rsplit("\n", 1)[0])                          # truncated stream: no result
    assert u2["input_tokens"] == 17 and u2["num_turns"] is None                 # summed fallback


def test_dry_run_end_to_end_and_preflight(source_repo, tmp_path):
    snap = tmp_path / "snap"; snapshot(source_repo, snap)
    fake = tmp_path / "fake_agent.py"
    fake.write_text(  # edits the verify file (success arm behavior); prints a minimal stream
        "import pathlib, json\n"
        "p = pathlib.Path('docs/GUIDE.md'); p.write_text(p.read_text() + 'the planted marker\\n')\n"
        "print(json.dumps({'type': 'result', 'num_turns': 2, 'duration_ms': 10,\n"
        "                  'usage': {'input_tokens': 3, 'output_tokens': 2}}))\n", encoding="utf-8")
    out = tmp_path / "runs.jsonl"
    rows = run_battery(snap, tasks=[TASK], repeats=2, max_turns=40, model="dry",
                       out_path=out, workdir=tmp_path / "work", keep=False,
                       agent_cmd=f'"{sys.executable}" "{fake}" {{prompt}}')
    assert len(rows) == 4                                                       # 1 task × 2 repeats × 2 arms
    assert all(r["success"] for r in rows) and all(r["output_tokens"] == 2 for r in rows)
    assert {r["arm"] for r in rows} == {"ON", "OFF"}
    assert len(out.read_text(encoding="utf-8").splitlines()) == 4               # crash-safe per-run flush
    # pre-satisfied oracle refuses to run (the free-success control)
    (snap / "docs" / "GUIDE.md").write_text("the planted marker\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        run_battery(snap, tasks=[TASK], repeats=1, max_turns=40, model="dry",
                    out_path=out, workdir=tmp_path / "work2", keep=False, agent_cmd="python -c pass")


def test_oracle_verify_absent_refutation(source_repo, tmp_path):
    """A refutation task fails when the false premise is parroted, even with the truth also present."""
    snap = tmp_path / "snap"; snapshot(source_repo, snap)
    trial = tmp_path / "trial"; thaw(snap, trial)
    task = {**TASK, "verify_regex": "100 episodes", "verify_absent": r"\b87\b"}
    g = trial / "docs" / "GUIDE.md"
    g.write_text("ran 100 episodes\n", encoding="utf-8")
    assert check_oracle(trial, task) is True                     # truth alone → pass
    g.write_text("ran 100 episodes (originally reported as 87)\n", encoding="utf-8")
    assert check_oracle(trial, task) is False                    # parroted false premise → fail
    g.write_text("ran 87 episodes\n", encoding="utf-8")
    assert check_oracle(trial, task) is False                    # premise only → fail


def test_sign_flip_null_and_signal():
    assert _sign_flip_p([0.0, 0.0, 0.0]) > 0.4                                  # no effect → no signal
    assert _sign_flip_p([-1.0, -1.0, -1.0, -1.0, -1.0]) <= 0.05                 # consistent ON-better
    assert _sign_flip_p([]) == 1.0


def test_report_tiers_success_gate():
    """Tier 2 must be conditional on success — the fast-but-wrong guard has a named assertion."""
    def row(arm, task, success, out_tok, steps):
        return {"arm": arm, "task": task, "pair": 1, "success": success, "cls": "guide-accrue#18",
                "contaminated": False, "output_tokens": out_tok, "input_tokens": 1, "steps": steps,
                "wall_s": 1.0, "num_turns": 1, "orientation_reads": 0, "failures": 0,
                "n_changed": 1, "n_out_of_scope": 0, "timed_out": False}
    rows = [row("ON", "T1", False, 1, 1),      # ON: fast but WRONG — must not count in Tier 2
            row("ON", "T1", True, 50, 5),
            row("OFF", "T1", True, 60, 6),
            row("OFF", "T1", True, 70, 7)]
    rep = report(rows, as_json=True)
    assert rep["tier1_success"]["ON"]["rate"] == 0.5
    assert rep["tier2_efficiency_given_success"]["output_tokens"]["ON_median"] == 50   # the failure excluded
    excluded = [row("ON", "T1", True, 1, 1)]
    excluded[0]["cls"] = "other#9"
    rep2 = report(rows + excluded, as_json=True)
    assert rep2["n_excluded_cls_or_contam"] == 1
