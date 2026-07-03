"""One-command install / uninstall of the Exocortex organism into a target repo.

The model is **one code install (this repo) → many project deployments**; each target keeps its own
gitignored runtime state. This module turns the manual 3-artifact runbook (docs/DEPLOY_TO_A_PROJECT.md)
into a clean, idempotent, **reversible** tool — uninstall is as simple as install, which is the safety net
for testing on a daily-driver repo.

    python -m exocortex.deploy install   <target> [--mode observe|somatic|full] [--integrity off|warn|enforce]
                                                   [--declarative off|live] [--vault PATH] [--ingest all|tracked]
                                                   [--no-audit-chain] [--wsl] [--no-colony]
    python -m exocortex.deploy uninstall <target> [--purge]      # --purge also deletes accrued state data
    python -m exocortex.deploy status    <target>

DISCIPLINE — uninstall is SURGICAL and NON-DESTRUCTIVE:
  * settings.local.json: removes ONLY hook entries whose command references this repo's ``hook.py`` (our
    entries), preserving the user's ``permissions`` / MCP / any foreign hooks; drops the ``hooks`` key only
    if it ends up empty. A one-time backup is written into the gitignored state dir on first install.
  * ignore rules: written to ``.git/info/exclude`` (LOCAL, never tracked → the target's committed
    ``.gitignore`` is never touched) for a git repo, else ``.gitignore``; and SKIPPED entirely if the rules
    already exist anywhere. Uninstall removes only our sentinel-delimited block, never user-committed lines.
  * exocortex_config.json: deleted (it is ours + gitignored = the activation file; deleting it reverts to
    dormant defaults).
  * state dir ``.claude/exocortex/`` (audit/colony — the ACCRUED DATA): KEPT by default so reinstall resumes;
    removed only with ``--purge``.

Stdlib-only, numpy-free; this is tooling, never on the hook hot path.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from exocortex.runner import _settings, _cursor_settings   # canonical hooks blocks (single source of truth)

_GI_BEGIN = "# >>> exocortex >>>"
_GI_END = "# <<< exocortex <<<"
_GI_BODY = [".claude/exocortex/", "/exocortex_config.json"]
# Every command we install references ONE of these; foreign hooks do not. Two generations:
#   "exocortex/hook.py"   — the legacy absolute-file form (checkout installs; still written when the
#                           package is not pip-importable at hook-fire time)
#   "-m exocortex.hook"   — the module form written for pip-installed envs (see runner._hook_invocation)
# Uninstall/status must recognize BOTH so surgical removal survives the packaging transition.
_HOOK_MARKS = ("exocortex/hook.py", "-m exocortex.hook")


def _ours(command) -> bool:
    c = str(command or "")
    return any(mk in c for mk in _HOOK_MARKS)


# ---- paths ----
def _state_dir(t: Path) -> Path:   return t / ".claude" / "exocortex"
def _audit_path(t: Path) -> Path:  return _state_dir(t) / "audit.jsonl"
def _config_path(t: Path) -> Path: return t / "exocortex_config.json"
def _settings_path(t: Path) -> Path: return t / ".claude" / "settings.local.json"
def _cursor_hooks_path(t: Path) -> Path: return t / ".cursor" / "hooks.json"


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def _dump_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")


def _is_git_repo(t: Path) -> bool:
    return (t / ".git").exists()


# ---- artifact 1: runtime-state ignore rules (NON-INVASIVE) ----
def _exclude_file(t: Path) -> Path:
    return t / ".git" / "info" / "exclude"   # local, per-clone, NEVER tracked → invisible to the repo


def _has_ignores(t: Path) -> bool:
    """True if the runtime-state ignore rules already exist (in .gitignore OR .git/info/exclude, in ANY
    form — a committed line, a sentinel block, …). We never duplicate or reformat what's already there."""
    for p in (t / ".gitignore", _exclude_file(t)):
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            if all(line in txt for line in _GI_BODY):
                return True
    return False


