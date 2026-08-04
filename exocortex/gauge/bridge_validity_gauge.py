"""Bridge-validity gauge — the ON-BODY gate the Hippocampus bridge (Ticket 2) has been waiting on.

Run:

    python -m exocortex.gauge.bridge_validity_gauge --state-dir <repo>/.claude/exocortex [--json]

WHY THIS EXISTS
---------------
``gauge/bridge_gauge.py`` answers a GEOMETRY question offline: can the HDC router recall a real route
(1-hop fidelity 1.0), and does the 0-well abstain lift 2-hop chord precision (0.96 → 1.00)? It then states
its own limit, and that limit is the whole reason the organ is dormant:

    executable validity of a direct A→D is NOT offline-decidable — only the body settles whether the
    skipped steps mattered.

This gauge answers the *body* question instead: **when a synthesized shortcut is walked, does the work
still reach ``exit 0``, and does offering it earn anything the body would not have done anyway?**

Until 2026-07-30 the bridge was dormant for a different, THERMODYNAMIC reason — the ≥2-note declarative
tail was measured at 8.9% and judged too thin to feed a bridge. Re-measurement killed that reason (26.5%
of 2,383 injected segments; ``results/declarative_tail_v1/``), which promoted this instrument from
"someday" to "the only thing left in the way".

THE DESIGN — why a retrospective arm is legitimate here
-------------------------------------------------------
A bridge's lifecycle IS the experiment: ``proposed`` → ``offered`` → ``confirmed`` (A and D both credited
in one ``exit 0``) | ``scarred``. So the gauge has two phases, and the first one is runnable TODAY with
the organ still off:

**PHASE A — pre-flight (organ dormant).** ``declarative.bridge.mode`` has never been anything but ``off``
and no ``wiki_bridges.json`` has ever existed, therefore **every** note→note edge in the live record was
earned with **no bridge ever offered**. The whole history is a clean control arm — a rare gift, and it
expires the moment the organ is flipped on. From it we can compute the thing a live arm must beat:

    BASE RATE = of the (A,D) pairs that were bridge CANDIDATES (2-hop reachable, no direct edge), what
    fraction later acquired a direct A→D edge ANYWAY, with nothing ever offered?

A confirmed-bridge rate that merely matches this number means the organ is taking credit for transitions
the body was going to make on its own. That is the load-bearing null, and it is why this gauge refuses to
score confirmations in isolation.

Candidate ordering uses the **F3 per-edge provenance stamps** (``meta{ts}``): a pair only counts as
spontaneously resolved if both legs of a 2-hop path predate the direct edge. Unstamped legacy edges are
excluded from the null rather than assumed — reported as ``unstampable``.

**PHASE B — readout (organ in ``suggest``).** Reads ``wiki_bridges.json`` read-only and reports confirm
vs scar, walks-to-verdict, and the confirm rate against Phase A's base rate.

PRE-REGISTERED FALSIFIER (state it before the data moves)
---------------------------------------------------------
- **−1 (park the organ permanently)** if the live confirm rate does **not exceed** the Phase-A base rate.
  Offering a chord that the body would have walked anyway buys nothing and costs context budget.
- **−1** if ``ungrounded`` proposals dominate: chords whose D is not reachable from A at all in the real
  transition record are geometry inventing links, not shortening routes.
- **0 (keep waiting)** if Phase A says the experiment is UNDERPOWERED — too few candidates to separate the
  arms. An underpowered flip that returns a null is worse than not flipping, because it burns the clean
  control arm above and cannot be undone.
- **+1** only on a live confirm rate clearing the base rate at adequate power, on a repo whose task mix
  was not chosen for the organ.

READ-ONLY SCOPE — stated exactly, because it was verified rather than assumed
----------------------------------------------------------------------------
It calls the REAL ``bridge.synthesize(..., save=False)``, so it measures the organ rather than a
re-implementation, and **deposits no memory**: no τ, no σ, no colony/wiki/scar/config mutation, and no
``wiki_bridges.json``. A whole-state-dir byte-compare across a run (221 files) changes exactly one file:
``wiki_cache.json``, the derived digest that ``load_graph`` refreshes in the **geometry phase only**. That
is a cache, not memory — the same boundary ``docs/MCP_SERVER.md`` already draws for the read-only MCP
server. The structural phases (candidates, base rate, power, live readout) touch nothing at all; omit
``--vault-path`` if you want a run that cannot write a byte.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SEP = "\t"
Z_ALPHA = 1.96      # two-sided 0.05
Z_POWER = 0.84      # 80% power


# ----------------------------------------------------------------- io (read-only)
def _json_file(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_note(nid: str) -> bool:
    """A note node is a vault path (carries '.md'); verb nodes ('Edit:src', 'bash:cd') and 'cue:' roots
    are not. Mirrors credit_funnel_gauge's note-anchored test so the two gauges agree on what a note is."""
    return ".md" in nid and not nid.startswith("cue:")


