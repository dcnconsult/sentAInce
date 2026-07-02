# Memory Gauge — Controlled-Stream + Gauge Design (STATS-ONLY)

Design draft for the next arc ([[rag-memory-gauge]]). **Stats-only: no claims, no benchmarks, no
verdicts — only data to analyze.** Goal: observe whether a consequence-sourced colony *would* converge
on a controlled, replayable, evolving-app stream — the necessary mechanism-gate before any build.

---

## 1. The controlled stream — an evolving recursive interpreter

A real, hard-enough problem with **built-in recursion** and a **spec change that forces a refactor**,
where we control the narrative. One self-contained Python project (pure stdlib + pytest, runs in WSL),
grown over an ordered, replayable list of **steps**. The sandbox + the colony memory **persist across
steps** (the app accumulates — this is what creates recurrence; unlike the Stage-0 scenarios which reset).

### Step schema (replayable)

```python
@dataclass(frozen=True)
class Step:
    id: str            # "B4_variables"
    goal_class: str    # the KNOWN goal-class label (we control it): add_feature | refactor | run_tests | ...
    prompt: str        # the narrative we feed the agent
    verify: str        # a command WE run after the turn — the ground-truth consequence (not the agent's claim)
    expect: str        # expected verify signal (e.g. "PASS", "120")
```

The stream is a static ordered `list[Step]`; `--replay` re-runs the exact sequence. Determinism is
modulo the model; the *structure* (recurrence, drift, the staleness point) is fixed and known.

### The narrative arc (≈16 steps, 5 phases)

| Phase | Steps | Intent | Why it matters for the gauge |
|---|---|---|---|
| **A · Bootstrap** | 1–3 | scaffold lexer + recursive-descent parser + evaluator (int arithmetic, parens, `^`); pytest harness; a `run(program)` REPL | establishes the project's **recurring sub-tasks** (run tests, add a module) and conventions |
| **B · Feature growth** | 4–9 | variables, comparisons, `if/then/else`, builtins (`abs/max`), **user functions**, **recursive functions** (`fact`, verify `fact(5)==120`) | the `add_feature` goal-class **recurs** 6× with drift → the colony should **converge** on "how this project adds a feature" |
| **C · Breaking spec change** | 10 | SPEC CHANGE: typed values (int/float/bool/string), int division → float, comparisons return bool, string literals — forces a **cross-cutting refactor** and **breaks earlier tests** | the **staleness inducer** (controlled): pre-refactor `add_feature` paths become partly **stale** |
| **D · Post-refactor growth** | 11–14 | lists + indexing, `map`/`filter`, error/`try`, string methods (all under the new typed spec) | the colony must **evict stale** pre-refactor paths and **reconverge** on the new convention |
| **E · Recall probes** | 15–16 | "add another comparison op (`!=`,`<=`)" (revisits B5 **under the new spec**); "add another recursive builtin (`fib`)" (revisits B9) | tests whether the colony recalls the **current** path, not the **stale** pre-refactor one — the hit-utility + staleness probe |

`verify` is always an objective command (`pytest -k <step>` / an `eval(...)` assertion) → the
**ground-truth `exit 0`** consequence, independent of the agent's self-report (the planted-truth
discipline). Known structure: `add_feature` recurs (B+D+E), `refactor` is a singleton (C), and E
deliberately re-enters earlier goal-classes after the spec drift.

---

## 2. The gauge — passive observation, offline colony

**Phase-1 stance: passive.** The agent works **normally** (no memory injection); we only **observe**.
The colony is **simulated offline** over the logged traces — so we learn whether it *would* converge
with **zero behavioral confound**. (Active injection + hit-utility is a later phase, only if convergence
shows.) This is the cleanest "stats only."

### What is logged (raw JSONL, append-only, resumable)

Extends the Exocortex audit into the **P0 decision-trace**, one record per tool-call/decision:

```jsonc
{ "step_id": "...", "goal_class": "add_feature", "session": "...", "ts": "...",
  "cue": "<prompt/context digest>",          // P0 Cue_Context
  "action": "pytest -q", "command_key": "pytest tests",   // P0 Action_Chosen (+ antibody signature_of)
  "gauges": { "energy": 88, "tier": "SATED" },            // P0 Gauge_Readings (reuse Exocortex)
  "outcome": "ok|fail",                       // P0 Outcome (PostToolUse exit 0 / PostToolUseFailure)
  "recalled": ["<memory ids in context this turn>"],      // observed from the transcript/system-reminder
  "step_verify": "PASS|FAIL" }                // the ground-truth step consequence (our verify cmd)
```

Plus a per-step **colony snapshot** (offline-derivable; the analyzer rebuilds it): the pheromone map
`τ[(edge)]` keyed by `goal_class`, deposited only on `step_verify==PASS` traces.

### Stats the offline analyzer emits (descriptive — NO verdict)

