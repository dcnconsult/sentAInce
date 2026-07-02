"""Slice-1 smoke test for the BYO-model testbed (Route A).

Proves the *central gotcha* is solved: a non-Claude (ollama) model, fronted by claude-code-router,
drives the six Exocortex hooks and grows an audit trail with `seg_len` records — exactly what the
live install does, but backed by a local model instead of a flagship Claude model.

Prereqs (see README.md):
  1. `npm i -g @musistudio/claude-code-router`
  2. copy ccr/config.example.json -> ~/.claude-code-router/config.json
  3. `ccr start`  (server on 127.0.0.1:3456)
  4. env: ANTHROPIC_BASE_URL=http://127.0.0.1:3456  ANTHROPIC_API_KEY=<placeholder>

Run:
  python -m exocortex.testbed.proof_route_a --model qwen2.5-coder:32b

It wires a throwaway sandbox with the six hooks (observe mode, reusing runner._settings), runs one
tool-using turn through `claude -p`, then reports whether PreToolUse/PostToolUse records (and any
`seg_len`) landed. Non-zero exit if no audit was produced (the proxy/hook wiring is wrong).
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

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from exocortex.runner import _settings, _extract_result, _read_audit  # noqa: E402

# A deliberately tool-forcing task: a Write (PreToolUse, all-tools matcher) + a Bash verify
# (PreToolUse + PostToolUse consequence -> colony deposit -> seg_len). Small enough for a local model.
PROMPT = ("Create a file named proof.txt whose only contents are the word PROOF. "
          "Then run the shell command `cat proof.txt` to verify it, and report what you saw.")

# This Claude Code build ships ~30 built-in tool definitions (Agent, Cron*, DesignSync, Monitor,
# Workflow, Task*, Web*, Skill, ...). Sent verbatim they bloat the request to ~26k tokens — which a
# local model needs a huge (and, on modest HW, too-slow) num_ctx to fit, or it truncates and narrates
# instead of calling tools. Disallowing the non-essentials drops the request to ~4k tokens (just the
# 6 file/shell tools), so a small fast context window suffices. KEEP Bash/Write/Read/Edit/Glob/Grep.
DISALLOW = ("Agent,CronCreate,CronDelete,CronList,DesignSync,EnterWorktree,ExitWorktree,Monitor,"
            "NotebookEdit,PowerShell,PushNotification,ScheduleWakeup,SendMessage,Skill,TaskCreate,"
            "TaskGet,TaskList,TaskOutput,TaskStop,TaskUpdate,WebFetch,WebSearch,Workflow,LSP")


def main() -> int:
    ap = argparse.ArgumentParser(description="Route-A BYO-model proof (ccr -> ollama drives the hooks)")
    ap.add_argument("--model", default="qwen2.5-coder:32b", help="ollama model (via ccr Router)")
    ap.add_argument("--max-turns", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--disallow", default=DISALLOW,
                    help="comma-separated tools to strip from the request (shrinks the prompt; '' to keep all)")
    ap.add_argument("--keep", action="store_true", help="keep the sandbox for inspection")
    args = ap.parse_args()

    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    if "127.0.0.1" not in base and "localhost" not in base:
        print(f"[warn] ANTHROPIC_BASE_URL={base!r} — expected the ccr proxy (http://127.0.0.1:3456). "
              f"Without it, `claude` talks to Anthropic, not ollama.", file=sys.stderr)

    sandbox = Path(tempfile.mkdtemp(prefix="exo_proofA_"))
    audit_path = sandbox / ".claude" / "exocortex" / "audit.jsonl"
    state_dir = sandbox / ".claude" / "exocortex"
    state_dir.mkdir(parents=True, exist_ok=True)
    (sandbox / ".claude" / "settings.json").write_text(
        json.dumps(_settings(audit_path, state_dir, "observe"), indent=2), encoding="utf-8")

    flags = (f"--output-format stream-json --include-hook-events --verbose "
             f"--max-turns {args.max_turns} --model {args.model}")
    if args.disallow:
        flags += f" --disallowedTools {args.disallow}"
    cmd = ["claude", "-p", args.prompt, *shlex.split(flags)]
    print(f"[proof] model={args.model} base={base or '(unset)'} sandbox={sandbox}")
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(sandbox),
                              env={**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox)},
                              capture_output=True, text=True, timeout=args.timeout)
        stdout, err, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        stdout, err, rc = "", "TIMEOUT", -1
    elapsed = round(time.time() - t0, 1)

    final = _extract_result(stdout)
    audit = _read_audit(audit_path)
    pre = [r for r in audit if r.get("event") == "PreToolUse"]
    cons = [r for r in audit if r.get("event") in ("PostToolUse", "PostToolUseFailure")]
    seglens = [r["seg_len"] for r in cons if isinstance(r.get("seg_len"), int)]

    print("\n=== ROUTE-A PROOF ===")
    print(f"  wall_s        : {elapsed}   rc={rc}")
    print(f"  audit records : {len(audit)}")
    print(f"  PreToolUse    : {len(pre)}")
    print(f"  consequences  : {len(cons)}  (seg_len values: {seglens})")
    print(f"  final (head)  : {final[:200]!r}")
    if err and err != "TIMEOUT":
        print(f"  stderr (tail) : {err.strip()[-300:]}")

    ok = len(audit) > 0 and len(pre) > 0
    print(f"\n  RESULT: {'PASS — a non-Claude model drove the hooks' if ok else 'FAIL — no hook activity (check ccr proxy / config / num_ctx)'}")
    if args.keep:
        print(f"  sandbox kept at: {sandbox}")
    else:
        shutil.rmtree(sandbox, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
