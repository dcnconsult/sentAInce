# The Hippocampus bridge organ — suggest-then-verify (Ticket 2 design)

Design for the §6A Hippocampus, **constrained by the bridge-validity gauge** (`results/bridge_gauge_v1/`).
The gauge's verdict sets the non-negotiables:

1. **Suggest-then-verify only** (§3B option A). Geometry *proposes* a provisional edge; the **body walks
   it**; `exit 0` crystallizes, `exit 1` scars. **No autonomous crystallization.**
2. **Gate every proposal with the 0-well abstain** — proven to lift chord precision 0.96→1.0
   (`epistemic_gate` v0.55, familiarity wall `WALL_BUNDLE≈0.14`).
3. **The real geometry lives in the declarative wiki, not the procedural colony.** The gauge showed the
   procedural router only *recalls* (random codebook → no generalization). The wiki's **semantic phasors**
   (`digest.encode_phasor`) DO generalize: two notes about the same concept are HDC-close even if never
   co-walked — that proximity is a genuine *candidate* link. So the organ lives on `WikiGraph`.

## The body is the live session (no new container)
§6A says "`container_body` executes the shortcut." For the **live** organ that is a category slip: the body
is the **user's actual Claude Code session** executing real tools. A provisional bridge `A→D` is "walked"
when the live session *uses note A then note D within one `exit 0` segment* — observed through the existing
consequence hook + attribution. `battle/container_body` is only for an *offline* bridge gauge (a Layer-2-style
planted run), not the live path. So confirmation reuses machinery we already have.

## Data model — the provisional bridge
A bridge is a **candidate `[[link]]` the graph's geometry suggests but consequence has not yet earned.** It
lives off-node (like τ and σ), in `state_dir/wiki_bridges.json`, never in the digest cache (it is earned
state, not matter):

```
ProvisionalBridge:
  a, d          : NodeId — endpoints (a's note → d's note)
  conf          : float  — HDC chord familiarity at synthesis (the abstain-gated score)
  status        : proposed | offered | confirmed | scarred
  proposed_at   : sleep-cycle stamp (passed in; no Date.now in the kernel path)
  walks         : int    — times offered-and-attributed without a clean exit-0 yet
```
Lifecycle: **proposed** (sleep) → **offered** (spliced for the LLM to try) → **confirmed** (a→d both
attributed in one exit-0 → crystallize) | **scarred** (exit-1 after a walk, or repeated no-pay → σ, never
re-proposed).

## The four stages

### 1. Synthesize (sleep / `PreCompact` — numpy, off the hot path)
Over the materialized `phasor_bank` (built by `build_phasor_bank`), for each note A find the top-k notes D by
**HDC overlap** (the same Z3 familiarity `|(ω^a)·conj(ω^d)|/M` used in `recall_successor`) that are **not
already `[[link]]`-connected and not co-walked** (no shared colony edge). Those are candidate bridges.
*Reuses:* `propose._dense` overlap machinery + the phasor bank. *New:* the "not-already-connected" filter +
candidate emission.

### 2. Gate — the 0-well abstain (the gauge's load-bearing step)
Keep a candidate only if its chord familiarity `conf ≥ WALL_BUNDLE (~0.14)` AND clears a margin over the
runner-up (a confident basin, not a 0-well tie). This is `epistemic_gate`'s geometry applied directly to the
chord (its module is emulator/cache-shaped, so we reuse the *familiarity-wall veto*, not its cache API).
Abstain ⇒ no bridge. *New:* a small `bridge_gate(conf, runner_up)` helper; cap total provisional bridges.

### 3. Offer (`UserPromptSubmit` — numpy-free, hot path)
When the proposer surfaces endpoint A this turn, the splice appends the provisional bridge as a **clearly
flagged hint** — a third channel beside verified exons and exploratory tissue:
`<!-- bridge (PROVISIONAL — earns a link only if walking A→D pays exit 0) · A ⇢ D -->` + D's text. Mark the
bridge `offered`; record both endpoint NodeIds as part of this turn's attribution surface (so a walk is
detectable). *Reuses:* `splice_with_ids` rendering + the injected-exon ledger.