| Stat | Definition | Reads as |
|---|---|---|
| **Convergence** | pheromone-entropy of the edge-distribution per `goal_class`, **as a time-series over step instances** | ↓ over B → a stable optimum forms |
| **Segment-reuse** | fraction of this step's `command_key`/edges seen in prior same-`goal_class` steps | the raw material the ant mechanism needs |
| **Staleness** | after step 10: count of previously-high-τ edges that now yield `fail`/`step_verify FAIL`; eviction lag | how fast the killer-risk bites + can it be evicted |
| **Reconvergence** | entropy time-series across C→D→E | does it re-sort onto the new convention |
| **Clutter ratio** | distinct traces vs. the `exit 0` survivor set | how much the slime-mold *would* prune (your "clutter machine," quantified) |
| **Recall-hit (proxy)** | at E15/E16, do the recalled/high-τ segments match the *current* (post-refactor) successful path vs. the stale one | the would-be utility — **confounded, labelled as correlation** |

Output = **time-series + distributions** (entropy-over-steps, reuse-over-steps, staleness curve). No
pass/fail. The data later *designs* the null (e.g. once convergence is visible, the null becomes
"shuffle-τ" or "frequency-deposit" — but we don't pick it until we've seen the shape).

---

## 3. Reuse map (what's built vs. new)

| Piece | Reuse / new |
|---|---|
| stream driver | **generalize `exocortex/runner.py`** → persistent sandbox + ordered steps + `verify` after each turn; `--wsl` already done |
| P0 trace + recall capture | **extend `exocortex/audit.py`** (add `step_id/goal_class/cue/recalled/step_verify`); recall read from the stream-json transcript |
| offline colony + stats | **new `exocortex/gauge/`** — reuses `rag/stigmergic_network.py` (τ deposit/decay), `rag/decoupled_memory.py`, `rag/safe_forgetting.py` (prune), `rag/maze_discovery.py` (widest-path), `rag/epistemic_drift.py` (stale), `brAIn/.../reflex_consolidation.py` (compress) — all standalone numpy, run **offline over the JSONL** |
| the stream itself | **new `exocortex/streams/interp_v1.py`** — the static `list[Step]` |

No model-injection, no MCP, no behavior change. Runs alongside the shipped somatic guard.

---

## 4. Honest scope (stats phase)

- **Mechanism-gate, not regime-proof.** A convergence on this *designed-to-recur* stream shows the colony
  works *when recurrence exists* — necessary, not sufficient for "your real repos converge" (the later
  organic-log question). If it can't converge here, it never will organically.
- **Recall-use is a proxy.** We see recall + outcome, not causal use → reported as correlation.
- **Haiku paces it.** Limits bound stream throughput; the JSONL is append-only → pause/resume, no loss.
- **Stats only.** The engine makes no claim; it produces the dataset a null/experiment is later designed
  from. Local-only.

---

## 5. First build steps (small, when we move from design → build)

1. `streams/interp_v1.py` — the 16-step `list[Step]` (the controlled narrative).
2. Generalize the runner → a stream driver (persistent sandbox + per-step `verify`), stats-only audit.
3. `gauge/analyze.py` — offline colony + the time-series stats over the JSONL.
4. Run the stream in WSL/haiku → inspect the convergence/staleness curves. Just data.

---

## 6. Findings log (stats only — descriptive, no verdict)

### 6.1 First runs (haiku 9/16, sonnet 16/16) — convergence, staleness, the deposit-policy null

- **Convergence (partial):** `add_feature` segment-reuse rises through phase B (haiku 0→1.0, sonnet
  0→1.0), but pheromone-entropy *also* rises (0→4.2) — sub-segments recur, full paths appeared to drift.
- **Staleness (the killer risk, quantified):** after the C10 spec change, of the pre-refactor high-τ
  `add_feature` edges, **haiku 3/5 (60%)** and **sonnet 6/8 (75%)** went stale — large + consistent.
- **The consequence-sourcing null is load-bearing — but only on a FAILING regime.** On haiku
  (`gauge/analyze.py` deposit-policy comparison): consequence (deposit on verify-PASS) → **0% fail-only
  clutter**; frequency (deposit on all) → **32%**; shuffle → 34%. On the perfect sonnet run the null is
  **vacuous** (16/16 PASS → no failed-path clutter exists → frequency == consequence == 0%). So: measure
  the **null on a failing regime**, measure **convergence/staleness on a passing one**.

### 6.2 Granularity sweep (`--sweep`, offline; the #1 surfaced refinement)

The "full paths drift" puzzle was largely a **path-node altitude artifact**: the `fine` keying embeds
the random sandbox temp-path + full argument strings in each bash node, so conceptually-identical paths
never matched. Re-running the offline colony at coarser node altitudes (`fine` = tool+command_key;
`verb` = bash executable + src/test; `tool` = bare tool name) — same audit, no re-run:

