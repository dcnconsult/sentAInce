"""FEATURES.md ↔ Genome consistency — the docs must never exceed (or drift from) reality.

OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_features_consistency.py

Two mechanized invariants (from the v1 agent review's transparency package, §7-3):
  1. every `Genome key | Default` row in FEATURES.md's "Knobs at a glance" table matches the shipped
     value in ``exocortex.genome.DEFAULTS``;
  2. every knob the docs call **dormant** actually ships ``off`` — dormant-by-default is a promise,
     not prose.
"""
from __future__ import annotations

import re
from pathlib import Path

from exocortex.genome import DEFAULTS

FEATURES = Path(__file__).resolve().parents[1] / "docs" / "FEATURES.md"

_ROW = re.compile(r"^\|\s*`(?P<key>[a-z_.]+)`\s*\|\s*(?P<default>[^|]+?)\s*\|\s*(?P<effect>.*)\|\s*$")


def _lookup(dotted: str):
    node = DEFAULTS
    for part in dotted.split("."):
        assert isinstance(node, dict) and part in node, (
            f"FEATURES.md documents `{dotted}` but genome DEFAULTS has no such key — doc drift")
        node = node[part]
    return node


def _rows():
    rows = [m.groupdict() for m in map(_ROW.match, FEATURES.read_text(encoding="utf-8").splitlines()) if m]
    assert len(rows) >= 10, "knobs table not found / format changed — update the parser deliberately"
    return rows


def test_every_documented_default_matches_the_shipped_genome():
    for row in _rows():
        real = _lookup(row["key"])
        doc = row["default"].strip().strip("`")
        if isinstance(real, (int, float)) and not isinstance(real, bool):
            assert float(doc) == float(real), (
                f"`{row['key']}`: FEATURES.md says {doc}, genome ships {real}")
        else:
            assert doc == str(real), (
                f"`{row['key']}`: FEATURES.md says {doc!r}, genome ships {real!r}")


def test_every_dormant_claim_actually_ships_off():
    dormant_rows = [r for r in _rows() if "dormant" in r["effect"].lower()]
    assert len(dormant_rows) >= 4, "expected the dormant organs to be marked in the knobs table"
    for row in dormant_rows:
        assert _lookup(row["key"]) == "off", (
            f"`{row['key']}` is documented dormant but ships {_lookup(row['key'])!r} — "
            f"dormant-by-default is a promise")


def test_known_dormant_organs_belt_and_braces():
    """The five organs the docs promise ship OFF — asserted by name so a table rewrite can't silently
    drop the invariant."""
    for key in ("endocrine.mode", "eligibility_trace.mode", "provenance.mode",
                "integrity.mode", "declarative.mode"):
        assert _lookup(key) == "off", f"{key} ships {_lookup(key)!r}, docs promise 'off'"
