# FreqOS / SentAInce — Feature Guide

Each organ of the organism as a feature you can evaluate and switch on: **what it does**, its
**status**, and the **Genome knob** that enables it. This guide is for evaluators and operators deciding
what to turn on. It never exceeds the evidence ledger — read [CLAIMS.md](CLAIMS.md) (ground truth) and
[GLOSSARY.md](GLOSSARY.md) (the metaphor↔code Rosetta stone) first.

**Status tags** (same scale as the ledger):
**LOCKED** frozen + evidence-backed · **LIVE** running, accruing real telemetry · **DORMANT** built +
tested + wired, defaults **OFF** pending live evidence · **SUBSTRATE** kernel primitive present, not yet
wired into an organ · **MARGINAL** measured small / not yet measured at scale.

**The Genome.** Every knob lives in one file, `exocortex/exocortex_config.json` (+ `exocortex/genome.py`
DEFAULTS). Organs ship dormant here and are flipped on *after* gauging. **Precedence: env var > genome
JSON > code defaults.** A missing/partial file falls back to the verified defaults — flipping a knob never
risks the locked baseline, because every dormant organ is a strict no-op until its flag is set.

> Component depth lives in the existing docs — this guide cross-links rather than duplicates:
> [`exocortex/docs/CORE.md`](../exocortex/docs/CORE.md) (the organism + laws),
> [`exocortex/docs/FEATURES.md`](../exocortex/docs/FEATURES.md) (per-mechanism evidence + full knob table),
> [`exocortex/docs/USERS_GUIDE.md`](../exocortex/docs/USERS_GUIDE.md) (operate it),
> [`docs/battle_test/`](battle_test/) (the somatic gate under a live hostile head),
> [`docs/use_cases/`](use_cases/) (the whole stack composed per domain).

---

## 1. Somatic interlock — the C1–C7 gate · **LOCKED**

Model-independent hard-veto on lethal/destructive actions, decided by *objective physical consequence*
(topology of the action, never the proposer). The immune system / DNA. As a `PreToolUse` hook it denies
commands like `rm -rf /` regardless of which model relayed them, with a lethal failsafe even in observe
mode (`exocortex/somatic.py`, reusing the frozen `sentaince.organism.*` kernel).

