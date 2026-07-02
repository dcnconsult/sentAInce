"""Slice 5 body-gauge classifier — the 3 behavioral outcomes (Ticket 2)."""

from exocortex.testbed import bridge_run as bg


def test_classifier_labels_the_three_outcomes():
    assert bg.run_sim("shortcut_ok")["outcome"] == bg.PAYOFF      # reached goal in < full-chain steps
    assert bg.run_sim("shortcut_fail")["outcome"] == bg.TOXIC     # jumped to D, missed B's dependency → fail
    assert bg.run_sim("walk_full")["outcome"] == bg.WASTE         # walked the full chain → bridge moot


def test_classifier_edges():
    M, G = bg.MAGIC, bg.GOAL
    # incomplete: never attempted D
    assert bg.classify([(f"echo {M} > dep.txt", "ok")]) == bg.INCOMPLETE
    # toxic: D attempted and failed
    assert bg.classify([(f"grep {M} dep.txt && echo {G} > done.txt", "fail")]) == bg.TOXIC
    # payoff: reached goal in fewer than the full chain
    assert bg.classify([(f"echo {M}>dep.txt && grep {M} dep.txt && echo {G}>done.txt", "ok")]) == bg.PAYOFF
    # waste: reached goal but took the full chain
    full = [(f"echo {M} > dep.txt", "ok"), ("ls .", "ok"),
            (f"grep {M} dep.txt && echo {G} > done.txt", "ok")]
    assert bg.classify(full) == bg.WASTE
