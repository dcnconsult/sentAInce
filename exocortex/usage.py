"""``sentaince status --full`` — the self-evidencing usage report.

The organism's one visible event is a refusal, which fires roughly once per thousand tool
calls; a working install and a broken install otherwise look identical from the outside
(the v0.1.5 DOA arc is the scar). The vitals line answers *am I alive*. This answers the
next question a user actually has: **is it doing anything for me, and how much?**

Two numbers carry it:

- **memory contribution** — the share of prompts where the colony had an earned route to
  splice. Low is not a fault: a class must be revisited before it can converge, so a fresh
  repo reads near 0% and climbs. It is the honest dose reading for *this* install.
- **somatic coverage** — the share of *mutating* tool calls the safety floor actually
  evaluated. Read/Grep/Glob are excluded by design (they cannot mutate), so the denominator
  is the set of calls where a veto could ever matter.

Deliberately NOT an outcome claim. Coverage says a channel is not dark; it never says harm
was prevented. Contribution says a route existed; it never says the route helped — that is
the outcome question the A/B parked at 0 (`results/guide_accrue_ab_v1/`). This module
reports dose, never effect, and the rendered footer says so to the user.

Read-only and stdlib-pure: it opens the repo's own ``audit.jsonl`` and ``colony_*.json``,
computes, and prints. Nothing is written, nothing is sent anywhere, no telemetry exists.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# The veto's actual domain: tools that execute a COMMAND, where destructiveness lives in the
# command's shape and a closed structural vocabulary can recognize it (`rm -rf /`, kill PID 1).
COMMAND_TOOLS = ("Bash", "PowerShell")

# File writes. Deliberately NOT in the coverage denominator, and not a gap: a write has no
# recognizable shape — `Write foo.py` is byte-identical whether it fixes a bug or destroys the
# file — so the somatic vocabulary has no referent here. Measured, not assumed: across 3,110
# real Write/Edit calls in 10 repos the dangerous-target population was EMPTY (0 system paths,
# 0 .git/, 0 audit.jsonl, 0 colony_*.json, 0 kernel-lock), while the most plausible broad rule
# (gate `.claude/` paths) would have fired on 687 legitimate calls — 22%. Any path-risk organ
# here produces only false positives on the evidence available. Reported separately so the
# volume stays visible without being miscounted as an uncovered hole.
FILE_WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

MUTATING = COMMAND_TOOLS + FILE_WRITE_TOOLS

_CLASS = re.compile(r"class=([^\s,]+)")


def _records(audit: Path):
    """Yield audit records, skipping anything unparseable. utf-8-sig because a BOM-written
    log must not take the report down (and the platform default is not UTF-8 on Windows)."""
    try:
        with audit.open(encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except OSError:
        return


def summarize(state_dir: Path) -> dict:
    """Compute the usage picture for one deployed repo. Never raises — a partial or absent
    audit yields zeros, because a status command that crashes is worse than one that shrugs."""
    audit = Path(state_dir) / "audit.jsonl"
    prompts = injected = 0
    commands = evaluated = refused = file_writes = 0
    classes: dict[str, int] = {}
    ungated: dict[str, int] = {}
    for r in _records(audit):
        ev = r.get("event")
        if ev == "UserPromptSubmit":
            prompts += 1
            if r.get("injected"):
                injected += 1
            m = _CLASS.search(str(r.get("reason") or ""))
            if m:
                classes[m.group(1)] = classes.get(m.group(1), 0) + 1
        elif ev == "PreToolUse":
            tool = str(r.get("tool") or "")
            if tool in COMMAND_TOOLS:
                commands += 1
                if r.get("somatic_permitted") is None:
                    ungated[tool] = ungated.get(tool, 0) + 1
                else:
                    evaluated += 1
                    if r.get("somatic_permitted") is False:
                        refused += 1
            elif tool in FILE_WRITE_TOOLS:
                file_writes += 1
    routes = 0
    earning = 0
    try:
        for p in sorted(Path(state_dir).glob("colony_*.json")):
            try:
                tau = json.loads(p.read_text(encoding="utf-8")).get("tau")
            except Exception:
                continue
            if isinstance(tau, dict) and tau:
                routes += len(tau)
                earning += 1
    except OSError:
        pass
    return {
        "prompts": prompts, "injected": injected,
        "commands": commands, "evaluated": evaluated, "refused": refused,
        "file_writes": file_writes, "ungated": ungated,
        "classes": len(classes),
        "singletons": sum(1 for v in classes.values() if v == 1),
        "routes": routes, "earning_classes": earning,
    }


def _pct(num: int, den: int) -> str:
    return f"{num / den * 100:.1f}%" if den else "n/a"


def render(state_dir: Path) -> str:
    """Human-readable report. Plain ASCII labels — this is read on Windows consoles that
    cannot encode the vitals emoji (see cli._say)."""
    s = summarize(state_dir)
    L: list[str] = []
    L.append("   memory")
    L.append(f"     prompts seen            {s['prompts']:>6}")
    L.append(f"     memory contributed on   {s['injected']:>6}  ({_pct(s['injected'], s['prompts'])})")
    if not s["prompts"]:
        L.append("       (no prompts recorded yet — the organism has not seen a session here)")
    L.append(f"     goal classes            {s['classes']:>6}")
    if s["classes"]:
        L.append(f"       seen only once        {s['singletons']:>6}  "
                 f"({_pct(s['singletons'], s['classes'])} — cannot converge until revisited)")
    L.append(f"     classes with routes     {s['earning_classes']:>6}  ({s['routes']} edges earned)")
    L.append("")
    L.append("   safety floor")
    L.append(f"     command calls           {s['commands']:>6}   (Bash, PowerShell)")
    L.append(f"     somatically evaluated   {s['evaluated']:>6}  ({_pct(s['evaluated'], s['commands'])})")
    # The "1 per N" gloss only informs when refusals are rare (the normal case, ~1/1000). At a high
    # refusal fraction it degenerates to "1 per 1", so state the share instead of a silly ratio.
    _rate = (s["commands"] // s["refused"]) if s["refused"] else 0
    L.append(f"     refusals                {s['refused']:>6}" + (
        f"  (1 per {_rate} command calls)" if _rate >= 2
        else f"  ({_pct(s['refused'], s['commands'])} of command calls)" if s["refused"] else ""))
    if s["ungated"]:
        worst = sorted(s["ungated"].items(), key=lambda kv: -kv[1])
        L.append("     NOT evaluated           " +
                 ", ".join(f"{t} {n}" for t, n in worst[:4]) + "   <- a real gap")
    L.append(f"     file writes             {s['file_writes']:>6}   not gated by design — a write has no")
    L.append("                                     recognizable shape; see exocortex/usage.py")
    L.append("")
    L.append("   Dose, not effect: these say the organism was present and what it covered —")
    L.append("   never that an outcome improved. Read from your own logs; nothing is sent anywhere.")
    return "\n".join(L)
