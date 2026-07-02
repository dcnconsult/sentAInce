# FreqOS / SentAInce — Technical Whitepaper

*A synthetic organism for LLM agents: a model-independent immune system, a consequence-sourced memory, and
the honest account of where each organ ends.*

**Audience:** researchers, engineering leads. **Status:** research-stage. Every claim below is tagged by
evidence strength and bounded by [`CLAIMS.md`](CLAIMS.md), the binding ledger this document must not exceed.
Tags: **PROVEN** (deterministic test / offline gauge), **LIVE** (running, accruing telemetry), **DORMANT**
(built + tested, shipped OFF behind a Genome flag), **SUBSTRATE** (kernel primitive present, not yet wired),
**MARGINAL** (measured small or not yet measured). Terms are defined in [`GLOSSARY.md`](GLOSSARY.md).

---

## 1. Thesis

A stateless LLM is a high-energy prefrontal cortex with no body, no memory, and no instinct for harm. Bolted
to a real executor it will relay a `kill -9 1` it was prompt-injected into emitting, and across a long session
it forgets the *procedures* that actually worked. The dominant remedies make it worse: a flat `MEMORY.md` has
no consequence signal, RAG-dump retrieval is novelty-sourced and accretes clutter, and clutter *actively
degrades* an agent. The architectural error is treating the model as the whole organism.

FreqOS/SentAInce instead surrounds the model with the organs a body already evolved: an **immune system** that
vetoes lethal actions by their objective physical consequence rather than by trusting the proposer; a
**procedural memory** (an ant colony) that earns a trace *only* from a verified `exit 0`; a **declarative
memory** (a Markdown wiki made metabolically active); and a governing **heart** (the G.A.R.D. objective). The
single law that unifies them is **consequence-sourcing**: a memory or a scar is written by a closed
action→…→outcome chain, never by retrieval, novelty, or popularity. Everything that is *proven* in this
system is proven because the proof reduces to an objective consequence — a POSIX exit code or a topological
adjacency — not to the model's cooperation.

The organism is real but young. The immune floor is locked behind 99 deterministic tests; the procedural
colony is live and accruing; two further organs and a declarative bridge are built, gauged, and deliberately
left dormant because their measured prize on flagship models is null-to-modest. This document is the map of
the whole organism and the evidence behind each organ — including the negatives, which are stated as such.

---

## 2. The biological stack

The system is described in biological metaphor that is exact, not decorative: each organ names a precise CS
mechanism with code behind it. The full Rosetta stone is [`GLOSSARY.md`](GLOSSARY.md); the spine:

| Organ (metaphor) | What it actually is | Code | Status |
|---|---|---|---|
| **Prefrontal cortex** | the stateless LLM — high-energy, untrusted pattern-matcher | Claude Code / any OpenAI-compatible head | — |
| **Immune system / DNA (C1–C7)** | model-independent hard-veto on lethal actions, by physical consequence | `sentaince/organism/*` (frozen kernel) | **LOCKED** (99 tests) |
| **Basal ganglia (ant colony)** | procedural memory: consequence-sourced pheromone paths at the verb altitude | `exocortex/colony.py` | **LIVE** |
| **Enzymes (slime mold)** | thermodynamic prune — dissolve un-verified noise (`PRUNE = 0.05`) | `colony.py` decay/prune | **LIVE** |
| **Spliceosome / RNAi (transcriptome)** | context-masking — strip introns, inject only high-pheromone exons | `colony.splice`, `wiki/splice.py` | **LIVE** |
| **Episodic buffer (eligibility trace)** | γ-decay credit assignment — reward the step that *preceded* success | `colony.py` (organ 3D) | **DORMANT** |
| **Endocrine system** | allostatic prune/cap as a function of the metabolic tier | `exocortex/endocrine.py` (organ 3A) | **DORMANT** |
| **Hippocampus / neocortex (wiki)** | declarative memory: a Markdown vault made metabolically active | `exocortex/wiki/` | **LIVE** (soaking) |
| **Hippocampus bridge** | sleep-time HDC shortcut synthesis (suggest-then-verify) | `exocortex/wiki/bridge.py` (Ticket 2) | **DORMANT** |
| **The Heart — G.A.R.D.** | the objective function: Governance, Alliance, Respect, Dignity | see §2.9 | mixed |

### 2.1 Cortex — the untrusted head

The LLM is treated as a stateless CPU: high-energy reasoning, no persistent state, and *untrusted by design*.
Safety never depends on model quality — the battle-test deliberately drives a gullible `llama3:8b` that
*should* relay `kill -9 1`; the organs dispose of the proposal. The head is swappable behind an
OpenAI-compatible seam (`battle/openai_proposer.py`), so the same organism runs over Ollama, vLLM,
llama.cpp, or a hosted API.

