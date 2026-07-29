"""WikiStore — load a Markdown vault into a WikiGraph, with a disk-backed digest cache (Ticket 1 / #2).

Each Claude Code hook is a FRESH PROCESS, so the WikiGraph cannot persist in memory across calls — it is
rebuilt from disk every hook that needs it. Re-digesting the whole vault each time wastes work, so the
shredded nodes are cached to ``state_dir()/wiki_cache.json`` keyed by a cheap vault SIGNATURE (sorted
relpath + mtime + size, hashed). Unchanged vault → rebuild nodes from the cache JSON (one read + a stat
sweep); changed → re-digest and rewrite. The per-class colony (τ) and the scar set (σ) are attached by
the caller / loaded here. Numpy-free, fail-open: any error → None (the organ stays silent, the procedural
baseline is untouched).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
from pathlib import Path

from ..colony import Colony
from ..config import state_dir, declarative_exclude, declarative_ingest
from ..fsutil import atomic_write_text
from .digest import digest_document
from .node import ExonNode, WikiGraph

_CACHE_NAME = "wiki_cache.json"


def _git_tracked_md(vault: Path, reasons: "list | None" = None) -> "list | None":
    """The Markdown files git TRACKS under ``vault`` — respects the vault's ``.gitignore`` AND excludes
    untracked / submodule noise (git lists neither). Paths are git's cwd-relative output (correct whether
    ``vault`` is the repo root or a subdirectory), re-joined to ``vault`` and existence-checked.

    Returns ``None`` on ANY failure (git absent, not a repo, timeout, decode) so the caller falls OPEN to
    the rglob scan. This is the first subprocess on the per-tool hot path, so it is BOUNDED (timeout) and
    NEVER raises — the ADR-007 numpy-free/fail-open contract carried to a process boundary.

    ``reasons`` (optional sink) collects WHY it failed. The failure used to be discarded here, which is
    what made the fail-open unauditable downstream — see ``_record_fail_open``."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(vault), "ls-files", "-z", "--", "*.md"],
            capture_output=True, timeout=5.0,
        )
        if proc.returncode != 0:
            if reasons is not None:
                reasons.append(f"git-rc-{proc.returncode}")
            return None
        rels = proc.stdout.decode("utf-8", errors="replace").split("\0")
        files = [vault / r for r in rels if r.endswith(".md")]
        return sorted(p for p in files if p.is_file())
    except Exception as exc:
        if reasons is not None:
            reasons.append(type(exc).__name__)
        return None


def _record_fail_open(vault: Path, reasons: list) -> None:
    """Stamp the audit when ``tracked`` could not resolve and the boundary fell open to ``all``.

    Motivated by a measured harm, not tidiness. The ADR-007 fail-open is correct, because a hook must never
    break. But it was also SILENT, and the silence is what made it dangerous: a vault configured
    ``ingest: "tracked"`` can quietly digest as ``all`` instead, and nothing anywhere records that the
    boundary moved. A run measured under one boundary then reads as if it ran under the other, and the
    difference is invisible after the fact. A fail-open that cannot be audited cannot carry a control.

    Best-effort and never raises: this sits on the per-tool hot path."""
    try:
        from ..audit import append
        append({"event": "WikiIngestFailOpen", "vault": str(vault),
                "requested": "tracked", "resolved": "all",
                "reason": (reasons or ["unknown"])[0]})
    except Exception:
        pass


def _excluded(vault: Path, files: list, patterns: list) -> list:
    """Drop vault-relative paths matching any ``declarative.exclude`` glob.

    Motivated by a measured harm, not tidiness: 42% of this repo's own 3,980-node vault was
    ``results/guide_accrue_ab_v1/ab_snap/`` — a FROZEN SNAPSHOT of the repo. It cost half of every
    candidate pool, and worse, it split earned credit: ``ab_snap/docs/ADR.md`` had accumulated 11 τ edges
    that belong to the live ``docs/ADR.md``. A duplicate corpus does not just waste slots, it competes
    with the original for consequence.

    Matching is ``fnmatch`` over the POSIX vault-relative path, so ``*`` DOES cross directory separators
    (``results/*`` excludes ``results/a/b.md``). That is deliberate — one obvious pattern per tree — and
    both ``**/x/**`` and ``*ab_snap*`` behave as a reader expects. Ships empty (ADR-003: main stays
    conservative); a repo opts in through its own gitignored ``exocortex_config.json``."""
    if not patterns:
        return files
    out = []
    for p in files:
        try:
            rel = p.relative_to(vault).as_posix()
        except Exception:
            out.append(p)
            continue
        if not any(fnmatch.fnmatch(rel, pat) for pat in patterns):
            out.append(p)
    return out


