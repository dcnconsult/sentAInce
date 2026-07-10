"""Repo Orientation Capsule (ADR-019) — the reader-side audit must be deterministic and honest:
the grade is computed from live probes + declared/observed drift, NEVER self-asserted; absent estate
data degrades to Unknown (a portable/public install carries none); the seeder is the ONE write path
and is idempotent. Each grade branch is pinned so the rubric can't drift silently."""
from datetime import date, datetime

import json

from exocortex import orient

TODAY = date(2026, 7, 8)

_LOG_FIXTURE = """# REPO_LOG — Test Portfolio Audit

_Root: `x` · Audited: **2026-07-01** · Method: test._

## Master ranking

| # | Repo | Last activity | Age | Maturity | Strength | Tier | One-line status |
|---|------|---------------|-----|----------|----------|------|-----------------|
| 1 | **Alpha** | 2026-06-30 | 1d | Beta | High | **A** | Flagship, actively developed. |
| 2 | **BravoOld** | 2026-06-20 | 11d | Alpha | Med | **C** | Superseded by `Alpha`. |
| 3 | **Liar** | 2026-01-01 | ~6mo | Alpha | Med | **B** | Log says dormant since January. |

## Cross-repo links

- `Alpha` supersedes `BravoOld`
- `BravoOld` superseded_by `Alpha` — mirrored pair, no flag
- `Alpha` public_mirror_of `AlphaPub`
"""


def _write_log(tmp_path, monkeypatch, text=_LOG_FIXTURE):
    p = tmp_path / "REPO_LOG.md"
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("EXOCORTEX_REPO_LOG", str(p))
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    return p


