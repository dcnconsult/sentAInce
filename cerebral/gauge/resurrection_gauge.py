"""TAO Resurrection Gauge — does the intent register surface genuinely-lost, worth-resuming research
threads? (STATS) Slice 0 of the Cerebral Substrate; gauge-first (ADR-002).

Read-only, pure-stdlib, fail-open. Harvests DECLARED intents from a vault (Markdown checkboxes + structured
``ledger.json`` — never inferred from prose; ``cerebral/intents.py``), flags the ``OPEN ∧ stale`` ones (open
past their ``reasonable_timeframe``), and — once the PI labels a sample — reports the ship/no-ship number:
**precision @ worth-resuming**. That number gates the persistent living ledger, the Consolidator, and the
Governor. A run over a real vault is a **labeled demonstration, never evidence**.

  python -m cerebral.gauge.resurrection_gauge --vault DIR --now 2026-07-01            # candidate list
  python -m cerebral.gauge.resurrection_gauge --vault DIR --now 2026-07-01 --json     # machine-readable
  python -m cerebral.gauge.resurrection_gauge --vault DIR --now 2026-07-01 --labels labels.json   # precision
  python -m cerebral.gauge.resurrection_gauge --vault DIR --now 2026-07-01 --timeframe issue=45    # override

``--now`` is REQUIRED (never call the wall clock implicitly — deterministic, reproducible runs). ``--labels``
is a JSON map ``{intent_id: "worth"|"mislabeled"|"abandoned"}`` (worth-resuming vs the two not-worth classes).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from cerebral.intents import OPEN, CLOSED, TIMEFRAME_DAYS, harvest, _iso_date

# ship/no-ship thresholds (thin — the numbers drive it)
PRECISION_BAR = 0.50      # precision @ worth-resuming must clear this to justify the persistent ledger
MIN_LABELED = 10          # …on at least this many PI-labeled candidates (else UNDERPOWERED)
DORMANT_DAYS = 90         # v2: a parent (paper) whose freshest stale item is older than this = a dormant cluster

_WORTH = {"worth", "worth_resuming", "resume", "yes", "true", "1"}
_NOT_WORTH = {"mislabeled", "already_closed", "abandoned", "correctly_abandoned", "no", "false", "0", "skip"}


def _parse_date(s: str):
    d = _iso_date(s)
    return datetime.strptime(d, "%Y-%m-%d").date() if d else None


def _days_between(iso: "str | None", now):
    d = _parse_date(iso or "")
    return (now - d).days if d else None


# ------------------------------------------------------------------ analysis
def analyze(intents: list, now, timeframe: dict, dormant_days: int) -> dict:
    for it in intents:
        it.reasonable_timeframe_days = timeframe.get(it.kind, it.reasonable_timeframe_days)
    open_intents = [it for it in intents if it.lifecycle == OPEN]
    closed = [it for it in intents if it.lifecycle == CLOSED]

    candidates = []
    undated_open = 0
    for it in open_intents:
        age = _days_between(it.last_activity, now)          # days_silent = time since last activity
        if age is None:
            undated_open += 1
            continue
        if age - it.reasonable_timeframe_days > 0:
            candidates.append({
                "id": it.id, "description": it.description, "source": it.source, "kind": it.kind,
                "parent": it.source.split("/", 1)[0],
                "last_activity": it.last_activity, "days_silent": age,
                "timeframe_days": it.reasonable_timeframe_days,
                "overdue_days": age - it.reasonable_timeframe_days,
                "executable": bool(it.executable),
                "action": it.action, "anticipated_result": it.anticipated_result,
            })
    # parent-liveness (v2): a parent whose MOST-recently-touched stale item is itself older than
    # dormant_days has gone quiet as a whole → its candidates are a dormant CLUSTER (offer close-together),
    # not individual resume targets. (Paper C: every item ~135d silent → dormant; D/E/F ~67d → live.)
    parent_min_silent: dict = {}
    for c in candidates:
        parent_min_silent[c["parent"]] = min(parent_min_silent.get(c["parent"], 10**9), c["days_silent"])
    for c in candidates:
        c["parent_dormant"] = parent_min_silent[c["parent"]] >= dormant_days
    candidates.sort(key=lambda c: (-c["days_silent"], c["source"]))   # v2: rank by silence, not overdue

    by_valence = {"+1": 0, "0": 0, "-1": 0, "none": 0}
    for it in closed:
        by_valence[{1: "+1", 0: "0", -1: "-1"}.get(it.valence, "none")] += 1
    by_kind: dict = {}
    for it in intents:
        by_kind[it.kind] = by_kind.get(it.kind, 0) + 1

    return {
        "counts": {
            "total": len(intents), "open": len(open_intents), "closed": len(closed),
            "stale_candidates": len(candidates), "open_undated": undated_open,
            "executable_candidates": sum(1 for c in candidates if c["executable"]),
            "live_parent_candidates": sum(1 for c in candidates if c["executable"] and not c["parent_dormant"]),
            "dormant_parents": sorted({c["parent"] for c in candidates if c["parent_dormant"]}),
            "closed_by_valence": by_valence, "by_kind": by_kind,
        },
        "candidates": candidates,
    }


def _normalize_labels(raw) -> dict:
    """Accept any of: flat ``{id: "worth"}`` · worksheet array ``[{"id":.., "label":..}]`` ·
    object-of-objects ``{id: {"label": ..}}`` → a flat ``{id: label_str}`` map (blank labels stay blank)."""
    out: dict = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("id"):
                out[str(item["id"])] = str(item.get("label", "")).strip()
    elif isinstance(raw, dict):
        for k, v in raw.items():
            out[str(k)] = (str(v.get("label", "")) if isinstance(v, dict) else str(v)).strip()
    return out


def _precision(cands: list, labels: dict) -> tuple:
    """(precision, worth, not_worth, n_labeled) over the labeled candidates within ``cands``."""
    ids = {c["id"] for c in cands}
    worth = not_worth = 0
    for iid, lab in labels.items():
        if iid not in ids:
            continue
        l = lab.lower()
        if l in _WORTH:
            worth += 1
        elif l in _NOT_WORTH:
            not_worth += 1
    n = worth + not_worth
    return (round(worth / n, 3) if n else None, worth, not_worth, n)


def verdict(candidates: list, labels) -> dict:
    labels = _normalize_labels(labels)
    n_cand = len(candidates)
    if not labels:
        return {"metric": "worth_resuming_precision", "value": None, "signal": None,
                "n_candidates": n_cand, "n_labeled": 0,
                "note": "label the candidates (worth / mislabeled / abandoned) then re-run with --labels"}
    p_raw, worth, not_worth, n_labeled = _precision(candidates, labels)              # pre-registered metric
    p_exec = _precision([c for c in candidates if c["executable"]], labels)[0]        # + harvest filter (v2)
    p_live = _precision([c for c in candidates                                        # + parent-liveness (v2)
                         if c["executable"] and not c["parent_dormant"]], labels)[0]
    powered = n_labeled >= MIN_LABELED
    signal = bool(powered and p_raw is not None and p_raw >= PRECISION_BAR)
    if not powered:
        note = f"UNDERPOWERED — {n_labeled} labeled < {MIN_LABELED}; label more candidates"
    elif signal:
        note = f"BUILD — raw {p_raw} ≥ {PRECISION_BAR} on {n_labeled} labeled → build the persistent intent ledger"
    else:
        note = f"PARK — raw {p_raw} < {PRECISION_BAR} on {n_labeled} labeled → harvest too noisy to resurrect from"
    return {"metric": "worth_resuming_precision", "value": p_raw, "signal": signal,
            "n_candidates": n_cand, "n_labeled": n_labeled, "worth": worth, "not_worth": not_worth,
            "precision_executable": p_exec, "precision_live_parent": p_live, "note": note}


def run(vault, now_iso: str, timeframe: "dict | None" = None, labels=None,
        dormant_days: int = DORMANT_DAYS, intents=None) -> dict:
    """``intents=None`` harvests the vault; a caller that already harvested (the S2 journal snapshots the
    same scan) passes its list in so one circadian tick costs ONE harvest, not two (D1b hygiene)."""
    now = _parse_date(now_iso)
    if now is None:
        raise SystemExit(f"--now must be an ISO date (got {now_iso!r})")
    tf = dict(TIMEFRAME_DAYS)
    if timeframe:
        tf.update(timeframe)
    if intents is None:
        intents = harvest(vault)
    a = analyze(intents, now, tf, dormant_days)
    return {
        "vault": str(vault), "repo": Path(vault).name, "now": now.isoformat(),
        "timeframe_days": tf, "dormant_days": dormant_days,
        "counts": a["counts"], "candidates": a["candidates"],
        "verdict": verdict(a["candidates"], labels),
        "thresholds": {"PRECISION_BAR": PRECISION_BAR, "MIN_LABELED": MIN_LABELED, "DORMANT_DAYS": dormant_days},
    }


# ------------------------------------------------------------------ text output
def _fmt(res: dict, top: int = 25) -> str:
    c = res["counts"]
    bv = c["closed_by_valence"]
    L = ["TAO RESURRECTION GAUGE  (intent register — OPEN∧stale = crack-fallers)",
         f"  repo={res['repo']}  now={res['now']}", "",
         f"  intents: total={c['total']}  open={c['open']}  closed={c['closed']}  "
         f"(open_undated={c['open_undated']})",
         f"  closed valence: +1={bv['+1']}  0={bv['0']}  -1={bv['-1']}  (none={bv['none']})",
         f"  by kind: " + ", ".join(f"{k}={v}" for k, v in sorted(c['by_kind'].items())),
         f"  STALE candidates: {c['stale_candidates']}  "
         f"(executable={c['executable_candidates']}  live-parent={c['live_parent_candidates']})",
         f"  dormant parents (whole-paper silent ≥ {res['dormant_days']}d): "
         + (", ".join(c['dormant_parents']) or "none"), ""]
    if res["candidates"]:
        L.append(f"  top {min(top, len(res['candidates']))} by days-silent:")
        for cand in res["candidates"][:top]:
            desc = cand["description"][:84] + ("…" if len(cand["description"]) > 84 else "")
            flag = "DORMANT" if cand["parent_dormant"] else ("non-exec" if not cand["executable"] else "live")
            L.append(f"    [{cand['days_silent']:>4}d silent | {flag:<8} | {cand['last_activity']}] {desc}")
            L.append(f"        id={cand['id']}  src={cand['source']}")
    v = res["verdict"]
    L += ["", "VERDICT:",
          f"  metric={v['metric']}  value={v['value']}  signal={v['signal']}  "
          f"candidates={v['n_candidates']}  labeled={v['n_labeled']}",
          f"  precision layers: raw={v['value']}  +harvest-filter={v.get('precision_executable')}  "
          f"+parent-liveness={v.get('precision_live_parent')}",
          f"  => {v['note']}",
          "  NOTE: harvest is of DECLARED intents only (checkboxes + ledgers), bounded to targeted file",
          "        patterns — recall is a floor, not complete. Precision needs PI labels. Live = demonstration."]
    return "\n".join(L) + "\n"


def format_candidates(res: dict, top: int = 25) -> str:
    """Consumer view (for the MCP Governor tool): counts + dormant-parent clusters + the top-N crack-fallers
    by days-silent — WITHOUT the dev-facing precision/verdict/BUILD block (that is the labeling-workflow
    output, `_fmt`). What a PI asking 'what fell through the cracks?' actually wants back."""
    c = res["counts"]
    L = [f"Resurrection — stale OPEN intents in [{res['repo']}] (now {res['now']}):",
         f"  {c['stale_candidates']} crack-fallers  (executable={c['executable_candidates']}  "
         f"live-parent={c['live_parent_candidates']})"]
    if c["dormant_parents"]:
        L.append(f"  dormant clusters (whole-parent silent ≥ {res['dormant_days']}d — consider "
                 f"close-together): " + ", ".join(c["dormant_parents"]))
    if not res["candidates"]:
        L.append("  (none open past its reasonable timeframe)")
        return "\n".join(L) + "\n"
    L.append(f"  top {min(top, len(res['candidates']))} by days-silent:")
    for cand in res["candidates"][:top]:
        desc = cand["description"][:96] + ("…" if len(cand["description"]) > 96 else "")
        flag = "DORMANT" if cand["parent_dormant"] else ("non-exec" if not cand["executable"] else "live")
        L.append(f"    [{cand['days_silent']:>4}d | {flag:<8}] {desc}  ({cand['source']})")
    L.append("  NOTE: DECLARED intents only (checkboxes + ledgers) — recall is a floor. Read-only; "
             "resume/close is yours. Live = demonstration.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TAO Resurrection Gauge — precision @ worth-resuming (Cerebral S0)")
    ap.add_argument("--vault", required=True, help="path to the research vault (an Obsidian/markdown repo)")
    ap.add_argument("--now", required=True, help="reference date, ISO (e.g. 2026-07-01) — deterministic")
    ap.add_argument("--timeframe", action="append", default=[], metavar="KIND=DAYS",
                    help="override a kind's reasonable-timeframe (repeatable, e.g. issue=45)")
    ap.add_argument("--labels", default=None, help="JSON labels (flat map or worksheet array) → precision")
    ap.add_argument("--emit-template", default=None, metavar="PATH",
                    help="write an editable labels worksheet (the stale candidates) to PATH and exit")
    ap.add_argument("--dormant-days", type=int, default=DORMANT_DAYS,
                    help=f"a parent is a dormant cluster if its freshest stale item is older than this "
                         f"(default {DORMANT_DAYS})")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    tf: dict = {}
    for kv in args.timeframe:
        try:
            k, val = kv.split("=", 1)
            tf[k.strip()] = int(val)
        except Exception:
            ap.error(f"--timeframe expects KIND=DAYS (got {kv!r})")
    labels = None
    if args.labels:
        try:
            labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
        except Exception as e:
            ap.error(f"could not read --labels {args.labels!r}: {e}")

    res = run(args.vault, args.now, tf or None, labels, args.dormant_days)
    if args.emit_template:
        worksheet = [{"id": c["id"], "kind": c["kind"], "overdue_days": c["overdue_days"],
                      "last_activity": c["last_activity"], "source": c["source"],
                      "description": c["description"], "label": ""} for c in res["candidates"]]
        Path(args.emit_template).write_text(
            json.dumps(worksheet, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {len(worksheet)} candidates to {args.emit_template}\n"
              f"fill each \"label\": worth | mislabeled | abandoned, then re-run with "
              f"--labels {args.emit_template}")
        return 0
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
