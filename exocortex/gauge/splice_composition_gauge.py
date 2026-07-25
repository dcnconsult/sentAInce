"""Splice-Composition Gauge — do the memory organs ever speak in the SAME turn? (STATS)

An external analysis (AttnRes: learned attention over prior layers instead of uniform residual
accumulation) proposed that the organism lacks a **retrieval controller over memory depths** — a
context-sensitive quorum across colony / wiki / bridge / interocept before reasoning. The *observation*
is right: ``hook.handle_userpromptsubmit`` assembles the turn's context as a ``blocks[]`` list, each
organ deciding independently whether to speak, concatenated in fixed source order — no arbitration, no
shared budget, no cross-organ comparison.

But the premise was never measured. A quorum is only meaningful if ≥2 organs actually contend for the
same turn. This gauge measures the CONTENTION CEILING, read-only, from what the organism already
records:

  LIVENESS   — which organs are switched on in this repo (its own ``exocortex_config.json``, never THIS
               repo's genome). Ships-dormant organs (wiki, bridge) are off unless deliberately enabled.
  READINESS  — of the live ones, which can actually emit today: the colony needs a class over
               ``min_deposits_to_splice``; the wiki needs a warmed cache; the bridge needs offers.
  CEILING    — organs that are live AND ready = the most that can ever co-fire in one turn. A ceiling
               of ≤1 makes "attention over memory depth" a solution to a non-problem *in this repo*.
  PAYLOAD    — the colony's real per-class splice cost, rendered through ``Colony.splice()`` VERBATIM
               (one implementation, no drift — the credit_funnel_gauge precedent).

**Deliberate measurement gap, and it is the point.** The per-turn TRUTH (which organs actually spoke
together, and how many chars each contributed) cannot be recovered read-only: ``audit.record`` stamps
only ``injected: bool``. Stamping it requires editing ``exocortex/hook.py``, which is inside the ADR-016
P1 pin (``test_reflect_preamble.py::test_the_p1_pin_holds`` asserts a byte-clean diff from ``6bb3465``)
— a PI-approved, on-the-record re-baseline. This gauge exists to decide whether that cost is worth
paying BEFORE paying it. It reads a ``splice`` field if one is ever present, so it needs no change if
the re-baseline happens.

Read-only, pure-stdlib (+ ``Colony`` for the renderer), deterministic, fail-open. A run over a live repo
is a labeled demonstration.

  python -m exocortex.gauge.splice_composition_gauge --state-dir .claude/exocortex
  python -m exocortex.gauge.splice_composition_gauge --estate <projects-root>
  python -m exocortex.gauge.splice_composition_gauge --estate <projects-root> --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_SPLICE_BAR = 3          # colony min_deposits_to_splice genome default; overridden by repo config
INTEROCEPT_MODES = ("epistemic", "full")   # hook.py:473 — the only modes that append an interoceptive block

# The organs that can contribute an additionalContext block on a UserPromptSubmit turn. The first four
# are blocks[] inside the PINNED hook; `preamble` is the R3 SIBLING hook (its own process, its own
# payload) — it contends for the same turn's context window, so it counts toward the ceiling.
ORGANS = ("interocept", "colony", "wiki", "bridge", "preamble")


# ------------------------------------------------------------------ loading (fail-open)
def _jsonl(path: Path) -> list:
    out: list = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _json_file(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def repo_config(state_dir: Path) -> dict:
    """The TARGET repo's own activation file (root = state_dir/../..) — never this repo's genome."""
    return _json_file(Path(state_dir).parent.parent / "exocortex_config.json")


# ------------------------------------------------------------------ liveness + readiness
def organ_liveness(cfg: dict, state_dir: Path, splice_bar: int) -> dict:
    """Per-organ {live, ready, why}. `live` = switched on by config; `ready` = has the state it needs to
    actually emit today. Mirrors the gates in hook.handle_userpromptsubmit (473/481/493/508) and the
    genome defaults in config.py — ships-dormant means absent-key → off."""
    sd = Path(state_dir)
    decl = dict(cfg.get("declarative", {}) or {})
    mode = str((cfg.get("somatic_gate", {}) or {}).get("mode", "observe")).lower()
    decl_live = str(decl.get("mode", "off")).lower() == "live" and bool(decl.get("vault_path"))
    bridge_live = str((decl.get("bridge", {}) or {}).get("mode", "off")).lower() == "suggest"
    preamble_live = str((cfg.get("reflection", {}) or {}).get("preamble", "off")).lower() == "live"

    classes = colony_classes(sd)
    servable = [c for c in classes if c["deposits"] >= splice_bar]
    wiki_nodes = len(_json_file(sd / "wiki_cache.json").get("nodes", []) or [])
    bridges = _json_file(sd / "wiki_bridges.json")
    n_bridges = len(bridges.get("bridges", bridges.get("edges", [])) or []) if bridges else 0

    return {
        "interocept": {
            "live": mode in INTEROCEPT_MODES, "ready": mode in INTEROCEPT_MODES,
            "why": f"somatic_gate.mode={mode} (block appended only in {'/'.join(INTEROCEPT_MODES)})"},
        "colony": {
            "live": True, "ready": bool(servable),
            "why": f"{len(servable)}/{len(classes)} classes at/over min_deposits_to_splice={splice_bar}"},
        "wiki": {
            "live": decl_live, "ready": decl_live and wiki_nodes > 0,
            "why": (f"declarative.mode={decl.get('mode', 'off')} vault={'set' if decl.get('vault_path') else 'unset'}"
                    f"; warmed cache={wiki_nodes} nodes")},
        "bridge": {
            "live": bridge_live, "ready": bridge_live and n_bridges > 0,
            "why": f"declarative.bridge.mode={(decl.get('bridge', {}) or {}).get('mode', 'off')}; {n_bridges} bridges"},
        "preamble": {
            "live": preamble_live, "ready": preamble_live,
            "why": f"reflection.preamble={(cfg.get('reflection', {}) or {}).get('preamble', 'off')} (SIBLING hook)"},
    }


# ------------------------------------------------------------------ colony payload (the one measurable cost)
def colony_classes(state_dir: Path) -> list:
    out = []
    for f in sorted(Path(state_dir).glob("colony_*.json")):
        d = _json_file(f)
        if d:
            out.append({"label": str(d.get("label", f.stem[len("colony_"):])),
                        "deposits": int(d.get("deposits", 0) or 0),
                        "tau": dict(d.get("tau", {}) or {}),
                        "meta": dict(d.get("meta", {}) or {})})
    return out


def colony_payload(state_dir: Path, splice_bar: int) -> dict:
    """Render each servable class through the REAL ``Colony.splice()`` and measure the chars it would
    inject. Not a simulation of the renderer — the renderer itself, on the live store."""
    try:
        from exocortex.colony import Colony, MIN_DEPOSITS_TO_SPLICE
    except Exception:
        return {"classes": 0, "note": "colony module unavailable"}
    sizes, abstained = [], 0
    for c in colony_classes(state_dir):
        if c["deposits"] < splice_bar:
            continue
        try:
            col = Colony(label=c["label"], tau=c["tau"], deposits=c["deposits"], meta=c["meta"])
            block = col.splice()
        except Exception:
            continue
        if block:
            sizes.append({"label": c["label"], "deposits": c["deposits"], "chars": len(block)})
        else:
            abstained += 1                      # servable by repo bar, refused by this build's constant
    sizes.sort(key=lambda s: -s["chars"])
    vals = [s["chars"] for s in sizes]
    return {"classes": len(sizes), "abstained_module_bar": abstained,
            "module_bar": MIN_DEPOSITS_TO_SPLICE, "repo_bar": splice_bar,
            "chars_p50": _pct(vals, 0.50), "chars_p90": _pct(vals, 0.90),
            "chars_max": max(vals) if vals else 0, "chars_total_if_all": sum(vals),
            "largest": sizes[:5]}


def _pct(vals: list, q: float) -> int:
    if not vals:
        return 0
    s = sorted(vals)
    return int(s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))])


# ------------------------------------------------------------------ audit (what IS recorded today)
def audit_composition(records: list) -> dict:
    """Turn-level injection from the audit. ``injected`` is a BOOL — it cannot tell us WHICH organ spoke.
    ``splice`` is read if a future (post-re-baseline) hook ever stamps per-organ chars; absent today, and
    its absence is reported, never silently treated as zero co-fire."""
    prompts = injected = 0
    per_organ: dict = {k: 0 for k in ORGANS}
    per_organ_chars: dict = {k: 0 for k in ORGANS}
    stamped = cofire = 0
    totals: list = []
    for r in records:
        if r.get("event") != "UserPromptSubmit":
            continue
        prompts += 1
        if r.get("injected"):
            injected += 1
        sp = r.get("splice")
        if isinstance(sp, dict) and sp:
            stamped += 1
            spoke = [k for k, v in sp.items() if int(v or 0) > 0]
            if len(spoke) >= 2:
                cofire += 1
            for k in spoke:
                per_organ[k] = per_organ.get(k, 0) + 1
                per_organ_chars[k] = per_organ_chars.get(k, 0) + int(sp[k] or 0)
            totals.append(sum(int(v or 0) for v in sp.values()))
    return {"prompts": prompts, "prompts_injected": injected,
            "splice_stamped": stamped, "cofire_turns": cofire,
            "cofire_rate": (round(cofire / stamped, 4) if stamped else None),
            "per_organ_turns": per_organ if stamped else {},
            "per_organ_chars": per_organ_chars if stamped else {},
            "payload_p50": _pct(totals, 0.50), "payload_p90": _pct(totals, 0.90),
            "payload_max": max(totals) if totals else 0,
            "measurable": bool(stamped)}


# ------------------------------------------------------------------ the verdict (pre-registered)
def verdict(ceiling: int, ready: list, audit: dict, payload: dict) -> dict:
    """The rule was written BEFORE the data was read:
      −1  ceiling ≤ 1  → nothing can ever contend; a quorum controller solves a non-problem here.
       0  ceiling ≥ 2  → contention is structurally possible; a BUDGET question exists. Note that a
                         controller still needs a cross-organ currency, and colony edge-τ and wiki
                         node-τ share no scale — so +1 is NOT reachable from this gauge.
    """
    if ceiling <= 1:
        return {"disposition": -1, "label": "NO CONTENTION POSSIBLE",
                "note": f"only {ceiling} organ can emit ({', '.join(ready) or 'none'}) — every injecting turn "
                        "is a monologue. 'Attention over memory depth' has nothing to arbitrate here; the "
                        "honest lack stays semantic retention (the dormant wiki), not selection."}
    measured = ("observed co-fire rate " + f"{audit['cofire_rate']:.0%} over {audit['splice_stamped']} stamped turns"
                if audit.get("measurable") else
                "the per-turn rate is UNMEASURED — audit stamps only injected:bool; measuring it means "
                "editing the P1-pinned hook.py (ADR-016 re-baseline)")
    return {"disposition": 0, "label": "CONTENTION POSSIBLE — BUDGET QUESTION OPEN",
            "note": f"{ceiling} organs can emit in one turn ({', '.join(ready)}); {measured}. Colony alone "
                    f"costs up to {payload.get('chars_max', 0)} chars/turn. A shared char budget with a "
                    "fixed priority order would need no common currency and no learning; a LEARNED "
                    "controller would — and colony edge-τ vs wiki node-τ have no shared scale, so +1 is "
                    "not reachable from this gauge."}


# ------------------------------------------------------------------ per-repo + estate
def run(state_dir, splice_bar: "int | None" = None) -> dict:
    sd = Path(state_dir).resolve()      # resolve so `.claude/exocortex` still yields the repo name
    cfg = repo_config(sd)
    bar = splice_bar if splice_bar is not None else int(
        (cfg.get("colony", {}) or {}).get("min_deposits_to_splice", DEFAULT_SPLICE_BAR))
    organs = organ_liveness(cfg, sd, bar)
    ready = [k for k in ORGANS if organs[k]["live"] and organs[k]["ready"]]
    live = [k for k in ORGANS if organs[k]["live"]]
    records = _jsonl(sd / "audit.jsonl")
    audit = audit_composition(records)
    payload = colony_payload(sd, bar)
    return {"state_dir": str(sd), "repo": sd.parent.parent.name, "splice_bar": bar,
            "audit_records": len(records), "organs": organs,
            "live": live, "ready": ready, "ceiling": len(ready),
            "audit": audit, "colony_payload": payload,
            "verdict": verdict(len(ready), ready, audit, payload)}


def estate(root, extra_repos=None) -> dict:
    """Sweep every repo under ``root`` that carries a ``.claude/exocortex`` state dir, plus any
    explicitly-named repo roots. ``extra_repos`` exists because the estate is NOT one directory:
    the estate's largest vault lives outside the projects root and a root-glob silently omits it — which is how a
    live declarative repo went unmeasured in the first census."""
    roots = [root] if isinstance(root, (str, Path)) else list(root or [])
    seen: set = set()
    state_dirs = []
    for r in roots:
        for sd in sorted(Path(r).glob("*/.claude/exocortex")):
            if str(sd.resolve()) not in seen:
                seen.add(str(sd.resolve()))
                state_dirs.append(sd)
    for rp in (extra_repos or []):
        sd = Path(rp) / ".claude" / "exocortex"
        if sd.is_dir() and str(sd.resolve()) not in seen:
            seen.add(str(sd.resolve()))
            state_dirs.append(sd)
    rows = []
    for sd in state_dirs:
        try:
            rows.append(run(sd))
        except Exception:
            continue
    ceilings = [r["ceiling"] for r in rows]
    contended = [r["repo"] for r in rows if r["ceiling"] >= 2]
    measurable = [r["repo"] for r in rows if r["audit"]["measurable"]]
    return {"root": str(root), "repos": len(rows),
            "ceiling_max": max(ceilings) if ceilings else 0,
            "ceiling_ge2": len(contended), "contended_repos": contended,
            "per_turn_measurable_repos": measurable,
            "rows": rows,
            "verdict": (
                {"disposition": -1, "label": "ESTATE: NO CONTENTION ANYWHERE",
                 "note": "no repo has ≥2 organs able to emit — the quorum premise is unfounded estate-wide"}
                if not contended else
                {"disposition": 0, "label": "ESTATE: CONTENTION IN A MINORITY",
                 "note": f"{len(contended)}/{len(rows)} repos can co-fire ({', '.join(contended)}); the rest "
                         "are colony monologues. Any arbitration layer would be dev-repo-only tissue "
                         "until the dormant organs are switched on elsewhere."})}


# ------------------------------------------------------------------ text output
def _fmt_repo(res: dict, indent: str = "") -> str:
    L = [f"{indent}repo={res['repo']}  audit_records={res['audit_records']}  splice_bar={res['splice_bar']}",
         f"{indent}  ceiling={res['ceiling']} (live: {', '.join(res['live']) or 'none'} | "
         f"ready: {', '.join(res['ready']) or 'none'})"]
    for k in ORGANS:
        o = res["organs"][k]
        mark = "++" if (o["live"] and o["ready"]) else ("+ " if o["live"] else "  ")
        L.append(f"{indent}    [{mark}] {k:<11} {o['why']}")
    p, a = res["colony_payload"], res["audit"]
    L.append(f"{indent}  colony payload: {p.get('classes', 0)} servable classes  "
             f"p50={p.get('chars_p50', 0)}  p90={p.get('chars_p90', 0)}  max={p.get('chars_max', 0)} chars")
    if p.get("abstained_module_bar"):
        L.append(f"{indent}    ({p['abstained_module_bar']} classes cleared the repo bar but not this build's "
                 f"MIN_DEPOSITS_TO_SPLICE={p.get('module_bar')})")
    L.append(f"{indent}  turns: {a['prompts_injected']}/{a['prompts']} prompts got context; per-turn composition "
             + (f"MEASURED on {a['splice_stamped']} turns (co-fire {a['cofire_rate']:.0%})"
                if a["measurable"] else "NOT RECORDED (audit has injected:bool only)"))
    return "\n".join(L)


def _disp(d: int) -> str:
    return {-1: "-1", 0: "0", 1: "+1"}.get(int(d), str(d))


def _fmt(res: dict) -> str:
    if "rows" in res:
        L = ["SPLICE-COMPOSITION GAUGE  (can the memory organs ever contend for one turn?)",
             f"  estate root={res['root']}  repos={res['repos']}  max ceiling={res['ceiling_max']}  "
             f"co-fire-capable={res['ceiling_ge2']}/{res['repos']}", ""]
        for r in res["rows"]:
            L.append(_fmt_repo(r, "  "))
            L.append("")
        v = res["verdict"]
        L += ["VERDICT:", f"  disposition={_disp(v['disposition'])}  {v['label']}", f"  => {v['note']}",
              "  NOTE: read-only; live = demonstration, never evidence."]
        return "\n".join(L) + "\n"
    v = res["verdict"]
    return ("SPLICE-COMPOSITION GAUGE  (can the memory organs ever contend for one turn?)\n"
            + _fmt_repo(res, "  ")
            + f"\n\nVERDICT:\n  disposition={_disp(v['disposition'])}  {v['label']}\n  => {v['note']}\n"
            + "  NOTE: read-only; live = demonstration, never evidence.\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Splice-Composition Gauge — organ contention ceiling per repo")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--state-dir", help="one repo's .claude/exocortex directory")
    g.add_argument("--estate", action="append",
                   help="projects root to sweep for */.claude/exocortex (repeatable)")
    ap.add_argument("--repo", action="append", default=[],
                    help="an extra repo root to include (repeatable) — for estate members outside the "
                         "projects root, which a root-glob would silently omit")
    ap.add_argument("--splice-bar", type=int, default=None,
                    help="override min_deposits_to_splice (default: repo config, else 3)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = (estate(args.estate, args.repo) if args.estate
           else run(args.state_dir, args.splice_bar))
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
