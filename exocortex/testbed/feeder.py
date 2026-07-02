"""Slice-4 repo-feeder — drive a repo through the Exocortex hooks to accrue real vitals.

The fuel pump for the testbed: it runs N episodes of scripted, tool-forcing tasks through `claude -p`
(flagship or a BYO model via ccr) against a **disposable** repo with the six hooks installed. Each
episode's Write/Edit (PreToolUse) + Bash verify (PostToolUse consequence -> colony deposit -> seg_len)
grows `<repo>/.claude/exocortex/{audit.jsonl,colony_*.json}` — exactly the vitals the multi-repo
exporter charts and the future Tuner consumes. The summary doubles as the **science check**: the
seg_len >=4 tail vs the flagship baseline (median 2, ~26% >=4) is the eligibility-trace (3D) flip-trigger.

SAFETY: the feeder drives a real agent that EDITS FILES and COMMITS. It runs only against a repo it
created (marked with `.exo_feeder`) unless you pass `--force`. Default target is a fresh disposable repo
under the projects root so the exporter auto-discovers it. Never point it at a repo you care about.

Run (flagship baseline):
  python -m exocortex.testbed.feeder --episodes 8
Run (BYO model via ccr; set ANTHROPIC_BASE_URL=http://127.0.0.1:3456 first):
  python -m exocortex.testbed.feeder --episodes 8 --model llama3.1-8b-8k
Setup only (create + wire the repo, no model calls — for inspection / CI):
  python -m exocortex.testbed.feeder --setup-only
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from exocortex.runner import _settings, _extract_result, _read_audit  # noqa: E402

# Default projects root = the parent of this repo (so a feed repo is a direct child the exporter scans).
DEFAULT_PROJECTS_ROOT = Path(_ROOT).resolve().parent
FEEDER_MARKER = ".exo_feeder"
FLAGSHIP_TAIL_BASELINE = 0.26   # ~26% of deposit windows are >=4 edges on haiku+sonnet (the 3D trigger ref)

# Shrink the request so a small BYO num_ctx fits (harmless for flagship). Mirrors proof_route_a.
DISALLOW = ("Agent,CronCreate,CronDelete,CronList,DesignSync,EnterWorktree,ExitWorktree,Monitor,"
            "NotebookEdit,PowerShell,PushNotification,ScheduleWakeup,SendMessage,Skill,TaskCreate,"
            "TaskGet,TaskList,TaskOutput,TaskStop,TaskUpdate,WebFetch,WebSearch,Workflow,LSP")

# A tiny seed project to give edit tasks a surface. Written once on first run.
SEED_FILES = {
    "calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    "notes.md": "# Notes\n\n- initial\n",
    "README.md": "# Feeder sandbox\n\nDisposable repo for the Exocortex repo-feeder (Slice 4). Safe to delete.\n",
}

# Scripted, tool-forcing tasks. Each = one Write/Edit (PreToolUse) + one Bash verify (consequence ->
# deposit -> seg_len). Multi-step ones lengthen the deposit window (the >=4 tail the science check measures).
TASKS = [
    "In calc.py, add a function `sub(a, b)` that returns a - b. Then run "
    "`python -c \"import calc; print(calc.sub(5, 2))\"` and report the output.",
    "Append a line '- review docs' to notes.md, then run `cat notes.md` and report what you saw.",
    "Add a function `mul(a, b)` to calc.py that returns a * b. Then run `python -m pytest -q` and "
    "report pass/fail.",
    "Create a new file utils.py with a function `is_even(n)` returning `n % 2 == 0`. Verify with "
    "`python -c \"import utils; print(utils.is_even(4))\"`.",
    "Create a file VERSION whose only contents are 0.1.0, then run `cat VERSION` to verify.",
    "Add a function `div(a, b)` to calc.py that returns a / b, or None if b == 0. Verify with "
    "`python -c \"import calc; print(calc.div(10, 2), calc.div(1, 0))\"`.",
    "Add a one-line docstring to the `add` function in calc.py, then run "
    "`python -c \"import calc; print(calc.add.__doc__)\"`.",
    "Stage and commit all changes with `git add -A && git commit -m feeder-change`, then run "
    "`git log --oneline -1` and report the commit.",
]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)


def ensure_repo(repo: Path, force: bool) -> None:
    """Create + seed + hook-wire a disposable feed repo (idempotent). Refuses a pre-existing non-feeder dir."""
    if repo.exists() and any(repo.iterdir()) and not (repo / FEEDER_MARKER).exists() and not force:
        raise SystemExit(
            f"[feeder] refusing: {repo} exists and is not a feeder repo (no {FEEDER_MARKER}). "
            f"Pass --force only if it is genuinely disposable.")
    repo.mkdir(parents=True, exist_ok=True)
    (repo / FEEDER_MARKER).write_text("disposable repo created by exocortex.testbed.feeder\n", encoding="utf-8")
    if not (repo / ".git").exists():
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "feeder@exocortex.local")
        _git(repo, "config", "user.name", "exo-feeder")
    for rel, body in SEED_FILES.items():
        p = repo / rel
        if not p.exists():
            p.write_text(body, encoding="utf-8")
    # .gitignore the runtime state so the agent's `git add -A` never tries to commit the audit trail.
    gi = repo / ".gitignore"
    if not gi.exists():
        gi.write_text(".claude/exocortex/\n/exocortex_config.json\n", encoding="utf-8")
    state_dir = repo / ".claude" / "exocortex"
    state_dir.mkdir(parents=True, exist_ok=True)
    audit_path = state_dir / "audit.jsonl"
    (repo / ".claude" / "settings.json").write_text(
        json.dumps(_settings(audit_path, state_dir, "observe"), indent=2), encoding="utf-8")
    # an initial commit so later `git commit` tasks have a HEAD to build on
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feeder seed")


def run_episode(repo: Path, task: str, model: str | None, disallow: str,
                max_turns: int, timeout: int) -> dict:
    flags = f"--output-format stream-json --include-hook-events --verbose --max-turns {max_turns}"
    if model:
        flags += f" --model {model}"
    if disallow:
        flags += f" --disallowedTools {disallow}"
    cmd = ["claude", "-p", task, *shlex.split(flags)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(repo),
                              env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
                              capture_output=True, text=True, timeout=timeout)
        rc, stdout, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        rc, stdout, err = -1, "", "TIMEOUT"
    return {"rc": rc, "wall_s": round(time.time() - t0, 1),
            "final": _extract_result(stdout), "err": err}


def summarize(repo: Path) -> dict:
    state_dir = repo / ".claude" / "exocortex"
    audit = _read_audit(state_dir / "audit.jsonl")
    cons = [r for r in audit if r.get("event") in ("PostToolUse", "PostToolUseFailure")]
    ok = sum(1 for r in cons if r.get("outcome") == "ok")
    fail = sum(1 for r in cons if r.get("outcome") == "fail")
    seglens = [r["seg_len"] for r in cons if isinstance(r.get("seg_len"), int) and r["seg_len"] > 0]
    n = len(seglens)
    ge4 = sum(1 for s in seglens if s >= 4)
    seglens_sorted = sorted(seglens)
    median = seglens_sorted[n // 2] if n else 0
    colonies = sorted((state_dir).glob("colony_*.json"))
    return {
        "audit_records": len(audit),
        "pre": sum(1 for r in audit if r.get("event") == "PreToolUse"),
        "consequences": len(cons), "ok": ok, "fail": fail,
        "deposits": n, "seg_len_median": median,
        "seg_len_ge4": ge4, "seg_len_ge4_pct": round(ge4 / n, 3) if n else 0.0,
        "seg_lens": seglens_sorted, "colony_classes": len(colonies),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Exocortex repo-feeder (Slice 4) — accrue real vitals")
    ap.add_argument("--repo-path", default=None,
                    help="disposable target repo (default: <projects-root>/_feed_demo)")
    ap.add_argument("--projects-root", default=str(DEFAULT_PROJECTS_ROOT),
                    help="where the default feed repo is created (must be the exporter's scan root to auto-show)")
    ap.add_argument("--label", default="demo", help="feed repo name suffix -> _feed_<label>")
    ap.add_argument("--model", default=None, help="claude --model (omit=flagship default; e.g. llama3.1-8b-8k for BYO)")
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--tasks", default=None, help="custom task file (one prompt per line); default=built-in suite")
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=300, help="per-episode seconds")
    ap.add_argument("--disallow", default=DISALLOW, help="tools to strip ('' to keep all)")
    ap.add_argument("--setup-only", action="store_true", help="create + wire the repo, no model calls")
    ap.add_argument("--force", action="store_true", help="allow a non-feeder target dir (be sure it's disposable)")
    args = ap.parse_args()

    repo = Path(args.repo_path).resolve() if args.repo_path else \
        (Path(args.projects_root).resolve() / f"_feed_{args.label}")
    ensure_repo(repo, args.force)
    print(f"[feeder] repo={repo}")

    if args.setup_only:
        print("[feeder] setup-only: repo created + hooks wired. Run without --setup-only to generate vitals.")
        print(json.dumps(summarize(repo), indent=2))
        return 0

    tasks = TASKS
    if args.tasks:
        tasks = [ln.strip() for ln in Path(args.tasks).read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not tasks:
        raise SystemExit("[feeder] no tasks")

    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    via = "BYO/ccr" if ("127.0.0.1" in base or "localhost" in base) else "flagship default"
    print(f"[feeder] model={args.model or '(default)'} via {via}; episodes={args.episodes}")
    for i in range(args.episodes):
        task = tasks[i % len(tasks)]
        r = run_episode(repo, task, args.model, args.disallow, args.max_turns, args.timeout)
        tag = "ok" if r["rc"] == 0 else f"rc={r['rc']}"
        print(f"  ep {i+1:>2}/{args.episodes}  {tag:>6}  {r['wall_s']:>5}s  task={task[:54]!r}")
        if r["err"] and r["err"] != "TIMEOUT":
            print(f"        stderr: {r['err'].strip()[-160:]}")

    s = summarize(repo)
    print("\n=== FEED SUMMARY (vitals accrued) ===")
    print(f"  audit records : {s['audit_records']}   PreToolUse: {s['pre']}")
    print(f"  consequences  : {s['consequences']}  (ok {s['ok']} / fail {s['fail']})")
    print(f"  deposits      : {s['deposits']}   colony classes: {s['colony_classes']}")
    print(f"  seg_len       : median {s['seg_len_median']}   >=4 tail {s['seg_len_ge4']}/{s['deposits']} "
          f"= {s['seg_len_ge4_pct']*100:.1f}%   dist={s['seg_lens']}")
    print(f"  SCIENCE CHECK : >=4 tail {s['seg_len_ge4_pct']*100:.1f}% vs flagship baseline "
          f"{FLAGSHIP_TAIL_BASELINE*100:.0f}% -> "
          f"{'FATTER (eligibility-trace 3D may earn its keep)' if s['seg_len_ge4_pct'] > FLAGSHIP_TAIL_BASELINE else 'not fatter (3D stays dormant — data gates ambition)'}")
    print(f"\n  Dashboard: http://localhost:3000  ($repo -> {repo.name})  ·  control: http://localhost:9109/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
