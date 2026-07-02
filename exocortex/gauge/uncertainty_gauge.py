"""Offline UNCERTAINTY / VETO-SIGNAL gauge (candidates G1, F2; F1 latent) — do the events these organs
consume actually occur? (STATS)

Three proposed organs feed on *rare-event signals* the live audit can measure directly, before any of them
is built (gauge-first, ADR-002):

  - **G1 — sovereign-uncertainty hand-off** consumes the epistemic 0-well *abstain* (an OOD signal). If the
    gate never abstains on real traffic, the ESCALATE hand-off has nothing to fire on.
  - **F2 — veto-sourced demotion** consumes the *somatic veto* (a gate-DENY). If vetoes are vanishingly rare,
    demotion has no signal to learn from.
  - **F1 — safety-pin eviction floor** protects a memory item *referenced by a safety invariant*. No such
    linkage exists in the audit (the gap F1 names), and safety lives in the frozen DNA, not the vault — so
    F1's prune-exposure is **latent** (0 safety-referenced items) until a vault carries safety notes.

This gauge reads one or more live ``audit.jsonl`` files and reports the abstain rate (G1), the veto rate +
veto-near-memory co-occurrence (F2), and the F1 latency note. Self-contained, numpy-free, read-only — the
same fail-open discipline as the hook. STATS-first; the verdict is a thin threshold the numbers drive.

  python -m exocortex.gauge.uncertainty_gauge                 # auto-scan sibling repos' live audits
  python -m exocortex.gauge.uncertainty_gauge --audit P [...]  # explicit audit file(s)
  python -m exocortex.gauge.uncertainty_gauge --json          # machine-readable (for a results file / CI)

Verdict on flagship data (results/uncertainty_gauge_v1): abstain 0/293, vetoes 1/1036 -> G1 & F2 are NULL on
real flagship coding; their signal lives in adversarial / untrusted-model (BYO) traffic. Park, data-gated.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# A non-trivial signal must clear this to justify building the organ (1% of assessed/Pre events).
SIGNAL_THRESHOLD = 0.01
CONSEQUENCE_EVENTS = ("PostToolUse", "PostToolUseFailure")
_REPO_ROOT = Path(__file__).resolve().parents[2]   # gauge -> exocortex -> repo root


def load(path) -> list:
    """Read one audit.jsonl (fail-open: missing file -> [], malformed line -> skipped)."""
    out: list = []
    p = Path(path)
    if not p.is_file():
        return out
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def analyze(records: list) -> dict:
    """The three candidate signals over one record set."""
    pre = [r for r in records if r.get("event") == "PreToolUse"]
    assessed = [r for r in pre if r.get("epistemic_decision")]   # the gate actually ran & recorded a verdict
    abstain = sum(1 for r in assessed if r.get("epistemic_decision") == "abstain")
    verify = sum(1 for r in assessed if r.get("epistemic_decision") == "verify")
    vetoes = [r for r in pre if r.get("somatic_permitted") is False]
    cons = [r for r in records if r.get("event") in CONSEQUENCE_EVENTS]
    inj_cons = [r for r in cons if int(r.get("wiki_injected", 0) or 0) > 0]
    inj_sessions = {r.get("session") for r in inj_cons}
    veto_near_memory = sum(1 for v in vetoes if v.get("session") in inj_sessions)
    return {
        "records": len(records),
        "pre_total": len(pre),
        "assessed": len(assessed),
        "abstain": abstain,
        "verify": verify,
        "abstain_rate": round(abstain / len(assessed), 4) if assessed else None,
        "verify_rate": round(verify / len(assessed), 4) if assessed else None,
        "vetoes": len(vetoes),
        "veto_rate": round(len(vetoes) / len(pre), 4) if pre else None,
        "veto_organs": sorted({r.get("somatic_organ") for r in vetoes if r.get("somatic_organ")}),
        "consequences": len(cons),
        "injected_consequences": len(inj_cons),
        "wiki_used_total": sum(int(r.get("wiki_used", 0) or 0) for r in cons),
        "veto_near_memory": veto_near_memory,
        # F1: no audit field links a memory item to a safety invariant (the gap F1 names) and safety lives in
        # the frozen DNA, not the vault -> structurally 0 safety-referenced items here.
        "safety_referenced_items": 0,
    }


def verdict(m: dict) -> dict:
    """Thin, numbers-driven classification: does each candidate have a signal worth building?"""
    g1 = (m["abstain_rate"] or 0.0) >= SIGNAL_THRESHOLD
    f2 = (m["veto_rate"] or 0.0) >= SIGNAL_THRESHOLD and m["veto_near_memory"] >= 3
    return {
        "G1_handoff": {
            "signal": g1, "metric": "abstain_rate", "value": m["abstain_rate"],
            "note": "epistemic 0-well abstain — the OOD hand-off trigger; null on flagship coding "
                    "(stays grounded), signal lives in adversarial / untrusted-model (BYO) traffic.",
        },
        "F2_veto_demotion": {
            "signal": f2, "metric": "veto_rate", "value": m["veto_rate"],
            "veto_near_memory": m["veto_near_memory"],
            "note": "somatic veto as a negative signal; flagship rarely proposes a lethal, so near-null.",
        },
        "F1_safety_pin": {
            "signal": False, "metric": "safety_referenced_items", "value": m["safety_referenced_items"],
            "note": "LATENT — no audit linkage from a memory item to a safety invariant, and safety lives "
                    "in frozen DNA not the vault; re-evaluate when a vault carries safety-relevant notes.",
        },
    }


def discover(scan_root: Path) -> list:
    """Sibling-repo live audits: ``<scan_root>/*/.claude/exocortex/audit.jsonl`` (mirrors the exporter)."""
    found = []
    if scan_root.is_dir():
        for child in sorted(scan_root.iterdir()):
            a = child / ".claude" / "exocortex" / "audit.jsonl"
            if a.is_file():
                found.append(a)
    return found


def run(audit_paths: list | None = None, scan_root: Path | None = None) -> dict:
    """Per-repo analysis + a pooled aggregate + the verdict over the pool."""
    paths = [Path(p) for p in (audit_paths or [])]
    if not paths:
        paths = discover(scan_root or _REPO_ROOT.parent)
    per_repo = []
    pooled: list = []
    for p in paths:
        recs = load(p)
        if not recs:
            continue
        per_repo.append({"audit": str(p), "repo": p.parents[2].name, **analyze(recs)})
        pooled.extend(recs)
    agg = analyze(pooled)
    return {"per_repo": per_repo, "aggregate": agg, "verdict": verdict(agg),
            "signal_threshold": SIGNAL_THRESHOLD}


def _fmt(res: dict) -> str:
    lines = ["UNCERTAINTY / VETO-SIGNAL GAUGE  (G1 abstain · F2 veto · F1 latent)", ""]
    for r in res["per_repo"]:
        lines.append(f"  [{r['repo']}] records={r['records']} pre={r['pre_total']} assessed={r['assessed']} "
                     f"abstain={r['abstain']} verify={r['verify']} vetoes={r['vetoes']} "
                     f"inj_cons={r['injected_consequences']} veto_near_mem={r['veto_near_memory']}")
    a = res["aggregate"]
    lines += ["", f"AGGREGATE: records={a['records']} pre={a['pre_total']} assessed={a['assessed']}",
              f"  G1 abstain_rate = {a['abstain_rate']} (abstain {a['abstain']}/{a['assessed']}, verify {a['verify']})",
              f"  F2 veto_rate    = {a['veto_rate']} (vetoes {a['vetoes']}/{a['pre_total']}, "
              f"organs {a['veto_organs']}, near_memory {a['veto_near_memory']})",
              f"  F1 safety_referenced_items = {a['safety_referenced_items']} (latent)", "", "VERDICT:"]
    for k, v in res["verdict"].items():
        lines.append(f"  {k}: signal={v['signal']}  {v['metric']}={v['value']}")
        lines.append(f"       {v['note']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Uncertainty/veto-signal gauge (G1/F2 candidates; F1 latent)")
    ap.add_argument("--audit", action="append", default=[], help="explicit audit.jsonl path (repeatable)")
    ap.add_argument("--scan-root", default=None, help="dir to scan for */.claude/exocortex/audit.jsonl")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    res = run(args.audit or None, Path(args.scan_root) if args.scan_root else None)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
