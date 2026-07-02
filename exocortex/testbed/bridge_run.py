"""Slice 5 — the Body Gauge: does the Cortex actually digest the Hippocampus's dream? (Ticket 2)

The bridge-validity gauge proved executable validity is NOT offline-decidable — the body must walk the path.
This harness plants a declarative chain A→B→C→D where **B carries a dependency D genuinely needs** (a magic
token written to a file), offers the provisional **A⇢D** bridge, and runs it through the live hook with a
capable model. It classifies each run into the three behavioral outcomes (the user's mandate):

  PAYOFF  — the body takes A⇢D, synthesizes B's gap correctly, and reaches exit 0 in FEWER steps.
  TOXIC   — the body blindly jumps to D, MISSES B's dependency, and crashes to exit 1 (the lethal hallucination).
  WASTE   — the body ignores the bridge and walks A→B→C→D anyway (the sleep-cycle compute was moot).
  (+ INCOMPLETE — the body never reached D.)

Modes:
  --mode sim   deterministic actors (shortcut_ok / shortcut_fail / walk_full) — validates the CLASSIFIER, no spend.
  --mode real --flagship   the real measurement through claude (native auth). Costs API spend; run only when
               the Ticket-1 soak shows a multi-note tail worth the ATP (else the bridge stays a dormant vestige).

CAVEAT: the classifier is heuristic (step-count + dependency-token + exit code); a behavioral crucible, not a
deterministic lock. STATS ONLY.
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

MAGIC = "BKEYZ91"                       # the dependency token B writes and D requires
GOAL = "SHIPPED"                        # D's success marker
PAYOFF, TOXIC, WASTE, INCOMPLETE = "PAYOFF", "TOXIC", "WASTE", "INCOMPLETE"

# The planted chain. B's step is REQUIRED — D's verify (`grep MAGIC dep.txt`) fails without it.
NOTES = {
    "alpha.md": "# Alpha — deploy task\n\nStart the deploy. It has a required setup step and a final ship step.\n",
    "beta.md":  f"# Beta — REQUIRED setup\n\nWrite the build key first (REQUIRED): `echo {MAGIC} > dep.txt`\n",
    "gamma.md": "# Gamma — check\n\nList the workspace: `ls .`\n",
    "delta.md": f"# Delta — finish\n\nShip it: `grep {MAGIC} dep.txt && echo {GOAL} > done.txt`\n",
}
PROMPT = ("Complete the deploy task described in the 'alpha' note. Follow your notes and use the Bash tool; "
          "report what you ran.")
FULL_CHAIN_STEPS = 3                    # beta + gamma + delta — a shortcut reaches the goal in fewer


# --------------------------------------------------------------- the classifier (shared sim + real)
def classify(trace: list) -> str:
    """trace = ordered list of (command, outcome) where outcome ∈ {'ok','fail'}. Heuristic 3-way + INCOMPLETE."""
    n_bash = len(trace)
    reached = any(GOAL in c and o == "ok" for c, o in trace)
    ship_attempts = [(c, o) for c, o in trace if f"grep {MAGIC}" in c or GOAL in c]
    toxic_fail = any(o == "fail" for _, o in ship_attempts)
    if reached:
        # reached the goal: a true shortcut does it in fewer steps than the full A→B→C→D walk
        return PAYOFF if n_bash < FULL_CHAIN_STEPS else WASTE
    if toxic_fail:
        return TOXIC                    # jumped to D's ship, missed B's dependency → crash
    return INCOMPLETE


# --------------------------------------------------------------- SIM actors (no model; validate classifier)
_SIM_TRACES = {
    "shortcut_ok":   [(f"echo {MAGIC} > dep.txt", "ok"),
                      (f"grep {MAGIC} dep.txt && echo {GOAL} > done.txt", "ok")],          # 2 steps → PAYOFF
    "shortcut_fail": [(f"grep {MAGIC} dep.txt && echo {GOAL} > done.txt", "fail")],         # skipped dep → TOXIC
    "walk_full":     [(f"echo {MAGIC} > dep.txt", "ok"), ("ls .", "ok"),
                      (f"grep {MAGIC} dep.txt && echo {GOAL} > done.txt", "ok")],           # 3 steps → WASTE
}


def run_sim(behavior: str) -> dict:
    trace = _SIM_TRACES[behavior]
    return {"behavior": behavior, "n_bash": len(trace), "outcome": classify(trace)}


# --------------------------------------------------------------- REAL actor (claude → live hook, bridge offered)
def _sandbox_config(vault: Path) -> dict:
    return {"declarative": {"mode": "live", "vault_path": str(vault.resolve()), "explore_budget": 3,
                            "bridge": {"mode": "suggest"}},
            "epistemic_classifier": {"mode": "lexical"}}


def _plant_bridge(state_dir: Path, vault: Path) -> bool:
    """Digest the vault, find the alpha & delta node ids, and plant an offered alpha⇢delta bridge."""
    try:
        from exocortex.wiki.store import load_graph
        os.environ["EXOCORTEX_STATE_DIR"] = str(state_dir)
        g = load_graph(str(vault))
        a = next((nid for nid in g.nodes if nid.split("#")[0] == "alpha.md"), None)
        d = next((nid for nid in g.nodes if nid.split("#")[0] == "delta.md"), None)
        if not (a and d):
            return False
        (state_dir / "wiki_bridges.json").write_text(json.dumps(
            [{"a": a, "d": d, "conf": 0.9, "status": "proposed", "proposed_at": "gauge", "walks": 0}]),
            encoding="utf-8")
        return True
    finally:
        os.environ.pop("EXOCORTEX_STATE_DIR", None)


def run_real(*, model: str, flagship: bool, timeout: int, keep: bool) -> dict:
    sandbox = Path(tempfile.mkdtemp(prefix="exo_bridge_"))
    state_dir = sandbox / ".claude" / "exocortex"
    state_dir.mkdir(parents=True, exist_ok=True)
    vault = sandbox / "vault"
    vault.mkdir()
    for name, text in NOTES.items():
        (vault / name).write_text(text, encoding="utf-8")
    (sandbox / ".claude" / "settings.json").write_text(
        json.dumps(_settings(state_dir / "audit.jsonl", state_dir, "observe", colony=False), indent=2),
        encoding="utf-8")
    (sandbox / "exocortex_config.json").write_text(json.dumps(_sandbox_config(vault)), encoding="utf-8")
    if not _plant_bridge(state_dir, vault):
        shutil.rmtree(sandbox, ignore_errors=True)
        return {"outcome": INCOMPLETE, "error": "could not plant bridge"}

    flags = (f"--output-format stream-json --include-hook-events --verbose --max-turns 8 "
             f"--model {model} --disallowedTools {DISALLOW}")
    cmd = ["claude", "-p", PROMPT, *shlex.split(flags)]
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(sandbox)}
    if flagship:
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_API_KEY", None)
    else:
        env["ANTHROPIC_BASE_URL"] = os.environ.get("ANTHROPIC_BASE_URL") or "http://127.0.0.1:3456"
        env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "sk-local-placeholder")
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(sandbox), env=env, capture_output=True, text=True, timeout=timeout)
        stdout, err, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        stdout, err, rc = "", "TIMEOUT", -1
    wall = round(time.time() - t0, 1)

    audit = _read_audit(state_dir / "audit.jsonl")
    trace = []
    for r in audit:
        if r.get("tool") == "Bash" and r.get("event") == "PreToolUse":
            trace.append([str(r.get("command", "")), None])
    # pair each Bash with its consequence outcome (ordered)
    outcomes = [r.get("outcome") for r in audit if r.get("event") in ("PostToolUse", "PostToolUseFailure")]
    for i, oc in enumerate(outcomes):
        if i < len(trace):
            trace[i][1] = oc or "ok"
    trace = [(c, o or "ok") for c, o in trace]
    res = {"outcome": classify(trace), "n_bash": len(trace), "wall_s": wall, "rc": rc,
           "trace": [c[:70] for c, _ in trace], "final": _extract_result(stdout)[:140],
           "stderr": (err or "")[-200:] if err and err != "TIMEOUT" else ""}
    shutil.rmtree(sandbox, ignore_errors=True) if not keep else res.update(sandbox=str(sandbox))
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Slice 5 — bridge body-gauge (does the Cortex digest the dream?)")
    ap.add_argument("--mode", choices=("sim", "real"), default="sim")
    ap.add_argument("--flagship", action="store_true", help="real via flagship claude (costs API spend)")
    ap.add_argument("--model", default=None)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    model = args.model or ("haiku" if args.flagship else "llama3.1-8b-8k:latest")

    results = []
    if args.mode == "sim":
        for beh in ("shortcut_ok", "shortcut_fail", "walk_full"):
            results.append(run_sim(beh))
    else:
        for i in range(max(1, args.trials)):
            print(f"[{i+1}/{args.trials}] real bridge trial ...", flush=True)
            results.append(run_real(model=model, flagship=args.flagship, timeout=args.timeout, keep=args.keep))

    from collections import Counter
    tally = Counter(r["outcome"] for r in results)
    out = {"mode": ("flagship" if args.flagship else args.mode), "model": model if args.mode == "real" else "sim",
           "n": len(results), "tally": dict(tally), "results": results}
    print("\n=== BRIDGE BODY GAUGE ===")
    print(f"  mode={out['mode']} model={out['model']} n={out['n']}")
    print(f"  outcomes: {dict(tally)}")
    print("  PAYOFF=true shortcut · TOXIC=skipped B's dependency → crash · WASTE=walked the full chain")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
