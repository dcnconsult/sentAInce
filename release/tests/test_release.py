"""Tests for the release boundary (ADR-011) — the is_public predicate + the fail-closed pre-push gates.

OUT of the 99-lock (``tests/`` only). Run explicitly:

    python -m pytest release/tests
    python release/tests/test_release.py
"""
from __future__ import annotations

import sys
import shutil
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]      # tests -> release -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from release import manifest as M                                  # noqa: E402
from release import prepush_gates as G                            # noqa: E402


# ---- the boundary predicate: community ships, commercial/private/cruft does not ----
def test_is_public_community():
    assert M.is_public("exocortex/colony.py")
    assert M.is_public("sentaince/organism/interlock.py")
    assert M.is_public("cerebral/journal.py")
    assert M.is_public("experiments/exp7_crucible.py")
    assert M.is_public("docs/ADR.md")
    assert M.is_public("LICENSE")


def test_is_public_commercial_and_private_excluded():
    assert not M.is_public("exocortex/tuner/policy.py")          # the paid brain
    assert not M.is_public("exocortex/tuner/emulator.py")
    assert not M.is_public("battle/twin_reporter.py")            # feasibility probe held private (no promotion)
    assert not M.is_public("battle/tests/test_twin_reporter.py")
    assert not M.is_public("results/twin_reporter_probe_v1/FINDINGS.md")
    assert M.is_public("battle/README.md")                       # ...but the rest of battle/ still ships
    assert not M.is_public("patent/PROVISIONAL_CLAIMS_DRAFT.md")  # never public
    assert not M.is_public("docs/INVESTOR_SUMMARY.md")
    assert not M.is_public("exocortex_config.json")
    assert not M.is_public("release/denylist_private.py")        # the tokens ARE the secrets
    assert not M.is_public(".agents/plugins/example/plugin.json")
    assert not M.is_public(".claude/settings.json")
    assert not M.is_public(".codex/config.toml")
    assert not M.is_public(".codex-tmp/session.json")
    assert not M.is_public("plugin-data/audit.jsonl")
    assert not M.is_public("AGENTS.md")
    assert not M.is_public("results/resurrection_gauge_v1/labels_completed.json")   # private-vault content
    assert not M.is_public("results/resurrection_gauge_v1/labels_template.json")
    # forward-looking IP docs (unfiled methods, patent-before-disclosure) are held whole
    assert not M.is_public("docs/ENHANCEMENTS.md")
    assert not M.is_public("docs/ROADMAP.md")
    assert not M.is_public("exocortex/docs/INVESTOR_OVERVIEW.md")
    assert not M.is_public("exocortex/docs/NEXT_PHASE_PLAN.md")
    # ...but the community-valuable, low-risk docs stay public
    assert M.is_public("docs/CLAIMS.md")
    assert M.is_public("docs/STORY.md")
    assert M.is_public("docs/WHITEPAPER.md")


def test_is_public_skips_cruft_and_unlisted():
    assert not M.is_public("exocortex/__pycache__/colony.cpython-314.pyc")
    assert not M.is_public("exocortex/colony.pyc")
    assert not M.is_public(".git/config")
    assert not M.is_public("some_new_toplevel_dir/thing.py")     # allowlist: private-by-default


# ---- gate: no commercial/private path leaks into the public set ----
def test_gate_no_commercial():
    good = G.gate_no_commercial(["exocortex/colony.py", "cerebral/journal.py"])
    assert good["ok"] is True
    leaked = G.gate_no_commercial(["exocortex/colony.py", "exocortex/tuner/policy.py"])
    assert leaked["ok"] is False and "exocortex/tuner/policy.py" in leaked["detail"]


