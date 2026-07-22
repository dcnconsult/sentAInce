"""``sentaince`` — the organism's command line.

The human-facing surface that does NOT depend on hook-UI rendering (the SessionStart
``systemMessage`` vitals line is doc-claimed but unverifiable headlessly — this CLI is the
promised, enforceable fallback; see hook._vitals).

Subcommands:
  ``sentaince status [path] [--full]`` -> the vitals voice line (``--full``: + usage report)
  ``sentaince body   [path]``      -> start the exporter (if not already up) and open the body page
  ``sentaince why    [path]``      -> render the latest deposits' consequence provenance (read-only)
  ``sentaince <other> ...``        -> dispatched to an installed ``sentaince.commands`` entry point

Extension point: third-party packages register console subcommands under the entry-points
group ``sentaince.commands`` (``name = "pkg.module:func"``; the function receives the argv
tail and returns an exit code). Discovery is deliberately LAZY — plugins are imported only
when an unknown subcommand is actually typed. ``status`` and ``body`` never touch the plugin
machinery, so a broken plugin can never break the vitals voice. Hook code never imports this
module.
"""
from __future__ import annotations

import copy
import json
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

DEFAULT_PORT = 9109
_STATE = (".claude", "exocortex")


def _say(line: str) -> None:
    """Print, surviving legacy Windows consoles that can't encode emoji (the vitals line must
    never crash the vitals command)."""
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


def _genome(root: Path) -> dict:
    """DEFAULTS deep-merged with the repo's config — same semantics as the exporter's
    ``load_genome_for``, importing only the core genome module. Fail-safe: DEFAULTS."""
    from exocortex.genome import DEFAULTS, _SOMATIC_ALIAS, _deep_merge
    g = copy.deepcopy(DEFAULTS)
    cfg = root / "exocortex_config.json"
    if cfg.is_file():
        try:
            _deep_merge(g, json.loads(cfg.read_text(encoding="utf-8")))
        except Exception:
            pass
    sm = str(g["somatic_gate"].get("mode", "observe")).lower()
    g["somatic_gate"]["mode"] = _SOMATIC_ALIAS.get(sm, sm)
    return g


def _routes(state_dir: Path) -> int:
    """Earned routes = retained τ edges across every per-class colony (raw JSON read — no
    hook/colony imports, so ``status`` stays stdlib-pure)."""
    n = 0
    for p in sorted(state_dir.glob("colony_*.json")):
        try:
            tau = json.loads(p.read_text(encoding="utf-8")).get("tau")
            n += len(tau) if isinstance(tau, dict) else 0
        except Exception:
            pass
    return n


def cmd_status(argv: list[str]) -> int:
    """The vitals voice line, unchanged. With ``--full``, follow it with the usage report
    (issue: the organism's only visible event is a refusal, ~1 per 1,000 calls, so a
    working install and a dead one otherwise look identical — see exocortex.usage)."""
    args = [a for a in argv if not a.startswith("-")]
    full = "--full" in argv or "-f" in argv
    root = Path(args[0] if args else ".").resolve()
    state = root.joinpath(*_STATE)
    if not state.is_dir():
        _say(f"🧬 sentaince: not deployed in {root}")
        _say(f"   deploy with:  python -m exocortex.deploy install {root}")
        return 1
    g = _genome(root)
    bits = [f"mode={g['somatic_gate']['mode']}"]
    n = _routes(state)
    bits.append(f"{n} routes earned" if n else "no routes yet — earning starts on your first exit 0")
    integ = str(g.get("integrity", {}).get("mode", "off"))
    if integ != "off":
        bits.append(f"integrity={integ}")
    _say("🧬 sentaince: " + " · ".join(bits) + f"  [{root.name}]")
    if full:
        # Imported on demand so the vitals line stays stdlib-thin and a fault in the
        # reporter can never break `sentaince status` (the same discipline as `why`).
        try:
            from exocortex.usage import render as _render
            _say("")
            _say(_render(state))
        except Exception as exc:                              # fail-safe, never fatal
            _say(f"   (usage report unavailable: {exc})")
    return 0


def cmd_why(argv: list[str]) -> int:
    """Render one repo's latest-deposit provenance as Markdown (issue #13). A strict reader —
    imports the renderer only on demand, so it never touches the hook/vitals path."""
    root = Path(argv[0] if argv and not argv[0].startswith("-") else ".").resolve()
    state = root.joinpath(*_STATE)
    if not state.is_dir():
        _say(f"🧬 sentaince: not deployed in {root}")
        return 1
    last = 3
    if "--last" in argv:
        try:
            last = int(argv[argv.index("--last") + 1])
        except (IndexError, ValueError):
            _say("usage: sentaince why [path] [--last N]")
            return 2
    from exocortex.provenance import render as _render
    _say(_render(state / "audit.jsonl", last=last, state_dir=state))
    return 0


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def cmd_body(argv: list[str]) -> int:
    """Open the body page — starting the exporter first if nothing is listening. The exporter
    scans the target repo's PARENT directory, so every deployed sibling repo appears too (the
    estate view); loopback-only by default."""
    root = Path(argv[0] if argv else ".").resolve()
    port = DEFAULT_PORT
    if "--port" in argv:
        try:
            port = int(argv[argv.index("--port") + 1])
        except (IndexError, ValueError):
            _say("usage: sentaince body [path] [--port N]")
            return 2
    url = f"http://127.0.0.1:{port}/"
    if not _listening(port):
        scan = root.parent if root.joinpath(*_STATE).is_dir() else root
        subprocess.Popen(
            [sys.executable, "-m", "exocortex.testbed.exporter.metrics",
             "--scan-root", str(scan), "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        for _ in range(20):                                   # wait for the socket, max ~5s
            if _listening(port):
                break
            time.sleep(0.25)
        else:
            _say(f"🧬 sentaince: exporter did not come up on :{port} — run it by hand:")
            _say(f"   python -m exocortex.testbed.exporter.metrics --scan-root {scan}")
            return 1
        _say(f"🧬 sentaince: exporter started (scanning {scan})")
    _say(f"🧬 sentaince: opening {url}")
    webbrowser.open(url)
    return 0


def _dispatch_plugin(name: str, argv: list[str]) -> int:
    """LAZY plugin dispatch — the ONLY place the entry-points machinery is touched."""
    try:
        from importlib.metadata import entry_points
        eps = entry_points(group="sentaince.commands")
    except Exception:
        eps = []
    for ep in eps:
        if ep.name == name:
            return int(ep.load()(argv) or 0)
    known = sorted({"status", "body", "why"} | {ep.name for ep in eps})
    _say(f"sentaince: unknown command '{name}'. Known: {', '.join(known)}")
    return 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        _say((__doc__ or "sentaince").strip().split("\n\n")[0])
        _say("\ncommands:\n  status [path] [--full] the vitals voice line (--full: + usage report)\n"
             "  body [path] [--port N] start the exporter + open the body page\n"
             "  why [path] [--last N]  render the latest deposits' consequence provenance\n"
             "  <plugin> ...           an installed sentaince.commands entry point")
        return 0
    cmd, tail = argv[0], argv[1:]
    if cmd == "status":
        return cmd_status(tail)
    if cmd == "body":
        return cmd_body(tail)
    if cmd == "why":
        return cmd_why(tail)
    return _dispatch_plugin(cmd, tail)


if __name__ == "__main__":
    raise SystemExit(main())
