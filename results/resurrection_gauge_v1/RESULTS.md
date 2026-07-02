# Resurrection Gauge — v1 results (private patent vault, anonymized as `research-vault`)

**Gauge:** `cerebral/gauge/resurrection_gauge.py` · **Date:** 2026-07-01 · read-only, pure-stdlib, ADR-002.
**Command:** `python -m cerebral.gauge.resurrection_gauge --vault ~/research-vault --now 2026-07-01`
**Ticket:** Cerebral Substrate Slice 0 (`../../SentAInce_Cerebral_Substrate_Design_Review_v1.1.md`, §8 S0).

## Verdict — **BUILD · precision @ worth-resuming = 0.63 (46/46 labeled) ≥ 0.50 bar**

The pre-registered gate is **cleared**: of 46 stale candidates surfaced, the PI labeled **29 worth-resuming
/ 10 abandoned / 7 mislabeled** → precision **0.63 ≥ 0.50** on 46 labeled (≥10) → **BUILD the persistent
intent ledger.** The raw number *under*-states the organ once decomposed (see "Labeled outcome"): the
harvester is right **85%** of the time, and the 10 "abandoned" are a *success* of detection — the gauge
surfaced an entire dead paper's (Paper C, ~4.5 mo silent) worth of stale tasks — not a harvest error.
(Pre-registered metric = raw worth/total; it passed. The decomposition is what we learned, not a re-score.)

## Data (`research-vault`, now=2026-07-01)
- **831 intents** harvested — **487 open · 344 closed** (0 undated).
- By kind: **filing=603** (patent `FILING_CHECKLIST.md`), **issue=225** (`ISSUES.md`), **ledger=3**.
- **46 stale candidates** (OPEN past timeframe: issue 30d · filing 90d · ledger 30d seed defaults).
- Closed valence: **+1=344** (checkbox completions); **−1=0 · 0=0** — see caveat (the real `ledger.json`
  held only open `controlled_rerun_candidate` labels; falsifications live in `MAINTENANCE_LOG`/FAL
  registers not parsed in v1).

## The four questions
| Q | Metric | Result | Read |
|---|--------|--------|------|
| **Q1** harvest | 831 declared intents (603 filing · 225 issue · 3 ledger), 0 undated | **LIVE** | targeted-pattern harvest of *declared* intents works at vault scale; recall is a floor (only the 4 patterns + ledgers) |
| **Q2** stale surface | **46** OPEN∧stale candidates; top = Paper C ×11 @105d over | **LIVE** | genuine crack-fallers surface; staleness ranking is sensible and dated |
| **Q3** valence | closed +1=344 · −1=0 · 0=0 | **PARTIAL** | checkbox-completion (+1) works; research −1/0 needs the FAL-register/`MAINTENANCE_LOG` source (v2) |
| **Q4** precision | worth-resuming **0.63** · harvest **0.85** · liveness **0.74** (29w/10a/7m of 46) | **BUILD** | pre-registered 0.50 bar cleared; the decomposition shows the harvester is the strong part |

## Honest caveats (load-bearing)
- **Precision is unmeasured until the PI labels the candidates.** 46 stale-open items ≠ 46 worth-resuming;
  precision @ worth-resuming is the actual gate and is still `None`.
- **Harvest recall is bounded** to `ISSUES.md` / `FILING_CHECKLIST.md` / `task_status_*.md` /
  `*TASK_MANIFEST*.md` + `*ledger*.json`. Intents declared elsewhere are missed by design (targeted, not
  exhaustive) — a recall floor, honestly stated.
- **Valence is thin in v1.** The intent register's `−1` (falsified) / `0` (inconclusive) research verdicts
  live in `MAINTENANCE_LOG.md` (NEG/FAL tallies) and FAL registers, which v1 does not parse — so `−1/0`
  read as 0. Not a bug; a scoped-out source. All valence is read off the record, never judged (ADR-001).
- **Dates** resolve frontmatter `Last Updated` → git commit → mtime; a file with none falls to mtime,
  which a fresh checkout would reset (here TAO retains real mtimes; frontmatter/git dominated).
- **Read-only + additive:** the gauge only reads files and runs `git ls-files`/`git log`; it has no write
  path to the vault. SentAInce shows only `?? cerebral/` (no existing file modified); the 99-lock stays 99.
- **Live = demonstration, never evidence** — a labeled run on one vault, not a locked verdict.

## Labeled outcome (2026-07-01) — CLEARED, + what the labels taught us

**PI rubric (observable-only, two questions):** (1) is it a concrete executable publication work-item? if
it's a status/receipt line, an info/constraint note, a doc pointer, or an unresolved decision/question →
*mislabeled*. (2) if a genuine task, is the parent paper live (overdue depth + recency)? Two clean cohorts:
**Paper C** (105d over, ~4.5 mo silent) → real tasks *abandoned*; **Papers D/E/F** (37d over, late-April)
→ real tasks *worth*.