# ---- gate: patent flag is the hard gate (fails without the marker, passes with it) ----
def test_gate_patent():
    root = Path(tempfile.mkdtemp(prefix="rel_patent_"))
    try:
        assert G.gate_patent(root)["ok"] is False                # no marker → BLOCKED
        flag = root / M.PATENT_GATE_FLAG
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("filed 2026-XX-XX", encoding="utf-8")
        assert G.gate_patent(root)["ok"] is True                 # marker present → cleared
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- gate: denylist tokens (a private-crucible / dev-path / PII leak fails closed) ----
# Fixtures use SYNTHETIC tokens via the ``tokens=`` param so this test file itself carries none of the
# real ones (the suite ships public; a real token here would trip the very gate it tests).
def test_gate_denylist_tokens():
    root = Path(tempfile.mkdtemp(prefix="rel_deny_"))
    try:
        (root / "clean.md").write_text("A perfectly public document about the colony.", encoding="utf-8")
        (root / "leak.md").write_text("we deployed into ACME_PrivateVault for the demo", encoding="utf-8")
        toks = ["ACME_PrivateVault", "ACME_"]
        r = G.gate_denylist_tokens(root, ["clean.md", "leak.md"], tokens=toks)
        assert r["ok"] is False
        assert any("leak.md" in h and "ACME_" in h for h in r["detail"])
        r2 = G.gate_denylist_tokens(root, ["clean.md"], tokens=toks)
        assert r2["ok"] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_gate_denylist_manifest_exempt_and_private_module_extends():
    # the manifest may name the generic tokens it bans without tripping the gate on itself
    assert "release/manifest.py" in G._DENYLIST_EXEMPT
    r = G.gate_denylist_tokens(_ROOT, ["release/manifest.py"])
    assert r["ok"] is True, r["detail"]
    # The private monorepo extends the effective list. The derived public tree deliberately omits the
    # identifying module, so the same public test must remain runnable there.
    try:
        from release.denylist_private import PRIVATE_TOKENS
    except ImportError:
        PRIVATE_TOKENS = []
    for tok in PRIVATE_TOKENS:
        assert tok in M.DENYLIST_TOKENS


def test_private_integration_tokens_extend_only_in_private_tree():
    try:
        from release.denylist_private import PRIVATE_TOKENS
    except ImportError:
        return
    synthetic_expected_count = 6
    assert len(PRIVATE_TOKENS) >= synthetic_expected_count
    assert all(token in M.DENYLIST_TOKENS for token in PRIVATE_TOKENS)


# ---- gate: no forward-looking IP disclosure (unfiled-method prose) ----
def test_gate_no_ip_disclosure():
    root = Path(tempfile.mkdtemp(prefix="rel_ip_"))
    try:
        (root / "clean.md").write_text("A shipped, claimed organ with measured evidence.", encoding="utf-8")
        # a doc carrying an unfiled-method IP pointer (the ENHANCEMENTS §F/§G format) must fail closed
        (root / "frontier.md").write_text(
            "This is a candidate. **IP:** a novel method, a filing opportunity before any disclosure.",
            encoding="utf-8")
        r = G.gate_no_ip_disclosure(root, ["clean.md", "frontier.md"])
        assert r["ok"] is False
        assert any("frontier.md" in h for h in r["detail"])
        r2 = G.gate_no_ip_disclosure(root, ["clean.md"])
        assert r2["ok"] is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_public_tree_has_no_ip_disclosure():
    """The strongest holdback regression: the ACTUAL public set (post-holdback) trips zero IP markers —
    the forward-looking docs are held whole / published as scrubbed variants, so nothing forward-looking
    survives into the public tree (the gate reads variant content via M.variant_source)."""
    from release.build_public import iter_public_files
    files = list(iter_public_files(_ROOT))
    r = G.gate_no_ip_disclosure(_ROOT, files)
    assert r["ok"] is True, r["detail"]


# ---- public variants: full doc held; a scrubbed variant publishes under the canonical name ----
def test_public_variants_mapping():
    # the private originals are held; the ".public.md" sources never ship under their own name
    for canonical, src in M.PUBLIC_VARIANTS.items():
        assert not M.is_public(canonical)          # the FULL doc is NEVER_PUBLIC
        assert not M.is_public(src)                # the variant SOURCE never ships as .public.md
        assert M.variant_source(canonical) == src  # ...but publishes under the canonical name
    assert M.variant_source("docs/CLAIMS.md") == "docs/CLAIMS.md"   # unmapped path = itself


def test_public_tree_publishes_variant_not_original():
    """The canonical name (docs/ROADMAP.md) IS in the public set (via the variant), and the tree reads the
    variant SOURCE — so the held original's IP content never materializes."""
    from release.build_public import iter_public_files
    files = set(iter_public_files(_ROOT))
    for canonical, src in M.PUBLIC_VARIANTS.items():
        if (_ROOT / src).exists():
            assert canonical in files              # published under the canonical name
            assert src not in files                # never as .public.md


