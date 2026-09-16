"""Red-team 4 — stale state.

Two lanes:
- Procedural: F3 provenance (recency decay at readout) is BUILT but ships DORMANT (``provenance.mode``
  off). By default a year-old, never-reconfirmed route splices at full τ.
- Declarative: a note's NodeId is its content hash, so an edited note re-earns τ from zero. Stale
  *text* never inherits trust.
"""
import time

import pytest

from exocortex import colony as C
from exocortex.colony import Colony
from exocortex.wiki.digest import digest_document

EDGE = "cue:stale\tbash:make"


def _old_route():
    col = Colony(label="stale")
    col.tau = {EDGE: 3.0}
    col.deposits = 5
    col.meta = {EDGE: {"ts": time.time() - 400 * 86400, "model": "old-model"}}
    col.save()


def test_recency_mode_decays_a_stale_route(state, monkeypatch):
    _old_route()
    monkeypatch.setattr(C, "PROV_MODE", "recency")
    (_, w), = Colony.load("stale").top()
    assert w < 0.01


@pytest.mark.xfail(strict=True, reason="GAP rt-stale-1: F3 provenance ships DORMANT (provenance.mode=off, "
                   "CLAIMS.md DORMANT); a 400-day-old unreconfirmed route splices at full τ by default.")
def test_default_config_decays_a_stale_route(state, monkeypatch):
    monkeypatch.setattr(C, "PROV_MODE", "off")   # the shipped default
    _old_route()
    (_, w), = Colony.load("stale").top()
    assert w < 3.0


def test_edited_note_gets_a_new_identity():
    """Content-identity: an edited block is a new node, so any τ earned by the old text is not inherited."""
    (a,) = digest_document("ops.md", "Run `make build` before `make test`.\n")
    (b,) = digest_document("ops.md", "Run `make build2` before `make test`.\n")
    assert a.id != b.id


@pytest.mark.xfail(strict=True, reason="GAP rt-stale-2: procedural nodes are verb-altitude (bash:make), "
                   "not file-bound; nothing ties a route to the artifacts it used, so deleting the "
                   "Makefile does not stale the route.")
def test_route_is_invalidated_when_its_artifact_disappears(state, tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PROV_MODE", "off")
    _old_route()   # the project's Makefile never existed in tmp_path
    assert not (tmp_path / "Makefile").exists()
    assert "bash:make" not in Colony.load("stale").splice()