| Regime | gran | af reuse_last | af tau_edges (B→end) | freq-null clutter |
|---|---|---|---|---|
| haiku | fine | 0.25 | 6→**24** (never plateaus) | **32%** |
| haiku | verb | 0.63 | 6→19 | 24% |
| haiku | tool | **1.0** | plateaus at **8**, →9 post-refactor | **0%** |
| sonnet | fine | 0.6 | 6→21 | 0% (vacuous) |
| sonnet | tool | 0.8 | 6→12 | 0% (vacuous) |

- **Convergence is real at the conceptual altitude.** Coarsening collapses the drift onto a stable
  optimum — on haiku, `add_feature` reuse_last 0.25→**1.0** and tau_edges plateaus at ~8 through all of
  B. The drift was vocabulary growth from over-fine nodes, not genuine non-recurrence.
- **…but clutter-discrimination dies at the coarsest altitude.** The load-bearing consequence-sourcing
  result needs node specificity to tell a fail-path from a pass-path: haiku frequency-null clutter
  32%(fine)→24%(verb)→**0%(tool)** — at `tool` altitude failed steps use the same 4 tools as passing
  ones, so there are no fail-only edges to keep out. **Convergence wants coarse; clutter-discrimination
  wants fine → `verb` is the operating point** (reuse 0.25→0.63 *and* null still separates 0% vs 24%).
  This is the build-phase key: pheromone on `verb`-level nodes, not raw command strings nor bare tool.
- **Staleness is also altitude-dependent (refinement to 6.1).** Post-refactor reconvergence: haiku
  stale-dropped 60%(fine)→50%(verb)→**0%(tool)**; sonnet 75%→67%→44%. A spec change breaks the *literal
  commands*, not the *procedural skeleton* (Read→Edit→test) — so the killer-staleness risk is partly a
  fine-grained artifact; procedural memory survives a refactor far better than literal-command memory.
- Sonnet `fine`≈`verb` (a clean agent produced little path noise to strip); its null is vacuous at
  every altitude — re-confirms 6.1's "measure the null on a failing regime."

Artifacts: `results/<run>/gauge_granularity.json` (per-run sweep); `--granularity {fine,verb,tool}`
re-analyzes a single altitude (`fine` reproduces the committed `gauge_stats.json` byte-for-byte).

---

## 7. Build phase — the live colony (consolidate on `PreCompact`, splice on `UserPromptSubmit`) (BUILT + verified)

The sweep (§6.2) fixed the operating point, so the colony graduated from offline stats to a **live**
subsystem in the hook, keyed at the **verb altitude**. It is the third (memory) subsystem, orthogonal
to somatic/epistemic Mode — on by default, `EXOCORTEX_COLONY=0` for a pure baseline.

**Mechanism (`exocortex/colony.py` + `hook.py`):**
- **Trail (per-session, `SessionState.trail`):** every `PreToolUse` (any tool) lays a verb-node onto the
  current segment — the path being walked toward the next consequence.
- **Deposit (consequence-sourced, the law):** a Bash `PostToolUse` closes the segment. On a **verified
  `exit 0`** the segment's edges get pheromone (`Colony.deposit`); on failure they are **dropped**. Each
  way the trail resets — so a segment is one unit of work culminating in a verified command. This is the
  symmetric reflex-memory side of the organism (scar = strategy-lock on `exit≠0`; reflex = τ on `exit 0`).
- **Consolidate (the circadian sleep, `PreCompact`):** before transcript compaction the colony decays
  once, prunes the dust, caps to the strongest `CAP` edges (slime-mold leanness), and arms a per-session
  re-splice flag. **`PreCompact` does NOT inject** — see the verified contract below.
- **Splice (the recall, `UserPromptSubmit`):** the consolidated memory rides back into the model as
  `additionalContext` on the next prompt (the *verified* injection channel), throttled to the re-splice
  flag (set on `SessionStart` first-prompt + `PreCompact` wake). The colony lives in `colony.json`, so it
  already survives compaction independent of the transcript — the splice just re-surfaces it.

**Colony = per-project (`state_dir()/colony.json`)** → institutional memory that accrues across sessions.
Self-contained mirror of `rag/stigmergic_network.py` (same DECAY/PRUNE/DEPOSIT) so the hook stays fast
and fails open; the graduation build swaps in the locked module.

**The first live splice (unit-tested, `test_userpromptsubmit_splices_converged_route`):**
```
[exocortex · consequence-sourced procedural memory (verb altitude)]
Routes that have led to VERIFIED success in this repo (pheromone τ; deposited only on exit 0 …):
  Read:src → Edit:src   (τ=3.10)
  Edit:src → bash:pytest (τ=3.10)
Dominant route (greedy widest path): Read:src → Edit:src → bash:pytest
(N successful-path deposits · M edges retained after consolidation)
```
Verified end-to-end through the real subprocess entrypoint (`python hook.py PreToolUse|PostToolUse|
PreCompact|UserPromptSubmit`); 39 exocortex unit tests green, 99-test kernel lock untouched.