def _ignore_ensure(t: Path) -> "str | None":
    """Add our ignore rules only if absent. Prefer ``.git/info/exclude`` (local, never tracked → the deploy
    leaves the target's committed ``.gitignore`` untouched) for a git repo; fall back to ``.gitignore`` for a
    non-git target. Returns the file written, or None if the rules were already present anywhere."""
    if _has_ignores(t):
        return None
    target = _exclude_file(t) if _is_git_repo(t) else (t / ".gitignore")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    block = "\n".join([_GI_BEGIN, *_GI_BODY, _GI_END])
    sep = "" if text == "" or text.endswith("\n") else "\n"
    target.write_text(text + sep + block + "\n", encoding="utf-8")
    return ".git/info/exclude" if target == _exclude_file(t) else ".gitignore"


def _ignore_remove(t: Path) -> bool:
    """Remove ONLY our sentinel block, from both ``.gitignore`` and ``.git/info/exclude``. Pre-existing
    (non-sentinel) ignore lines a user committed themselves are left untouched — surgical."""
    changed = False
    for p in (t / ".gitignore", _exclude_file(t)):
        if not p.exists():
            continue
        out, skipping, ch = [], False, False
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip() == _GI_BEGIN:
                skipping, ch = True, True
                continue
            if ln.strip() == _GI_END:
                skipping = False
                continue
            if skipping:
                continue
            out.append(ln)
        if ch:
            p.write_text(("\n".join(out).rstrip("\n") + "\n") if out else "", encoding="utf-8")
            changed = True
    return changed


# ---- artifact 2: exocortex_config.json (the activation file) ----
def _write_config(t: Path, *, mode: str, integrity: str, audit_chain: bool,
                  declarative: str, vault: str | None, ingest: str | None) -> None:
    cfg = _load_json(_config_path(t))   # preserve any extra keys the user added
    cfg["_comment"] = ("Exocortex activation (gitignored; found via CLAUDE_PROJECT_DIR). "
                       "Delete this file or run `python -m exocortex.deploy uninstall` to revert.")
    cfg.setdefault("integrity", {})["mode"] = integrity
    cfg["integrity"]["audit_chain"] = bool(audit_chain)
    cfg.setdefault("somatic_gate", {})["mode"] = mode
    dec = cfg.setdefault("declarative", {})
    dec["mode"] = declarative
    if vault:
        dec["vault_path"] = vault
    if ingest:
        dec["ingest"] = ingest
    _dump_json(_config_path(t), cfg)


# ---- artifact 3: hooks in settings.local.json ----
def _purge_our_hooks(hooks: dict) -> dict:
    """Return ``hooks`` with every entry whose command references our hook.py removed; empty groups/events
    pruned. Foreign hooks are preserved verbatim."""
    cleaned = {}
    for event, groups in (hooks or {}).items():
        new_groups = []
        for g in groups if isinstance(groups, list) else []:
            kept = [h for h in g.get("hooks", []) if not _ours(h.get("command", ""))]
            if kept:
                new_groups.append({**g, "hooks": kept})
        if new_groups:
            cleaned[event] = new_groups
    return cleaned


def _install_hooks(t: Path, *, mode: str, wsl: bool, colony: bool) -> None:
    sp = _settings_path(t)
    d = _load_json(sp)
    bak = _state_dir(t) / "settings.local.json.bak"   # inside the gitignored state dir → invisible to the repo
    if sp.exists() and "hooks" in d and not bak.exists():
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sp, bak)   # one-time restore point
    ours = _settings(_audit_path(t), _state_dir(t), mode, wsl=wsl, colony=colony)["hooks"]
    merged = _purge_our_hooks(d.get("hooks", {}))   # drop any prior exocortex entries first (idempotent)
    for event, groups in ours.items():
        merged.setdefault(event, [])
        merged[event].extend(groups)
    d["hooks"] = merged
    _dump_json(sp, d)


def _uninstall_hooks(t: Path) -> bool:
    sp = _settings_path(t)
    if not sp.exists():
        return False
    d = _load_json(sp)
    if "hooks" not in d:
        return False
    cleaned = _purge_our_hooks(d["hooks"])
    if cleaned:
        d["hooks"] = cleaned
    else:
        d.pop("hooks", None)   # we were the only hooks → drop the key entirely
    _dump_json(sp, d)
    return True