def read_note_edges(state_dir: Path) -> dict:
    """Every note→note transition the live colonies earned, per class, with its F3 stamp when present.

    Returns ``{label: {(a, d): ts_or_None}}``. Self-edges are dropped: ADR/W5 already treats ``a→a`` as
    carrying no routing information, and a self-bridge is meaningless."""
    out: dict = {}
    for f in sorted(state_dir.glob("colony_*.json")):
        d = _json_file(f)
        tau = d.get("tau") or {}
        meta = d.get("meta") or {}
        if not tau:
            continue
        label = f.stem[len("colony_"):]
        edges: dict = {}
        for k in tau:
            a, _, b = k.partition(_SEP)
            if not b or a == b or not _is_note(a) or not _is_note(b):
                continue
            ts = (meta.get(k) or {}).get("ts")
            edges[(a, b)] = float(ts) if isinstance(ts, (int, float)) else None
        if edges:
            out[label] = edges
    return out


# ----------------------------------------------------------------- phase A: candidates + the null
def candidates_and_base_rate(note_edges: dict) -> dict:
    """The pre-flight census and the control arm.

    A **candidate** is (A,D) with a real 2-hop path A→B→D and no real A→D: exactly what a bridge would
    shortcut. A candidate **resolved spontaneously** if a direct A→D edge exists AND both legs of some
    2-hop path predate it (F3 stamps) — i.e. the body made the jump with nothing offered.

    The base rate is resolved / (resolved + open). It is the number a live confirm rate must beat."""
    open_c = resolved = unstampable = 0
    per_class: dict = {}
    for label, edges in note_edges.items():
        succ: dict = {}
        for (a, b) in edges:
            succ.setdefault(a, set()).add(b)
        direct = set(edges)
        pairs_2hop: dict = {}
        for a, bs in succ.items():
            for b in bs:
                for d in succ.get(b, ()):    # A→B→D
                    if d == a or d == b:
                        continue
                    legs = (edges.get((a, b)), edges.get((b, d)))
                    prev = pairs_2hop.get((a, d))
                    # keep the EARLIEST fully-stamped 2-hop path for the ordering test
                    if None in legs:
                        pairs_2hop.setdefault((a, d), prev)
                        continue
                    latest_leg = max(legs)
                    if prev is None or latest_leg < prev:
                        pairs_2hop[(a, d)] = latest_leg
        c_open = c_res = c_uns = 0
        for (a, d), leg_ts in pairs_2hop.items():
            if (a, d) not in direct:
                c_open += 1
                continue
            ts_ad = edges.get((a, d))
            if ts_ad is None or leg_ts is None:
                c_uns += 1                    # a direct edge exists but ordering is unknowable → excluded
            elif leg_ts < ts_ad:
                c_res += 1                    # the 2-hop route existed FIRST, then the body jumped it
            else:
                c_uns += 1                    # direct edge predates the path → not a shortcut event
        open_c += c_open
        resolved += c_res
        unstampable += c_uns
        if c_open or c_res:
            per_class[label] = {"open": c_open, "resolved": c_res, "unstampable": c_uns}
    denom = resolved + open_c
    return {"candidates_open": open_c, "resolved_spontaneously": resolved,
            "unstampable": unstampable, "base_rate_denominator": denom,
            "base_rate": round(resolved / denom, 4) if denom else None,
            "classes_with_candidates": len(per_class),
            "top_classes": dict(sorted(per_class.items(),
                                       key=lambda kv: -(kv[1]["open"] + kv[1]["resolved"]))[:8])}


