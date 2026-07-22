# Class fragmentation — v1 results (the classifier arc: does anything beat what ships?)

**Harness:** `results/class_fragmentation_v1/replay.py` (+ `bootstrap.py`) · **Date:** 2026-07-22 ·
read-only, replays real transcripts through the real classifiers; live cue stores never touched
(`EXOCORTEX_STATE_DIR` → scratch). **Ticket:** the 80%-singleton reading from `sentaince status --full`
(ADR-021 arc), and the 2026-07-01 note routing fragmentation to a persistent-classifier fix
(`results/credit_funnel_and_consolidation_v1/` verdict 2).

## Verdict — **the shipped lexical classifier is the best measured option. Semantic is FALSIFIED as an upgrade; the persistent-classifier daemon is RETIRED (no prize behind it).**

Fragmentation is **not** shown to be a defect: every variant that reduced class count did so by
grouping prompts that did *not* lead to the same work.

## Method — judged by consequence, not by eye

Prompt text was never retained in the audit, so 37 Claude Code transcripts were replayed: the same
real prompt stream, chronological, through **both real classifiers starting cold**. The precision
metric is deliberately independent of wording — for each prompt, collect what the session actually
**did next** (tool names, file basenames, command verbs from the following assistant turns) and score
a class by the mean pairwise Jaccard of its members' downstream artifact sets. A classifier is precise
if the prompts it groups actually led to the same work. This is the project's own epistemology
(consequence, not appearance) turned on its own classifier.

Calibrated against a **null**: the same class-size distribution assigned at random, 20 trials. Lift =
coherence ÷ null. A classifier earns credit only for coherence *above* what its class sizes alone buy.

## ⚠ The instrument bug that voided the first run — read this before mining transcripts

In Claude Code transcripts **tool results arrive as `type:"user"` entries** — here **6,074 of 6,584**
of them. The first attribution loop treated any non-prompt user entry as a prompt boundary, so the
first tool result severed attribution and discarded the rest of the turn:

| extraction | tool_use blocks captured |
|---|---|
| naive (user entry ⇒ boundary) | **346 / 6,077 — 5.7%** |
| fixed (tool_result does not sever) | **4,982 / 6,077 — 82.0%** |

A **14× undercount**; median artifacts/prompt 2 → 9. Every number in the first pass was computed on
5.7% of the evidence and was discarded. The tell was diagnostic: the register-stoplist effect
*shrank* (+0.047 → +0.007) when the instrument improved — an effect that dissolves under better
measurement was an artifact of the measurement.

## Data — 299 prompts with downstream consequence, 37 transcripts

| variant | classes | singletons | rate | largest | coherence | null | **lift** |
|---|---|---|---|---|---|---|---|
| **lexical (ships)** | 170 | 132 | 77.6% | 14 | 0.1812 | 0.1439 | **1.26×** |
| semantic | 151 | 111 | 73.5% | 22 | 0.1765 | 0.1442 | 1.22× |
| lexical + register | 184 | 152 | 82.6% | 13 | 0.1883 | 0.1428 | 1.32× |
| semantic + register | 149 | 108 | 72.5% | 46 | 0.1470 | 0.1441 | **1.02×** |
| lexical content-only | 165 | 127 | 77.0% | 16 | 0.1869 | 0.1454 | 1.28× |
| semantic content-only | 148 | 103 | **69.6%** | **55** | 0.1420 | 0.1454 | **0.98×** |

`register` = discourse scaffolding stripped (task verbs protected); `content-only` = task verbs +
long content tokens, the verb/noun proxy.

**Paired bootstrap, `lexical + register` vs `lexical`, B=200, resampling the prompt stream:**
delta **+0.0071**, 95% CI **[−0.0459, +0.0842]**, P(delta>0) = **0.525**. Not separable from noise.

## Read

- **The two most fragmentation-reducing variants are at or below chance** (0.98×, 1.02×). Their classes
  group prompts no more consistently than shuffling a partition of the same sizes. Reducing class
  count is bought entirely with noise.
- **No semantic variant beats lexical.** Plain semantic (1.22×) is already below the shipped default.
- **The verb/noun hypothesis is not supported**, and its apparent support was instrument artifact.
  It is not *decisively* dead — the CI still admits ~+0.05 — but nothing here recommends shipping it.
- **Structural, needing no statistics:** semantic content-only puts **55 of 299 prompts (18%) in one
  class**; the earlier replay showed such a class fusing 24 unrelated lexical classes ("commit, now we
  brainstorm", "we are using local repos only", "yes, capture all"). A class like that has no coherent
  route to earn τ — the pheromone trap the design exists to avoid.
- **Mechanism:** MiniLM on conversational prompts encodes *register* (one maintainer's consistent
  voice) rather than task identity. Embeddings are not at fault; the corpus is one person writing
  consistently about varied work.
- **The sober part — a low ceiling for everyone.** The winner is only **1.26× random**. Random already
  scores 0.144 because Read/Edit/Bash are ubiquitous. Goal-class identity is only weakly related to the
  work that follows *under every method tested*, which is more useful to know than which variant edges ahead.

## What this retires

1. **Persistent-classifier daemon (for fragmentation): RETIRED.** The 2026-07-01 note routed
   fragmentation to it; there is no measured prize. It may still be justified on latency grounds — that
   is a different argument needing its own evidence.
2. **Semantic-as-default: stays OFF**, now on consequence grounds rather than only cost grounds.
3. **"80% singletons" is not a gap.** Reported by `sentaince status --full` as a fact about task
   variety, not a defect. Consistent with ADR-022's finding for Write/Edit, reached the same way:
   measure the population before building the fix.

## Caveats (honest scope)

- **n = 1 maintainer, 1 estate, 1 writing voice.** A multi-contributor corpus might separate these
  methods where this one cannot; the register finding especially may be voice-specific.
- The `register`/`content-only` stoplists were hand-authored against *this* corpus — overfitting risk,
  and a reason not to ship them even had they been significant.
- `<task-notification>` boilerplate (81 of 409 raw prompts, 20%) is excluded; leaving it in lets a
  contaminant carry the result, and it forms the single largest apparent "merge".
- Coherence is a proxy for task identity, not a ground-truth label. Lift is comparative, not absolute.
- Emulator-grade throughout: a labeled replay of real prompts, never a live product claim.

## Reproduce

```bash
python results/class_fragmentation_v1/replay.py      # variant table + null-calibrated lift
python results/class_fragmentation_v1/bootstrap.py   # paired bootstrap on the register variant
```

Both read `~/.claude/projects/<slug>/*.jsonl` read-only and write nothing outside a temp dir.

**The corpus is LIVE** — every session appends to it, so exact counts drift upward between runs and
will not reproduce to the digit. A same-day re-run at N=300 (vs the N=299 tabled above) gave delta
**+0.0066**, CI **[−0.0421, +0.0813]**, P = **0.545** — the verdict is stable, the decimals are not.
Numbers here are pinned to 2026-07-22; a later re-run drifting is expected, not a failure.
