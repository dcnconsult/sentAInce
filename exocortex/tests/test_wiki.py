"""Ticket-1 sure-win loop — the immutable physical invariants (NEXT_PHASE_PLAN §6).

Crystallizes the B1–B4 + safety smoke into permanent tests, bound to the VERIFIED API:
  * matter vs earned-state split — τ in the `Colony` dict, σ in `WikiGraph.scars`, phasors lazy.
  * the crown jewel — only a closed exit-0 chain deposits τ; retrieval never does.
  * the safety law — a plain POSIX exit-1 deposits nothing and drops NO immortal σ.
  * the lane law — the forage/splice hot path never imports numpy (proven in a clean subprocess).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from exocortex.colony import _SEP, Colony
from exocortex.wiki import digest as digest_mod
from exocortex.wiki.digest import digest_document, shred
from exocortex.wiki.attribute import attribute_used, deposit_attributed, salient_tokens
from exocortex.wiki.node import ExonNode, WikiGraph
from exocortex.wiki.propose import propose
from exocortex.wiki.splice import EXPLORE_BUDGET, node_tau, splice_payload
from exocortex.wiki.wire import on_consequence

_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------- Digestive System (shred)
def test_digestive_cleavage_preserves_code_fence():
    """The shredder must NOT shatter a code block — blank lines inside a ``` fence stay whole."""
    raw = "P1\n\n```python\ndef foo():\n\n    return True\n```\n\nP2"
    blocks = [b.text for b in shred(raw)]
    assert blocks[0] == "P1"
    assert blocks[-1] == "P2"
    fenced = [b for b in blocks if "def foo()" in b]
    assert len(fenced) == 1, "code fence was split into multiple blocks"
    assert "def foo():\n\n    return True" in fenced[0], "blank line inside the fence was lost"


def test_digest_headings_links_and_content_identity():
    """Heading stack tracked, [[link|alias]] resolved to the bare target, ids are content-identity."""
    raw = "# Arch\n\nThe gate is [[somatic-gate|the gate]] and [[colony]].\n\n## Sub\n\nLeaf."
    exons = digest_document("doc.md", raw)
    assert [e.heading_path for e in exons] == [("Arch",), ("Arch", "Sub")]
    assert exons[0].links == ("somatic-gate", "colony")           # alias dropped, order kept
    assert exons[0].id.startswith("doc.md#")                       # content-identity, not position
    # edit the text -> id changes (τ must be re-earned); identical text -> identical id
    assert digest_document("doc.md", raw)[0].id == exons[0].id
    assert digest_document("doc.md", raw.replace("Leaf.", "Changed."))[-1].id != exons[-1].id


# --------------------------------------------------------------- the lane law (numpy vacuum)
def test_hot_path_is_numpy_free():
    """CRITICAL INVARIANT: digest -> wire -> splice never wakes numpy. Run in a clean interpreter so
    the result is immune to whatever other suite modules have already imported."""
    code = (
        "import sys\n"
        "from exocortex.wiki.digest import digest_document\n"
        "from exocortex.wiki.wire import on_consequence\n"
        "from exocortex.wiki.splice import splice_payload\n"
        "from exocortex.wiki.propose import propose\n"
        "from exocortex.wiki.attribute import deposit_attributed\n"
        "from exocortex.wiki.node import WikiGraph\n"
        "g = WikiGraph()\n"
        "ns = digest_document('d.md', 'Run `pytest -q`.\\n\\nSecond para.')\n"
        "[g.add(n) for n in ns]\n"
        "deposit_attributed(g, [n.id for n in ns], 'pytest -q', 0, cue='cue:_vac', label='_vac', save=False)\n"
        "cands = propose(g, prompt='para', active_context=[ns[0].id])\n"
        "splice_payload(g, cands, explore=2)\n"
        "assert 'numpy' not in sys.modules, 'FATAL: numpy woke on the hot path'\n"
        "print('OK')\n"
    )
    env = dict(os.environ, PYTHONPATH=str(_ROOT))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(_ROOT), env=env)
    assert r.returncode == 0, f"hot-path vacuum failed:\nSTDOUT={r.stdout}\nSTDERR={r.stderr}"
    assert "OK" in r.stdout


# --------------------------------------------------------------- Bloodstream (consequence -> τ)
def _graph_with(*ids):
    g = WikiGraph()
    for nid in ids:
        g.add(ExonNode(id=nid, text=nid))
    g.colony = Colony(label="_test")     # pre-bound so on_consequence never touches disk
    return g


def test_exit1_deposits_nothing_and_drops_no_scar():
    """Safety: a plain exit-1 is failure, not lethality — no τ, and crucially NO immortal σ."""
    g = _graph_with("a", "b", "c")
    laid = on_consequence(g, ["a", "b", "c"], exit_code=1, label="_test", save=False)
    assert laid is False
    assert g.colony.tau == {}
    assert g.scars == set(), "exit-1 must not drop an immortal σ scar"


def test_exit0_deposits_tau_once_per_consequence():
    """Crown jewel + B2: one deposit call lays the trail's edges once (per-edge τ, not per-node)."""
    g = _graph_with("a", "b", "c")
    laid = on_consequence(g, ["a", "b", "c"], exit_code=0, label="_test", save=False)
    assert laid is True
    assert g.colony.deposits == 1                                  # exactly one consequence
    assert g.colony.tau == {f"a{_SEP}b": pytest.approx(1.0), f"b{_SEP}c": pytest.approx(1.0)}


def test_single_used_note_forms_no_edge():
    """A trail needs ≥2 distinct used notes to form a transition; a lone note deposits nothing."""
    g = _graph_with("a")
    assert on_consequence(g, ["a"], exit_code=0, label="_test", save=False) is False
    assert g.colony.tau == {}


# --------------------------------------------------------------- Transcriptome (splice)
def _spliceable():
    g = WikiGraph()
    g.add(ExonNode(id="intro", text="Intro Matter", span=(1, 1)))
    g.add(ExonNode(id="core", text="Core Logic", span=(5, 5)))
    g.add(ExonNode(id="outro", text="Outro Matter", span=(9, 9)))
    g.add(ExonNode(id="toxic", text="Toxic Matter", span=(7, 7)))
    g.colony = Colony(label="_test")
    # per-edge τ -> node_tau sums incident edges (each node edged to a sink not in candidates)
    g.colony.tau = {
        f"intro{_SEP}_sink": 0.01,    # starved (< PRUNE floor 0.05)
        f"core{_SEP}_sink": 0.90,     # survives
        f"outro{_SEP}_sink": 1.20,    # survives
        f"toxic{_SEP}_sink": 1.50,    # high τ but will be σ-scarred
    }
    g.scar("toxic")
    return g


def test_splice_floor_veto_and_chronological_reentrainment():
    """τ is the survival filter (prune sub-floor), σ is the Liver veto (silence scarred tissue even at
    high τ), and survivors are re-sorted to document order, not τ order."""
    g = _spliceable()
    payload = splice_payload(g, ["outro", "toxic", "intro", "core"])  # deliberately out of order
    assert "Intro Matter" not in payload, "Enzymes failed to prune below the τ floor"
    assert "Toxic Matter" not in payload, "Liver failed to honor the σ veto"
    assert "Core Logic" in payload and "Outro Matter" in payload
    assert payload.index("Core Logic") < payload.index("Outro Matter"), "doc order not restored"


def test_splice_abstains_into_silence():
    """With no consequence-verified τ, the splice injects NOTHING (the truest 0-well behavior)."""
    g = WikiGraph()
    g.add(ExonNode(id="n", text="Unverified."))
    g.colony = Colony(label="_test")
    assert splice_payload(g, ["n"]) == ""


def test_node_tau_sums_incident_edges():
    col = Colony(label="_t")
    col.tau = {f"x{_SEP}y": 0.3, f"z{_SEP}x": 0.4, f"p{_SEP}q": 9.0}
    assert node_tau(col, "x") == pytest.approx(0.7)               # source of x→y + dest of z→x
    assert node_tau(col, "absent") == 0.0
    assert node_tau(None, "x") == 0.0                             # fail-safe to abstain


# --------------------------------------------------------------- the Z3 adapter (bridge lane, B4)
def test_encode_phasor_adapter_does_not_collapse(monkeypatch):
    """B4: a real (not complex) embedding through ``_phase_of`` alone would collapse to ~2 labels; the
    fixed complex projection must yield a genuine 3-symbol Z3 phasor, deterministically. Tests the
    adapter math directly with a synthetic dense vector — no MiniLM load required."""
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(0)
    fake = rng.standard_normal(384)
    fake /= np.linalg.norm(fake)
    monkeypatch.setattr(digest_mod, "_dense_embed", lambda _text: fake)

    v = digest_mod.encode_phasor("anything")
    assert v is not None, "encoder failed (is the frozen kernel on the path?)"
    assert v.shape == (2048,) and v.dtype == np.int8
    assert len(set(v.tolist())) == 3, "phasor collapsed — real vector not lifted into Z3 phase space"
    assert (digest_mod.encode_phasor("anything") == v).all(), "encoding must be deterministic"


def test_encode_phasor_fail_open_without_embedder(monkeypatch):
    """If the embedder is unavailable the bridge lane stays dormant (None) — never raises."""
    monkeypatch.setattr(digest_mod, "_dense_embed", lambda _text: None)
    assert digest_mod.encode_phasor("anything") is None


# --------------------------------------------------------------- the Proposer (graze list)
def test_proposer_structural_spreading_activation():
    """From the active context, expand [[links]] across the graph (hippocampal place-field expansion)."""
    g = WikiGraph()
    a = digest_document("alpha.md", "Alpha note that links to [[beta]].")[0]
    b = digest_document("beta.md", "Beta content lives here.")[0]
    g.add(a)
    g.add(b)
    out = propose(g, prompt="", active_context=[a.id])
    assert b.id in out, "1st-degree [[link]] target was not proposed"


def test_proposer_lexical_reflex():
    """A note whose heading/doc tokens appear in the prompt is proposed (numpy-free)."""
    g = WikiGraph()
    n = digest_document("colony.md", "# Stigmergy\n\nPheromone deposits accrue here.")[0]
    g.add(n)
    assert n.id in propose(g, prompt="how does stigmergy converge")
    assert n.id not in propose(g, prompt="unrelated query about turtles")


def test_proposer_muscle_memory_floor_on_cold_prompt():
    """With no active context and no lexical hit, the top global-τ notes still surface (the skeleton)."""
    g = WikiGraph()
    for nid in ("m1", "m2"):
        g.add(ExonNode(id=nid, text=f"matter {nid}"))
    g.colony = Colony(label="_t")
    g.colony.tau = {f"m1{_SEP}m2": 0.9}
    out = propose(g, prompt="", active_context=[])
    assert "m1" in out and "m2" in out


def test_proposer_excludes_scarred_even_with_tau():
    """A σ-scarred note is never proposed, even if it carries τ."""
    g = WikiGraph()
    n = ExonNode(id="x#1", text="toxic but pheromoned")
    g.add(n)
    g.colony = Colony(label="_t")
    g.colony.tau = {f"x#1{_SEP}sink": 0.9}
    g.scar("x#1")
    assert "x#1" not in propose(g)


# --------------------------------------------------------------- bootstrap exploration (cold-start break)
def test_exploration_dormant_by_default():
    """The Genome default keeps exploration OFF — a cold wiki abstains into silence (status quo)."""
    assert EXPLORE_BUDGET == 0
    g = WikiGraph()
    ns = digest_document("doc.md", "First.\n\nSecond.\n\nThird.")
    for n in ns:
        g.add(n)
    g.colony = Colony(label="_t")
    assert splice_payload(g, [n.id for n in ns]) == ""


def test_exploration_breaks_cold_start_deadlock():
    """With a budget, sub-floor candidates inject as flagged UNVERIFIED tissue so they can earn first τ.
    The budget counts NOTES (documents): budget=1 admits doc_a whole and leaves doc_b out entirely."""
    g = WikiGraph()
    ns_a = digest_document("doc_a.md", "First block.\n\nSecond block.\n\nThird block.")
    ns_b = digest_document("doc_b.md", "Other note.")
    for n in ns_a + ns_b:
        g.add(n)
    g.colony = Colony(label="_t")                       # zero τ everywhere (a fresh wiki)
    cands = [n.id for n in ns_a + ns_b]
    payload = splice_payload(g, cands, explore=1)
    assert "UNVERIFIED" in payload
    assert payload.count("explore ·") == 3, "admitted note must deliver ALL its blocks"
    assert "First block." in payload and "Second block." in payload and "Third block." in payload
    assert "Other note." not in payload                 # second NOTE is beyond the budget


def test_exploration_note_atomic_never_partial():
    """The delivery-budget sizing law (DELIVERY_BUDGET_PROBE, 2026-07-08): a multi-block note is
    never split by the budget — pre-fix, budget=2 BLOCKS delivered 2 of 8 blocks of the conventions
    note and the task could not succeed. budget=1 NOTE must deliver every proposed block."""
    g = WikiGraph()
    text = "\n\n".join(f"Convention {i}: rule body {i}." for i in range(8))
    ns = digest_document("project_conventions.md", text)
    assert len(ns) == 8
    for n in ns:
        g.add(n)
    g.colony = Colony(label="_t")
    payload = splice_payload(g, [n.id for n in ns], explore=1)
    assert payload.count("explore ·") == 8, "partial-note starvation regressed"
    for i in range(8):
        assert f"Convention {i}:" in payload


def test_exploration_block_cap_bounds_payload(monkeypatch):
    """`explore_block_cap` is the stated byte bound — the ONE place a note may still truncate."""
    from exocortex.wiki import splice as sp
    monkeypatch.setattr(sp, "EXPLORE_BLOCK_CAP", 5)
    g = WikiGraph()
    ns = digest_document("big.md", "\n\n".join(f"Block {i}." for i in range(9)))
    for n in ns:
        g.add(n)
    g.colony = Colony(label="_t")
    payload = splice_payload(g, [n.id for n in ns], explore=1)
    assert payload.count("explore ·") == 5, "block cap must bound total explore blocks"


def test_exploration_skips_scarred_and_verified():
    """Exploration only offers genuinely un-earned tissue: never σ-scarred, never already-verified."""
    g = WikiGraph()
    g.add(ExonNode(id="ver", text="VERIFIED matter", span=(1, 1)))
    g.add(ExonNode(id="tox", text="TOXIC matter", span=(2, 2)))
    g.add(ExonNode(id="new", text="NEW matter", span=(3, 3)))
    g.colony = Colony(label="_t")
    g.colony.tau = {f"ver{_SEP}sink": 0.9}             # ver is verified (above floor)
    g.scar("tox")
    payload = splice_payload(g, ["ver", "tox", "new"], explore=5)
    assert "VERIFIED matter" in payload                # injected as a normal (τ) exon
    assert "TOXIC matter" not in payload               # σ veto holds in the explore channel too
    assert "NEW matter" in payload                     # the only genuine exploration candidate
    # 'ver' must appear as a verified exon, not in the exploratory section
    assert payload.index("VERIFIED matter") < payload.index("UNVERIFIED")
    assert payload.index("NEW matter") > payload.index("UNVERIFIED")


def test_proposer_dense_lift_reuses_embedding(monkeypatch):
    """Optional embed-mode lift: HDC overlap vs the phasor bank, reusing an already-computed embedding
    (no second MiniLM load). A query embedding equal to a node's ranks that node first."""
    np = pytest.importorskip("numpy")
    import hashlib

    def fake_embed(text):
        seed = int.from_bytes(hashlib.blake2b((text or "").encode(), digest_size=4).digest(), "big")
        v = np.random.default_rng(seed).standard_normal(64)
        return v / (np.linalg.norm(v) + 1e-9)

    monkeypatch.setattr(digest_mod, "_dense_embed", fake_embed)
    g = WikiGraph()
    n1 = ExonNode(id="d.md#1", text="alpha tissue")
    n2 = ExonNode(id="d.md#2", text="omega tissue")
    g.add(n1)
    g.add(n2)
    g.build_phasor_bank(digest_mod.encode_phasor)      # (2, 2048) Z3 bank via the (patched) encoder
    out = propose(g, prompt="", prompt_embedding=fake_embed("omega tissue"), k=2)
    assert out and out[0] == n2.id, "dense lift did not rank the matching node first"


def test_bootstrap_cycle_explore_then_crystallize():
    """The whole point of exploration: a note offered UNVERIFIED, then used in a closed exit-0 chain,
    crystallizes into VERIFIED tissue on the next splice — the cold-start deadlock, demonstrably broken."""
    g = WikiGraph()
    ns = digest_document("doc.md", "Alpha fact.\n\nBeta fact.")
    for n in ns:
        g.add(n)
    g.colony = Colony(label="_t")
    a, b = ns[0].id, ns[1].id

    # cold wiki: nothing verified → only the exploratory channel offers the notes
    p0 = splice_payload(g, [a, b], explore=2)
    assert "explore ·" in p0 and "exon ·" not in p0, "cold notes should be exploratory, not verified"

    # the LLM uses both explored notes and the chain closes exit 0 → they earn their first τ
    assert on_consequence(g, [a, b], exit_code=0, label="_t", save=False)

    # next splice: now injected as verified exons, no longer exploration
    p1 = splice_payload(g, [a, b], explore=2)
    assert "exon ·" in p1 and "UNVERIFIED" not in p1, "earned notes should crystallize as verified"
    assert "Alpha fact." in p1 and "Beta fact." in p1


# --------------------------------------------------------------- used-note attribution (#2)
def test_salient_tokens_are_code_and_paths_not_prose():
    """Distinctive tokens come from code (fenced/inline) + path/identifier tokens; plain prose yields none."""
    note = "Run the suite via `pytest -q` against src/main.py.\n\n```bash\nalembic upgrade head\n```"
    sal = salient_tokens(note)
    assert "pytest" in sal and "src/main.py" in sal and "alembic" in sal
    assert salient_tokens("The colony is the basal ganglia of the organism.") == set(), \
        "a prose-only note must have no salient tokens (→ never action-credited)"


def test_attribution_credits_actionable_echo_not_conceptual():
    """A note whose distinctive content appears in the action is 'used'; a conceptual note is not."""
    g = WikiGraph()
    g.add(ExonNode(id="act", text="Deploy with `alembic upgrade head`."))
    g.add(ExonNode(id="concept", text="Migrations evolve the schema over time."))
    used = attribute_used(g, ["act", "concept"], action_text="alembic upgrade head  # run migration")
    assert used == ["act"], "only the note echoed in the action should be credited"


def test_attribution_no_action_text_credits_nothing():
    g = WikiGraph()
    g.add(ExonNode(id="act", text="Run `pytest -q`."))
    assert attribute_used(g, ["act"], action_text="") == []


def test_attribution_skips_scarred_note():
    g = WikiGraph()
    g.add(ExonNode(id="act", text="Run `pytest -q`."))
    g.scar("act")
    assert attribute_used(g, ["act"], action_text="pytest -q") == []


def test_deposit_attributed_only_on_exit0_and_only_used():
    """The consequence law: exit-0 deposits τ on the used note only; exit-1 deposits nothing."""
    g = WikiGraph()
    g.add(ExonNode(id="used", text="Build with `make release`."))
    g.add(ExonNode(id="unused", text="An unrelated conceptual aside."))
    g.colony = Colony(label="_t")
    action = "make release && echo done"

    # exit-1 → nothing credited, no σ
    assert deposit_attributed(g, ["used", "unused"], action, 1, cue="cue:_t", label="_t", save=False) == []
    assert g.colony.tau == {} and g.scars == set()

    # exit-0 → only the echoed note earns τ (cue-rooted edge so a single used note still forms an edge)
    out = deposit_attributed(g, ["used", "unused"], action, 0, cue="cue:_t", label="_t", save=False)
    assert out == ["used"]
    assert node_tau(g.colony, "used") > 0.0
    assert node_tau(g.colony, "unused") == 0.0


def test_attribution_min_overlap_precision_lever():
    """Raising min_overlap demands more distinctive echo before crediting (precision knob)."""
    g = WikiGraph()
    g.add(ExonNode(id="n", text="Use `pytest` here."))             # one salient token: pytest
    assert attribute_used(g, ["n"], "pytest", min_overlap=1) == ["n"]
    assert attribute_used(g, ["n"], "pytest", min_overlap=2) == []


# --------------------------------------------------------------- live hook.py integration (#2)
def test_declarative_dormant_by_default(monkeypatch):
    """The organ ships OFF: no env, Genome mode 'off' → the live hook never touches the wiki."""
    monkeypatch.delenv("EXOCORTEX_DECLARATIVE", raising=False)
    from exocortex.config import declarative_enabled
    assert declarative_enabled() is False


def test_store_digest_cache_roundtrip(tmp_path, monkeypatch):
    """load_graph digests a vault, writes a signature-keyed cache, and reloads identical nodes from it."""
    from exocortex.wiki import store
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# Build\n\nRun `pytest -q`.\n", encoding="utf-8")

    g1 = store.load_graph(str(vault), label="_t")
    assert g1 is not None and g1.nodes
    assert (tmp_path / "state" / "wiki_cache.json").exists()
    g2 = store.load_graph(str(vault), label="_t")            # second load hits the cache
    assert sorted(g2.nodes) == sorted(g1.nodes)
    assert store.action_text_of("Bash", {"tool_input": {"command": "pytest -q"}}) == "pytest -q"
    assert "x.py" in store.action_text_of("Edit", {"tool_input": {"file_path": "x.py", "new_string": "c"}})
    assert store.load_graph("", label="_t") is None         # no vault → dormant (None)


def _git_init_repo(vault, track):
    """Init a hermetic git repo at ``vault`` and commit only ``track`` — nulls global/system config and
    supplies identity via env, so the test never depends on (or mutates) the dev's git setup."""
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for args in (("init",), ("add", *track), ("commit", "-m", "init")):
        subprocess.run(["git", "-C", str(vault), *args], check=True, capture_output=True, env=env)


def test_md_files_ingest_tracked_vs_all(tmp_path, monkeypatch):
    """T4 inclusion boundary (store._md_files): 'tracked' returns only git-tracked .md (respecting
    .gitignore AND excluding untracked files), 'all' returns every .md, and a non-git vault + 'tracked'
    falls OPEN to 'all' (the ADR-007 fail-open contract carried to the git subprocess)."""
    import shutil
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    from exocortex.wiki import store

    vault = tmp_path / "vault"
    (vault / "sub").mkdir(parents=True)
    (vault / "tracked.md").write_text("# T\n\nRun `pytest -q`.\n", encoding="utf-8")
    (vault / "sub" / "nested.md").write_text("# N\n\nRun `make ship`.\n", encoding="utf-8")
    (vault / "ignored.md").write_text("# I\n\njunk\n", encoding="utf-8")
    (vault / "untracked.md").write_text("# U\n\njunk\n", encoding="utf-8")
    (vault / ".gitignore").write_text("ignored.md\n", encoding="utf-8")

    everything = {"tracked.md", "nested.md", "ignored.md", "untracked.md"}
    assert {p.name for p in store._md_files(vault, "all")} == everything
    # not a git repo yet (pytest tmp dirs are not under a repo) → 'tracked' fails open to 'all'
    assert {p.name for p in store._md_files(vault, "tracked")} == everything

    _git_init_repo(vault, track=["tracked.md", "sub/nested.md"])
    # 'tracked' now excludes BOTH the gitignored and the merely-untracked file; 'all' is unchanged
    assert {p.name for p in store._md_files(vault, "tracked")} == {"tracked.md", "nested.md"}
    assert {p.name for p in store._md_files(vault, "all")} == everything

    # load_graph threads the mode through end-to-end and builds only from the tracked set
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    g = store.load_graph(str(vault), label="_t4", ingest="tracked")
    assert g is not None and g.nodes


def test_declarative_ingest_config(monkeypatch):
    """The accessor defaults to 'all' (committed-conservative, ADR-003) and honors the env override."""
    from exocortex.config import declarative_ingest
    monkeypatch.delenv("EXOCORTEX_WIKI_INGEST", raising=False)
    assert declarative_ingest() == "all"
    monkeypatch.setenv("EXOCORTEX_WIKI_INGEST", "TRACKED")   # normalized
    assert declarative_ingest() == "tracked"


def test_live_hook_bootstrap_then_crystallize(tmp_path, monkeypatch):
    """End-to-end through the real handlers: cold wiki → exploration injects UNVERIFIED → the model uses a
    note and closes exit-0 → next turn it crystallizes as a VERIFIED exon. The whole organ, wired."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "build.md").write_text(
        "# Build\n\nRun `make release` to ship.\n\n# Colors\n\nThe sky is blue.\n", encoding="utf-8")
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EXOCORTEX_WIKI_VAULT", str(vault))
    monkeypatch.setenv("EXOCORTEX_DECLARATIVE", "1")
    monkeypatch.setenv("EXOCORTEX_COLONY", "0")              # isolate the wiki; goal_class stays _default
    monkeypatch.setenv("EXOCORTEX_EMBED", "0")

    from exocortex import hook
    from exocortex.config import Mode
    from exocortex.wiki import splice as splice_mod
    monkeypatch.setattr(splice_mod, "EXPLORE_BUDGET", 5)     # enable bootstrap exploration for the run

    sid = "live1"
    out = hook.handle_userpromptsubmit({"session_id": sid, "prompt": "how do I build and release"}, Mode.OBSERVE)
    assert out, "cold wiki with exploration should inject"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "make release" in ctx and "UNVERIFIED" in ctx, "cold note should be offered as exploratory"

    hook._buffer_action(sid, "Bash", {"tool_input": {"command": "make release && echo ok"}})
    hook.handle_consequence(
        {"session_id": sid, "tool_name": "Bash", "tool_input": {"command": "make release && echo ok"},
         "tool_response": {"stdout": "ok"}}, Mode.OBSERVE, "ok")

    out2 = hook.handle_userpromptsubmit({"session_id": sid, "prompt": "build and release again"}, Mode.OBSERVE)
    assert out2, "the crystallized note should now splice"
    ctx2 = out2["hookSpecificOutput"]["additionalContext"]
    # the USED Build note now renders as a VERIFIED exon, no longer exploratory (the bootstrap closed)
    assert "exon · Build" in ctx2 and "make release" in ctx2, "used note should crystallize as verified"
    assert "explore · Build" not in ctx2, "a crystallized note must not be re-offered as exploratory"
