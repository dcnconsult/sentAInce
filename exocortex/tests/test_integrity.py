"""The cryptographic immune system (ADR-009) — hash-chained audit + kernel-lock apoptosis."""

import json

import pytest

from exocortex import integrity as ig


# --------------------------------------------------------------- hash-chain (epigenetic ledger)
def test_chain_hash_deterministic_and_payload_sensitive():
    rec = {"event": "PostToolUse", "outcome": "ok", "ts": "t0"}
    h = ig.chain_hash(rec, ig.GENESIS)
    assert h == ig.chain_hash(rec, ig.GENESIS)                    # deterministic
    assert ig.chain_hash({**rec, "outcome": "fail"}, ig.GENESIS) != h   # payload change → different hash
    assert ig.chain_hash(rec, "other") != h                      # prev change → different hash
    # the chain fields themselves are excluded from the hashed payload
    assert ig.chain_hash({**rec, "prev": "x", "hash": "y"}, ig.GENESIS) == h


def test_verify_audit_clean_then_detects_edit(tmp_path):
    path = tmp_path / "audit.jsonl"
    prev = ig.GENESIS
    recs = []
    for i in range(4):
        r = {"event": "E", "i": i, "prev": prev}
        r["hash"] = ig.chain_hash(r, prev)
        prev = r["hash"]
        recs.append(r)
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    assert ig.verify_audit(path)["ok"] is True

    # tamper a past payload (index 1) without recomputing → chain snaps there
    recs[1]["i"] = 999
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    v = ig.verify_audit(path)
    assert v["ok"] is False and v["first_break"] == 1


def test_audit_append_chains(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EXOCORTEX_AUDIT_CHAIN", "1")
    from exocortex import audit
    for i in range(3):
        audit.append(audit.record(session="s", event="PostToolUse", mode="observe", outcome="ok"))
    v = ig.verify_audit(tmp_path / "audit.jsonl")
    assert v["ok"] is True and v["chained"] == 3


def test_concurrent_appends_never_fork_the_chain(tmp_path, monkeypatch):
    """D7 (Desktop audit 2026-07-01): two writers 148 µs apart both read the same tail hash and forked
    the chain (append-order inversion in the unlocked read-tail→append window). With ``append_lock``
    holding the section, N racing writers must yield an INTACT chain."""
    import threading
    monkeypatch.setenv("EXOCORTEX_AUDIT", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EXOCORTEX_AUDIT_CHAIN", "1")
    from exocortex import audit
    n_writers, per = 8, 6
    barrier = threading.Barrier(n_writers)

    def writer(k):
        barrier.wait()                                     # maximize the race window
        for i in range(per):
            audit.append({"event": "Race", "writer": k, "i": i})

    threads = [threading.Thread(target=writer, args=(k,)) for k in range(n_writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    v = ig.verify_audit(tmp_path / "audit.jsonl")
    assert v["ok"] is True, v
    assert v["chained"] == n_writers * per


def test_append_lock_fail_open_on_contention(tmp_path):
    """The lock must never wedge a hook: a held lock + a short timeout yields locked=False and the
    caller proceeds (a rare fork beats a blocked agent)."""
    path = str(tmp_path / "a.jsonl")
    with ig.append_lock(path) as got:
        assert got is True
        with ig.append_lock(path, timeout=0.15) as got2:
            assert got2 is False


# --------------------------------------------------------------- kernel-lock (apoptosis)
def test_manifest_detects_a_changed_file(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    m1 = ig.compute_manifest(tmp_path, ["*.py"])
    (tmp_path / "a.py").write_text("x = 2  # tampered\n", encoding="utf-8")
    m2 = ig.compute_manifest(tmp_path, ["*.py"])
    assert m1 != m2 and m1["a.py"] != m2["a.py"]


def test_committed_baseline_matches_repo():
    """Regression guard: the frozen DNA on disk matches the committed baseline. If a vendored kernel /
    somatic-organ file changes without `python -m exocortex.integrity --update-baseline`, this fails — which
    is exactly the lock doing its job."""
    r = ig.verify_kernel()
    assert r["ok"] is True, f"frozen-DNA drift vs baseline: {r}"


# --------------------------------------------------------------- the apoptosis wiring (SessionStart)
def test_sessionstart_apoptosis(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    from exocortex import hook, integrity
    from exocortex.config import Mode

    # enforce + a verified mismatch → fail-closed exit 1 (death over mutated DNA)
    monkeypatch.setattr(integrity, "verify_kernel", lambda *a, **k: {"ok": False, "mismatched": ["x.py"],
                                                                     "missing": [], "extra": []})
    monkeypatch.setenv("EXOCORTEX_INTEGRITY", "enforce")
    with pytest.raises(SystemExit) as e:
        hook.handle_sessionstart({"session_id": "viol"}, Mode.OBSERVE)
    assert e.value.code == 1

    # warn → records the violation but does NOT exit. Since 2026-07-16 SessionStart also returns the
    # vitals line (the organism's one user-facing channel) — and in warn it SAYS so, which is the point:
    # a degraded posture the user can see beats a silent one.
    monkeypatch.setenv("EXOCORTEX_INTEGRITY", "warn")
    out = hook.handle_sessionstart({"session_id": "warn"}, Mode.OBSERVE)
    assert "systemMessage" in out and "integrity=warn" in out["systemMessage"]

    # a clean kernel → normal startup, no exit, vitals emitted
    monkeypatch.setattr(integrity, "verify_kernel", lambda *a, **k: {"ok": True})
    out = hook.handle_sessionstart({"session_id": "ok"}, Mode.OBSERVE)
    assert "systemMessage" in out and "sentaince" in out["systemMessage"]
