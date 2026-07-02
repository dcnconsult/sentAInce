"""Unit tests for the Cerebral Substrate Slice 0 — the intent harvester + resurrection gauge.

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]`` collects only ``tests/``): this is a
beta organ instrument, not part of the C1–C7 evidence lock. Run explicitly:

    python -m pytest cerebral/tests                 # from the repo root
    python cerebral/tests/test_resurrection.py      # standalone (no pytest needed)

Uses a synthetic temp vault (no git) so it exercises the rglob fail-open path and frontmatter dating,
with a FIXED ``--now`` for determinism.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]   # tests -> cerebral -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cerebral import intents                              # noqa: E402
from cerebral.gauge import resurrection_gauge as rg       # noqa: E402


def _mkvault() -> Path:
    d = Path(tempfile.mkdtemp(prefix="cerebral_vault_"))
    (d / "PAPER_X").mkdir()
    (d / "PAPER_X" / "ISSUES.md").write_text(
        "# Paper X Issues\n\n**Last Updated:** 2026-01-01\n\n"
        "## Outstanding\n"
        "- [ ] **Full bibliography population** — populate ~60 references\n"
        "- [ ] Extract filling fractions from Zhou Fig. 4\n"
        "## Completed\n"
        "- [x] ~~Rename Six to Seven~~ ✓ done — 2026-01-01\n",
        encoding="utf-8")
    (d / "PAPER_Y").mkdir()
    (d / "PAPER_Y" / "ISSUES.md").write_text(
        "# Paper Y Issues\n\n**Last Updated:** 2026-06-30\n\n"
        "- [ ] Recent open item still fresh\n",
        encoding="utf-8")
    led = d / "Research" / "QEC" / "qeg"
    led.mkdir(parents=True)
    (led / "ledger.json").write_text(json.dumps([
        {"use_case_id": "theory_a", "decision_label": "falsified", "created_at_utc": "2026-02-01T00:00:00Z"},
        {"use_case_id": "theory_b", "decision_label": "confirmed", "created_at_utc": "2026-02-02T00:00:00Z"},
        {"use_case_id": "theory_c", "decision_label": "controlled_rerun_candidate",
         "created_at_utc": "2026-02-03T00:00:00Z", "next_step": "run rerun to confirm phase-coherence"},
    ]), encoding="utf-8")
    return d


# ---- checkbox lifecycle + stale detection (the core resurrection metric) ----
def test_counts_lifecycle_and_stale():
    d = _mkvault()
    try:
        res = rg.run(d, "2026-07-01")
        c = res["counts"]
        # 3 checkboxes (X: 2 open + 1 closed) + 1 open (Y) + 3 ledger (falsified, confirmed, candidate)
        assert c["total"] == 7, c
        assert c["open"] == 4, c           # X:2 + Y:1 + ledger candidate:1
        assert c["closed"] == 3, c         # X closed:1 + falsified + confirmed
        # stale (now 2026-07-01): X's 2 open (Jan 1, >30d) + ledger candidate (Feb 3, >30d); Y (Jun 30) fresh
        assert c["stale_candidates"] == 3, (c, res["candidates"])
        # closed valence: +1 (X checkbox) + +1 (confirmed) = 2 ; -1 (falsified) = 1
        assert c["closed_by_valence"]["+1"] == 2, c["closed_by_valence"]
        assert c["closed_by_valence"]["-1"] == 1, c["closed_by_valence"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_fresh_open_item_not_stale():
    d = _mkvault()
    try:
        res = rg.run(d, "2026-07-01")
        srcs = {cand["source"] for cand in res["candidates"]}
        assert not any("PAPER_Y" in s for s in srcs), srcs   # Y's item is within its timeframe
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---- ledger valence mapping (consequence-sourced, from the recorded decision label) ----
def test_ledger_valence_mapping():
    d = _mkvault()
    try:
        items = [it for it in intents.harvest(d) if it.kind == "ledger"]
        fal = next(it for it in items if "theory_a" in it.description)
        con = next(it for it in items if "theory_b" in it.description)
        cand = next(it for it in items if "theory_c" in it.description)
        assert fal.lifecycle == intents.CLOSED and fal.valence == -1
        assert con.lifecycle == intents.CLOSED and con.valence == 1
        assert cand.lifecycle == intents.OPEN and cand.valence is None
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---- (action, anticipated_result): structure, never hallucinate; regex fallback when spaCy absent ----
def test_parse_action_result():
    a, r = intents.parse_action_result("populate all 60 references")
    assert a is not None                       # some action token extracted
    assert r is None                           # no purpose/result clause → NOT hallucinated
    a2, r2 = intents.parse_action_result("run the rerun to confirm phase-coherence")
    assert a2 is not None
    assert r2 is not None and "confirm phase-coherence" in r2
    assert intents.parse_action_result("") == (None, None)


# ---- precision @ worth-resuming, from a PI labels map ----
def test_precision_from_labels():
    d = _mkvault()
    try:
        res = rg.run(d, "2026-07-01")
        cands = res["candidates"]
        assert len(cands) == 3
        # label 2 worth + 1 not-worth → precision 2/3
        labels = {cands[0]["id"]: "worth", cands[1]["id"]: "worth", cands[2]["id"]: "abandoned"}
        res2 = rg.run(d, "2026-07-01", labels=labels)
        v = res2["verdict"]
        assert v["worth"] == 2 and v["not_worth"] == 1
        assert v["value"] == round(2 / 3, 3)
        assert v["signal"] is False            # n_labeled 3 < MIN_LABELED → underpowered, not a build
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---- labels also accept the editable worksheet (array-of-objects) form ----
def test_labels_worksheet_array_form():
    d = _mkvault()
    try:
        cands = rg.run(d, "2026-07-01")["candidates"]
        worksheet = [{"id": cands[0]["id"], "label": "worth"},
                     {"id": cands[1]["id"], "label": "worth"},
                     {"id": cands[2]["id"], "label": "mislabeled"}]
        v = rg.run(d, "2026-07-01", labels=worksheet)["verdict"]
        assert v["worth"] == 2 and v["not_worth"] == 1 and v["value"] == round(2 / 3, 3)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---- determinism: same vault + same now → byte-identical result ----
def test_determinism():
    d = _mkvault()
    try:
        r1 = rg.run(d, "2026-07-01")
        r2 = rg.run(d, "2026-07-01")
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---- read-only: harvesting a missing vault is a safe empty, never a crash ----
def test_missing_vault_is_empty():
    assert intents.harvest(Path(tempfile.gettempdir()) / "does_not_exist_cerebral") == []


# ---- v2: is_executable harvest filter (conservative — drops ONLY high-confidence non-tasks) ----
def test_is_executable_filter():
    assert intents.is_executable("Figure creation — 7 figures planned, 0 created") is True
    assert intents.is_executable("How much can §2 lean on the companion paper?") is False   # ends '?'
    assert intents.is_executable("See Vault_Checklist_v1.md for full pipeline") is False     # leading See <doc>
    # NOT dropped — semantically non-tasks but mechanically indistinguishable from real ones (v1 finding):
    assert intents.is_executable("Check SmithA2026 vs SmithB2026 duplicate warning") is True   # ' vs '
    assert intents.is_executable("arXiv posting: PENDING (requires endorsement)") is True          # 'PENDING'


def _mkvault_v2() -> Path:
    d = Path(tempfile.mkdtemp(prefix="cerebral_vault2_"))
    (d / "PAPER_OLD").mkdir()
    (d / "PAPER_OLD" / "ISSUES.md").write_text(
        "# Old\n\n**Last Updated:** 2026-01-01\n\n- [ ] Old task one\n- [ ] Old task two\n", encoding="utf-8")
    (d / "PAPER_NEW").mkdir()
    (d / "PAPER_NEW" / "ISSUES.md").write_text(
        "# New\n\n**Last Updated:** 2026-05-15\n\n"
        "- [ ] New real task\n- [ ] Should we pick option A?\n- [ ] See OTHER_DOC.md for the plan\n",
        encoding="utf-8")
    return d


# ---- v2: parent-liveness clustering + layered precision (raw < +filter < +liveness) ----
def test_parent_liveness_and_layered_precision():
    d = _mkvault_v2()
    try:
        res = rg.run(d, "2026-07-01")          # dormant_days default 90
        c = res["counts"]
        assert c["stale_candidates"] == 5                       # OLD 2 + NEW 3 (all past the 30d timeframe)
        assert c["executable_candidates"] == 3                  # OLD 2 + NEW real; the '?' and 'See' drop
        assert c["dormant_parents"] == ["PAPER_OLD"]            # OLD ~181d silent; NEW ~47d → live
        assert c["live_parent_candidates"] == 1                 # only NEW real task (executable + live)
        by_parent = {cand["parent"]: cand for cand in res["candidates"]}
        assert by_parent["PAPER_OLD"]["parent_dormant"] is True
        assert by_parent["PAPER_NEW"]["parent_dormant"] is False
        cid = {cand["description"]: cand["id"] for cand in res["candidates"]}
        labels = {cid["Old task one"]: "abandoned", cid["Old task two"]: "abandoned",
                  cid["New real task"]: "worth",
                  cid["Should we pick option A?"]: "mislabeled",
                  cid["See OTHER_DOC.md for the plan"]: "mislabeled"}
        v = rg.run(d, "2026-07-01", labels=labels)["verdict"]
        assert v["value"] == 0.2                                # raw: worth1 / 5
        assert v["precision_executable"] == round(1 / 3, 3)     # +filter: worth1 / (worth1 + 2 abandoned)
        assert v["precision_live_parent"] == 1.0               # +liveness: only the live executable worth task
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_harvest_git_calls_bounded_by_checkbox_filter():
    """D1b close-with-evidence (Desktop audit 2026-07-01): a huge vault must NOT translate into per-file
    git subprocesses. The harvest filters filenames against CHECKBOX_PATTERNS BEFORE any dating, so
    ``_git_commit_date`` (the only per-file `git log`) runs at most once per *matched* file — vault node
    count does not multiply subprocesses. 300 unmatched notes + 2 matched files ⇒ ≤ 2 dating calls."""
    d = Path(tempfile.mkdtemp(prefix="cerebral_big_"))
    dated = []
    orig = intents._git_commit_date
    try:
        for i in range(300):                       # the "huge vault" body — none match CHECKBOX_PATTERNS
            (d / f"note_{i}.md").write_text(f"# note {i}\n- [ ] looks like a task but wrong file\n",
                                            encoding="utf-8")
        (d / "ISSUES.md").write_text("- [ ] fix the flange\n- [x] close the loop\n", encoding="utf-8")
        (d / "FILING_CHECKLIST.md").write_text("- [ ] file the thing\n", encoding="utf-8")

        def counting(vault, rel, cache):
            dated.append(str(rel))
            return orig(vault, rel, cache)

        intents._git_commit_date = counting
        its = intents.harvest(d)
        srcs = {i.source.rsplit("/", 1)[-1].split("#", 1)[0] for i in its}   # strip the #L<line> anchor
        assert srcs == {"ISSUES.md", "FILING_CHECKLIST.md"}
        assert len(dated) <= 2, f"unbounded scan: {len(dated)} git-date calls (expected ≤ 2): {dated[:5]}"
        assert all(r.rsplit("/", 1)[-1] in ("ISSUES.md", "FILING_CHECKLIST.md") for r in dated)
    finally:
        intents._git_commit_date = orig
        shutil.rmtree(d, ignore_errors=True)


def test_git_dates_bulk_one_walk_seeds_the_cache():
    """D1b scale fix: ONE ``git log --name-only`` walk dates every matched file — the per-file
    ``git log -1`` becomes a fallback, not a per-file cost. Verified on a real tiny git repo; the
    harvest must then run with ZERO per-file dating subprocesses."""
    import subprocess
    d = Path(tempfile.mkdtemp(prefix="cerebral_git_"))
    try:
        def git(*args):
            r = subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=True, timeout=30,
                               env={**__import__("os").environ,
                                    "GIT_AUTHOR_DATE": "2026-03-03T12:00:00+00:00",
                                    "GIT_COMMITTER_DATE": "2026-03-03T12:00:00+00:00"})
            assert r.returncode == 0, r.stderr
        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        (d / "ISSUES.md").write_text("- [ ] task one\n", encoding="utf-8")
        (d / "FILING_CHECKLIST.md").write_text("- [ ] file it\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "seed")

        dates = intents._git_dates_bulk(d, ["ISSUES.md", "FILING_CHECKLIST.md"])
        assert dates == {"ISSUES.md": "2026-03-03", "FILING_CHECKLIST.md": "2026-03-03"}, dates

        # the harvest bulk-seeds the cache → the per-file fallback is never invoked
        calls = []
        orig = intents._git_commit_date
        try:
            def counting(vault, rel, cache):
                if rel not in cache:
                    calls.append(rel)
                return orig(vault, rel, cache)
            intents._git_commit_date = counting
            its = intents.harvest(d)
            assert len(its) == 2
            assert calls == [], f"per-file git dating ran despite the bulk seed: {calls}"
            assert all(i.last_activity == "2026-03-03" for i in its)
        finally:
            intents._git_commit_date = orig
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":   # standalone runner (no pytest required)
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} resurrection tests passed")
