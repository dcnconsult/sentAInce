# Exocortex — Core Concepts & Architecture

The conceptual spine of the system. For features see [FEATURES.md](FEATURES.md); to operate it see
[USERS_GUIDE.md](USERS_GUIDE.md); for the science see [WHITEPAPER.md](WHITEPAPER.md).

---

## The organism

The Exocortex models an agent's cognition as a small organism with three subsystems, all governed by one
**Genome** (`exocortex_config.json`) and wired into the Claude Code hook lifecycle by a single synchronous
Python program (`exocortex/hook.py`). There is no daemon; each hook event is a fresh process.

```
                         ┌──────────────────────── the Genome (exocortex_config.json) ───────────────────────┐
   user prompt ─▶ UserPromptSubmit ──▶ [EPISTEMIC] classify cue → goal-class ; SPLICE that class's memory
                                       seed trail = [cue:<class>]
   tool call   ─▶ PreToolUse ────────▶ [SOMATIC] veto destructive? ; lay verb-node on the trail
   tool result ─▶ PostToolUse(exit 0)▶ [THERMODYNAMIC] DEPOSIT the trail's edges into colony_<class>.json
                  PostToolUseFailure ─▶ drop the segment (scar via strategy-lock)
   compaction  ─▶ PreCompact ────────▶ [THERMODYNAMIC] CONSOLIDATE (decay/prune/cap) — the circadian sleep
```

## The three subsystems

- **Somatic gate** — a model-independent `PreToolUse` veto on lethal/destructive commands (reuses the
  locked immune-system gate). Safety; pre-dates the memory work.
- **Epistemic classifier** — turns the *cue* (the user prompt) into a **discovered goal-class** (no fixed
  list; classes emerge). Default = semantic (MiniLM embedding + centroid match with a novelty-abstain);
  fallback = lexical TF. The label keys the colony and roots the trail.
- **Thermodynamic colony** — per-class pheromone (`τ`) over **decision-edges**, the memory itself.

## Core laws

1. **Consequence-sourcing.** Pheromone is deposited *only* on a verified `exit 0`. Never on novelty,
   recency, or frequency. (Symmetric: failures form *scars*, successes form *reflexes*.)
2. **Abstain on novelty.** A new/unconverged goal-class injects nothing — never surface stale memory on
   novel work (the anti-clutter discipline). Concretely: splice only after a class has repetition
   (`min_deposits_to_splice`), and the classifier seeds a *new* class rather than forcing a false merge.
3. **Fail open.** A hook must never crash the agent. Every error path falls through to allow / no-op /
   lexical fallback.
4. **Verify against the substrate.** Hook contracts and kernel behaviors are *measured*, not trusted from
   docs (the docs were wrong twice).

## Key representational choices

- **Verb altitude.** Nodes are `bash:<executable>` (e.g. `bash:pytest`) and `Read|Edit|Write:src|test|other`
  — not raw command strings. Measured: this is the altitude where recurring work converges while clutter
  remains discriminable.
- **Edges, not nodes.** Memory is over *transitions* (`cue:<class> → Read:src → Edit:src → bash:pytest`).
  The `cue:` root means even a one-command task forms an edge, and binds every deposit to its class.
- **Per-class colonies.** One `colony_<class>.json` per discovered goal-class → similar tasks converge
  together; cross-class contamination is structurally impossible.
- **Off-transcript state.** The colony persists on disk, independent of the conversation, so it survives
  compaction; recall is re-injected via `UserPromptSubmit` (the verified channel).

## Lifecycle of a memory

1. **Birth** — a tool-path culminates in `exit 0` → its edges get pheromone, weighted by *session quality*
   (a focused task deposits at full weight; a flailing session's later deposits are discounted).
2. **Reinforcement** — recurring routes are re-deposited each time the class is used; `τ` climbs.
3. **Evaporation** — every deposit decays all edges; non-recurring (clutter) edges fall below the
   `prune_floor` and are forgotten; recurring edges survive.
4. **Consolidation** — `PreCompact` decays/prunes and caps each class to `max_edges_per_class` (leanness).
5. **Recall** — on a matching cue, the class's dominant route is spliced into context.

## Latent organs (gauge-first; ship dormant)

Two further organs are **built, gauge-verified, and wired — but default OFF** behind Genome flags, because on
flagship models their measured prize is null-to-modest. The discipline is explicit: *gauge offline → wire
dormant → size the prize on a real accrual → flip only if the bar is cleared.* Each is a strict no-op until
its flag is set, so the verified baseline behaviour is preserved.

- **Endocrine — allostatic thermodynamics** (`endocrine.mode: off | tier`). Makes `prune_floor`/`max_edges`
  functions of the metabolic **tier** (SATED/STARVING/HYPOXIA, from the interoceptive energy gauge) instead
  of static constants: under stress the prune floor rises and the cap falls (tunnel-vision — shed
  exploration); when sated, the reverse (dream). Gauged **SAFE** (never evicts a converged or marginal real
  route at the shipped envelope) but a **modest** clutter lever — `decay` already does most of the work; the
  stronger-but-double-edged lever is the cap, whose safe floor sits above the skeleton size.
- **Eligibility trace — credit assignment** (`eligibility_trace.mode: off | trace`). Weights each deposited
  edge by recency-to-consequence (`γ^Δ`) so the step that immediately preceded `exit 0` crystallizes and the
  flail prefix fades, instead of crediting the whole segment uniformly. Gauged to isolate the "ah-ha" and
  evaporate the panic — but the *deposit window* is structurally short because the trail **re-roots at every
  verified Bash**, so on real accruals (haiku **and** sonnet, identical) it is a no-op on ~74 % of deposits:
  median segment 2, ~26 % ≥ 4. Deposit-window length is architectural, not model-driven.

The recurring lesson both organs teach: the colony's core laws (consequence-sourcing, recurrence-eviction)
already capture most of the available signal, so added organs are deliberately small, reversible, and dormant
by default. On world-class flagship models, any net improvement is the achievement; null is the expected case.

## Module map

| Module | Role |
|---|---|
| `genome.py` + `exocortex_config.json` | the Genome (all knobs) + factory loader |
| `hook.py` | the single hook dispatcher (deposit / consolidate / splice / veto) |
| `colony.py` | per-class pheromone (deposit/consolidate/splice), verb-node keying |
| `cue_classifier.py` | lexical (TF) discovered-class classifier |
| `embed_classifier.py` | semantic (MiniLM) classifier + novelty-abstain (the default) |
| `state.py` | per-session state (trail, goal-class, energy/tier, session-deposit count) |
| `endocrine.py` | allostatic levers — `(prune, cap)` as a function of metabolic tier (organ 3A, dormant) |
| `somatic.py` / `epistemic.py` / `interocept.py` | the safety/epistemic engines (reused) |
| `gauge/` | offline mechanism-gates — stats-only (`analyze`, `palace_gauge`, `endocrine_gauge`, `eligibility_gauge`) |
