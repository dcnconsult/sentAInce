"""Tests for the Suggestion Ledger (§G6) — the human-as-body consequence channel (ADR-010).

The load-bearing assertion: credit attaches ONLY to a verified-good outcome, NEVER to the selection
(ADR-001). Plus append-only event-sourcing and hash-chain tamper-evidence (the G1 responsibility ledger).
"""
import pytest

from exocortex import ledger


def _p(tmp_path):
    return tmp_path / "suggestion_ledger.jsonl"


def test_record_and_fold(tmp_path):
    p = _p(tmp_path)
    sid = ledger.record_suggestion(suggestion="use a worktree", selection="take",
                                   source="assistant", path=p)
    st = ledger.state(p)
    assert sid in st
    assert st[sid]["selection"] == "take"
    assert st[sid]["suggestion"] == "use a worktree"
    assert st[sid]["credited"] is False  # selection alone never credits


def test_selection_never_credits(tmp_path):
    p = _p(tmp_path)
    for sel in ledger.SELECTIONS:
        sid = ledger.record_suggestion(suggestion=f"x {sel}", selection=sel, path=p)
        assert ledger.state(p)[sid]["credited"] is False


def test_only_good_outcome_credits(tmp_path):
    p = _p(tmp_path)
    good = ledger.record_suggestion(suggestion="good one", selection="take", path=p)
    bad = ledger.record_suggestion(suggestion="bad one", selection="take", path=p)
    rev = ledger.record_suggestion(suggestion="reverted one", selection="take", path=p)
    ledger.record_outcome(good, "good", path=p)
    ledger.record_outcome(bad, "bad", path=p)
    ledger.record_outcome(rev, "reverted", path=p)
    st = ledger.state(p)
    assert st[good]["credited"] is True
    assert st[bad]["credited"] is False
    assert st[rev]["credited"] is False


def test_outcome_is_event_sourced_not_mutated(tmp_path):
    p = _p(tmp_path)
    sid = ledger.record_suggestion(suggestion="evolving", selection="take", path=p)
    ledger.record_outcome(sid, "unknown", path=p)
    assert ledger.state(p)[sid]["credited"] is False
    ledger.record_outcome(sid, "good", evidence="exit 0 / tests pass", path=p)
    row = ledger.state(p)[sid]
    assert row["credited"] is True
    assert row["outcome_evidence"] == "exit 0 / tests pass"
    # event-sourced: nothing mutated — three append-only lines exist
    assert len(ledger.load_events(p)) == 3


def test_invalid_inputs_rejected(tmp_path):
    p = _p(tmp_path)
    with pytest.raises(ValueError):
        ledger.record_suggestion(suggestion="x", selection="grab", path=p)
    sid = ledger.record_suggestion(suggestion="x", selection="take", path=p)
    with pytest.raises(ValueError):
        ledger.record_outcome(sid, "great", path=p)


def test_hash_chain_intact_and_tamper_evident(tmp_path):
    p = _p(tmp_path)
    a = ledger.record_suggestion(suggestion="one", selection="take", path=p)
    ledger.record_outcome(a, "good", path=p)
    ledger.record_suggestion(suggestion="two", selection="decline", path=p)
    assert ledger.verify(p)["ok"] is True, ledger.verify(p)
    # tamper: rewrite a past payload; the chain must snap (self-hash mismatch)
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"one"', '"hacked"')
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ledger.verify(p)["ok"] is False


def test_summary_counts(tmp_path):
    p = _p(tmp_path)
    s1 = ledger.record_suggestion(suggestion="a", selection="take", path=p)
    ledger.record_suggestion(suggestion="b", selection="decline", path=p)
    s3 = ledger.record_suggestion(suggestion="c", selection="take", path=p)
    ledger.record_outcome(s1, "good", path=p)
    ledger.record_outcome(s3, "bad", path=p)
    summ = ledger.summary(p)
    assert summ["total"] == 3
    assert summ["by_selection"]["take"] == 2
    assert summ["by_selection"]["decline"] == 1
    assert summ["uptake_rate"] == round(2 / 3, 3)
    assert summ["good_rate"] == round(1 / 2, 3)  # of the 2 with outcomes, 1 good
    assert summ["credited"] == 1
    assert summ["pending_outcome"] == 1
