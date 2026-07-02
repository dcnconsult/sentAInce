"""Persistent intent journal + transition detection — Cerebral Substrate S2 (the Governor gets a memory).

S1's Governor was **stateless**: every scrape re-walked the vault and returned "here are the 46 stale
OPEN intents." Useful, but it cannot say *what changed since last time* — and "3 items JUST fell through
the cracks / Paper C JUST went dormant / issue X was reopened" is the actionable, anti-nag signal. S2 adds
the missing state: an append-only **hash-chained JSONL journal** of circadian intent snapshots, and a
**diff** that emits transitions between consecutive scans.

Design laws it keeps (Cerebral guardrails):
  · **Proposer / archivist, never a live-τ source.** The journal is a *record* — it never deposits τ,
    writes σ, or mutates a colony/vault/config. Read-only w.r.t. the organism (ADR-001 untouched).
  · **JSONL journal = the truth, hash-chained** (the ADR-009 chain, reused byte-for-byte from
    ``exocortex.integrity`` — ONE chain implementation, never a second drifting copy). A SQLite/Postgres
    *view* is a later slice; the journal is always rebuildable by replay, never a 2nd source of truth.
  · **No drift in "stale"/"dormant".** The per-intent staleness + parent-dormancy verdict is taken verbatim
    from ``resurrection_gauge.run()`` (the SAME code S0/S1 gauged), not recomputed here.
  · **−1 informs, never forbids** (ADR-004 echo). A REOPENED transition is *reported*, never a re-learning
    scar; closure valence is read off the record, never judged.

Deterministic (``--now`` required, no wall clock), pure-stdlib + the two cerebral/exocortex reads, fail-open.

  python -m cerebral.journal --vault DIR --now 2026-07-01 --journal PATH            # scan → transitions
  python -m cerebral.journal --vault DIR --now 2026-07-02 --journal PATH            # next day → the diff
  python -m cerebral.journal --journal PATH --verify                               # verify the hash-chain
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cerebral.intents import OPEN, harvest
from cerebral.gauge.resurrection_gauge import run as _gauge_run, _days_between, _parse_date
from exocortex.integrity import chain_hash, verify_audit, GENESIS, append_lock   # the ONE ADR-009 chain

_DESC_CAP = 72                       # snapshot description cap — self-describing but lean at ~800 intents/scan
_VAL_CODE = {1: "+1", 0: "0", -1: "-1", None: ""}


# ------------------------------------------------------------------ snapshot (the per-intent state at a scan)
def snapshot(vault, now_iso: str) -> dict:
    """{id: compact-state} for EVERY declared intent at ``now``, plus counts. Staleness + parent-dormancy are
    taken verbatim from the resurrection gauge (no drift); lifecycle/valence/days-silent from the harvest.
    Compact so a daily journal stays lean; self-describing (``d``/``s``/``k``) so a DISAPPEARED id is still
    renderable and the journal replays to a readable view."""
    now = _parse_date(now_iso)
    if now is None:
        raise SystemExit(f"--now must be an ISO date (got {now_iso!r})")
    intents = harvest(vault)                                    # ONE harvest per scan (D1b: was harvested twice —
    gauge = _gauge_run(vault, now_iso, intents=intents)         # once here, once inside the gauge)
    stale_ids = {c["id"]: c for c in gauge["candidates"]}       # id -> candidate (has days_silent, parent_dormant)
    states: dict = {}
    for it in intents:
        cand = stale_ids.get(it.id)
        ds = cand["days_silent"] if cand else _days_between(it.last_activity, now)
        states[it.id] = {
            "lc": "O" if it.lifecycle == OPEN else "C",
            "v": _VAL_CODE.get(it.valence, ""),
            "ds": ds,
            "st": 1 if cand else 0,                             # stale (OPEN past timeframe) per the gauge
            "pd": 1 if (cand and cand["parent_dormant"]) else 0,
            "d": it.description[:_DESC_CAP],
            "s": it.source,
            "k": it.kind,
            "p": (cand["parent"] if cand else it.source.split("/", 1)[0]),
        }
    return {"now": now.isoformat(), "repo": gauge["repo"], "states": states,
            "counts": gauge["counts"]}


# ------------------------------------------------------------------ diff (the transitions between two scans)
def diff(prev: "dict | None", cur: dict) -> list:
    """Transitions from the ``prev`` snapshot's state-map to ``cur``'s. First scan (prev None/empty) → every
    intent is NEW (bootstrap; no stale/dormant transitions fire until there is a baseline to cross)."""
    pstates = (prev or {}).get("states", {}) if prev else {}
    cstates = cur["states"]
    out: list = []

    def rec(t, cid, st):
        return {"type": t, "id": cid, "description": st.get("d", ""), "source": st.get("s", ""),
                "kind": st.get("k", ""), "days_silent": st.get("ds"), "valence": st.get("v", ""),
                "parent": st.get("p", "")}

    newly_dormant_parents: set = set()
    for cid, st in cstates.items():
        prev_st = pstates.get(cid)
        if prev_st is None:
            out.append({**rec("NEW", cid, st), "stale": bool(st.get("st"))})
            continue
        if prev_st.get("lc") == "C" and st.get("lc") == "O":
            out.append(rec("REOPENED", cid, st))                       # ADR-004 echo — report, never re-scar
        elif prev_st.get("lc") == "O" and st.get("lc") == "C":
            out.append(rec("CLOSED_NOW", cid, st))                     # resolved; valence read off the record
        elif prev_st.get("lc") == "O" and st.get("lc") == "O":
            if not prev_st.get("st") and st.get("st"):
                out.append(rec("NEWLY_STALE", cid, st))                # JUST crossed its timeframe
            if not prev_st.get("pd") and st.get("pd"):
                newly_dormant_parents.add(st.get("p", ""))             # parent-level → deduped below
    # a parent that just crossed dormancy → ONE cluster transition (anti-nag: not one nag per item)
    for parent in sorted(p for p in newly_dormant_parents if p):
        members = [cid for cid, st in cstates.items() if st.get("p") == parent and st.get("st")]
        out.append({"type": "NEWLY_DORMANT", "parent": parent, "members": len(members),
                    "description": f"whole cluster [{parent}] went dormant", "kind": "cluster"})
    for pid, st in pstates.items():                                    # ids gone from the vault this scan
        if pid not in cstates and st.get("lc") == "O":
            out.append({**rec("DISAPPEARED", pid, st),
                        "note": "OPEN id absent this scan — resolved OR edited/moved (ambiguous; not judged)"})
    _order = {"NEWLY_STALE": 0, "NEWLY_DORMANT": 1, "REOPENED": 2, "CLOSED_NOW": 3, "NEW": 4, "DISAPPEARED": 5}
    out.sort(key=lambda t: (_order.get(t["type"], 9), -(t.get("days_silent") or 0), t.get("source", "")))
    return out


# ------------------------------------------------------------------ the hash-chained journal
def _read_records(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def last_snapshot(path) -> "dict | None":
    """The most-recent scan's snapshot (for diffing), or None if the journal is empty/absent."""
    recs = _read_records(path)
    return recs[-1]["snapshot"] if recs else None


