"""Unit tests for the bridge-validity gauge — Ticket 2's on-body gate.

OUT of the deterministic 99-lock. Run explicitly:

    python -m pytest exocortex/tests/test_bridge_validity_gauge.py -q

This gauge decides whether an organ ships, so the properties pinned here are the ones that would let it
lie: the base rate (its load-bearing null) must only count pairs whose ordering is actually KNOWN, and the
falsifier must not fire on a denominator artifact. Both failure modes were observed while building it.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.gauge import bridge_validity_gauge as bv  # noqa: E402

SEP = "\t"
A, B, D = "docs/a.md#1", "docs/b.md#1", "docs/d.md#1"


def _colony(tmp: Path, label: str, edges: dict) -> None:
    """edges: {(src, dst): ts_or_None} -> a colony_<label>.json with tau + F3 meta."""
    tau = {f"{s}{SEP}{d}": 1.0 for (s, d) in edges}
    meta = {f"{s}{SEP}{d}": {"ts": ts} for (s, d), ts in edges.items() if ts is not None}
    (tmp / f"colony_{label}.json").write_text(
        json.dumps({"tau": tau, "meta": meta, "deposits": len(edges)}), encoding="utf-8")


# ------------------------------------------------------------------ edge reading
def test_only_note_to_note_edges_are_read_and_self_edges_dropped():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {
            (A, B): 1.0,
            (A, A): 1.0,                       # self-edge: no routing information (W5) — dropped
            ("cue:c1", A): 1.0,                # cue root: not a note
            ("Edit:src", "bash:cd"): 1.0,      # verb nodes: not notes
        })
        edges = bv.read_note_edges(tmp)
        assert edges == {"c1": {(A, B): 1.0}}, edges


# ------------------------------------------------------------------ the null
def test_spontaneous_resolution_requires_the_two_hop_path_to_come_FIRST():
    """The control arm only counts a pair if the body walked the long way BEFORE jumping it. A direct
    edge that predates its own 2-hop path is not a shortcut event and must not inflate the base rate."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {(A, B): 10.0, (B, D): 20.0, (A, D): 30.0})   # path first, then the jump
        r = bv.candidates_and_base_rate(bv.read_note_edges(tmp))
        assert r["resolved_spontaneously"] == 1, r
        assert r["candidates_open"] == 0, r
        assert r["base_rate"] == 1.0, r

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {(A, B): 10.0, (B, D): 20.0, (A, D): 5.0})    # jump PREDATES the path
        r = bv.candidates_and_base_rate(bv.read_note_edges(tmp))
        assert r["resolved_spontaneously"] == 0, r
        assert r["unstampable"] == 1, r


def test_open_candidate_is_two_hop_reachable_with_no_direct_edge():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {(A, B): 10.0, (B, D): 20.0})
        r = bv.candidates_and_base_rate(bv.read_note_edges(tmp))
        assert r["candidates_open"] == 1 and r["resolved_spontaneously"] == 0, r
        assert r["base_rate"] == 0.0, r


def test_unstamped_edges_are_EXCLUDED_from_the_null_not_assumed():
    """F3 coverage is ~94%, not 100%. An unstampable pair must be reported, never silently counted as
    either resolved or open — assuming it either way biases the number a live arm has to beat."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {(A, B): None, (B, D): None, (A, D): None})
        r = bv.candidates_and_base_rate(bv.read_note_edges(tmp))
        assert r["resolved_spontaneously"] == 0, r
        assert r["unstampable"] == 1, r
        assert r["base_rate_denominator"] == 0, r
        assert r["base_rate"] is None, r


def test_a_to_b_to_a_is_not_a_candidate():
    """A 2-hop path back to the source is a cycle, not a shortcut target."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {(A, B): 10.0, (B, A): 20.0})
        r = bv.candidates_and_base_rate(bv.read_note_edges(tmp))
        assert r["candidates_open"] == 0, r


# ------------------------------------------------------------------ power
def test_power_scales_and_is_absent_without_a_base_rate():
    assert bv.power_needed(None)["detectable"] is None
    low, high = bv.power_needed(0.05), bv.power_needed(0.40)
    assert low["offers_needed_per_arm"] < high["offers_needed_per_arm"]   # rarer event, easier to beat