### 4. Verify → crystallize / scar (`PostToolUse` — numpy-free, hot path)
At an `exit 0`, run the existing `attribute_used` over the action buffer. If **both A and D are attributed in
the same segment**, the bridge was walked and paid → **crystallize**: deposit τ on the `A→D` edge (via
`wire.on_consequence` with trail `[A, D]`) and promote it to a real link; status `confirmed`. On an `exit 1`
after the bridge was offered-and-used, or after K offers with no pay → **scar** (σ, status `scarred`, never
re-proposed). *Reuses:* `attribute_used`, `wire.on_consequence`, the `scars` set. *New:* the both-endpoints
co-attribution check + status transitions.

## Safety, dormancy, Genome
- **Dormant by default.** New Genome block `declarative.bridge = { mode: off|suggest, top_k: 4,
  abstain_conf: 0.14, abstain_margin: 0.03, max_provisional: 32, scar_after_k_walks: 3 }`. Off → the organ
  never synthesizes/offers; Ticket 1 behaves exactly as today.
- **Consequence-sourced, always.** A bridge crystallizes ONLY via a walked `exit 0`. Synthesis alone never
  deposits τ. Scarring is σ (immortal) — but unlike doc-rot, a bridge scar is cheap/correct (a refuted
  hypothesis), so K-walk patience before scarring avoids killing a good-but-unlucky bridge.
- **Lanes preserved.** Synthesis is `PreCompact`-only (numpy, with the phasor bank). Offer + verify are
  numpy-free hot-path (read `wiki_bridges.json`, string ops). The iron law holds.

## Reused vs new (build scope)
- **Reused:** `phasor_bank`/`encode_phasor` (geometry), `propose._dense` (overlap), `splice_with_ids`
  (offer rendering), `attribute_used` (walk detection), `wire.on_consequence` (crystallize deposit),
  `WikiGraph.scars` (scar). The organ is mostly *composition*.
- **New:** `wiki/bridge.py` — `synthesize(graph, …)`, `bridge_gate(conf, runner)`, `offer(graph, bridges,
  candidates)`, `verify(graph, bridges, attributed, exit_code)`; bridge persistence; the Genome block; the
  PreCompact synthesis call + the offer/verify hooks (gated).

## Open risks (honest)
1. **Value still gated by declarative chain length.** The gauge confirmed the *mechanism*; the *prize*
   needs the wiki to develop multi-note exit-0 routes worth shortcutting — which the **Ticket-1 soak is
   measuring right now** (`wiki_credit_rate`, used-note co-occurrence). Build dormant; flip only if the soak
   shows bridgeable structure. If declarative routes are median-2 like procedural, the prize is null.
2. **Co-attribution sharpness.** "A and D used in one segment" must be a real traversal, not coincidental
   double-echo. min_overlap=2 (Layer-2-validated) plus requiring *both* endpoints keeps precision high; an
   offline bridge gauge (planted A→D vault, `attribution_run`-style) should validate before flipping.
3. **Provisional-offer noise.** Offering bridges every turn could clutter context. Cap per-splice (1–2),
   prefer high-conf, and let unwalked offers age out (scar_after_k_walks).

## Build sequence (each slice tested, dormant, gauge-gated)
1. `bridge.py` data model + `bridge_gate` + persistence (pure, tested).
2. `synthesize` over the phasor bank + the not-connected filter (PreCompact; tested on a synthetic graph).
3. `offer` channel in the splice (gated; tested) — provisional rendering + ledger.
4. `verify` crystallize/scar on co-attribution (gated; tested) — the full loop closes.
5. Offline **bridge-validity-on-the-body gauge** (planted A→D vault, flagship) before any `mode=suggest`
   flip — the Layer-2 analogue for bridges.
Only then: dormant ship, soak, flip if the prize is real.
