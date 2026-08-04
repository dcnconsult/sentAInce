# Declarative multi-note tail v1 — the number that gates the Hippocampus bridge

**Run date:** 2026-07-30 · **Repo:** SentAInce (its own live store) · **Read-only.**

Reproduce:

```bash
python -m exocortex.gauge.credit_funnel_gauge --state-dir .claude/exocortex
```

## Why this exists

The Hippocampus bridge (Ticket 2) is DORMANT, and `CLAIMS.md` justified that dormancy **thermodynamically**:
the share of injected segments crediting **≥2 notes** — the tail a bridge needs, since a shortcut requires at
least two credited notes in one segment — was measured at **8.9%** and described as having *thinned* from an
earlier 18%. That is the number this project has quoted since.

It is now stale. This bank records the corrected measurement, the regime history behind it, and the control
that rules out the obvious confound.

## Headline

| | segments | ≥2 notes | share |
|---|---|---|---|
| **Binding CLAIMS figure** (earlier soak) | 79 | 7 | **8.9%** |
| **This run** (2026-07-30) | **2,383** | **631** | **26.5%** |

Notes-credited histogram (this run):

```
{0: 1395, 1: 357, 2: 246, 3: 113, 4: 82, 5: 62, 6: 46, 7: 32, 8: 25, 9: 15, 10: 4, 11: 2, 12: 2, 13: 1, 16: 1}
```

Denominator = **injected** segments (a segment that was never injected cannot credit a note). Credit is at
the shipped `min_overlap=2`, gated on `exit 0`, and `wiki_used` counts notes the model actually **used** by
content echo — never merely offered.

## The 8.9% was not wrong — it was a real regime

Daily rate over the store's whole life (days with ≥15 injected segments):

| day | segs | ≥2 | share |
|---|---|---|---|
| 2026-06-28 | 84 | 8 | 9.5% |
| 2026-06-29 | 90 | 4 | 4.4% |
| 2026-06-30 | 152 | 14 | 9.2% |
| 2026-07-01 | 107 | 19 | 17.8% |
| 2026-07-02 | 227 | 10 | 4.4% |
| 2026-07-03 | 135 | 0 | 0.0% |
| 2026-07-04 | 86 | 12 | 14.0% |
| 2026-07-05 | 136 | 10 | 7.4% |
| 2026-07-08 | 164 | 16 | 9.8% |
| **2026-07-09** | 74 | 20 | **27.0%** |
| 2026-07-10 | 63 | 30 | 47.6% |
| 2026-07-16 | 178 | 87 | 48.9% |
| 2026-07-17 | 151 | 85 | 56.3% |
| 2026-07-20 | 80 | 29 | 36.2% |
| 2026-07-22 | 253 | 136 | 53.8% |
| 2026-07-23 | 39 | 23 | 59.0% |
| 2026-07-25 | 205 | 95 | 46.3% |
| 2026-07-28 | 61 | 13 | 21.3% |
| 2026-07-29 | 85 | 14 | 16.5% |

Through 2026-07-08 the rate sits around **0–18%**, averaging ~9%: **the 8.9% figure was correct for the
window it was measured in.** From 2026-07-09 it steps to **27–59%**. The correction is not "the old
measurement was a mistake", it is "the corpus moved and nobody re-measured."

## Control — it is NOT the 0.1.10 proposer fix

The obvious confound is that v0.1.10's IDF-ranked proposer and explore rotation (shipped 2026-07-25) simply
offer better notes, so more get echoed. Splitting on that ship date:

| era | segments | ≥2 notes | share |
|---|---|---|---|
| before 0.1.10 | 2,040 | 507 | **24.9%** |
| after 0.1.10 | 353 | 122 | **34.6%** |

The tail was **already fat before the proposer changed**. The fix added on top of an existing regime shift;
it did not cause it. What caused the 2026-07-09 step is **not established here** and is left open.

## What this does and does not license

- It **falsifies the stated reason for bridge dormancy.** "The tail is too thin to bother" is no longer
  supported by the data.
- It does **not** license flipping the bridge. The second condition — an **on-body bridge-validity gauge** —
  does not exist, and `bridge_gauge` states that executable validity of a direct `A→D` is *not offline
  decidable*: only the body can settle whether the skipped steps mattered. Its topological path counts are
  self-flagged as inflated by graph cycles.
- The bridge therefore stays **DORMANT**, with its justification restated: not *"the prize is too small"*
  but *"the validity instrument is unbuilt."*

## Read this number with its date

Corpus, vault, and credited set are all live, and the daily table above ranges 0%→59%. A bare percentage
from this gate is meaningless. Quote it as **26.5% of 2,383 injected segments, 2026-07-30**, or re-run the
gauge. The two most recent days (21.3%, 16.5%) are lower than the mid-July peak, so the tail is not a
constant and may be trending; a later run may legitimately differ.