# ------------------------------------------------------------------ verdict branches
def _base(open_c: int, res: int) -> dict:
    denom = open_c + res
    return {"candidates_open": open_c, "resolved_spontaneously": res, "unstampable": 0,
            "base_rate_denominator": denom, "base_rate": (res / denom) if denom else None,
            "classes_with_candidates": 1, "top_classes": {}}


def test_underpowered_store_refuses_to_flip():
    v = bv.verdict(_base(5, 1), bv.power_needed(0.16), {"available": False}, {"live": False})
    assert v["disposition"] == 0 and v["gate"] == "UNDERPOWERED", v


def test_ready_to_flip_when_powered_and_organ_never_run():
    v = bv.verdict(_base(400, 25), bv.power_needed(0.06), {"available": False}, {"live": False})
    assert v["disposition"] == 0 and v["gate"] == "READY-TO-FLIP", v


def test_falsifier_fires_when_confirm_rate_does_not_beat_the_base_rate():
    base = _base(400, 40)                                   # base rate 0.0909
    power = bv.power_needed(base["base_rate"])
    live = {"live": True, "by_status": {}, "settled": power["offers_needed_per_arm"] + 1,
            "confirm_rate": base["base_rate"], "mean_walks_to_verdict": 1.0}
    v = bv.verdict(base, power, {"available": False}, live)
    assert v["disposition"] == -1 and "FALSIFIER" in v["gate"], v


def test_promotes_only_when_confirm_rate_clears_the_base_rate_at_power():
    base = _base(400, 40)
    power = bv.power_needed(base["base_rate"])
    live = {"live": True, "by_status": {}, "settled": power["offers_needed_per_arm"] + 1,
            "confirm_rate": 0.5, "mean_walks_to_verdict": 1.0}
    v = bv.verdict(base, power, {"available": False}, live)
    assert v["disposition"] == 1, v


def test_accruing_is_not_a_verdict():
    base = _base(400, 40)
    power = bv.power_needed(base["base_rate"])
    live = {"live": True, "by_status": {}, "settled": 3, "confirm_rate": 1.0,
            "mean_walks_to_verdict": 1.0}
    v = bv.verdict(base, power, {"available": False}, live)
    assert v["disposition"] == 0 and v["gate"] == "ACCRUING", v


def test_unscoreable_geometry_is_a_coverage_fact_not_an_organ_defect():
    """THE REGRESSION. An early draft scored chords against ONE class's edges and read 32/32 'ungrounded',
    which would have been reported as a −1 against the organ. A chord whose endpoint has no credited
    history at all cannot be called an invention."""
    geo = {"available": True, "proposed": 32, "already_real": 1, "grounded_shortcuts": 2,
           "invented": 0, "unseen_endpoint": 29, "invented_frac_of_scoreable": 0.0, "scoreable": 3}
    v = bv.verdict(_base(400, 25), bv.power_needed(0.06), geo, {"live": False})
    assert v["disposition"] == 0 and v["gate"] == "GEOMETRY-UNSCOREABLE", v


def test_invented_geometry_does_fire_when_scoreable_and_dominant():
    geo = {"available": True, "proposed": 60, "already_real": 2, "grounded_shortcuts": 8,
           "invented": 40, "unseen_endpoint": 10, "invented_frac_of_scoreable": 0.8, "scoreable": 50}
    v = bv.verdict(_base(400, 25), bv.power_needed(0.06), geo, {"live": False})
    assert v["disposition"] == -1 and v["gate"] == "INVENTED", v


# ------------------------------------------------------------------ read-only
def test_structural_run_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _colony(tmp, "c1", {(A, B): 10.0, (B, D): 20.0})
        before = {p.name: p.read_bytes() for p in tmp.iterdir()}
        bv.run(str(tmp))                                     # no --vault-path → no digest, no writes
        after = {p.name: p.read_bytes() for p in tmp.iterdir()}
        assert before == after, "the structural path must not write a byte"


def test_live_readout_absent_ledger_is_a_state_not_a_failure():
    with tempfile.TemporaryDirectory() as td:
        out = bv.live_readout(Path(td))
        assert out["live"] is False and "never run" in out["note"], out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
