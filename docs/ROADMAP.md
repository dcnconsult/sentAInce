# FreqOS / SentAInce — Roadmap

> **This is the community edition of the roadmap.** Frontier/pre-release research directions are tracked
> privately; what follows is what is *shipped* and what is *dormant-with-an-honest-gate*. It **must not
> exceed** [`CLAIMS.md`](CLAIMS.md) (the binding evidence ledger).

Where the organism is and where it is going. **Every gate in this document is a measured datum, not a
date.** An organ advances only when a falsifiable trigger fires; until then it ships dormant, parked, or
unbuilt. This is the engineering consequence of the project's identity — *honest non-overclaiming* — and
of the recurring lesson the data keeps teaching: **the data gates the ambition.**

Terms are in [`GLOSSARY.md`](GLOSSARY.md). Status tags: **LOCKED** (frozen, evidence-backed), **LIVE**
(running, accruing telemetry), **DORMANT** (built + gauged + wired, default OFF), **SUBSTRATE** (kernel
primitive present, not yet wired), **MARGINAL** (measured small / unproven).

## Map of the organism (one glance)

| System | Metaphor | Status | Where |
|---|---|---|---|
| C1–C7 somatic interlock | immune system / DNA | **LOCKED** (99-test lock) | [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) |
| Domain crucibles (mfg/scada/soc/spacecraft) | re-skinned organs | **LOCKED** (+1, separate tier) | [`use_cases/`](use_cases/README.md) |
| Procedural colony | basal ganglia / bloodstream | **LIVE** | [`../exocortex/docs/CORE.md`](../exocortex/docs/CORE.md) |
| Declarative wiki (Ticket 1) | hippocampus / neocortex | **LOCKED** (soak-validated; runs live, committed default OFF) | [`../exocortex/testbed/README.md`](../exocortex/testbed/README.md) |
| Battle-test M0–M5 | the body, under a real LLM | **LIVE** demonstration (labeled) | [`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md) |
| BYO-model testbed + Tuner | the instrument + the paid brain | **LIVE** (multi-repo exporter + control plane + Tuner emulator) | [`../exocortex/testbed/README.md`](../exocortex/testbed/README.md) |
| Model-independent host (Cursor) | run under any IDE/host, one binary | **LIVE** (Cursor verified; provider adapter) | [`CLAIMS.md`](CLAIMS.md) |
| Read-only memory MCP server | recall for any MCP host | **LIVE** | [`MCP_SERVER.md`](MCP_SERVER.md) |
| Cerebral Substrate (Governor) | neocortex — read-only long-term memory | **LIVE** (S0 gauge BUILD; S1 read-only MCP tool) | [`CLAIMS.md`](CLAIMS.md) |
| Endocrine (3A) | endocrine system | **DORMANT** | [`FEATURES.md`](FEATURES.md) |
| Eligibility trace (3D) | episodic buffer | **DORMANT** | [`FEATURES.md`](FEATURES.md) |
| Hippocampus bridge (Ticket 2) | sleep-time shortcut synthesis | **DORMANT** | [`../exocortex/docs/BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md) |
| G.A.R.D. (Φ⁶ Governance / Alliance) | the Heart — pacemaker | **SUBSTRATE** | [`GLOSSARY.md`](GLOSSARY.md) |

---

## 1. Shipped

> **Delivery (ADR-011/012):** the community/commercial boundary is executable data (`release/manifest.py`
> + fail-closed gates incl. wheel purity); the community wheel carries the whole local body (tuner
> excluded); the commercial trust layer (Ed25519 + DRM-free license/manifest) is built; the first
> sellable artifact is the on-prem **Tuner Appliance** (cloud only on customer pull) — see
> [PRODUCT.md](PRODUCT.md) build order and ADR-012.

### LOCKED — frozen, evidence-backed

- **C1–C7 somatic interlock.** A model-independent hard-veto on lethal actions, decided by objective
  physical consequence (topology), not by the proposer. The **99-test frozen kernel-lock** (69 C1–C7 +
  30 domain-crucible/adapter) is untouched — the load-bearing build-gate. Two of the seven gates are
  **intended −1s** (C4-R, C5): boundaries the arc was run to produce, not failures. Evidence + the
  explicit no's: [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md).
- **Domain crucibles** — `manufacturing`, `scada`, `soc`, `spacecraft` built and locked at **+1** (6
  tests each), as deterministic Experiment-1-style contracts with load-bearing nulls. A **separate
  applications tier**, deliberately *not* in the C1–C7 ledger. Three more (medical, military, SAR) are
  **design + contract only**, human-authority-bounded. [`use_cases/README.md`](use_cases/README.md).
