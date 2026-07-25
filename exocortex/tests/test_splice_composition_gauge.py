"""Unit tests for the Splice-Composition Gauge — can the memory organs contend for one turn?

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]``). Run explicitly:

    python -m pytest exocortex/tests/test_splice_composition_gauge.py
    python exocortex/tests/test_splice_composition_gauge.py

Synthetic ``<root>/.claude/exocortex`` state dirs (config + colonies + wiki_cache + audit), so every
liveness branch, both verdict branches, and the UNMEASURED-vs-measured distinction are exercised
deterministically. The load-bearing test is ``test_absent_stamp_is_not_reported_as_zero_cofire``: the
gauge must never let a missing instrument read as evidence of no contention.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.gauge import splice_composition_gauge as sc   # noqa: E402


def _mkrepo(cfg: dict | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="sc_repo_"))
    sd = root / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (root / "exocortex_config.json").write_text(json.dumps(cfg or {}), encoding="utf-8")
    return root


def _colony(sd: Path, label: str, deposits: int, edges: int = 3) -> None:
    tau = {f"a{i}\tb{i}": 1.0 - i * 0.01 for i in range(edges)}
    (sd / f"colony_{label}.json").write_text(
        json.dumps({"label": label, "deposits": deposits, "tau": tau}), encoding="utf-8")


def _cache(sd: Path, n: int) -> None:
    (sd / "wiki_cache.json").write_text(json.dumps(
        {"signature": "s", "nodes": [{"id": f"d{i}.md#h", "text": "t"} for i in range(n)]}), encoding="utf-8")


def _audit(sd: Path, rows: list) -> None:
    (sd / "audit.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


# ---- ceiling 1: the ships-dormant default — colony alone can never contend → −1 ----
def test_dormant_default_has_no_contention():
    root = _mkrepo({"somatic_gate": {"mode": "somatic"}})
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "x", deposits=9)
        res = sc.run(sd)
        assert res["ceiling"] == 1 and res["ready"] == ["colony"]
        assert res["verdict"]["disposition"] == -1
        assert "monologue" in res["verdict"]["note"]
        # the dormant organs are reported as off, not merely absent
        assert res["organs"]["wiki"]["live"] is False
        assert res["organs"]["bridge"]["live"] is False
        assert res["organs"]["interocept"]["live"] is False      # somatic mode appends no interoceptive block
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- ceiling 3: the dev-repo shape (wiki live + preamble live) → contention possible, 0 ----
def test_live_wiki_and_preamble_raise_the_ceiling():
    root = _mkrepo({"somatic_gate": {"mode": "somatic"},
                    "declarative": {"mode": "live", "vault_path": "V"},
                    "reflection": {"preamble": "live"}})
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "x", deposits=9)
        _cache(sd, 12)
        res = sc.run(sd)
        assert res["ceiling"] == 3
        assert set(res["ready"]) == {"colony", "wiki", "preamble"}
        assert res["verdict"]["disposition"] == 0
        # +1 must be explicitly unreachable — no shared currency between colony τ and wiki τ
        assert "no shared scale" in res["verdict"]["note"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- a live-but-cold organ raises liveness, NOT the ceiling ----
def test_live_but_unwarmed_wiki_does_not_count_as_ready():
    root = _mkrepo({"declarative": {"mode": "live", "vault_path": "V"}})
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "x", deposits=9)
        res = sc.run(sd)
        assert res["organs"]["wiki"]["live"] is True
        assert res["organs"]["wiki"]["ready"] is False        # no warmed cache → cannot emit today
        assert res["ceiling"] == 1 and res["verdict"]["disposition"] == -1
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- the colony's own abstention law: below the bar is not servable ----
def test_below_the_splice_bar_is_not_servable():
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "thin", deposits=1)
        res = sc.run(sd)
        assert res["organs"]["colony"]["ready"] is False
        assert res["ceiling"] == 0
        assert res["colony_payload"]["classes"] == 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- payload is measured through the REAL renderer, not a copy of it ----
def test_payload_uses_the_real_colony_renderer():
    from exocortex.colony import Colony
    root = _mkrepo()
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "x", deposits=9, edges=4)
        res = sc.run(sd)
        p = res["colony_payload"]
        assert p["classes"] == 1 and p["chars_max"] > 0
        expect = len(Colony(label="x", deposits=9,
                            tau={f"a{i}\tb{i}": 1.0 - i * 0.01 for i in range(4)}).splice())
        assert p["largest"][0]["chars"] == expect        # byte-for-byte the block the hook would inject
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- THE LOAD-BEARING TEST: a missing instrument is reported as missing, never as a zero ----
def test_absent_stamp_is_not_reported_as_zero_cofire():
    root = _mkrepo({"declarative": {"mode": "live", "vault_path": "V"},
                    "reflection": {"preamble": "live"}})
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "x", deposits=9)
        _cache(sd, 5)
        _audit(sd, [{"event": "UserPromptSubmit", "injected": True} for _ in range(20)])
        res = sc.run(sd)
        a = res["audit"]
        assert a["prompts"] == 20 and a["prompts_injected"] == 20
        assert a["measurable"] is False
        assert a["cofire_rate"] is None                   # NOT 0.0 — absence of instrument, not absence of co-fire
        assert "UNMEASURED" in res["verdict"]["note"]
        assert res["verdict"]["disposition"] == 0         # ceiling still decides; the gap is disclosed
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- forward-compatible: if a future (re-baselined) hook stamps `splice`, it is read ----
def test_per_organ_stamp_is_read_when_present():
    root = _mkrepo({"declarative": {"mode": "live", "vault_path": "V"}})
    sd = root / ".claude" / "exocortex"
    try:
        _colony(sd, "x", deposits=9)
        _cache(sd, 5)
        _audit(sd, [
            {"event": "UserPromptSubmit", "injected": True, "splice": {"colony": 800, "wiki": 400}},
            {"event": "UserPromptSubmit", "injected": True, "splice": {"colony": 600, "wiki": 0}},
            {"event": "UserPromptSubmit", "injected": True, "splice": {"colony": 900, "wiki": 300}},
            {"event": "PostToolUse", "tool": "Bash", "outcome": "ok"},
        ])
        a = sc.run(sd)["audit"]
        assert a["measurable"] is True
        assert a["splice_stamped"] == 3 and a["cofire_turns"] == 2
        assert a["cofire_rate"] == round(2 / 3, 4)
        assert a["per_organ_turns"]["colony"] == 3 and a["per_organ_turns"]["wiki"] == 2
        assert a["per_organ_chars"]["wiki"] == 700
        assert a["payload_max"] == 1200
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- estate sweep: rolls up, names the contended repos, and stays fail-open on junk ----
def test_estate_sweep_rolls_up_and_is_fail_open():
    root = Path(tempfile.mkdtemp(prefix="sc_estate_"))
    try:
        for name, cfg in (("quiet", {}),
                          ("loud", {"declarative": {"mode": "live", "vault_path": "V"},
                                    "reflection": {"preamble": "live"}})):
            sd = root / name / ".claude" / "exocortex"
            sd.mkdir(parents=True)
            (root / name / "exocortex_config.json").write_text(json.dumps(cfg), encoding="utf-8")
            _colony(sd, "x", deposits=9)
            if name == "loud":
                _cache(sd, 7)
        # junk: unreadable config + corrupt colony + corrupt audit line — must not raise
        sdj = root / "junk" / ".claude" / "exocortex"
        sdj.mkdir(parents=True)
        (root / "junk" / "exocortex_config.json").write_text("{not json", encoding="utf-8")
        (sdj / "colony_bad.json").write_text("<<<", encoding="utf-8")
        (sdj / "audit.jsonl").write_text("{bad}\n" + json.dumps({"event": "UserPromptSubmit"}) + "\n",
                                         encoding="utf-8")

        res = sc.estate(root)
        assert res["repos"] == 3
        assert res["ceiling_max"] == 3
        assert res["contended_repos"] == ["loud"]
        assert res["verdict"]["disposition"] == 0
        junk = [r for r in res["rows"] if r["repo"] == "junk"][0]
        assert junk["ceiling"] == 0 and junk["audit"]["prompts"] == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- an estate with nothing switched on returns the −1 branch ----
def test_estate_all_dormant_is_minus_one():
    root = Path(tempfile.mkdtemp(prefix="sc_estate2_"))
    try:
        for name in ("a", "b"):
            sd = root / name / ".claude" / "exocortex"
            sd.mkdir(parents=True)
            (root / name / "exocortex_config.json").write_text("{}", encoding="utf-8")
            _colony(sd, "x", deposits=9)
        res = sc.estate(root)
        assert res["ceiling_ge2"] == 0
        assert res["verdict"]["disposition"] == -1
        assert "unfounded estate-wide" in res["verdict"]["note"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- a missing state dir degrades honestly instead of raising ----
def test_missing_state_dir_is_fail_open():
    res = sc.run(Path(tempfile.gettempdir()) / "sc_does_not_exist" / ".claude" / "exocortex")
    assert res["ceiling"] == 0 and res["audit_records"] == 0
    assert res["verdict"]["disposition"] == -1


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
