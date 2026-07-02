# FreqOS / SentAInce — Glossary & Concept Map

The system is described in biological metaphor; this is the Rosetta stone between the metaphor, the
computer-science reality, and the code. Every other document leans on these terms. Status tags: **LOCKED**
(evidence-backed, design frozen — the kernel is immutable DNA; a soak-validated organ may still run live),
**LIVE** (running, accruing data), **DORMANT** (built + tested, shipped off behind a flag), **SUBSTRATE**
(kernel primitive present, not yet wired into an organ).

## The biological stack
| Metaphor | What it actually is | Code | Status |
|---|---|---|---|
| **Prefrontal cortex** | the stateless LLM (high-energy, untrusted pattern-matching) | Claude Code / any OpenAI-compatible head | — |
| **Immune system / DNA (C1–C7 interlock)** | model-independent hard-veto on lethal actions, by objective physical consequence | `sentaince.organism.*` (frozen kernel) | **LOCKED** (99 tests) |
| **Bloodstream / basal ganglia (ant colony)** | procedural memory: consequence-sourced pheromone paths at the verb altitude | `exocortex/colony.py` | **LIVE** |
| **Enzymes (slime mold)** | thermodynamic prune — dissolve un-verified noise (`PRUNE = 0.05`) | `colony.py` decay/prune | **LIVE** |
| **Spliceosome / RNAi (transcriptome)** | context-masking: strip introns, inject only high-pheromone "exons" | `colony.splice`, `wiki/splice.py` | **LIVE** |
| **Episodic buffer (eligibility trace)** | γ-decay credit assignment — reward the step that *preceded* success | `colony.py` (organ 3D) | **DORMANT** |
| **Endocrine system** | allostatic prune/cap as a function of the metabolic tier | `exocortex/endocrine.py` (organ 3A) | **DORMANT** |
| **Hippocampus/neocortex (declarative wiki)** | declarative memory: a Markdown vault made metabolically active | `exocortex/wiki/` | **LOCKED** (soak-validated; runs live) |
| **Hippocampus bridge** | sleep-time HDC shortcut synthesis (suggest-then-verify) | `exocortex/wiki/bridge.py` (Ticket 2) | **DORMANT** (verified vestige — ≥2-note tail 8.9%) |
| **Cerebral Substrate (bookkeeper)** | slow, off-hot-path functional-information ledger + Governor (portfolio memory) | `cerebral/` | **LIVE** (read-only, Slices 0–1) |
| **The Heart — G.A.R.D.** | the objective function: Governance, Alliance, Respect, Dignity (love, not paperclips) | see below | mixed |

## Core mechanisms
- **Consequence-sourcing** (the crown jewel) — a memory/τ deposit is earned **only** by a closed
  action→…→`exit 0` chain, **never** by retrieval or popularity. Rewarding retrieval reimports semantic
  dilution; the whole system refuses it.
- **Pheromone (τ)** — the scalar weight on a colony edge; deposited on success, evaporated by decay/prune.
- **DNA scar (σ)** — an immortal mark on a lethal/toxic path; never resurrected. Reserved for the somatic
  lethal class (and confirmed doc-rot) — *not* dropped on a plain `exit 1`.
- **Deposit window / `seg_len`** — number of edges a single consequence deposits; the colony re-roots at
  every verified `Bash`, so it is short (cross-model **median 2**) — the recurring "data gates ambition."
- **Verb altitude** — the granularity at which the colony keys nodes (a Bash *verb* + a file *category*),
  the gauge-validated operating point between drift (too fine) and signal-loss (too coarse).
- **0-well abstain** — the HDC "no-basin" veto (`freqos/epistemic_gate.py` v0.55, familiarity wall
  `WALL_BUNDLE ≈ 0.14`): when the geometry has no confident basin, the organism abstains rather than
  hallucinate. The "Respect" of G.A.R.D.
- **Z3 phasor / HDC / VSA** — Vector-Symbolic Architecture over cube-root-of-unity phases `{0,1,2}`
  (`freqos/tam.py`, `phase_router.py`); the substrate for associative recall and the bridge geometry.
- **Genome** — the single JSON of every tunable knob (`exocortex/exocortex_config.json` + `genome.py`
  DEFAULTS); organs ship dormant here and are flipped on after gauging.
