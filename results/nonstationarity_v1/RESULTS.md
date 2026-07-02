# Non-Stationarity Gauge v1 — F3 provenance · recency/version decay

**Gauge:** `exocortex/gauge/nonstationarity_gauge.py` (stdlib, read-only, fail-open). **Run:**
`python -m exocortex.gauge.nonstationarity_gauge [--state-dir <repo>/.claude/exocortex] [--json]`.
**Discipline:** gauge-first (ADR-002) — before building F3 (the "quiet rot-killer": stamp each deposit with a
model-id + timestamp, decay τ by recency-and-version-distance), measure on the EXISTING audit + colony whether
the signal is present *and whether the provenance to measure it was ever recorded*.

**Data:** live fleet — SentAInce (387 consequences / 7 sessions / 578 colony edges), tao-zeta-phase-lab (14),
_feed_byo (0). Aggregate 401 consequences over a 2.6-day span, ts-coverage 1.0.

---

## Finding 1 — provenance coverage = **0.0** (the decision-relevant, rock-solid result)

| metric | value |
|---|---|
| consequences carrying a **model-id** | **0 / 401 (0.0)** |
| colony edges carrying a **per-deposit timestamp** | **0 / 578 (0.0)** |

The live hook records **neither** a model-id nor a per-edge timestamp (verified in code: the only model-id in
the codebase is the test-runner CLI, never the hook; the hook stdin contract carries no model field at all).
**So version-distance non-stationarity is UNMEASURABLE retroactively — the instrument was never installed.**
This is the finding that drives the build: F3 is fundamentally a **go-forward instrument**, not a retrofit. Its
first value is simply to *start* recording provenance so the signal becomes measurable next cycle, at model
upgrades, and at OSS-population scale.

## Finding 2 — the drift signal fires (0.48) but is **MISATTRIBUTED** — do not over-claim it

| metric | aggregate | SentAInce | tao-zeta |
|---|---|---|---|
| verb-mix drift early→late (TV distance) | **0.482** | 0.453 | 0.857 |
| verb-set churn (born-or-died fraction) | **0.65** | 0.632 | 0.833 |
| born verbs (late only) | docker, python, curl, export, mkdir, rm, … | | |
| died verbs (early only) | `&&`, `-t`, `command`, `wc` | | |

The verdict prints `signal=True` (both thresholds tripped), but the honest read is that **this metric measures
the wrong *kind* of non-stationarity** to validate F3's thesis. Two confounds:

1. **Verb-extractor noise.** `born`/`died` include `\`, `&&`, `-t`, `command`, `wc` — shell artifacts of taking
   `split()[0]` on compound/piped command-keys, not real routing verbs.
2. **Cross-class task-mix shift (the dominant confound).** The gauge **pools all consequences regardless of
   goal-class**. Over the 2.6-day window the operator's work moved from one subtask into the docker/testbed/
   python arc (matches the recent commit history) — so the *pooled* verb mix shifts even though each **per-class
   colony** already isolates its own routes. This is task-phase movement, **not within-route rot, and not model
   non-stationarity** (which is what F3's version-distance term targets).

So the v1 read was **0.48 is an upper bound, dominated by task-mix shift.** Recency is mild:
`recent_quartile_frac = 0.214` (≈ the uniform 0.25) → the store is **steadily refreshed, only slightly
front-loaded** — no dramatic staleness for recency-decay to reclaim.

### Update (class-bucketing + permutation null) — the v1 "cross-class" hypothesis was itself wrong

The class-bucketing follow-up (de-confound) + a permutation null (de-bias) **decomposed** the 0.48 and refuted
the v1 guess that task-mix pooling was the dominant confound. Goal-class is recoverable: the audit's
UserPromptSubmit `reason=class=…` is carried forward onto each session's consequences (`stationarity_by_class`),
and each class's drift is compared to a shuffle null (same verb multiset, random temporal order — the
small-sample TV floor, since ~7-vs-7 splits differ a lot even with no real rot). Live SentAInce decomposition:

| layer | value | what it is |
|---|---|---|
| pooled drift | **0.514** | naive (cross-class + small-sample inflated) |
| within-class observed | **0.489** | de-confounded — so cross-class was only **~0.025**, NOT the dominant confound |
| shuffle null | **0.288** | small-sample TV bias — the **real** dominant inflation (~0.29) |
| **excess (observed − null)** | **0.20** | the **de-biased, F3-relevant within-class non-stationarity** |

So the honest size of the signal is **excess ≈ 0.20** (above `EXCESS_THRESHOLD 0.10` → `signal=True`): there **is**
real within-class route rot over the 2.6-day window — concentrated in meta-work classes (`emulator-next#32`
excess 0.75, `_misc` 0.55, `orient-re#25` 0.51) — but it is **~40% of the naive 0.51**, the rest being sampling
bias. The null also absorbs the verb-extractor noise (shuffling the same noisy verbs reproduces the floor), so
excess is robust to it. **Net: F3's recency axis is real-but-modest, not the 0.48 headline and not pure noise.**
The robust conclusion (Finding 1: instrument-absent → F3 is a go-forward instrument) is unchanged.

**Gauge self-limit (honest):** the drift proxy is a verb-mix floor (the audit stores per-event keys, not
transitions), and model-distance is still unmeasurable until the instrument accrues model stamps. But goal-class
IS recoverable (the UserPromptSubmit carry-forward), so the within-class + null decomposition above is now a
fair offline read of the recency axis; the version axis waits on accrued provenance.

---

## Verdict → **build the provenance substrate, ship it DORMANT** (the endocrine/eligibility/declarative pattern)

- **Version-distance decay:** unmeasurable retroactively (instrument absent). Prize is real-but-unmeasurable on
  single-dev / single-model flagship traffic — the **latent regime** of [[oss-community-strategy]]; the signal
  lives at model upgrades and population scale. Build dormant; it is also the **prerequisite for W6** (cross-agent
  stigmergy needs provenance to avoid trail-poisoning) and the **only mechanism that demotes a stale
  false-success route** (a partial corrective to the amplification ceiling).
- **Recency decay:** real-but-modest — **de-biased excess ≈ 0.20** (the naive 0.51 is mostly small-sample TV
  bias, ~0.29, plus a tiny cross-class confound, ~0.025). Build it, default off, with a half-life long enough
  not to evaporate a steadily-refreshed skeleton.
- **Stamp source:** `time.time()` at deposit (free) + model-id from the **transcript tail** (the hook stdin has
  no model field). Record `model=""` until the transcript-tail sourcing is wired — recency works on `ts` alone;
  version-distance stays dormant until model provenance is reliable.

**Recommendation:** ship a `genome.provenance` block (mode `off|recency|full`, default **off**), a per-edge
`meta{ts,model}` lane in `Colony.deposit` (back-compat: pre-F3 colonies load with empty meta → byte-identical
behavior), and a recency-weighted readout. Re-gauge once provenance accrues (and add class-bucketing to remove
the cross-class confound). See [[exocortex-hook-integration-roadmap]].