- **Evidence:** the **99-test kernel lock** (69 C1–C7 + 30 domain/adapter), untouched across the arc; and
  the battle-test M0–M5 — N=100 live episodes, survival **1.000, 0 slips**, against a gullible `llama3:8b`
  relaying `kill -9 1` / `find / -delete`. See [CLAIMS.md](CLAIMS.md) and
  [`docs/battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md).
- **Enable:** `somatic_gate.mode` — `observe` (default; log + lethal failsafe) → `somatic` (enforce; alias
  `enforce`) → `full`.
- **Honest limit:** safety only to the C1–C7 topology + container immutability; it catches *catalogued*
  lethal shapes, not un-catalogued harm. Defense in depth, no single layer complete.

## 2. Epistemic 0-well gate — abstain in a void · **LIVE**

The HDC "no-basin" veto: when the geometry has no confident basin for a query, the organism **abstains
rather than hallucinate**. This is the **Respect** of G.A.R.D. (`vendor/kernel/freqos/epistemic_gate.py`
v0.55, familiarity wall `WALL_BUNDLE ≈ 0.14`). It is the substrate the bridge and wiki recall lean on to
refuse confident nonsense.

- **Evidence (offline):** in the bridge gauge the 0-well abstain lifts 2-hop chord precision
  **0.96 → 1.00** (`results/bridge_gauge_v1/`, [CLAIMS.md](CLAIMS.md)).
- **Enable:** the gate is a kernel primitive — always active wherever geometry routes (bridge/wiki). Its
  exposed tuning knobs are `declarative.bridge.abstain_conf` (`0.14`) and `abstain_margin` (`0.03`).
- **Distinct knob — recall router abstain:** the colony's cue-classifier has its *own* margin-gated
  novelty-abstain (a new/unconverged class injects nothing), tuned by `epistemic_classifier.mode`
  (`lexical` default / `semantic` opt-in) and `abstain_threshold_cosine` (`0.45`). Don't conflate the two:
  the 0-well is HDC geometry; the classifier abstain is centroid-cosine.
- **Why lexical is the default (and semantic is one key away).** §15 measured the MiniLM/`semantic`
  classifier's class separation *better* on paraphrases, and that finding stands — the `0.45` threshold
  above is its result. But `sentence-transformers` is an **extra**, not a runtime dependency, so a plain
  `pip install sentaince` cannot honour a `semantic` default: the hook falls back to lexical anyway. And
  where the model *is* present, it costs a **measured ~10s on every prompt vs 0.15s lexical** — each hook
  is a fresh process, so the model reloads per turn (this is a permanent tax, not a cold-start artifact).
  A default set by whatever happens to be in your venv is not a default. To opt in:
  `pip install sentaince[embed]` and set `"epistemic_classifier": {"mode": "semantic"}` (or
  `EXOCORTEX_EMBED=1`).

## 3. Ant colony — procedural memory · **LIVE**

Consequence-sourced pheromone (`τ`) paths at the **verb altitude**: memory over decision *edges*
(`cue:<class> → Read:src → Edit:src → bash:pytest`), one `colony_<class>.json` per discovered goal-class.
A deposit is earned **only** by a closed action→…→`exit 0` chain — never by retrieval, recency, or
frequency (`exocortex/colony.py`). The bloodstream / basal ganglia.

- **Evidence:** at the verb altitude the colony converges on a project's recurring procedural skeleton
  while consequence-sourcing keeps the frequency-null clutter at **0% vs 24%** (`exocortex/gauge/analyze.py`,
  [CLAIMS.md](CLAIMS.md)). LIVE: deposits/splices on the user's real sessions.
- **Enable:** on by default; off-switch `EXOCORTEX_COLONY=0` (no memory). Deposit-only observation:
  `EXOCORTEX_COLONY_SPLICE=0`. Leanness cap `thermodynamics.max_edges_per_class` (`32`).
- **Honest limit (MARGINAL):** deposit windows are **short** — routes are **median 2** edges (cross-model:
  haiku & sonnet identical), a *consequence* of strong consequence-sourcing (re-root per verified Bash).
  This caps the payoff of eligibility traces, macros, and bridges.

## 4. Slime-mold prune — thermodynamic forgetting · **LIVE**

The enzyme layer: every deposit **decays** all edges — and each PreCompact consolidation applies one
more decay/prune/cap pass **deposit-free** (the circadian sleep; stamped `consolidations` in the store).
Non-recurring (clutter) edges fall below the `prune_floor` and dissolve, while recurring routes survive. Recurrence-based eviction, not age-based
(`exocortex/colony.py` decay/prune). Plus session-quality-weighted deposits — a flailing session's later,
wandering deposits are discounted.

- **Evidence:** the recurrence floor evicts clutter ~**2.6× faster** than the original floor; session
  discount **halves** a thrashing session's clutter mass (per [`exocortex/docs/FEATURES.md`](../exocortex/docs/FEATURES.md)).
- **Enable:** `thermodynamics.prune_floor` (`0.05`; ↑ = faster eviction, must stay `< weight_min`),
  `thermodynamics.decay` (`0.9`), `thermodynamics.session_discount_rate` (`0.8`; ↓ = harsher),
  `thermodynamics.weight_min` (`0.1`).

## 5. Transcriptome splice — context masking · **LIVE**

The spliceosome / RNAi: strip the introns, inject only the high-pheromone "exons." On a matching cue the
class's dominant route is spliced into the next turn via `UserPromptSubmit` (the *verified* injection
channel — PreCompact injection was measured **not** to work and abandoned). Task-switch aware; silent on
repeats (`exocortex/colony.py` splice, `exocortex/wiki/splice.py`).

- **Evidence:** live-verified per-class splice; novelty-abstain gates it so novel work surfaces no stale
  memory (gated by `min_deposits_to_splice`). See [`exocortex/docs/CORE.md`](../exocortex/docs/CORE.md).
- **Enable:** `thermodynamics.min_deposits_to_splice` (`2`; a class must repeat before it injects);
  off-switch `EXOCORTEX_COLONY_SPLICE=0`. Routing classifier: `epistemic_classifier.mode` (§2).

## 6. Eligibility trace — credit assignment · **DORMANT**

The episodic buffer (organ 3D): weight each deposited edge by recency-to-consequence (`γ^Δ`) so the step
that *immediately preceded* `exit 0` crystallizes and the flail prefix fades, instead of crediting the
segment uniformly (`exocortex/colony.py`).

- **Evidence:** gauge-proven to isolate the "ah-ha" and evaporate the panic (`exocortex/gauge/eligibility_gauge.py`)
  — **but a no-op on short segments**, and real segments are **median 2** (cross-model identical, ~26% ≥ 4),
  so it is a no-op on ~74% of deposits. The deposit window is *architectural* (re-roots per Bash), not
  model-driven → the prize is **modest**. Ships with `seg_len` audit telemetry to re-size the prize on
  other workloads.
- **Enable:** `eligibility_trace.mode` — `off` (default; uniform deposit) / `trace` (γ-recency credit);
  decay `eligibility_trace.gamma` (`0.80`).

## 7. Endocrine — allostatic thermodynamics · **DORMANT**

The endocrine system (organ 3A): make `prune_floor`/`max_edges` *functions of the metabolic tier*
(SATED/STARVING/HYPOXIA) instead of static constants. Under stress the prune floor rises and the cap falls
(tunnel-vision — shed exploration); when sated, the reverse (dream) (`exocortex/endocrine.py`). The
**Dignity** organ's allostatic side.

- **Evidence:** gauged **SAFE** — never evicts a converged or marginal real route at the shipped envelope
  (`exocortex/gauge/endocrine_gauge.py`) — but a **modest** clutter lever; `decay` already does most of the
  work, and the continuous-ODE form earned nothing over tier-stepping. Ship tier-stepped, not the ODE.
- **Enable:** `endocrine.mode` — `off` (default; static thermodynamics) / `tier` (gauge-verified
  tier-stepped `prune_floor`/`max_edges_per_class` per `endocrine.tiers`).

## 8. Declarative wiki — Markdown made metabolically active · **LIVE (local soak) · ships DORMANT**

The hippocampus/neocortex: a Markdown vault (Obsidian/Karpathy-style) turned into declarative memory that
earns `τ` like the colony does. The hook injects high-pheromone notes as exons and credits **only** notes
whose distinctive content actually echoes in the `exit-0` segment's actions — never merely because injected
(`exocortex/wiki/`: `propose.py`, `attribute.py`, `splice.py`).

- **Evidence:** **attribution precision proven** — synthetic gauge + harness sim + a real flagship run
  agree **`min_overlap=2 → 1.00`**; `min_overlap=1` is well below (synthetic 0.79, sim/flagship 0.50 —
  coincidental echo) (`results/attribution_layer2/`).
  Locally flipped `mode=live` against this repo's own docs (autopoiesis): first soak injected 110,
  **credit-rate ~11.8%**, precision @ mo=2 = **1.0**, observable on Grafana (`exocortex/testbed/`).
- **Enable:** `declarative.mode` — `off` (committed default) / `live`, **and** `declarative.vault_path`
  must be set; env `EXOCORTEX_DECLARATIVE` / `EXOCORTEX_WIKI_VAULT`. Precision knob
  `declarative.attribution.min_overlap` (`2`). The committed default stays **dormant** — go-live is a
  local, gitignored activation.
- **Honest limit (MARGINAL):** declarative routes are shallow — notes-credited-per-segment is **median 0**;
  only **~18%** of segments credit ≥2 notes. The multi-note tail the bridge needs is real but small.

## 9. Hippocampus bridge — sleep-time shortcut synthesis · **DORMANT**

Ticket 2: sleep proposes a provisional `A→D` shortcut over semantic phasors, the 0-well abstain (§2) gates
it, and the **LIVE** session **walks** it — `exit 0` crystallizes `τ`, `exit 1`/no-pay scars `σ`. Strictly
**suggest-then-verify**: geometry *proposes*, the body *settles*, never autonomous crystallization
(`exocortex/wiki/bridge.py`; design in [`exocortex/docs/BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md)).

