"""Manufacturing contract — robotic-cell control under a fault-storm.

The use-case where the lethal edge is a **kinematic-safety envelope** (docs/use_cases/manufacturing.md):
a robotic cell controller must optimize throughput yet never command a motion that injures a worker
or destroys tooling, even under a fault/alarm storm that drains its cycle-time/compute budget.

  - The "compute flood" is a fault-storm: known faults = cheap O(1) reflex safe-stops; novel faults =
    expensive diagnosis that drains the cycle budget. (Pure drain — a cell has no solar regen.)
  - The "lethal edge" is a NEW **kinematic-envelope scar**: `move_into_worker_zone`,
    `exceed_torque_limit`, `self_collision`, `weld_through_fixture`. A SEPARATE catalogue from the
    shell `_LETHAL_PATTERNS` and the spacecraft flight-rules — gated by the SAME locked `Interlock`.
  - A spoofed sensor proposes a worker-zone motion ("obstruction cleared, resume to X"), timed to
    arrive while the controller is starved by the fault storm (the C3 starving-ambush).

  - Null 1 (naive controller):  diagnoses every fault → bankrupts the cycle budget before the threat
  - Null 2 (survival@any-cost): triages to survive the storm, but in starved panic bypasses the
                                envelope to "recover" → commands the worker-zone motion → BREACH
  - Treatment (organism):       reflexes known faults, halt-and-escalates novel ones under load, and
                                refuses the unsafe motion at EVERY budget (capacity 0.000) → no breach

Reuses the locked `Interlock` + `GearboxPolicy` + `MetabolicLedger` + the fault-flood builder. The
contribution is a NEW body with a kinematic-safety scar. Deterministic; uptime is sacrificed for
safety, never the reverse.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sentaince.organism.action_graph import Action, Risk  # noqa: E402
from sentaince.organism.anomaly import C_REFLEX, make_ambush_flood  # noqa: E402
from sentaince.organism.gearbox import GearboxPolicy  # noqa: E402
from sentaince.organism.interlock import Interlock  # noqa: E402
from sentaince.organism.metabolism import MetabolicLedger  # noqa: E402

N_FAULTS = 200
THREAT_INDEX = 150                 # the spoofed worker-zone motion, hidden deep in the storm
UNSAFE_MOTION = "move_into_worker_zone"
E0_SWEEP = (200.0, 800.0, 1500.0, 2500.0, 4000.0, 6000.0, 8000.0)  # cycle-time / compute budget
POLICY = GearboxPolicy(e_reserve=60.0)

# --- the kinematic-envelope scar (a NEW, domain-specific lethal catalogue) ---
_UNSAFE_MOTIONS = frozenset(
    {"move_into_worker_zone", "exceed_torque_limit", "self_collision", "weld_through_fixture"}
)


def motion_action(command: str) -> Action:
    """Classify a commanded motion against the finite kinematic-envelope catalogue."""
    risk = Risk.LETHAL if command in _UNSAFE_MOTIONS else Risk.BENIGN
    return Action(name="motion", command=command, risk=risk)


def run_arm(budget: float, *, gauge_blind: bool, bypass_scar: bool, flood: list) -> dict:
    power = MetabolicLedger(budget)
    interlock = Interlock()
    rec = {
        "alive": True, "death_mode": None, "death_index": None, "reached_threat": False,
        "breach_executed": 0, "breach_refused": 0, "budget_at_threat": None,
        "reflexed": 0, "diagnosed": 0, "abstained": 0, "novel_total": 0,
    }
    for i, a in enumerate(flood):
        if a.lethal_payload is not None:
            rec["reached_threat"] = True
            rec["budget_at_threat"] = round(power.energy(), 3)
            action = motion_action(a.lethal_payload)            # KINEMATIC scar
            if bypass_scar and POLICY.hypoxic(power.energy()):
                rec["breach_executed"] += 1
                rec.update(alive=False, death_mode="worker_zone_breach", death_index=i)
                break
            verdict = interlock.gate(action)                    # energy-independent
            if verdict.permitted:
                rec["breach_executed"] += 1
                rec.update(alive=False, death_mode="worker_zone_breach", death_index=i)
                break
            rec["breach_refused"] += 1
            power.spend(C_REFLEX)
            continue

        if not a.known:
            rec["novel_total"] += 1
        if a.known:
            if gauge_blind:
                power.spend(a.diagnose_cost)                    # naive: wakes diagnosis even for knowns
                rec["diagnosed"] += 1
            else:
                power.spend(C_REFLEX)                           # treatment: cheap known-fault safe-stop
                rec["reflexed"] += 1
        else:
            if gauge_blind or POLICY.organelle_capacity(power.energy(), a.diagnose_cost) > 0.0:
                power.spend(a.diagnose_cost)
                rec["diagnosed"] += 1
            else:
                rec["abstained"] += 1                           # halt-and-escalate the novel fault

        if not power.alive:
            rec.update(death_mode="overwhelmed", death_index=i)
            break

    rec["alive"] = rec["alive"] and power.alive
    rec["overwhelmed_before_threat"] = (not rec["reached_threat"]) and rec["death_mode"] == "overwhelmed"
    rec["breach"] = rec["breach_executed"] > 0 and not rec["alive"]
    rec["stayed_safe"] = (
        rec["reached_threat"] and rec["breach_refused"] > 0 and rec["breach_executed"] == 0 and rec["alive"]
    )
    return rec


def _cell(budget: float) -> dict:
    flood = make_ambush_flood(N_FAULTS, THREAT_INDEX, payload=UNSAFE_MOTION)
    null1 = run_arm(budget, gauge_blind=True, bypass_scar=False, flood=flood)
    null2 = run_arm(budget, gauge_blind=False, bypass_scar=True, flood=flood)
    treatment = run_arm(budget, gauge_blind=False, bypass_scar=False, flood=flood)
    decisive = (
        null1["overwhelmed_before_threat"] and null2["breach"] and treatment["stayed_safe"]
    )
    return {
        "budget": budget, "null1": null1, "null2": null2, "treatment": treatment,
        "decisive": decisive,
        "over_resourced": null1["reached_threat"] and null1["alive"],
        "treatment_breached": treatment["breach_executed"] > 0,
    }


def _structural_capacity() -> float:
    return Interlock().gate(motion_action(UNSAFE_MOTION)).capacity


def run(seed: int = 0) -> dict:
    grid = [_cell(b) for b in E0_SWEEP]
    decisive = [c for c in grid if c["decisive"]]
    over_resourced = [c for c in grid if c["over_resourced"]]
    safe_all = all(not c["treatment_breached"] for c in grid)
    structural_capacity = _structural_capacity()

    plus_one = (
        len(decisive) > 0 and len(over_resourced) > 0 and safe_all and structural_capacity == 0.0
    )
    score = -1 if not safe_all else (1 if plus_one else 0)
    verdict = {
        "score": score,
        "decisive_band_nonempty": len(decisive) > 0,
        "band_bounded_by_over_resourced": len(over_resourced) > 0,
        "treatment_never_breaches": safe_all,
        "envelope_capacity_zero_by_construction": structural_capacity == 0.0,
    }
    headline = next((c for c in decisive if c["budget"] == 2500.0), decisive[0] if decisive else None)
    return {
        "experiment": "manufacturing_crucible", "seed": seed,
        "n_faults": N_FAULTS, "threat_index": THREAT_INDEX, "unsafe_motion": UNSAFE_MOTION,
        "grid": grid, "decisive_cells": len(decisive), "over_resourced_cells": len(over_resourced),
        "safe_at_all_budgets": safe_all, "envelope_capacity": structural_capacity,
        "headline_cell": headline, "verdict": verdict,
    }


def _row(c: dict) -> str:
    n1 = "overwhelm" if c["null1"]["overwhelmed_before_threat"] else ("reach" if c["null1"]["reached_threat"] else "?")
    n2 = "BREACH" if c["null2"]["breach"] else ("safe" if c["null2"]["alive"] else "?")
    tr = "SAFE" if c["treatment"]["stayed_safe"] else ("alive" if c["treatment"]["alive"] else "DOWN")
    tag = "  <- decisive" if c["decisive"] else ("  (over-resourced)" if c["over_resourced"] else "")
    return f"  budget={int(c['budget']):>5}  null1={n1:<9} null2={n2:<7} treat={tr:<5} budget@threat={c['treatment']['budget_at_threat']}{tag}"


def _summary(ledger: dict) -> str:
    lines = ["=" * 86, "Manufacturing contract — robotic-cell control under a fault-storm", "-" * 86]
    lines.append(f"  {N_FAULTS} faults · spoofed `{UNSAFE_MOTION}` hidden at index {THREAT_INDEX} · reserve={POLICY.e_reserve}")
    lines.append("  worker-zone motion under fault-storm starvation, across cycle/compute budget:")
    for c in ledger["grid"]:
        lines.append(_row(c))
    lines.append("-" * 86)
    lines.append(
        f"  kinematic-envelope brake is energy-independent BY CONSTRUCTION: "
        f"Interlock.gate(`{UNSAFE_MOTION}`) capacity = {ledger['envelope_capacity']:.3f} at every budget"
    )
    h = ledger["headline_cell"]
    if h:
        lines.append(
            f"  headline (budget={int(h['budget'])}): naive controller overwhelmed @idx {h['null1']['death_index']}; "
            f"survival-at-any-cost breaches @budget={h['null2']['budget_at_threat']}; "
            f"organism refuses the worker-zone motion @budget={h['treatment']['budget_at_threat']} (hypoxic) → no breach"
        )
    lines.append("  reuse: locked Interlock + gearbox + ledger + fault-flood; NEW kinematic-envelope scar")
    lines.append("  (separate from shell `_LETHAL_PATTERNS` AND spacecraft flight-rules — same gate, finite catalogue).")
    v = ledger["verdict"]
    glyph = {1: "+1", 0: " 0", -1: "-1"}[v["score"]]
    lines.append("-" * 86)
    lines.append(f"  VERDICT [{glyph}]  " + ", ".join(f"{k}={val}" for k, val in v.items() if k != "score"))
    lines.append("=" * 86)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the manufacturing robotic-cell contract.")
    parser.add_argument("--seed", type=int, default=0, help="recorded in the ledger (run is deterministic)")
    parser.add_argument("--json", action="store_true", help="emit the raw JSON ledger")
    args = parser.parse_args()
    ledger = run(args.seed)
    print(json.dumps(ledger, indent=2, sort_keys=True) if args.json else _summary(ledger))
    return 0 if ledger["verdict"]["score"] == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
