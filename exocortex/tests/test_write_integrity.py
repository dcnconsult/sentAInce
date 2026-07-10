"""Write-integrity tests (ADR-020, W1–W4) — the corruption class the cursor_testbed Codex probe
demonstrated live (torn rows + chain forks under subagent fan-out, quarantined 2026-07-09).

  W1 — atomic replace: a reader NEVER sees a torn store, no matter how the writer is interleaved.
  W2 — quarantine: an unreadable store is renamed aside and NEVER written back over (the τ-wipe
       amplifier: torn read → silent empty load → save clobbers the earned memory).
  W3 — colony lock: the load→deposit→save RMW is cross-process exclusive; concurrent depositors
       and the consolidation sweep lose nothing.
  W4 — telemetry: a fail-open lock acquisition surfaces as ``lock_failopen`` (omit-when-zero).

The two-process tests follow the subprocess pattern the Codex probe used for its audit-lock battery.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from exocortex import audit
from exocortex.colony import Colony
from exocortex.fsutil import atomic_write_text, load_store_json
from exocortex.state import SessionState

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_workers(scripts: list[str], state_dir: Path) -> None:
    """Run each script as a separate Python process against the same state dir; assert all exit 0."""
    env = dict(os.environ, PYTHONPATH=str(_REPO_ROOT), EXOCORTEX_STATE_DIR=str(state_dir),
               PYTHONDONTWRITEBYTECODE="1")
    procs = [subprocess.Popen([sys.executable, "-c", textwrap.dedent(s)], cwd=str(_REPO_ROOT),
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
             for s in scripts]
    for p in procs:
        _out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err.decode("utf-8", errors="replace")


# ----------------------------------------------------------------- W1: atomicity under concurrency
def test_concurrent_save_load_never_torn(tmp_path, monkeypatch):
    """A reader hammering Colony.load while a writer hammers Colony.save must never observe a torn
    store: every load is either the empty pre-first-write colony or a COMPLETE snapshot. Pre-W1
    (truncate-then-write) this races into parse failures → silent-empty loads."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    writer = """
        from exocortex.colony import Colony
        col = Colony(label="atomic")
        big = {f"n{i}\\tm{i}": 2.0 for i in range(400)}
        for _ in range(150):
            col.tau = dict(big)
            col.deposits += 1
            col.save()
    """
    reader = """
        from exocortex.colony import Colony
        for _ in range(300):
            col = Colony.load("atomic")
            assert not col._load_degraded, "reader saw a torn/unreadable store"
            assert len(col.tau) in (0, 400), f"reader saw a PARTIAL store: {len(col.tau)} edges"
    """
    _run_workers([writer, reader], tmp_path)
    assert not list(tmp_path.glob("*.corrupt-*")), "atomic writes must never trigger quarantine"


# ----------------------------------------------------------------- W2: quarantine + write refusal
def test_torn_colony_quarantined_and_write_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    p = tmp_path / "colony_torn.json"
    torn = '{"label": "torn", "tau": {"a\\tb": 2.0, "b\\tc'   # a mid-write tear
    p.write_text(torn, encoding="utf-8")

    col = Colony.load("torn")
    assert col._load_degraded is True
    assert col.tau == {}                                       # nothing invented from the wreck
    q = list(tmp_path.glob("colony_torn.json.corrupt-*"))
    assert len(q) == 1 and q[0].read_text(encoding="utf-8") == torn   # evidence preserved, byte-exact
    assert not p.exists()                                      # original moved aside, not deleted

    col.deposit([("a", "b")], 1.0)
    col.save()                                                 # must REFUSE: degraded load
    assert not p.exists(), "save() wrote back over a store it failed to read"
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "StoreQuarantine" in audit_text                     # the incident is in the ledger


def test_torn_session_state_write_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    st0 = SessionState(session_id="s-torn")
    p = st0._path()
    p.write_text('{"energy": 55.0, "history": [["git push", "o', encoding="utf-8")
    st = SessionState.load("s-torn")
    assert st._load_degraded is True
    st.energy = 1.0
    st.save()                                                  # must refuse
    assert not p.exists() and list(tmp_path.glob("state_s-torn.json.corrupt-*"))


def test_fresh_store_loads_and_saves_normally(tmp_path, monkeypatch):
    """No W2 false-positive: a MISSING store is a normal fresh start, not a quarantine case."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    col = Colony.load("fresh")
    assert col._load_degraded is False and col.tau == {}
    col.deposit([("cue:fresh", "bash:pytest")], 1.0)
    col.save()
    again = Colony.load("fresh")
    assert again.deposits == 1 and "cue:fresh\tbash:pytest" in again.tau
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_load_store_json_roundtrip_and_atomic_write(tmp_path):
    p = tmp_path / "store.json"
    atomic_write_text(p, json.dumps({"k": 1}))
    d, degraded = load_store_json(p)
    assert d == {"k": 1} and degraded is False
    assert not list(tmp_path.glob("store.json.tmp*")), "staging file must not linger"
    missing, deg2 = load_store_json(tmp_path / "absent.json")
    assert missing is None and deg2 is False


