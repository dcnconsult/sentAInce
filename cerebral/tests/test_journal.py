"""Unit tests for the Cerebral Substrate S2 — the persistent intent journal + transition detection.

OUT of the 99-lock (``tests/`` only). Run explicitly:

    python -m pytest cerebral/tests
    python cerebral/tests/test_journal.py

Drives an EVOLVING synthetic vault across consecutive scans (fixed ``now`` per scan → deterministic) to
exercise each transition class, then verifies the hash-chain is tamper-evident.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cerebral import journal as J                       # noqa: E402
from exocortex.integrity import verify_audit            # noqa: E402


def _write(vault: Path, rel: str, body: str) -> None:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _issues(updated: str, *lines: str) -> str:
    return f"# Issues\n\n**Last Updated:** {updated}\n\n" + "\n".join(lines) + "\n"


def _types(res) -> list:
    return [t["type"] for t in res["transitions"]]


def _mk():
    vault = Path(tempfile.mkdtemp(prefix="cerebral_j_vault_"))
    jdir = Path(tempfile.mkdtemp(prefix="cerebral_j_journal_"))
    return vault, jdir / "intent_journal.jsonl"


# ---- snapshot covers every declared intent with compact state ----
def test_snapshot_covers_all_intents():
    vault, _ = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Open task one", "- [x] Done task two"))
        snap = J.snapshot(vault, "2026-06-10")
        assert len(snap["states"]) == 2
        lcs = sorted(s["lc"] for s in snap["states"].values())
        assert lcs == ["C", "O"]                          # one open, one closed
        for s in snap["states"].values():
            assert set(("lc", "v", "ds", "st", "pd", "d", "s", "k", "p")) <= set(s)
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- first scan → every intent is NEW; chain verifies; first_scan flagged ----
def test_first_scan_all_new():
    vault, jpath = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Task one", "- [ ] Task two"))
        res = J.record_scan(vault, "2026-06-10", jpath)
        assert res["first_scan"] is True
        assert _types(res) == ["NEW", "NEW"]
        assert verify_audit(jpath)["ok"] is True
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- an item fresh at scan 1 goes stale by scan 2 → NEWLY_STALE (not NEW again) ----
def test_newly_stale():
    vault, jpath = _mk()
    try:
        # issue timeframe = 30d; dated 2026-06-01
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Aging task"))
        r1 = J.record_scan(vault, "2026-06-10", jpath)      # 9d silent → fresh (NEW, not stale)
        assert _types(r1) == ["NEW"] and r1["transitions"][0]["stale"] is False
        r2 = J.record_scan(vault, "2026-07-10", jpath)      # 39d silent → crosses 30d timeframe
        assert _types(r2) == ["NEWLY_STALE"]
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- toggling a checkbox flips lifecycle → CLOSED_NOW then REOPENED (same id preserved) ----
def test_closed_then_reopened():
    vault, jpath = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Toggle me"))
        J.record_scan(vault, "2026-06-05", jpath)                                   # NEW (open)
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [x] Toggle me"))
        r2 = J.record_scan(vault, "2026-06-06", jpath)                              # open → closed
        assert _types(r2) == ["CLOSED_NOW"]
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Toggle me"))
        r3 = J.record_scan(vault, "2026-06-07", jpath)                              # closed → open
        assert _types(r3) == ["REOPENED"]
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- a whole parent crossing the 90d dormancy line → ONE NEWLY_DORMANT (deduped, not per-item) ----
def test_newly_dormant_cluster():
    vault, jpath = _mk()
    try:
        _write(vault, "PAPER_OLD/ISSUES.md",
               _issues("2026-01-01", "- [ ] Old one", "- [ ] Old two"))
        r1 = J.record_scan(vault, "2026-03-20", jpath)      # ~78d silent: stale, parent NOT yet dormant
        assert set(_types(r1)) == {"NEW"} and len(r1["transitions"]) == 2
        r2 = J.record_scan(vault, "2026-04-15", jpath)      # ~104d: parent crosses 90d → dormant
        dorm = [t for t in r2["transitions"] if t["type"] == "NEWLY_DORMANT"]
        assert len(dorm) == 1                                # one cluster transition, not two item nags
        assert dorm[0]["parent"] == "PAPER_OLD" and dorm[0]["members"] == 2
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- removing an OPEN item's line → DISAPPEARED (ambiguous resolved/edited; reported, not judged) ----
def test_disappeared():
    vault, jpath = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Keep me", "- [ ] Remove me"))
        J.record_scan(vault, "2026-06-10", jpath)
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Keep me"))
        r2 = J.record_scan(vault, "2026-06-11", jpath)
        assert _types(r2) == ["DISAPPEARED"]
        assert "ambiguous" in r2["transitions"][0]["note"]
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- steady vault + same now → no transitions on the second scan ----
def test_steady_no_transitions():
    vault, jpath = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] Stable"))
        J.record_scan(vault, "2026-06-10", jpath)
        r2 = J.record_scan(vault, "2026-06-10", jpath)
        assert r2["transitions"] == []
        assert r2["first_scan"] is False
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- the hash-chain is tamper-evident: editing a past record snaps it (ADR-009) ----
def test_chain_tamper_evident():
    vault, jpath = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] One"))
        J.record_scan(vault, "2026-06-10", jpath)
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] One", "- [ ] Two"))
        J.record_scan(vault, "2026-06-20", jpath)
        assert verify_audit(jpath)["ok"] is True                     # intact after two chained scans
        # silently edit the FIRST record's payload → the chain must break
        lines = Path(jpath).read_text(encoding="utf-8").splitlines()
        rec0 = json.loads(lines[0])
        rec0["counts"]["total"] = 999                                 # tamper
        lines[0] = json.dumps(rec0, ensure_ascii=True)
        Path(jpath).write_text("\n".join(lines) + "\n", encoding="utf-8")
        v = verify_audit(jpath)
        assert v["ok"] is False and v["first_break"] == 0
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- determinism: snapshot twice (same vault, same now) → byte-identical ----
def test_snapshot_determinism():
    vault, _ = _mk()
    try:
        _write(vault, "PAPER_A/ISSUES.md", _issues("2026-06-01", "- [ ] A", "- [x] B"))
        s1 = J.snapshot(vault, "2026-06-15")
        s2 = J.snapshot(vault, "2026-06-15")
        assert json.dumps(s1, sort_keys=True) == json.dumps(s2, sort_keys=True)
    finally:
        shutil.rmtree(vault, ignore_errors=True)


# ---- verify on a missing journal is a safe report, never a crash ----
def test_verify_missing_journal():
    v = verify_audit(str(Path(tempfile.gettempdir()) / "no_such_journal_cerebral.jsonl"))
    assert v["ok"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} journal tests passed")