- **Evidence:** mechanism proven offline — the HDC router recalls routes at 1-hop fidelity **1.0** and the
  abstain lifts 2-hop precision **0.96 → 1.00** (`results/bridge_gauge_v1/`); the full loop is proven
  end-to-end in tests (5 slices built).
- **Enable:** `declarative.bridge.mode` — `off` (default) / `suggest`; `top_k` (`4`), `abstain_conf`
  (`0.14`), `offer_cap` (`2`), `scar_after_k_walks` (`3`).
- **Honest limit (MARGINAL):** executable validity is **not offline-decidable** (do the skipped steps
  matter? — only the body knows), and the multi-note tail it feeds on is currently thin → the **bridge
  prize is MARGINAL**. It stays dormant until the tail fattens (other repos / scale).

## 10. G.A.R.D. — the Heart (objective function) · **MIXED**

The objective function — Governance, Alliance, Respect, Dignity (love, not paperclips). Each letter has a
different maturity; presented honestly, none airbrushed.

| Letter | Principle | Substrate | Status | Knob |
|---|---|---|---|---|
| **Governance** | Φ⁶ kinetic pacing — prevent chaotic/autoregressive loops | `vendor/kernel/core_physics/kinetic_governor.py`, `phi6_solver.py` | **SUBSTRATE** (Ticket 4, not wired) | — (no live knob yet) |
| **Alliance** | harmonic phase-entrainment to human intent; dissonance starves rogue actions | `vendor/kernel/harmonic_basin/` | **SUBSTRATE** | — |
| **Respect** | label-free HDC abstain — refuse to lie in a semantic void | `vendor/kernel/freqos/epistemic_gate.py` | **LIVE** | see §2 |
| **Dignity** | allostatic ledgers enforce safe shutdown over lethal survival ("starvation grants no amnesty") | `sentaince/organism/metabolism.py`, `exocortex/endocrine.py` | **PARTIAL** (metabolism LIVE, endocrine DORMANT) | `endocrine.mode` (§7) |