# ---- artifact 3b: hooks in .cursor/hooks.json (the Cursor host) ----
def _purge_our_cursor_hooks(hooks: dict) -> dict:
    """Cursor ``hooks`` with every entry whose command references our hook.py removed; empty events pruned.
    Foreign hooks preserved (sentinel = ``exocortex/hook.py``, same as the Claude path)."""
    cleaned = {}
    for event, entries in (hooks or {}).items():
        kept = [e for e in (entries if isinstance(entries, list) else [])
                if not _ours(e.get("command", ""))]
        if kept:
            cleaned[event] = kept
    return cleaned


def _install_cursor_hooks(t: Path, *, mode: str, wsl: bool, colony: bool) -> None:
    cp = _cursor_hooks_path(t)
    d = _load_json(cp)
    bak = _state_dir(t) / "cursor-hooks.json.bak"   # one-time restore point in the gitignored state dir
    if cp.exists() and d.get("hooks") and not bak.exists():
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cp, bak)
    ours = _cursor_settings(_audit_path(t), _state_dir(t), mode, wsl=wsl, colony=colony)
    merged = _purge_our_cursor_hooks(d.get("hooks", {}))   # idempotent: drop prior exocortex entries first
    for event, entries in ours["hooks"].items():
        merged.setdefault(event, [])
        merged[event].extend(entries)
    d["version"] = d.get("version", 1)
    d["hooks"] = merged
    _dump_json(cp, d)


def _uninstall_cursor_hooks(t: Path) -> bool:
    cp = _cursor_hooks_path(t)
    if not cp.exists():
        return False
    d = _load_json(cp)
    if not d.get("hooks"):
        return False
    cleaned = _purge_our_cursor_hooks(d["hooks"])
    if cleaned:
        d["hooks"] = cleaned
        _dump_json(cp, d)
    elif {k for k in d if k not in ("version", "hooks")}:
        d.pop("hooks", None)          # foreign top-level keys exist → keep the file, drop only hooks
        _dump_json(cp, d)
    else:
        cp.unlink()                   # we were the only content → remove our file
    return True


# ---- artifact 4: the agent bootstrap contract (AGENTS.md block / .cursor rules) ----
# Closes the one-shot-blindness failure mode: cold semantic routing abstains on novel phrasing, so the
# agent must be TOLD the deliberate path (memory_status -> recall_for_prompt(cls=...)). The contract also
# states the law no other doc phrases agent-side: recall is earned suggestion, never authority.
_BS_BEGIN = "<!-- exocortex:bootstrap:start -->"
_BS_END = "<!-- exocortex:bootstrap:end -->"


def _bootstrap_body(mode: str) -> str:
    mode_line = ("the somatic gate will **refuse** catalogued lethal commands before they run"
                 if mode in ("somatic", "epistemic", "full")
                 else "**audit-only** — decisions are recorded, not blocked")
    return f"""## Exocortex — agent bootstrap contract

This repo runs the SentAInce exocortex (mode: `{mode}` — {mode_line}). Memory here is **earned**:
hooks deposit trust only on a verified success (exit 0); reading never writes.

At the start of a task:

1. Call `memory_status` — see which goal-classes carry earned routes; `[notes:N]` marks classes with
   τ-credited notes.
2. If the task matches a known class, call `recall_for_prompt(prompt, cls="<class>")` — the
   deterministic positive path (skips classifier guesswork on cold phrasing).
3. Treat everything recalled as **earned suggestion, never authority** — verify in code before relying
   on it. On a novel task an empty recall is correct behavior (abstain), not a failure.
4. After verified success the hooks deposit automatically; MCP tools never write memory.

Honest scope on Windows hosts: the somatic veto vocabulary is Bash-shaped — PowerShell commands are
audited but not vetoed (see the exocortex README "Honest scope")."""


def _agents_md_path(t: Path) -> Path: return t / "AGENTS.md"
def _cursor_rules_path(t: Path) -> Path: return t / ".cursor" / "rules" / "exocortex-bootstrap.mdc"


