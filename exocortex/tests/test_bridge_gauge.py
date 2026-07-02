"""Bridge-validity gauge (Ticket 2 gate) — deterministic checks on a known colony graph."""

import json

import pytest

from exocortex.gauge import bridge_gauge as bg


def _write_colony(d, label, edges):
    tau = {f"{a}\t{b}": 1.0 for a, b in edges}
    (d / f"colony_{label}.json").write_text(json.dumps({"label": label, "tau": tau}), encoding="utf-8")


def test_payoff_ceiling_on_a_clean_chain(tmp_path):
    """A→B→C→D: one 3-edge path, two 2-edge, three 1-edge; 2 genuine bridge candidates (A→C, B→D)."""
    _write_colony(tmp_path, "chain", [("A", "B"), ("B", "C"), ("C", "D")])
    cols = bg.load_colonies(str(tmp_path))
    assert set(cols) == {"chain"}
    p = bg.payoff(cols)
    assert p["path_len_hist"] == {1: 3, 2: 2, 3: 1}
    assert p["bridge_candidates"] == 2
    assert p["frac_ge2"] == pytest.approx((2 + 1) / 6)


def test_hdc_fidelity_and_abstain_raises_precision(tmp_path):
    """On an unambiguous chain the router recalls perfectly (1-hop fidelity 1.0); the 0-well abstain must
    never LOWER 2-hop precision (it culls low-confidence sink-recalls)."""
    _write_colony(tmp_path, "chain", [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")])
    cols = bg.load_colonies(str(tmp_path))
    h = bg.hdc_bridge_test(cols, m=2048, abstain=0.10, seed=7)
    assert h["one_hop_fidelity"] == 1.0
    assert h["bridges_proposed"] >= 2 and h["bridge_precision"] is not None
    if h["bridge_precision_abstained"] is not None:
        assert h["bridge_precision_abstained"] >= h["bridge_precision"]


def test_run_endtoend_and_skips_tiny_classes(tmp_path):
    """run() composes payoff + hdc; a 2-node class (no 2-hop route) contributes no HDC chords."""
    _write_colony(tmp_path, "chain", [("A", "B"), ("B", "C"), ("C", "D")])
    _write_colony(tmp_path, "tiny", [("X", "Y")])
    res = bg.run(str(tmp_path))
    assert res["n_classes"] == 2
    assert res["payoff"]["bridge_candidates"] >= 2
    assert res["hdc"]["one_hop_fidelity"] == 1.0   # only the chain contributes; tiny is skipped