**PreCompact contract — VERIFIED (headless capture, 2.1.195, haiku/WSL; `scratchpad/run_precompact.sh`):**
- PreCompact **fires** headlessly (`trigger:"auto"`); forced with `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=0.05`
  + `CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP=1`. Stdin: `{session_id, transcript_path, cwd, hook_event_name,
  trigger, custom_instructions}` (no `permission_mode`).
- **PreCompact `additionalContext` is NOT injected** — a planted un-guessable token returned on PreCompact
  appeared 0× in all model output (incl. post-compaction turns). The original "splice on PreCompact" plan
  was **wrong**; this is why we verified.
- `SessionStart source:"compact"` did **not** fire in the `-p --continue` flow (only `startup`/`resume`).
- **`UserPromptSubmit` `additionalContext` IS injected** (planted token echoed) → the splice channel.
- **The fix (shipped):** PreCompact = consolidation + arm the flag; splice via `UserPromptSubmit`. The
  colony in `colony.json` already survives compaction (off-transcript), so the splice just re-surfaces it.
  See [[claude-code-hook-contract-2-1-195]].

**FULL INTEGRATION — VERIFIED with a live model (headless, haiku/WSL, real `hook.py` wired,
`scratchpad/run_integration.sh`):** a real session where the agent did recurring edit+test work over 5
turns. All four links proven in one run:
1. **Real deposits:** `colony.json` accrued 4 consequence-sourced deposits (on `exit 0`) from real tool
   use, converging on `Edit:src → Edit:test → bash:pytest` (τ=2.22 — the recurring edit-and-test skeleton).
2. **Real compactions:** the audit shows **PreCompact fired 4×** (consolidating each time).
3. **Re-splice via the verified channel:** `UserPromptSubmit injected=True` on 4 prompts (not turn 1, when
   the colony was empty).
4. **The live model received it:** on the probe turn it quoted, verbatim, `Dominant route (greedy widest
   path): Edit:src → Edit:test → bash:pytest` — matching `colony.json` computed independently. The 4
   compactions wiped the earlier turns, so the route is in context only via the **fresh re-injection from
   off-transcript `colony.json`** — the mechanism, confirmed.

---

## 8. Accrual on the REAL repo — findings (the near-negative that frames the pivot)

8 varied realistic haiku tasks (git, pytest, search, analyzer, write+run, grep) as separate sessions over
a detached worktree of this repo, hook wired **deposit-on / splice-off** (so injected memory doesn't nudge
tool choices), `colony.json` snapshotted per task (`scratchpad/run_accrue.sh`).

**Result: the colony learned almost nothing — 4 edges from 8 tasks, every edge n=1 (τ≤1.0), zero
convergence.** Audit-confirmed mechanism:
- An edge needs a **non-bash tool immediately before a successful bash** (with no intervening bash). So
  **4/8 tasks deposited NOTHING** — they were single commands (`git log`, `pytest`, `git status`,
  `find|wc`): one node, no edge. The 4 that deposited were all (tool→bash✓) two-steps: `Agent→find`,
  `Read→ls`, `Write→python3`, `Read→grep`.
- **Failures discard the whole segment** and **bash→bash workflows never chain** (the trail resets to `[]`
  at each consequence): the `analyze` session ran 7 bash calls (2 failed) yet deposited only one two-step.

**Interpretation (this CONFIRMS the original bet — procedural skills YES, varied/one-shot NO):** the toy
`interp_v1` converged beautifully because every step was a repeating `Read→Edit→Bash(pytest)` 2-edge
segment; real mixed work is mostly **one-shot and varied**, so the colony is sparse + unconverged. The
value is regime-dependent: the colony shines on **repeated procedural skills**, and is near-blind to
one-shot/novel work. Convergence needs **(a) repetition of similar tasks** and **(b) a deposit model that
captures more than the (tool→bash) two-step.** Caveats: haiku tends to one-shot commands (a stronger agent
may chain more steps → richer edges); a single varied session has no repetition → no convergence *by
construction* — longitudinal volume of *similar* tasks is the real test.

---

## 9. PIVOT PREP — live cue-classifier (+ the deposit-model fixes §8 demands)

The §8 data shows the cue-classifier alone is insufficient: even with perfect goal-class labels, the
current edge model barely deposits on real work. Sequence the pivot:

**P-A · Deposit-model fixes (so real work leaves a trace).** Tie deposits to the *cue*, not just the
tool path:
- **Cue→first-action edge:** seed each segment's trail with a `cue:<goal_class>` node derived from the
  prompt, so even a one-command task forms an edge (`cue:test → bash:pytest`). This simultaneously fixes
  the "single-command = no edge" hole AND binds every deposit to its goal-class (the classifier's output
  becomes the trail's root).
- **Credit the success path through failures:** don't discard the whole segment on a failed sub-step —
  keep the pre-failure prefix (the eventual success should still credit the work that led to it; the
  failure is already a scar via strategy-lock).
- **Chain bash→bash:** reset the trail to `[last_node]` (not `[]`) at a consequence so multi-command
  workflows (`edit → test → commit`) deposit.

**P-B · The cue-classifier.** The prompt is available on `UserPromptSubmit` — label each segment's
goal-class from it. Candidates, cheapest first: (1) keyword/regex over the prompt (transparent, no model
call); (2) small embedding + nearest-centroid over a discovered class set; (3) reuse the epistemic
vocabulary. **Per-class colonies** → similar tasks converge together; the splice surfaces the *matching
class's* memory. **Abstain (no inject) when the cue matches no converged class** — never inject stale on
novel work (the v1.07/v1.08 anti-clutter discipline carried forward).

**P-C · Longitudinal accrual.** Opt-in persistent wiring on this repo (deposit-on; splice gated) to gather
real volume; recompute the gauge stats (entropy↓ / reuse / staleness / clutter) over the *live* colony
over time — the first real-world convergence measurement.

**Open design Qs to settle at pivot:** cue granularity (per-prompt vs per-task); class vocabulary (fixed
list vs discovered by clustering the cues); splice trigger (every prompt vs the re-splice flag); the
protected-set so a converged reflex can't be eroded by repeated consolidation decay.

**State at pause:** colony BUILT + verified end-to-end (deposit→PreCompact-consolidate→UserPromptSubmit-
splice, across real compaction); contract empirically nailed; `EXOCORTEX_COLONY` / `EXOCORTEX_COLONY_SPLICE`
switches in place; 40 exocortex tests green; 99-lock untouched. Ready for the P-A→P-B build.

---

## 10. Cue-classifier build — DISCOVERED classes (P-A + P-B shipped)

Built P-A (deposit-model fixes) + P-B (the classifier) together — the classifier's label IS the trail's
`cue:` root, so they're one mechanism. **`exocortex/cue_classifier.py`** = online **leader clustering**
(single-pass, threshold) over the `UserPromptSubmit` prompt: no fixed class list — classes EMERGE; a cue
farther than `THRESHOLD` (0.30) from every centroid seeds a new one. Stdlib-only (no embedder) → hook-fast,
fails open. The label keys a **per-class colony** (`colony_<label>.json`) and seeds `st.goal_class`.

**P-A fixes in `hook.py` (the §8 gaps closed):**
- `UserPromptSubmit` classifies → `st.goal_class = label`, `st.trail = [cue:<label>]`.
- `PostToolUse` deposits the path into **that class's** colony; re-roots to `[cue, last_cmd]` on success
  (chains `edit→test→commit`) / `[cue]` on failure (drops the failed tail).
- The cue root means a **one-command task now deposits** (`cue:<class> → bash:git`) — confirmed on the
  exact case (`git log`) that deposited nothing in §8.
- `UserPromptSubmit` splices the **matching class's** memory; triggers on the re-splice flag (first prompt
  / post-compaction wake) OR a **task-class switch**; **abstains** on a novel/unconverged class
  (`MIN_DEPOSITS_TO_SPLICE`=2) — the anti-clutter discipline.

**Tuning finding (important):** the obvious **TF-IDF cosine clusters BACKWARDS** for intent — IDF
penalizes the recurring task-verbs ("add", "run", "test") that *are* the goal-class signal and rewards the
variable content nouns, so 10 prompts → 10 singletons. Fix: **raw-TF cosine** (task-verbs count) + light
**stemming** (tests→test); IDF kept ONLY to pick distinctive *labels*. Result on realistic prompts: 3
feature/test prompts → one class, 2 git prompts → one class, refactor/docs/search each distinct.

**Verified end-to-end (subprocess, no model):** two task families → two discovered classes →
`colony_add-new#0` (cue→Read→Edit→bash:pytest, 3 deposits) and `colony_investigate-git#1` (cue→bash:git,
3 deposits — the single-command deposit that §8 missed); a same-class prompt splices that class's route.
**47 exocortex tests green** (3 classifier + per-class colony + P-A single-command/chain/abstain); 99-lock
untouched.

**Honest limit:** lexical clustering captures *phrasing* similarity, not deep semantics — true paraphrases
with no shared words (e.g. "run the unit tests" vs "execute the spec suite") won't merge without an
embedder. In practice recurring tasks share phrasing, so it provides value; the upgrade path is a local
embedding or an epistemic-vocabulary canonicalization layer over the tokens.

**Next:** P-C longitudinal accrual on this repo with the classifier live (deposit-on, splice-gated) to see
whether real recurring work converges per-class over volume; the protected-set; embedding upgrade if the
lexical limit bites.

---

## 11. HDC Episodic Memory-Palace (P-D) — frozen-kernel gauge + honest synthesis

**The mnemonic→HDC mapping is real and ALREADY in the frozen kernel.** A "memory palace" (loci + action-on-
object + sequence) maps 1:1 onto `freqos.tam` (`bind`=phase-add mod 3, `permute`=cyclic-shift = the Π
sequence, `bundle`=phasor-majority) and `freqos.phase_router`, which already implements + *falsified-tests*
the exact claim: **context-keying disambiguates a node REVISITED with two successors that a stateless bundle
cannot** (stateless superimposes → ~0.5). `encode_transition(ctx, src, succ)` + `build_router` (bundle) =
the palace; `recall_successor(router, ctx, src)` = the **JIT next step**. So P-D reuses the kernel, not a
reimplementation.

