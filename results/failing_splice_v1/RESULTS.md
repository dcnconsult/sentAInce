# Failing-splice gauge v1: do suggested routes fail, and does the memory keep offering them? (avenue 2)

> **Public labels (2026-10-28).** Private estate repositories appear as `repo-A` … `repo-H`. This repo,
> `lab`, `research-vault` and `cursor_testbed` keep their usual public labels. Only the names changed: every
> number is as run, the mapping is the same across this run's result files, and the frozen pre-registration is
> untouched.

**Run:** 2026-10-26, under the frozen protocol [`PREREG.md`](PREREG.md) (committed before the gauge
existed). **Gauge:** `exocortex/gauge/failing_splice_gauge.py`. Its controls are in
`exocortex/tests/test_failing_splice_gauge.py` (7 pass). The key control: on the same stream, the replay
colony reproduces the live `Colony` exactly, both τ and the dominant path, across deposits and sleeps.

**Data:**
- every estate audit;
- this repo's audit, as a run-time snapshot of 14,915 lines, with working-verb keying from the R0 epoch;
- the research vault's audit, through 2026-10-16.

Aggregates: [`results_2026-10-26.json`](results_2026-10-26.json).

## Results

A store is evaluable at ≥30 followed turns.

| Store | Spliced turns | Followed | Follow rate | **X** contradiction | **E** excess [95% CI] | Off-route fail rate | Contradictions | **P** median | Deposit before next splice |
|---|---|---|---|---|---|---|---|---|---|
| this repo | 312 | 160 | 0.51 | **0.069** | −0.033 [−0.125, +0.054] | 0.076 | 11 | **0** | 1.0 |
| research-vault | 312 | 209 | 0.67 | **0.057** | +0.004 [−0.026, +0.035] | 0.070 | 12 | **0** | 1.0 |

Below the evaluability floor, descriptive only:

| Store | Followed | X | Contradictions |
|---|---|---|---|
| lab | 29 | 0.0 | 0 |
| repo-A | 27 | 0.074 | 2 (P = 0) |
| repo-B | 26 | 0.0 | 0 |
| repo-H | 23 | 0.0 | 0 |
| repo-C | 7 | 0.0 | 0 |
| repo-E | 4 | 0.25 | 1 (P = 0) |

## Disposition (frozen rule, §5): **0**

- **+1 fails:** X is below 0.10 on both evaluable stores, E's CI includes 0, and P's median is 0.
- **−1 is not met:** X is just above 0.05 on both stores, and E's CI upper bound is above 0.

## Reading

**The hypothesis behind avenue 2 is not supported.** It came from this project's 2026-10-26 landscape scan:
because decay is clocked by successes, a route that starts failing would keep being offered.
- **Suggested routes rarely fail.** The first route command fails in 6–7% of followed turns.
- **When they fail, they fail like anything else.** The failure rate is indistinguishable from the same
  verbs off-route (E ≈ 0, both CIs straddle 0). These look like ordinary failures (a test that fails, a
  command that errors), not a wrong route.
- **They do not persist.** After every one of the 23 contradictions, the class earned another deposit before
  its next splice, and the spliced route had changed by then (median P = 0).

The defect is real in the mechanism, but these stores are active enough that success-clocked decay never
leaves a failing route standing. A read-side "failing" marker would have almost nothing to mark.

**Still true:**
- **The replay approximates.** Session-discounted weights are not reproduced, so a replayed dominant path can
  differ from the one actually spliced. The PREREG's go-forward splice stamp would remove that error.
- **Follow rate is a new number, though only a replay estimate.** About half to two-thirds of spliced turns
  run a command on the suggested route. That is the closest this project has come to measuring how much the
  splice steers the agent.
- **Quiet repos are the untested case.** Too few followed turns there to say anything, and recency decay
  (live since 2026-10-26) is the mechanism aimed at them.

**Verdict:** 0 · kind: experimental-design · on both evaluable stores, failing suggestions are rare (5.7–6.9%),
indistinguishable from off-route failure, and never re-spliced unchanged, so no failing marker is warranted ·
−1 on the avenue (park it) if a go-forward run with the exact splice stamp reproduces X < 0.10 with
P median 0.