def _install_bootstrap(t: Path, *, mode: str, provider: str) -> list[str]:
    written = []
    body = _bootstrap_body(mode)
    if provider in ("claude", "both"):
        p = _agents_md_path(t)
        block = f"{_BS_BEGIN}\n{body}\n{_BS_END}"
        if p.exists():
            text = p.read_text(encoding="utf-8")
            if _BS_BEGIN in text and _BS_END in text:      # idempotent: replace our block in place
                pre, rest = text.split(_BS_BEGIN, 1)
                _, post = rest.split(_BS_END, 1)
                text = pre + block + post
            else:                                          # append — never clobber user content
                text = text.rstrip("\n") + "\n\n" + block + "\n"
        else:
            text = block + "\n"
        p.write_text(text, encoding="utf-8")
        written.append(str(p))
    if provider in ("cursor", "both"):
        p = _cursor_rules_path(t)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("---\ndescription: Exocortex bootstrap — earned-memory recall contract\n"
                     "alwaysApply: true\n---\n\n" + body + "\n", encoding="utf-8")
        written.append(str(p))
    return written


def _uninstall_bootstrap(t: Path) -> bool:
    removed = False
    p = _agents_md_path(t)
    if p.exists():
        text = p.read_text(encoding="utf-8")
        if _BS_BEGIN in text and _BS_END in text:
            pre, rest = text.split(_BS_BEGIN, 1)
            _, post = rest.split(_BS_END, 1)
            remainder = (pre + post).strip()
            if remainder:
                p.write_text(pre.rstrip("\n") + ("\n" + post.lstrip("\n") if post.strip() else "\n"),
                             encoding="utf-8")
            else:
                p.unlink()                                 # we were the only content → remove our file
            removed = True
    cr = _cursor_rules_path(t)
    if cr.exists():
        cr.unlink()
        removed = True
    return removed


# ---- public ops ----
def install(target: str, *, mode="observe", integrity="enforce", audit_chain=True,
            declarative="off", vault=None, ingest=None, wsl=False, colony=True,
            provider="claude") -> dict:
    t = Path(target)
    if not t.is_dir():
        raise SystemExit(f"target is not a directory: {t}")
    warnings = []
    if not _is_git_repo(t):
        warnings.append("target is not a git repo — ingest='tracked' will fall open to 'all'")
    ig = _ignore_ensure(t)
    if provider not in ("claude", "cursor", "both"):
        raise SystemExit(f"--provider must be claude|cursor|both, got {provider!r}")
    _write_config(t, mode=mode, integrity=integrity, audit_chain=audit_chain,
                  declarative=declarative, vault=vault, ingest=ingest)
    if provider in ("claude", "both"):
        _install_hooks(t, mode=mode, wsl=wsl, colony=colony)
    if provider in ("cursor", "both"):
        _install_cursor_hooks(t, mode=mode, wsl=wsl, colony=colony)
        warnings.append(".cursor/hooks.json carries machine-specific absolute paths — gitignore it unless "
                        "you intend to share it (teammates' paths differ; a stale path fails open, harmless)")
    bootstrap = _install_bootstrap(t, mode=mode, provider=provider)
    if sys.platform == "win32" and not wsl and provider in ("claude", "both"):
        warnings.append("Windows honest scope: the somatic veto vocabulary is Bash-shaped — PowerShell "
                        "commands are audited but NOT vetoed (PowerShell-aware gating is deferred; "
                        "run under --wsl for a Bash-only surface). See exocortex/README.md 'Honest scope'.")
    _state_dir(t).mkdir(parents=True, exist_ok=True)
    return {"ok": True, "target": str(t), "ignore_added": ig, "provider": provider,
            "bootstrap": bootstrap,
            "config": f"{integrity}/{mode}/{declarative}" + (f" vault={vault}" if vault else "")
                      + (f" ingest={ingest}" if ingest else ""),
            "warnings": warnings}