def _tail_hash(path) -> str:
    """The chain head = the last record's ``hash`` (or GENESIS). NOTE: we do NOT reuse
    ``integrity.tail_hash`` here — it reads only a 16 KB file tail (fine for small flat audit rows), but a
    journal record embeds a full ~800-intent snapshot (one line ≫ 16 KB), so the windowed read would land
    mid-line and fall back to GENESIS, silently breaking the chain link. A full read is correct at journal
    record-counts (one per circadian scan). ``verify_audit`` already reads full lines, so it stays reusable."""
    recs = _read_records(path)
    return recs[-1].get("hash") or GENESIS if recs else GENESIS


def record_scan(vault, now_iso: str, journal_path) -> dict:
    """Harvest → snapshot → diff against the last journaled scan → append a NEW hash-chained record → return
    the transitions + counts. The one stateful entry point. Appends only its own journal file (a record)."""
    cur = snapshot(vault, now_iso)
    prev = last_snapshot(journal_path)
    transitions = diff(prev, cur)
    record = {"now": cur["now"], "repo": cur["repo"], "counts": cur["counts"],
              "n_transitions": len(transitions), "transitions": transitions, "snapshot": cur}
    try:
        Path(journal_path).parent.mkdir(parents=True, exist_ok=True)
        # read-tail → hash → append under the same advisory lock the exocortex audit uses (D7: an
        # unlocked window lets two concurrent writers link onto the same tail and fork the chain)
        with append_lock(journal_path):
            prev_hash = _tail_hash(journal_path)            # ADR-009 chain: link onto the tail (full-read)
            record["prev"] = prev_hash
            record["hash"] = chain_hash(record, prev_hash)
            with open(journal_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        pass                                               # archivist must never crash the caller
    return {"repo": cur["repo"], "now": cur["now"], "counts": cur["counts"],
            "transitions": transitions, "n_transitions": len(transitions),
            "first_scan": prev is None}


# ------------------------------------------------------------------ consumer view (Governor)
def format_transitions(res: dict, top: int = 25) -> str:
    """What a PI asking 'what changed?' wants: the deltas since last scan, most-actionable first."""
    ts = res["transitions"]
    L = [f"Intent journal — changes in [{res['repo']}] as of {res['now']}"
         + ("  (first scan — establishing the baseline)" if res["first_scan"] else "") + ":"]
    if not ts:
        L.append("  (no transitions since the last scan — the register is steady)")
        return "\n".join(L) + "\n"
    from collections import Counter
    tally = Counter(t["type"] for t in ts)
    L.append("  " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    for t in ts[:top]:
        if t["type"] == "NEWLY_DORMANT":
            L.append(f"    [NEWLY_DORMANT] cluster [{t['parent']}] went quiet ({t['members']} stale items — "
                     f"consider close-together)")
        else:
            ds = t.get("days_silent")
            dss = f"{ds}d silent" if ds is not None else "—"
            desc = (t.get("description") or "")[:88]
            L.append(f"    [{t['type']:<13}] {dss:<10} {desc}  ({t.get('source', '')})")
    if len(ts) > top:
        L.append(f"    … +{len(ts) - top} more")
    L.append("  READ-ONLY: the journal records; resume/close is yours. −1/reopened INFORMS, never forbids.")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cerebral S2 — persistent intent journal + transition detection")
    ap.add_argument("--vault", help="path to the research vault (required unless --verify)")
    ap.add_argument("--now", help="reference date ISO (e.g. 2026-07-01) — deterministic; required to scan")
    ap.add_argument("--journal", required=True, help="path to the hash-chained JSONL journal (append-only)")
    ap.add_argument("--verify", action="store_true", help="verify the journal's hash-chain and exit")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.verify:
        v = verify_audit(args.journal)
        print(json.dumps(v, indent=2) if args.json else f"[journal] chain verify: {v}")
        return 0 if v.get("ok") else 1
    if not args.vault or not args.now:
        ap.error("--vault and --now are required to scan (or pass --verify)")
    res = record_scan(args.vault, args.now, args.journal)
    print(json.dumps(res, indent=2) if args.json else format_transitions(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
