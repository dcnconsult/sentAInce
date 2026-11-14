# Masked-exit gauge v1: what withholding τ from masked, unverifiable consequences would cost (R1a)

**Run:** 2026-10-26, under the frozen protocol [`PREREG.md`](PREREG.md) (committed `1bfd2f6` before the gauge
existed). **Gauge:** `exocortex/gauge/masked_exit_gauge.py`; its controls are
`exocortex/tests/test_masked_exit_gauge.py` (22 pass).

**Data:** read-only replay.
- **This repo:** a snapshot of `.claude/exocortex/audit.jsonl` taken at run time (14,675 lines).
- **`research-vault`:** its audit through 2026-10-16 (26,002 lines). Its orientation grade was Medium (activity
  drift). The store itself was confirmed current against the repo's commits since then.

Aggregates: [`results_2026-10-26.json`](results_2026-10-26.json). Reproduce:

```
python -m exocortex.gauge.masked_exit_gauge --audit <this-repo audit> --label SentAInce \
    --audit <research-vault audit> --label research-vault --json
```

## Results

| Store | Variant | Population | Withheld | L (loss) | C (starved) | R (retry excess) | R 95% CI | Raw retry, withheld vs kept |
|---|---|---|---|---|---|---|---|---|
| this repo | silent | 3,275 | 3 | 0.0009 | 0 | −0.075 | [−0.234, +0.006] | 0.33 vs 0.30 |
| research-vault | silent | 6,488 | 57 | 0.0088 | 0 | −0.199 | **[−0.281, −0.116]** | 0.14 vs 0.30 |
| this repo | masked | 3,275 | 206 | **0.0629** | **1** | −0.073 | [−0.156, +0.015] | 0.22 vs 0.31 |
| research-vault | masked | 6,488 | 375 | **0.0578** | 0 | −0.058 | [−0.123, +0.019] | 0.26 vs 0.30 |

`R_dropped_withheld` (withheld rows with no same-verb kept stratum): silent 0 / 1; masked 8 / 13.

## Disposition (frozen rule, §5)

- **silent → 0.**
  - Loss and starvation pass on both stores.
  - +1 fails: in the research vault, R's CI lies wholly below 0.
  - −1 is not met: it needs that on **both** stores, and this repo's upper bound is +0.006 on only 3 rows.
- **masked → 0.** Loss exceeds 0.05 on both stores (but stays under the 0.10 −1 bar), and one class in this repo
  would be starved.
- **Build selection:** `silent` is not +1, **so nothing is built.** Red-team `rt-tool-1` stays a strict xfail.

## Reading

- **Cost is not the obstacle.** Withholding τ from silenced masked consequences would forgo 0.09% and 0.88% of
  deposits and starve no class.
- **The blocker is the sanity check.** In the research vault, a silenced consequence is followed by a same-verb
  command about half as often as a comparable kept one (0.14 vs 0.30), and the effect is clear of zero. The
  check cannot separate two readings, as §7 of the prereg anticipated:
  - **Success:** the silenced commands mostly worked and the agent moved on, so the rule would discard good
    signal.
  - **Nothing to retry:** silenced commands skew to fire-and-forget housekeeping (`mkdir`, `docker`, `sleep`,
    `git`, scripted `python` runs), which nobody retries whether they worked or not.
- **The law argument is unchanged and was never this gauge's to settle.** An exit status the command text
  discards verifies nothing. Building R1a anyway would be a PI judgment under ADR-003, stated as that judgment,
  not as a gauge result.
- **A v2 needs a failure signal that discriminates**, measured **go-forward**. Re-cutting this data until it
  passes is ruled out. Candidates:
  - the same command re-run *unmasked* within the stream;
  - an artifact the command should have produced being absent at the next read.

## Side findings (descriptive, not gated)

- **Windows keying artifacts in the working-verb keying (R0).**
  - `python.exe` and `python` are separate verbs.
  - A quoted env assignment containing spaces (`GH="/c/Program Files/GitHub CLI/gh.exe" && "$GH" …`) is keyed
    `GitHub`. The whitespace tokenizer strips only `GH="/c/Program`, so the fragment `Files/GitHub` becomes
    the verb.

  Both split one working verb into several nodes. **This bears on R0's soak**, which runs on this repo, before
  any default flip.
- **PowerShell masking idioms** (`-ErrorAction SilentlyContinue`, `2>$null`, `Out-Null`) appear in **7.8%**
  (18/230) and **10.1%** (37/366) of PowerShell `ok` rows. That is a larger share than Bash's silent case, and
  no rule covers it. Note that `2>$null` and `Out-Null` suppress output without necessarily masking failure.
  Any rule needs its own prereg.

**Verdict:** 0 · kind: experimental-design · R1a's cost is negligible (≤0.9% of deposits, no class starved), but
the pre-registered sanity check fails on the research vault: silenced consequences are retried less, not more,
so the rule is not built · −1 if a go-forward v2 with a discriminating failure signal shows silenced masked
consequences succeed at or above the kept rate.

*Hash note (2026-10-26):* this branch was rebased once, before review, to move two scheduled-routine commits
back to `main`. The freeze commit `c17e9a4` became `1bfd2f6`, and the gauge commit `9148470` became `eb6faa7`.
Author dates are preserved: the freeze is 08:48:17 and the gauge commit 08:51:35 (UTC−7).
