"""Red-team 8 — route keying (DQ-1).

A compound command is remembered by its first token at the shipped default, so a route through
`cd repo && pytest` is stored as `bash:cd`. That is not an integrity breach, since the exit-0 law still
holds, but it is a data-quality gap in what the memory says. The `colony.verb_keying = working` fix
exists (R0, pre-registered +1) and ships opt-in; the default-config gap stays pinned until the default
flips.
"""
import pytest

from exocortex import colony as C
from exocortex.colony import Colony

from .conftest import run_turn

PROMPT = "run the unit tests for the parser"
CMD = "cd repo && pytest -q"


def test_working_keying_remembers_the_working_verb(state, monkeypatch):
    monkeypatch.setattr(C, "VERB_KEYING", "working")
    label = run_turn("s", PROMPT, [CMD])
    assert f"cue:{label}\tbash:pytest" in Colony.load(label).tau


@pytest.mark.xfail(strict=True, reason="GAP rt-key-1 / DQ-1: colony.verb_keying ships 'first' "
                   "(ADR-003 opt-in); at the default, `cd repo && pytest` is remembered as bash:cd.")
def test_default_keying_remembers_the_working_verb(state, monkeypatch):
    monkeypatch.setattr(C, "VERB_KEYING", "first")
    label = run_turn("s", PROMPT, [CMD])
    assert f"cue:{label}\tbash:pytest" in Colony.load(label).tau
