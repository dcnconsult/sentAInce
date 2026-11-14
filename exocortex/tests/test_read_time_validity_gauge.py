"""Read-time validity gauge (avenue 3 / R4b) — offline, read-only. Controls for PREREG §3–§5."""
import json
import os
import shutil
import subprocess

import pytest

from exocortex.gauge import read_time_validity_gauge as g

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(root), *args],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _repo(tmp_path):
    """A repo where `tools/old.py` and `Makefile` were committed, then deleted; `tools/new.py` exists."""
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    (root / "docs").mkdir()
    for rel in ("tools/old.py", "tools/new.py", "Makefile", "docs/guide.md"):
        (root / rel).write_text("x\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    (root / "tools" / "old.py").unlink()
    (root / "Makefile").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "remove")
    return root


def test_extraction_normalizes_and_drops_by_the_frozen_rule():
    text = ("Run `python tools/new.py --x` then see [guide](../docs/guide.md#top) and `colony.py:42`. "
            "Also `python -m pkg.mod`, `./scripts/run.sh`, `results/v1/`, `test_x.py::test_a`.\n"
            "Not: `https://x.io/a.py`, `D:/data/a.py`, `/etc/a.py`, `$HOME/a.py`, `src/*.py`, "
            "`feat/close-gaps`, `bash:make`, `self.tau`, `user@host.py`.")
    got = {c for cs in g.extract_citations(text) for c in cs}
    assert {"tools/new.py", "../docs/guide.md", "colony.py", "scripts/run.sh", "results/v1/",
            "test_x.py", "pkg/mod.py", "pkg/mod/"} <= got
    for bad in ("https://x.io/a.py", "D:/data/a.py", "/etc/a.py", "$HOME/a.py", "src/*.py",
                "feat/close-gaps", "bash:make", "self.tau", "user@host.py"):
        assert bad not in got


def test_classify_present_vanished_unresolved(tmp_path):
    root = _repo(tmp_path)
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "node_modules" / "pkg" / "old.py").write_text("x\n", encoding="utf-8")   # pruned: never "present"
    idx = g.RepoIndex(root)
    assert idx.classify(("tools/new.py",)) == "present"
    assert idx.classify(("new.py",)) == "present"                    # bare basename
    assert idx.classify(("repo_prefix/tools/new.py",)) == "unresolved"
    assert idx.classify(("TOOLS/NEW.PY",)) == "present"              # case-insensitive (Windows)
    assert idx.classify(("new.py",), doc_dir="tools") == "present"   # doc-relative
    assert idx.classify(("../tools/new.py",), doc_dir="docs") == "present"
    assert idx.classify(("tools/old.py",)) == "vanished"             # committed, then deleted
    assert idx.classify(("old.py",)) == "vanished"
    assert idx.classify(("tools/never.py",)) == "unresolved"         # never tracked → never counted
    assert idx.classify(("../outside.py",)) is None                  # resolves outside the repo → dropped
    assert idx.classify(("pkg/mod.py", "tools/")) == "present"       # any candidate present wins


def _state(root, colonies, offers=None, config=None):
    st = root / ".claude" / "exocortex"
    st.mkdir(parents=True)
    for i, c in enumerate(colonies):
        (st / f"colony_c{i}.json").write_text(json.dumps(c), encoding="utf-8")
    if offers is not None:
        (st / "wiki_offers.json").write_text(json.dumps(offers), encoding="utf-8")
    (root / "exocortex_config.json").write_text(json.dumps(config or {}), encoding="utf-8")


def test_declarative_lanes_measure_a_planted_vanished_citation(tmp_path):
    root = _repo(tmp_path)
    (root / "docs" / "ops.md").write_text(
        "# Ops\n\nRun `tools/old.py` first.\n\n## Next\n\nThen `tools/new.py`, not `tools/never.py`.\n", encoding="utf-8")
    (root / "docs" / "clean.md").write_text("# Clean\n\nUse `tools/new.py`.\n", encoding="utf-8")
    nodes = g.digest_now(root, {"vault_path": str(root)})
    ops = sorted((n for n in nodes if n.id.startswith("docs/ops.md#")), key=lambda n: n.span)
    bad_id = next(n.id for n in ops if "old.py" in n.text)
    good_id = next(n.id for n in ops if "new.py" in n.text)
    clean_id = next(n.id for n in nodes if n.id.startswith("docs/clean.md#"))
    tau = {f"cue:x\t{bad_id}": 0.5, f"cue:x\t{good_id}": 1.5, "cue:x\tdocs/gone.md#abcdef": 1.0,
           f"cue:x\t{clean_id}": 0.01}                               # below the splice floor: not credited
    _state(root, [{"label": "x", "deposits": 3, "tau": tau}],
           offers={"docs/ops.md": 3, "docs/clean.md": 1, "docs/deleted.md": 5},
           config={"declarative": {"mode": "live", "vault_path": str(root), "explore_budget": 5}})
    out, flagged, _ = g.run_store(root)
    d = out["declarative"]
    assert out["declarative_serving"] is True
    assert d["D1"]["present"] == 2 and d["D1"]["orphans"] == 1       # gone.md id already invalidated
    assert d["D1"]["V1"] == 0.5 and d["D1"]["V1_tau_weighted"] == 0.25   # unresolved never.py not counted
    assert d["D1"]["citations"] == {"vanished": 1, "present": 1, "unresolved": 1}
    ops_share = sum(1 for n in nodes if n.id.startswith("docs/ops.md#") and "old.py" in n.text) / \
        sum(1 for n in nodes if n.id.startswith("docs/ops.md#"))
    assert d["D2"]["present_docs"] == 2 and d["D2"]["gone_docs"] == 1 and d["D2"]["gone_offers"] == 5
    assert d["D2"]["V2"] == round(3 * ops_share / 4, 4)
    assert d["D2"]["U2"] == 0.75
    assert (bad_id, "tools/old.py") in flagged
    assert all(c != "tools/never.py" for _, c in flagged)