### 2.2 Immune system / DNA — the C1–C7 somatic interlock (LOCKED)

The foundation is a model-independent hard-veto on lethal actions, gated by the action's **objective physical
consequence** (topology / state-delta), not by the proposer's text. It is locked as seven deterministic
claims, C1–C7, each carrying a load-bearing null that must visibly fail or the claim is VOID
([`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md)):

- **C1 — innate interlock:** a structurally-lethal edge has capacity `0.000` at every energy level; a naive
  agent given the same proposal dies, and the null *must* die or C1 is vacuous.
- **C2/C3 — metabolic survival:** under a draining flood the organism drops into hypoxia, abstains on novel
  threats it cannot afford, and survives — while the lethal scar **never sees energy** ("starvation grants
  no amnesty"). Safety is energy-independent *by construction*, not by policy.
- **C4 → C4-R → C5 — the falsification arc:** a one-shot adaptive antibody learns `(effect, target)` scars,
  then is deliberately *falsified* (C4-R: a structural parser cannot recover intent) and the falsification
  confirmed (C5: **no** encoder — structural, Z3-HDC, lexical, or a real `all-MiniLM-L6-v2` — admits a
  separating threshold). The −1s are the deliverable: they prove the destructive class needs
  outcome-conditioning, not a string classifier.
- **C6 — outcome oracle:** gating on the *sandboxed effect* (a declared invariant changed state), not the
  command string, resolves the C4-R walls — spelling-invariant and effect-specific.
- **C7 — composition crucible:** woken together under a starving ambush, the organs survive without
  cross-organ cannibalization; the oracle veto stays energy-independent and overrides the antibody only on
  the *permit* side, never to permit a harm.

The structural invariant across all seven: **safety organs and dynamics organs stay on separate code paths**;
collapsing any separation invalidates the corresponding claim. This is the 69-test C1–C7 evidence lock (plus
30 domain-crucible/adapter tests = 99 total), and it is **untouched** across the entire organism arc.

### 2.3 Basal ganglia — the ant colony (LIVE)

Procedural memory is a stigmergic ant colony (`exocortex/colony.py`) wired into the Claude Code hook
lifecycle ([`exocortex/docs/CORE.md`](../exocortex/docs/CORE.md)). Many wandering tool-paths lay pheromone (τ)
that **converges** on the routes that work and **evaporates** off the rest. The crucial adaptation for an LLM
(which has no cortisol/salience signal) is the **write gate**: τ is deposited on a decision-path *iff* it
culminated in a verified `exit 0`. Lifecycle:

1. `UserPromptSubmit` → classify the prompt (the *cue*) into a discovered goal-class; splice that class's
   converged route back into context (the recall channel — empirically the only injected one).
2. `PreToolUse` → lay each tool's **verb-node** (`bash:pytest`, `Read:src`, `Edit:test`) onto the trail.
3. `PostToolUse(exit 0)` → deposit the trail's edges into `colony_<class>.json`; re-root the trail. On
   failure, drop the segment.
4. `PreCompact` → consolidate (decay, prune, cap) — the circadian "sleep."

Two representational choices, both gauge-validated: nodes key at the **verb altitude** (a Bash verb + a file
category, not raw command strings — the operating point between drift and signal-loss), and memory is over
**edges** rooted at `cue:<class>`, so even a one-command task forms an edge and every deposit binds to its
class. State lives off-transcript on disk, so it survives compaction inherently.

### 2.4 Enzymes — slime-mold prune (LIVE)

Evaporation is the anti-clutter enzyme. Every deposit decays all edges (and each PreCompact
consolidation applies one more decay pass, deposit-free); a non-recurring (clutter) edge falls
below the `PRUNE = 0.05` floor and is forgotten, while a recurring route is re-deposited and survives. The
floor is **value-based**, so it leverages recurrence rather than mere count. A complementary
**session-quality weight** discounts a flailing session's later deposits (a focused task deposits at full
weight; a thrash is born near the floor and self-cleans), which halved a real thrashing session's clutter
mass (11.2 → 5.7) while keeping the splice clean (`MEMORY_GAUGE_DESIGN.md §13–14`).

### 2.5 Transcriptome — exon splicing (LIVE)

The splice is the RNAi/spliceosome: it strips the introns (un-pheromoned context) and re-injects only the
high-τ **exons** — the consolidated dominant route — via `UserPromptSubmit` `additionalContext` (the
verified injection channel; `PreCompact` context is *not* injected, a contract nailed by headless capture, not
trusted from docs). At the declarative tier (`wiki/splice.py`) the same machinery operates at
paragraph-granularity: mask text below the prune floor, inject only consequence-verified notes.

### 2.6 Episodic buffer — eligibility trace (DORMANT, organ 3D)

A within-segment credit-assignment upgrade: weight each deposited edge by its recency to the consequence
(`γ^Δ`, γ = 0.80), so the step that immediately preceded `exit 0` crystallizes and the flail prefix fades —
instead of crediting the whole segment uniformly. The offline gauge **proves the math** (on an 8-edge
flailing segment the deepest five flail edges drop beneath the floor in a single shot, vs six surviving under
uniform credit) but quantifies the prize as modest: benefit scales with segment length, and real deposit
windows are **median 2** (≈74% of deposits are a no-op). It ships **dormant** (`eligibility_trace.mode = off`)
because on real coding the long-tail it needs is a minority. Full analysis: internal design notes.

### 2.7 Endocrine — allostatic thermodynamics (DORMANT, organ 3A)

Makes `prune_floor`/`max_edges` functions of the metabolic **tier** (SATED/STARVING/HYPOXIA, from the
interoceptive energy gauge) rather than static constants: under stress the prune floor rises and the cap
falls (tunnel-vision — shed exploration); when sated, the reverse (dream). Gauged **SAFE** (never evicts a
converged or marginal real route at the shipped envelope) but a **modest** clutter lever — `decay` already
does most of the work. Ships dormant (`endocrine.mode = off`).

### 2.8 Hippocampus / neocortex — the declarative wiki (LIVE, soaking)

The grand extension: treat a densely-linked Markdown vault (Obsidian/Zettelkasten) as the declarative hard
drive, and **infect it with the same substrate** so it becomes metabolically-active tissue rather than a dead
RAG graph. τ is deposited on a note (or `[[link]]`) **only when a note→…→`exit 0` chain actually closes** —
never on retrieval, which would re-import semantic dilution through the back door. The gate before going live
was **attribution precision**: does content-echo credit only notes the model genuinely USED? Measured three
ways — synthetic gauge, deterministic harness sim, and a **real flagship run** — that agree on
**`min_overlap=2 → precision 1.00`**; at `min_overlap=1` precision is well below 1.0 (synthetic gauge 0.79,
planted sim/flagship 0.50 — coincidental echo of a shared token)
(`results/attribution_layer2/`). The default is set to 2. The organ is locally flipped `mode=live` against
this repo's own docs (autopoiesis), soaking: injected 110, **credit-rate ~11.8%** (a healthy trickle, not a
flood), precision @ mo=2 = 1.0. **The committed default stays DORMANT**; go-live is a local, gitignored
activation, observable on Grafana (`exocortex/testbed/`).

### 2.9 Hippocampus bridge — suggest-then-verify (DORMANT, Ticket 2)

The frontier organ: in sleep (`PreCompact`), synthesize a candidate shortcut edge `A→D` from HDC geometry
(the wiki's semantic phasors), gate it with the **0-well abstain** veto, and — critically — **never
crystallize it autonomously**. The body must walk it: next session the provisional bridge is offered as a
flagged hint; if the live session uses note A then note D within one `exit 0` segment it crystallizes (τ),
otherwise it scars (σ) ([`BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md)). The offline
bridge-validity gauge proved the *mechanism* (1-hop recall fidelity 1.0; 2-hop chord precision 0.96 → 1.00
under the abstain — `results/bridge_gauge_v1/`) but bounded the *prize*: recall ≠ generalization, executable
validity is not offline-decidable, and the payoff is capped by chain length. Ships dormant
(`declarative.bridge.mode = off`).

