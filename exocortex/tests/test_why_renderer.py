"""Consequence-provenance "why" renderer (issue #13) — a strict READER over persisted state.

Contract under test: reconstructs a deposit's segment from audit records alone; reports τ
evidence (and honest absence, incl. the W5 self-edge rule); re-verifies the hash chain from
bytes and DETECTS a tampered record; never writes anything.

OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_why_renderer.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex import provenance as P                                    # noqa: E402
from exocortex.integrity import chain_hash                               # noqa: E402


def _chained(records: list[dict]) -> list[dict]:
    prev = "GENESIS"
    out = []
    for r in records:
        r = dict(r)
        r["prev"] = prev
        r["hash"] = chain_hash(r, prev)
        prev = r["hash"]
        out.append(r)
    return out


def _mkstore(tmp_path: Path) -> Path:
    """A tiny session: git status → pytest (ok, the deposit, seg_len 1) with a credited note."""
    sd = tmp_path / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    recs = _chained([
        {"session": "s1", "event": "SessionStart", "mode": "observe", "ts": "t0"},
        {"session": "s1", "event": "PostToolUse", "tool": "Bash", "command": "git status",
         "outcome": "ok", "ts": "t1"},
        {"session": "s1", "event": "PostToolUse", "tool": "Bash", "command": "pytest -q",
         "outcome": "ok", "seg_len": 1, "wiki_injected": 3, "wiki_used": 1,
         "energy": 90.0, "tier": "SATED", "ts": "t2"},
    ])
    (sd / "audit.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    (sd / "colony_build.json").write_text(json.dumps({
        "label": "build", "deposits": 7,
        "tau": {"bash:git\tbash:pytest": 1.25},
        "meta": {"bash:git\tbash:pytest": {"ts": 1750000000.0, "model": "test-model"}},
    }), encoding="utf-8")
    return sd


def test_renders_route_tau_note_credit_and_verified_chain(tmp_path):
    sd = _mkstore(tmp_path)
    md = P.render(sd / "audit.jsonl")
    assert "session `s1`" in md
    assert "`bash:pytest` exit 0 (seg_len 1)" in md
    assert "`bash:git` → `bash:pytest`: τ=1.250 in class `build` (7 lifetime deposits" in md
    assert "model=test-model" in md
    assert "3 note(s) injected; **1 credited**" in md
    assert md.count("✓ payload + link verified") == 2          # both segment records verified
    assert "CHAIN BROKEN" not in md


def test_tampered_record_snaps_the_chain(tmp_path):
    """The negative control: silently edit one audited command → the renderer must say BROKEN."""
    sd = _mkstore(tmp_path)
    audit = sd / "audit.jsonl"
    lines = audit.read_text(encoding="utf-8").splitlines()
    r = json.loads(lines[1])
    r["command"] = "git status --tampered"                     # payload edit, hash left as-was
    lines[1] = json.dumps(r)
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    md = P.render(audit)
    assert "CHAIN BROKEN" in md


def test_self_edges_reported_as_never_stored_not_pruned(tmp_path):
    sd = _mkstore(tmp_path)
    audit = sd / "audit.jsonl"
    recs = [json.loads(x) for x in audit.read_text(encoding="utf-8").splitlines()]
    extra = _chained([
        {"session": "s2", "event": "PostToolUse", "tool": "Bash", "command": "grep a", "outcome": "ok", "ts": "t3"},
        {"session": "s2", "event": "PostToolUse", "tool": "Bash", "command": "grep b",
         "outcome": "ok", "seg_len": 1, "ts": "t4"},
    ])
    audit.write_text("\n".join(json.dumps(r) for r in recs + extra) + "\n", encoding="utf-8")
    md = P.render(audit, session="s2")
    assert "self-edge — never stored (W5 credit hygiene" in md
    assert "decayed or pruned" not in md


def test_default_session_is_latest_with_a_deposit_and_reader_writes_nothing(tmp_path):
    sd = _mkstore(tmp_path)
    before = {p.name: p.read_bytes() for p in sd.iterdir()}
    md = P.render(sd / "audit.jsonl", session=None)
    assert "session `s1`" in md
    after = {p.name: p.read_bytes() for p in sd.iterdir()}
    assert before == after                                     # strictly a reader — bytes untouched


def test_depositless_session_says_so(tmp_path):
    sd = _mkstore(tmp_path)
    md = P.render(sd / "audit.jsonl", session="no-such-session")
    assert "no memory was written" in md.lower() or "no deposits" in md.lower()
