"""Red-team 5 — conflicting memory.

Procedural routes are alternatives ranked by τ. Since R5 (2026-09-16) the splice marks near-tied
alternatives out of one step as contested; this is read-side only, with no τ change. Declarative notes
that contradict each other are still both eligible, and that gap stays pinned.
"""
import pytest

from exocortex.colony import Colony
from exocortex.wiki.attribute import attribute_used
from exocortex.wiki.digest import digest_document
from exocortex.wiki.node import WikiGraph


def _competing():
    col = Colony(label="conf")
    col.tau = {"cue:conf\tbash:pytest": 2.0, "cue:conf\tbash:unittest": 1.9}
    col.deposits = 5
    col.save()
    return Colony.load("conf").splice()


def test_competing_routes_are_both_surfaced(state):
    s = _competing()
    assert "bash:pytest" in s and "bash:unittest" in s


def test_near_tied_competing_routes_are_flagged(state):
    """Closed by R5 (2026-09-16): near-tied alternatives out of one step carry a read-side marker."""
    s = _competing()
    assert "contested" in s.lower()
    assert "cue:conf → bash:pytest | bash:unittest" in s


def test_a_clear_preference_is_not_flagged(state):
    col = Colony(label="pref")
    col.tau = {"cue:pref\tbash:pytest": 2.0, "cue:pref\tbash:unittest": 1.0}
    col.deposits = 5
    col.save()
    assert "contested" not in Colony.load("pref").splice().lower()


@pytest.mark.xfail(strict=True, reason="GAP rt-conf-2: contradicting notes are independent nodes; both can "
                   "be credited on one exit 0 (no contradiction check on the declarative lane).")
def test_contradicting_notes_are_not_both_credited():
    g = WikiGraph()
    for text in ("Deploy with `deploy.sh --region us-east-1` only.\n",
                 "Never use `deploy.sh --region us-east-1`; it is decommissioned.\n"):
        for n in digest_document("ops.md", text):
            g.add(n)
    used = attribute_used(g, list(g.nodes), "bash deploy.sh --region us-east-1")
    assert len(used) < 2
