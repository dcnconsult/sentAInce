# Cerebral S2 — persistent intent journal + transition detection — v1 build record

**Module:** `cerebral/journal.py` (+ `cerebral/tests/test_journal.py`) · **Date:** 2026-07-01 · read-only
w.r.t. the organism, deterministic, hash-chained. **Ticket:** Cerebral Substrate S2 (the Governor gets a
memory), the persistence S1 deferred-with-reason. Not a gauge — a **build slice** implementing the already-
gauged-BUILD resurrection organ (`resurrection_gauge_v1` = 0.63→0.85).

## What it adds over stateless S1
S1's Governor re-walked the vault every scrape and returned "here are the 46 stale OPEN intents" — it could
not say *what changed*. S2 persists each circadian scan as a **hash-chained JSONL snapshot** and **diffs**
consecutive scans into transitions:

| Transition | Meaning | Why it matters |
|---|---|---|
| `NEWLY_STALE` | OPEN item just crossed its timeframe | "this just fell through the cracks" (the daily trickle) |
| `NEWLY_DORMANT` | a whole **parent/cluster** just went quiet (≥90d) | cluster-close, **deduped to one per parent** (anti-nag) |
| `REOPENED` | CLOSED → OPEN again | ADR-004 echo — reported, **never re-scarred** |
| `CLOSED_NOW` | OPEN → CLOSED | resolved; valence read off the record, never judged |
| `NEW` | first sight of an intent | bootstrap / freshly-declared |
| `DISAPPEARED` | an OPEN id is gone from the vault | resolved **OR** edited/moved — ambiguous, **flagged not judged** |

## Design laws kept
- **Proposer/archivist, never a live-τ source.** The journal is a *record* — no τ deposit, no σ, no colony/
  vault/config mutation. ADR-001 untouched; the organism is unchanged (additive `cerebral/` only).
- **One chain, not a second copy.** Reuses `exocortex.integrity.chain_hash` / `verify_audit` — the ADR-009
  epigenetic chain, byte-for-byte. Tamper-evident: editing any past record snaps the chain (tested).
- **No drift in "stale"/"dormant".** Per-intent staleness + parent-dormancy are taken verbatim from
  `resurrection_gauge.run()` (the SAME code S0/S1 gauged), never recomputed here.
- **Snapshot = truth; transitions = a sealed derived view.** The full per-intent snapshot is the
  rebuildable truth; the stored transitions are a convenience cache of "what the diff said that day"
  (recomputable from the snapshot chain), not a competing ledger. SQLite/Postgres view = a later slice.

## Live demonstration (private patent vault `research-vault`, deterministic `--now`)
- **Scan 1** `now=2026-06-24` → baseline, **831 NEW**, `first_scan=true`.
- **Scan 2** `now=2026-08-15` → **NEWLY_STALE=323, NEWLY_DORMANT=4** (a patent `FILING_CHECKLIST.md` batch
  crossing the 90-day filing timeframe; 4 parent clusters crossing dormancy). **Chain verify: intact.**
- The 323 is a **big-jump artifact** (52 days collapsed into one diff). At true daily cadence each scan
  surfaces only the few crossing *that* day — which is the whole point of the circadian/anti-nag design.
- Live = demonstration, never evidence.

## Two honest findings from the run
1. **`integrity.tail_hash` 16 KB-window bug (FIXED in-module).** That helper reads only the last 16 KB of a
   file (fine for small flat audit rows). A journal record embeds a full ~800-intent snapshot (one line
   ≈ 300–450 KB ≫ 16 KB), so the windowed read landed mid-line, failed to parse, returned GENESIS, and
   silently broke the chain link between scans. Fixed with a **full-read `_tail_hash`** in `journal.py`
   (record-count is small — one per scan); `verify_audit` already reads full lines, so it stays reused.
   *Not* changed in `exocortex.integrity` (no organism change) — the small-record assumption there is valid
   for the audit; only this large-record consumer needed the full read.
2. **Record size ≈ 300–450 KB/scan** (the snapshot's per-intent description dominates). Tolerable at
   circadian cadence (~130 MB/yr worst case) but the **#1 optimization for the SQLite-view slice** — drop
   repeated descriptions from the snapshot (keep id/source/state), or store deltas over a periodic full
   base. Deferred, not forgotten.

## Tests / gates
`cerebral/tests/test_journal.py` — 10 tests: snapshot coverage, first-scan-all-NEW, NEWLY_STALE,
CLOSED_NOW→REOPENED (id preserved across a checkbox toggle), NEWLY_DORMANT cluster dedup, DISAPPEARED,
steady-no-transitions, **chain tamper-evidence**, determinism, missing-journal safety. **cerebral suite
33/33; 99-lock stays 99; zero existing files modified.**

## Next (deferred, gauge-/design-gated)
The SQLite rebuildable view (Phase 2 store + the size fix); wiring `record_scan` behind the circadian
cadence (idle-detection) and exposing the transition surface via the Governor MCP tool; the utility register
(colony-prune observation) — the latter needs prune instrumentation (an organism change) and the FI_hat
NULL says its procedural prize is thin at flagship scale, so it stays parked.

## Reproduce
```
python -m cerebral.journal --vault <TAO> --now 2026-06-24 --journal J.jsonl     # baseline
python -m cerebral.journal --vault <TAO> --now 2026-08-15 --journal J.jsonl     # the diff
python -m cerebral.journal --journal J.jsonl --verify                          # chain intact
```
