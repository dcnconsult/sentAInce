"""Stats-only stream driver — runs a controlled, replayable Stream of build steps over a PERSISTENT
sandbox (the app accumulates → recurrence) through WSL ``claude``, capturing the P0 decision-trace per
step plus an objective per-step ``verify`` (ground-truth consequence). PASSIVE: no memory injection, no
veto beyond the lethal failsafe. Emits raw JSONL only — no claims, no verdicts.

  python -m exocortex.stream_runner --stream smoke --model haiku --out exocortex/results/stream_smoke
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

from exocortex.runner import _settings, _to_wsl, _read_audit, _extract_result   # noqa: E402
from exocortex.streams import BY_NAME                                            # noqa: E402


def _wsl(inner: str, timeout: int):
    try:
        p = subprocess.run(["wsl", "-e", "bash", "-lc", inner], capture_output=True, text=True,
                            timeout=timeout)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"


def run_stream(stream, *, model, out_dir: Path, max_turns: int, timeout: int) -> None:
    sandbox = Path(tempfile.mkdtemp(prefix=f"exo_stream_{stream.name}_"))
    sandbox_wsl = _to_wsl(sandbox)
    audit_dir = out_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    steps_path = out_dir / "steps.jsonl"
    state_dir = sandbox / ".claude" / "exocortex"
    (sandbox / ".claude").mkdir(parents=True, exist_ok=True)
    try:
        with open(steps_path, "a", encoding="utf-8") as sf:
            for i, step in enumerate(stream.steps):
                audit_path = audit_dir / f"{i:02d}_{step.id}.jsonl"
                (sandbox / ".claude" / "settings.json").write_text(
                    json.dumps(_settings(audit_path, state_dir, "observe", wsl=True, colony=False),
                               indent=2),   # passive gauge: no live deposits/splice (offline colony only)
                    encoding="utf-8")
                run_cmd = (f"cd {shlex.quote(sandbox_wsl)} && claude -p {shlex.quote(step.prompt)} "
                           f"--output-format stream-json --include-hook-events --verbose "
                           f"--max-turns {max_turns}" + (f" --model {model}" if model else ""))
                t0 = time.time()
                rc, stdout, _ = _wsl(run_cmd, timeout)
                elapsed = round(time.time() - t0, 1)
                final = _extract_result(stdout)

                vrc, vout, verr = (0, "", "")
                if step.verify:
                    vrc, vout, verr = _wsl(f"cd {shlex.quote(sandbox_wsl)} && {step.verify}", 60)
                vblob = f"{vout}\n{verr}"
                verify_pass = (vrc == 0) and (step.expect.lower() in vblob.lower() if step.expect else True)

                audit = _read_audit(audit_path)
                rec = {"idx": i, "step_id": step.id, "goal_class": step.goal_class, "stream": stream.name,
                       "wall_s": elapsed, "rc": rc, "n_trace": len(audit),
                       "step_verify": "PASS" if verify_pass else "FAIL", "verify_rc": vrc,
                       "result": final[:300], "verify_out": vblob.strip()[:200]}
                sf.write(json.dumps(rec) + "\n")
                sf.flush()
                print(f"[{i:02d} {step.id} {step.goal_class}] "
                      f"verify={'PASS' if verify_pass else 'FAIL'} trace={len(audit)} ({elapsed}s)")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Exocortex stats-only stream driver (passive)")
    ap.add_argument("--stream", default="smoke", choices=sorted(BY_NAME))
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", default=str(Path(_ROOT) / "exocortex" / "results" / "stream"))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    run_stream(BY_NAME[args.stream], model=args.model, out_dir=out,
               max_turns=args.max_turns, timeout=args.timeout)


if __name__ == "__main__":
    main()
