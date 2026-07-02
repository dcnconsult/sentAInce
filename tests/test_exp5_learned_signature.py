"""Evidence-lock tests for Experiment 5 — learned-signature scars.

The locked verdict (−1) rests on the two deterministic, self-contained arms (structural + hdc_z3);
the gated RAG arms (hashing, real semantic) are non-deterministic telemetry and are NOT tested here.
A non-vacuity test proves the separability metric *can* report a positive margin when separation
truly exists — so the −1 is a finding about the command string, not a rigged harness.
"""
from __future__ import annotations

import json

from experiments.exp5_learned_signature import SHOULD_PASS, SHOULD_REFUSE, WITNESS, run
from sentaince.organism.learned_signature import (
    HDCEncoder,
    StructuralEncoder,
    separability,
)


def test_core_verdict_is_minus_one():
    ledger = run(seed=0, gated=False)
    assert ledger["verdict"] == -1
    assert ledger["core_separates"] is False
    assert all(ledger["checks"].values())


def _arm(ledger: dict, name: str) -> dict:
    return next(a for a in ledger["arms"] if a["encoder"] == name)


def test_structural_reproduces_the_c4r_wall():
    """The hand-specified signature: a benign protected-delete collides at sim 1.0; an evasion misses."""
    s = _arm(run(0, gated=False), "structural")
    assert s["separable"] is False
    assert s["margin"] == -1.0
    assert s["closest_benign_sim"] == 1.0          # benign collision sits at maximal similarity


def test_hdc_shows_the_lexical_inversion():
    """The kernel VSA groups by tokens: a benign look-alike outscores a lexically-distant toxin."""
    h = _arm(run(0, gated=False), "hdc_z3")
    assert h["separable"] is False
    assert h["margin"] < 0
    assert h["closest_benign_sim"] > h["hardest_toxin_sim"]   # the inversion, quantified


def test_anchor_is_self_recognized():
    """Sanity: each encoder recognizes the witnessed toxin against itself (sim ≈ 1)."""
    ledger = run(0, gated=False)
    for name in ("structural", "hdc_z3"):
        assert _arm(ledger, name)["self_sim"] >= 0.999


def test_separability_metric_is_not_rigged():
    """Non-vacuity: on a genuinely separable corpus the metric reports a positive margin."""
    sep = separability(
        StructuralEncoder(),
        witness=["rm -rf /backups"],
        should_refuse=["rm -rf /var/lib/db", "dd if=x of=/dev/sda"],   # both (DESTROY, PROTECTED)
        should_pass=["echo hi", "ls /tmp"],                            # different signatures
    )
    assert sep["separable"] is True
    assert sep["margin"] == 1.0


def test_hdc_encoder_is_deterministic():
    """The kernel-VSA encoding is stable run-to-run (blake2b item seeds)."""
    enc = HDCEncoder()
    a = enc.encode("rm -rf /backups")
    b = enc.encode("rm -rf /backups")
    assert (a == b).all()
    assert enc.similarity(a, b) == 1.0


def test_same_seed_is_byte_identical():
    assert json.dumps(run(0, gated=False), sort_keys=True) == json.dumps(run(0, gated=False), sort_keys=True)


def test_corpus_is_balanced_and_nontrivial():
    assert len(WITNESS) == 1 and len(SHOULD_REFUSE) == 5 and len(SHOULD_PASS) == 5
