"""Consumer contracts (R6) — the SentAInce surface downstream control planes depend on.

Downstream tools import SentAInce modules, parse its stores, scrape its exporter, and in places COPY SentAInce
values instead of importing them (colony constants, `verb_node`, the chain formula). None of that was
versioned, so a SentAInce change could break a consumer silently. Each test below pins one consumed property
(the consumer surface was surveyed read-only on 2026-10-26).

A failure here is a contract change, not necessarily a bug. Make it deliberately: update the consumer in the
same change, and record it.
"""
import importlib
import inspect
import json
import re
from datetime import datetime

import pytest

from exocortex import audit, colony, genome, state
from exocortex.integrity import GENESIS, chain_hash


@pytest.fixture
def sd(tmp_path, monkeypatch):
    d = tmp_path / "proj" / ".claude" / "exocortex"
    d.mkdir(parents=True)
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(d))
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(d / "audit.jsonl"))
    monkeypatch.setenv("EXOCORTEX_AUDIT_CHAIN", "1")
    monkeypatch.setenv("EXOCORTEX_COLONY", "1")
    monkeypatch.setenv("EXOCORTEX_DECLARATIVE", "0")
    monkeypatch.delenv("EXOCORTEX_MODEL", raising=False)
    return d


def _rows(d):
    return [json.loads(ln) for ln in (d / "audit.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---------------------------------------------------------------- audit.jsonl records
# consumers: evidence exporters, outcome attribution, replay and event-prediction gauges
CONSUMED_FIELDS = {"session", "event", "tool", "command", "command_key", "outcome", "reason", "injected",
                   "output", "seg_len", "agent_id", "agent_type"}
CONSUMED_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure", "UserPromptSubmit", "SessionStart",
                   "PreCompact", "CircadianSleep"}


def test_audit_record_carries_every_consumed_field():
    r = audit.record(session="s", event="PostToolUse", mode="observe")
    assert CONSUMED_FIELDS <= set(r)
    assert not any(k.startswith("_") for k in r)   # one consumer strips `_` keys before hashing


def test_wiki_counts_are_ints_when_present():
    r = audit.record(session="s", event="PostToolUse", mode="observe", wiki_injected=2, wiki_used=1)
    assert r["wiki_injected"] == 2 and r["wiki_used"] == 1


def test_appended_records_carry_an_iso_ts_and_the_chain_fields(sd):
    audit.append(audit.record(session="s", event="SessionStart", mode="observe"))
    audit.append(audit.record(session="s", event="PostToolUse", mode="observe", outcome="ok"))
    a, b = _rows(sd)
    assert datetime.fromisoformat(a["ts"]) and datetime.fromisoformat(b["ts"])
    assert a["prev"] == GENESIS and b["prev"] == a["hash"]
    assert a["hash"] == chain_hash(a, a["prev"]) and b["hash"] == chain_hash(b, b["prev"])


def test_prompt_rows_carry_the_class_reason(sd):
    from exocortex.config import Mode
    from exocortex.hook import handle_userpromptsubmit
    handle_userpromptsubmit({"session_id": "s", "prompt": "run the unit tests for the parser"}, Mode.OBSERVE)
    row = next(r for r in _rows(sd) if r["event"] == "UserPromptSubmit")
    assert re.match(r"^class=(\S+)$", row["reason"])
    assert isinstance(row["injected"], bool)


def test_every_consumed_event_name_is_still_emitted():
    src = inspect.getsource(importlib.import_module("exocortex.hook"))
    for ev in CONSUMED_EVENTS:
        assert f'"{ev}"' in src, ev


def test_circadian_sleep_reason_keeps_its_parsed_shape():
    # a replay consumer parses `(\d+) classes consolidated` and hard-codes the 24 h window
    from exocortex import hook
    assert "{slept} classes consolidated" in inspect.getsource(hook)
    assert hook.CIRCADIAN_SLEEP_SECS == 24 * 3600


# ---------------------------------------------------------------- chain law (ADR-009)
# consumers import chain_hash AND carry local reimplementations (a fallback, a self-verifying bundle)
def _lab_formula(record: dict, prev: str) -> str:
    import hashlib
    payload = {k: v for k, v in record.items() if k not in ("prev", "hash")}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(f"{canonical}|{prev}".encode("utf-8")).hexdigest()


def test_chain_hash_golden_value():
    rec = {"session": "s", "event": "PostToolUse", "outcome": "ok", "ts": "2026-10-26T00:00:00+00:00",
           "seg_len": 1}
    assert GENESIS == "GENESIS"
    assert chain_hash(rec, GENESIS) == "a7deab663cdd462b0c417d9fd7b44369a152f86a90fd1185eb131f524317a9d9"


@pytest.mark.parametrize("rec", [{"a": 1}, {"command": "echo ünï", "n": None, "x": [1, {"y": 2}]},
                                 {"event": "E", "prev": "p", "hash": "h"}])
def test_chain_hash_matches_the_reimplemented_formula(rec):
    for prev in ("", GENESIS, "abc"):
        assert chain_hash(rec, prev) == _lab_formula(rec, prev)


# ---------------------------------------------------------------- colony_*.json stores
# consumers: an estate graph UI, export bundles, a profiler, a replay gauge
def test_colony_store_schema_and_separator(sd):
    assert colony._SEP == "\t"
    c = colony.Colony(label="build it")
    c.deposit([("cue:build it", "bash:pytest"), ("bash:pytest", "bash:git")], ts=1.0, model="m")
    c.save()
    c.consolidate()
    c.save()
    f = sd / f"colony_{colony._safe('build it')}.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    assert {"label", "tau", "deposits", "meta", "consolidations", "last_consolidated"} <= set(d)
    assert d["label"] == "build it" and isinstance(d["deposits"], int) and isinstance(d["consolidations"], int)
    assert all(k.count("\t") == 1 for k in d["tau"])
    assert all(set(m) == {"ts", "model"} for m in d["meta"].values())
    loaded = colony.Colony.load("build it")
    assert loaded.tau == d["tau"] and loaded.deposits == d["deposits"]


def test_safe_label_golden_values():
    # a profiler builds the filename with colony._safe
    assert colony._safe("stand-estate#188") == "stand-estate_188"
    assert colony._safe("a b/c") == "a_b_c"
    assert colony._safe("") == "_default"


# one consumer imports verb_node; two others COPY it
VERB_NODE_GOLDEN = [
    ("Bash", "cd repo && pytest -q", "bash:cd", "bash:pytest"),
    ("Bash", "PYTHONIOENCODING=utf-8 python x.py", "bash:PYTHONIOENCODING=utf-8", "bash:python"),
    ("Bash", "git status", "bash:git", "bash:git"),
    ("Bash", "", "bash:?", "bash:?"),
    ("PowerShell", "Get-ChildItem x", "ps:Get-ChildItem", "ps:Get-ChildItem"),
    ("Read", "src/a_test.py", "Read:test", "Read:test"),
    ("Edit", "pkg/mod.py", "Edit:src", "Edit:src"),
    ("Write", "README.md", "Write:other", "Write:other"),
]


@pytest.mark.parametrize("tool,payload,first,working", VERB_NODE_GOLDEN)
def test_verb_node_golden_table(tool, payload, first, working):
    assert colony.verb_node(tool, payload, keying="first") == first
    assert colony.verb_node(tool, payload, keying="working") == working


def test_values_the_lab_copies_instead_of_importing():
    # a replay consumer hard-codes these; another derives TAU_CEIL = DEPOSIT / (1 - DECAY)
    t = genome.DEFAULTS["thermodynamics"]
    assert (t["decay"], t["deposit_base_weight"], t["prune_floor"], t["max_edges_per_class"],
            t["session_discount_rate"], t["weight_min"]) == (0.9, 1.0, 0.05, 32, 0.8, 0.1)
    assert (state._TRAIL_CAP, state._HISTORY_CAP) == (24, 80)


# ---------------------------------------------------------------- exporter (:9109)
# consumers scrape exocortex_audit_records, read /api/repos, and drive apply_config
def test_audit_records_metric_line_shape(tmp_path):
    from exocortex.testbed.exporter import metrics as M
    d = tmp_path / ".claude" / "exocortex"
    d.mkdir(parents=True)
    (d / "audit.jsonl").write_text('{"event":"SessionStart"}\n{"event":"PreToolUse"}\n', encoding="utf-8")
    p = M.Prom({"repo": "r1"})
    M.collect_repo(p, d, {})
    lines = "\n".join(p.lines)
    m = re.search(r'^exocortex_audit_records\{repo="([^"]+)"\} ([0-9.]+)$', lines, re.M)
    assert m and m.group(1) == "r1" and float(m.group(2)) == 2


def test_api_repos_keys(tmp_path):
    from exocortex.testbed.exporter.metrics import repos_api
    out = repos_api([{"name": "r1", "root": tmp_path, "config_path": tmp_path / "exocortex_config.json",
                      "state_dir": tmp_path}])
    assert {"schema", "frozen_keys", "repos"} <= set(out)
    assert {"name", "tunable", "frozen"} <= set(out["repos"][0])


def test_apply_config_codes(tmp_path):
    from exocortex.testbed.exporter.metrics import apply_config
    code, body = apply_config(tmp_path, "integrity.mode", "off")
    assert code == 403 and "never web-writable" in body["error"]
    assert not (tmp_path / "exocortex_config.json").exists()       # a refused write leaves no file
    assert apply_config(tmp_path, "declarative.explore_budget", "not-a-number")[0] == 400
    assert apply_config(tmp_path, "declarative.explore_budget", 7)[0] == 200
    assert json.loads((tmp_path / "exocortex_config.json").read_text())["declarative"]["explore_budget"] == 7


# ---------------------------------------------------------------- plugin entry points
# a consumer registers a subcommand under `[project.entry-points."sentaince.commands"]`
def test_plugin_group_passes_the_argv_tail_and_returns_its_int(monkeypatch):
    import importlib.metadata as md
    from exocortex import cli
    seen = {}

    class EP:
        name = "plug"

        def load(self):
            return lambda argv: seen.setdefault("argv", argv) and 3

    def fake(group=None, **_):
        seen["group"] = group
        return [EP()]

    monkeypatch.setattr(md, "entry_points", fake)
    assert cli._dispatch_plugin("plug", ["a", "b"]) == 3
    assert seen == {"group": "sentaince.commands", "argv": ["a", "b"]}


# ---------------------------------------------------------------- imported names and call shapes
IMPORTED = {
    "exocortex.colony": ["verb_node", "DECAY", "DEPOSIT", "PRUNE", "_SEP", "_safe", "Colony"],
    "exocortex.integrity": ["chain_hash"],
    "exocortex.runner": ["_settings", "_read_audit", "_extract_result"],
    "exocortex.cue_classifier": ["THRESHOLD", "CueClassifier", "_featurize"],
    "exocortex.wiki.digest": ["digest_document"],
    "exocortex.wiki.propose": ["propose"],
    "exocortex.wiki.splice": ["splice_with_ids"],
    "exocortex.wiki.store": ["load_graph"],
    "exocortex.wiki.node": ["WikiGraph"],
    "exocortex.mcp_server": ["recall_notes", "memory_status", "list_repos"],
    "exocortex.testbed.exporter.metrics": ["apply_config", "collect", "collect_repo", "Prom"],
}


@pytest.mark.parametrize("mod", sorted(IMPORTED))
def test_imported_names_exist(mod):
    if mod == "exocortex.mcp_server":
        pytest.importorskip("mcp")          # optional extra: the MCP server is not importable without it
    m = importlib.import_module(mod)
    for name in IMPORTED[mod]:
        assert hasattr(m, name), f"{mod}.{name}"


def test_call_shapes_the_lab_uses():
    pytest.importorskip("mcp")          # optional extra: the MCP server is not importable without it
    from exocortex import mcp_server
    from exocortex.cue_classifier import CueClassifier
    from exocortex.wiki.store import load_graph
    assert {"label", "ingest"} <= set(inspect.signature(load_graph).parameters)
    assert {"query", "repo", "cls"} <= set(inspect.signature(mcp_server.recall_notes).parameters)
    for meth in ("load", "classify", "save", "_cos"):
        assert hasattr(CueClassifier, meth), meth


def test_wiki_cache_node_keys():
    # consumers read wiki_cache.json nodes
    from exocortex.wiki.digest import digest_document
    from exocortex.wiki.store import _node_to_dict
    (n,) = digest_document("ops.md", "# Ops\nRun `make build`.\n")
    assert {"id", "links", "heading_path", "span", "text"} <= set(_node_to_dict(n))


def test_mcp_text_shapes_the_lab_parses(tmp_path, monkeypatch):
    pytest.importorskip("mcp")          # optional extra: the MCP server is not importable without it
    from exocortex import mcp_server
    proot = tmp_path / "projects"
    d = proot / "RepoA" / ".claude" / "exocortex"
    d.mkdir(parents=True)
    (d / "colony_c.json").write_text(json.dumps({"label": "c", "tau": {"a\tb": 1.0}, "deposits": 3}))
    monkeypatch.delenv("EXOCORTEX_STATE_DIR", raising=False)
    monkeypatch.setenv("EXOCORTEX_PROJECTS_ROOT", str(proot))
    assert re.search(r"· RepoA:", mcp_server.list_repos())
    assert re.search(r"· c(?: \[notes:\d+\])?:", mcp_server.memory_status(repo="RepoA"))


# ---------------------------------------------------------------- private-monorepo surface (absent in the public tree)
def test_release_token_lists_are_string_iterables():
    # a consumer's export hygiene refuses to run when these cannot be imported
    dp = pytest.importorskip("release.denylist_private")
    man = pytest.importorskip("release.manifest")
    for toks in (dp.PRIVATE_TOKENS, man.DENYLIST_TOKENS):
        assert toks and all(isinstance(t, str) for t in toks)