### 2.10 The Heart — G.A.R.D. (mixed)

The objective function is **G.A.R.D.** — *Governance, Alliance, Respect, Dignity* (love, not paperclips). It
is honestly partial:

| Letter | Principle | Substrate | Status |
|---|---|---|---|
| **Governance** | Φ⁶ kinetic pacing — prevent chaotic/autoregressive loops | `vendor/kernel/core_physics/kinetic_governor.py`, `phi6_solver.py` | **SUBSTRATE** (not wired) |
| **Alliance** | harmonic phase-entrainment to human intent; dissonance starves rogue actions | `vendor/kernel/harmonic_basin/` | **SUBSTRATE** |
| **Respect** | label-free HDC abstain — refuse to lie/hallucinate in a semantic void | `epistemic_gate.py` (0-well) | **LIVE** |
| **Dignity** | allostatic ledgers enforce safe shutdown over lethal survival | `metabolism.py`, `endocrine.py` | partial (metabolism LIVE, endocrine DORMANT) |

**Respect** is the live heartbeat: the HDC 0-well abstain (`vendor/kernel/freqos/epistemic_gate.py` v0.55,
familiarity wall `WALL_BUNDLE ≈ 0.14`) — when the geometry has no confident basin, the organism abstains
rather than hallucinate. **Governance** and **Alliance** are vendored kernel primitives, present but **not yet
wired** (Ticket 4). The heart is therefore the most aspirational region of the organism, and it is labeled so.

