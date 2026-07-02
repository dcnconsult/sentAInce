# Cold-start gauge (Cursor first-turn miss) — v1 results (baseline)

**Gauge:** `exocortex/gauge/coldstart_gauge.py` · **Date:** 2026-07-01 · read-only, pure-stdlib, ADR-002.
**Command:** `python -m exocortex.gauge.coldstart_gauge --scan-root <dev-root>`.
**Sizes:** arc Task #4 / limitation L9 (Cursor lazy-init for the first `beforeSubmitPrompt`/`sessionStart` miss).

## Verdict — **BUILD (signal=True).** The gauge flipped L9 from "probably park" to "material."

On Cursor the first-turn miss is **pervasive, not an edge case**, and it doesn't just lose a deposit — it
**misattributes real deposits to `_default`**, undermining the per-class colony (the multi-model-stigmergy value).

## Data (per repo)
| repo | host | sessions | cold-start | rate | sessionStart miss | lost deposits | `_default` cons |
|------|------|----------|-----------|------|-------------------|---------------|-----------------|
| SentAInce | Claude Code | 8 | 0 | **0.0** | 0 | 0 | 0 |
| cursor_testbed | Cursor | 13 | 11 | **0.846** | 12 (0.92) | 10 | **76** |
| tao-zeta-phase-lab | Claude | 2 | 1 | 0.5 | 0 | 0 | 0 |
| _feed_byo | (BYO) | 2 | 0 | 0.0 | 0 | 0 | 0 |
| **pooled** | | 25 | 12 | 0.48 | 12 | **10** | 76 |

Flip-trigger (`cold_start_rate ≥ 0.10` **and** `lost_deposits ≥ 3`): **MET** (cursor 0.85 / 10 lost).

## Read
- **Claude Code = 0** on both counts → `UserPromptSubmit`/`SessionStart` fire reliably; the fix is Cursor-only.
- **Cursor**: ~85% of sessions have a tool call *before* the first `UserPromptSubmit`, and `sessionStart`
  almost never fires (92% miss — matches the documented Cursor beta caveat). Cost split: **10 deposits lost
  entirely** (empty trail → `seg_len 0`) + **~66 deposits misattributed to `_default`** (bound to the wrong
  goal-class). The class-misattribution is the bigger cost — it dilutes the per-class colony.

## Caveat (honest)
`cursor_testbed` is a throwaway carrying the live deny/echo tests + the early Android-app soak; the 0.85 rate
is indicative, not final. **Re-run on the fuller Android-recipe-app soak** to confirm the rate holds before/after
building the fix.

## Next (Task #4)
Build the **transcript-recovery lazy-init** (guarded to `provider=cursor`): on `preToolUse`, if this turn was
never classified (no preceding `UserPromptSubmit`), recover the last user prompt from the payload
`transcript_path` → classify → seed `goal_class` + the trail cue. **Empirical prerequisite:** `transcript_path`
was `null` on the *first* call in the probe — verify the transcript is reachable exactly when needed; else fall
back to seeding `cue:<lightweight>` so the first success at least deposits (to `_default`) rather than vanishing.
Re-run this gauge after the fix — the cold-start rate should stay (Cursor still misses) but `lost_deposits` and
`_default` cons should drop toward 0.

Reproduce: `python -m exocortex.gauge.coldstart_gauge --json`.
