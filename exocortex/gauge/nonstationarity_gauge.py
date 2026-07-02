"""Offline NON-STATIONARITY gauge (candidate F3 — provenance + recency/version decay) — gauge-first, ADR-002.

F3 is the "quiet rot-killer" from the 2026-06-30 Desktop self-audit: a route learned under one model/era may
not transfer to the next, and a route that was right-but-passed and never re-confirmed should DECAY rather
than persist at full τ forever (the only mechanism that lets reality *demote* a route — a partial corrective
to false-success amplification). The proposed organ stamps each deposit with a model-id + timestamp and decays
τ by recency-and-version-distance. Before building it (ADR-002), measure on the EXISTING audit + colony whether
the signal is even present on this operator's traffic — and, critically, whether the provenance needed to
measure it was ever recorded.

Three readouts, read-only over each repo's `<repo>/.claude/exocortex/{colony_*.json, audit.jsonl}`:

  - **Provenance coverage.** What fraction of colony edges carry a per-deposit timestamp and a model-id (the F3
    ``meta`` lane)? On a pre-F3 store this is ~0 — the finding that non-stationarity is UNMEASURABLE
    retroactively because the instrument was never installed, so F3 is a go-forward instrument. Once the
    provenance hook is live it rises as new deposits are stamped (ts = ``time.time()``; model = the transcript
    tail, since the hook stdin has no model field).

  - **Temporal span & recency.** From the audit `ts`: how long does the store span, and is it actively refreshed
    (deposits ongoing → self-healing, low stale-risk) or front-loaded-then-silent (routes earned long ago and
    never re-confirmed → stale-risk high)?

  - **Stationarity proxy.** Split the consequence stream (verb-altitude command keys) at its time-median into an
    early and a late half; measure how much the verb-frequency distribution DRIFTS (total-variation distance)
    and how much the verb SET churns (born/died). Low drift → a stable recurring dev skeleton (the low-variance
    single-operator regime — F3 latent, ships dormant); high drift → the routing mix is moving and recency
    weighting pays. The POOLED split confounds real within-route rot with the operator merely switching tasks
    over time, so the gauge also reports a WITHIN-CLASS drift (``stationarity_by_class``): the audit's
    UserPromptSubmit ``reason=class=…`` is carried forward onto each session's consequences, and drift is the
    consequence-weighted mean over goal-classes — the de-confounded F3-relevant signal the verdict uses. NB the
    audit stores per-event keys, not transitions, so this is a verb-mix proxy, not an edge-level drift; it is a
    floor on the true non-stationarity, not a ceiling.

Self-contained, numpy-free, read-only — the same fail-open discipline as the hook. STATS-first; the verdict is
a thin threshold the numbers drive.

  python -m exocortex.gauge.nonstationarity_gauge                  # auto-scan sibling repos' live state
  python -m exocortex.gauge.nonstationarity_gauge --state-dir P    # explicit state dir(s) (repeatable)
  python -m exocortex.gauge.nonstationarity_gauge --json           # machine-readable (results file / CI)
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

_SEP = "\t"                                                  # colony τ key separator (colony._SEP)
DRIFT_THRESHOLD = 0.25                                       # TV-distance of verb mix early→late ≥ this → F3 pays
CHURN_THRESHOLD = 0.40                                       # verb-set symmetric-difference fraction ≥ this → turnover
EXCESS_THRESHOLD = 0.10                                      # within-class drift ABOVE the shuffle null ≥ this → real
_NULL_ITERS = 200                                           # permutation-null shuffles per class (small-sample TV floor)
_MIN_SPLIT = 8                                               # need this many keyed consequences to split early/late
_REPO_ROOT = Path(__file__).resolve().parents[2]            # gauge -> exocortex -> repo root
_CONS = ("PostToolUse", "PostToolUseFailure")


# ------------------------------------------------------------------- loaders (read-only, fail-open)
def load_colonies(state_dir) -> list:
    """(label, tau, meta) per ``colony_*.json``. ``meta`` is the F3 per-edge provenance dict if present
    (``{edge_key: {ts, model}}``) — absent on every pre-F3 colony, which is exactly the coverage finding."""
    out = []
    for f in sorted(Path(state_dir).glob("colony_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append((str(d.get("label", "?")),
                        {str(k): float(v) for k, v in dict(d.get("tau", {})).items()},
                        dict(d.get("meta", {}))))
        except Exception:
            continue
    return out


def load_audit(state_dir) -> list:
    out: list = []
    p = Path(state_dir) / "audit.jsonl"
    if p.is_file():
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    return out


def _verb(key: str) -> str:
    s = (key or "").strip()
    return s.split()[0] if s else ""


def _ts(rec: dict):
    """Parse an ISO-8601 audit ``ts`` to an epoch float; None if absent/unparseable (fail-open)."""
    raw = rec.get("ts")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)).timestamp()
    except Exception:
        return None


# ------------------------------------------------------------------- provenance coverage
def provenance(records: list, colonies: list) -> dict:
    """Was the instrument F3 needs ever installed? Fraction of colony edges carrying a per-deposit **timestamp**
    and a **model-id** (the F3 ``meta`` lane). ~0 on a pre-F3 store; rises as the wired hook stamps new deposits
    — model-id is sourced from the transcript tail (the hook stdin has no model field). ``consequences`` is the
    audit count, kept for context."""
    cons = [r for r in records if r.get("event") in _CONS]
    tot_edges = with_ts = with_model = 0
    for _label, tau, meta in colonies:
        for k in tau:
            if _SEP not in k:
                continue
            tot_edges += 1
            m = meta.get(k) if isinstance(meta, dict) else None
            if isinstance(m, dict):
                if m.get("ts"):
                    with_ts += 1
                if m.get("model"):
                    with_model += 1
    return {
        "consequences": len(cons),
        "edges": tot_edges,
        "edge_ts_coverage": round(with_ts / tot_edges, 3) if tot_edges else None,
        "model_coverage": round(with_model / tot_edges, 3) if tot_edges else None,   # colony-edge model stamps (F3)
    }


# ------------------------------------------------------------------- temporal span & recency
def temporal(records: list) -> dict:
    """Span and refresh-recency of the consequence stream (from audit ``ts``)."""
    cons = [r for r in records if r.get("event") in _CONS]
    stamped = sorted((t for t in (_ts(r) for r in cons) if t is not None))
    sessions = len({r.get("session") for r in cons if r.get("session")})
    if len(stamped) < 2:
        return {"ts_coverage": round(len(stamped) / len(cons), 3) if cons else None,
                "span_days": None, "recent_quartile_frac": None, "sessions": sessions}
    first, last = stamped[0], stamped[-1]
    span = last - first
    # fraction of consequences in the most-recent quartile of the [first,last] window (the store's own
    # "present" is its last ts — avoids a wall-clock dependency so the gauge is deterministic in tests).
    q_start = last - span / 4.0
    recent = sum(1 for t in stamped if t >= q_start)
    return {
        "ts_coverage": round(len(stamped) / len(cons), 3) if cons else None,
        "span_days": round(span / 86400.0, 2),
        "recent_quartile_frac": round(recent / len(stamped), 3),   # high → actively refreshed; low → front-loaded/stale
        "sessions": sessions,
    }


# ------------------------------------------------------------------- stationarity proxy
def _tv_distance(a: Counter, b: Counter) -> float | None:
    """Total-variation distance between two verb-frequency distributions (∈ [0,1])."""
    na, nb = sum(a.values()), sum(b.values())
    if not na or not nb:
        return None
    keys = set(a) | set(b)
    return round(0.5 * sum(abs(a[k] / na - b[k] / nb) for k in keys), 3)


def stationarity(records: list) -> dict:
    """Does the verb-altitude consequence mix drift across the timeline? Median time-split → early vs late."""
    cons = [r for r in records if r.get("event") in _CONS and r.get("command_key")]
    pairs = sorted(((t, _verb(r.get("command_key"))) for r in cons if (t := _ts(r)) is not None and _verb(r.get("command_key"))),
                   key=lambda x: x[0])
    n = len(pairs)
    if n < _MIN_SPLIT:
        return {"keyed_consequences": n, "drift_tv": None, "verb_churn": None,
                "born": None, "died": None, "note": f"too few keyed+stamped consequences (<{_MIN_SPLIT}) to split"}
    mid = n // 2
    early = Counter(v for _t, v in pairs[:mid])
    late = Counter(v for _t, v in pairs[mid:])
    born = sorted(set(late) - set(early))         # verbs that appear only in the late half (new routes)
    died = sorted(set(early) - set(late))         # verbs that vanished after the early half (abandoned routes)
    union = set(early) | set(late)
    churn = round((len(born) + len(died)) / len(union), 3) if union else None
    return {
        "keyed_consequences": n,
        "drift_tv": _tv_distance(early, late),     # 0 = identical mix, 1 = disjoint
        "verb_churn": churn,                       # fraction of the verb set that is born-or-died across halves
        "born": born[:8], "died": died[:8],
        "n_born": len(born), "n_died": len(died), "distinct_verbs": len(union),
    }


# ------------------------------------------------------------------- within-class drift (de-confounded)
def _consequences_by_class(records: list) -> dict:
    """Reconstruct which goal-class each consequence belonged to. The audit stamps no class on a consequence,
    but UserPromptSubmit records carry ``reason="class=<label>"``; walk each session in ts order and carry the
    active class forward onto the consequences that follow. Returns {class_label: [(ts, verb), …]} for the
    keyed+stamped consequences. This is what lets the drift metric separate WITHIN-class route rot from the
    operator merely switching tasks (the cross-class confound that inflates the pooled ``stationarity``)."""
    by_session: dict = defaultdict(list)
    for r in records:
        t = _ts(r)
        if t is not None:
            by_session[r.get("session")].append((t, r))
    out: dict = defaultdict(list)
    for _sess, evs in by_session.items():
        evs.sort(key=lambda x: x[0])
        cur = None
        for _t, r in evs:
            ev = r.get("event")
            if ev == "UserPromptSubmit":
                reason = str(r.get("reason") or "")
                if reason.startswith("class="):
                    cur = reason[len("class="):]
            elif ev in _CONS and cur:
                v = _verb(r.get("command_key"))
                if v:
                    out[cur].append((_t, v))
    return out


def _split_drift(verbs: list):
    """TV distance between the early and late half of a time-ordered verb sequence (None if < _MIN_SPLIT)."""
    n = len(verbs)
    if n < _MIN_SPLIT:
        return None
    mid = n // 2
    return _tv_distance(Counter(verbs[:mid]), Counter(verbs[mid:]))


def stationarity_by_class(records: list, null_iters: int = _NULL_ITERS, seed: int = 0) -> dict:
    """Within-class verb-mix drift, de-confounded AND de-biased — the F3-relevant signal.

    (1) De-confound: bucket consequences by their carried-forward goal-class (``_consequences_by_class``) so the
        operator switching task types doesn't read as drift. (2) De-bias: at ~7-vs-7 splits over many verbs, the
        TV distance between two small samples of the SAME distribution is large by sampling variance alone — so
        for each class compare the observed early→late drift to a PERMUTATION NULL (the same verb multiset in
        random temporal order, ``null_iters`` shuffles). The real signal is the EXCESS = observed − null; a
        class whose verbs are merely time-shuffled noise has excess ≈ 0. Seeded → deterministic."""
    buckets = _consequences_by_class(records)
    rng = random.Random(seed)
    per_class = []
    wsum = nsum = 0.0
    tot = 0
    for cls, pairs in buckets.items():
        if len(pairs) < _MIN_SPLIT:
            continue
        verbs = [v for _t, v in sorted(pairs, key=lambda x: x[0])]
        d = _split_drift(verbs)
        if d is None:
            continue
        nd = sum((_split_drift(rng.sample(verbs, len(verbs))) or 0.0) for _ in range(null_iters)) / null_iters
        n = len(verbs)
        per_class.append({"class": cls, "n": n, "drift_tv": d, "null_drift": round(nd, 3),
                          "excess": round(d - nd, 3)})
        wsum += d * n
        nsum += nd * n
        tot += n
    per_class.sort(key=lambda c: -c["excess"])      # rank by EXCESS over the null (the de-biased signal)
    return {
        "classes_measured": len(per_class),
        "consequences": tot,
        "mean_within_class_drift": round(wsum / tot, 3) if tot else None,   # raw observed (still TV-biased)
        "null_drift": round(nsum / tot, 3) if tot else None,                # small-sample TV floor (shuffle null)
        "mean_excess_drift": round((wsum - nsum) / tot, 3) if tot else None,  # observed − null = the real signal
        "top": per_class[:5],
    }


# ------------------------------------------------------------------- verdict
def verdict(prov: dict, temp: dict, stat: dict, stat_cls: dict | None = None) -> dict:
    sc = stat_cls or {}
    pooled = stat.get("drift_tv")
    within = sc.get("mean_within_class_drift")
    null = sc.get("null_drift")
    excess = sc.get("mean_excess_drift")
    churn = stat.get("verb_churn")
    # The de-biased signal is the EXCESS of within-class drift over the shuffle null. Fall back to the raw
    # pooled threshold only when there's no per-class data (no UserPromptSubmit class stamps to bucket by).
    if excess is not None:
        signal = bool(excess >= EXCESS_THRESHOLD)
    else:
        signal = bool((pooled is not None and pooled >= DRIFT_THRESHOLD)
                      or (churn is not None and churn >= CHURN_THRESHOLD))
    instrument_absent = (prov.get("model_coverage") in (0, 0.0)) and (prov.get("edge_ts_coverage") in (None, 0, 0.0))
    return {
        "F3_nonstationarity": {
            "signal": signal,
            "excess_drift": excess,                     # within-class drift ABOVE the shuffle null = the real signal
            "within_class_drift": within,               # raw observed (still small-sample TV-biased)
            "null_drift": null,                         # the shuffle floor (what pure sampling noise produces)
            "drift_tv_pooled": pooled,                  # cross-class-confounded reference (upper bound)
            "classes_measured": sc.get("classes_measured"),
            "verb_churn": churn,
            "instrument_absent": instrument_absent,
            "note": "signal is driven by EXCESS_DRIFT = within-class drift − a permutation null. The pooled "
                    "drift is doubly inflated: by cross-class task-mix (removed via the UserPromptSubmit "
                    "`reason=class=…` carry-forward) AND by small-sample TV bias (~7-vs-7 splits differ a lot "
                    "even with no real rot — quantified by the shuffle null). Only EXCESS over the null is real "
                    "non-stationarity; near-zero excess → the apparent drift is sampling noise, F3 latent → ship "
                    "the provenance instrument DORMANT. instrument_absent=True (no model-id / per-edge ts ever "
                    "recorded) means version-distance was UNMEASURABLE retroactively → F3 is a go-forward "
                    "instrument + the W6 anti-poisoning prerequisite (live stamp = time.time() + transcript-tail model).",
        },
    }


def discover(scan_root: Path) -> list:
    found = []
    if scan_root.is_dir():
        for child in sorted(scan_root.iterdir()):
            sd = child / ".claude" / "exocortex"
            if sd.is_dir():
                found.append(sd)
    return found


def run(state_dirs: list | None = None, scan_root: Path | None = None) -> dict:
    dirs = [Path(d) for d in (state_dirs or [])]
    if not dirs:
        dirs = discover(scan_root or _REPO_ROOT.parent)
    per_repo, all_col, all_rec = [], [], []
    for sd in dirs:
        col, rec = load_colonies(sd), load_audit(sd)
        if not col and not rec:
            continue
        per_repo.append({"repo": sd.parents[1].name,
                         "provenance": provenance(rec, col), "temporal": temporal(rec),
                         "stationarity": stationarity(rec), "stationarity_by_class": stationarity_by_class(rec)})
        all_col.extend(col); all_rec.extend(rec)
    p, t, s, sc = provenance(all_rec, all_col), temporal(all_rec), stationarity(all_rec), stationarity_by_class(all_rec)
    return {"per_repo": per_repo,
            "aggregate": {"provenance": p, "temporal": t, "stationarity": s, "stationarity_by_class": sc},
            "verdict": verdict(p, t, s, sc),
            "thresholds": {"drift_tv": DRIFT_THRESHOLD, "verb_churn": CHURN_THRESHOLD}}


def _fmt(res: dict) -> str:
    lines = ["NON-STATIONARITY GAUGE  (F3 provenance · recency/version decay)", ""]
    for r in res["per_repo"]:
        p, t, s, sc = r["provenance"], r["temporal"], r["stationarity"], r["stationarity_by_class"]
        lines.append(f"  [{r['repo']}] cons={p['consequences']} model_cov={p['model_coverage']} "
                     f"edge_ts_cov={p['edge_ts_coverage']} | span={t['span_days']}d "
                     f"recent_q={t['recent_quartile_frac']} sess={t['sessions']} | "
                     f"drift_pooled={s['drift_tv']} within={sc['mean_within_class_drift']} "
                     f"null={sc['null_drift']} excess={sc['mean_excess_drift']}({sc['classes_measured']}cls)")
    p, t, s, sc = (res["aggregate"]["provenance"], res["aggregate"]["temporal"],
                   res["aggregate"]["stationarity"], res["aggregate"]["stationarity_by_class"])
    lines += ["", "AGGREGATE:",
              f"  provenance:    consequences={p['consequences']} model_coverage={p['model_coverage']} "
              f"edges={p['edges']} edge_ts_coverage={p['edge_ts_coverage']}",
              f"  temporal:      span={t['span_days']}d recent_quartile_frac={t['recent_quartile_frac']} "
              f"sessions={t['sessions']} ts_coverage={t['ts_coverage']}",
              f"  stationarity:  keyed={s['keyed_consequences']} drift_POOLED={s['drift_tv']} "
              f"verb_churn={s['verb_churn']} distinct_verbs={s.get('distinct_verbs')}",
              f"  within-class:  observed={sc['mean_within_class_drift']} null={sc['null_drift']} "
              f"EXCESS={sc['mean_excess_drift']} over {sc['classes_measured']} classes ({sc['consequences']} cons) "
              f"— top excess: " + ", ".join(f"{c['class']}={c['excess']}" for c in sc.get("top", [])),
              "", "VERDICT:"]
    v = res["verdict"]["F3_nonstationarity"]
    lines.append(f"  F3_nonstationarity: signal={v['signal']}  excess_drift={v['excess_drift']} "
                 f"(within={v['within_class_drift']} − null={v['null_drift']}; pooled={v['drift_tv_pooled']})  "
                 f"instrument_absent={v['instrument_absent']}")
    lines.append(f"       {v['note']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Non-stationarity gauge (F3 provenance; recency/version decay)")
    ap.add_argument("--state-dir", action="append", default=[], help="explicit .claude/exocortex dir (repeatable)")
    ap.add_argument("--scan-root", default=None, help="dir to scan for */.claude/exocortex")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    res = run(args.state_dir or None, Path(args.scan_root) if args.scan_root else None)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
