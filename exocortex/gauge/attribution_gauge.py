"""Attribution-precision gauge — the honest gate before flipping ``declarative.mode = live`` (Ticket 1 / #2).

The live wiki credits a note iff its distinctive content ECHOES in the exit-0 segment's actions
(``wiki.attribute``). This gauge measures whether that echo actually tracks USE, against GROUND TRUTH —
which only exists in CONTROLLED scenarios, so the corpus is synthetic-but-realistic: each "task" injects
some genuinely-used notes (their distinctive content drives the action) alongside DISTRACTORS, including
the real failure mode — *coincidental echo* (a distractor sharing a common token like ``git``/``kubectl``
with an action driven by a DIFFERENT note). Pure-prose distractors (no salient tokens) are the safe case.

It runs the REAL ``attribute_used`` over each scenario and sweeps ``min_overlap``:
  · precision = of the notes credited, how many were truly used (the crown-jewel metric — false credits
    reimport semantic dilution).
  · recall    = of the truly-used notes, how many got credited (missed credit only slows learning; the
    bootstrap exploration + repeat-exposure recover it — so precision is weighted higher).

STATS ONLY: the numbers gate the flag-flip; the recommendation is the smallest ``min_overlap`` whose
precision clears a target (precision-first, matching the consequence-sourcing asymmetry). No verdict baked
in — the operator reads the curve and sets ``declarative.attribution.min_overlap``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.wiki.attribute import attribute_used          # noqa: E402  (the live mechanism under test)
from exocortex.wiki.node import ExonNode, WikiGraph          # noqa: E402


def _note(nid: str, text: str, used: bool) -> dict:
    return {"id": nid, "text": text, "used": used}


def scenarios() -> list:
    """Labeled tasks. Each used note's distinctive content appears in ``action`` (so recall is reachable);
    each distractor is genuinely NOT used — but some share a COMMON token with the action (the coincidental-
    echo precision stressor) and some are pure prose (the safe case)."""
    return [
        {"name": "deploy_common_token", "action": "kubectl apply -f k8s/prod.yaml", "notes": [
            _note("deploy#cmd", "Deploy: `kubectl apply -f k8s/prod.yaml`", True),
            _note("deploy#concept", "Kubernetes schedules pods onto nodes.", False),       # prose → safe
            _note("deploy#status", "Inspect with `kubectl get pods`.", False)]},           # coincidental: kubectl
        {"name": "path_single_token", "action": "edited src/auth/login.py def login", "notes": [
            _note("auth#path", "Login logic: `src/auth/login.py`", True),                  # one distinctive token
            _note("auth#concept", "Authentication verifies identity.", False),
            _note("auth#nearmiss", "Schema: `src/auth/login.yaml`", False)]},              # near-miss path
        {"name": "flag_single_token", "action": "curl --max-retries 5 https://api", "notes": [
            _note("net#flag", "Add `--max-retries 5` for flaky nets.", True),
            _note("net#concept", "Curl transfers data over HTTP.", False)]},
        {"name": "pure_conceptual_distractors", "action": "pytest -q tests/unit", "notes": [
            _note("test#cmd", "Run `pytest -q`.", True),
            _note("test#tdd", "Write the test first.", False),                             # prose → safe
            _note("test#ci", "CI runs on every push.", False)]},                           # prose → safe
        {"name": "coincidental_git", "action": "git rebase main", "notes": [
            _note("git#rebase", "Rebase: `git rebase main`", True),
            _note("git#commit", "Commit: `git commit -m`", False)]},                       # coincidental: git
        {"name": "multi_used", "action": "make release && cp out dist/app.bin", "notes": [
            _note("build#cmd", "Build: `make release`", True),
            _note("build#artifact", "Output to `dist/app.bin`", True),                     # second used note
            _note("build#concept", "Releases are versioned.", False)]},
        {"name": "nearmiss_no_overmatch", "action": "vim config.prod.yaml", "notes": [
            _note("cfg#prod", "Edit `config.prod.yaml`", True),
            _note("cfg#dev", "Dev uses `config.dev.yaml`", False)]},                       # must NOT match
        {"name": "prose_only_safe", "action": "alembic upgrade head", "notes": [
            _note("mig#cmd", "Migrate: `alembic upgrade head`", True),
            _note("mig#prose", "Always run the suite before deploy.", False)]},            # prose → safe
        {"name": "coincidental_ruff", "action": "ruff check .", "notes": [
            _note("lint#check", "Lint: `ruff check .`", True),
            _note("lint#format", "Format: `ruff format`", False)]},                        # coincidental: ruff
        {"name": "distinctive_identifier", "action": "grep compute_holonomy src/freqos.py", "notes": [
            _note("fn#holonomy", "See `compute_holonomy(` in the router.", True),
            _note("fn#concept", "Holonomy accumulates around a loop.", False)]},
    ]


def _score(min_overlap: int) -> dict:
    tp = fp = fn = tn = 0
    per = []
    for scn in scenarios():
        g = WikiGraph()
        for n in scn["notes"]:
            g.add(ExonNode(id=n["id"], text=n["text"]))
        truth = {n["id"] for n in scn["notes"] if n["used"]}
        credited = set(attribute_used(g, [n["id"] for n in scn["notes"]], scn["action"],
                                      min_overlap=min_overlap))
        s_tp = len(credited & truth)
        s_fp = len(credited - truth)
        s_fn = len(truth - credited)
        s_tn = len(g.nodes) - s_tp - s_fp - s_fn
        tp += s_tp; fp += s_fp; fn += s_fn; tn += s_tn
        per.append({"name": scn["name"], "tp": s_tp, "fp": s_fp, "fn": s_fn,
                    "false_credits": sorted(credited - truth), "missed": sorted(truth - credited)})
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    f05 = (1.25 * precision * recall / (0.25 * precision + recall)) if (0.25 * precision + recall) else 0.0
    return {"min_overlap": min_overlap, "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "f05": round(f05, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "per_scenario": per}


def sweep(overlaps=(1, 2, 3)) -> list:
    return [_score(mo) for mo in overlaps]


def recommend(rows: list, precision_target: float = 0.9) -> dict:
    """Precision-first (the crown-jewel asymmetry): the SMALLEST min_overlap whose precision clears the
    target; if none do, the highest-precision one (flagged). Recall is reported but not the gate — the
    bootstrap exploration + repeat-exposure recover missed credit."""
    ok = [r for r in rows if r["precision"] >= precision_target]
    if ok:
        best = min(ok, key=lambda r: r["min_overlap"])
        return {"min_overlap": best["min_overlap"], "reason": f"smallest min_overlap with precision≥{precision_target}",
                "precision": best["precision"], "recall": best["recall"], "target_met": True}
    best = max(rows, key=lambda r: (r["precision"], r["recall"]))
    return {"min_overlap": best["min_overlap"], "reason": f"NO min_overlap reached precision≥{precision_target}; highest-precision",
            "precision": best["precision"], "recall": best["recall"], "target_met": False}


def run(precision_target: float = 0.9, overlaps=(1, 2, 3)) -> dict:
    rows = sweep(overlaps)
    scns = scenarios()
    return {"n_scenarios": len(scns),
            "n_used": sum(1 for s in scns for n in s["notes"] if n["used"]),
            "n_notes": sum(len(s["notes"]) for s in scns),
            "precision_target": precision_target,
            "sweep": rows, "recommended": recommend(rows, precision_target)}


def _print(res: dict) -> None:
    print(f"Attribution-precision gauge — {res['n_scenarios']} tasks, "
          f"{res['n_used']} used / {res['n_notes']} injected notes (synthetic ground truth)")
    print(f"  {'min_overlap':>11} {'precision':>9} {'recall':>7} {'F1':>6} {'F0.5':>6} "
          f"{'TP':>4} {'FP':>4} {'FN':>4}")
    for r in res["sweep"]:
        print(f"  {r['min_overlap']:>11} {r['precision']:>9.3f} {r['recall']:>7.3f} {r['f1']:>6.3f} "
              f"{r['f05']:>6.3f} {r['tp']:>4} {r['fp']:>4} {r['fn']:>4}")
    rec = res["recommended"]
    print(f"\n  recommended min_overlap = {rec['min_overlap']}  ({rec['reason']}; "
          f"P={rec['precision']:.3f} R={rec['recall']:.3f})")
    print("  read: precision is the crown-jewel metric (false credits reimport dilution); recall is "
          "recoverable\n        via exploration + repeat-exposure, so the gate is precision-first. "
          "Set declarative.attribution.min_overlap.")
    # surface the coincidental-echo cost at min_overlap=1 (the precision stressor)
    mo1 = next((r for r in res["sweep"] if r["min_overlap"] == 1), None)
    if mo1:
        offenders = [p["name"] for p in mo1["per_scenario"] if p["fp"]]
        if offenders:
            print(f"  coincidental false-credits at min_overlap=1: {offenders}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Attribution-precision gauge (declarative wiki, Ticket 1) — offline")
    ap.add_argument("--precision-target", type=float, default=0.9)
    ap.add_argument("--overlaps", default="1,2,3", help="comma-separated min_overlap values to sweep")
    ap.add_argument("--json", default=None, help="write the full result to this path (for the exporter/Grafana)")
    args = ap.parse_args()
    overlaps = tuple(int(x) for x in args.overlaps.split(",") if x.strip())
    res = run(args.precision_target, overlaps)
    _print(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