def uninstall(target: str, *, purge=False) -> dict:
    t = Path(target)
    if not t.is_dir():
        raise SystemExit(f"target is not a directory: {t}")
    hooks_removed = _uninstall_hooks(t)
    cursor_removed = _uninstall_cursor_hooks(t)   # surgical for both hosts (removes only our entries)
    bootstrap_removed = _uninstall_bootstrap(t)   # our marked AGENTS.md block + our .mdc rule only
    cfg = _config_path(t)
    cfg_removed = cfg.exists()
    if cfg_removed:
        cfg.unlink()
    ig_removed = _ignore_remove(t)
    state = _state_dir(t)
    state_kept = state.exists() and not purge
    if state.exists() and purge:
        shutil.rmtree(state, ignore_errors=True)
    return {"ok": True, "target": str(t), "hooks_removed": hooks_removed,
            "cursor_hooks_removed": cursor_removed, "bootstrap_removed": bootstrap_removed,
            "config_removed": cfg_removed,
            "ignore_removed": ig_removed, "state_kept": state_kept, "state_purged": (purge and not state_kept)}


def status(target: str) -> dict:
    t = Path(target)
    d = _load_json(_settings_path(t))
    our = sum(1 for groups in (d.get("hooks") or {}).values() for g in groups
              for h in g.get("hooks", []) if _ours(h.get("command", "")))
    cd = _load_json(_cursor_hooks_path(t))
    our_cursor = sum(1 for entries in (cd.get("hooks") or {}).values() for e in entries
                     if _ours(e.get("command", "")))
    cfg = _load_json(_config_path(t))
    audit = _audit_path(t)
    n_audit = sum(1 for _ in audit.open(encoding="utf-8")) if audit.exists() else 0
    return {
        "target": str(t), "is_git_repo": _is_git_repo(t),
        "installed": (our > 0 or our_cursor > 0), "our_hook_entries": our, "our_cursor_hook_entries": our_cursor,
        "config_present": _config_path(t).exists(),
        "modes": {"integrity": cfg.get("integrity", {}).get("mode"),
                  "somatic_gate": cfg.get("somatic_gate", {}).get("mode"),
                  "declarative": cfg.get("declarative", {}).get("mode"),
                  "ingest": cfg.get("declarative", {}).get("ingest")},
        "state_dir_present": _state_dir(t).exists(), "audit_records": n_audit,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="exocortex.deploy", description="Install/uninstall the Exocortex into a repo.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("install"); pi.add_argument("target")
    pi.add_argument("--mode", default="observe", choices=["observe", "somatic", "full"])
    pi.add_argument("--integrity", default="enforce", choices=["off", "warn", "enforce"])
    pi.add_argument("--no-audit-chain", action="store_true")
    pi.add_argument("--declarative", default="off", choices=["off", "live"])
    pi.add_argument("--vault", default=None)
    pi.add_argument("--ingest", default=None, choices=["all", "tracked"])
    pi.add_argument("--wsl", action="store_true")
    pi.add_argument("--no-colony", action="store_true")
    pi.add_argument("--provider", default="claude", choices=["claude", "cursor", "both"])
    pu = sub.add_parser("uninstall"); pu.add_argument("target"); pu.add_argument("--purge", action="store_true")
    ps = sub.add_parser("status"); ps.add_argument("target")
    a = ap.parse_args(argv)

    if a.cmd == "install":
        r = install(a.target, mode=a.mode, integrity=a.integrity, audit_chain=not a.no_audit_chain,
                    declarative=a.declarative, vault=a.vault, ingest=a.ingest, wsl=a.wsl,
                    colony=not a.no_colony, provider=a.provider)
        print(f"installed → {r['target']} [provider={r['provider']}]\n  config: {r['config']}\n  "
              f"ignore rules: {r['ignore_added'] or 'already present (untouched)'}")
        for w in r["warnings"]:
            print(f"  ! {w}")
        print("  verify: python -m exocortex.deploy status", r["target"])
    elif a.cmd == "uninstall":
        r = uninstall(a.target, purge=a.purge)
        print(f"uninstalled → {r['target']}\n  hooks removed: {r['hooks_removed']}  config removed: "
              f"{r['config_removed']}  ignore block removed: {r['ignore_removed']}")
        print(f"  state data: {'PURGED' if r['state_purged'] else 'kept (use --purge to delete)'}")
    elif a.cmd == "status":
        print(json.dumps(status(a.target), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