def _md_files(vault: Path, ingest: str = "all", exclude: "list | None" = None,
              *, audit_fail_open: bool = False) -> list:
    """Discover the vault's Markdown files (T4 inclusion boundary). ``ingest``:
      - ``"all"`` (default): every ``*.md`` under the vault — the verified baseline (zero behaviour change).
      - ``"tracked"``: only git-tracked ``*.md``; falls OPEN to ``"all"`` if the vault is not a git repo
        or git is unavailable, so ``tracked`` can never break a hook (ADR-007).
    ``exclude`` (``declarative.exclude``) then removes matching paths under EITHER boundary — a frozen
    snapshot is just as duplicated whether or not git tracks it. Changing it changes the vault signature,
    so the next load re-digests; that is the intended, self-healing behaviour.

    ``audit_fail_open`` stamps the audit when ``tracked`` falls open (see ``_record_fail_open``). It
    defaults to **False** so that read-only callers — the gauges and the MCP server — never write to a
    repo's audit just by measuring it; only the live hook path (``_load_or_digest``) opts in."""
    pats = declarative_exclude() if exclude is None else list(exclude)
    if ingest == "tracked":
        reasons: list = []
        tracked = _git_tracked_md(vault, reasons)
        if tracked is not None:
            return _excluded(vault, tracked, pats)
        # fail-open: git unavailable / not a repo → behave exactly as "all"
        if audit_fail_open:
            _record_fail_open(vault, reasons)
    return _rglob_md(vault, pats)


# Directories that can never hold vault content but dominate a full-tree walk. `.git` alone is thousands
# of files in this repo, and discovery — not the cache parse — turned out to be the biggest term in
# load_graph (51 ms of 67 ms measured 2026-07-24), so pruning them is the cheapest real win available.
_ALWAYS_PRUNE = frozenset({".git", ".hg", ".svn", "node_modules", "__pycache__",
                           ".venv", "venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"})


def _rglob_md(vault: Path, patterns: list) -> list:
    """``*.md`` under ``vault``, walking with directory PRUNING rather than ``rglob`` + filter.

    ``rglob`` descends into every directory and the exclusion then discards the results, so a 42%
    exclusion bought 0 ms of discovery. Walking with ``os.walk`` lets an excluded subtree be skipped
    outright: a pattern ending in the conventional ``/*`` is matched against directory paths too, so
    ``results/*/ab_snap/*`` prunes the snapshot tree instead of traversing it.

    Output is sorted and identical to the old ``rglob`` path EXCEPT that ``_ALWAYS_PRUNE`` directories no
    longer contribute (this repo loses exactly ``.pytest_cache/README.md`` — build residue that was being
    digested as declarative memory). Both properties are pinned by tests."""
    out: list = []
    vs = str(vault)
    for dirpath, dirnames, filenames in os.walk(vs):
        rel_dir = Path(dirpath).relative_to(vault).as_posix()
        keep = []
        for d in dirnames:
            if d in _ALWAYS_PRUNE:
                continue
            sub = f"{rel_dir}/{d}" if rel_dir not in ("", ".") else d
            if any(fnmatch.fnmatch(sub, pat.rstrip("/*")) for pat in patterns if pat.rstrip("/*")):
                continue                      # the whole subtree is excluded — never descend into it
            keep.append(d)
        dirnames[:] = keep
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            rel = f"{rel_dir}/{fn}" if rel_dir not in ("", ".") else fn
            if any(fnmatch.fnmatch(rel, pat) for pat in patterns):
                continue                      # a file-level pattern that no directory prune covered
            out.append(Path(dirpath) / fn)
    return sorted(out)


def _signature(vault: Path, files: list) -> str:
    h = hashlib.blake2b(digest_size=16)
    for p in files:
        try:
            stt = p.stat()
            rel = p.relative_to(vault).as_posix()
            h.update(f"{rel}|{stt.st_mtime_ns}|{stt.st_size}\n".encode("utf-8"))
        except Exception:
            continue
    return h.hexdigest()


