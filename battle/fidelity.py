"""Sandbox-fidelity check (M3) — does the symbolic oracle faithfully model the real body?

For each permitted command we: read the body's real state, ask the locked symbolic oracle
(``outcome_oracle.apply``) what it PREDICTS the state will become, actually run the command on the
body, then compare the MEASURED state to the prediction. A match means C6's effect-model is faithful;
a mismatch is an honest finding — the sandbox's fidelity is the claim's fidelity.

Also asserts the protected invariants are untouched after the permitted commands (defense-in-depth:
nothing that reaches the body should ever move a declared invariant).
"""
from __future__ import annotations

from sentaince.organism.outcome_oracle import PROTECTED, apply

from .body_client import BodyAgentClient


def check_fidelity(client: BodyAgentClient, commands: list[str]) -> dict:
    """Run each command on the real body and compare measured vs modelled state."""
    per_command = []
    for command in commands:
        before = client.snapshot()
        predicted = apply(command, before)          # the locked symbolic oracle's prediction
        result = client.run(command)
        measured = result["after"]                  # the real, observed state
        mismatch = {
            r: {"predicted": predicted.get(r), "measured": measured.get(r)}
            for r in set(predicted) | set(measured)
            if predicted.get(r) != measured.get(r)
        }
        per_command.append({
            "command": command,
            "match": not mismatch,
            "delta": result["delta"],
            "mismatch": mismatch,
        })

    final = client.snapshot()
    protected_intact = all(final.get(r) == "present" for r in PROTECTED)
    all_match = all(c["match"] for c in per_command)
    return {
        "per_command": per_command,
        "all_match": all_match,
        "protected_intact": protected_intact,
        "verdict": int(all_match and protected_intact),
    }


def format_fidelity(report: dict, energy_block: list[str] | None = None) -> str:
    lines = [
        "=" * 88,
        "M3 Sandbox-Fidelity Check — measured real-body delta vs the symbolic oracle's prediction",
        "-" * 88,
    ]
    for c in report["per_command"]:
        tag = "MATCH" if c["match"] else "MISMATCH"
        lines.append(f"  [{tag}] {c['command']!r}  delta={c['delta']}")
        if c["mismatch"]:
            lines.append(f"          mismatch: {c['mismatch']}")
    lines.append("-" * 88)
    lines.append(f"  protected invariants intact after permitted commands: {report['protected_intact']}")
    for line in energy_block or []:
        lines.append(line)
    lines.append("-" * 88)
    glyph = "+1" if report["verdict"] == 1 else "-1"
    head = ("the symbolic oracle faithfully models the real body; protected invariants untouched"
            if report["verdict"] == 1 else "fidelity gap — measured and modelled diverge (see mismatch)")
    lines.append(f"  VERDICT: [{glyph}] {head}")
    lines.append("=" * 88)
    return "\n".join(lines)
