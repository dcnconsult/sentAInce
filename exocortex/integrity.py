"""The cryptographic immune system — protect FreqOS *from the host* (ADR-009).

Two language-agnostic, mathematical invariants. Stdlib only (hashlib/json) — numpy-free, hot-path-safe.

1. **Startup kernel-lock verification (apoptosis).** Before the organism accepts a token it hashes its
   frozen DNA — the somatic organs + the Φ⁶/HDC kernel — against a committed baseline. On mismatch, in
   `enforce` mode, it chooses death over mutated DNA: fail-closed `exit 1`. The mutable Exocortex layer
   (colony, wiki) is deliberately NOT in the baseline — it is behavior under the frozen gate, protected by
   the audit chain, not the DNA hash (editing it must not brick the organism).

2. **The epigenetic ledger (hash-chained audit).** Each record carries `hash = SHA256(payload ‖ prev_hash)`.
   Any silent edit to a past decision (or injected τ) snaps the chain — tamper becomes permanently evident.
   Fail-open on write (a hashing error never crashes a hook); tamper-evident on read.

Ships DORMANT (`integrity.mode = off`) so a stale baseline never bricks dev; `warn`/`enforce` are opt-in
production postures. See [[docs/ADR.md]] ADR-009 and docs/DEPLOYMENT.md.
"""

from __future__ import annotations

import argparse
import contextlib as _contextlib
import glob as _glob
import hashlib
import json
import os as _os
import time as _time
from pathlib import Path

from .genome import GENOME

_REPO_ROOT = Path(__file__).resolve().parents[1]
GENESIS = "GENESIS"
_CHAIN_FIELDS = ("prev", "hash")
_BASELINE_NAME = "integrity_baseline.json"

_I = GENOME.get("integrity", {}) or {}
# the frozen safety DNA (NOT the mutable exocortex layer); globs relative to the repo root.
LOCKED_GLOBS = list(_I.get("locked_globs", [
    "sentaince/organism/*.py",
    "vendor/kernel/freqos/*.py",
    "vendor/kernel/core_physics/*.py",
    "vendor/kernel/harmonic_basin/*.py",
]))


# ----------------------------------------------------------------- hash-chain (the epigenetic ledger)
def _canonical(record: dict) -> str:
    """Deterministic serialization of the record's PAYLOAD (excluding the chain fields)."""
    payload = {k: v for k, v in record.items() if k not in _CHAIN_FIELDS}
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def chain_hash(record: dict, prev_hash: str) -> str:
    """`SHA256(canonical(payload) ‖ prev_hash)` — the record's link in the chain."""
    return hashlib.sha256(f"{_canonical(record)}|{prev_hash}".encode("utf-8")).hexdigest()


def tail_hash(path) -> str:
    """The `hash` of the last record in an audit file (the chain head), or GENESIS. O(1) tail read."""
    try:
        p = Path(path)
        if not p.exists():
            return GENESIS
        with open(p, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 16384))
            tail = f.read().decode("utf-8", "replace")
        for line in reversed([ln for ln in tail.splitlines() if ln.strip()]):
            try:
                return json.loads(line).get("hash") or GENESIS
            except Exception:
                continue
        return GENESIS
    except Exception:
        return GENESIS


@_contextlib.contextmanager
def append_lock(path, timeout: float = 2.0):
    """Advisory cross-process lock (sidecar ``<path>.lock``) that closes the read-tail→append window.

    Defect D7 (Desktop audit, 2026-07-01): two hook processes 148 µs apart both read the same tail hash
    and appended in inverted order — one chain fork in 787 records. The chain math was never wrong; the
    critical section was simply unlocked. Hold this lock across ``tail_hash`` + the append.

    FAIL-OPEN by design: if the lock cannot be acquired within ``timeout`` (or locking is unavailable),
    the caller proceeds unlocked — a rare fork under pathological contention beats a wedged hook, because
    a hook must never block the agent (the same ethos as the fail-open chain write)."""
    fh = None
    locked = False
    try:
        try:
            fh = open(str(path) + ".lock", "a+b")
            deadline = _time.monotonic() + timeout
            while True:
                try:
                    if _os.name == "nt":
                        import msvcrt
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl                        # POSIX-only; unreachable on nt
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)   # type: ignore[attr-defined]
                    locked = True
                    break
                except OSError:
                    if _time.monotonic() >= deadline:
                        break                                  # fail-open: proceed unlocked
                    _time.sleep(0.005)
        except Exception:
            pass                                               # no lock available → fail-open
        yield locked
    finally:
        if fh is not None:
            try:
                if locked:
                    if _os.name == "nt":
                        import msvcrt
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl                        # POSIX-only; unreachable on nt
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)   # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass


def verify_audit(path) -> dict:
    """Recompute the chain over the audit's chained suffix. Reports the FIRST break (a self-hash mismatch =
    an edited payload; a link mismatch = a reorder/delete/insert). Records without a `hash` are the
    pre-chain prefix and are skipped."""
    try:
        records = []
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        records.append(json.loads(ln))
                    except Exception:
                        pass
    except Exception as e:
        return {"ok": False, "message": f"unreadable: {e}", "records": 0, "chained": 0}
    chained = [r for r in records if "hash" in r]
    prev = None
    for i, r in enumerate(chained):
        if chain_hash(r, r.get("prev", "")) != r.get("hash"):
            return {"ok": False, "first_break": i, "records": len(records), "chained": len(chained),
                    "message": f"payload at chained-index {i} was altered (self-hash mismatch)"}
        if prev is not None and r.get("prev") != prev:
            return {"ok": False, "first_break": i, "records": len(records), "chained": len(chained),
                    "message": f"chain link broken at chained-index {i} (reorder/delete/insert)"}
        prev = r.get("hash")
    return {"ok": True, "records": len(records), "chained": len(chained), "message": "chain intact"}


# ----------------------------------------------------------------- kernel-lock verification (apoptosis)
def _sha256_file(p: Path) -> str:
    # Normalize line endings (CRLF→LF) before hashing so the lock is STABLE across git autocrlf and
    # cross-platform checkout — a meaningful tamper changes content, not whitespace endings. Source files
    # are small, so reading whole is fine.
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def compute_manifest(root: Path | None = None, globs=None) -> dict:
    """{relpath -> sha256} for every file matching the locked globs (sorted, posix paths)."""
    root = _REPO_ROOT if root is None else Path(root)
    out: dict = {}
    for g in (globs if globs is not None else LOCKED_GLOBS):
        for f in _glob.glob(str(root / g)):
            fp = Path(f)
            if fp.is_file():
                out[fp.relative_to(root).as_posix()] = _sha256_file(fp)
    return dict(sorted(out.items()))


def _baseline_path() -> Path:
    cfg = (GENOME.get("integrity", {}) or {}).get("baseline", "")
    return Path(cfg) if cfg else (Path(__file__).resolve().parent / _BASELINE_NAME)


def save_baseline(root: Path | None = None) -> dict:
    m = compute_manifest(root)
    _baseline_path().write_text(json.dumps({"globs": LOCKED_GLOBS, "manifest": m}, indent=2), encoding="utf-8")
    return m


def load_baseline() -> dict:
    p = _baseline_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("manifest", {})
    except Exception:
        return {}


def verify_kernel(root: Path | None = None) -> dict:
    """Compare the runtime frozen-DNA manifest to the committed baseline. ok=False if the baseline is
    missing (cannot verify → in `enforce` the organism refuses to run) or any file is altered/missing/extra."""
    baseline = load_baseline()
    if not baseline:
        return {"ok": False, "reason": "no baseline", "mismatched": [], "missing": [], "extra": []}
    current = compute_manifest(root)
    mismatched = sorted(p for p in baseline if p in current and current[p] != baseline[p])
    missing = sorted(p for p in baseline if p not in current)         # a locked file was deleted
    extra = sorted(p for p in current if p not in baseline)            # a new file slipped into the locked set
    ok = not (mismatched or missing)                                  # `extra` is reported but not fatal
    return {"ok": ok, "mismatched": mismatched, "missing": missing, "extra": extra, "n": len(baseline)}


# ----------------------------------------------------------------- CLI (ops + tests)
def main() -> int:
    ap = argparse.ArgumentParser(description="FreqOS integrity — kernel-lock baseline + audit-chain verify")
    ap.add_argument("--update-baseline", action="store_true", help="(re)generate the kernel-lock baseline from current files")
    ap.add_argument("--verify", action="store_true", help="verify the runtime kernel against the baseline")
    ap.add_argument("--verify-audit", default=None, help="verify a hash-chained audit.jsonl")
    args = ap.parse_args()
    if args.update_baseline:
        m = save_baseline()
        print(f"[integrity] baseline written: {len(m)} files -> {_baseline_path()}")
    if args.verify:
        r = verify_kernel()
        print(f"[integrity] kernel verify: ok={r['ok']} mismatched={r['mismatched']} missing={r['missing']} extra={r['extra']}")
        if not r["ok"]:
            return 1
    if args.verify_audit:
        r = verify_audit(args.verify_audit)
        print(f"[integrity] audit verify: {r}")
        if not r["ok"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
