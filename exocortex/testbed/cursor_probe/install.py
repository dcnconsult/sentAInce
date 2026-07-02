#!/usr/bin/env python3
"""Install / uninstall the Cursor hook PROBE into a target project's ``.cursor/``.

Writes ``<target>/.cursor/hooks.json`` (registering probe.py for every event, with three preToolUse matcher
variants that resolve P0-a) and seeds ``<target>/.cursor/rules/exocortex-probe.mdc``. Absolute --log/--rules
/--tag are baked into each command (Cursor does not forward arbitrary env). Idempotent; ``uninstall`` removes
only our entries (sentinel = ``cursor_probe/probe.py``). Logs default to this dir's ``runs/<project-name>/``.

  python install.py <target-project-dir> [--log <dir>]
  python install.py <target-project-dir> uninstall

Use a THROWAWAY project. This writes into your live Cursor config; restart Cursor after install/uninstall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE = (HERE / "probe.py").as_posix()
MARK = "cursor_probe/probe.py"   # sentinel identifying OUR hook entries

# matchers chosen to disambiguate the engine for a `Shell` tool call:
#   "Shell"   -> fires under exact | regex | glob (baseline: does Shell fire at all)
#   "^Shell$" -> fires ONLY under regex (anchors are literal under exact/glob)
#   "Sh*ll"   -> fires ONLY under glob ("Sh"+anything+"ll"; as regex "Sh*ll" does NOT match "Shell")
_PRE_MATCHERS = [("Shell", "exact"), ("^Shell$", "regex"), ("Sh*ll", "glob")]


def _cmd(event: str, tag: str, log: str, rules: str, timeout: int = 15, deny: bool = False) -> dict:
    d = " --deny" if deny else ""
    return {"command": f'python "{PROBE}" {event} --log "{log}" --rules "{rules}" --tag {tag}{d}',
            "timeout": timeout}


def _hooks_block(log: str, rules: str, deny: bool = False) -> dict:
    pre = [{"matcher": m, **_cmd("preToolUse", tag, log, rules, deny=deny)} for m, tag in _PRE_MATCHERS]
    return {
        "version": 1,
        "hooks": {
            "preToolUse": pre,
            "postToolUse":        [{"matcher": "Shell", **_cmd("postToolUse", "post", log, rules)}],
            "postToolUseFailure": [{"matcher": "Shell", **_cmd("postToolUseFailure", "postfail", log, rules)}],
            "beforeSubmitPrompt": [_cmd("beforeSubmitPrompt", "submit", log, rules)],
            "sessionStart":       [_cmd("sessionStart", "start", log, rules)],
            "preCompact":         [_cmd("preCompact", "compact", log, rules, timeout=30)],
            "stop":               [_cmd("stop", "stop", log, rules)],
        },
    }


def _seed_rules(rules: Path) -> None:
    rules.parent.mkdir(parents=True, exist_ok=True)
    rules.write_text(
        "---\ndescription: EXO-PROBE dynamic rules-file timing test (auto-generated)\nalwaysApply: true\n---\n"
        "EXO-PROBE | seq=0 | ch=rules_file | ev=seed | tag=- | tok=seed0000\n"
        "When asked to list EXO-PROBE lines, echo the line above verbatim.\n", encoding="utf-8")


def _exclude(target: Path) -> None:
    ex = target / ".git" / "info" / "exclude"
    if not ex.parent.is_dir():
        return
    cur = ex.read_text(encoding="utf-8") if ex.exists() else ""
    if "exocortex cursor-probe" in cur:
        return
    block = ("# >>> exocortex cursor-probe >>>\n.cursor/hooks.json\n"
             ".cursor/rules/exocortex-probe.mdc\n# <<< exocortex cursor-probe <<<\n")
    ex.write_text((cur.rstrip() + "\n\n" if cur.strip() else "") + block, encoding="utf-8")


def install(target: Path, log_dir: Path, deny: bool = False) -> None:
    cdir = target / ".cursor"
    rules = cdir / "rules" / "exocortex-probe.mdc"
    log = log_dir / "cursor_probe_log.jsonl"
    log_dir.mkdir(parents=True, exist_ok=True)
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "hooks.json").write_text(json.dumps(_hooks_block(log.as_posix(), rules.as_posix(), deny=deny), indent=2),
                                     encoding="utf-8")
    _seed_rules(rules)
    _exclude(target)
    if deny:
        print("  *** DENY-EVERYTHING TEST MODE: preToolUse returns permission:deny + exit 2 ***")
    print(f"installed cursor-probe into {cdir}")
    print(f"  hooks.json -> {cdir / 'hooks.json'}")
    print(f"  rules      -> {rules}")
    print(f"  log        -> {log}")
    print("Next: FULLY restart Cursor, open this project, follow README.md (the run procedure).")


def uninstall(target: Path) -> None:
    cdir = target / ".cursor"
    hk = cdir / "hooks.json"
    removed = []
    if hk.exists():
        try:
            d = json.loads(hk.read_text(encoding="utf-8"))
            kept = {ev: [e for e in entries if MARK not in str(e.get("command", ""))]
                    for ev, entries in (d.get("hooks") or {}).items()}
            kept = {ev: es for ev, es in kept.items() if es}
            if kept:
                d["hooks"] = kept
                hk.write_text(json.dumps(d, indent=2), encoding="utf-8")
            else:
                hk.unlink(); removed.append(str(hk))
        except Exception:
            pass
    rules = cdir / "rules" / "exocortex-probe.mdc"
    if rules.exists():
        rules.unlink(); removed.append(str(rules))
    print("uninstalled cursor-probe" + (": " + ", ".join(removed) if removed else " (nothing to remove)"))


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(2)
    target = Path(args[0]).resolve()
    if not target.is_dir():
        print(f"error: not a directory: {target}"); sys.exit(2)
    if "uninstall" in args[1:]:
        uninstall(target); return
    log_dir = HERE / "runs" / target.name
    if "--log" in args:
        log_dir = Path(args[args.index("--log") + 1]).resolve()
    install(target, log_dir, deny="--deny" in args)


if __name__ == "__main__":
    main()