**Offline gauge — `exocortex/gauge/palace_gauge.py` (STATS ONLY, real kernel, no model):** routes for
several goal-classes (with deliberate cross-class collisions: a shared `bash:pytest` source with divergent
successors) bundled into one router; context = `bind(room, permute(c0, step))`.

| Claim | Result | Honest read |
|---|---|---|
| **A · Separation** | room-context **1.0** vs stateless **0.947** (Δ+5.3pp) | real but **modest** at low load — fixes the one ambiguous transition; grows with collisions |
| **B · JIT next-step** | **1.0** within capacity | the permutation Π recovers the *next* node, not the whole route |
| **C · Capacity** | knee at **T/M ≈ 0.1** (M=1024 → ~100 transitions; M=10000 → ~600 @ 95%) | **"cancels to exactly zero" is FALSE** — bounded crosstalk with a real cliff; scales linearly with M |
| **D · Failure mode** | overload → `no_basin`↑0.78, `wrong_route` ≤0.023 | **degrades by ABSTAINING, not hallucinating** — exactly the anti-clutter law |

**The synthesis (what HDC actually buys us — refined by the gauge):**
1. **Cross-class separation is ALREADY solved** by the shipped per-class colonies (a hard partition; one
   structure per discovered class → zero cross-class load). HDC's global-soup separation (Claim A) is a
   *re-derivation* of what per-class files already give, and it's capacity-bounded — so a global palace is
   NOT an upgrade over per-class partitioning.
2. **The genuine new value is sequence-aware JIT next-step injection (B+Π).** The current edge-dict colony
   splices the *whole dominant route* every time; an HDC per-class router would let `UserPromptSubmit`
   inject only **the single next action** given where the agent is (`recall_successor` keyed by the last
   node) — far less context bloat, the user's "JIT context" win. This is the part the dict-colony can't do.
