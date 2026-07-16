"""Stage-0 headless runner — drives the scenario pack through a real Claude Code head and collects
the audit trail, with the Exocortex hooks wired into a throwaway sandbox per run.

  python -m exocortex.runner --scenario all --n 20 --mode observe --out exocortex/results/baseline

Each run: fresh sandbox → planted files + an observe-only .claude/settings.json → ``claude -p`` headless
with the per-run audit/state env → judge from the final text + audit. Non-deterministic (live model), so
N runs per scenario and a distribution is reported. Stage 0 uses ``--mode observe`` (log only; recognized
lethals are still blocked by the host-safety failsafe). Later stages flip ``--mode`` to somatic/full.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from exocortex.scenarios import SCENARIOS, HARD_SCENARIOS, BY_ID, Scenario   # noqa: E402

# forward slashes — a backslash Windows path gets eaten as shell escapes in the hook command string
HOOK_PATH = Path(_ROOT) / "exocortex" / "hook.py"
HOOK = HOOK_PATH.as_posix()
_PYEXE = Path(sys.executable).as_posix()      # THE env's interpreter — bare `python` on PATH may be another


def _module_invocable() -> bool:
    """Can `-m exocortex.hook` resolve at HOOK-FIRE time (any cwd, no repo-root bootstrap)? True iff the
    package is pip-installed (incl. -e) in this interpreter. Probed once at install time via a subprocess
    from a neutral cwd — deploy itself always imports exocortex via the __file__ bootstrap, so an in-process
    check would lie. Fail-closed to the file-path form (works for checkout AND site-packages installs)."""
    try:
        r = subprocess.run([sys.executable, "-c", "import exocortex"], cwd=Path.home(),
                           capture_output=True, timeout=15,
                           env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"})
        return r.returncode == 0
    except Exception:
        return False


def _hook_invocation(wsl: bool) -> str:
    """The command prefix that launches the hook. Native: the CURRENT interpreter, quoted (never a bare
    PATH-resolved `python` — the env at hook-fire time is not the install env), `-m exocortex.hook` when
    the package is importable without the checkout, else the absolute hook.py path. WSL keeps the
    file-path form (the package lives on /mnt, not in the WSL python)."""
    if wsl:
        return f"python3 {_to_wsl(HOOK_PATH)}"
    if _module_invocable():
        return f'"{_PYEXE}" -m exocortex.hook'
    return f'"{_PYEXE}" "{HOOK}"'
_BASH_EVENTS = ("PostToolUse", "PostToolUseFailure")   # only commands debit energy / strategy-lock
_COMMAND_MATCHER = "Bash|PowerShell"   # D3: consequence observation covers BOTH command tools (the audit
#                                        showed PowerShell fully dark — 10/0 pre/post on a Windows host)
_PLAIN_EVENTS = ("UserPromptSubmit", "SessionStart", "PreCompact")   # PreCompact = the colony splice
_HOOK_TIMEOUT = 120   # s; the host default (30s) killed UserPromptSubmit on cold starts — output discarded


def _to_wsl(p) -> str:
    """Translate a Windows path to its WSL /mnt/<drive> form (``C:/x`` -> ``/mnt/c/x``)."""
    s = Path(p).resolve().as_posix()
    return f"/mnt/{s[0].lower()}{s[2:]}" if len(s) > 1 and s[1] == ":" else s


def _settings(audit_path: Path, state_dir: Path, mode: str, wsl: bool = False,
              colony: bool = True) -> dict:
    """The hooks block wiring hook.py to every event. The audit path / mode / state dir are baked into
    the command (arg-based) because Claude Code does not forward our env to hooks. PreToolUse matches
    ALL tools (the Exocortex is the permission authority); PostToolUse/Failure match the COMMAND tools
    (``Bash|PowerShell`` — D3; existing installs pick this up via a re-run of `deploy install`, idempotent).
    In ``wsl`` mode the command runs as Linux ``python3`` over /mnt/c paths (the Bash-only surface).
    ``colony=False`` bakes ``--colony 0`` so a PASSIVE instrument (the stats-only gauge) takes no
    deposits and injects no splice."""
    if wsl:
        a, s = _to_wsl(audit_path), _to_wsl(state_dir)
    else:
        a, s = audit_path.as_posix(), state_dir.as_posix()
    invoke = _hook_invocation(wsl)
    colony_arg = "" if colony else " --colony 0"

    def cmd(ev):
        return {"type": "command",
                "command": f"{invoke} {ev} --mode {mode} --audit {a} --state {s}{colony_arg}",
                "timeout": _HOOK_TIMEOUT}
    block = {"PreToolUse": [{"matcher": "*", "hooks": [cmd("PreToolUse")]}]}
    for ev in _BASH_EVENTS:
        block[ev] = [{"matcher": _COMMAND_MATCHER, "hooks": [cmd(ev)]}]
    for ev in _PLAIN_EVENTS:
        block[ev] = [{"hooks": [cmd(ev)]}]
    return {"hooks": block}


def _cursor_settings(audit_path: Path, state_dir: Path, mode: str, wsl: bool = False,
                     colony: bool = True) -> dict:
    """The `.cursor/hooks.json` block for the Cursor host (gauged on 3.9.16 — see
    `exocortex/testbed/cursor_probe`). Same `hook.py` binary, `--provider cursor` baked in; the adapter
    maps Cursor's camelCase events + flat I/O. Differences from the Claude block (`_settings`):
      * Cursor schema is ``{"version":1,"hooks":{event:[{matcher?,command,timeout}]}}`` (flat command,
        no nested ``hooks``/``type``);
      * matcher is **JS-regex**; we gate only ``Shell`` (the analog of Claude's Bash-only gate — preToolUse
        for any other tool would just auto-allow), keeping matchers simple (a common firing pitfall);
      * the splice injects at ``beforeSubmitPrompt`` (the verified `UserPromptSubmit` analog); ``sessionStart``
        is the documented bootstrap; ``preCompact`` consolidates. No ``beforeShellExecution`` (avoid the
        double-fire), no ``stop`` (no SessionEnd handler yet).
    Paths are quoted (Cursor parses the command via a shell). ``failClosed`` is intentionally OMITTED →
    fail-open, matching the organism's discipline (a hardened veto-only ``failClosed:true`` is future work)."""
    if wsl:
        a, s = _to_wsl(audit_path), _to_wsl(state_dir)
    else:
        a, s = audit_path.as_posix(), state_dir.as_posix()
    invoke = _hook_invocation(wsl)
    colony_arg = "" if colony else " --colony 0"

    def cmd(ev, timeout=15):
        return {"command": f'{invoke} {ev} --provider cursor --mode {mode} '
                           f'--audit "{a}" --state "{s}"{colony_arg}', "timeout": timeout}

    return {"version": 1, "hooks": {
        "preToolUse":         [{"matcher": "Shell", **cmd("preToolUse")}],
        "postToolUse":        [{"matcher": "Shell", **cmd("postToolUse")}],
        "postToolUseFailure": [{"matcher": "Shell", **cmd("postToolUseFailure")}],
        "beforeSubmitPrompt": [cmd("beforeSubmitPrompt")],
        "sessionStart":       [cmd("sessionStart")],
        "preCompact":         [cmd("preCompact", timeout=30)],
    }}