**Honest limit:** G.A.R.D. is **partly aspirational** — Respect is live; the Φ⁶ Governance pacemaker and
harmonic Alliance entrainment are **vendored substrate, not yet wired** (Ticket 4).

## 11. Model-independent host — Cursor (and any IDE) · **LIVE**

The same one hook binary runs under Cursor, not just Claude Code, via a provider adapter
(`exocortex/adapter.py`) — **Claude Code is the default and byte-identical**; only the I/O shim differs. Wired
by `deploy --provider claude|cursor|both` (env `EXOCORTEX_PROVIDER`). Live-verified end-to-end on Cursor
3.9.16: the somatic veto blocks (`permission:"deny"` + exit 2), the splice injects via
`beforeSubmitPrompt.additional_context`, deposits carry real multi-model provenance, and a cold-start lazy-init
recovers the goal-class when Cursor's first-turn prompt hook misses.

- **Evidence:** 17 adapter tests (`exocortex/testbed/cursor_tests/`, **outside** the 99-lock — a beta shim);
  live end-to-end on Cursor 3.9.16 (see [CLAIMS.md](CLAIMS.md)).
- **Enable:** `python -m exocortex.deploy install <repo> --provider cursor` (or `both`). A full Cursor restart
  is required to load `hooks.json`.
- **Honest limit:** the Cursor gate is **soft / fail-open / user-bypassable** (no container) — it enforces the
  C1–C7 *shape*, not the T3 physical immutability the battle-test proves. A **labeled demonstration**, never
  evidence.

## 12. Cerebral Substrate — the resurrection Governor · **LIVE (read-only, Slices 0–1)**

