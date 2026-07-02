"""Smoke test for the read-only Governor MCP tool (``resurrection_candidates`` in
``exocortex/mcp_server.py``). OUTSIDE the 99-lock; run explicitly (``python -m pytest cerebral/tests``).

Skipped when the optional ``mcp`` dependency is absent (the server imports FastMCP at module load). Uses a
synthetic temp repo (config `declarative.vault_path` → a tiny vault) with a FIXED ``now`` for determinism,
and scrubs the EXOCORTEX_* env so the run is single-repo and vault-resolved from the config.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

pytest.importorskip("mcp")   # optional dep — skip cleanly if the MCP SDK isn't installed

_ENV_KEYS = ("EXOCORTEX_STATE_DIR", "EXOCORTEX_PROJECTS_ROOT", "EXOCORTEX_WIKI_VAULT", "EXOCORTEX_WIKI_INGEST")


def _clean_env(state_dir: Path) -> dict:
    saved = {k: os.environ.get(k) for k in _ENV_KEYS}
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    os.environ["EXOCORTEX_STATE_DIR"] = str(state_dir)
    return saved


def _restore(saved: dict) -> None:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _mkrepo(with_vault: bool) -> Path:
    root = Path(tempfile.mkdtemp(prefix="cerebral_gov_"))
    (root / ".claude" / "exocortex").mkdir(parents=True)
    if with_vault:
        (root / "exocortex_config.json").write_text(
            json.dumps({"declarative": {"vault_path": str(root), "ingest": "all"}}), encoding="utf-8")
        (root / "PAPER_X").mkdir()
        (root / "PAPER_X" / "ISSUES.md").write_text(
            "# X\n\n**Last Updated:** 2026-01-01\n\n- [ ] Stale bibliography population task\n",
            encoding="utf-8")
    return root


def test_resurrection_candidates_surfaces_crack_faller():
    import time
    root = _mkrepo(with_vault=True)
    saved = _clean_env(root / ".claude" / "exocortex")
    try:
        import exocortex.mcp_server as m
        # D1 contract: the maiden call may return a 'warming' note instantly; the scan lands in background
        out = m.resurrection_candidates(now="2026-07-01", limit=10)
        for _ in range(100):
            if "warming" not in out:
                break
            time.sleep(0.1)
            out = m.resurrection_candidates(now="2026-07-01", limit=10)
        assert isinstance(out, str)
        assert "Stale bibliography population task" in out, out
        assert "crack-fallers" in out
    finally:
        _restore(saved)
        shutil.rmtree(root, ignore_errors=True)


def test_maiden_call_never_blocks_and_scan_holds_no_lock():
    """The D1 defect: the maiden scan ran synchronously INSIDE _enter() (holding the server RLock), so a
    59k-node vault hung the calling tool ≥240s AND wedged every other endpoint. Contract now: the maiden
    call returns a 'warming' note fast, and OTHER endpoints stay responsive while a slow scan runs."""
    import time
    root = _mkrepo(with_vault=True)
    saved = _clean_env(root / ".claude" / "exocortex")
    try:
        import exocortex.mcp_server as m
        import cerebral.gauge.resurrection_gauge as rg
        real_run = rg.run

        def slow_run(vault, now_iso, *a, **k):        # stand-in for the 59k-node maiden scan
            time.sleep(2.0)
            return {"repo": "slow", "now": now_iso, "counts": {"stale_candidates": 0,
                    "executable_candidates": 0, "live_parent_candidates": 0, "dormant_parents": []},
                    "candidates": [], "dormant_days": 90}
        rg.run = slow_run
        try:
            t0 = time.time()
            out1 = m.resurrection_candidates(now="2026-05-05")     # fresh key → maiden
            assert time.time() - t0 < 1.5, "maiden call must not block on the scan"
            assert "warming" in out1, out1
            t0 = time.time()
            m.memory_status()                                       # the wedge check: other endpoints live
            assert time.time() - t0 < 1.5, "another endpoint blocked behind the scan (the D1 wedge)"
        finally:
            time.sleep(2.2)                                         # let the daemon thread drain
            rg.run = real_run
    finally:
        _restore(saved)
        shutil.rmtree(root, ignore_errors=True)


def test_no_vault_abstains():
    root = _mkrepo(with_vault=False)          # no exocortex_config.json → no declarative vault
    saved = _clean_env(root / ".claude" / "exocortex")
    try:
        import exocortex.mcp_server as m
        out = m.resurrection_candidates(now="2026-07-01")
        assert out.startswith("(") and "no declarative vault" in out, out
    finally:
        _restore(saved)
        shutil.rmtree(root, ignore_errors=True)


def test_reply_path_watchdog_recycles_a_parked_worker():
    """D1b (Desktop audit, post-fix build): the maiden reply parked ≥240 s SOMEWHERE in the resolve path
    and exhausted the host's worker pool — the park site was never caught locally, so the fix is
    structural: the WHOLE reply path runs under an 8 s watchdog. Simulate a park anywhere before the
    warming return (here: repo discovery hangs) and the tool must still return a busy note with the
    worker recycled — a >240 s reply is now impossible by construction."""
    import time
    root = _mkrepo(with_vault=True)
    saved = _clean_env(root / ".claude" / "exocortex")
    try:
        import exocortex.mcp_server as m
        real_repos = m._repos

        def parked_repos():                    # stand-in for the unidentified Desktop-side park
            time.sleep(10.0)
            return real_repos()

        m._repos = parked_repos
        try:
            t0 = time.time()
            out = m.resurrection_candidates(now="2026-06-06")
            took = time.time() - t0
            assert took < 9.5, f"reply parked {took:.1f}s — the watchdog did not recycle"
            assert "busy" in out and "recycled" in out, out
        finally:
            time.sleep(2.5)                    # let the orphaned resolve thread drain (it holds _LOCK)
            m._repos = real_repos
    finally:
        _restore(saved)
        shutil.rmtree(root, ignore_errors=True)
