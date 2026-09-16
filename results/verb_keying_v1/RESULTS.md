# Verb-keying gauge v1: results (R0 / DQ-1)

**Run:** 2026-09-16, against the frozen [`PREREG.md`](PREREG.md) (committed before the gauge existed).
**Gauge:** `exocortex/gauge/verb_keying_gauge.py`, tests in `exocortex/tests/test_verb_keying_gauge.py` (14).
**Data:** the live audit stores of two repos: this repo, and `research-vault` (a private research vault).
**Raw:** [`results_2026-09-16.json`](results_2026-09-16.json), aggregates only.
**Reproduce:**

```
python -m exocortex.gauge.verb_keying_gauge --audit <repo>/.claude/exocortex/audit.jsonl [--audit … --label …]
```

## Numbers

Metrics (defined in PREREG §4):
- **M1 nav/env share:** ok-segment edges that touch a navigation or env key.
- **M2 frequency clutter:** fail-only share of the frequency-null memory.
- **M3 pass/fail Jaccard:** overlap between the edges of successful and failed segments.
- **Check:** consequence-policy clutter, which must be 0.

| Repo | Segments (ok) | Keying | M1 nav/env | M2 freq clutter | M3 pass/fail Jaccard | Nodes | Edges | Check |
|---|---|---|---|---|---|---|---|---|
| SentAInce | 3,471 (3,222) | first | 0.237 | 0.020 | 0.159 | 356 | 2,190 | 0.0 |
| | | **working** | **0.016** | 0.019 | 0.155 | 363 | 2,326 | 0.0 |
| research-vault | 3,634 (3,422) | first | 0.441 | 0.015 | 0.118 | 328 | 2,048 | 0.0 |
| | | **working** | **0.051** | 0.018 | 0.121 | 357 | 2,364 | 0.0 |

**Decision rule (PREREG §5), per repo:**
- (a) M1 halved: ✓ on both repos.
- (b) M2 kept within 0.02: ✓ on both (−0.001, +0.003).
- (c) M3 kept within 0.02: ✓ on both (−0.004, +0.003).
- The consequence check is 0 on both, so the run is valid.

**Disposition: +1. Build R0 behind a Genome knob.**

## Reading, kept to what was measured
- **What the +1 means:** working-verb keying **removes the navigation/env keys** (edge share 23.7% → 1.6%
  and 44.1% → 5.1%) **without losing** the discrimination signal. It does **not** show that discrimination
  *improves*: M2 and M3 moved by 0.004 or less, well inside the tolerance.
- **Working keying resolves more of the vocabulary:** distinct edges +6% and +15%, as routes that
  collapsed into `bash:cd` separate back into their real verbs.
- **On recorded live traffic the frequency-null clutter is small** (about 2%), far below the scripted-stream
  24% behind the PROVEN clutter row. Live sessions contain few failure segments (249 of 3,471 here), so
  there is little fail-only material to discriminate. That is a property of this traffic and does **not**
  revise the PROVEN row, which was measured on a different, scripted stream.
- **Out of scope** (PREREG §6): whether working-verb routes help an agent reach `exit 0`. Efficacy stays
  unmeasured.

**Verdict:** +1 · kind: experimental-design · the frozen three-part rule passed on both repos, with the
consequence-clutter check at 0 · −1 if a replay of a third repo's audit fails (b) or (c).
