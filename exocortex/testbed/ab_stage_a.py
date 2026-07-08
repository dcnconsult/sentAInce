"""Stage A sandbox harness — paired same-task splice ON/OFF trials from a frozen golden snapshot.

PREREG: ``results/guide_accrue_ab_v1/PREREG.md`` (Stage A section; metric tiers are binding).
Design: every trial thaws two BYTE-IDENTICAL copies of one golden snapshot (repo tree + exocortex
organs) and runs the SAME task prompt headless (``claude -p``) in each — the only difference is
``EXOCORTEX_COLONY_SPLICE=0`` in the OFF arm. Trials reset from the snapshot, so arms never drift.
"Helping" is measured lexicographically (the fast-but-wrong guard): Tier 1 success (mechanical oracle)
gates everything; Tier 2 efficiency (tokens/steps/duration) is computed over successful runs ONLY;
Tier 3 process and Tier 4 blast-radius are diagnostics, never promotable alone.

    python -m exocortex.testbed.ab_stage_a snapshot --source . --out <dir>
    python -m exocortex.testbed.ab_stage_a run --snapshot <dir> [--repeats 3] [--max-turns 40]
                                               [--model claude-fable-5] [--out runs.jsonl]
                                               [--agent-cmd "<template>"]   # dry-run/BYO override
    python -m exocortex.testbed.ab_stage_a report --runs runs.jsonl [--json]

Cloud-sandbox friendly: the snapshot is relocatable (no absolute paths inside; the trial's hooks and
vault path are re-derived at thaw by ``exocortex.deploy.install``); the harness never reads the local
estate's exocortex — only the snapshot it is given. SAFETY: trials are disposable copies; the source
repo is never written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

# ---- experiment constants (PREREG Stage A; PI-set 2026-07-08) ----
REPEATS = 3
MAX_TURNS = 40
MODEL = "claude-fable-5"            # "same model" — pin explicitly; --model overrides
RUN_TIMEOUT_S = 1800
TARGET_CLS = "guide-accrue#18"
TASKS_FILE = Path(__file__).with_name("ab_tasks.json")

# Hermetic headless launch (verified against the Claude Code CLI docs — see PREREG Stage A §launch):
#   -p                      non-interactive single-prompt run
#   --output-format stream-json + --verbose   per-message JSONL incl. the final result record with
#                            usage (input/output/cache tokens), num_turns, duration, total_cost_usd
#   --include-hook-events    hook firings visible in the stream (the feeder's proven flag set)
#   --max-turns              the pre-registered failure boundary
#   --strict-mcp-config --mcp-config <trial>/ab_mcp_empty.json   NO MCP servers load (hermeticity
#                            control C1 — the lab's contamination lesson: agents bypass the organ via
#                            MCP recall). A FILE, not inline JSON: the Windows .cmd shim strips the
#                            quotes from an inline {"mcpServers":{}} and the CLI then reads it as a path.
#   Permissions: the installed PreToolUse hook is the permission authority (matcher "*", returns
#   allow/deny) — the same mechanism every live install uses; no --dangerously-skip-permissions.
HERMETIC_FLAGS = '--output-format stream-json --include-hook-events --verbose --strict-mcp-config'
MCP_EMPTY_NAME = "ab_mcp_empty.json"

ORGAN_GLOBS = ("colony_*.json", "cues.json", "embed_cues.json")   # what a snapshot carries besides the tree


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rmtree(p: Path) -> None:
    """rmtree that survives Windows read-only git objects (chmod +w on failure, retry). A half-deleted
    trial would collide with the next thaw — deletion must be total, not best-effort.
    ``onexc`` is 3.12+; 3.11 takes the deprecated ``onerror`` (exc_info triple) — support both."""
    import stat

    def _onexc(func, path, exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass
    if not p.exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(p, onexc=_onexc)
    else:
        shutil.rmtree(p, onerror=lambda func, path, exc_info: _onexc(func, path, exc_info[1]))


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


# --------------------------------------------------------------------------------- snapshot
def snapshot(source: Path, out: Path) -> dict:
    """Freeze source's git-tracked tree + exocortex organs + activation config into a relocatable dir."""
    source, out = source.resolve(), out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"snapshot target not empty: {out}")
    ls = _git(source, "ls-files", "-z")
    if ls.returncode != 0:
        raise SystemExit("source is not a git repo (snapshot copies the TRACKED tree)")
    files = [f for f in ls.stdout.split("\0") if f]
    for rel in files:
        src = source / rel
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copy2(src, dst)
    organs = []
    state = source / ".claude" / "exocortex"
    for pat in ORGAN_GLOBS:
        for p in state.glob(pat):
            dst = out / ".claude" / "exocortex" / p.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            organs.append(p.name)
    cfg = source / "exocortex_config.json"
    if cfg.exists():
        shutil.copy2(cfg, out / "exocortex_config.json")
    head = _git(source, "rev-parse", "HEAD").stdout.strip()
    manifest = {"created": _now(), "source": str(source), "source_commit": head,
                "tracked_files": len(files), "organs": sorted(organs),
                "config_carried": cfg.exists()}
    (out / "ab_snapshot.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------------- thaw
def thaw(snap: Path, trial: Path) -> None:
    """One byte-identical trial copy: tree + organs, hooks re-derived FOR THIS PATH by deploy.install
    (settings.local.json / vault_path are never carried from the snapshot — no absolute-path leakage),
    git-initialized so file touches are measurable, organ churn excluded from the git surface."""
    shutil.copytree(snap, trial, dirs_exist_ok=False)
    (trial / "ab_snapshot.json").unlink(missing_ok=True)
    _git(trial, "init", "-q")
    excl = trial / ".git" / "info" / "exclude"
    excl.parent.mkdir(parents=True, exist_ok=True)
    excl.write_text(".claude/\n/exocortex_config.json\nab_runs.jsonl\n", encoding="utf-8")
    # Re-derive the machine-local artifacts for THIS path. Config values mirror the live SentAInce
    # activation (PREREG "held constant"), except integrity=warn: the kernel-lock baseline is not under
    # test and a path-sensitive enforce would apoptose the clone (symmetric across arms, pre-registered).
    from exocortex import deploy
    deploy.install(str(trial), mode="somatic", integrity="warn", audit_chain=True,
                   declarative="live", vault=str(trial), ingest=None, provider="claude")
    (trial / MCP_EMPTY_NAME).write_text('{"mcpServers": {}}\n', encoding="utf-8")   # C1, as a file
    # Baseline commit AFTER install: deploy's artifacts (AGENTS.md bootstrap, settings) are baseline,
    # so the post-run git surface shows ONLY what the agent changed (the Tier 4 metric stays clean).
    _git(trial, "add", "-A")
    _git(trial, "-c", "user.email=ab@stage-a", "-c", "user.name=ab-stage-a",
         "commit", "-q", "-m", "ab snapshot baseline")


# --------------------------------------------------------------------------------- run
def _usage_from_stream(stdout: str) -> dict:
    """Token/turn/cost telemetry from the stream-json output. The final ``result`` record carries the
    authoritative totals; per-message ``usage`` records are summed as a fallback for truncated streams."""
    total = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_creation_tokens": 0}
    final: dict = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        u = (obj.get("message") or {}).get("usage") if isinstance(obj.get("message"), dict) else obj.get("usage")
        if isinstance(u, dict) and obj.get("type") != "result":
            total["input_tokens"] += int(u.get("input_tokens") or 0)
            total["output_tokens"] += int(u.get("output_tokens") or 0)
            total["cache_read_tokens"] += int(u.get("cache_read_input_tokens") or 0)
            total["cache_creation_tokens"] += int(u.get("cache_creation_input_tokens") or 0)
        if obj.get("type") == "result":
            final = obj
    u = final.get("usage") or {}
    return {
        "num_turns": final.get("num_turns"),
        "duration_ms": final.get("duration_ms"),
        "total_cost_usd": final.get("total_cost_usd"),
        "is_error": bool(final.get("is_error", False)) if final else None,
        "subtype": final.get("subtype", ""),
        "input_tokens": int(u.get("input_tokens") or 0) or total["input_tokens"],
        "output_tokens": int(u.get("output_tokens") or 0) or total["output_tokens"],
        "cache_read_tokens": int(u.get("cache_read_input_tokens") or 0) or total["cache_read_tokens"],
        "cache_creation_tokens": int(u.get("cache_creation_input_tokens") or 0) or total["cache_creation_tokens"],
        "model": ((final.get("modelUsage") or {}) and sorted((final.get("modelUsage") or {}).keys())) or None,
    }


def check_oracle(trial: Path, task: dict) -> bool:
    """Mechanical success oracle (no LLM judge, ADR-010): the verify file exists and matches the truth
    regex. A refutation task additionally carries ``verify_absent`` — the false-premise pattern; writing
    it into the file (parroting instead of checking the repo's ground truth) FAILS the oracle."""
    p = trial / task["verify_file"]
    if not p.exists():
        return False
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        if re.search(task["verify_regex"], text, re.IGNORECASE) is None:
            return False
        absent = task.get("verify_absent")
        if absent and re.search(absent, text, re.IGNORECASE) is not None:
            return False
        return True
    except Exception:
        return False


def file_touches(trial: Path, task: dict) -> dict:
    """Tier 4: what changed vs the baseline commit (organ churn already excluded via .git/info/exclude)."""
    out = _git(trial, "status", "--porcelain")
    changed = [ln[3:].strip().strip('"') for ln in out.stdout.splitlines() if ln.strip()]
    scope = [task["verify_file"], *task.get("scope", [])]
    outside = [f for f in changed if not any(f.replace("\\", "/").startswith(s) for s in scope)]
    return {"files_changed": changed, "n_changed": len(changed),
            "out_of_scope": outside, "n_out_of_scope": len(outside)}


def audit_metrics(trial: Path) -> dict:
    """Tier 3 process metrics + controls, from the trial's own audit via the Stage-B instrument."""
    from exocortex.gauge.ab_outcome_gauge import _sessions, session_metrics
    by = _sessions(trial / ".claude" / "exocortex" / "audit.jsonl", None)
    if not by:
        return {"steps": 0, "orientation_reads": 0, "failures": 0, "cls": "", "contaminated": False,
                "n_sessions": 0}
    merged: list = []
    for recs in by.values():
        merged.extend(recs)
    merged.sort(key=lambda r: r["_ts"])
    m = session_metrics("merged", merged)
    return {"steps": m["total_steps"], "orientation_reads": m["orientation_reads"],
            "failures": m["failures"], "cls": m["cls"], "contaminated": m["contaminated"],
            "n_sessions": len(by)}


def launch(trial: Path, prompt: str, arm: str, *, model: str, max_turns: int,
           timeout: int, agent_cmd: str | None) -> tuple[int, str, str, float]:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(trial), "EXOCORTEX_EMBED": "0"}
    env.pop("EXOCORTEX_COLONY_SPLICE", None)
    if arm == "OFF":
        env["EXOCORTEX_COLONY_SPLICE"] = "0"
    if agent_cmd:                                   # dry-run / BYO override (tests; token-free smoke)
        cmd = [c.replace("{prompt}", prompt) for c in shlex.split(agent_cmd)]
    else:
        cmd = ["claude", "-p", prompt, "--max-turns", str(max_turns), "--model", model,
               *shlex.split(HERMETIC_FLAGS), "--mcp-config", str(trial / MCP_EMPTY_NAME)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(trial), env=env, capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout or "", proc.stderr or "", time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT", time.time() - t0


def run_battery(snap: Path, *, tasks: list[dict], repeats: int, max_turns: int, model: str,
                out_path: Path, workdir: Path | None, keep: bool, agent_cmd: str | None,
                transcripts_dir: Path | None = None) -> list[dict]:
    work = workdir or Path(tempfile.mkdtemp(prefix="ab_stage_a_"))
    work.mkdir(parents=True, exist_ok=True)
    # Pre-flight control: every oracle must be UNSATISFIED at baseline, or "success" is free and the
    # trial measures nothing. Fail loudly before any tokens are spent.
    pre = [t["id"] for t in tasks if check_oracle(snap, t)]
    if pre:
        raise SystemExit(f"oracle already satisfied in the snapshot (fix the task marker): {pre}")
    rows = []
    for r in range(repeats):
        arm_order = ("ON", "OFF") if r % 2 == 0 else ("OFF", "ON")   # balance drift within a repeat
        for task in tasks:
            for arm in arm_order:
                trial = work / f"{task['id']}_r{r}_{arm.lower()}"
                _rmtree(trial)
                thaw(snap, trial)
                rc, stdout, stderr, wall = launch(trial, task["prompt"], arm, model=model,
                                                  max_turns=max_turns, timeout=RUN_TIMEOUT_S,
                                                  agent_cmd=agent_cmd)
                row = {
                    "ts": _now(), "task": task["id"], "pair": task.get("pair"), "arm": arm,
                    "repeat": r, "model": model, "max_turns": max_turns,
                    "rc": rc, "wall_s": round(wall, 1), "timed_out": stderr == "TIMEOUT",
                    "success": check_oracle(trial, task),                       # Tier 1
                    **_usage_from_stream(stdout),                               # Tier 2
                    **audit_metrics(trial),                                     # Tier 3 + controls
                    **file_touches(trial, task),                                # Tier 4
                }
                if transcripts_dir:
                    transcripts_dir.mkdir(parents=True, exist_ok=True)
                    (transcripts_dir / f"{task['id']}_r{r}_{arm}.jsonl").write_text(
                        stdout, encoding="utf-8")
                rows.append(row)
                with open(out_path, "a", encoding="utf-8") as f:                # flush per run (crash-safe)
                    f.write(json.dumps(row) + "\n")
                print(f"  [{arm:3s}] {task['id']} r{r}: success={row['success']} steps={row['steps']} "
                      f"out_tok={row['output_tokens']} wall={row['wall_s']}s"
                      f"{' TIMEOUT' if row['timed_out'] else ''}", flush=True)
                if not keep:
                    _rmtree(trial)
    return rows


# --------------------------------------------------------------------------------- report
def _sign_flip_p(deltas: list[float]) -> float:
    """Paired one-sided sign-flip permutation (ON−OFF per task; H1: deltas < 0). Exact ≤ 2^20."""
    n = len(deltas)
    if not n:
        return 1.0
    observed = sum(deltas)
    if n <= 20:
        hits = total = 0
        for mask in range(1 << n):
            s = sum(d if not (mask >> i) & 1 else -d for i, d in enumerate(deltas))
            total += 1
            if s <= observed:
                hits += 1
        return hits / total
    import random
    rng = random.Random(20260708)
    hits = 0
    for _ in range(20000):
        s = sum(d if rng.random() < 0.5 else -d for d in deltas)
        if s <= observed:
            hits += 1
    return hits / 20000


def report(rows: list[dict], as_json: bool = False) -> dict:
    ok_cls = [r for r in rows if r.get("cls") == TARGET_CLS and not r.get("contaminated")]
    excluded = len(rows) - len(ok_cls)
    arms = {"ON": [r for r in ok_cls if r["arm"] == "ON"], "OFF": [r for r in ok_cls if r["arm"] == "OFF"]}
    rep: dict = {"n_rows": len(rows), "n_included": len(ok_cls), "n_excluded_cls_or_contam": excluded}
    # Tier 1 — success rate (primary)
    tier1 = {a: {"n": len(rs), "successes": sum(r["success"] for r in rs),
                 "rate": round(sum(r["success"] for r in rs) / len(rs), 3) if rs else None}
             for a, rs in arms.items()}
    tasks = sorted({r["task"] for r in ok_cls})
    deltas = []
    for t in tasks:
        on = [r["success"] for r in arms["ON"] if r["task"] == t]
        off = [r["success"] for r in arms["OFF"] if r["task"] == t]
        if on and off:
            deltas.append((sum(off) / len(off)) - (sum(on) / len(on)))   # OFF−ON so "ON better" ⇒ <0? no:
    # ON better on success = higher rate ⇒ delta_success = ON−OFF per task, H1: > 0. Flip sign for _sign_flip_p.
    deltas = [-d for d in deltas]
    rep["tier1_success"] = {**tier1, "paired_p_on_better": round(_sign_flip_p([-d for d in deltas]), 4)}
    # Tier 2 — efficiency, CONDITIONAL ON SUCCESS (the fast-but-wrong guard)
    tier2 = {}
    for metric in ("output_tokens", "input_tokens", "steps", "wall_s", "num_turns"):
        vals = {a: [r[metric] for r in rs if r["success"] and isinstance(r.get(metric), (int, float))]
                for a, rs in arms.items()}
        if vals["ON"] and vals["OFF"]:
            tier2[metric] = {"ON_median": median(vals["ON"]), "OFF_median": median(vals["OFF"]),
                             "n": (len(vals["ON"]), len(vals["OFF"]))}
    rep["tier2_efficiency_given_success"] = tier2
    # Tier 3 / 4 — diagnostics
    rep["tier3_process"] = {a: {"median_orientation": median([r["orientation_reads"] for r in rs]) if rs else None,
                                "median_failures": median([r["failures"] for r in rs]) if rs else None}
                            for a, rs in arms.items()}
    rep["tier4_blast_radius"] = {a: {"runs_with_out_of_scope": sum(1 for r in rs if r["n_out_of_scope"]),
                                     "median_files_changed": median([r["n_changed"] for r in rs]) if rs else None}
                                 for a, rs in arms.items()}
    rep["timeouts"] = {a: sum(1 for r in rs if r.get("timed_out")) for a, rs in arms.items()}
    if as_json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"Stage A report — {len(ok_cls)}/{len(rows)} runs included "
              f"(excluded {excluded}: wrong class / contaminated)")
        t1 = rep["tier1_success"]
        for a in ("ON", "OFF"):
            print(f"  Tier1 {a:3s}: {t1[a]['successes']}/{t1[a]['n']} success ({t1[a]['rate']})")
        print(f"  Tier1 paired sign-flip p (ON better): {t1['paired_p_on_better']}")
        for m, v in rep["tier2_efficiency_given_success"].items():
            print(f"  Tier2 {m}: ON~{v['ON_median']} vs OFF~{v['OFF_median']} (n={v['n']}, success-only)")
        print(f"  Tier3 orientation: ON~{rep['tier3_process']['ON']['median_orientation']} "
              f"OFF~{rep['tier3_process']['OFF']['median_orientation']}  ·  Tier4 out-of-scope runs: "
              f"ON={rep['tier4_blast_radius']['ON']['runs_with_out_of_scope']} "
              f"OFF={rep['tier4_blast_radius']['OFF']['runs_with_out_of_scope']}  ·  timeouts {rep['timeouts']}")
        print("  (numbers only — the PREREG Stage A rule renders the disposition)")
    return rep