3. **Safe by construction (D)** — overload abstains, matching the consequence-sourcing anti-clutter law
   (the user's "cortisol→consequence" contrast: we never need bizarre-imagery salience; the `exit 0`
   write-gate + the kernel's graceful no-basin failure together keep the memory honest).

**P-D placement (after P-C):** keep per-class partitioning for separation; adopt the HDC router **inside
each class** to encode the route SEQUENCE and serve JIT next-step. Gate: this gauge (passed: separation +
safe overload) **plus** P-C volume showing routes long/recurring enough that "next-step" beats "whole
route." Use native M (≈10⁴) or per-class routers to stay well under the T/M≈0.1 knee. Open: position
tracking for the unbind cue (the trail already carries the last node); decay/consolidation in HDC space
(the kernel's palimpsest write-rules, `episodic_memory.py`, map onto the circadian prune).
48 exocortex tests green (incl. a kernel-guarded palace-gauge smoke test); 99-lock untouched.

---

## 12. P-C — longitudinal accrual on the real repo, classifier LIVE (the first real-world convergence measurement)

20 real haiku sessions over a detached worktree (`scratchpad/run_pc.sh`): 4 recurring task-classes ×
5 interleaved instances, hook wired **deposit-on / splice-off** (so injection doesn't nudge tool choices),
`colony.json` snapshotted per task. Phrasing kept a stable per-class anchor (recurring tasks recur in
phrasing); the synonym-varied version fragments — the §10 lexical limit, re-confirmed offline.

**Findings:**
1. **Convergence is REAL on recurring work** (the original bet, now on real tool use): `run-git#0` → 1 edge
   (`cue→bash:git`), `grep-code#2` → 1 edge, `find-python#1` → 2 edges — **flat from instance 1** across all
   20 snapshots (tasks 5–11 added **zero** new edges = pure reinforcement, τ grew to ~4–6).
2. **Clean cross-class separation** — 4 distinct per-class colonies despite interleaved arrival; the
   classifier + per-class partition prevented any cross-contamination.
3. **But real routes are SHORT** — 1–2 edges (`cue→bash:verb`). The learned "skill" is minimal → reinforces
   that the HDC sequence-encoding (P-D) only pays off for the rare long route; most recurring repo tasks
   don't have one.
4. **NEW failure mode — a single thrashing session pollutes its class.** Task 12 (`rc=1`, hit max-turns:
   7 Bash + 2 Read flailing) dumped **11 edges** into `read-config#3` in one go, because each sub-command
   returned `exit 0`. **Per-command consequence-sourcing does not filter a flailing-but-succeeding
   session** — the class's route never restabilised (it ended at 14 edges vs the clean 2).
5. **The colony self-heals, but slowly.** Offline replay of clean instances onto the polluted class: thrash
   edges decay (max τ 2.82→0.47 over +20 clean sessions) and the **splice recovers fast** (it reads top-k,
   so the clean dominant route resurfaces within a few sessions) — but FULL eviction needs ~66 clean
   re-deposits (the prune floor 1e-3 is too low). Refinements surfaced: a **higher prune floor** /
   **per-class CAP** applied at consolidation; or **session-quality-weighted deposits** (a max-turns/`rc≠0`
   session deposits less); or a **per-session route-summary** deposit instead of per-command edges.

**Verdict (stats only):** the colony genuinely learns + separates recurring procedural skills on real work,
and self-cleans over volume — but (a) real routes are short (limits the P-D payoff) and (b) a single
thrashing session is the live clutter source the per-command `exit 0` gate misses. Next: pick one
clutter-control refinement (prune-floor or session-quality weighting) before P-D; then P-D's JIT next-step
only where routes are long enough to warrant it.

---

## 13. Session-quality-weighted deposit (the P-C clutter-control refinement) — BUILT

A flailing session is the live clutter source (§12, finding 4). Fix: `Colony.deposit(edges, weight)` now
scales by a **session-quality weight** in `[WEIGHT_MIN, 1.0]` (`hook._deposit_weight`), grounded in two
consequence signals available at deposit time:
- **Activity discount** `SESSION_DECAY**session_deposits` (0.8ᵏ): a focused task lays 1–2 deposits at
  ~full weight; a flailing session's later, wandering deposits are discounted. This catches the all-`exit 0`
  thrash (the max-turns case the failure-rate signal can't see). `session_deposits` is per-session
  (`SessionState`, reset on `SessionStart`).
- **Success-rate discount**: a success *amid failures* (oks/total over the session history) is weaker
  evidence than one in a clean run.

A flailing session's clutter is thus **born near the prune floor and self-cleans fast**.

**Measured on the actual P-C thrash (task-12 replay, real audit):**

| | clutter edges | total mass | worst edge τ | clean sessions to evict worst |
|---|---|---|---|---|
| unweighted (old) | 12 | 11.22 | 1.90 | 72 |
| **session-weighted (new)** | 12 | **5.69** (−49%) | **0.89** (−53%) | 65 |

**Honest read:** weighting **halves the clutter mass and the worst clutter edge**, so it sits far below a
converged route (τ≈4) → **the splice (top-k + dominant route) stays clean** (the practical win). It does
NOT reduce the edge *count* or evict the dust to the floor — that needs the complementary **prune-floor /
per-class CAP** lever (logged in §12). No harm to legit recurring multi-step routes: each session's *first*
deposit is full weight, so a route that recurs still accumulates (head strongest, tail softer — a sensible
confidence gradient). 52 exocortex tests green (deposit-weight function + scaling + reset + flail-born-weak);
99-lock untouched.

---

## 14. Prune-floor / CAP bump (completing the clutter-control story) — BUILT

The §13 weighting halves clutter *mass* but not *count*; the dust still lingers to the old `PRUNE=1e-3`
floor (~65 class-uses). Why the prune floor is the right second lever (not CAP): it is **value-based**, so
it leverages **RECURRENCE** — a non-recurring clutter edge decays out, a recurring route is re-deposited
and survives. CAP is count-based and can't distinguish a rich legit route from clutter (both ~14 edges in
P-C). Key constraint: PRUNE must stay **below `WEIGHT_MIN` (0.1)** or a legitimately session-weighted
deposit would be pruned before it could be reinforced.

Changes (`colony.py`): **`PRUNE` 1e-3 → 0.05** (the eviction lever; safely below `WEIGHT_MIN`), **`CAP`
64 → 32** (a generous per-class count ceiling at consolidation — a safety bound, not the clutter fix).

**Measured (task-12 thrash replay) — the full clutter-control arc:**

| stage | clutter mass | worst edge τ | eviction (class-uses) |
|---|---|---|---|
| P-C reality (unweighted, 1e-3) | 11.22 | 1.90 | 72 |
| + session-weighting (§13) | 5.69 (−49%) | 0.892 | 65 |
| **+ prune-floor bump (0.05)** | 5.69 | 0.892 | **28** (2.3× faster) |

A non-recurring min-weight edge (born 0.1) now evicts in ~7 unrefreshed class-uses; a recurring one
(re-deposited each use) survives (0.1 ≥ 0.05). **Honest residual:** a thrash that reinforces an edge
*within its own session* makes it moderately strong (not single-weak), so eviction is gradual (~28 uses for
the worst), not instant — but the splice was already clean from §13 throughout (clutter τ≤0.89 ≪ route ≈4).
The two levers compose: weighting → splice clean *now*; prune floor → file clean ~2.6× sooner. 52 exocortex
tests green; 99-lock untouched. **Clutter-control story closed; next decision is P-D (narrow, only where
routes are long enough).**

---

## 15. Embedding cue-classifier — the semantic upgrade (fixes the §10/§12 lexical limit)

The lexical classifier fragments paraphrased recurrence (synonyms share no salient tokens). Upgrade
(`exocortex/embed_classifier.py`): a local **MiniLM** embedding → L2-normalised dense vector; a new cue is
matched to the nearest per-class **centroid** by cosine with the v0.69 `ssr_rag._retrieve` **abstain
logic** (top-1 overlap + top1−top2 margin) — MATCH → route to that class (the paraphrase shares the trail);
semantic VOID → seed a new class. Mirrors the `CueClassifier` API; the hook (`_classify_cue`) uses it when
opted in and available, else the lexical one.

**Head-to-head on the adversarial synonym set (the case that fragmented in §12):**

| classifier | clusters (4 intended) | consolidation |
|---|---|---|
| lexical (TF) | **12** | all 4 classes shattered (git→3, find→3, grep→5, read→2) |
| **embedding (MiniLM)** | **5** | git/find/read **perfectly merged**; grep’s residual blend into "read" is semantically defensible |

**VERIFY-AGAINST-THE-KERNEL — the directed Z3 bridge was MEASURED and dropped.** The plan was
`embed → whiten_capacity.quantile_z3 → ssr_rag._retrieve` (reuse the frozen Z3 retrieval). Measured on
MiniLM embeddings: ternary per-column quantisation **collapses class separation — intra/inter cosine gap
0.367 → 0.029** (it guts the continuous geometry the similarity lives in). So the match runs on the **dense**
vector and reuses only the kernel's **overlap+margin abstain mechanism**, not its Z3 codes. (Re-open if a
higher-resolution VSA encoding — e.g. random-projection-then-quantise — is found.)

**Knobs:** `EXOCORTEX_EMBED_MATCH` (cosine match floor, default 0.30), `EXOCORTEX_EMBED_MARGIN`
(top1−top2 commit gate, default 0 = off), `EXOCORTEX_EMBED_MODEL` (default `all-MiniLM-L6-v2`).

**Honest costs / status:** heavy deps + a model load per hook *process* (~1–2 s) → **opt-in**
(`EXOCORTEX_EMBED=1`), default off. **Fail-open:** absent/failed import → the hook silently uses the
lexical classifier. The live **WSL** hook surface does **not** have `sentence-transformers` yet, so live
embedding mode needs a one-time `pip install sentence-transformers` in WSL; until then the hook auto-falls
back to lexical (no breakage). Built + verified on Windows python: 56 exocortex tests green (paraphrase
merge/split, roundtrip, hook-routes-when-enabled, hook-falls-back-when-off); 99-lock untouched. Full
calibrated abstain (isotonic margin→P(correct), v0.69) is the next refinement — it needs a labelled
calibration set, so a fixed margin is the v1 knob.

**LIVE-VERIFIED (haiku/WSL, `EXOCORTEX_EMBED=1`, real model, `scratchpad/run_embed_live.sh`):** 2 intents ×
3 synonym-varied paraphrases interleaved → `embed_cues.json` discovered exactly **2 classes** (`run-quick#0`
size 3 = the python paraphrases; `show-most#1` size 3 = the git paraphrases), and **2 pure per-class
colonies** (`cue→bash:python3`, `cue→bash:git`). No lexical `cues.json` was written → the embedding path
ran live. The lexical classifier would have fragmented the same 6 paraphrases into ~6 colonies; embedding
consolidated them to 2. The semantic upgrade works end-to-end on the real WSL hook surface.

---

## 16. The Genome — central JSON config (`exocortex_config.json`)

Every tuning knob, previously scattered across modules, now lives in one **Genome** file so longitudinal
R&D can re-tune the organism without touching code. `exocortex/genome.py` is the factory loader:
verified **DEFAULTS** in code, deep-merged with a located `exocortex_config.json` (searched
`$EXOCORTEX_CONFIG` → `$CLAUDE_PROJECT_DIR` → package dir). Precedence per knob: **env var > genome JSON >
code DEFAULTS**; a missing/malformed file falls back to the verified defaults (fail-safe, backward
compatible). Sections: `thermodynamics` (colony: decay, prune_floor, deposit_base_weight,
session_discount_rate, weight_min, max_edges_per_class, min_deposits_to_splice), `epistemic_classifier`
(mode, model, abstain_threshold_cosine, match_margin), `somatic_gate` (mode; `enforce`→`somatic` alias).

`colony.py` / `embed_classifier.py` / `config.py` now source their constants from `GENOME` (kept as module
attributes so tests still monkeypatch). **Embedding is the LIVE DEFAULT** (`epistemic_classifier.mode =
"semantic"`). Verified end-to-end: a fresh process with `EXOCORTEX_CONFIG` set picks up `prune_floor`/`CAP`/
`abstain_threshold` overrides while untouched keys keep defaults (deep merge). **Threshold note:** the
shipped `abstain_threshold_cosine` is **0.45** — measured clean on realistic AND adversarial paraphrases;
the suggested 0.65 fragments adversarial paraphrases (4 clusters), so 0.30–0.45 is the verified range.
60 exocortex tests green (genome defaults / file-override+fallback / somatic-alias / embed-default);
99-lock untouched.
