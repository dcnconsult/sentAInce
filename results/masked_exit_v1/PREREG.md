# Pre-registration: masked-exit non-deposit (R1a / rt-tool-1) — what does withholding τ cost?

**Frozen:** 2026-10-26, committed before the gauge is written or run. **Kind:** experimental-design.
**Gauge:** `exocortex/gauge/masked_exit_gauge.py` (read-only over audit JSONL, stdlib).

## 1. Question

When an agent masks a command's exit status (`|| true`, `; echo "exit: $?"`), the Bash tool exits 0 and the
hook judges the outcome from stdout/stderr alone (`classify_outcome`). R1c widened the failure signatures.
What remains is the **fully silenced** case (`2>/dev/null || true`): there is no output to read, so it
reads as `ok` and earns τ. That is red-team gap `rt-tool-1`, the one strict xfail R1c left open.

The law is that persistence is gated on a **verified** outcome, and an exit status the command text itself
discards verifies nothing. So the case for a third outcome, `unknown` (no τ, no scar), comes from the law,
not from this gauge. **The gauge bounds its cost:** how many legitimate deposits would be withheld, whether
any goal-class would be starved, and whether the withheld consequences look *better* than ordinary ones
(in which case the rule would discard good signal, which is the remediation plan's −1).

## 2. What has already been seen (disclosed before freezing)

The 2026-09-16 scratch replay (dossier 06 §0) counted exit-code masking (`|| true`, `|| echo`, `echo … $?`)
in **172 of 3,207 (5.4%)** SentAInce and **189 of 3,407 (5.5%)** research-vault depositing records, and
44 / 17 `ok` snippets carrying a then-missed failure signature (most now caught by R1c).

**Not yet computed:** the silent share, the retry proxy, class starvation, or anything under the exact
definitions below.

## 3. Definitions (frozen)

Scope: `tool == "Bash"` consequences. PowerShell masking idioms differ (`-ErrorAction SilentlyContinue`,
`2>$null`, `| Out-Null`). They are counted **descriptively only** (§4 D1) and no rule is gated on them.

- **Masked M(cmd):** the command text matches any of
  1. `\|\|\s*(?:true|:)(?=\s*(?:$|[;&|)]))` (`|| true`, `|| :`)
  2. `\|\|\s*echo\b` (`|| echo …`)
  3. `\|\|\s*exit\s+0\b` (`|| exit 0`)
  4. `\$\?` (any reference to the exit status, e.g. `echo "exit: $?"`)
  5. `;\s*(?:true|:)\s*$` (a trailing `; true` / `; :`)

  Pipes (`cmd | tail`) are **out of scope**: their output is still visible, which is R1c's lane.
- **Silent S(row):** the recorded `output` snippet (first 240 chars of stdout+stderr), stripped, is empty.
  Truncation cannot hide output, so emptiness is exact.
- **Signature F(row):** today's `exocortex.hook.classify_outcome` returns `fail` on the snippet.
- **Population:** audit rows with `event == "PostToolUse"`, `outcome == "ok"`, `tool == "Bash"`, and
  `¬F` (re-classified under today's rules, since rows today's classifier calls `fail` already deposit
  nothing). Every such row is a deposit event (the cue root guarantees ≥1 edge).
- **Variants** (the rows each would turn into `unknown`):
  - **silent:** `M ∧ S`
  - **masked:** `M ∧ ¬F` (output may be present)
- **Stream:** rows keyed by `(session, agent_id)`, in file order. A `UserPromptSubmit` row for the session
  ends every stream of that session (a new prompt is a new task, not a retry).
- **Working verb:** `exocortex.colony._working_verb` (frozen in `results/verb_keying_v1/PREREG.md` §3).
- **Goal-class:** carried forward from the session's latest `UserPromptSubmit` `reason` field (`class=<label>`),
  else `_default`.

## 4. Metrics (per store, per variant)

- **L `loss_share`:** withheld rows ÷ population rows.
- **C `starved_classes`:** goal-classes with ≥5 population rows of which the variant withholds >50%.
- **R `retry_excess`:** for each population row, `retry = 1` if the next consequence row (`PostToolUse` or
  `PostToolUseFailure`, any tool with command text) in the same stream, before the stream ends, has the
  same working verb; else 0. Stratify by working verb; keep verbs with ≥1 withheld and ≥1 kept row.
  `R = Σ_v n_w,v (p_w,v − p_k,v) / Σ_v n_w,v`, where `w` = withheld and `k` = kept population rows.
  **CI:** session-cluster bootstrap, 1,000 resamples, seed `20261026`, percentile 95%. Report the number of
  withheld rows dropped for lack of a same-verb kept stratum.
- **Descriptive only:** D1 PowerShell rows matching `-ErrorAction SilentlyContinue|2>\$null|Out-Null`;
  D2 the top working verbs among withheld rows (verbs only, no command text); D3 raw retry rates.

## 5. Decision rule (frozen), applied per variant

Stores: this repo and the research vault (labelled `research-vault`).

- **+1 (build behind a knob, default off):** on **both** stores, `L ≤ 0.05`, `C = 0`, and R's CI upper
  bound `≥ 0` (withheld rows are not shown to be retried *less* than comparable kept rows).
- **−1:** `L > 0.10` on either store, **or** R's CI upper bound `< 0` on **both** stores (the rule would
  discard demonstrably better-than-average signal).
- **0:** anything else.

**Build selection:** the `silent` variant is built if it is +1. The `masked` variant becomes a second knob
value only if it is also +1. If `silent` is not +1, nothing is built.

## 6. Build contract (only if §5 yields +1)

- Genome knob `consequence.masked_exit = trust | silent | masked`, default `trust` (byte-identical).
- `unknown` deposits no τ, credits no wiki note, and never walks a bridge to a scar (ADR-004). The energy
  debit is the plain action cost. It re-roots the trail at the cue, as a failure does, so a later success
  cannot credit the unverified segment. In the strategy-lock streak it is transparent: it neither counts
  as a failure nor resets one.
- The audit row keeps `event = PostToolUse` (the tool call did exit 0) with `outcome = "unknown"`.
- The edit touches `exocortex/hook.py`, so it needs an ADR-016 pin re-baseline, approved by the PI and
  recorded.
- Red-team `rt-tool-1`: the silenced row is restated as "earns no τ" and stays a strict xfail on the
  shipped default, like `rt-key-1`. A passing companion test pins the knob's behavior.

## 7. What this cannot show

- It cannot say how many withheld rows were real failures. A silent masked command carries no evidence
  either way; the retry proxy is a sanity check against discarding good signal, not a failure detector.
- It does not show that withholding τ helps an agent reach `exit 0`. Efficacy stays unmeasured, as in CLAIMS.
- PowerShell masking is uncounted by any gated rule.

## 8. Output

`results/masked_exit_v1/RESULTS.md` plus an aggregate-only JSON. No command text; the second store is
labelled `research-vault`.