def test_kernel_subtraction_holds_deep_ip_ships_wired_closure():
    """The vendored physics kernel ships only the wired closure; the deep-IP research modules (several cite
    patent claims in-source) are held. The empty freqos/__init__ variant ships so `import freqos.tam` does
    not eager-load the held modules."""
    from release.build_public import _projection_source, iter_public_files
    files = set(iter_public_files(_ROOT))
    # the wired closure ships
    for keep in ("vendor/kernel/freqos/tam.py", "vendor/kernel/freqos/phase_router.py",
                 "vendor/kernel/freqos/gue_routing.py", "vendor/kernel/freqos/capacity.py",
                 "vendor/kernel/freqos/gue.py", "vendor/kernel/freqos/__init__.py"):
        assert keep in files, keep
    # the deep-IP research is held (a representative sample incl. the patent-claim-citing modules)
    for hold in ("vendor/kernel/freqos/quantum.py", "vendor/kernel/freqos/whiten_capacity.py",
                 "vendor/kernel/freqos/p_order_capacity.py", "vendor/kernel/freqos/holonomy_nav.py",
                 "vendor/kernel/freqos/kinetic_z3.py", "vendor/kernel/freqos/ssr_rag.py",
                 "vendor/kernel/freqos/topology_audit.py"):
        assert not M.is_public(hold), hold
        assert hold not in files, hold
    # the shipped freqos/__init__ is the EMPTY variant (no eager submodule-import STATEMENTS)
    assert M.variant_source("vendor/kernel/freqos/__init__.py") == "vendor/kernel/freqos/__init__.public.py"
    variant = (_ROOT / _projection_source(_ROOT, "vendor/kernel/freqos/__init__.py")).read_text(encoding="utf-8")
    for line in variant.splitlines():
        s = line.strip()
        if s.startswith("from .") or (s.startswith("import ") and "freqos" in s):
            raise AssertionError(f"public freqos/__init__ eager-imports a submodule: {s!r}")


# ---- gate: secrets ----
def test_gate_secrets():
    root = Path(tempfile.mkdtemp(prefix="rel_secret_"))
    try:
        (root / "ok.py").write_text("x = compute()  # no secrets here", encoding="utf-8")
        # fixture assembled by concatenation so THIS source file never contains the joined literal
        # (the secrets gate scans release/tests too — it must not trip on its own fixture)
        (root / "bad.py").write_text('API_' + 'KEY = "abcd1234efgh5678ijkl9012"', encoding="utf-8")
        assert G.gate_secrets(root, ["ok.py"])["ok"] is True
        assert G.gate_secrets(root, ["ok.py", "bad.py"])["ok"] is False
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_derived_public_tree_reads_canonical_variant(tmp_path):
    canonical = tmp_path / "docs" / "ROADMAP.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("community-safe canonical\n", encoding="utf-8")
    assert G._read(tmp_path, "docs/ROADMAP.md") == "community-safe canonical\n"


def test_private_tree_never_falls_back_to_unscrubbed_canonical(tmp_path):
    canonical = tmp_path / "docs" / "ROADMAP.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("private original\n", encoding="utf-8")
    private_marker = tmp_path / "release" / "denylist_private.py"
    private_marker.parent.mkdir(parents=True)
    private_marker.write_text("PRIVATE_TOKENS = []\n", encoding="utf-8")
    assert G._read(tmp_path, "docs/ROADMAP.md") is None