# --------------------------------------------------------------------------------- cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="exocortex.testbed.ab_stage_a")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("snapshot"); ps.add_argument("--source", default="."); ps.add_argument("--out", required=True)
    pr = sub.add_parser("run"); pr.add_argument("--snapshot", required=True)
    pr.add_argument("--tasks", default=str(TASKS_FILE)); pr.add_argument("--repeats", type=int, default=REPEATS)
    pr.add_argument("--max-turns", type=int, default=MAX_TURNS); pr.add_argument("--model", default=MODEL)
    pr.add_argument("--out", default="ab_stage_a_runs.jsonl"); pr.add_argument("--workdir", default=None)
    pr.add_argument("--keep", action="store_true"); pr.add_argument("--agent-cmd", default=None)
    pr.add_argument("--transcripts", default=None)
    pr.add_argument("--task-filter", default=None, help="comma-separated task ids (a pilot slice)")
    pp = sub.add_parser("report"); pp.add_argument("--runs", required=True); pp.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "snapshot":
        m = snapshot(Path(a.source), Path(a.out))
        print(json.dumps(m, indent=2))
        return 0
    if a.cmd == "run":
        tasks = json.loads(Path(a.tasks).read_text(encoding="utf-8"))
        if a.task_filter:
            want = set(a.task_filter.split(","))
            tasks = [t for t in tasks if t["id"] in want]
        print(f"Stage A: {len(tasks)} tasks × {a.repeats} repeats × 2 arms = {len(tasks)*a.repeats*2} runs "
              f"(model {a.model}, cap {a.max_turns} turns)")
        run_battery(Path(a.snapshot), tasks=tasks, repeats=a.repeats, max_turns=a.max_turns,
                    model=a.model, out_path=Path(a.out),
                    workdir=Path(a.workdir) if a.workdir else None, keep=a.keep,
                    agent_cmd=a.agent_cmd,
                    transcripts_dir=Path(a.transcripts) if a.transcripts else None)
        print(f"rows → {a.out}; next: python -m exocortex.testbed.ab_stage_a report --runs {a.out}")
        return 0
    rows = [json.loads(ln) for ln in Path(a.runs).read_text(encoding="utf-8").splitlines() if ln.strip()]
    report(rows, as_json=a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