- **Provider adapter (model-independent host)** — `exocortex/adapter.py`: a thin I/O shim that normalizes a
  host's hook payload/decision format to the organism's internal (Claude-shaped) contract, so one hook binary
  runs under **Claude Code (default, byte-identical) or Cursor**. Selected by `deploy --provider` /
  `EXOCORTEX_PROVIDER`.
- **Functional information (FI / FI_hat)** — the Cerebral Substrate's formal measure: `FI_hat(o,m) =
  -log₂(successes-like-m / attempts-like-m)` — the *rarity of configurations that actually help* toward an
  objective `o`. It is what consequence-sourcing already estimates (weight from verified outcomes, never
  retrieval). Adopt the Szostak/Hazen estimator; stay agnostic on the contested "law of increasing FI".
- **Intent register / crack-faller** — the Cerebral Substrate tracks *intents* (declared research threads) as
  open loops with a reasonable-timeframe TTL: opened → OPEN until closed; one still OPEN past its TTL is a
  **crack-faller** (a resurrection candidate). Valence: −1 failed/falsified · 0 under-test/inconclusive · +1
  survived selection. (`cerebral/`.)

## G.A.R.D. — the Heart (objective function)
| Letter | Principle | Substrate | Status |
|---|---|---|---|
| **Governance** | Φ⁶ kinetic pacing — prevent chaotic/autoregressive loops | `vendor/kernel/core_physics/kinetic_governor.py`, `phi6_solver.py` | **SUBSTRATE** (Ticket 4, not wired) |
| **Alliance** | harmonic phase-entrainment to human intent; dissonance starves rogue actions | `vendor/kernel/harmonic_basin/` | **SUBSTRATE** |
| **Respect** | label-free HDC abstain — refuse to lie/hallucinate in a semantic void | `epistemic_gate.py` (0-well) | **AVAILABLE** (epistemic/full mode; default `observe`) |
| **Dignity** | allostatic ledgers enforce safe shutdown over lethal survival ("starvation grants no amnesty") | `sentaince/organism/metabolism.py`, `endocrine.py` | partial (metabolism LIVE, endocrine DORMANT) |

## Method terms
- **Gauge-first** — measure a proposed organ offline against real data *before* wiring it; build only if
  the numbers justify it. (`exocortex/gauge/*`.)
- **VoI cross-check (D'Ambrogio β1–β4)** — an independent value-of-information model of stigmergic foraging
  (β1 inertia · β2 satiation · β3 undirected · β4 directed exploration) fit to the live colony logs as an
  outside-frame validation: the colony embodies β1–β3 (pooled dep↔τ **ρ ≈ 0.60**); β4 is a powered null.
  (`exocortex/gauge/dambrogio_gauge.py`.)
- **Crucible** — a deterministic test contract that yields a `−1 / 0 / +1` verdict (the C1–C7 lock; the
  domain crucibles).
- **The body** — whatever actually executes and returns a POSIX exit code: the live Claude Code session,
  or `battle/container_body` (a hardened disposable Docker body for the battle-test).
- **Suggest-then-verify** — the only safe form of a synthesized shortcut, and an instance of the
  **proposer/disposer split** (below): geometry *proposes*, the body *walks*, `exit 0` crystallizes,
  `exit 1`/no-pay scars. Never autonomous crystallization.
- **Proposer/disposer split** (ADR-010, the spine) — generation (the LLM's next action, bridge geometry, a
  dream's recombination) may only *suggest*; the sole authority to *act* is the small, frozen, model-
  independent disposer (somatic C1–C7 + epistemic 0-well abstain), ratified by *the body*'s `exit 0`. One
  chokepoint turns a suggestion into an action — which is why a new organ cannot regress the lock, and why the
  safety and measurability properties coincide. When the body is a *human* (a hand-off, a recommendation), the
  consequence is *taken-and-it-worked* — credited on the outcome, never the selection.
- **Dormant / ship-dormant** — an organ is merged, tested, and wired but defaults OFF in the Genome until
  live evidence justifies flipping it (endocrine, eligibility, bridge).

See [CLAIMS.md](CLAIMS.md) for what is proven vs dormant vs unproven, and [../README.md](../README.md) for the
documentation map.
