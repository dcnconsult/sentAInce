"""Verb-Keying Gauge — does working-verb keying keep the consequence law's discrimination? (R0 / DQ-1)

The live colony keys a Bash action by its FIRST token (``colony._bash_verb``). For compound commands that
token is navigation or an env assignment: ``cd repo && pytest -q`` is remembered as ``bash:cd``. This
gauge replays a recorded audit under that keying and under a WORKING-verb keying, and compares what the
consequence law needs: fail/pass separability and the frequency-null clutter it discriminates against.

Frozen protocol: ``results/verb_keying_v1/PREREG.md`` (the keyings, the replay model, the decision rule).
Read-only over one audit JSONL, pure stdlib (+ the ``analyze`` mirror colony), deterministic, fail-open on
malformed rows. Emits aggregates only — never command text. A run over a live repo is a labeled
demonstration.

  python -m exocortex.gauge.verb_keying_gauge --audit .claude/exocortex/audit.jsonl
  python -m exocortex.gauge.verb_keying_gauge --audit A.jsonl --audit B.jsonl --label A --label B --json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from exocortex.colony import _working_verb as working_verb  # noqa: F401 — re-exported; the ONE implementation (PREREG §3)
from exocortex.colony import verb_node
from exocortex.gauge.analyze import _Colony, _entropy

EPS = 0.02                                     # PREREG §5 absolute tolerance
_NAV_KEYS = {f"bash:{v}" for v in ("cd", "pushd", "popd", "export", "set", "source")}
KEYINGS = ("first", "working")


def node(tool: str, payload: str, keying: str) -> str:
    return verb_node(tool, payload, keying=keying)


def _is_nav_env(key: str) -> bool:
    return key in _NAV_KEYS or "=" in key.split(":", 1)[-1]


def segments(records, keying: str) -> list:
    """Replay (PREREG §4): per-session trails → closed segments ``(class, outcome, edges)``."""
    trails: dict = {}
    classes: dict = collections.defaultdict(lambda: "_default")
    out = []
    for r in records:
        s = str(r.get("session", r.get("session_id", "")))
        ev = r.get("event")
        if ev == "UserPromptSubmit":
            m = re.match(r"class=(.+)", str(r.get("reason") or ""))
            classes[s] = m.group(1) if m else "_default"
            trails[s] = [f"cue:{classes[s]}"]
        elif ev == "PreToolUse" and r.get("tool"):
            trails.setdefault(s, [f"cue:{classes[s]}"]).append(
                node(str(r["tool"]), str(r.get("command") or ""), keying))
        elif ev in ("PostToolUse", "PostToolUseFailure") and r.get("tool") in ("Bash", "PowerShell"):
            outcome = "ok" if (ev == "PostToolUse" and r.get("outcome", "ok") == "ok") else "fail"
            trail = trails.get(s, [f"cue:{classes[s]}"])
            edges = [(a, b) for a, b in zip(trail, trail[1:]) if a != b]
            out.append((classes[s], outcome, edges))
            cue = f"cue:{classes[s]}"
            trails[s] = [cue, node(str(r["tool"]), str(r.get("command") or ""), keying)] \
                if outcome == "ok" else [cue]
    return out


def measure(segs: list) -> dict:
    ok_edges, fail_edges = set(), set()
    ok_list = []
    for _, oc, es in segs:
        (ok_edges if oc == "ok" else fail_edges).update(es)
        if oc == "ok":
            ok_list.extend(es)
    fail_only = fail_edges - ok_edges
    result = {}
    for policy in ("consequence", "frequency"):
        cols: dict = collections.defaultdict(_Colony)
        for cls, oc, es in segs:
            if es and (policy == "frequency" or oc == "ok"):
                cols[cls].deposit(es)
        memory = {(c, e) for c, col in cols.items() for e in col.tau}
        clutter = sum(1 for _, e in memory if e in fail_only)
        result[policy] = {"memory": len(memory), "clutter_frac": round(clutter / max(1, len(memory)), 4),
                          "mean_class_entropy": round(
                              sum(_entropy(c.tau) for c in cols.values()) / max(1, len(cols)), 3)}
    union = ok_edges | fail_edges
    nodes = {n for e in union for n in e}
    return {
        "segments": len(segs), "ok_segments": sum(1 for _, oc, _ in segs if oc == "ok"),
        "M1_nav_env_share": round(sum(1 for e in ok_list if _is_nav_env(e[0]) or _is_nav_env(e[1]))
                                  / max(1, len(ok_list)), 4),
        "M2_frequency_clutter": result["frequency"]["clutter_frac"],
        "M3_pass_fail_jaccard": round(len(ok_edges & fail_edges) / max(1, len(union)), 4),
        "check_consequence_clutter": result["consequence"]["clutter_frac"],
        "M4": {"distinct_nodes": len(nodes), "distinct_edges": len(union),
               "consequence_memory": result["consequence"]["memory"],
               "mean_class_entropy": result["consequence"]["mean_class_entropy"]},
    }


def _read(path: Path) -> list:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if isinstance(r, dict):
                rows.append(r)
    return rows


def run(audit: Path) -> dict:
    recs = _read(audit)
    return {k: measure(segments(recs, k)) for k in KEYINGS}


def repo_verdict(res: dict) -> dict:
    f, w = res["first"], res["working"]
    a = w["M1_nav_env_share"] <= 0.5 * f["M1_nav_env_share"]
    b = w["M2_frequency_clutter"] >= f["M2_frequency_clutter"] - EPS
    c = w["M3_pass_fail_jaccard"] <= f["M3_pass_fail_jaccard"] + EPS
    void = f["check_consequence_clutter"] != 0 or w["check_consequence_clutter"] != 0
    return {"a_nav_halved": a, "b_clutter_kept": b, "c_separability_kept": c, "void": void}


def verdict(per_repo: dict) -> dict:
    """PREREG §5 across repos."""
    vs = {k: repo_verdict(v) for k, v in per_repo.items()}
    if any(v["void"] for v in vs.values()):
        return {"disposition": "VOID", "per_repo": vs}
    if len(vs) >= 2 and all(v["a_nav_halved"] and v["b_clutter_kept"] and v["c_separability_kept"]
                            for v in vs.values()):
        d = "+1"
    elif len(vs) >= 2 and all(not (v["b_clutter_kept"] and v["c_separability_kept"]) for v in vs.values()):
        d = "-1"
    else:
        d = "0"
    return {"disposition": d, "per_repo": vs}


def is_nav_env_node(n: str) -> bool:
    """A navigation/env-keyed COMMAND node (``bash:cd``, ``ps:cd``, ``bash:VAR=1``…); file nodes never are."""
    ns, _, verb = n.partition(":")
    return ns in ("bash", "ps") and (verb in _NAV_VERBS or "=" in verb)


_NAV_VERBS = {"cd", "pushd", "popd", "export", "set", "source"}


def chain_breaks_from(audit: Path, from_line: int) -> dict:
    """S4: EVERY chain break among records at 1-based audit line ≥ ``from_line`` (``verify_audit`` reports
    only the FIRST break in the file, so a known historic break would mask a new one). Each chained record
    in the window must match its own self-hash and link to the chained record just before it."""
    from exocortex.integrity import chain_hash
    breaks, checked, prev = [], 0, None
    try:
        with open(audit, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not isinstance(r, dict) or "hash" not in r:
                    continue
                if n >= from_line:
                    checked += 1
                    if chain_hash(r, r.get("prev", "")) != r.get("hash"):
                        breaks.append({"line": n, "kind": "self-hash"})
                    elif prev is not None and r.get("prev") != prev:
                        breaks.append({"line": n, "kind": "link"})
                prev = r.get("hash")
    except Exception as e:
        return {"ok": False, "checked": checked, "breaks": breaks, "error": type(e).__name__}
    return {"ok": not breaks, "checked": checked, "breaks": breaks[:20]}


def soak(state_dir: Path, since: float) -> dict:
    """Trial readout over a live store (SOAK.md): edges whose F3 stamp is ≥ ``since`` were deposited (or
    re-reinforced) after the flip. Read-only; aggregates only."""
    tot = nav = 0.0
    edges = nav_edges = new = new_nav = 0
    classes = deposits = 0
    top_nav = top_seen = 0
    for f in sorted(Path(state_dir).glob("colony_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        classes += 1
        deposits += int(d.get("deposits", 0))
        tau, meta = d.get("tau", {}) or {}, d.get("meta", {}) or {}
        fresh = {k: w for k, w in tau.items() if float((meta.get(k) or {}).get("ts") or 0) >= since}
        for k, w in tau.items():
            a, _, b = k.partition("\t")
            hit = is_nav_env_node(a) or is_nav_env_node(b)
            edges += 1
            tot += w
            nav_edges += hit
            nav += w if hit else 0.0
            if k in fresh:
                new += 1
                new_nav += hit
        if fresh:
            top_seen += 1
            ka = max(fresh, key=lambda k: fresh[k])
            top_nav += any(is_nav_env_node(x) for x in ka.split("\t"))
    return {"since": since, "classes": classes, "deposits": deposits, "edges": edges,
            "S1_new_edges": new, "S1_new_nav_env_share": round(new_nav / max(1, new), 4),
            "S2_classes_with_new_edges": top_seen, "S2_top_new_edge_is_nav": top_nav,
            "S5_nav_env_edge_share": round(nav_edges / max(1, edges), 4),
            "S5_nav_env_tau_share": round(nav / max(tot, 1e-9), 4)}


def _fmt(per_repo: dict, v: dict) -> str:
    lines = ["Verb-Keying Gauge (R0 / DQ-1) — PREREG results/verb_keying_v1/PREREG.md", ""]
    for name, res in per_repo.items():
        lines.append(f"[{name}]  segments={res['first']['segments']} ok={res['first']['ok_segments']}")
        for k in KEYINGS:
            m = res[k]
            lines.append(f"  {k:8} M1 nav/env={m['M1_nav_env_share']:.3f}  M2 freq-clutter="
                         f"{m['M2_frequency_clutter']:.3f}  M3 jaccard={m['M3_pass_fail_jaccard']:.3f}  "
                         f"nodes={m['M4']['distinct_nodes']} edges={m['M4']['distinct_edges']}  "
                         f"(check conseq-clutter={m['check_consequence_clutter']})")
        lines.append(f"  → {v['per_repo'][name]}")
    lines.append(f"\nDISPOSITION: {v['disposition']}  (labeled demonstration over recorded traffic)")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verb-Keying Gauge — first-token vs working-verb keying")
    ap.add_argument("--audit", action="append", default=[], help="audit.jsonl (repeatable)")
    ap.add_argument("--label", action="append", default=[], help="label per --audit (default: stem)")
    ap.add_argument("--soak-state", help="trial readout over a live state dir (see SOAK.md)")
    ap.add_argument("--since", type=float, default=0.0, help="flip epoch for --soak-state")
    ap.add_argument("--from-line", type=int, default=0,
                    help="with --soak-state: S4 chain check over <state>/audit.jsonl from this line on")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.soak_state:
        sd = Path(args.soak_state)
        out = soak(sd, args.since)
        if args.from_line:
            out["S4_chain_from_flip"] = chain_breaks_from(sd / "audit.jsonl", args.from_line)
            out["S4_quarantine_files"] = len(list(sd.glob("*.corrupt-*")))
        print(json.dumps(out, indent=2))
        return 0
    if not args.audit:
        ap.error("--audit is required unless --soak-state is given")
    labels = args.label + [Path(a).parent.parent.parent.name or Path(a).stem
                           for a in args.audit[len(args.label):]]
    per_repo = {lab: run(Path(a)) for lab, a in zip(labels, args.audit)}
    v = verdict(per_repo)
    print(json.dumps({"results": per_repo, "verdict": v}, indent=2) if args.json else _fmt(per_repo, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
