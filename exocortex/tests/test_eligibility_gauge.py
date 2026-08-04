"""Unit tests for the Eligibility-trace gauge (organ 3D) — the REAL-segment scanner.

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]``). Run explicitly:

    python -m pytest exocortex/tests/test_eligibility_gauge.py

The load-bearing property here is not the arithmetic, it is that a **parse failure can never masquerade
as a corpus finding**. ``measure_real_segments`` used to parse each audit file in one all-or-nothing
comprehension, so a single torn row — an expected artifact of an append-only, fail-open audit — dropped
the entire file and returned ``segments=0``. The gauge's own printed read turns that into "N≥4 is ~0%
→ park 3D", i.e. the instrument silently returned the parked verdict on unread data. On the live
SentAInce store, 5 malformed lines out of 11,029 suppressed all 2,758 segments.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.gauge.eligibility_gauge import measure_real_segments  # noqa: E402


def _rec(session: str, event: str, tool: str = "") -> str:
    return json.dumps({"session": session, "event": event, "tool": tool})


def _write_audit(root: Path, lines: list) -> None:
    (root / "audit.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clean_segment_lines() -> list:
    """Two segments in one session: a 3-step one (2 Pre + closing Bash) and a 4-step one."""
    return [
        _rec("s1", "PreToolUse", "Read"),
        _rec("s1", "PreToolUse", "Edit"),
        _rec("s1", "PostToolUse", "Bash"),      # closes segment of length 3
        _rec("s1", "PreToolUse", "Read"),
        _rec("s1", "PreToolUse", "Edit"),
        _rec("s1", "PreToolUse", "Grep"),
        _rec("s1", "PostToolUse", "Bash"),      # closes segment of length 4
    ]


def test_clean_audit_yields_expected_segments():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_audit(root, _clean_segment_lines())
        out = measure_real_segments(str(root))
        assert out["files_used"] == 1, out
        assert out["segments"] == 2, out
        assert out["lines_malformed"] == 0, out
        assert out["ge4_count"] == 1, out       # the length-4 segment only


def test_one_torn_row_does_not_discard_the_whole_file():
    """THE REGRESSION. A torn row must cost its own row, never the file's segments."""
    lines = _clean_segment_lines()
    lines.insert(3, '0e6530a32b75"}')           # a real-shaped fragment of a split append
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_audit(root, lines)
        out = measure_real_segments(str(root))
        assert out["lines_malformed"] == 1, out
        assert out["files_used"] == 1, out
        # the whole point: the surviving rows still produce their segments
        assert out["segments"] == 2, out
        assert out["ge4_count"] == 1, out


def test_torn_first_row_still_identifies_the_file_as_hook_audit():
    """A tear in row 1 must not make the file look like a non-audit batch and get skipped."""
    lines = ['{"session": "s1", "eve'] + _clean_segment_lines()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_audit(root, lines)
        out = measure_real_segments(str(root))
        assert out["files_used"] == 1, out
        assert out["segments"] == 2, out


def test_non_audit_json_is_still_skipped():
    """The original skip behaviour must survive: a demo batch file is not a hook audit."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "batch.jsonl").write_text(json.dumps({"commands": ["ls"]}) + "\n", encoding="utf-8")
        out = measure_real_segments(str(root))
        assert out["files_used"] == 0, out
        assert out["files_skipped"] == 1, out
        assert out["segments"] == 0, out


def test_well_formed_non_dict_rows_are_ignored_not_crashed():
    lines = _clean_segment_lines()
    lines.insert(2, "[1, 2, 3]")                # valid JSON, not a record
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_audit(root, lines)
        out = measure_real_segments(str(root))
        assert out["lines_malformed"] == 0, out
        assert out["segments"] == 2, out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
