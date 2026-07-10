"""Atomic filesystem primitives for the organism's hot-path stores (ADR-020).

A truncate-then-write ``write_text`` leaves a torn file visible to any concurrent reader (and a
half-written file after a crash) — and a torn colony read silently loads EMPTY, which the next
save writes back over the earned τ store. Write-integrity law: **fail-open for the agent,
fail-closed for the memory store** — a store file on disk is either the old bytes or the new
bytes, never a mixture. Provenance: the cursor_testbed Codex-probe corruption artifact
(2026-07-09: torn rows under subagent fan-out) + defect D7 lineage.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def atomic_write_text(path: Path | str, text: str) -> None:
    """Write ``text`` to ``path`` atomically: tmp file in the same directory + ``os.replace``
    (atomic on NTFS and POSIX). The pid-suffixed tmp name keeps concurrent writers from clobbering
    each other's staging file; last ``os.replace`` wins wholesale — a reader can never observe a
    torn file. A crash mid-write leaves only a stray ``.tmp<pid>`` (harmless), never a torn store."""
    path = Path(path)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        for attempt in range(5):   # Windows: a concurrent reader/AV scan can hold the target through
            try:                   # a replace window — transient, so retry briefly before giving up
                os.replace(tmp, path)
                return
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.02)
    finally:
        try:                       # a failed replace must not leave staging litter behind
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def load_store_json(path: Path | str) -> tuple[dict | None, bool]:
    """Guarded store read → ``(data, degraded)``. Missing file → ``(None, False)`` (a fresh store
    is normal). An existing file that won't parse as a JSON dict is retried once (~50 ms — tolerates
    a torn read from an unpatched legacy truncate-writer), then QUARANTINED: renamed to
    ``<name>.corrupt-<UTC-date>`` and reported as ``(None, True)`` — the caller must refuse to
    write back over a store it failed to read (the τ-wipe amplifier: torn read → silent empty
    load → save clobbers the earned memory). One ``StoreQuarantine`` audit row marks the incident;
    a rename that loses (Windows sharing violation) still returns degraded."""
    p = Path(path)
    if not p.exists():
        return None, False
    parse_failed = False
    for attempt in range(5):
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None, False                 # swapped away mid-replace → same as missing (fresh store)
        except OSError:                        # Windows sharing violation during a concurrent atomic
            if attempt < 4:                    # replace — CONTENTION, not corruption: retry, and never
                time.sleep(0.02)               # quarantine a file we could not even read
                continue
            return None, True                  # persistently unreadable → refuse writes, leave in place
        try:
            d = json.loads(text)
            if isinstance(d, dict):
                return d, False
        except Exception:
            pass
        parse_failed = True                    # read OK but the BYTES are wrong — the tear signature
        if attempt < 4:
            time.sleep(0.02)
    if not parse_failed:
        return None, True                      # unreachable belt-and-braces: no proof of corruption
    q = p.with_name(p.name + ".corrupt-" + datetime.now(timezone.utc).strftime("%Y%m%d"))
    try:
        os.replace(p, q)                       # same-day re-quarantine overwrites, by design
        moved = q.name
    except OSError:
        moved = ""                             # another process holds it open → leave in place
    try:
        from . import audit
        audit.append({"event": "StoreQuarantine", "store": p.name, "quarantined_to": moved,
                      "reason": "unreadable store (torn/corrupt JSON) — writes refused this load"})
    except Exception:
        pass                                   # a hook must never crash the agent
    return None, True