# ----------------------------------------------------------------- W3: the lost-update races
def test_lost_deposit_race_two_processes(tmp_path, monkeypatch):
    """THE regression test for the corruption class: two processes each lay 25 deposits into the
    same class under Colony.locked — all 50 must survive. Unlocked load→deposit→save loses updates
    (last-write-wins), exactly what the Codex probe's flagship fan-out hit."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    n = 25
    worker = f"""
        from exocortex.colony import Colony
        for _ in range({n}):
            with Colony.locked("race") as col:
                col.deposit([("cue:race", "bash:pytest")], 1.0)
                col.save()
    """
    _run_workers([worker, worker], tmp_path)
    col = Colony.load("race")
    assert col._load_degraded is False
    assert col.deposits == 2 * n, f"lost updates: {2 * n - col.deposits} of {2 * n} deposits vanished"


def test_sweep_vs_deposit_no_lost_updates(tmp_path, monkeypatch):
    """The PreCompact consolidation sweep RMW must not overwrite a concurrent deposit (nor vice
    versa): final counters equal exactly what each side performed."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    n_dep, n_con = 20, 20
    depositor = f"""
        from exocortex.colony import Colony
        for _ in range({n_dep}):
            with Colony.locked("sweep") as col:
                col.deposit([("cue:sweep", "bash:pytest")], 1.0)
                col.save()
    """
    sweeper = f"""
        from exocortex.colony import Colony
        for _ in range({n_con}):
            with Colony.locked("sweep") as col:
                col.consolidate()
                col.save()
    """
    _run_workers([depositor, sweeper], tmp_path)
    col = Colony.load("sweep")
    assert col.deposits == n_dep, f"the sweep clobbered {n_dep - col.deposits} deposit(s)"
    assert col.consolidations == n_con, f"deposits clobbered {n_con - col.consolidations} sweep(s)"


# ----------------------------------------------------------------- W4: contention telemetry
def test_colony_locked_surfaces_failopen(tmp_path, monkeypatch):
    """A contended lock that times out FAILS OPEN (the hook must never wedge the agent) and says so:
    the yielded instance carries _lock_failopen for the audit row."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    from exocortex.integrity import append_lock
    path = Colony(label="_default")._path()
    with append_lock(path, timeout=5.0) as got_outer:
        assert got_outer is True
        with Colony.locked("_default", timeout=0.1) as col:    # same sidecar, held → must fail open
            assert col._lock_failopen is True
    with Colony.locked("_default", timeout=2.0) as col:        # uncontended → clean acquisition
        assert col._lock_failopen is False


def test_audit_record_lock_failopen_omit_when_zero():
    row = audit.record(session="s", event="PostToolUse", mode="somatic", lock_failopen=2)
    assert row["lock_failopen"] == 2
    clean = audit.record(session="s", event="PostToolUse", mode="somatic")
    assert "lock_failopen" not in clean                        # uncontended rows stay byte-identical


# ----------------------------------------------------------------- the gauge reads it all back
def test_lock_contention_gauge_reads_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    a = tmp_path / "audit.jsonl"
    rows = [
        audit.record(session="s", event="PostToolUse", mode="somatic"),
        audit.record(session="s", event="PostToolUse", mode="somatic", lock_failopen=1),
        audit.record(session="s", event="PostToolUseFailure", mode="somatic"),
    ]
    a.write_text("\n".join(json.dumps(r) for r in rows) + "\ntorn{{{\n", encoding="utf-8")
    from exocortex.gauge.lock_contention_gauge import gauge_state_dir, verdict
    s = gauge_state_dir(tmp_path)
    assert s["consequence_rows"] == 3 and s["lock_failopen_rows"] == 1 and s["torn_lines"] == 1
    v = verdict([s])
    assert "-1" in v["verdict"]                                # 1/3 ≥ 1% → contention would be real