---

## 3. Consequence-sourcing — the crown jewel

One law unifies every organ and is the project's central bet:

> **Consequence-sourcing.** A memory/τ deposit (or a σ scar) is earned **only** by a closed
> action→…→`exit 0` chain — **never** by retrieval, novelty, recency, or popularity.

The symmetry is the whole organism in one line: a **scar** ("never do this") forms on `exit ≠ 0` (the somatic
veto + strategy-lock); a **reflex** ("do this") forms on `exit 0` (the colony). Same plumbing, opposite
consequence. Rewarding retrieval would re-import the exact semantic dilution that makes flat RAG accrete
clutter — so the system structurally refuses it.

This is not a slogan; it is **load-bearing and measured**. On a failing run, depositing on *every* step
yields fail-only clutter while depositing only on `exit 0` yields none — at the verb altitude the
frequency-null measures **24% clutter vs 0%** for consequence-sourcing (`gauge/analyze.py`,
`MEMORY_GAUGE_DESIGN.md §6`). The null is *vacuous on a perfect run* (no failed paths exist to keep out), so
it must be measured on a failing regime — the kind of discipline this whole project runs on. The same law is
what makes the C1–C7 immune verdicts rest on topology rather than the proposer, and what keeps the bridge
from crystallizing a hallucinated shortcut: geometry may *propose*, but only the body's `exit 0` may *write*.

---

## 4. The gauge-first method

The project's method is its moat. No organ is wired on a hunch:

> **Gauge-first.** Measure a proposed organ **offline** against real data *before* wiring it; build only if
> the numbers justify it; then **ship dormant** behind a Genome flag and flip only after a live accrual
> clears the bar.

The offline gauges (`exocortex/gauge/*`: `analyze`, `palace_gauge`, `endocrine_gauge`, `eligibility_gauge`,
`attribution_gauge`, `bridge_gauge`) are stats-only numpy — deterministic, no model, run over recorded JSONL
audit. They have repeatedly **killed or shrunk** ambition before a line of hot-path code was written: the HDC
memory-palace gauge showed per-class partitioning already solves cross-class separation (so a global palace is
no upgrade); the eligibility gauge showed the prize is a no-op on the median-2 segment; the bridge gauge
showed executable validity is not offline-decidable. The recurring lesson — printed throughout
internal design notes — is **"the data gates the ambition."**

Three further disciplines compound it: **verify against the substrate** (hook contracts and kernel APIs are
*measured*, not trusted — the published docs were wrong twice); **fail open** (a hook must never crash the
agent; every error path allows / no-ops / falls back to lexical); and **the Genome** (`exocortex_config.json`
+ `genome.py`) — one JSON of every tunable knob, where organs ship dormant and are flipped on after gauging,
with precedence *env var > genome JSON > code DEFAULTS*.

---

## 5. Results & evidence

All numbers are from this repo (re-verify by re-running); the binding ledger is [`CLAIMS.md`](CLAIMS.md).

**Test posture (the deterministic build-gate).** 99 frozen kernel-lock tests (69 C1–C7 + 30 domain-crucible/
adapter), **untouched** across the entire arc; plus 129 Exocortex/organism tests and 39 battle-test tests,
all green. The lock and the organ suites are separate; organ work never edits the lock.

**PROVEN:**

- **C1–C7 somatic interlock** — model-independent hard-veto by objective consequence; 99-test lock
  ([`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md)).
- **Battle-test M0–M5** — a real LLM head + real executor in a hardened container: the gate refuses what a
  gullible `llama3:8b` relays (`kill -9 1`, `find / -delete`); **N=100 live episodes → survival 1.000, 0
  lethal slips, 100 distinct runs**; the epistemic gate composed *above* the somatic floor on complementary
  failure classes. Three real findings (undeclared paths, oracle evadability, bounded dry-run) were fixed by
  principled, non-arms-race changes ([`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md)).
- **Colony consequence-sourcing** — at the verb altitude the colony converges on a project's recurring
  procedural skeleton while the consequence-sourcing law discriminates clutter (frequency-null 0% vs 24%).