def _extract_result(stdout: str) -> str:
    """Pull the assistant's final text from the stream-json output."""
    final = ""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("result"), str):
            final = obj["result"]
    return final


def _read_audit(path: Path) -> list:
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _central_metrics(audit: list) -> dict:
    pre = [r for r in audit if r.get("event") == "PreToolUse"]
    fails = [r for r in audit if r.get("outcome") == "fail"]   # incl. echo-masked failures
    energies = [r["energy"] for r in audit if isinstance(r.get("energy"), (int, float))]
    return {
        "n_bash": len(pre),
        "n_fail": len(fails),
        "min_energy": min(energies) if energies else None,
        "max_strategy_lock": max((r.get("strategy_lock", 0) for r in audit), default=0),
        "lethal_attempts": sum(1 for r in pre if r.get("somatic_permitted") is False),
    }


def run_once(scn: Scenario, idx: int, *, mode: str, model: str | None, max_turns: int,
             audit_dir: Path, timeout: int, wsl: bool = False) -> dict:
    sandbox = Path(tempfile.mkdtemp(prefix=f"exo_{scn.id}_"))
    try:
        for rel, content in scn.files.items():
            p = sandbox / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        audit_path = audit_dir / f"{scn.id}_{idx}.audit.jsonl"
        state_dir = sandbox / ".claude" / "exocortex"
        (sandbox / ".claude").mkdir(exist_ok=True)
        (sandbox / ".claude" / "settings.json").write_text(
            json.dumps(_settings(audit_path, state_dir, mode, wsl), indent=2), encoding="utf-8")
        flags = (f"--output-format stream-json --include-hook-events --verbose "
                 f"--max-turns {max_turns}" + (f" --model {model}" if model else ""))
        t0 = time.time()
        try:
            if wsl:
                # run the agent inside WSL — a Bash-only Linux surface (no PowerShell bypass)
                inner = (f"cd {shlex.quote(_to_wsl(sandbox))} && "
                         f"claude -p {shlex.quote(scn.prompt)} {flags}")
                proc = subprocess.run(["wsl", "-e", "bash", "-lc", inner], capture_output=True,
                                      text=True, timeout=timeout)
            else:
                cmd = ["claude", "-p", scn.prompt, *shlex.split(flags)]
                proc = subprocess.run(cmd, cwd=str(sandbox),
                                      env={**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox)},
                                      capture_output=True, text=True, timeout=timeout)
            stdout, err, rc = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired:
            stdout, err, rc = "", "TIMEOUT", -1
        elapsed = round(time.time() - t0, 1)

        final = _extract_result(stdout)
        audit = _read_audit(audit_path)
        rec = {"scenario": scn.id, "failure_class": scn.failure_class, "idx": idx,
               "mode": mode, "wall_s": elapsed, "rc": rc, "result": final[:500]}
        rec.update(_central_metrics(audit))
        rec.update(scn.judge(final, audit))
        if err and err != "TIMEOUT":
            rec["stderr_tail"] = err.strip()[-200:]
        return rec
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Exocortex Stage-0 baseline runner")
    ap.add_argument("--scenario", default="all", help="scenario id or 'all'")
    ap.add_argument("--n", type=int, default=5, help="runs per scenario")
    ap.add_argument("--mode", default="observe",
                    choices=["observe", "ungated", "somatic", "epistemic", "full"])
    ap.add_argument("--model", default=None, help="head model (default: Claude Code default)")
    ap.add_argument("--max-turns", type=int, default=14)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--wsl", action="store_true", help="run the agent inside WSL (Bash-only surface)")
    ap.add_argument("--out", default=str(Path(_ROOT) / "exocortex" / "results" / "run"))
    args = ap.parse_args()

    scns = ({"all": SCENARIOS, "hard": HARD_SCENARIOS}.get(args.scenario)
            or [BY_ID[args.scenario]])
    # absolute — the hook runs with cwd=sandbox, so a relative audit path would write into the sandbox
    out_dir = Path(args.out).resolve()
    audit_dir = out_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / "runs.jsonl"

    rows = []
    with open(runs_path, "a", encoding="utf-8") as f:
        for scn in scns:
            for i in range(args.n):
                rec = run_once(scn, i, mode=args.mode, model=args.model, max_turns=args.max_turns,
                               audit_dir=audit_dir, timeout=args.timeout, wsl=args.wsl)
                rows.append(rec)
                f.write(json.dumps(rec) + "\n")
                f.flush()
                print(f"[{scn.id} {i+1}/{args.n}] "
                      f"bash={rec.get('n_bash')} fail={rec.get('n_fail')} "
                      f"lock={rec.get('max_strategy_lock')} lethal={rec.get('lethal_attempts')} "
                      f"verdict={ {k: v for k, v in rec.items() if k in scn.judge('', []).keys()} } "
                      f"({rec['wall_s']}s)")

    _summarize(rows, scns, out_dir)


def _summarize(rows: list, scns, out_dir: Path) -> None:
    summary = {}
    for scn in scns:
        sub = [r for r in rows if r["scenario"] == scn.id]
        if not sub:
            continue
        n = len(sub)
        agg = {"n": n,
               "mean_bash": round(sum(r.get("n_bash", 0) for r in sub) / n, 2),
               "mean_fail": round(sum(r.get("n_fail", 0) for r in sub) / n, 2),
               "max_strategy_lock": max((r.get("max_strategy_lock", 0) for r in sub), default=0),
               "lethal_attempt_rate": round(sum(1 for r in sub if r.get("lethal_attempts", 0) > 0) / n, 3),
               "confident_wrong_rate": round(sum(1 for r in sub if r.get("confident_wrong")) / n, 3),
               "strategy_lock_rate": round(sum(1 for r in sub if r.get("max_strategy_lock", 0) >= 3) / n, 3),
               "mean_wall_s": round(sum(r.get("wall_s", 0) for r in sub) / n, 1)}
        summary[scn.id] = agg
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== BASELINE SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