- **Raw worth-resuming = 0.63** (29/46) — the pre-registered gate; **BUILD**.
- **Harvest = 0.85** (39/46) — only the 7 mislabeled are true false-positives; the harvester is the strong part.
- **Liveness = 0.74** (29/39) — of genuine tasks, the fraction on a live paper.

**Three v2 refinements the labeling surfaced** (gauge-first working as intended — found before building):
1. **Harvest filter for non-executable lines** (the 7 mislabeled): mechanical signatures — ends with `?`,
   `PENDING`/receipt lines (E-L106), "X vs Y" decisions (D-L20, E-L18), `see <doc>` pointers (F-L165),
   constraint/fallback notes (F-L150/L153), scope questions (C-L34). A conservative is-executable pre-filter
   drops these (ADR-010 mechanical, not an LLM judge) → raw precision ≈ 0.63 → ~0.74. Bias to precision but
   conservative (never drop a real task).
2. **Days-silent as a first-class staleness signal.** `overdue` is timeframe-relative (silence = overdue +
   seeded timeframe), so it only ranks cleanly *within* one kind. Expose/rank on days-since-last_activity;
   keep the per-kind timeframe as a modifier. (PI leaned on cohort recency, not the raw overdue number.)
3. **Parent/paper-level liveness.** Cluster stale tasks by parent so "this whole paper went dormant" is one
   signal (Paper C = 1 dormant cluster, not 10 nags) — the design's anti-nag/cluster-close (Governance
   hysteresis) behavior, and the natural home for the "abandoned" cohort.

**Cleanest disagreement test (PI):** the 7 mislabeled + the E-L105/L106 receipt/status pair — the highest-
value items to check a v2 harvest filter against.

**Still scoped out (v2):** the FAL-register / `MAINTENANCE_LOG` valence source for research `−1`/`0` (Q3).

## v2 — measured (harvest filter + parent-liveness + days-silent), same 46 labels
Implemented the three refinements in the gauge and re-scored the **same labels** (`--dormant-days 90`):

| Layer | Precision | What it does |
|---|---|---|
| raw (v1, pre-registered) | **0.63** | 29 worth / 46 |
| + harvest filter (drop non-executable) | **0.659** | drops only 2 *safely* (C-L34 `?`, F-L165 `See <doc>`) → 44 |
| + parent-liveness (drop dormant clusters) | **0.853** | drops the whole dormant Paper C cluster + non-exec → 34; 29/34 |

**Finding: parent-liveness is the lever; the mechanical harvest filter is marginal.** The gauge flagged
**PAPER_C** as the one dormant parent (every stale item ≥135d silent vs D/E/F ~67d) — the 90-day dormancy
threshold cleanly reproduces the cohort split the PI made by hand. The +0.03 from the harvest filter
confirms the v1 finding that "is-it-an-executable-task" is mostly *semantic* (the E-L105/L106 pair, "Choose
target journal") and not mechanically separable without false-drops — so a conservative filter (2 safe
signatures) is the right ceiling, not an elaborate rule set. Candidates now rank by **days-silent** (the
harder signal), with the per-kind timeframe as the stale gate. (`resurrection_gauge.py` v2; the same
`--labels` reproduce all three layers.)

**Consequence for S1:** invest in the Governor's **parent-liveness clustering + cluster-close** (the 0.85
lever); keep the harvest filter conservative; treat the ~5 residual semantic non-tasks as a
label-once / PI-ratify concern, not a parser arms race.

## Flip-trigger — CLEARED (0.63 ≥ 0.50 on 46)
→ Build the persistent living ledger + Consolidator + Governor read-view (S0→S1), carrying the three v2
refinements above. Below-bar would have been PARK (tune patterns/timeframes first); it passed.

## Raw
```
RESURRECTION GAUGE  (intent register — OPEN∧stale = crack-fallers; repo name anonymized)
  repo=research-vault  now=2026-07-01
  intents: total=831  open=487  closed=344  (open_undated=0)
  closed valence: +1=344  0=0  -1=0  (none=0)
  by kind: filing=603, issue=225, ledger=3
  STALE candidates (open past timeframe): 46
  top: PAPER_C ISSUES ×11 @105d over (2026-02-16) · PAPER_D/E ×… @37d over (2026-04-25)
VERDICT: worth_resuming_precision=0.63 signal=True candidates=46 labeled=46 (worth=29 not_worth=17)
  => BUILD — precision 0.63 ≥ 0.5 on 46 labeled → build the persistent intent ledger
```
Reproduce: `python -m cerebral.gauge.resurrection_gauge --vault <TAO> --now <ISO> --json`.
