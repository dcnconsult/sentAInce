# Pre-registration — guide-accrue#18 outcome A/B (the first outcome-grade experiment)

**Status:** DRAFT v1.2 (2026-07-08) — **frozen on PI approval**; any post-freeze change is a numbered
amendment recorded in this file (the lab's `NOTE_SALIENCE_ABLATION.md` v1.1 discipline), never a silent edit.
**v1.1 (pre-freeze draft revision):** the experiment is now **two-stage** — Stage A (sandbox, automated,
paired same-task counterfactuals; §10) runs FIRST and gates Stage B (the original live design, §§3–9).
**v1.2 (pre-freeze, PI-directed):** the Stage A battery is redesigned **memory-intense** after the pilot
showed Tier-1 ceiling on path-explicit doc tasks (12/12 success both arms). Four categories × 4 tasks
(pairs homogeneous): **B** fact-required (path given; the oracle demands the repo's TRUE value — e.g. the
committed gate default `observe`, the 69+30 lock composition); **C** false-premise refutation (path given;
the prompt asserts a wrong value — e.g. "M4 used 87 episodes" — and the oracle demands the true value AND
fails if the false value is written: `verify_absent`); **A** retrieval-required (no path — the prompt names
the doc only by role, e.g. "the guide that carries the honest-scope section"; the oracle checks the ONE
canonical file); **D** = A+C combined (no path + false premise; hardest). **Fairness invariant, audited per
task:** every required fact lives in git-tracked files in the snapshot, equally readable by both arms —
memory may change the *efficiency and reliability of access*, never the *availability*; oracles score
against repo ground truth, never against injected content; no fact is exclusive to the injected notes (the
notes are exons of tracked `battle/README.md`). Known oracle bluntness, stated: `verify_absent` fails a
correction that *quotes* the false value; symmetric across arms; the LLM-judge alternative stays rejected
(ADR-010). All 16 prompts verified offline: 16/16 route to `guide-accrue#18`, all oracles
baseline-unsatisfied. Binding text: `exocortex/testbed/ab_tasks.json`.
**Instrument:** `exocortex/gauge/ab_outcome_gauge.py` (read-only harvest; arm log in the gitignored state dir).
**Provenance:** ranked #1 by the Desktop 4-session longitudinal audit (2026-07-01): instrument-grade evidence
is saturated; *"tool improves outcomes"* is 0/UNMEASURED — this experiment is the promotion gate for the
value claim. Protocol sketch: `results/credit_funnel_and_consolidation_v1/RESULTS.md` §"ranked path" item 1.

## 1. Question

Does injecting the converged procedural route (the colony **splice** on `UserPromptSubmit`) causally reduce
the effort a live session spends completing a task of the class it converged on?

This tests the **splice channel only**, at its best case. It does not test the declarative channel (held
constant), and a null here scopes the *splice* value claim — it does not falsify consequence-sourcing.

## 2. Why this class

`guide-accrue#18` is the most converged asset in the SentAInce colony: 37 deposits, a 4-hop converged route,
3 τ-credited notes. Maximum possible arm contrast; a null here is a real null, not a cold-start artifact.
Class lexical centroid (from `cues.json`, what prompts must sound like): *guide, documentation, document,
user, whitepaper, roadmap, summary*.

## 3. Arms

| Arm | Launch | Effect |
|---|---|---|
| **ON** | normal environment | UserPromptSubmit injects the converged route + credited notes |
| **OFF** | `EXOCORTEX_COLONY_SPLICE=0` in the session's environment | splice suppressed; **accrual continues by design** (deposits identical mechanically) |

**Held constant across arms (the live SentAInce config as of 2026-07-08):** `declarative: live`
(vault = repo, explore_budget 5), `somatic_gate: somatic`, `eligibility_trace: trace`, reflection preamble
sibling hook `live`, lexical cue-classifier (`EXOCORTEX_EMBED=0`), same model, same repo.

## 4. Controls (pre-registered)

- **C1 — MCP recall disabled, both arms.** The lab hermeticity finding (2026-07-07): agents bypass the organ
  by calling `exocortex-memory` MCP tools directly. All A/B sessions launch with the `exocortex-memory` MCP
  server unavailable (e.g. `claude --strict-mcp-config` with a config that omits it). Symmetric across arms.
- **C2 — Store-read contamination detector (structural).** The harvest flags any session whose commands touch
  `.claude/exocortex`, `colony_*.json`, or the recall tools; flagged sessions are **excluded** (listed, not
  hidden).
- **C3 — Classification check.** A session whose first `UserPromptSubmit` audit record does not carry
  `class=guide-accrue#18` is **excluded** (the arms never engaged the asset under test). Task prompts are
  worded on the class centroid (§2) to minimize this.
- **C4 — One session at a time.** No other Claude session on this repo during a trial (the arm join is
  time-based). The harvest flags ambiguous joins.
- **C5 — Session hygiene.** Each trial is a fresh session; the session is ended immediately after the task's
  verification command succeeds (defines the effort window).

## 5. Task set (16 tasks · 8 matched pairs · DRAFT pending PI approval/substitution)

Design: 8 pairs of same-shape documentation-guide tasks; within each pair one task goes to each arm
(assignment pre-fixed below, ON/OFF position alternating by pair parity to balance drift). Every prompt ends
with a verification command so the trial closes on a verified success. The PI may substitute any task with
real upcoming work **of the same shape** before the freeze — substitutions are part of the freeze, not after it.

**Wording revision (2026-07-08, pre-freeze; the binding text is `exocortex/testbed/ab_tasks.json`).** The
first pilot run exposed that naturally-worded doc-editing prompts route to `md-doc#19` (0/16 hit the class
under test — C3 fired exactly as designed). All 16 prompts now carry a uniform framing on the class centroid
("Let the user guide documentation accrue for other users before we close this session: …"), verified
**offline against the real lexical classifier on the snapshot's cue store: 16/16 route to
`guide-accrue#18`, all oracles baseline-unsatisfied** (deterministic, zero tokens). Stated honestly: prompts
are classification-targeted — a legitimate part of engaging the asset under test, at a small cost in prompt
naturalness (noted as a scope caveat, symmetric across arms). C3 remains the runtime check on every run.

| Pair | Arm | Task prompt (verbatim; note the centroid tokens) |
|---|---|---|
| 1 | ON | Update the user guide documentation: document the `state_<session>.json.lock` sidecar in `exocortex/docs/USER_GUIDE.md` (what it is, when it appears, safe to delete when no session is live). Verify with a grep for "lock" in that file. |
| 1 | OFF | Update the user guide documentation: document the `ab_arms.jsonl` arm log in `exocortex/docs/USER_GUIDE.md` (what it is, where it lives, how to reset it). Verify with a grep for "ab_arms" in that file. |
| 2 | OFF | Document the v0.1.3 release in the guide: add a short "what changed for users" summary section to `docs/STORY.md`. Verify with a grep for "0.1.3". |
| 2 | ON | Document the v0.1.2 release in the guide: add a short "what changed for users" summary section to `docs/STORY.md`. Verify with a grep for "0.1.2". |
| 3 | ON | Update the deploy guide documentation: add a user-facing troubleshooting entry for the hook timeout symptom to `docs/DEPLOY_TO_A_PROJECT.md`. Verify with a grep for "timeout". |
| 3 | OFF | Update the deploy guide documentation: add a user-facing troubleshooting entry for the "zero stats in Desktop" symptom (bare-`python` spawn env) to `docs/DEPLOY_TO_A_PROJECT.md`. Verify with a grep for "Desktop". |
| 4 | OFF | Document the guide for users: add a GLOSSARY entry for "fused edge" to `docs/GLOSSARY.md`. Verify with a grep for "fused". |
| 4 | ON | Document the guide for users: add a GLOSSARY entry for "arm (A/B)" to `docs/GLOSSARY.md`. Verify with a grep for "arm". |
| 5 | ON | Update the whitepaper documentation summary: add one paragraph on the session-state lock to the relevant section of `docs/WHITEPAPER.md`. Verify with a grep for "lock". |
| 5 | OFF | Update the whitepaper documentation summary: add one paragraph on audit tail anchoring (ADR-018, proposed) to the relevant section of `docs/WHITEPAPER.md`. Verify with a grep for "anchor". |
| 6 | OFF | Update the battle guide documentation: add a "reading the episode log" user note to `battle/README.md`. Verify with a grep for "episode". |
| 6 | ON | Update the battle guide documentation: add a "reproducing a single episode" user note to `battle/README.md`. Verify with a grep for "reproduc". |
| 7 | ON | Document in the user guide: a summary of which files the exocortex writes and which it never touches, in `exocortex/README.md`. Verify with a grep for "never". |
| 7 | OFF | Document in the user guide: a summary of the fail-open discipline (every hook path, timeouts) in `exocortex/README.md`. Verify with a grep for "fail-open". |
| 8 | OFF | Update the roadmap documentation guide: reconcile the ADR count reference ("eighteen decisions") anywhere it is stale in `docs/`. Verify with a grep for "eighteen". |
| 8 | ON | Update the roadmap documentation guide: add ADR-017/ADR-018 one-line entries to any ADR index/summary in `docs/`. Verify with a grep for "ADR-018". |

**Schedule:** run pairs in order 1→8, the two tasks of a pair back-to-back, arm order as listed. Target
**N = 8 per arm** (16 trials). Trials may be spread across days; the schedule order is fixed.

## 6. Per-trial protocol (the PI's runbook)

1. `python -m exocortex.gauge.ab_outcome_gauge log-arm <ON|OFF> --task P<pair><a|b>` (writes the arm
   declaration + timestamp to the state-dir arm log).
2. Launch a **fresh** session with the arm's environment (§3) and C1's MCP config, in this repo.
3. Paste the task prompt **verbatim**.
4. Let the session work; intervene only as you naturally would (interventions are part of both arms' reality).
5. When the verification command succeeds, end the session.
6. (Any time later) `python -m exocortex.gauge.ab_outcome_gauge harvest --since 2026-07-08` — metrics are
   computed from the audit log; nothing is scored by hand.

## 7. Metrics (computed by the gauge; definitions are binding)

A *session* = all audit records sharing a `session` id, joined to an arm by the latest `log-arm` entry at
most 30 minutes before the session's first record.

- **PRIMARY — `total_steps`:** count of `PreToolUse` records in the session (effort to completion; the
  session ends on verified success per C5).
- **Secondary — `orientation_reads`:** `PreToolUse` records whose `command_key` verb ∈ {`cd`, `ls`, `pwd`,
  `cat`, `dir`} (the flail signature).
- **Secondary — `failures`:** count of `PostToolUseFailure` records.
- **Secondary — `duration_s`:** last record ts − first record ts.

## 8. Exclusion rules (pre-registered; excluded sessions are listed in the harvest output)

E1 wrong class (C3) · E2 store-read contamination (C2) · E3 no arm assignment / ambiguous join (C4) ·
E4 zero `PreToolUse` records (a dud launch) · E5 session predates `--since`.

## 9. Analysis & decision rule

- Per-arm **median** of the primary; one-sided permutation test (ON < OFF), exact when the assignment count
  ≤ 200,000, else 20,000 Monte Carlo resamples (seed 20260708).
- **+1 (promote the splice-value claim):** ON median `total_steps` < OFF with p ≤ 0.05, secondaries not
  contradicting.
- **0 (directional — extend N before claiming):** p ≤ 0.20 and `orientation_reads` in the same direction.
- **−1 (scope the claim):** at full N, ON median ≥ OFF median — no efficiency gain at the organism's *best*
  convergence; the splice pitch is then scoped to accrual/consistency until a class exists where it pays.
- Pre-registered secondary analysis: paired by pair-id (matched-pairs sign-flip permutation) — reported
  alongside, not a substitute for the primary rule.

**Power, honestly:** N=8/arm detects only a large effect; this yields **directional evidence or a decisive
null**, not a small-effect estimate. That is the intended grade — the current evidence is zero.

## 10. Stage A — sandbox paired counterfactuals (runs first; gates Stage B)

**Design.** One **golden snapshot** freezes the repo's git-tracked tree + the exocortex organs
(`colony_*.json`, `cues.json`, `embed_cues.json`) + the activation config. Every trial **thaws two
byte-identical copies** and runs the **same task prompt** headless in each; the only difference is
`EXOCORTEX_COLONY_SPLICE=0` in the OFF arm. Trials reset from the snapshot — arms never drift in repo
state or colony state. Harness: `exocortex/testbed/ab_stage_a.py`; tasks: `exocortex/testbed/ab_tasks.json`
(16 tasks, 8 pairs, on the class centroid).

**Parameters (PI-set 2026-07-08):** repeats **R=3** per task per arm (96 runs), turn cap **40**
(`--max-turns 40`; hitting the cap = failure), **same model** pinned `claude-fable-5`, run timeout 1800s.

**Launch (hermetic):** `claude -p <prompt> --max-turns 40 --model claude-fable-5 --output-format
stream-json --include-hook-events --verbose --strict-mcp-config --mcp-config {"mcpServers":{}}` with
cwd = the trial copy. `--strict-mcp-config` + empty server map = **no MCP loads** (control C1, both arms);
project hooks fire normally in `-p` mode and the installed PreToolUse hook is the permission authority
(the feeder's production-proven pattern). `EXOCORTEX_EMBED=0` both arms (matches live lexical routing).
Designed to run in a **cloud sandbox that never reads the local estate**: the harness touches only the
snapshot it is given; the snapshot is relocatable (hook paths + vault re-derived per trial by
`exocortex.deploy.install`).

**Held constant, with two pre-registered deviations from the live config (symmetric across arms):**
`integrity: warn` (the kernel-lock is not under test; a path-sensitive `enforce` would apoptose clones)
and the wiki digest cache starts cold in every trial (both arms equally; the splice channel under test is
unaffected).

**Success oracle (Tier 1) is mechanical** (ADR-010 — no LLM judge): each task requires a distinctive
marker phrase in a named file; the harness greps for it. **Pre-flight control:** every oracle must be
UNSATISFIED in the snapshot or the run refuses to start (no free successes).

**Metrics — the lexicographic "helping" definition (binding):**
- **Tier 1 (primary, gates everything):** success rate; paired per-task sign-flip permutation (ON better).
- **Tier 2 (efficiency, computed over successful runs ONLY — the fast-but-wrong guard, from the lab's
  splice-only 0.00-success precedent):** output/input tokens, steps (PreToolUse count), turns, wall clock.
- **Tier 3 (process diagnostics, never promotable alone):** orientation reads, hook-observed failures.
- **Tier 4 (do-no-harm):** files changed, out-of-scope touches (git surface vs the baseline commit;
  deploy artifacts and organ churn excluded from the surface).
- Controls carried per run: classified class must be `guide-accrue#18`; store-read contamination flags;
  timeouts reported per arm.

**Stage A decision rule (gates Stage B):**
- **Proceed to Stage B** if Tier 1 moves (paired p ≤ 0.05, ON better) **or** Tier 1 is at ceiling in both
  arms and Tier 2 (given success) moves (p ≤ 0.05 on output tokens or steps).
- **Stage B not warranted** (decisive sandbox null): Tier 1 and Tier 2 both flat or ON-worse at full N —
  the splice value claim is scoped to accrual/consistency for autonomous completion, and the PI's 16 live
  sessions are saved.
- **Scope, stated:** Stage A is **emulator-grade** evidence about *autonomous single-prompt completion*
  from identical state. It is never presented as the live assisted-session product claim — that is Stage
  B's job (alignment ≠ transfer).

## 11. What ratification means (ADR-013)

The PI approves the freeze (§5 substitutions included), runs the 16 trials, and signs the verdict the
measured deltas produce. Ratification is metadata — it never earns τ; the verdict rides on the audit-derived
numbers alone. A rendered verdict is a legible claim, not a consequence.