def _digest_vault(vault: Path, files: list) -> list:
    exons: list = []
    for p in files:
        try:
            rel = p.relative_to(vault).as_posix()
            exons.extend(digest_document(rel, p.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            continue
    return exons


def _node_to_dict(n: ExonNode) -> dict:
    return {"id": n.id, "text": n.text, "heading_path": list(n.heading_path),
            "span": list(n.span), "links": list(n.links), "content_hash": n.content_hash}


def _node_from_dict(d: dict) -> ExonNode:
    return ExonNode(
        id=str(d["id"]), text=str(d.get("text", "")),
        heading_path=tuple(d.get("heading_path", []) or []),
        span=tuple(d.get("span", [0, 0]) or [0, 0])[:2] or (0, 0),
        links=tuple(d.get("links", []) or []),
        content_hash=str(d.get("content_hash", "")),
    )


def _load_or_digest(vault: Path, ingest: str = "all") -> list:
    """The vault's nodes, from the cache if the signature matches, else freshly digested (and re-cached).
    The signature is computed over the resolved file set, so switching ``ingest`` mode (fewer/more files)
    changes the signature and correctly invalidates the cache once.

    This is the LIVE path (hooks), so it is the one caller that stamps a fail-open — a boundary flip here
    silently re-digests the whole vault and rewrites the cache, which is exactly the harm to make visible."""
    files = _md_files(vault, ingest, audit_fail_open=True)
    if not files:
        return []
    sig = _signature(vault, files)
    cache = state_dir() / _CACHE_NAME
    if cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("signature") == sig:
                return [_node_from_dict(nd) for nd in d.get("nodes", [])]
        except Exception:
            pass
    exons = _digest_vault(vault, files)
    try:
        cache.write_text(json.dumps({"signature": sig, "nodes": [_node_to_dict(n) for n in exons]}),
                         encoding="utf-8")
    except Exception:
        pass
    return exons


def load_graph(vault_path: str, *, label: str = "_default", ingest: "str | None" = None) -> "WikiGraph | None":
    """Build a WikiGraph for ``vault_path``: nodes from the digest cache, the τ lane = the goal-class
    colony (``Colony.load(label)``), σ from the scar set. Returns None on a missing/empty/unreadable
    vault (the organ then stays silent). Fail-open. ``ingest`` (``all`` | ``tracked``) defaults to the
    Genome (``declarative_ingest()``); pass it explicitly in tests."""
    try:
        if not vault_path:
            return None
        vault = Path(vault_path)
        if not vault.is_dir():
            return None
        nodes = _load_or_digest(vault, ingest if ingest is not None else declarative_ingest())
        if not nodes:
            return None
        g = WikiGraph()
        for n in nodes:
            g.add(n)
        g.colony = Colony.load(label)
        g.scars = _load_scars()
        return g
    except Exception:
        return None


# ---- σ scar persistence (global; only the confirmed-rot path writes it — none wired yet) ----
def _scar_path() -> Path:
    return state_dir() / "wiki_scars.json"


def _load_scars() -> set:
    try:
        p = _scar_path()
        if p.exists():
            return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        pass
    return set()


def save_scars(scars: set) -> None:
    try:
        _scar_path().write_text(json.dumps(sorted(scars)), encoding="utf-8")
    except Exception:
        pass


# ---- explore-offer ledger (F2; derived bookkeeping, NOT earned state) ----
# How many times each NOTE has been offered through the exploration channel WITHOUT yet earning τ. The
# 2026-07-24 log audit found the channel re-offering the identical never-credited notes every turn
# (exocortex-reflection/SKILL.md: 109 blocks offered, 5 ever credited) because admission walked the
# proposer's fixed order with no memory. This counter lets `splice._select` order least-offered-first.
# It is NOT immunity: nothing is ever banned, an exhausted pool still explores, and a note's count is
# dropped the moment it earns τ. Losing this file costs nothing but a round of re-offers.
def _offers_path() -> Path:
    return state_dir() / "wiki_offers.json"


def load_offers() -> dict:
    try:
        p = _offers_path()
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return {str(k): int(v) for k, v in d.items()}
    except Exception:
        pass
    return {}


def save_offers(offers: dict) -> None:
    try:
        atomic_write_text(_offers_path(), json.dumps(offers, sort_keys=True))
    except Exception:
        pass                                        # fail-open: bookkeeping must never break a splice


# ---- action-text extraction (what the model actually did, for used-note attribution) ----
def action_text_of(tool: str, data: dict) -> str:
    """The consequence-bearing content of a tool call — the Bash command, or an edit/write's path +
    content — concatenated for the attribution echo. Empty for tools with no actionable payload."""
    ti = data.get("tool_input") or {}
    if not isinstance(ti, dict):
        return ""
    if tool == "Bash":
        return str(ti.get("command", ""))
    parts = [str(ti.get(k)) for k in ("file_path", "path", "new_string", "content", "old_string")
             if ti.get(k)]
    return " ".join(parts)