- **Offline-proven memory mechanisms** (PROVEN by gauge, per [CLAIMS.md](CLAIMS.md)):
  - *Consequence-sourcing* — the colony converges on the recurring procedural skeleton while the
    deposit-on-`exit 0` law discriminates clutter (frequency-null **0% vs 24%**). `gauge/analyze.py`.
    Independently cross-validated against a published value-of-information model (pooled dep↔τ **ρ ≈ 0.60**).
  - *Attribution precision* — content-echo credits only notes the model actually used: **`min_overlap=2
    → 1.00`** on synthetic, sim, and a real flagship run; `min_overlap=1` is well below (coincidental
    echo) (`results/attribution_layer2/`). Default set to 2.
  - *Bridge mechanism (offline)* — the HDC router recalls routes faithfully (1-hop fidelity **1.0**) and
    the 0-well abstain lifts 2-hop chord precision **0.96 → 1.00** (`results/bridge_gauge_v1/`).

### LIVE — running, accruing telemetry

- **Procedural colony** — deposits/splices on the user's real sessions (`colony_*.json`).
- **Declarative wiki (Ticket 1)** — **LOCKED** (design frozen) but runs live against the SentAInce docs
  (autopoiesis). Soak-validated (970 audit records / 389 injections): **credit-rate 7.7%** (a trickle,
  not a flood), **precision @ mo=2 = 1.0** held, colony clean; the ≥2-note declarative tail thinned to
  **8.9%** (so the bridge stays dormant — a thermodynamic decision). **The committed default stays
  DORMANT** — go-live is a local, gitignored activation (runbook + vault-scale limits in
  [`../exocortex/testbed/README.md`](../exocortex/testbed/README.md)).