def test_not_serving_when_explore_off_and_nothing_credited(tmp_path):
    root = _repo(tmp_path)
    _state(root, [{"label": "x", "deposits": 3, "tau": {"cue:x\tbash:git": 1.0}}],
           offers={"docs/guide.md": 9}, config={"declarative": {"mode": "live", "vault_path": str(root)}})
    out, flagged, _ = g.run_store(root)
    assert out["declarative_serving"] is False and out["declarative"] is None and flagged == []


def test_procedural_census_and_tau_floor(tmp_path):
    root = _repo(tmp_path)
    (root / "run.sh").write_text("x\n", encoding="utf-8")
    now = 2_000_000_000.0
    fresh, ancient = now - 1.0, now - 400 * 86400.0
    cols = [
        {"deposits": 5, "tau": {"cue:a\tbash:make": 2.0, "bash:make\tbash:run.sh": 1.0},
         "meta": {"cue:a\tbash:make": {"ts": fresh}}},
        {"deposits": 5, "tau": {"cue:b\tbash:git": 1.0}, "meta": {"cue:b\tbash:git": {"ts": ancient}}},
        {"deposits": 1, "tau": {"cue:c\tbash:npm": 9.0}},                # not servable (1 deposit)
    ]
    _state(root, cols)
    p = g.run_store(root, now=now)[0]["procedural"]
    assert p["servable_classes"] == 2 and p["classes_with_artifact_bound_node"] == 1
    assert p["artifact_nodes"] == {"vanished": 1, "present": 1}         # Makefile deleted; run.sh present
    assert p["tau_floor_classes"] == 1                                  # the 400-day-old route reads < 0.05


def test_artifact_of():
    assert g.artifact_of("bash:make") == ("manifest", ("makefile", "gnumakefile"))
    assert g.artifact_of("ps:deploy.ps1") == ("script", ("deploy.ps1",))
    assert g.artifact_of("bash:python") is None and g.artifact_of("Edit:src") is None


def _store(v1=None, v2=None, n1=40, n2=40):
    return {"declarative": {"D1": {"evaluable": n1 >= 30, "V1": v1}, "D2": {"evaluable": n2 >= 30, "V2": v2}}}


def test_verdict_rule():
    two = {"a": _store(0.10, 0.0), "b": _store(None, 0.06, n1=5)}
    assert g.verdict(two)["pending"] == "precision audit"
    assert g.verdict(two, precision=0.75)["disposition"] == 1
    assert g.verdict(two, precision=0.60)["disposition"] == 0           # too noisy for a naive check
    assert g.verdict({"a": _store(0.10, 0.0), "b": _store(0.0, 0.0)})["disposition"] == 0
    assert g.verdict({"a": _store(0.005, 0.0), "b": _store(None, 0.009, n1=5)})["disposition"] == -1
    assert g.verdict({"a": {"declarative": None}})["disposition"] == 0  # nothing evaluable


def test_gauge_is_read_only(tmp_path):
    root = _repo(tmp_path)
    (root / "docs" / "ops.md").write_text("# Ops\n\nRun `tools/old.py`.\n", encoding="utf-8")
    _state(root, [{"deposits": 3, "tau": {"cue:x\tbash:git": 1.0}}], offers={"docs/ops.md": 2},
           config={"declarative": {"mode": "live", "vault_path": str(root), "explore_budget": 5}})
    before = {p: os.stat(p).st_mtime_ns for p in root.rglob("*") if ".git" not in p.parts}
    g.run_store(root)
    after = {p: os.stat(p).st_mtime_ns for p in root.rglob("*") if ".git" not in p.parts}
    assert before == after
