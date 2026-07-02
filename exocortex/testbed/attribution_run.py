"""Layer-2 attribution-precision run — validate echo-attribution on REAL BYO action buffers (Ticket 1 / #2).

The offline gauge (``gauge/attribution_gauge.py``) measured precision on SYNTHETIC action buffers and
recommended ``min_overlap=2``. This harness checks that on REAL ones: a planted-token vault driven through
the live hook by an ollama model (Route A: ``claude`` -> claude-code-router -> ollama), scored against
ground truth.

Plant: each task has ONE solution note carrying a unique MAGIC token + the exact shell command to emit it,
plus distractors — one COINCIDENTAL (shares a common token like ``echo`` with the solution command, the
real precision stressor) and one pure-prose. The task can only be completed by reading the note and running
its command, so an exit-0 carrying the magic token ⟹ the solution note was genuinely USED. Attribution
then credits whatever its content-echo decides; we score those credits against the known plant.

  precision = credited-from-solution / all-credited   (the crown-jewel metric: false credits = dilution)
  recall    = solution-credited ? 1 : 0               (per completed task)
  completion= did the model actually run the magic command and exit 0 (small-model reliability)

Modes:
  --mode sim   deterministic actor (runs the solution command in-process) — validates the plant + scorer
               + the wiki functions, no ollama. Fast; used by the test suite.
  --mode real  the BYO loop (needs ccr up + ANTHROPIC_BASE_URL=the proxy). The actual Layer-2 measurement.

Run (real):
  ANTHROPIC_BASE_URL=http://127.0.0.1:3456 ANTHROPIC_API_KEY=local \\
    python -m exocortex.testbed.attribution_run --mode real --model llama3.1-8b-8k:latest \\
           --tasks 4 --min-overlap 2 --json results.json
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

from exocortex.runner import _settings, _extract_result, _read_audit          # noqa: E402
from exocortex.testbed.proof_route_a import DISALLOW                           # noqa: E402
from exocortex.wiki.attribute import deposit_attributed                       # noqa: E402
from exocortex.wiki.propose import propose                                    # noqa: E402
from exocortex.wiki.splice import splice_with_ids                            # noqa: E402
from exocortex.wiki.store import load_graph                                   # noqa: E402


# --------------------------------------------------------------- the planted corpus (ground truth)
def plant() -> list:
    """Planted tasks. Each solution note's MAGIC token is distinctive; the coincidental distractor shares
    a COMMON token (echo) with the solution command — so min_overlap=1 should false-credit it and =2 not."""
    raw = [
        ("deploy", "FREQOK7Q2A", "echo FREQOK7Q2A > done.txt",
         "Check progress with `echo working`."),
        ("migrate", "FREQMG5W1B", "echo FREQMG5W1B > done.txt",
         "Roll back with `echo rollback`."),
        ("seed", "FREQSD8K3C", "echo FREQSD8K3C > done.txt",
         "Reset later with `echo reset`."),
        ("token", "FREQTK4P7D", "echo FREQTK4P7D > done.txt",
         "Rotate it with `echo rotate`."),
        ("build", "FREQBD6R9E", "echo FREQBD6R9E > done.txt",
         "Clean with `echo clean`."),
    ]
    tasks = []
    for topic, magic, cmd, coincidental in raw:
        tasks.append({
            "id": topic,
            "magic": magic,
            "solution_cmd": cmd,
            "solution_file": f"{topic}.md",
            "notes": [
                (f"{topic}.md", f"# {topic.capitalize()} task\n\nTo finish the {topic}, run exactly this "
                                f"shell command: `{cmd}`\n"),
                (f"{topic}-ops.md", f"# {topic.capitalize()} ops\n\n{coincidental}\n"),       # coincidental
                (f"{topic}-doc.md", f"# {topic.capitalize()} theory\n\nThe {topic} step promotes state "
                                    f"through the pipeline.\n"),                               # pure prose
            ],
            # MUST contain the topic keyword (the lexical proposer surfaces the note by it) and MUST NOT
            # leak the magic token (else the model echoes the prompt, not the note → contaminated truth).
            "prompt": (f"Finish the {topic} task. Your notes contain the exact shell command for it — find "
                       f"that command and run it verbatim with the Bash tool (it writes done.txt). Run "
                       f"nothing else, then report exactly what you ran."),
        })
    return tasks


def _write_vault(task: dict, vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    for name, text in task["notes"]:
        (vault / name).write_text(text, encoding="utf-8")


def _credited_docs(credited_ids, vault_files: set) -> dict:
    """Map credited node ids -> their doc (file). Only vault docs count (ignore the cue root)."""
    docs = {}
    for nid in credited_ids:
        doc = str(nid).split("#", 1)[0]
        if doc in vault_files:
            docs[nid] = doc
    return docs


def _score_task(task: dict, credited_ids: set) -> dict:
    vault_files = {n[0] for n in task["notes"]}
    docs = _credited_docs(credited_ids, vault_files)
    tp = sum(1 for d in docs.values() if d == task["solution_file"])
    fp = sum(1 for d in docs.values() if d != task["solution_file"])
    return {"id": task["id"], "credited": sorted(docs.values()),
            "tp": tp, "fp": fp, "solution_credited": tp > 0}


# --------------------------------------------------------------- SIM actor (deterministic, no ollama)
def run_sim(task: dict, *, explore: int, min_overlap: int) -> dict:
    """Drive the wiki functions directly with a deterministic actor that runs the solution command.
    Validates the plant + scorer + attribution end-to-end without a model."""
    sandbox = Path(tempfile.mkdtemp(prefix="exo_attrSim_"))
    try:
        vault = sandbox / "vault"
        _write_vault(task, vault)
        os.environ["EXOCORTEX_STATE_DIR"] = str(sandbox / "state")
        graph = load_graph(str(vault), label="_default")
        cands = propose(graph, prompt=task["prompt"])
        _, injected = splice_with_ids(graph, cands, explore=explore)
        used = deposit_attributed(graph, injected, task["solution_cmd"], 0,
                                  cue="cue:_default", label="_default", min_overlap=min_overlap, save=False)
        res = _score_task(task, set(used))
        res.update(completed=True, injected=len(injected), used=len(used))
        return res
    finally:
        os.environ.pop("EXOCORTEX_STATE_DIR", None)
        shutil.rmtree(sandbox, ignore_errors=True)


# --------------------------------------------------------------- REAL actor (claude -> ccr -> ollama)
def _sandbox_config(vault: Path, explore: int, min_overlap: int) -> dict:
    return {"declarative": {"mode": "live", "vault_path": str(vault.resolve()),
                            "explore_budget": explore, "attribution": {"min_overlap": min_overlap}},
            "epistemic_classifier": {"mode": "lexical"}}   # no MiniLM in the hook (faster)


def _read_colony_credits(state_dir: Path, vault_files: set) -> set:
    """The notes that earned τ this run — credited node ids, read from the persisted colony."""
    credited = set()
    for p in state_dir.glob("colony_*.json"):
        try:
            tau = json.loads(p.read_text(encoding="utf-8")).get("tau", {})
        except Exception:
            continue
        for edge in tau:
            for part in str(edge).split("\t"):
                if part.split("#", 1)[0] in vault_files:
                    credited.add(part)
    return credited


def run_real(task: dict, *, model: str, explore: int, min_overlap: int, timeout: int, keep: bool,
             flagship: bool = False) -> dict:
    sandbox = Path(tempfile.mkdtemp(prefix="exo_attrReal_"))
    state_dir = sandbox / ".claude" / "exocortex"
    state_dir.mkdir(parents=True, exist_ok=True)
    audit_path = state_dir / "audit.jsonl"
    vault = sandbox / "vault"
    _write_vault(task, vault)
    (sandbox / ".claude" / "settings.json").write_text(
        json.dumps(_settings(audit_path, state_dir, "observe", colony=False), indent=2), encoding="utf-8")
    (sandbox / "exocortex_config.json").write_text(
        json.dumps(_sandbox_config(vault, explore, min_overlap)), encoding="utf-8")

    flags = (f"--output-format stream-json --include-hook-events --verbose --max-turns 6 "
             f"--model {model} --disallowedTools {DISALLOW}")
    cmd = ["claude", "-p", task["prompt"], *shlex.split(flags)]
    if flagship:
        # flagship: claude talks to Anthropic with the user's native auth — NO ccr override, NO key stub
        base = "(flagship/anthropic)"
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox)}
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_API_KEY", None)
    else:
        base = os.environ.get("ANTHROPIC_BASE_URL") or "http://127.0.0.1:3456"
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox), "ANTHROPIC_BASE_URL": base,
               "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "sk-local-placeholder")}
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(sandbox), env=env, capture_output=True, text=True, timeout=timeout)
        stdout, err, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        stdout, err, rc = "", "TIMEOUT", -1
    wall = round(time.time() - t0, 1)

    audit = _read_audit(audit_path)
    vault_files = {n[0] for n in task["notes"]}
    ran_magic = any(task["magic"] in str(r.get("command", "")) for r in audit if r.get("event") == "PreToolUse")
    exit0 = any(r.get("event") == "PostToolUse" and r.get("outcome") == "ok" for r in audit)
    wiki_injected = sum(int(r.get("wiki_injected", 0) or 0) for r in audit)
    wiki_used = sum(int(r.get("wiki_used", 0) or 0) for r in audit)
    credited = _read_colony_credits(state_dir, vault_files)

    res = _score_task(task, credited)
    res.update(completed=bool(exit0 and ran_magic), ran_magic=ran_magic, exit0=exit0,
               wiki_injected=wiki_injected, wiki_used=wiki_used, wall_s=wall, rc=rc,
               final=_extract_result(stdout)[:160], stderr=(err or "")[-200:] if err and err != "TIMEOUT" else "")
    if keep:
        res["sandbox"] = str(sandbox)
    else:
        shutil.rmtree(sandbox, ignore_errors=True)
    return res


# --------------------------------------------------------------- scoring + report
def aggregate(results: list) -> dict:
    completed = [r for r in results if r.get("completed")]
    tp = sum(r["tp"] for r in completed)
    fp = sum(r["fp"] for r in completed)
    sol = sum(1 for r in completed if r["solution_credited"])
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = sol / len(completed) if completed else None
    return {"n_tasks": len(results), "n_completed": len(completed),
            "completion_rate": round(len(completed) / len(results), 3) if results else 0.0,
            "precision": round(precision, 3) if precision is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "tp": tp, "fp": fp, "per_task": results}


def main() -> int:
    ap = argparse.ArgumentParser(description="Layer-2 attribution-precision run (real BYO via ccr->ollama)")
    ap.add_argument("--mode", choices=("sim", "real"), default="sim")
    ap.add_argument("--flagship", action="store_true",
                    help="real mode via flagship claude (native Anthropic auth, no ccr) — costs API spend")
    ap.add_argument("--model", default=None, help="ollama model (BYO) or claude model (flagship); auto by default")
    ap.add_argument("--tasks", type=int, default=5, help="number of planted tasks to run (<= corpus size)")
    ap.add_argument("--min-overlap", type=int, default=2)
    ap.add_argument("--explore", type=int, default=8, help="explore_budget so cold notes inject")
    ap.add_argument("--timeout", type=int, default=300, help="per-task timeout (real mode)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    model = args.model or ("haiku" if args.flagship else "llama3.1-8b-8k:latest")
    tasks = plant()[: max(1, args.tasks)]
    results = []
    for i, task in enumerate(tasks, 1):
        tag = "flagship" if args.flagship else args.mode
        print(f"[{i}/{len(tasks)}] {tag} task={task['id']} min_overlap={args.min_overlap} ...", flush=True)
        if args.mode == "sim":
            r = run_sim(task, explore=args.explore, min_overlap=args.min_overlap)
        else:
            r = run_real(task, model=model, explore=args.explore, min_overlap=args.min_overlap,
                         timeout=args.timeout, keep=args.keep, flagship=args.flagship)
        print(f"     -> completed={r.get('completed')} credited={r.get('credited')} "
              f"tp={r['tp']} fp={r['fp']}" + (f" wall={r.get('wall_s')}s" if args.mode == "real" else ""),
              flush=True)
        results.append(r)

    agg = aggregate(results)
    agg.update(mode=("flagship" if args.flagship else args.mode),
               model=(model if args.mode == "real" else "sim"), min_overlap=args.min_overlap)
    print("\n=== LAYER-2 ATTRIBUTION RUN ===")
    print(f"  mode={agg['mode']} model={agg['model']} min_overlap={agg['min_overlap']}")
    print(f"  completed {agg['n_completed']}/{agg['n_tasks']} (rate {agg['completion_rate']})")
    print(f"  precision={agg['precision']} recall={agg['recall']}  (TP={agg['tp']} FP={agg['fp']})")
    if args.json:
        Path(args.json).write_text(json.dumps(agg, indent=2), encoding="utf-8")
        print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