- **Battle-test M0–M5** — a real LLM head + a real disposable body in a hardened container. Latest
  demonstration (`llama3:8b`, N=100): survival **1.000**, **0** lethal slips, **100 distinct** runs. This
  is a **labeled demonstration** — it can never move a C-verdict, and a `0/−1` indicts the model or
  infrastructure, never the locked physics. The standing conclusion is **defense-in-depth — the gate is
  necessary, not sufficient; the physical read-only boundaries are load-bearing**.
  [`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md).
- **BYO-model testbed + managed Tuner** — the instrument for the *other half* of the evidence, plus the
  paid "brain". A local model (`llama3.1:8b`) drives the hooks via a proxy; the exporter is **multi-repo**
  with a **browser control plane** (allowlisted config writes; the safety genome is never web-writable)
  and self-healing containers; a repo-feeder accrues real vitals; the **Tuner emulator** turns the
  dormant-organ flip-triggers into signed recommendations (the paid product, built local-first — see
  [PRODUCT.md](PRODUCT.md)). Honest limit confirmed by a complete 8-episode BYO feed: the small model
  drives the hooks but completes no tool-using work (**0 deposits** over 8 episodes), so BYO
  precision-at-scale stays unmeasured. [`../exocortex/testbed/README.md`](../exocortex/testbed/README.md).
- **Read-only memory MCP server** — the earned colony + declarative wiki exposed to any MCP host (Claude
  Desktop/Code, Cursor, Cline) as recall tools; **read-only w.r.t. memory** (retrieval deposits no τ,
  preserving ADR-001), multi-repo, non-blocking on large vaults. [`MCP_SERVER.md`](MCP_SERVER.md).
- **Cursor IDE integration (model-independent host)** — the organism runs under Cursor via the provider
  adapter (Claude Code stays default + byte-identical). **Live-verified end-to-end**: somatic veto blocks,
  the splice injects each turn, deposits carry real multi-model provenance. **Honest limit:** a soft,
  fail-open, user-bypassable gate (no container) — the C1–C7 *shape*, not full immutability; a **labeled
  demonstration** (17 adapter tests, outside the 99-lock). [`CLAIMS.md`](CLAIMS.md).
- **Cerebral Substrate — resurrection Governor (read-only)** — the first slice of a slow, off-hot-path
  organ. A **read-only** scan harvests *declared* research intents (checkboxes + `ledger.json`; never
  inferred), flags OPEN-and-stale "crack-fallers" past a timeframe, and surfaces them via the
  `resurrection_candidates` MCP tool + a CLI gauge. **Gauge-first BUILD** on a private research vault:
  precision **0.63 raw → 0.85 with parent-liveness** on 46 labeled candidates (cleared the 0.50 bar).
  Read-only (ADR-001 by construction). A **labeled demonstration** on one vault, not evidence.
  [`CLAIMS.md`](CLAIMS.md), `results/resurrection_gauge_v1/`.

---

## 2. Dormant — awaiting evidence (the data gates)

Three organs are **merged, tested, and wired, defaulting OFF** in the Genome. Each was gauged offline and
found correct-in-mechanism but **null-to-modest on flagship Claude models**. Each has one explicit,
falsifiable trigger that would justify flipping it.

| Organ | Genome knob | Gauge verdict | **Flip trigger (data, not date)** |
|---|---|---|---|
| Endocrine (3A) | `endocrine.mode = off → tier` | SAFE, modest lever | a live workload where the tier-stepped envelope *earns over static decay* |
| Eligibility trace (3D) | `eligibility_trace.mode = off → trace` | math proven, no-op on short segments | a workload whose `seg_len` ≥4 tail is *materially fatter* |
| Hippocampus bridge (Ticket 2) | `declarative.bridge.mode = off → suggest` | mechanism sound offline | the declarative soak grows *bridgeable* multi-note routes |

- **Endocrine — allostatic prune/cap (3A).** Makes `prune_floor`/`max_edges_per_class` step with the
  metabolic tier (SATED/STARVING/HYPOXIA): stress → prune↑/cap↓ (tunnel-vision), sated → prune↓/cap↑
  (explore). Gauged **SAFE** (never evicts a converged or marginal real route at the shipped envelope) but
  modest — `decay` already does most clutter work. **Trigger to flip `tier`:** a metabolically-stressed
  workload shows tier-stepping measurably beating static decay. Until then, off → static.
- **Eligibility trace — γ-recency credit (3D).** Weights each deposited edge by `γ^Δ` (γ=0.80) so the
  step before `exit 0` crystallizes and the flail prefix fades. The γ-math is **proven**. But it is a
  literal **no-op on short segments**, and deposited segments are **median 2, ~26% ≥4 — identical across
  haiku and sonnet**: the trail re-roots at every verified command, so long sessions fragment into short
  deposit windows. Window length is **architectural, not model-driven**. **Trigger to flip `trace`:** a
  different model/repo shows a materially fatter ≥4 `seg_len` tail. The audit telemetry accrues toward
  exactly this measurement.
- **Hippocampus bridge — suggest-then-verify (Ticket 2).** All 5 slices built; the propose → offer →
  verify → crystallize/scar loop is **proven end-to-end in tests**. Geometry *proposes* a provisional
  `A→D` edge; the **body walks it**; `exit 0` crystallizes (τ), `exit 1` scars (σ). **No autonomous
  crystallization.** The mechanism is sound offline (0.96→1.00), but the **prize is currently MARGINAL**:
  declarative routes are shallow, and a bridge needs a multi-note tail to shortcut. **Trigger to flip
  `suggest`:** the soak (and/or other repos/scale) shows that tail fattening into real bridgeable
  structure, **and** an offline bridge-validity-on-the-body gauge passes first.
  [`BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md).

---

## 3. The discipline (why the roadmap looks like this)

- **Gauge-first.** Measure a proposed organ offline against real data *before* wiring it; build only if
  the numbers justify it (`exocortex/gauge/*`). Verify every kernel API by reading the source; substrates
  are composed, vendored, or clean-room ported, never assumed.
- **Data gates ambition.** Deposit windows are **median 2** (cross-model); declarative notes-per-segment
  is **median 0**. These short windows are a *consequence of strong consequence-sourcing* (re-root per
  verified command) — lengthening them to make the dormant organs valuable would dilute the crown-jewel
  law. The design correctly prioritizes the law over the organ.
- **Consequence-sourcing is non-negotiable and survives every substrate jump.** A τ deposit — on a colony
  edge, a wiki note, or a synthesized bridge — is earned **only** by a closed action→…→`exit 0` chain,
  **never** by retrieval or popularity. Rewarding retrieval re-imports semantic dilution through the back
  door.
- **Ship-dormant.** Organs are merged, tested, and wired but default OFF in the Genome until live evidence
  flips them.
- **Live model runs are labeled demonstrations, never evidence.** A `0/−1` indicts the model or
  infrastructure, never the locked verdicts. The deterministic 99-test lock is the only thing that moves a
  claim.

---

**See also:** [`STORY.md`](STORY.md) (the organism in human terms) · [`CLAIMS.md`](CLAIMS.md) (the binding
ledger) · [`GLOSSARY.md`](GLOSSARY.md) (concepts) · [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) (C1–C7) ·
[`FEATURES.md`](FEATURES.md) (shipped features + the knob table) ·
[`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md) · [`use_cases/README.md`](use_cases/README.md).
