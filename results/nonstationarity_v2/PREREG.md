# Pre-registration: non-stationarity re-gauge on go-forward stamps (R4 / rt-stale-1)

**Frozen:** 2026-10-26. It is committed before the stamp-age readout (§4 D2–D3) is written and before either
the gauge or the readout is run. **Kind:** experimental-design.
**Gauge:** `exocortex/gauge/nonstationarity_gauge.py`. The within-class excess is unchanged since v1; the
stamp-age readout is added after this freeze.

## 1. Question

F3 recency decay (`provenance.mode = recency`, 30-day half-life at readout) is built and ships DORMANT, so a
route that is never re-confirmed keeps splicing at full τ. Red-team `rt-stale-1` pins that a 400-day-old route
splices at full weight.

There is a second reason it matters, found 2026-10-26 in `colony.py`. τ decay is clocked by **successful
deposits** in a class, plus one pass per sleep. A class whose route has started failing, or a class gone
idle, barely forgets. Recency decay is the only **time-clocked** forgetting in the organism.

Does the evidence now justify flipping the shipped default to `recency`? The gate is the one the remediation
plan set (dossier 06 R4; ROADMAP §2b): within-class drift in **excess** of a permutation null, ≥ the bar, on
≥2 repos. v1 could not act on it because the provenance instrument did not yet exist (0% stamp coverage).

## 2. What has already been seen (disclosed before freezing)

- **v1** (`results/nonstationarity_v1/`, 2.6-day window, SentAInce only): within-class excess **0.20** (over
  `EXCESS_THRESHOLD` 0.10), and stamp coverage 0.0.
- **Today:** the R0 soak readout counted 119 edges in this repo stamped since 2026-09-16. Store-level τ is
  visible in the estate overlap probe and the R1a gauge run. **No excess drift, coverage figure or stamp age
  has been computed** on any repo since v1.

## 3. Repo set and evaluability (frozen)

- **Stores:** every `*/.claude/exocortex` under the estate's projects root, plus the research vault's state
  dir (labelled `research-vault`). *(Redaction note, 2026-10-26, after the freeze commit and before any run:
  a private path token was replaced with "the estate's projects root" so the file can pass the public
  denylist gate. Nothing else in the protocol changed.)*
- **Evaluable:** the gauge's `stationarity_by_class.classes_measured ≥ 3`. Classes below the gauge's own
  `_MIN_SPLIT` are skipped by the gauge.

## 4. Metrics

- **G (gated): `mean_excess_drift`** per store, from the unchanged `stationarity_by_class`. It is the
  consequence-weighted mean over classes of observed early→late verb-mix TV distance minus its shuffle null
  (200 shuffles, seed 0).
- **Descriptive only:**
  - **D1:** `edge_ts_coverage` (share of colony edges carrying a stamp).
  - **D2 stamp age:** at a fixed `--now`, the share of stamped τ-mass older than 30 days and older than
    90 days. The flip would weight these at ≤½ and ≤⅛ respectively.
  - **D3 dominant change:** the share of classes with ≥2 edges whose strongest edge changes when τ is
    weighted by `0.5^(age/30d)` (unstamped edges weight 1.0, as in `colony._recency_weight`). This is what
    the flip would visibly do to the splice.

## 5. Decision rule (frozen)

- **+1:** ≥2 evaluable stores have `G ≥ 0.10`, and they are a majority of the evaluable stores. Outcome:
  propose flipping the committed default to `recency`. **That flip is a separate PI decision** (ADR-003),
  and it flips `rt-stale-1`.
- **−1:** ≥2 stores are evaluable and none has `G ≥ 0.10`. Outcome: recency stays dormant, and
  `rt-stale-1` is re-scoped as by-design pending a different staleness signal.
- **0:** anything else, including fewer than 2 evaluable stores.

D1–D3 never change the disposition. They are reported so that a +1 says how much the flip would act. If
D2 shows little stamped τ-mass over 30 days old, the flip would do little today, and the result must say so.

## 6. What this cannot show

- Verb-mix drift is a proxy for route rot (v1 §"Gauge self-limit"). It shows the routing mix moves within a
  class. It does not show that down-weighting old routes helps an agent reach `exit 0`; efficacy stays
  unmeasured.
- The version-distance term (`full`) stays inert. Model stamps are reported (`model_coverage`), not gated.

## 7. Output

`results/nonstationarity_v2/RESULTS.md` plus an aggregate-only JSON (repo names and class labels only, no
command text).