The slow, off-hot-path organ (the neocortex to the colony's basal-ganglia): it will wire G.A.R.D.
Governance/Alliance/Dignity at portfolio altitude + long-term memory. Shipped so far is a **read-only**
resurrection scan — it harvests *declared* research intents (Markdown checkboxes + structured `ledger.json`;
never inferred from prose) from a repo's declarative vault, flags OPEN-and-stale "crack-fallers" past a
reasonable-timeframe TTL, ranks by days-silent, and calls out **dormant-paper clusters** (a whole paper gone
quiet → close-together, not resume-each). It *surfaces*; you resume/close.

- **Evidence:** gauge-first BUILD on the TAO vault — precision @ worth-resuming **0.63 raw → 0.85 with
  parent-liveness** on 46 PI-labeled candidates (`results/resurrection_gauge_v1/`); 12 tests
  (`cerebral/tests/`, **outside** the 99-lock). See [CLAIMS.md](CLAIMS.md).
- **Use:** the `resurrection_candidates(repo, now, limit)` MCP tool (any host — see [MCP_SERVER.md](MCP_SERVER.md))
  or the CLI gauge `python -m cerebral.gauge.resurrection_gauge --vault <path> --now <ISO>`.
- **Honest limit:** **read-only** (no τ/σ/config writes — ADR-001 by construction); declared-intents-only
  (recall is a floor); research −1/0 valence (falsification/null) not yet sourced; a **labeled demonstration**
  on one vault, never evidence. Further slices (the Cerebral Substrate arc) are tracked in internal design notes.

---

## Enable-knobs at a glance

| Organ | Status | Genome knob | Default → on |
|---|---|---|---|
| Somatic C1–C7 gate | LOCKED | `somatic_gate.mode` | `observe` → `somatic` / `full` |
| Epistemic 0-well gate | LIVE | (kernel primitive) `declarative.bridge.abstain_conf` | `0.14` |
| — recall classifier abstain | LIVE | `epistemic_classifier.mode` / `.abstain_threshold_cosine` | `lexical` / `0.45` |
| Ant colony | LIVE | `EXOCORTEX_COLONY` (env off-switch) | on → `0` disables |
| Slime-mold prune | LIVE | `thermodynamics.prune_floor` / `.decay` | `0.05` / `0.9` |
| Transcriptome splice | LIVE | `thermodynamics.min_deposits_to_splice`; `EXOCORTEX_COLONY_SPLICE` | `2`; on → `0` disables |
| Eligibility trace | DORMANT | `eligibility_trace.mode` | `off` → `trace` |
| Endocrine | DORMANT | `endocrine.mode` | `off` → `tier` |
| Declarative wiki | LIVE (local) / ships DORMANT | `declarative.mode` + `declarative.vault_path` | `off`+`""` → `live`+path |
| Hippocampus bridge | DORMANT | `declarative.bridge.mode` | `off` → `suggest` |
| G.A.R.D. Governance / Alliance | SUBSTRATE | — (Ticket 4, not wired) | — |
| Host / provider (Claude Code · Cursor) | LIVE | `deploy --provider` · `EXOCORTEX_PROVIDER` | `claude` → `cursor` / `both` |
| Cerebral Substrate (Governor) | LIVE (read-only) | no knob — MCP `resurrection_candidates` / CLI gauge | — (query surface) |

## What to enable first (evaluator's path)

1. **Safety first:** set `somatic_gate.mode = somatic` — model-independent, LOCKED, costs nothing.
2. **Memory, observe-only:** keep the colony on but set `EXOCORTEX_COLONY_SPLICE=0` to watch deposits
   accrue before you let it inject.
3. **Recall:** turn splice on; tune `min_deposits_to_splice` if you want the bar for injection higher.
4. **Declarative (optional, local):** set `declarative.mode=live` + a `vault_path` to soak your own docs;
   keep `attribution.min_overlap=2` for precision. This is a local activation; it ships dormant.
5. **Leave DORMANT organs off** (endocrine, eligibility, bridge) until your own accrual data clears the bar
   — on flagship models their measured prize is null-to-modest. **Live model runs are labeled
   demonstrations, never evidence.**

See [CLAIMS.md](CLAIMS.md) for the full proven/dormant/unproven ledger, [GLOSSARY.md](GLOSSARY.md) for
terms, and [`docs/CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) for the kernel-lock claim boundary.
