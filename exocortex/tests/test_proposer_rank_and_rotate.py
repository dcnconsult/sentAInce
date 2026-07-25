"""Unit tests for F1 (ranked lexical proposer) + F2 (explore rotation) — the 2026-07-24 log-audit fixes.

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]``). Run explicitly:

    python -m pytest exocortex/tests/test_proposer_rank_and_rotate.py

The defect both fixes address: ``_lexical`` matched on ANY single shared token and returned nodes in
vault FILE order, so ``proposer_k`` did the selecting — alphabetically. A doc named ``aaa`` beat the doc
the prompt was actually about. ``test_rare_token_beats_alphabetical_position`` is that defect, pinned.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.colony import Colony, _SEP                       # noqa: E402
from exocortex.wiki.node import ExonNode, WikiGraph             # noqa: E402
from exocortex.wiki.propose import _idf, _lexical, propose      # noqa: E402
from exocortex.wiki.splice import _select                       # noqa: E402


def _graph(specs) -> WikiGraph:
    """specs: [(doc, heading, text)] → a graph whose insertion order IS the file order."""
    g = WikiGraph()
    for i, (doc, heading, text) in enumerate(specs):
        g.add(ExonNode(id=f"{doc}#{heading}:{i}", text=text, heading_path=(heading,), span=(i, i + 1)))
    return g


def _rank(on: bool):
    os.environ["EXOCORTEX_LEXICAL_RANK"] = "1" if on else "0"


def _rotate(on: bool):
    os.environ["EXOCORTEX_EXPLORE_ROTATE"] = "1" if on else "0"


def teardown_function(_fn):
    os.environ.pop("EXOCORTEX_LEXICAL_RANK", None)
    os.environ.pop("EXOCORTEX_EXPLORE_ROTATE", None)


# ---- THE DEFECT, PINNED: alphabetical position must not beat topical relevance ----
def test_rare_token_beats_alphabetical_position():
    g = _graph([
        ("aaa/generic.md", "Run the summary", "x"),      # sorts first, matches only the common token
        ("zzz/endocrine.md", "Endocrine organ", "y"),    # sorts last, carries the rare token
        ("mmm/other.md", "Run the report", "z"),         # another common-token match
    ])
    prompt = "run the endocrine organ"
    _rank(False)
    assert _lexical(g, prompt)[0].startswith("aaa/")     # old behaviour: file order wins
    g._lex_idf = None
    _rank(True)
    assert _lexical(g, prompt)[0].startswith("zzz/")     # fixed: the rare, specific token wins


# ---- ranking must not change WHICH nodes match, only their order (recall is preserved) ----
def test_ranking_preserves_the_match_set():
    g = _graph([("a.md", "Colony deposit", "x"), ("b.md", "Unrelated topic", "y"),
                ("c.md", "Deposit ledger", "z")])
    _rank(False)
    old = set(_lexical(g, "colony deposit"))
    g._lex_idf = None
    _rank(True)
    new = set(_lexical(g, "colony deposit"))
    assert old == new and len(old) == 2


# ---- a long heading path must not win on breadth alone (the sqrt normalisation) ----
def test_verbose_headings_do_not_win_on_breadth():
    g = WikiGraph()
    g.add(ExonNode(id="wide.md#h:0", text="x",
                   heading_path=("run report summary build test deploy check", ), span=(0, 1)))
    g.add(ExonNode(id="narrow.md#h:1", text="y", heading_path=("endocrine",), span=(1, 2)))
    _rank(True)
    assert _lexical(g, "endocrine run")[0].startswith("narrow")


# ---- an empty prompt still abstains; no crash, no candidates ----
def test_empty_prompt_abstains():
    g = _graph([("a.md", "Anything", "x")])
    _rank(True)
    assert _lexical(g, "") == [] and propose(g, prompt="") == []


# ---- IDF is cached on the graph and rebuilt when invalidated ----
def test_idf_is_cached_and_invalidatable():
    g = _graph([("a.md", "Colony", "x")])
    first = _idf(g)
    assert _idf(g) is first                              # same object → cached, not recomputed
    g._lex_idf = None
    assert _idf(g) is not first


# ---- above the cost ceiling the IDF pass is skipped, but ranking still beats file order ----
def test_oversized_corpus_skips_idf_but_still_ranks():
    import exocortex.wiki.propose as PR
    g = _graph([("aaa/generic.md", "Run", "x"),
                ("zzz/specific.md", "Endocrine organ colony", "y")])
    old = PR.IDF_MAX_NODES
    try:
        PR.IDF_MAX_NODES = 1                             # force the degraded path
        g._lex_idf = None
        assert _idf(g) == {}                             # no IDF map built — the O(N) pass is skipped
        _rank(True)
        # uniform weights: the node matching MORE prompt tokens still outranks the alphabetical winner
        assert _lexical(g, "endocrine organ colony run")[0].startswith("zzz/")
    finally:
        PR.IDF_MAX_NODES = old


# ---- F2: rotation admits the least-offered notes; proposer order is only the tie-break ----
def test_rotation_prefers_the_least_offered_note():
    g = _graph([("stale.md", "Alpha", "x"), ("fresh.md", "Alpha", "y")])
    cands = [n for n in g.nodes]                         # stale.md first in proposer order
    import exocortex.wiki.splice as SP
    orig = SP._offers
    try:
        SP._offers = lambda: {"stale.md": 9}
        _rotate(False)
        _top, ex = _select(g, cands, floor=0.05, cap=20, budget=1)
        assert ex[0].id.startswith("stale")              # old behaviour: proposer order admits the stale one
        _rotate(True)
        _top, ex = _select(g, cands, floor=0.05, cap=20, budget=1)
        assert ex[0].id.startswith("fresh")              # rotated: the un-offered note gets the slot
    finally:
        SP._offers = orig


# ---- rotation NEVER starves: an all-tired pool still explores (nothing is banned) ----
def test_rotation_never_stalls_exploration():
    g = _graph([("a.md", "Alpha", "x"), ("b.md", "Alpha", "y")])
    import exocortex.wiki.splice as SP
    orig = SP._offers
    try:
        SP._offers = lambda: {"a.md": 50, "b.md": 50}
        _rotate(True)
        _top, ex = _select(g, list(g.nodes), floor=0.05, cap=20, budget=1)
        assert len(ex) == 1                              # still explores — fatigue reorders, never bans
    finally:
        SP._offers = orig


# ---- a note that has EARNED τ leaves the explore pool entirely (exploit, not explore) ----
def test_earned_notes_are_not_explored():
    g = _graph([("earned.md", "Alpha", "x"), ("cold.md", "Alpha", "y")])
    earned_id = [n for n in g.nodes if n.startswith("earned")][0]
    col = Colony(label="t")
    col.tau = {f"cue:t{_SEP}{earned_id}": 2.0}
    g.colony = col
    _rotate(True)
    top, ex = _select(g, list(g.nodes), floor=0.05, cap=20, budget=5)
    assert [n.id for n in ex] == [i for i in g.nodes if i.startswith("cold")]
    assert any(n.id == earned_id for _t, _p, n in top)   # it exploits instead


# ---- the explore BLOCK cap still bounds the payload after rotation ----
def test_block_cap_still_bounds_the_payload():
    import exocortex.wiki.splice as SP
    g = _graph([("big.md", f"Alpha{i}", "x") for i in range(50)])
    _rotate(True)
    _top, ex = _select(g, list(g.nodes), floor=0.05, cap=20, budget=5)
    assert len(ex) <= SP.EXPLORE_BLOCK_CAP


# ---- the LIVE splice path persists the ledger; the read-only MCP path (explore=0) must not ----
def test_live_splice_writes_the_ledger_and_readonly_path_does_not():
    import json
    import shutil
    import tempfile

    from exocortex.wiki.splice import splice_payload, splice_with_ids
    sd = Path(tempfile.mkdtemp(prefix="offers_"))
    old = os.environ.get("EXOCORTEX_STATE_DIR")
    os.environ["EXOCORTEX_STATE_DIR"] = str(sd)
    try:
        g = _graph([("a.md", "Alpha", "x"), ("b.md", "Alpha", "y")])
        _rotate(True)
        text, ids = splice_with_ids(g, list(g.nodes), explore=2)
        assert text and ids
        ledger = sd / "wiki_offers.json"
        assert ledger.exists()
        offers = json.loads(ledger.read_text(encoding="utf-8"))
        assert offers == {"a.md": 1, "b.md": 1}

        splice_with_ids(g, list(g.nodes), explore=2)             # a second splice accumulates
        assert json.loads(ledger.read_text(encoding="utf-8")) == {"a.md": 2, "b.md": 2}

        # RENDERING must never mutate state: splice_payload explores here (explore=2) yet writes nothing.
        # Before this guard, running the test suite polluted the repo's own live wiki_offers.json.
        splice_payload(g, list(g.nodes), explore=2)
        assert json.loads(ledger.read_text(encoding="utf-8")) == {"a.md": 2, "b.md": 2}
    finally:
        if old is None:
            os.environ.pop("EXOCORTEX_STATE_DIR", None)
        else:
            os.environ["EXOCORTEX_STATE_DIR"] = old
        shutil.rmtree(sd, ignore_errors=True)


# ---- declarative.exclude: drop a frozen duplicate corpus under EITHER ingest boundary ----
def _vault(paths) -> Path:
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="vault_"))
    for rel in paths:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# H\n\nbody\n", encoding="utf-8")
    return root


def test_exclude_drops_a_frozen_snapshot_tree():
    import shutil

    from exocortex.wiki.store import _md_files
    root = _vault(["docs/ADR.md", "README.md",
                   "results/run_v1/ab_snap/docs/ADR.md", "results/run_v1/ab_snap/README.md"])
    try:
        assert len(_md_files(root, "all", exclude=[])) == 4
        kept = _md_files(root, "all", exclude=["results/*/ab_snap/*"])
        rels = sorted(p.relative_to(root).as_posix() for p in kept)
        assert rels == ["README.md", "docs/ADR.md"]          # the live docs survive, the snapshot does not
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exclude_applies_under_the_tracked_boundary_too():
    """A frozen snapshot is just as duplicated whether or not git tracks it."""
    import shutil
    import subprocess

    from exocortex.wiki.store import _md_files
    root = _vault(["docs/ADR.md", "results/run_v1/ab_snap/docs/ADR.md"])
    try:
        for cmd in (["init", "-q"], ["add", "-A"]):
            subprocess.run(["git", "-C", str(root)] + cmd, capture_output=True, timeout=20)
        tracked = _md_files(root, "tracked", exclude=[])
        if len(tracked) != 2:
            import pytest
            pytest.skip("git unavailable — the tracked boundary falls open by design")
        kept = _md_files(root, "tracked", exclude=["results/*/ab_snap/*"])
        assert [p.relative_to(root).as_posix() for p in kept] == ["docs/ADR.md"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exclude_defaults_to_empty_and_reads_the_env():
    """Ships conservative (ADR-003): no patterns unless a repo opts in."""
    import shutil

    from exocortex.config import declarative_exclude
    from exocortex.wiki.store import _md_files
    root = _vault(["a.md", "skip/b.md"])
    old = os.environ.get("EXOCORTEX_WIKI_EXCLUDE")
    try:
        os.environ.pop("EXOCORTEX_WIKI_EXCLUDE", None)
        assert declarative_exclude() == []
        assert len(_md_files(root, "all")) == 2              # nothing excluded by default
        os.environ["EXOCORTEX_WIKI_EXCLUDE"] = "skip/*"
        assert declarative_exclude() == ["skip/*"]
        assert [p.name for p in _md_files(root, "all")] == ["a.md"]
    finally:
        if old is None:
            os.environ.pop("EXOCORTEX_WIKI_EXCLUDE", None)
        else:
            os.environ["EXOCORTEX_WIKI_EXCLUDE"] = old
        shutil.rmtree(root, ignore_errors=True)


def test_walk_prunes_instead_of_filtering_and_matches_rglob():
    """The exclusion must skip the subtree, not walk it and discard the results — and apart from the
    always-pruned build dirs the file set must equal the old rglob path exactly."""
    import shutil

    from exocortex.wiki.store import _ALWAYS_PRUNE, _md_files
    root = _vault(["a.md", "docs/b.md", "results/r1/ab_snap/docs/b.md",
                   ".git/hooks/note.md", "node_modules/pkg/readme.md", "__pycache__/x.md"])
    try:
        got = {p.relative_to(root).as_posix() for p in _md_files(root, "all",
                                                                 exclude=["results/*/ab_snap/*"])}
        assert got == {"a.md", "docs/b.md"}
        rglob = {p.relative_to(root).as_posix() for p in root.rglob("*.md") if p.is_file()}
        expect = {r for r in rglob
                  if "ab_snap/" not in r and not any(seg in _ALWAYS_PRUNE for seg in r.split("/"))}
        assert got == expect                            # equivalence with the pre-fix discovery
        assert rglob - got >= {".git/hooks/note.md", "node_modules/pkg/readme.md"}   # prune list in force
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_residue_is_not_declarative_memory():
    """`.pytest_cache/README.md` was being digested as a note. Build residue is not memory."""
    import shutil

    from exocortex.wiki.store import _md_files
    root = _vault(["real.md", ".pytest_cache/README.md", ".ruff_cache/x.md"])
    try:
        assert [p.name for p in _md_files(root, "all")] == ["real.md"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_exclude_changes_the_vault_signature():
    """Excluding must invalidate the digest cache, or a stale 194k-node cache would outlive the config."""
    import shutil

    from exocortex.wiki.store import _md_files, _signature
    root = _vault(["a.md", "skip/b.md"])
    try:
        wide = _signature(root, _md_files(root, "all", exclude=[]))
        narrow = _signature(root, _md_files(root, "all", exclude=["skip/*"]))
        assert wide != narrow
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