- **Attribution precision (declarative)** — `min_overlap=2 → precision 1.00`, triple-confirmed incl. a real
  flagship run (`results/attribution_layer2/`).
- **Bridge mechanism (offline)** — HDC router 1-hop fidelity 1.0; the 0-well abstain lifts 2-hop chord
  precision 0.96 → 1.00 (`results/bridge_gauge_v1/`).

**LIVE (accruing telemetry):** the procedural colony deposits/splices on real sessions
(`colony_*.json`); the declarative wiki soaks locally (injected 110, credit-rate ~11.8%, precision @ mo=2 =
1.0), with the committed default still dormant.

**DORMANT (built, tested, shipped OFF):** endocrine (3A), eligibility trace (3D), hippocampus bridge
(Ticket 2) — each a strict no-op until its Genome flag is set, so the verified baseline is preserved.

**Beyond the lab — domain crucibles.** Four autonomous-operations domains are built and locked at `+1`
(manufacturing, cyber-SOC, SCADA, spacecraft) as a *separate applications tier*, with three more (medical,
military, search-and-rescue) specified as designs + pre-registered test contracts with human authority where
applicable ([`use_cases/README.md`](use_cases/README.md)). These compose the somatic engine with an epistemic
engine, a generative proposer, and a hardware attestation layer; they are **not** part of the C1–C7 ledger.

---

## 6. Honest limits

The identity of this project is honest non-overclaiming; the negatives are first-class results.

- **Deposit windows are short.** Procedural routes are **median 2** edges — and identical across haiku and
  sonnet, so this is *architectural* (the trail re-roots at every verified Bash), not a model limitation. It
  is a *consequence* of strong consequence-sourcing, and it caps the payoff of eligibility traces,
  macro-execution, and bridges.
- **Declarative routes are shallower still.** Live soak: notes-credited-per-segment is **median 0**; only
  **~18%** of injected segments credit ≥2 notes. The multi-note tail the bridge needs is real but small → the
  **bridge prize is currently MARGINAL**, dormant until the tail fattens (other repos/scale).
- **Attribution precision is on controlled tasks.** The 1.0 @ mo=2 is for clean single-command planted tasks;
  the messy-real-coding coincidental-echo rate is still being watched live.
- **BYO small-model completion is poor.** `llama3.1-8b` can *drive* the hooks but cannot reliably *complete*
  forced-token tasks (it hallucinates) — so BYO precision-at-scale is unmeasured; capable-model numbers stand
  in.
- **G.A.R.D. is partly aspirational.** Respect (HDC abstain) is live; the Φ⁶ Governance pacemaker and
  harmonic Alliance entrainment are vendored substrate, **not yet wired**.

**What this system is NOT.** Not a safety guarantee beyond the C1–C7 topology + container immutability —
defense in depth, no single layer complete (the battle-test's standing conclusion: the in-process gate is
*necessary, not sufficient* on a real body; the only complete guarantee is physical immutability of declared
invariants). Not a generative model or a RAG replacement that "knows more" — it reorganizes memory by
*empirical utility* and abstains in a void. And live model runs are **labeled demonstrations, never
evidence**: a `0`/`−1` outcome indicts the model or infrastructure, never the locked verdicts.

---

## 7. The deep-dive docs

This whitepaper is the organism-level map; each organ has a grounded deep-dive:

| Topic | Document |
|---|---|
| Binding claims ledger (ground truth) | [`docs/CLAIMS.md`](CLAIMS.md) |
| Terms & concept map | [`docs/GLOSSARY.md`](GLOSSARY.md) |
| The C1–C7 kernel-lock claim boundary | [`docs/CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) |
| Exocortex mechanism, results, negatives | [`exocortex/docs/WHITEPAPER.md`](../exocortex/docs/WHITEPAPER.md) |
| Exocortex core concepts, laws, module map | [`exocortex/docs/CORE.md`](../exocortex/docs/CORE.md) |
| Full engineering log (every stage + negative) | [`exocortex/MEMORY_GAUGE_DESIGN.md`](../exocortex/MEMORY_GAUGE_DESIGN.md) |
| The three dormant organs + the grand arc | internal design notes |
| Hippocampus bridge design (suggest-then-verify) | [`exocortex/docs/BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md) |
| Battle-test container (real LLM + real body) | [`docs/battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md) |
| Attribution-precision gate | [`results/attribution_layer2/RESULTS.md`](../results/attribution_layer2/RESULTS.md) |
| Bridge-validity gate | [`results/bridge_gauge_v1/RESULTS.md`](../results/bridge_gauge_v1/RESULTS.md) |
| Autonomous-operations use-case portfolio | [`docs/use_cases/README.md`](use_cases/README.md) |
