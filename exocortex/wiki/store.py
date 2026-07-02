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

import hashlib
import json
import subprocess
from pathlib import Path

from ..colony import Colony
from ..config import state_dir, declarative_ingest
from .digest import digest_document
from .node import ExonNode, WikiGraph

_CACHE_NAME = "wiki_cache.json"


def _git_tracked_md(vault: Path) -> "list | None":
    """The Markdown files git TRACKS under ``vault`` — respects the vault's ``.gitignore`` AND excludes
    untracked / submodule noise (git lists neither). Paths are git's cwd-relative output (correct whether
    ``vault`` is the repo root or a subdirectory), re-joined to ``vault`` and existence-checked.

    Returns ``None`` on ANY failure (git absent, not a repo, timeout, decode) so the caller falls OPEN to
    the rglob scan. This is the first subprocess on the per-tool hot path, so it is BOUNDED (timeout) and
    NEVER raises — the ADR-007 numpy-free/fail-open contract carried to a process boundary."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(vault), "ls-files", "-z", "--", "*.md"],
            capture_output=True, timeout=5.0,
        )
        if proc.returncode != 0:
            return None
        rels = proc.stdout.decode("utf-8", errors="replace").split("\0")
        files = [vault / r for r in rels if r.endswith(".md")]
        return sorted(p for p in files if p.is_file())
    except Exception:
        return None


def _md_files(vault: Path, ingest: str = "all") -> list:
    """Discover the vault's Markdown files (T4 inclusion boundary). ``ingest``:
      - ``"all"`` (default): every ``*.md`` under the vault — the verified baseline (zero behaviour change).
      - ``"tracked"``: only git-tracked ``*.md``; falls OPEN to ``"all"`` if the vault is not a git repo
        or git is unavailable, so ``tracked`` can never break a hook (ADR-007)."""
    if ingest == "tracked":
        tracked = _git_tracked_md(vault)
        if tracked is not None:
            return tracked
        # fail-open: git unavailable / not a repo → behave exactly as "all"
    return sorted(p for p in vault.rglob("*.md") if p.is_file())


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
    changes the signature and correctly invalidates the cache once."""
    files = _md_files(vault, ingest)
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
