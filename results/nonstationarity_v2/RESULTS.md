# Non-stationarity gauge v2: the re-gauge on go-forward stamps (R4 / rt-stale-1)

> **Public labels (2026-10-28).** Private estate repositories appear as `repo-A` … `repo-H`. This repo,
> `lab`, `research-vault` and `cursor_testbed` keep their usual public labels. Only the names changed: every
> number is as run, the mapping is the same across this run's result files, and the frozen pre-registration is
> untouched.

**Run:** 2026-10-26, under the frozen protocol [`PREREG.md`](PREREG.md) (committed `d8eb399` before the
stamp-age readout existed). **Gauge:** `exocortex/gauge/nonstationarity_gauge.py`. The within-class excess is
unchanged since v1. The new `stamp_age` readout has controls in `exocortex/tests/test_nonstationarity_gauge.py`
(11 pass).

**Reference time:** `--now 1793059200` (2026-10-27 00:00 UTC). **Stores:** every estate state dir plus the
research vault (labelled `research-vault`; its audit runs through 2026-10-16). **Aggregates:**
[`results_2026-10-26.json`](results_2026-10-26.json).

## Gated metric: within-class excess drift (G)

A store is evaluable when the gauge measures at least 3 classes.

| Store | Classes measured | Within-class | Null | **Excess G** | Clears 0.10 |
|---|---|---|---|---|---|
| SentAInce | 105 | 0.494 | 0.274 | **0.219** | yes |
| research-vault | 104 | 0.379 | 0.206 | **0.173** | yes |
| lab | 56 | 0.579 | 0.377 | **0.202** | yes |
| repo-B | 35 | 0.361 | 0.223 | **0.138** | yes |
| repo-C | 15 | 0.497 | 0.277 | **0.221** | yes |
| repo-A | 10 | 0.481 | 0.184 | **0.297** | yes |
| repo-H | 10 | 0.508 | 0.303 | **0.204** | yes |
| repo-E | 10 | 0.148 | 0.087 | **0.061** | no |

Not evaluable: repo-F (2 classes), cursor_testbed (1), repo-D (0), repo-G (no data).

## Disposition (frozen rule, §5): **+1**

7 of the 8 evaluable stores clear the bar, a majority. So the prereg's outcome applies: **propose flipping the
committed default to `provenance.mode = recency`.** That flip is a separate PI decision (ADR-003). It is not
made here.

## What the flip would actually do (descriptive, §4 D1–D3)

| Store | Edge stamp coverage | Stamped τ > 30 d | Stamped τ > 90 d | Classes whose strongest edge changes |
|---|---|---|---|---|
| SentAInce | 0.993 | 0.184 | 0.049 | 0 / 17 |
| research-vault | 1.0 | 0.03 | 0.0 | 0 / 16 |
| lab | 1.0 | 0.847 | 0.635 | 2 / 97 (2.1%) |
| repo-B | 1.0 | 1.0 | 0.498 | 0 / 57 |
| repo-A | 1.0 | 1.0 | 0.0 | 0 / 18 |
| repo-C | 1.0 | 1.0 | 1.0 | 0 / 26 |
| repo-H | 0.901 | 1.0 | 0.0 | 0 / 19 |
| repo-E | 1.0 | 1.0 | 0.659 | 0 / 16 |

Aggregate edge stamp coverage is **0.993** and model-id coverage **0.977**, so the provenance instrument that
v1 found absent now exists.

**The honest size of the flip:**

1. **It acts mostly on idle stores.** On the two busiest stores, little stamped τ is over a month old
   (18% and 3%). On quiet stores it is all of it. That is the staleness case F3 was built for.
2. **It almost never changes what is spliced first.** The strongest edge changes in 2 of 266 measured classes.
   A class's edges tend to age together, so recency rescales them more than it re-ranks them.
3. **It does not stop a stale route from being injected.** The splice abstains on the deposit *count*
   (`MIN_DEPOSITS_TO_SPLICE`), not on τ. Under `recency`, an idle class's routes still splice, but with their
   decayed weight shown (a 400-day-old route reads τ≈0). Withholding a stale route outright would need a τ
   floor at readout, a separate design that would need its own gauge.
4. **It does not address the success-clocked-decay defect inside an active class.** A route that keeps
   failing in a busy class stays fresh-stamped by any success in that class.

## Before the flip (owed, if the PI approves)

- **`rt-stale-1` cannot flip as written.** Its test monkeypatches `PROV_MODE = "off"` as "the shipped default".
  The test must instead read the default from the Genome; otherwise it stays xfail even after the flip.
- **CLAIMS.md:** the F3 row moves from DORMANT to LIVE, with this result's date and n.
- **Estate-wide effect.** The estate runs one editable checkout, so a committed default reaches every repo
  without a local override as soon as it merges. Running MCP servers need a restart to pick it up.

**Verdict:** +1 · kind: experimental-design · within-class excess drift clears 0.10 on 7 of 8 evaluable stores
with 99% stamp coverage, so the pre-registered gate for proposing the `recency` default is met. The flip mainly
rescales stale τ and rarely re-ranks (2/266 classes), so the result supports a modest change, not a large
one · −1 if the same gauge, re-run on a later window that this run did not see, finds excess below 0.10 on a
majority of evaluable stores (the drift does not replicate).

*Hash note (2026-10-26):* this branch was rebased once, before review, to move two scheduled-routine commits
back to `main`. The freeze commit `e604996` became `d8eb399`, and the result commit `b2c29c4` became `b48dc87`.
Author dates are preserved: the freeze is 08:53:33 and the result commit 08:56:28 (UTC−7).

## Erratum (2026-10-26, after the run): an earlier re-gauge existed

PREREG §2 states that no excess drift had been computed on any repo since v1. **That is wrong.** A local
re-gauge on 2026-07-30 measured this repo at **excess 0.186** (5,178 consequences, 185 classes, 32.6 days).
It also found 1 of 124 stamped colonies changing its top route, and this repo has run `recency` locally since
that date.

That evidence was recorded only in this repo's gitignored `exocortex_config.json` comment. CLAIMS never
carried it, and it was not read before this freeze. So the rule was not tuned to it, but the disclosure was
incomplete.

It **corroborates** this run rather than contradicting it:
- this repo's excess was 0.186 then and is 0.219 now;
- top routes changed in about 1% of classes then, and in 0 of 17 classes here.

The default flip followed this result on 2026-10-26 (PI decision, ADR-003; CLAIMS F3 is LIVE).
