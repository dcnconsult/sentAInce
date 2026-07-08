"""Read-only memory MCP server (T2 entry point). The load-bearing property: RETRIEVAL CREATES NO MEMORY —
querying never deposits τ, never persists the cue classifier, never mutates a colony. Desktop consumes;
only a verified exit-0 (Code side) earns. (The derived wiki digest cache is excluded — it's a cache, not
memory.)"""
import pytest

# The read-only MCP server (T2) needs the optional `mcp` extra. Skip cleanly when it is absent (e.g. a lean
# `numpy + pytest` environment) instead of erroring collection — the extra is exercised where it is installed.
pytest.importorskip("mcp")

from exocortex import mcp_server
from exocortex.colony import Colony, MIN_DEPOSITS_TO_SPLICE, _SEP
from exocortex.cue_classifier import CueClassifier


def _plant_colony(prompt, edges):
    """Seed a converged colony under the label the classifier assigns to `prompt`, and persist the cue map
    (state dir comes from EXOCORTEX_STATE_DIR, set by the caller)."""
    cc = CueClassifier()
    label = cc.classify(prompt)["label"]
    cc.save()
    col = Colony(label=label)
    col.tau = {f"{a}{_SEP}{b}": w for a, b, w in edges}
    col.deposits = MIN_DEPOSITS_TO_SPLICE + 1
    col.save()
    return label


def test_recall_procedural_returns_earned_route(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    prompt = "run pytest and build the project"
    _plant_colony(prompt, [("bash:pytest", "Edit:src", 0.9), ("Edit:src", "bash:git", 0.5)])

    out = mcp_server.recall_procedural(prompt)
    assert "consequence-sourced procedural memory" in out
    assert "bash:pytest" in out
    # an unmatched / novel task abstains honestly (no fabricated memory)
    assert "abstains" in mcp_server.recall_procedural("zzz unrelated nonsense about turtles and clouds")


def test_retrieval_creates_no_memory(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    _plant_colony("deploy the service to staging", [("bash:kubectl", "Edit:other", 0.8)])

    def snap():   # every persisted MEMORY file (exclude the derived wiki cache)
        return {p.name: p.read_bytes() for p in state.glob("*.json") if "cache" not in p.name}

    before = snap()
    mcp_server.recall_procedural("deploy the service to staging")
    mcp_server.recall_procedural("a totally novel unseen query")   # would seed+save a class IF we saved
    mcp_server.memory_status()
    assert snap() == before        # colony_*.json + cues.json byte-identical → retrieval earned nothing


def test_recall_notes_warms_then_abstains_and_status_never_blocks(tmp_path, monkeypatch):
    import time
    state = tmp_path / "state"; state.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    (vault / "build.md").write_text("# Build\n\nRun `pytest -q` to verify.\n", encoding="utf-8")
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))

    monkeypatch.delenv("EXOCORTEX_WIKI_VAULT", raising=False)
    assert "no declarative vault" in mcp_server.recall_notes("build")

    monkeypatch.setenv("EXOCORTEX_WIKI_VAULT", str(vault))
    # memory_status NEVER digests → returns immediately even before the vault has warmed
    st = mcp_server.memory_status()
    assert "earned memory" in st and "goal-classes" in st

    # recall_notes warms the vault in the BACKGROUND, then abstains honestly (un-credited vault, no τ)
    out = ""
    for _ in range(80):
        out = mcp_server.recall_notes("how do I build")
        if "warming" not in out:
            break
        time.sleep(0.05)
    assert "abstains" in out or "empty" in out                # never a crash, never a block

    st2 = mcp_server.memory_status()                          # now warmed → reports node count
    assert "nodes" in st2


def test_multi_repo_list_and_select(tmp_path, monkeypatch):
    proot = tmp_path / "projects"
    (proot / "RepoA" / ".claude" / "exocortex").mkdir(parents=True)
    (proot / "RepoB" / ".claude" / "exocortex").mkdir(parents=True)
    # plant a converged colony in RepoA (single-repo mode while planting)
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(proot / "RepoA" / ".claude" / "exocortex"))
    _plant_colony("build and test repo a", [("bash:pytest", "Edit:src", 0.9), ("Edit:src", "bash:git", 0.5)])

    # switch to MULTI-repo mode (scan the projects root)
    monkeypatch.delenv("EXOCORTEX_STATE_DIR", raising=False)
    monkeypatch.setenv("EXOCORTEX_PROJECTS_ROOT", str(proot))

    lst = mcp_server.list_repos()
    assert "RepoA" in lst and "RepoB" in lst                       # both discovered
    assert "pass repo=" in mcp_server.recall_procedural("build and test repo a")  # ambiguous w/o repo=
    out = mcp_server.recall_procedural("build and test repo a", repo="RepoA")
    assert "bash:pytest" in out                                    # explicit repo → its earned route
    assert "not found" in mcp_server.recall_procedural("anything", repo="NoSuch")
    assert "RepoA" in mcp_server.memory_status(repo="RepoA")


