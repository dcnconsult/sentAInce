# Pre-registration: failing suggestions (avenue 2) — how often does a spliced route fail, and does it persist?

**Frozen:** 2026-10-26, committed before the gauge is written or run. **Kind:** experimental-design.
**Gauge:** `exocortex/gauge/failing_splice_gauge.py` (read-only replay over audit JSONL, stdlib).

## 1. Question

The colony deposits τ only on a verified exit 0, and decay is clocked by **successful** deposits in a class,
plus one pass per sleep (`colony.py` `deposit`/`consolidate`). A failure moves nothing. So when the route the
splice recommends starts failing, nothing in the memory registers it. The route keeps being offered until
other successes in that class, or sleeps, erode it.

The landscape scan (2026-10-26) adds two pressures:
- the field converges on failure-aware memory (a success-only strategy lost to a reflexion-style one);
- a greedy single-path readout behaves like Physarum's μ>1 lock-in regime.

**Questions:**
1. How often is a spliced route followed and then **fails** at its first route command (the *contradiction
   rate*)?
2. Is that more than those same verbs fail off-route (the *excess*)?
3. After a contradiction, does the same route keep being spliced (*persistence*)?

A read-side "failing" marker (R5-like: no τ write, ADR-004 untouched) is worth designing only if all three
are non-trivial.

## 2. What has already been seen (disclosed before freezing)

Today's audits were read for other gauges (R1a, R4) and the estate overlap probe. **None of the measures
below has been computed.** Known structure: `UserPromptSubmit` rows carry `injected` (bool) and `reason`
(`class=…`), but **not which route was spliced**. Hence the replay.

## 3. Replay model (frozen)

Per store, in file order, mirroring `hook.py` and `colony.py`:
- **Trail:**
  - `UserPromptSubmit` sets the session's class (from `reason`, `class=<label>`) and resets the trail to
    `[cue:<class>]`.
  - `PreToolUse` appends `verb_node(tool, command)`.
  - `PostToolUse` / `PostToolUseFailure` on Bash or PowerShell closes the segment. Outcome is `ok` only when
    `event == PostToolUse` and `outcome == ok`.
  - After `ok`: deposit the segment's edges (self-edges dropped) into the class colony, then re-root to
    `[cue, node]`. After `fail`: re-root to `[cue]`.
- **Colony:**
  - Each deposit multiplies all of the class's edges by 0.9, adds 1.0 per path edge, and prunes below 0.05.
  - `PreCompact` and `CircadianSleep` rows consolidate every class: one 0.9 pass, prune below 0.05, cap at
    the strongest 32.
  - **Approximations, disclosed:**
    - every deposit has weight 1.0 (the live session discount is not reproduced);
    - endocrine and eligibility are off, as shipped;
    - readout is raw τ (recency was local-only on this repo before 2026-10-26).
- **Keying:** `first` for every store, except this repo from the R0 flip epoch `1789583027` onward, where it
  is `working` (what was live).
- **Spliced turn:** a `UserPromptSubmit` with `injected == true`, whose class colony has ≥2 deposits
  (`MIN_DEPOSITS_TO_SPLICE`), and whose dominant path (greedy widest walk from the strongest edge, ≤6 nodes,
  as in `Colony.dominant_path`) contains ≥1 **command node** (`bash:` / `ps:`).
- **Turn:** the rows of that session after the prompt, up to its next `UserPromptSubmit`.

## 4. Metrics (per store)

- **N:** spliced turns.
- **F `follow_rate`:** the share of spliced turns in which some command consequence's node is a command node
  of the dominant path. The **route command** is the first such consequence in the turn.
- **X `contradiction_rate`:** among followed turns, the share whose route command failed.
- **E `excess`:** verb-stratified `X_v − B_v`, weighted by followed turns per verb. `B_v` is the failure rate
  of the first consequence of verb `v` in turns where `v` is **not** a command node of a spliced dominant
  path (unspliced turns included). Verbs without an off-route stratum are dropped and counted.
  **CI:** session-cluster bootstrap, 1,000 resamples, seed `20261026`, percentile 95%.
- **P `persistence`:** for each contradiction, the number of later spliced turns in the same class whose
  dominant path equals the contradicted one, counted until it first differs. Report the median, and the
  share with P ≥ 2.
- **Descriptive:** the share of contradictions followed by a class deposit before the next spliced turn.

## 5. Decision rule (frozen)

**Evaluable store:** ≥30 followed turns. **Stores:** every estate state dir plus the research vault
(labelled `research-vault`, the lab labelled `lab`).

- **+1 (design a dormant read-side "failing" marker; gauge it before building):** on ≥2 evaluable stores,
  all of `X ≥ 0.10`, E's CI lower bound `> 0`, and median `P ≥ 2`.
- **−1 (park avenue 2: failing suggestions are rare, or are ordinary failure noise):** ≥2 stores are
  evaluable, and on **every** evaluable store, `X < 0.05` **or** E's CI upper bound `≤ 0`.
- **0:** anything else, including fewer than 2 evaluable stores.

## 6. What this cannot show

- The replay is approximate (§3), so its dominant path may differ from the one actually spliced. The
  go-forward splice stamp (proposed alongside this gauge) exists to remove that error.
- A route command failing does not prove the route is wrong. That is why E is measured against the same
  verbs off-route.
- No efficacy: a marker's effect on reaching `exit 0` would need its own gauge.

## 7. Output

`results/failing_splice_v1/RESULTS.md` plus an aggregate-only JSON (store labels and numbers; no command
text, class labels or paths).
