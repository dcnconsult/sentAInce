# Layer-2 attribution-precision results (Ticket 1 / #2)

The gate before `declarative.mode = live`: does content-echo attribution credit only notes the model
genuinely USED? Measured three ways, all agreeing.

## Setup
Planted-token vault (`exocortex/testbed/attribution_run.py`): each task has a **solution note** carrying a
unique MAGIC token + the exact shell command, a **coincidental distractor** (`*-ops.md`, shares the common
token `echo` with the solution command), and a **prose distractor**. Driven through the live hook; credited
notes read from the persisted colony, scored against the plant. An exit-0 carrying the magic token ⟹ the
solution note was genuinely used.

## Result — the same contrast at every level of realism

| measurement                          | min_overlap=1        | min_overlap=2        |
|--------------------------------------|----------------------|----------------------|
| synthetic gauge (`attribution_gauge`)| precision 0.79       | precision 1.00       |
| harness `sim` (deterministic actor)  | precision 0.50       | precision 1.00       |
| **real flagship (haiku, 5/5 done)**  | **precision 0.50**   | **precision 1.00**   |

Real run, per task (recall 1.00, completion 5/5 in both):
- **min_overlap=1** — every task credits the solution note AND its coincidental `*-ops.md` distractor
  (shares `echo`) → FP on all 5 → **precision 0.50**.
- **min_overlap=2** — every task credits ONLY the solution note → **precision 1.00, FP 0**.

The coincidental-echo failure the gauge predicted is real and reproduces on real hook-driven action
buffers; `min_overlap=2` eliminates it. The shipped default (`declarative.attribution.min_overlap = 2`,
set by the gauge) is validated.

## Caveats (honest scope)
- **Controlled tasks, not arbitrary coding.** Each task is a single clean command; real coding produces
  messier multi-command action buffers where coincidental echo could be higher. Precision 1.0 is for the
  controlled case — the messy-real-coding rate is still unmeasured.
- **Recall.** Here recall is 1.0 because the planted command-notes echo ≥2 distinctive tokens; the synthetic
  gauge showed `min_overlap=2` misses single-distinctive-token notes (recall ~0.45). Real notes vary.
- **BYO completion is the deployment wall, not the logic.** `llama3.1-8b-8k` could NOT complete the
  forced-token tasks (it hallucinated / paraphrased), so this precision number is from a CAPABLE model
  (flagship haiku) — which IS the user's real Claude Code deployment. The attribution LOGIC is validated;
  small-BYO-model completion remains poor (revisit with a stronger native-tool-call local model).

## Verdict
The precision gate is met (mo=2, triple-confirmed). The organ is ready to flip `declarative.mode = live`
against a real vault on a capable model — starting conservative, with the messy-real-coding precision to be
watched live (the exporter plots `exocortex_wiki_credit_rate`).
