"""``sentaince status --full`` — the self-evidencing usage report (exocortex/usage.py).

Run: ``python -m pytest exocortex/tests/test_usage.py``
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:                                            # noqa: E402
    sys.path.insert(0, str(_ROOT))

from exocortex import cli                                                 # noqa: E402
from exocortex import usage as U                                          # noqa: E402


def _state(tmp_path: Path, records: list[dict], colonies: dict | None = None) -> Path:
    root = tmp_path / "repo"
    state = root / ".claude" / "exocortex"
    state.mkdir(parents=True)
    with (state / "audit.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    for label, tau in (colonies or {}).items():
        (state / f"colony_{label}.json").write_text(
            json.dumps({"label": label, "tau": tau, "deposits": len(tau)}), encoding="utf-8")
    return state


def _ups(injected: bool, cls: str) -> dict:
    return {"event": "UserPromptSubmit", "injected": injected, "reason": f"class={cls}"}


def _pre(tool: str, permitted) -> dict:
    return {"event": "PreToolUse", "tool": tool, "somatic_permitted": permitted}


# ---------------------------------------------------------------- summarize
def test_summarize_counts_injection_classes_and_coverage(tmp_path):
    state = _state(tmp_path, [
        _ups(True, "a#1"), _ups(True, "a#1"), _ups(False, "b#2"), _ups(False, "c#3"),
        _pre("Bash", True), _pre("Bash", False), _pre("PowerShell", True),
        _pre("Edit", None), _pre("Write", None),
        _pre("Read", None),          # non-mutating: excluded from every count
    ], colonies={"a_1": {"cue:a#1\tx": 0.9}})
    s = U.summarize(state)
    assert s["prompts"] == 4 and s["injected"] == 2
    assert s["classes"] == 3 and s["singletons"] == 2          # b#2, c#3 seen once; a#1 twice
    assert s["commands"] == 3                                   # Bash x2 + PowerShell; Read excluded
    assert s["evaluated"] == 3 and s["refused"] == 1
    assert s["file_writes"] == 2                                # Edit + Write, counted separately
    assert s["ungated"] == {}
    assert s["routes"] == 1 and s["earning_classes"] == 1


def test_read_only_tools_never_count_as_a_coverage_gap(tmp_path):
    """Read/Grep/Glob cannot mutate, so counting them ungated would invent a gap that does
    not exist — the denominator is calls where a veto could ever matter."""
    state = _state(tmp_path, [_pre(t, None) for t in ("Read", "Grep", "Glob", "WebFetch")])
    s = U.summarize(state)
    assert s["commands"] == 0 and s["file_writes"] == 0 and s["ungated"] == {}


def test_file_writes_are_not_counted_as_an_uncovered_gap(tmp_path):
    """The Write/Edit determination, pinned. A file write has no recognizable shape, so the
    somatic vocabulary has no referent — measured across 3,110 real calls, the dangerous-target
    population was empty while the most plausible broad rule would have fired on 22% of
    legitimate work. Write/Edit are therefore OUT OF SCOPE, not an uncovered hole. If a future
    edit folds them back into the coverage denominator, this test fails and forces the argument
    to be made again rather than drifting in."""
    state = _state(tmp_path, [_pre("Bash", True)] + [_pre("Edit", None)] * 50)
    s = U.summarize(state)
    assert s["commands"] == 1 and s["evaluated"] == 1           # coverage is 100%, not 2%
    assert s["file_writes"] == 50
    assert "Edit" not in s["ungated"]
    out = U.render(state)
    assert "not gated by design" in out


def test_summarize_survives_a_corrupt_and_absent_audit(tmp_path):
    root = tmp_path / "repo"
    state = root / ".claude" / "exocortex"
    state.mkdir(parents=True)
    assert U.summarize(state)["prompts"] == 0                   # absent audit -> zeros, no raise
    (state / "audit.jsonl").write_text('{"event": "UserPromptSubmit"\nnot json\n',
                                       encoding="utf-8")
    assert U.summarize(state)["prompts"] == 0                   # unparseable lines skipped


def test_bom_written_audit_is_still_read(tmp_path):
    """A BOM must not zero the report (the platform default encoding is not UTF-8 here)."""
    root = tmp_path / "repo"
    state = root / ".claude" / "exocortex"
    state.mkdir(parents=True)
    (state / "audit.jsonl").write_text(json.dumps(_ups(True, "a#1")) + "\n",
                                       encoding="utf-8-sig")
    assert U.summarize(state)["prompts"] == 1


# ---------------------------------------------------------------- render
def test_render_on_an_empty_install_does_not_divide_by_zero(tmp_path):
    out = U.render(_state(tmp_path, []))
    assert "n/a" in out and "no prompts recorded yet" in out


def test_render_states_dose_not_effect(tmp_path):
    """The report must never read as an outcome claim — the A/B that would license one is
    parked at 0 (results/guide_accrue_ab_v1/)."""
    out = U.render(_state(tmp_path, [_ups(True, "a#1")]))
    assert "Dose, not effect" in out
    assert "nothing is sent anywhere" in out


# ---------------------------------------------------------------- CLI wiring
def test_status_full_appends_the_report(tmp_path, capsys):
    state = _state(tmp_path, [_ups(True, "a#1"), _pre("Bash", True)])
    root = state.parents[1]
    assert cli.cmd_status([str(root), "--full"]) == 0
    out = capsys.readouterr().out
    assert "🧬 sentaince:" in out and "safety floor" in out


def test_plain_status_stays_the_one_line_vitals(tmp_path, capsys):
    """Contract pin: the default output is the voice line and nothing else."""
    state = _state(tmp_path, [_ups(True, "a#1"), _pre("Bash", True)])
    root = state.parents[1]
    assert cli.cmd_status([str(root)]) == 0
    out = capsys.readouterr().out
    assert "safety floor" not in out
    assert len([ln for ln in out.strip().splitlines() if ln.strip()]) == 1


def test_a_broken_reporter_cannot_break_the_vitals_line(tmp_path, monkeypatch, capsys):
    """Same discipline as the plugin machinery: the vitals voice survives a fault below it."""
    state = _state(tmp_path, [_ups(True, "a#1")])
    root = state.parents[1]
    monkeypatch.setattr(U, "render", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli.cmd_status([str(root), "--full"]) == 0
    out = capsys.readouterr().out
    assert "🧬 sentaince:" in out and "usage report unavailable" in out


# ---------------------------------------------------------------- the promise in the output
def test_the_reporter_has_no_network_surface():
    """`nothing is sent anywhere` is printed to users, so it is pinned, not trusted: the
    module must not import a transport. Guards against a later 'just add telemetry' edit."""
    src = (_ROOT / "exocortex" / "usage.py").read_text(encoding="utf-8")
    for banned in ("socket", "urllib", "requests", "http.client", "httpx", "subprocess"):
        assert banned not in src, f"usage.py must stay transport-free (found {banned!r})"


def test_the_reporter_never_writes(tmp_path):
    """Read-only pin: a status read must not mutate the store it reads."""
    state = _state(tmp_path, [_ups(True, "a#1"), _pre("Bash", True)],
                   colonies={"a_1": {"cue:a#1\tx": 0.9}})
    before = {p.name: p.read_bytes() for p in state.iterdir()}
    U.render(state)
    after = {p.name: p.read_bytes() for p in state.iterdir()}
    assert before == after