def _repo(tmp_path, name, *, git=True, tests=True, deployed=False, mtime=None):
    """A minimal on-disk repo the bounded probe can read."""
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.py").write_text("x = 1\n", encoding="utf-8")
    if git:
        (root / ".git").mkdir()
    if tests:
        (root / "tests").mkdir()
        (root / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    if deployed:
        (root / ".claude" / "exocortex").mkdir(parents=True)
    if mtime is not None:
        import os
        ts = datetime(mtime.year, mtime.month, mtime.day, 12).timestamp()
        for p in root.rglob("*"):
            if p.is_file():
                os.utime(p, (ts, ts))
    return root


# ----------------------------------------------------------------------------- parsing the estate log
def test_parse_repo_log_rows_audited_and_links(tmp_path, monkeypatch):
    p = _write_log(tmp_path, monkeypatch)
    log = orient.parse_repo_log(p)
    assert log["audited"] == date(2026, 7, 1)
    row = log["rows"]["Alpha"]
    assert (row["last_activity"], row["maturity"], row["strength"], row["tier"]) == \
           (date(2026, 6, 30), "Beta", "High", "A")
    assert ("Alpha", "supersedes", "BravoOld") in log["links"]
    assert ("BravoOld", "superseded_by", "Alpha") in log["links"]     # trailing "—" comment tolerated
    assert len(log["links"]) == 3


def test_unreadable_log_is_empty_not_fatal(tmp_path):
    assert orient.parse_repo_log(tmp_path / "missing.md") == {}


# ----------------------------------------------------------------------------- grade branches (the rubric)
def _decl(**kw):
    base = {"name": "X", "source": "repo_log", "superseded": False, "tier": "A",
            "last_reviewed": date(2026, 7, 1), "declared_activity": date(2026, 6, 30), "links": []}
    base.update(kw)
    return base


def _probed(**kw):
    base = {"exists": True, "git_present": True, "tests_present": True,
            "last_activity": date(2026, 6, 30)}
    base.update(kw)
    return base


def test_grade_unknown_when_nothing_declared():
    g, reasons = orient.grade(_decl(source=None), _probed(exists=False), TODAY)
    assert g == "Unknown" and "no capsule and no REPO_LOG row" in reasons[0]


def test_grade_low_no_git():
    g, reasons = orient.grade(_decl(), _probed(git_present=False), TODAY)
    assert g == "Low" and any("no git" in r for r in reasons)


def test_grade_low_superseded():
    g, reasons = orient.grade(_decl(superseded=True), _probed(), TODAY)
    assert g == "Low" and any("superseded" in r for r in reasons)


def test_grade_low_tier_c_dormant():
    g, reasons = orient.grade(_decl(tier="C", declared_activity=date(2026, 4, 1)),
                              _probed(last_activity=date(2026, 4, 1)), TODAY)
    assert g == "Low" and any("dormant" in r for r in reasons)


def test_grade_tier_c_with_recent_activity_is_not_low():
    # the dormancy branch keys on live_age, never tier alone
    g, _ = orient.grade(_decl(tier="C", last_reviewed=date(2026, 5, 1),
                              declared_activity=date(2026, 7, 6)),
                        _probed(tests_present=False, last_activity=date(2026, 7, 6)), TODAY)
    assert g == "Medium"


def test_grade_low_stale_review():
    g, reasons = orient.grade(_decl(last_reviewed=date(2026, 3, 1)), _probed(), TODAY)
    assert g == "Low" and any("review stale" in r for r in reasons)


def test_grade_low_declaration_contradicts_disk():
    g, reasons = orient.grade(_decl(declared_activity=date(2026, 1, 1)),
                              _probed(last_activity=date(2026, 6, 30)), TODAY)
    assert g == "Low" and any("contradicts disk" in r for r in reasons)


def test_grade_high_when_fresh_reviewed_and_disk_agrees():
    g, reasons = orient.grade(_decl(), _probed(), TODAY)
    assert g == "High" and "git + tests" in reasons[0]


def test_grade_medium_otherwise_with_reasons():
    g, reasons = orient.grade(_decl(last_reviewed=date(2026, 5, 15)), _probed(tests_present=False), TODAY)
    assert g == "Medium" and reasons        # never a bare letter


# ----------------------------------------------------------------------------- end-to-end orient()
def test_orient_high_end_to_end(tmp_path, monkeypatch):
    _write_log(tmp_path, monkeypatch)
    root = _repo(tmp_path, "Alpha", mtime=date(2026, 6, 30))
    v = orient.orient("Alpha", root, today=TODAY)
    assert v["grade"] == "High" and v["log_reachable"]
    assert v["declared"]["tier"] == "A"
    assert ("Alpha", "supersedes", "BravoOld") in v["declared"]["links"]


def test_orient_unknown_without_any_estate_source(tmp_path, monkeypatch):
    monkeypatch.delenv("EXOCORTEX_REPO_LOG", raising=False)
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    v = orient.orient("Ghost", None, today=TODAY)
    assert v["grade"] == "Unknown" and not v["log_reachable"]
    assert "REPO_LOG not reachable" in orient.render(v)


def test_capsule_overrides_log_row_and_grade_is_never_self_asserted(tmp_path, monkeypatch):
    _write_log(tmp_path, monkeypatch)
    root = _repo(tmp_path, "BravoOld", mtime=date(2026, 6, 20))
    cap = orient.skeleton("BravoOld")
    cap.update({"tier": "B", "canonical_status": "canonical", "last_reviewed": "2026-07-07",
                "grade": "High"})                       # smuggled self-grade must be DROPPED
    orient.capsule_path(root).parent.mkdir(parents=True)
    orient.capsule_path(root).write_text(json.dumps(cap), encoding="utf-8")
    v = orient.orient("BravoOld", root, today=TODAY)
    assert v["declared"]["tier"] == "B"                  # capsule outranks the log row
    loaded = orient.load_capsule(root)
    assert loaded is not None and "grade" not in loaded
    # the estate log still says superseded_by → the reader's audit stays Low regardless of the claim
    assert v["grade"] == "Low"


def test_render_carries_rule_reminder_below_high(monkeypatch):
    monkeypatch.delenv("EXOCORTEX_REPO_LOG", raising=False)
    monkeypatch.delenv("EXOCORTEX_PROJECTS_ROOT", raising=False)
    out = orient.render(orient.orient("Ghost", None, today=TODAY))
    assert "credibility: UNKNOWN" in out and "RE-ORIENT" in out and "never earns tau" in out


def test_probe_ignores_the_organisms_own_deployment_footprint(tmp_path):
    # deploying into a dormant repo must not make it look alive: exocortex_config.json / AGENTS.md /
    # .claude / .cursor never count as repo activity (else every deploy fan-out fires the drift signal)
    import os
    root = _repo(tmp_path, "Parked", mtime=date(2026, 1, 1))
    fresh = datetime(2026, 7, 8, 12).timestamp()
    for rel in ("exocortex_config.json", "AGENTS.md"):
        p = root / rel
        p.write_text("{}", encoding="utf-8")
        os.utime(p, (fresh, fresh))
    (root / ".cursor").mkdir()
    (root / ".cursor" / "hooks.json").write_text("{}", encoding="utf-8")
    assert orient.probe(root)["last_activity"] == date(2026, 1, 1)


# ----------------------------------------------------------------------------- link symmetry (estate view)
def test_symmetry_flags_one_sided_mirrored_pairs_only():
    links = [("Alpha", "supersedes", "BravoOld"), ("BravoOld", "superseded_by", "Alpha"),  # mirrored: ok
             ("Alpha", "public_mirror_of", "AlphaPub"),                                    # one-sided: flag
             ("Alpha", "feeds_into", "Gamma")]                                             # unmirrored edge: ok
    flags = orient.symmetry_flags(links)
    assert len(flags) == 1 and "public_mirror_of" in flags[0] and "private_canonical_of" in flags[0]


def test_estate_links_unions_capsules_and_log(tmp_path, monkeypatch):
    _write_log(tmp_path, monkeypatch)
    root = _repo(tmp_path, "Delta", deployed=True)
    cap = orient.skeleton("Delta")
    cap["links"] = [{"edge": "depends_on", "target": "Alpha"}, {"edge": "bogus_edge", "target": "X"}]
    orient.capsule_path(root).write_text(json.dumps(cap), encoding="utf-8")
    links = orient.estate_links([{"name": "Delta", "root": root}])
    assert ("Delta", "depends_on", "Alpha") in links
    assert not any(e == "bogus_edge" for _, e, _ in links)   # off-vocabulary edges never enter the graph
    assert ("Alpha", "supersedes", "BravoOld") in links      # log links included


# ----------------------------------------------------------------------------- seeder (the one write path)
def test_seed_writes_only_deployed_repos_and_is_idempotent(tmp_path, monkeypatch):
    _write_log(tmp_path, monkeypatch)
    _repo(tmp_path, "Alpha", deployed=True)
    _repo(tmp_path, "BravoOld", deployed=False)              # not deployed → never seeded
    written = orient.seed(tmp_path)
    assert len(written) == 1 and "Alpha" in written[0]
    cap = orient.load_capsule(tmp_path / "Alpha")
    assert cap is not None
    assert cap["tier"] == "A" and cap["maturity"] == "Beta"
    assert cap["last_reviewed"] == "2026-07-01"              # the log's audit date, not today
    assert {"edge": "supersedes", "target": "BravoOld"} in cap["links"]
    assert orient.seed(tmp_path) == []                       # idempotent: existing capsules kept
    cap_path = orient.capsule_path(tmp_path / "Alpha")
    cap_path.write_text(json.dumps({**cap, "tier": "HAND-EDIT"}), encoding="utf-8")
    orient.seed(tmp_path)                                    # still no overwrite without --force
    assert (orient.load_capsule(tmp_path / "Alpha") or {})["tier"] == "HAND-EDIT"
    orient.seed(tmp_path, force=True)                        # force re-derives from the log
    assert (orient.load_capsule(tmp_path / "Alpha") or {})["tier"] == "A"


def test_seed_marks_superseded_status(tmp_path, monkeypatch):
    _write_log(tmp_path, monkeypatch)
    _repo(tmp_path, "BravoOld", deployed=True)
    orient.seed(tmp_path)
    assert (orient.load_capsule(tmp_path / "BravoOld") or {})["canonical_status"] == "superseded"
