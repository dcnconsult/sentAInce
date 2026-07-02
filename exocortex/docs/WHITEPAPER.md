# The Exocortex: Consequence-Sourced Procedural Memory for LLM Agents

**A technical whitepaper.** Status: research-stage, end-to-end verified on a single repository with a small
model (haiku) + a local embedder (MiniLM). All quantitative claims below are measured; honest negatives are
stated as such.

---

## Abstract

An LLM agent's context window is a finite, flat store — functionally a low-capacity LRU cache. Across a long
session or many sessions it forgets the *procedures* that have actually worked. The **Exocortex** is an
external, self-maintaining procedural memory that lives outside the model weights and outside the transcript,
accreted by **consequence-sourcing**: a route through the agent's tool-calls earns pheromone *only* when it
produces a verified success (`exit 0`), never on novelty or frequency. It is implemented as a synchronous
local Python program wired into Claude Code's hook lifecycle, reusing a frozen Hyperdimensional-Computing
(HDC) kernel and an immune-system "somatic gate." This document describes the mechanism, the empirical
results that validate (and bound) it, and the honest limitations.

---

## 1. Problem

- **Flat, finite context.** Working memory for an LLM is the context window: unordered, capacity-bounded,
  evicted by recency. Long agentic loops overflow it; compaction discards the middle.
- **No procedural memory.** Existing options are weak: a hand-maintained flat `MEMORY.md` (no consequence
  signal), RAG-dump retrieval (novelty-sourced → clutter), or fine-tuning (static, expensive). None capture
  *"the sequence of actions that verifiably worked for this kind of task in this repo."*
- **Clutter actively harms.** Injecting irrelevant or stale context degrades performance — so a memory that
  accumulates everything is worse than none.

## 2. Approach: stigmergy with a consequence gate

The design borrows from ant-colony optimization and slime-mold networks: many wandering paths, pheromone
that **converges** on the optimum and **evaporates** off the rest. The crucial adaptation for an LLM (which
has no cortisol/salience signal) is the **write gate**:

> **Consequence-sourcing law.** Deposit pheromone on a decision-path **iff** it culminated in a verified
> `exit 0`. The symmetric organism: a *scar* ("never do this") forms on `exit≠0` (the somatic veto +
> strategy-lock); a *reflex* ("do this") forms on `exit 0` (the colony). Same plumbing, opposite consequence.

This is the anti-clutter mechanism: novelty/frequency never write, so the memory stays free of the noise
that flat-logging accumulates.

## 3. Architecture

Three subsystems, governed by one **Genome** (`exocortex_config.json`):

- **Somatic gate** (safety, pre-existing): a model-independent `PreToolUse` veto on destructive commands.
- **Epistemic classifier** (routing): maps each user prompt (the *cue*) to a **discovered goal-class**.
- **Thermodynamic colony** (memory): per-class pheromone over **verb-altitude** decision-edges.

**Lifecycle (verified hook contract, Claude Code 2.1.195):**

1. `UserPromptSubmit` → classify the cue into a goal-class; seed the trail's `cue:<class>` root; **splice**
   the matching class's converged memory back into context (the recall).
2. `PreToolUse` → lay each tool's **verb-node** onto the trail (`bash:<verb>`, `Read:src`, `Edit:test`, …).
3. `PostToolUse` (`exit 0`) → **deposit** the trail's edges into that class's colony; re-root the trail.
   On failure, drop the segment (no deposit).
4. `PreCompact` → **consolidate** the colony (decay, prune, cap) — the circadian "sleep."

State lives in `colony_<class>.json` (per project, off-transcript), so it survives compaction inherently.

## 4. Key empirical results (measured)

| Finding | Result |
|---|---|
| **Consequence-sourcing is load-bearing** | On a failing run, depositing on *every* step → 32% fail-only clutter; depositing only on `exit 0` → **0%**. (Vacuous on a perfect run — measure the null on a failing regime.) |
| **Convergence is a verb-altitude phenomenon** | Keyed on raw command strings the memory drifts (entropy ↑, never plateaus); at the **verb altitude** (`bash:<verb>` + src/test) it converges (segment-reuse → 1.0, edge-count plateaus). |
| **Convergence is real on recurring work** | Live, 20 real tasks: recurring goal-classes converge from instance 1 (flat edge-count, pure reinforcement) with clean cross-class separation. |
| **Clutter control** | Session-quality weighting halves a thrashing session's clutter mass (11.2 → 5.7) and keeps the splice clean; a prune-floor bump cuts clutter eviction ~2.6× (72 → 28 class-uses). |
| **Semantic classifier** | Lexical TF fragments paraphrases (12 clusters for 4 intents); a MiniLM embedding consolidates them (5 clusters, 3/4 intents perfect) — live-verified. |

## 5. The verified hook contract (verify, don't trust docs)

Empirically captured (headless planted-token runs), because the published docs were wrong twice:

- **`PreCompact` fires** headlessly (forced via `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`) but its `additionalContext`
  is **NOT injected** into the model — so the original "splice on PreCompact" plan was abandoned.
- **`UserPromptSubmit` `additionalContext` IS injected** — this is the recall channel. Because the colony
  lives off-transcript, the consolidated memory simply re-surfaces on the next prompt after compaction.

## 6. Honest negatives & limitations

- **Real routes are short.** Most recurring repo tasks are 1–2 edges (`cue → bash:verb`). The richer
  sequence machinery (an HDC "memory palace" for just-in-time *next-step* recall) is therefore marginal —
  it only pays off on rare long routes.
- **The HDC quantization bridge failed.** Quantizing MiniLM embeddings to ternary (Z3) collapsed class
  separation (intra/inter cosine gap 0.367 → 0.029); the classifier runs on dense vectors instead.
- **Lexical fragments paraphrases**; the embedding upgrade fixes this but adds a heavy dependency and a
  per-process model load (~1–2 s) — hence opt-out-able, fail-open to lexical.
- **Regime-dependent value.** The colony shines on *repeated procedural skills*; it is near-blind to
  one-shot/novel work (by design — it abstains rather than inject stale).
- **Single-repo, single-model evidence.** Longitudinal, multi-repo, multi-model validation is future work.
- **Compliance ceiling.** We observe recall + outcome, not whether the model *used* an injected memory;
  hit-utility is a confounded proxy.

## 7. Reproducibility

Every claim is backed by an offline *gauge* (numpy, deterministic) or a scripted live run:
`exocortex/gauge/analyze.py` (`--sweep` granularity, deposit-policy null), `gauge/palace_gauge.py`
(HDC capacity, against the frozen kernel), and the `scratchpad/run_*.sh` headless drivers. 60 unit tests
cover the subsystem; a separate 99-test kernel lock is untouched throughout.

## 8. Future work

Longitudinal multi-repo accrual; isotonic-calibrated abstain (the full v0.69 mechanism); narrow HDC
next-step for long routes; graduation to an MCP server for bring-your-own-model over industry-standard hosts.