def power_needed(base_rate: "float | None", lift: float = 0.15) -> dict:
    """Offers required to separate a live confirm rate from the base rate, at α=0.05 / power=0.80.

    Deliberately a plain two-proportion calculation, printed with its assumption, so an underpowered flip
    is refused BEFORE it burns the one-shot control arm rather than explained afterwards."""
    if base_rate is None:
        return {"detectable": None, "note": "no base rate — nothing to power against"}
    p0 = min(max(base_rate, 1e-6), 1 - 1e-6)
    p1 = min(p0 + lift, 0.999)
    pbar = (p0 + p1) / 2
    num = (Z_ALPHA * math.sqrt(2 * pbar * (1 - pbar)) + Z_POWER * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    n = num / ((p1 - p0) ** 2)
    return {"target_lift_pp": round(lift * 100, 1), "p0": round(p0, 4), "p1": round(p1, 4),
            "offers_needed_per_arm": int(math.ceil(n))}


# ----------------------------------------------------------------- phase A: what geometry would propose
def geometry_proposals(vault_path: str, label: str, note_edges: dict) -> dict:
    """Run the ORGAN'S OWN synthesis (``save=False``) and classify each chord against the real record.

    - ``already_real``  — a real A→D edge exists: geometry rediscovering a known transition. Precision
      evidence, but it shortcuts nothing.
    - ``grounded``      — no direct edge, but D IS reachable from A: the genuine shortcut target.
    - ``ungrounded``    — D is not reachable from A at all: geometry inventing a link. The risk class.

    Reachability is checked against the **union of note transitions across ALL classes**, not one class's.
    ``synthesize`` proposes over the whole vault graph, so scoring its chords against a single colony's
    edges measures the wrong thing: an early draft did exactly that and read 32/32 ungrounded — a −1 the
    gauge would have reported as a finding about the ORGAN when it was an artifact of the DENOMINATOR.
    Per-class figures are reported alongside, since a chord grounded only in another class is weaker
    evidence than one grounded in the class that would offer it.

    Optional: needs the phasor bank (MiniLM, the ``[embed]`` extra). Absent → skipped, never fatal, and
    NOT silently reported as zero."""
    try:
        from ..wiki.bridge import synthesize
        from ..wiki.digest import encode_phasor
        from ..wiki.store import load_graph
    except Exception as e:
        return {"available": False, "reason": f"import failed: {type(e).__name__}"}
    try:
        graph = load_graph(vault_path, label=label)
        if graph is None or not graph.nodes:
            return {"available": False, "reason": "no graph for this vault/label"}
        if graph.build_phasor_bank(encode_phasor) is None:
            return {"available": False,
                    "reason": "phasor bank unavailable (needs the [embed] extra: pip install sentaince[embed])"}
        proposed = synthesize(graph, bridges={}, stamp="gauge", save=False)   # PURE — deposits nothing
    except Exception as e:
        return {"available": False, "reason": f"synthesis failed: {type(e).__name__}"}

    edges = {e for per in note_edges.values() for e in per}     # union: the body's whole record
    in_class = set(note_edges.get(label, {}))
    succ: dict = {}
    for (a, b) in edges:
        succ.setdefault(a, set()).add(b)

    def reachable(a: str, d: str, hops: int = 4) -> bool:
        seen, frontier = {a}, {a}
        for _ in range(hops):
            nxt = set()
            for x in frontier:
                for y in succ.get(x, ()):
                    if y == d:
                        return True
                    if y not in seen:
                        seen.add(y)
                        nxt.add(y)
            frontier = nxt
            if not frontier:
                break
        return False

    seen = {x for e in edges for x in e}          # notes that appear ANYWHERE in the credited record
    already = grounded = invented = unseen = already_in_class = 0
    for key in proposed:
        a, _, d = key.partition(_SEP)
        if (a, d) in edges:
            already += 1
            already_in_class += int((a, d) in in_class)
        elif reachable(a, d):
            grounded += 1
        elif a in seen and d in seen:
            invented += 1                          # both endpoints have history, yet no route joins them
        else:
            unseen += 1                            # an endpoint has NO credited history — unscoreable
    n = already + grounded + invented + unseen
    scoreable = already + grounded + invented
    return {"available": True, "proposed": n, "already_real": already,
            "already_real_in_offering_class": already_in_class,
            "grounded_shortcuts": grounded,
            "invented": invented, "unseen_endpoint": unseen,
            # the FALSIFIER denominator is scoreable chords only: a chord whose endpoint was never
            # credited cannot be called an invention — that is vault coverage, not geometry misfiring.
            "invented_frac_of_scoreable": round(invented / scoreable, 4) if scoreable else None,
            "scoreable": scoreable,
            "scored_against_edges": len(edges), "credited_notes": len(seen), "label": label}


# ----------------------------------------------------------------- phase B: the live readout
def live_readout(state_dir: Path) -> dict:
    """Read ``wiki_bridges.json`` (read-only). Absent → the organ has never run, which is what makes the
    Phase-A control arm clean; that is a *state*, not a failure."""
    d = _json_file(state_dir / "wiki_bridges.json")
    if not d:
        return {"live": False, "note": "no bridges ledger — organ has never run (control arm intact)"}
    counts: dict = {}
    walks: list = []
    for b in d.values():
        if not isinstance(b, dict):
            continue
        counts[b.get("status", "?")] = counts.get(b.get("status", "?"), 0) + 1
        if b.get("status") in ("confirmed", "scarred"):
            walks.append(int(b.get("walks", 0) or 0))
    settled = counts.get("confirmed", 0) + counts.get("scarred", 0)
    return {"live": True, "by_status": counts, "settled": settled,
            "confirm_rate": round(counts.get("confirmed", 0) / settled, 4) if settled else None,
            "mean_walks_to_verdict": round(sum(walks) / len(walks), 2) if walks else None}


# ----------------------------------------------------------------- verdict
def verdict(base: dict, power: dict, geo: dict, live: dict) -> dict:
    """Dispositions are the project's triad: −1 falsified · 0 not yet decidable · +1 survives its control."""
    br = base["base_rate"]
    if base["base_rate_denominator"] < 30:
        return {"disposition": 0, "signal": False, "gate": "UNDERPOWERED",
                "note": f"only {base['base_rate_denominator']} candidate pairs on this store — too few to "
                        "separate a live arm from the base rate. Do NOT flip: an underpowered run burns "
                        "the one-shot no-offer control arm and cannot be undone. Accrue, or run on a "
                        "repo with a denser declarative record."}
    if geo.get("available") and (geo.get("scoreable") or 0) >= 20 \
            and (geo.get("invented_frac_of_scoreable") or 0) > 0.5:
        return {"disposition": -1, "signal": True, "gate": "INVENTED",
                "note": f"{geo['invented_frac_of_scoreable']:.0%} of SCOREABLE proposals join two notes "
                        "that both have credited history but no route between them — geometry inventing "
                        "links rather than shortening routes. Fix synthesis before any flip."}
    if geo.get("available") and (geo.get("scoreable") or 0) < 20:
        return {"disposition": 0, "signal": False, "gate": "GEOMETRY-UNSCOREABLE",
                "note": f"only {geo.get('scoreable')} of {geo.get('proposed')} proposals are scoreable "
                        f"({geo.get('unseen_endpoint')} have an endpoint with no credited history at all). "
                        "The vault is far larger than its credited subgraph, so this says nothing about "
                        "geometry quality — it is a coverage fact. Do not read it as an organ defect."}
    if not live.get("live"):
        return {"disposition": 0, "signal": False, "gate": "READY-TO-FLIP" if br is not None else "NO-BASE-RATE",
                "note": f"pre-flight only. base_rate={br} over {base['base_rate_denominator']} candidate "
                        f"pairs; a live arm needs ~{power.get('offers_needed_per_arm')} settled offers to "
                        f"detect +{power.get('target_lift_pp')}pp. Flip `declarative.bridge.mode=suggest` "
                        "LOCALLY to open the live arm, then re-run this gauge."}
    cr = live.get("confirm_rate")
    if cr is None:
        return {"disposition": 0, "signal": False, "gate": "NO-VERDICTS-YET",
                "note": "organ is live but no bridge has settled (confirmed/scarred) yet."}
    if live["settled"] < power.get("offers_needed_per_arm", 10**9):
        return {"disposition": 0, "signal": False, "gate": "ACCRUING",
                "note": f"confirm_rate={cr} vs base_rate={br}, but only {live['settled']} settled of "
                        f"~{power.get('offers_needed_per_arm')} needed. Not yet decidable."}
    if br is not None and cr <= br:
        return {"disposition": -1, "signal": True, "gate": "NULL — FALSIFIER FIRED",
                "note": f"confirm_rate={cr} does not exceed the no-offer base rate {br}: the body walks "
                        "these transitions anyway. The bridge earns nothing for its context cost — park it."}
    return {"disposition": 1, "signal": True, "gate": "SURVIVES ITS CONTROL",
            "note": f"confirm_rate={cr} exceeds the no-offer base rate {br} at adequate power. Promote only "
                    "if this repo's task mix was not selected for the organ (self-selection is not evidence)."}


# ----------------------------------------------------------------- run / report
def run(state_dir: str, vault_path: str = "", label: str = "", lift: float = 0.15) -> dict:
    sd = Path(state_dir)
    note_edges = read_note_edges(sd)
    base = candidates_and_base_rate(note_edges)
    power = power_needed(base["base_rate"], lift=lift)
    geo = ({"available": False, "reason": "no --vault-path given (structural phases still valid)"}
           if not vault_path else geometry_proposals(vault_path, label or "_default", note_edges))
    live = live_readout(sd)
    return {"state_dir": str(sd), "classes_with_note_edges": len(note_edges),
            "note_edges": sum(len(e) for e in note_edges.values()),
            "phase_a_candidates": base, "power": power, "geometry": geo, "phase_b_live": live,
            "verdict": verdict(base, power, geo, live)}


def _fmt(r: dict) -> str:
    b, p, g, lv, v = (r["phase_a_candidates"], r["power"], r["geometry"], r["phase_b_live"], r["verdict"])
    L = ["BRIDGE-VALIDITY GAUGE  (does the body confirm a synthesized shortcut?)",
         f"  state_dir={r['state_dir']}",
         f"  real note→note transitions: {r['note_edges']} over {r['classes_with_note_edges']} classes", "",
         "PHASE A — pre-flight (the no-offer control arm; the organ has never been on)",
         f"  bridge candidates still open      : {b['candidates_open']}",
         f"  candidates resolved SPONTANEOUSLY : {b['resolved_spontaneously']}  (2-hop path predates a direct edge)",
         f"  excluded, ordering unknowable     : {b['unstampable']}  (unstamped legacy edges — F3)",
         f"  BASE RATE (what a live arm must beat) : {b['base_rate']}  over n={b['base_rate_denominator']}",
         f"  classes carrying candidates       : {b['classes_with_candidates']}"]
    if b["top_classes"]:
        L.append("  densest classes: " + ", ".join(f"{k}({vv['open']}o/{vv['resolved']}r)"
                                                   for k, vv in b["top_classes"].items()))
    if p.get("offers_needed_per_arm"):
        L += ["", f"  POWER: ~{p['offers_needed_per_arm']} settled offers to detect "
                  f"+{p['target_lift_pp']}pp over p0={p['p0']} (α=0.05, power=0.80)"]
    L += ["", "GEOMETRY — what the organ's own synthesis would propose"]
    if g.get("available"):
        L += [f"  gated proposals: {g['proposed']}  (scored against {g['scored_against_edges']} real "
              f"transitions over {g['credited_notes']} credited notes)",
              f"    already-real {g['already_real']} · grounded shortcuts {g['grounded_shortcuts']} · "
              f"INVENTED {g['invented']} · unseen-endpoint {g['unseen_endpoint']} (unscoreable)",
              f"    invented share of the {g['scoreable']} SCOREABLE: "
              f"{'n/a' if g['invented_frac_of_scoreable'] is None else format(g['invented_frac_of_scoreable'], '.0%')}"]
    else:
        L += [f"  (skipped: {g.get('reason')})"]
    L += ["", "PHASE B — live readout"]
    L += ([f"  by_status={lv['by_status']}  settled={lv['settled']}  confirm_rate={lv['confirm_rate']}  "
           f"mean_walks={lv['mean_walks_to_verdict']}"] if lv.get("live") else [f"  {lv['note']}"])
    L += ["", "VERDICT:", f"  disposition={v['disposition']:+d}  gate={v['gate']}", f"  {v['note']}",
          "", "  read-only; deposits nothing. The falsifier is pre-registered in this module's docstring."]
    return "\n".join(L)


def main(argv: "list | None" = None) -> int:
    ap = argparse.ArgumentParser(description="Bridge-validity gauge (Ticket 2's on-body gate)")
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--vault-path", default="", help="enable the geometry phase (needs the [embed] extra)")
    ap.add_argument("--label", default="", help="goal-class for the geometry phase")
    ap.add_argument("--lift", type=float, default=0.15, help="target lift over base rate (default 0.15)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = run(a.state_dir, a.vault_path, a.label, a.lift)
    print(json.dumps(res, indent=2) if a.json else _fmt(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