def test_note_anchors_ranks_md_nodes_only():
    from exocortex.colony import Colony, _SEP
    col = Colony(tau={f"docs/a.md#1{_SEP}docs/b.md#2": 0.4,     # a.md incident 0.4, b.md incident 0.4+0.9
                      f"docs/b.md#2{_SEP}cue:c": 0.9,
                      f"Read:src{_SEP}bash:pytest": 2.0})        # procedural — no '.md' → excluded
    anchors = mcp_server._note_anchors(col)
    assert [a for a, _ in anchors] == ["docs/b.md#2", "docs/a.md#1"]   # ranked by incident τ
    assert all(".md" in a for a, _ in anchors)


def test_memory_status_marks_credited_note_count(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    from exocortex.colony import Colony, _SEP
    col = Colony(label="declcls")
    col.tau = {f"docs/a.md#1{_SEP}docs/b.md#2": 0.9, f"docs/b.md#2{_SEP}cue:declcls": 0.5}
    col.deposits = 3
    col.save()
    assert "[notes:2]" in mcp_server.memory_status()           # two distinct .md anchors credited


def test_recall_notes_cls_empty_query_returns_credited_notes_directly(tmp_path, monkeypatch):
    import time
    state = tmp_path / "state"; state.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    (vault / "build.md").write_text("# Build\n\nRun pytest to verify the WIDGET.\n", encoding="utf-8")
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.setenv("EXOCORTEX_WIKI_VAULT", str(vault))
    monkeypatch.setenv("EXOCORTEX_WIKI_INGEST", "all")
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    # warm the vault graph (background digest), then read back a real node id
    for _ in range(80):
        if "warming" not in mcp_server.recall_notes("warm me", cls="seed"):
            break
        time.sleep(0.05)
    graph = mcp_server._GRAPHS[(str(vault), "all")][1]
    from exocortex.colony import Colony, _SEP
    col = Colony(label="buildcls")
    col.tau = {f"{nid}{_SEP}cue:buildcls": 0.9 for nid in graph.nodes}   # credit every build.md node
    col.deposits = 3
    col.save()
    out = mcp_server.recall_notes("", cls="buildcls")          # empty query + cls → DIRECT credited recall
    assert "WIDGET" in out                                     # the credited note body is returned, no lexical guess
    assert "abstains" in mcp_server.recall_notes("", cls="uncredited")   # an un-credited class still abstains


def test_cls_targets_a_known_class_deterministically(tmp_path, monkeypatch):
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    _plant_colony("seed prompt for a class", [("bash:make", "Edit:src", 0.9), ("Edit:src", "bash:make", 0.5)])
    from exocortex.colony import Colony
    target = Colony.all()[0].label
    # cls= bypasses the opaque semantic classifier — an UNRELATED task string still hits the named class
    out = mcp_server.recall_procedural("totally unrelated words xyz", cls=target)
    assert "consequence-sourced procedural memory" in out and "bash:make" in out


def test_recall_for_prompt_cls_passthrough_composes_direct_paths(tmp_path, monkeypatch):
    """D5: with cls= the wrapper addresses the class DETERMINISTICALLY — route via cls, notes via
    cls + EMPTY query (the deliberate direct path) — never the semantic classifier / lexical guess."""
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    label = _plant_colony("guide accrue the memory",
                          [("cue:g", "battle/README.md#abc", 1.2), ("battle/README.md#abc", "bash:pytest", 0.6)])
    seen = {}
    real_notes = mcp_server.recall_notes

    def spy_notes(query, repo="", cls=""):
        seen["notes"] = {"query": query, "cls": cls}
        return real_notes(query=query, repo=repo, cls=cls)

    monkeypatch.setattr(mcp_server, "recall_notes", spy_notes)
    out = mcp_server.recall_for_prompt("totally unrelated free text", cls=label)
    assert seen["notes"] == {"query": "", "cls": label}          # the direct-notes path, not lexical
    assert "consequence-sourced procedural memory" in out        # route returned despite unrelated prompt
    assert "battle/README.md#abc" in out


def test_recall_for_prompt_surfaces_credited_notes_hint_on_lexical_miss(tmp_path, monkeypatch):
    """D6: when the notes half abstains but the prompt's class DOES carry credited notes, the wrapper
    must say so (and how to fetch them) — never silently return route-only."""
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    monkeypatch.delenv("EXOCORTEX_WIKI_VAULT", raising=False)    # no vault → notes abstains "(...)"
    prompt = "work on the guide accrual arc"
    label = _plant_colony(prompt,
                          [("cue:ga", "docs/GUIDE.md#h1", 1.5), ("docs/GUIDE.md#h1", "bash:pytest", 0.7)])
    out = mcp_server.recall_for_prompt(prompt)
    assert "consequence-sourced procedural memory" in out        # the route half
    assert "τ-credited note" in out and label in out             # the D6 hint names class + count
    assert 'cls="' in out                                        # ...and the retrieval path


# ---- read-side enhancements (2026-07 pre-push; all provably read-only) ----
def test_resolve_repo_nearest_name():
    """Item 4: memory_status("acme") must resolve Acme_Research. Case/prefix/substring tolerant, but only
    when UNambiguous; a tie or a miss returns None (caller then lists candidates). Name resolution only."""
    repos = [{"name": "Acme_Research"}, {"name": "SentAInce"}, {"name": "sentaince-fork"}]
    R = mcp_server._resolve_repo
    assert R("Acme_Research", repos)["name"] == "Acme_Research"         # exact
    assert R("acme_research", repos)["name"] == "Acme_Research"         # case-insensitive exact
    assert R("acme", repos)["name"] == "Acme_Research"                  # unique prefix (the papercut)
    assert R("Resea", repos)["name"] == "Acme_Research"                 # unique substring
    assert R("SentAInce", repos)["name"] == "SentAInce"                 # exact wins over the fork's substring
    assert R("sent", repos) is None                                     # ambiguous prefix → None (lists later)
    assert R("nope", repos) is None                                     # miss → None
    assert R("", [{"name": "only"}])["name"] == "only"                  # empty + sole repo → that repo
    assert R("", repos) is None                                         # empty + many → None


def test_warming_note_counts_files(tmp_path):
    """Item 3: the warming note carries a cheap file count (read-only — no digest, no body reads)."""
    vault = tmp_path / "vault"; vault.mkdir()
    for i in range(4):
        (vault / f"n{i}.md").write_text("# note\n", encoding="utf-8")
    (vault / "notmd.txt").write_text("ignore", encoding="utf-8")
    note = mcp_server._warming_note(str(vault), "all")
    assert "warming" in note and "~4" in note


def test_memory_diff_snapshot_then_delta_is_read_only(tmp_path, monkeypatch):
    """Item 1: lock a baseline, then a new deposit shows as a delta. And memory_diff itself writes no store."""
    state = tmp_path / "state"; state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    mcp_server._MEM_BASELINES.clear()
    _plant_colony("build the widget", [("bash:make", "Edit:src", 0.9)])

    def snap_files():
        return {p.name: p.read_bytes() for p in state.glob("*.json") if "cache" not in p.name}

    locked = mcp_server.memory_diff(mode="snapshot")
    assert "baseline locked" in locked
    before = snap_files()

    # earn a new deposit in a fresh class (the "work" between baseline and re-read)
    from exocortex.colony import Colony, MIN_DEPOSITS_TO_SPLICE, _SEP
    col = Colony(label="fresh-class#9")
    col.tau = {f"cue:x{_SEP}bash:deploy": 1.0}
    col.deposits = MIN_DEPOSITS_TO_SPLICE + 3
    col.save()

    out = mcp_server.memory_diff()
    assert "changes since baseline" in out
    assert "NEW class fresh-class#9" in out
    # memory_diff must not have written any memory file (only the planted+manual saves changed state)
    after = snap_files()
    assert set(after) - set(before) == {"colony_fresh-class_9.json"}   # only OUR save, not memory_diff's


def test_cli_transport_flag_defaults_and_choices(monkeypatch):
    """The transport flag is additive: no args ⇒ stdio (every existing install unchanged); the remote
    transports parse with their bind settings; junk is rejected. Parsing only — nothing binds a port."""
    monkeypatch.delenv("SENTAINCE_MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("SENTAINCE_MCP_HOST", raising=False)
    monkeypatch.delenv("SENTAINCE_MCP_PORT", raising=False)

    args = mcp_server._parse_args([])
    assert (args.transport, args.host, args.port) == ("stdio", "127.0.0.1", 8001)

    args = mcp_server._parse_args(["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"])
    assert (args.transport, args.host, args.port) == ("streamable-http", "0.0.0.0", 9000)

    monkeypatch.setenv("SENTAINCE_MCP_TRANSPORT", "sse")     # env default honored, flag still wins
    assert mcp_server._parse_args([]).transport == "sse"
    assert mcp_server._parse_args(["--transport", "stdio"]).transport == "stdio"

    with pytest.raises(SystemExit):
        mcp_server._parse_args(["--transport", "carrier-pigeon"])