# ---- gate: clean public worktree (build_public + the wheel read the WORKING TREE) ----
# Fixtures are real throwaway git repos: the gate is about git state, so synthetic paths won't do.
def _git(root: Path, *args: str) -> None:
    import subprocess
    r = subprocess.run(["git", "-C", str(root),
                        "-c", "user.email=release-test@local", "-c", "user.name=release-test",
                        *args], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"git {args}: {r.stderr}"


def _worktree_fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix="rel_wt_"))
    _git(root, "init", "-q")
    (root / "docs").mkdir()
    (root / "commercial").mkdir()
    (root / "docs" / "GUIDE.md").write_text("public doc", encoding="utf-8")
    (root / "commercial" / "notes.md").write_text("private notes", encoding="utf-8")
    (root / "docs" / "ENHANCEMENTS.public.md").write_text("scrubbed variant", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def test_gate_clean_worktree_passes_on_clean_and_private_dirty():
    root = _worktree_fixture()
    try:
        assert G.gate_clean_public_worktree(root)["ok"] is True                 # clean tree
        (root / "commercial" / "notes.md").write_text("edited privately", encoding="utf-8")
        assert G.gate_clean_public_worktree(root)["ok"] is True                 # dirty PRIVATE path: fine
        (root / "docs" / "new_untracked.md").write_text("new", encoding="utf-8")
        assert G.gate_clean_public_worktree(root)["ok"] is True                 # untracked cannot ship
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_gate_clean_worktree_fails_on_dirty_public_file():
    root = _worktree_fixture()
    try:
        (root / "docs" / "GUIDE.md").write_text("public doc + WIP private scrape job", encoding="utf-8")
        r = G.gate_clean_public_worktree(root)
        assert r["ok"] is False
        assert any("docs/GUIDE.md" in h for h in r["detail"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_gate_clean_worktree_fails_on_dirty_variant_source():
    """An edited .public.md is NEVER_PUBLIC by path but its CONTENT publishes under the canonical
    name — a dirty variant source ships exactly like a dirty public file."""
    root = _worktree_fixture()
    try:
        (root / "docs" / "ENHANCEMENTS.public.md").write_text("edited variant", encoding="utf-8")
        r = G.gate_clean_public_worktree(root)
        assert r["ok"] is False
        assert any("docs/ENHANCEMENTS.public.md" in h for h in r["detail"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_gate_clean_worktree_fails_closed_outside_git():
    root = Path(tempfile.mkdtemp(prefix="rel_wt_nogit_"))
    try:
        assert G.gate_clean_public_worktree(root)["ok"] is False                # not a repo = FAIL, not skip
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_real_tree_public_worktree_is_clean():
    """The live regression: the actual monorepo worktree carries no uncommitted edit to any
    public-shipping path (the v0.1.5 prometheus.yml near-miss stays fixed)."""
    r = G.gate_clean_public_worktree(_ROOT)
    assert r["ok"] is True, r["detail"]


# ---- wheel member CONTENT scan (the wheel bundles non-.py files from the working tree) ----
def test_scan_members_for_tokens():
    toks = ["ACME_PrivateVault", "backend:9999"]                  # synthetic — this file ships public
    members = [
        ("pkg/config.yml", b'targets: ["backend:9999"]'),
        ("pkg/clean.py", b"x = 1\n"),
        ("pkg/binary.bin", b"\xff\xfe\x00\x01"),                  # undecodable: skipped, never a crash
    ]
    hits = G.scan_members_for_tokens(members, toks)
    assert hits == ["pkg/config.yml :: backend:9999"]
    assert G.scan_members_for_tokens([("pkg/clean.py", b"x = 1\n")], toks) == []


# ---- run_gates aggregates: any FAIL → overall FAIL ----
def test_run_gates_aggregate():
    root = Path(tempfile.mkdtemp(prefix="rel_run_"))
    try:
        (root / "a.py").write_text("clean", encoding="utf-8")
        (root / "LICENSE").write_text("Apache License 2.0", encoding="utf-8")
        _git(root, "init", "-q")                       # the clean-worktree gate fails closed outside git
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "seed")
        # no patent flag → overall must be False even though the file set is clean
        all_ok, results = G.run_gates(root, ["a.py", "LICENSE"])
        assert all_ok is False
        assert any(g["gate"] == "patent_filed" and not g["ok"] for g in results)
        # add the flag (committed, so the worktree stays clean) → every gate passes
        flag = root / M.PATENT_GATE_FLAG
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text("filed", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "flag")
        all_ok2, _ = G.run_gates(root, ["a.py", "LICENSE"])
        assert all_ok2 is True
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} release tests passed")


# ---- wheel purity: no pyproject → skip-ok; the REAL tree must build a clean wheel ----
def test_wheel_gate_skips_without_pyproject():
    root = Path(tempfile.mkdtemp(prefix="rel_wheel_"))
    try:
        g = G.gate_wheel_purity(root)
        assert g["ok"] is True and "skipped" in g["detail"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_wheel_gate_real_tree_is_clean():
    """The strongest packaging regression: a wheel built from THIS tree carries the three community
    packages and zero exocortex/tuner members (the ADR-011/012 boundary, asserted at build level)."""
    g = G.gate_wheel_purity(_ROOT)
    assert g["ok"] is True, g["detail"]


def test_every_non_py_wheel_member_is_public():
    """Closes the CLASS behind the NEXT_PHASE_PLAN.md leak, not just the instance.

    hatchling bundles **every** non-.py file under a package root into the wheel, regardless of
    release/manifest.py — the manifest governs the public *tree*, not the wheel. That is how a
    NEVER_PUBLIC design doc under `exocortex/docs/` (carrying absolute maintainer paths) rode
    private-tree wheels to a second machine. `pyproject.toml` now wheel-excludes `exocortex/docs` — but
    that fixed one directory. Today every other bundled non-.py happens to be public; that is a
    coincidence of the current file set, not a property of the build.

    So assert the INVARIANT: anything the wheel bundles must be publishable. Add a NEVER_PUBLIC .md
    under a package root (outside exocortex/docs) and this fails instead of silently shipping.

    NB this is about the PRIVATE-tree wheel — the one `python -m build` produces locally and the publish
    skill's smoke test installs. The published wheel is built by CI from the PUBLIC checkout, which
    cannot contain these files at all; a leak here taints local/side-channel wheels only.

    (This docstring was itself rewritten once: its first draft named the real paths and tripped
    no_denylisted_tokens — this file is public. The gate was right.)
    """
    import glob
    import subprocess
    import sys
    import tempfile
    import zipfile
    from release.manifest import is_public

    out = Path(tempfile.mkdtemp(prefix="rel_whlscan_"))
    try:
        r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
                           cwd=_ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            import pytest
            pytest.skip(f"wheel build unavailable: {r.stderr[-200:]}")
        whl = sorted(glob.glob(str(out / "*.whl")))[-1]
        members = zipfile.ZipFile(whl).namelist()
        leaked = [m for m in members
                  if not m.endswith(".py") and "dist-info" not in m and not m.endswith("/")
                  and not is_public(m)]
        assert not leaked, (
            "the wheel bundles non-public files (hatchling packages every non-.py under a package "
            f"root; wheel-exclude them in pyproject.toml): {leaked}")
    finally:
        shutil.rmtree(out, ignore_errors=True)


# ---- iter_public_files: publication derives from git-TRACKED files, never a disk walk ----
def test_iter_public_files_tracked_only():
    import subprocess
    from release.build_public import iter_public_files
    files = set(iter_public_files(_ROOT))
    tracked = set(f for f in subprocess.run(
        ["git", "-C", str(_ROOT), "ls-files", "-z"],
        capture_output=True, text=True, timeout=60).stdout.split("\0") if f)
    assert files, "public set must not be empty"
    assert files <= tracked, f"untracked files leaked into the public set: {sorted(files - tracked)[:5]}"
    # the known gitignored local artifact must never ship
    assert "exocortex/testbed/compose/docker-compose.override.yml" not in files
    # the never-public exclusions hold at the file-set level too
    assert "release/denylist_private.py" not in files
    assert "results/resurrection_gauge_v1/labels_completed.json" not in files


def test_iter_public_files_fails_closed_on_git_error():
    """An unreadable git state is UNPUBLISHABLE — no silent fallback to a disk walk."""
    import subprocess
    from release import build_public as B
    real_run = subprocess.run

    class _Fail:
        returncode = 128
        stdout = ""
        stderr = "fatal: not a git repository"

    try:
        subprocess.run = lambda *a, **k: _Fail()
        try:
            B.iter_public_files(_ROOT)
            assert False, "expected RuntimeError when git ls-files fails"
        except RuntimeError as e:
            assert "refusing to fall back" in str(e)
    finally:
        subprocess.run = real_run


def test_build_refuses_every_existing_output_target(tmp_path):
    from release import build_public as B
    target = tmp_path / "existing"
    target.mkdir()
    try:
        B.build(target, _ROOT)
        assert False, "existing output target must be refused"
    except FileExistsError:
        pass
    (target / ".git").mkdir()
    try:
        B.build(target, _ROOT)
        assert False, "git checkout output target must be refused"
    except FileExistsError as exc:
        assert ".git" in str(exc)


def test_projection_receipt_verifies_exact_tracked_set(tmp_path):
    import json
    from release import build_public as B
    root = tmp_path / "public"
    root.mkdir()
    (root / "release").mkdir()
    (root / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
    (root / "README.md").write_bytes(b"public\r\n")
    files = [".gitattributes", "README.md"]
    _git(root, "init", "-q")
    _git(root, "add", *files)
    receipt = {
        "schema": 1,
        "release_version": "0.0.0",
        "generated_utc": "2026-07-16T00:00:00+00:00",
        "projection_digest": B._git_index_digest(root, files),
        "digest_format": "git-index-blob-v1",
        "file_count": 2,
        "gates": [{"name": "synthetic", "ok": True}],
    }
    (root / B.GENERATED_RECEIPT).write_text(json.dumps(receipt), encoding="utf-8")
    _git(root, "add", B.GENERATED_RECEIPT)
    _git(root, "commit", "-q", "-m", "projection")
    assert B.verify_receipt(root)["ok"] is True
    # Git's clean filter treats this working-tree CRLF presentation as the same canonical LF blob.
    (root / "README.md").write_bytes(b"public\r\n")
    assert B.verify_receipt(root)["ok"] is True
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    assert B.verify_receipt(root)["ok"] is False


def test_release_preparer_never_stages_ambient_files():
    source = (_ROOT / "release" / "prepare_public_release.py").read_text(encoding="utf-8")
    assert '"add", "-A"' not in source
    assert '"add", "--"' in source
