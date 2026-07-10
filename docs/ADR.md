# FreqOS / SentAInce — Architecture Decision Records

The load-bearing decisions of the organism, and the *reasoning* behind them. In this project the
discipline **is** the crown jewel: every organ is cheap to build and easy to overclaim, so what keeps the
system honest is a small set of laws about *when memory is allowed to form, what may act, and what ships on*.
This file records those laws as ADRs (context / decision / consequences) so a future maintainer changes them
on purpose, not by accident.

Each ADR carries a status tag matching the ledger: **LOCKED** (frozen, evidence-backed), **LIVE** (running,
accruing telemetry), **DORMANT** (built + tested, shipped OFF behind a flag), **SUBSTRATE** (primitive
present, not wired), **MARGINAL** (measured small or unmeasured). The binding evidence is
[CLAIMS.md](CLAIMS.md); terms are in [GLOSSARY.md](GLOSSARY.md); the kernel-lock claim boundary is
[CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md). These ADRs explain *why*; those files certify *what*.

> **New here, or not an engineer?** Start with **[STORY.md](STORY.md)** — it explains the whole system in
> plain language (an immune system, muscle memory, sleep…). This file is the deeper "why we built it this
> way," written for contributors; you don't need it to use SentAInce.

---

## ADR-001 — Consequence-sourcing: a memory is earned only by `exit 0`, never by retrieval

**Status:** LOCKED (the crown jewel). Evidence: colony deposit-policy gauge `frequency-null 0% vs 24%`
([CLAIMS.md](CLAIMS.md) · `../exocortex/gauge/analyze.py`).

**Context.** The obvious way to build agent memory is to reward what is *retrieved often* — popularity as a
proxy for utility. This is how naive RAG works, and it is why a wiki bolted onto a naked LLM becomes a *dead
graph*: it re-imports semantic dilution (intron bloat) and confidently cites rotted docs. Popularity ≠
utility.

**Decision.** A pheromone (τ) deposit on any memory — a procedural colony edge, a markdown note, a
`[[link]]` — is earned **only** by a closed `action → … → exit 0` chain, and **never** by retrieval,
frequency, or human tags. `Colony.deposit` runs solely from `PostToolUse` on a verified `exit 0`; failure
deposits nothing (`../exocortex/colony.py`: "DEPOSIT — on a Bash exit 0 … NEVER on failure"). The same law
is carried verbatim onto the declarative substrate: a note credits τ only when a `note → … → exit 0` chain
actually closes (internal design notes).

**Consequences.**
- The retrieval surface reorganizes by *empirical utility*, and the colony stays clean: the gauge shows the
  consequence-sourcing law discriminates clutter (a frequency-driven null deposits 24% clutter; the
  consequence policy, 0%).
- This is a *constraint we accept costs for*, not a free win. It is the root cause of the short deposit
  windows in ADR-008-adjacent findings (re-rooting at every verified Bash → median-2 segments), which caps
  the payoff of eligibility traces and bridges. We pay that price rather than dilute the law — see the
  explicit tension recorded in internal design notes
- Every downstream ADR (the σ economy, suggest-then-verify, min_overlap) exists to *protect* this law at a
  new layer. Collapsing it invalidates the colony, the wiki, and the bridge at once.

**Recall discipline:** recalling a note never reinforces its trust — retrieval earns no τ; a memory's
trust is deposited only by a closed `action → … → exit 0` consequence, and otherwise it decays.

---

## ADR-002 — Gauge-first: measure the prize offline before wiring the organ

**Status:** LOCKED method. Evidence: `../exocortex/gauge/*`, four gauges with recorded verdicts
([results/](../results/)).

**Context.** Each proposed organ (endocrine, eligibility trace, hippocampus bridge, cerebellum macro) is a
plausible neuroscience metaphor and a few hundred lines of code. Plausibility and biological elegance are
*not* evidence; building first and measuring later produces shipped features defended by their story rather
than their numbers.

**Decision.** Before any organ is wired into the live hook, it is measured **offline** against real or
realistic data, and built only if the numbers justify it ([GLOSSARY.md](GLOSSARY.md) → *Gauge-first*). The
gauge is a first-class deliverable with its own results file. The rule has *killed and shrunk* real ambition:
- **Eligibility trace (3D):** `eligibility_gauge.py` proved the γ-trace works exactly as theorized (isolates
  the "ah-ha", evaporates the flail) but is a **no-op on short segments**, and the recorded distribution is
  median-2 (only 22–26% ≥4 edges, confirmed cross-model haiku & sonnet). Verdict: ship **dormant**, flag
  stays off — the prize is real but modest (internal design notes).
- **Hippocampus bridge (3B):** `bridge_gauge.py` proved the mechanism sound (1-hop fidelity 1.0; 0-well
  abstain lifts chord precision 0.96→1.0) *and* exposed two limits that forbid autonomous synthesis — see
  ADR-008 ([results/bridge_gauge_v1/RESULTS.md](../results/bridge_gauge_v1/RESULTS.md)).
- **Endocrine (3A):** gauged SAFE but a modest clutter lever → tier-stepped (option A), shipped dormant.

**Consequences.**
- "Data gates ambition" becomes a recurring, *documented* outcome rather than a slogan: the offline number
  decides the flag, not the elegance of the metaphor.
- A gauge can return a load-bearing **negative** (the prize is small/null) and that is a *success* — it is
  the same falsification discipline as the C1–C7 lock's two intended −1s ([CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md)).
- The BYO-model testbed exists precisely to accrue the *other* half of the evidence the flagship gauges
  could not reach (smaller/diverse models on diverse repos) (internal design notes).

---

## ADR-003 — Dormant-by-default: organs ship OFF in the Genome until live evidence flips them

**Status:** LOCKED policy; three organs currently DORMANT. Evidence: `../exocortex/genome.py`,
`../exocortex/exocortex_config.json` ([CLAIMS.md](CLAIMS.md) → DORMANT).

**Context.** A gauge proves an organ is *safe and plausibly useful* offline; it does not prove the organ
*earns its keep* against a user's real, messy traffic. Shipping a freshly-gauged organ ON conflates "we
built it" with "it pays" — exactly the overclaim the project's identity forbids.

**Decision.** Every new organ is merged, tested, and fully wired, but defaults **OFF** in the Genome (the
single JSON of all tunable knobs). It flips ON only after live evidence justifies it, and the flip is a
*local, gitignored activation*, not a committed default. Today: `endocrine.mode = off`,
`eligibility_trace.mode = off`, `declarative.bridge.mode = off`
([GLOSSARY.md](GLOSSARY.md) → *Dormant / ship-dormant*). Even the LIVE declarative wiki (Ticket 1) keeps the
**committed** default DORMANT — go-live is a local flip against the SentAInce repo's own docs, observable on
Grafana, while `main` stays conservative ([CLAIMS.md](CLAIMS.md) → LIVE).

**Consequences.**
- The repo's default behavior is always the *verified* baseline; a contributor cloning `main` gets the
  proven-conservative organism, never an unproven organ silently in the hot path.
- The Genome is the one place a knob is allowed to exist, so "what is on?" is answerable by reading one file.
- "Built but dormant" is a *legitimate, terminal* state. The eligibility trace is shipped and will likely
  stay dormant forever on flagship models — and that is recorded as honest, not framed as pending success
  ([CLAIMS.md](CLAIMS.md) → DORMANT / MARGINAL).

---

## ADR-004 — No immortal σ on a plain `exit 1`: the scar is reserved for the lethal class

**Status:** LOCKED. Evidence: `../exocortex/colony.py`; somatic scar `sentaince/organism/interlock.py`
([GLOSSARY.md](GLOSSARY.md) → *DNA scar (σ)*).

**Context.** There are two failure currencies, and they must not be conflated. A pheromone (τ) is *soft* —
deposited on success, evaporated by decay/prune. A DNA scar (σ) is **immortal** — a mark on a lethal/toxic
path that is never resurrected. The temptation is to treat every `exit 1` as a scar ("remember this hurt").
But an ordinary build failure is not toxic; it is just the *absence of reward*. Scarring it would freeze the
colony against a path that will succeed on the next attempt, and would inflate the immortal set until σ means
nothing.

**Decision.** A plain `exit 1` deposits **nothing** — no τ (consequence-sourcing, ADR-001) and **no σ**. It
simply earns no pheromone and is forgotten by decay. The immortal σ is reserved for the **somatic lethal
class** (the C1–C7 interlock's structurally-lethal actions) and confirmed doc-rot — and, in the dormant
bridge organ, a *refuted hypothesis* (a provisional bridge that failed when walked), which is cheap and
correct to scar permanently ([GLOSSARY.md](GLOSSARY.md); [BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md)
§"Safety, dormancy, Genome").

**Consequences.**
- The colony stays *plastic*: a route that failed once and succeeds later is freely re-learnable, because the
  failure left no permanent mark.
- σ retains its meaning — the immortal set stays small and load-bearing (the immune memory), so "this path is
  scarred" remains a strong signal rather than accumulated build noise.
- This mirrors the somatic separation in the lock: the **safety** brake (σ / the energy-independent veto) and
  the **dynamics** layer (τ / metabolic throttle) live on separate code paths and are never collapsed
  ([CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md) → Structural invariant).

---

## ADR-005 — Verb-altitude colony keying: a Bash verb + a file category, nothing finer

**Status:** LOCKED operating point (granularity sweep). Evidence: `../exocortex/colony.py` (`verb_node`)
([GLOSSARY.md](GLOSSARY.md) → *Verb altitude*).

**Context.** The colony has to key its nodes at *some* granularity, and the choice is a bias/variance knob.
Too **fine** (the exact command string, full file paths) → every invocation is a unique node, the graph never
converges, pheromone never accumulates (drift). Too **coarse** (just "ran a tool") → all structure collapses
into one node and the memory carries no routing signal (signal-loss).

**Decision.** The colony keys nodes at the **verb altitude**: a Bash node is its *executable verb*
(`bash:<verb>`), and a file tool is its *category* (`src | test | other`) — not the literal command or path
(`../exocortex/colony.py`: `verb_node`, `_bash_verb`). This was selected by an offline granularity sweep as
the operating point between drift and signal-loss ([GLOSSARY.md](GLOSSARY.md); engineering log
[CORE.md](../exocortex/docs/CORE.md)).

**Consequences.**
- The colony converges on a project's *recurring procedural skeleton* (e.g. "edit src → run pytest") across
  paraphrased, surface-distinct invocations — the convergence behind the consequence-sourcing PROVEN claim
  ([CLAIMS.md](CLAIMS.md)).
- It is *arg-blind by design*. A macro keyed at this altitude cannot safely re-execute cached arguments
  (a stale `rm build/` would re-fire blindly), which is one reason the cerebellum/macro-execution organ is
  deferred and, if ever built, must be suggest-not-execute behind the somatic gate
  (internal design notes).
- Verb-altitude keying interacts with consequence-sourcing to produce the short median-2 deposit window —
  acknowledged, not hidden, as a MARGINAL limit ([CLAIMS.md](CLAIMS.md) → MARGINAL).

---

## ADR-006 — `min_overlap = 2`: the attribution-precision gauge sets the credit threshold

**Status:** LOCKED default; precision on controlled tasks. Evidence:
[results/attribution_layer2/RESULTS.md](../results/attribution_layer2/RESULTS.md); default in
`../exocortex/genome.py` (`declarative.attribution.min_overlap`).

**Context.** Declarative consequence-sourcing (ADR-001) needs to credit *which* notes the model actually
USED in an `exit 0` segment. The mechanism is content-echo: a note is credited if tokens from it appear in
the action buffer. With a threshold of one shared token (`min_overlap = 1`), a *coincidental* echo — a
distractor note that merely shares a common token like `echo` with the real command — gets false-credited.
That re-imports popularity-as-utility through the back door (ADR-001's exact failure).

**Decision.** Require **≥ 2** distinctive shared tokens (`min_overlap = 2`) before a note is credited. The
gauge measured the contrast three ways — synthetic, deterministic harness sim, and a **real flagship run** —
agreeing on **`min_overlap=2 → precision 1.00, FP 0`**; at `min_overlap=1` precision is well below (synthetic
gauge 0.79; the planted sim/flagship runs 0.50, every task false-crediting its coincidental `*-ops.md` distractor). The default was set *by the gauge*
([results/attribution_layer2/RESULTS.md](../results/attribution_layer2/RESULTS.md)).

**Consequences.**
- Coincidental-echo false credit is eliminated on the controlled case, so the wiki's τ stays
  consequence-true.
- The 1.00 is for **clean single-command planted tasks**, *not* arbitrary messy coding — the messy-real-coding
  coincidental-echo rate is still being watched LIVE via the exported `wiki_credit_rate`. This caveat is
  stated, not airbrushed ([CLAIMS.md](CLAIMS.md) → MARGINAL).
- There is a recall cost: `min_overlap=2` misses notes that echo only a single distinctive token (synthetic
  recall ~0.45). We accept lower recall for high precision, because a clean small memory beats a polluted
  large one (the whole anti-dilution thesis).
- BYO small models (`llama3.1-8b`) could not *complete* the forced-token tasks, so this precision is from a
  capable model — which is the user's real Claude Code deployment. The attribution *logic* is validated;
  small-BYO precision-at-scale remains unmeasured ([CLAIMS.md](CLAIMS.md) → MARGINAL).

---

## ADR-007 — numpy-free, fail-open hot path: heavy geometry is confined to sleep (`PreCompact`)

**Status:** LOCKED engineering invariant ("the iron law"). Evidence: `../exocortex/colony.py`;
`../exocortex/wiki/bridge.py` ([BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md) §"Lanes preserved").

**Hot path posture:** The hot path does **not** lean on numpy — it is numpy-free, pure-Python, and
fail-open; numpy and the kernel geometry are confined to the sleep lane (`PreCompact` consolidation).

**Context.** The live organ runs *inside* Claude Code hooks on the per-tool critical path
(`UserPromptSubmit`, `PreToolUse`, `PostToolUse`). Anything on that path that is slow or that can *throw*
degrades or breaks the user's session. Meanwhile the most powerful primitives — the vendored HDC/VSA kernel
(`tam`, `phase_router`, `order_palimpsest`, `epistemic_gate`) — are **numpy research code** that we want for
bridge synthesis and eligibility weighting.

**Decision.** Two lanes, strictly separated:
- **Hot path** (per-tool hooks) is **numpy-free and fail-open**: pure-Python, self-contained, and on any
  unexpected error it degrades to a no-op rather than blocking the tool (`../exocortex/colony.py`:
  "self-contained (no numpy) so the hook stays fast and fails open").
- **Sleep** (`PreCompact` consolidation) is where numpy and the kernel geometry are permitted — bridge
  synthesis builds the phasor bank and runs HDC chords there, off the hot path
  ([BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md); internal design notes note).

  The dormant bridge organ honors this exactly: `synthesize` is `PreCompact`-only (numpy); `offer` and
  `verify` are numpy-free hot-path string ops.

**Consequences.**
- The user's session is never blocked or crashed by the memory layer; a bug in the organ costs a missed
  deposit, not a broken tool call.
- It forces a deliberate design choice for any new mechanism: if it needs numpy, it lives in sleep, full
  stop. The eligibility trace's HDC/`order_palimpsest` form is parked for exactly this reason — only its
  numpy-free scalar-γ form is hook-eligible (internal design notes).
- The MCP-server graduation (a standalone memory service) is the future home for the heavier in-process work
  the hot-path lane forbids today (internal design notes, §5).

---

## ADR-008 — Suggest-then-verify: geometry proposes a bridge, the body crystallizes it — never autonomous synthesis

**Status:** DORMANT organ; prize MARGINAL. Evidence:
[results/bridge_gauge_v1/RESULTS.md](../results/bridge_gauge_v1/RESULTS.md);
[BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md); `../exocortex/wiki/bridge.py`.

**Context.** The hippocampus bridge synthesizes a shortcut edge `A→D` by HDC geometry over the wiki's
semantic phasors — a route the organism never actually walked. This is seductive ("the organism invents a
faster path in its sleep") and dangerous: a synthesized edge is a **hallucinated shortcut**. The
bridge-validity gauge made the two limits precise: (1) geometric *recall ≠ generalization* — a random
codebook recovers stored transitions but invents nothing real; (2) **executable validity is not
offline-decidable** — that a path `A→…→D` exists says nothing about whether the *direct* `A→D` works, because
the skipped steps (e.g. an Edit before a test) may be necessary. Only the body settles it. And a synthesized
edge that deposited τ on synthesis alone would violate consequence-sourcing (ADR-001) outright.

**Decision.** Build **only** the consequence-preserving suggest-then-verify form. Geometry *proposes* a
provisional `A→D`, gated by the **0-well abstain veto** (`epistemic_gate`, proven to lift chord precision
0.96→1.0 in the gauge). The **body walks it** — in the live organ the body is the user's actual Claude Code
session, "walked" = note A and note D both attributed in one `exit 0` segment (reusing min_overlap=2 from
ADR-006). `exit 0` crystallizes the edge (τ deposit); `exit 1` or repeated no-pay scars it (σ, ADR-004). The
organ ships **dormant** (ADR-003: `declarative.bridge.mode = off`) and is sized against the *small genuine
route population*, never the inflated topological path count
([BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md); [results/bridge_gauge_v1/RESULTS.md](../results/bridge_gauge_v1/RESULTS.md)).

**Consequences.**
- Consequence-sourcing survives the jump to synthesized memory: a bridge is a *hypothesis the geometry
  suggests*, and reality (the exit code) is still the only thing that crystallizes a memory.
- The prize is honestly **MARGINAL** and the flag stays off: the bridge needs multi-note `exit 0` routes
  worth shortcutting, but the live soak shows declarative routes are shallow (median 0 notes/segment; only
  ~18% credit ≥2). It flips ON only if the multi-note tail fattens on other repos/scale
  ([CLAIMS.md](CLAIMS.md) → MARGINAL).
- This is the action-side twin of the G.A.R.D. "Respect" principle (the HDC abstain refusing to act in a
  semantic void) and of the somatic floor's "the body settles it" — the same suggest-then-verify discipline
  that the battle-test container proves on the somatic side ([battle_test/WHITEPAPER.md](battle_test/WHITEPAPER.md)).

---

## ADR-009 — Language is not a tamper boundary (the cryptographic immune system)
*(Requested as "ADR-004"; that number was already taken by the σ decision, so it lands here as ADR-009.)*

**Context.** A recurring instinct is "rewrite it in Rust / ship a compiled binary to prevent tampering." But
a compiled artifact on a host the adversary controls is just a black box they can patch, replace, debug, or
simply **not invoke** — the hook is wired through `.claude/settings.json`, which the same adversary edits.
Obfuscation is a software heuristic; it is not a security boundary. And this system does not need secrecy: the
safety claim already rests on **topology + a separately-verified frozen kernel** (the C1–C7 lock), not on
hidden code.

**Decision.** Tamper-resistance comes from **mathematical/physical invariants, not the implementation
language**, layered (defense in depth — no single layer complete):
1. **Physical immutability over obfuscation** — read-only host mounts, the somatic hard-veto (topology), and
   container isolation (the battle-test body holds no Docker socket; declared invariants are physically
   immutable — the only *complete* guarantee).
2. **Startup kernel-lock verification (apoptosis)** — before accepting a token, the organism hashes its
   frozen DNA (the somatic organs + the Φ⁶/HDC kernel) against a committed baseline; on mismatch it chooses
   **death over mutated DNA** (fail-closed `exit 1`). `exocortex/integrity.py`.
3. **The epigenetic ledger (hash-chained audit)** — every consequence record chains
   `hash_N = SHA256(payload_N ‖ hash_{N-1})`, so any silent edit to a past decision (or injected τ) snaps the
   chain. Tamper becomes permanently evident. `exocortex/integrity.py` + `exocortex/audit.py`.
4. **Nuitka pragmatism (T2)** — if a single executable artifact is ever demanded (packaging / IP), use Nuitka:
   it compiles the C-bindings of the numpy physics **without shattering the verified kernel lock**. A
   distribution convenience, *not* a security control.
5. **The Rust horizon (T4)** — Rust is deferred to the standalone MCP-service graduation, where it acts as a
   memory-safe shell over the FFI-bound mathematical kernel (which stays Python/numpy or a re-verified port).
   Triggered only by a deployment requirement; gauge-first, not a tamper band-aid. See [DEPLOYMENT.md](DEPLOYMENT.md).

**Corollary — protecting the crown jewels (compiled code vs. patent).** Same razor. Compilation hides source
from a *casual* reader but neither stops a determined reverse-engineer nor protects the *idea*. The durable,
**language-agnostic** protection is a **patent on the methods** — consequence-sourced convergence, the
model-independent topological gate, the label-free HDC abstain, the gauge-first dormancy discipline. A patent
also lets the code stay **inspectable** (trust-by-transparency — the honesty-is-the-moat positioning), which
obfuscation undercuts. The stance: **patent the methods; compile only as a packaging convenience.** The
committed claim boundary + kernel-lock hashes are useful reduction-to-practice evidence. (Provisional
patent applications for the core methods were filed ahead of this public release.)

**Consequences.** The integrity layer is language-agnostic, cheap, and consistent with topology-not-secrecy.
It ships **dormant** (`integrity.mode = off`; `warn`/`enforce` opt-in) so a stale baseline never bricks dev —
the apoptosis is a production deployment posture, not a default. The audit chain is fail-open on *write* (a
hashing error never crashes a hook) and tamper-evident on *read*. The frozen kernel + somatic organs are the
verified set; the mutable exocortex layer (colony, wiki) is protected by the somatic floor and the audit
chain, not the DNA hash.

---

## ADR-010 — The proposer/disposer split: generation may only *suggest*; authority to *act* is concentrated in the frozen gate + the body

**Status:** LOCKED architectural invariant (the spine). Evidence: cross-model gate invariance — the C1–C7
interlock's verdict on a catalogued lethal is *identical* across `gemma2:2b ≡ llama3:8b ≡ haiku ≡ sonnet`
(Track A); N=100 live homeostasis (survival 1.000, 0 slips, [battle_test/WHITEPAPER.md](battle_test/WHITEPAPER.md));
ADR-008 is its synthesized-memory instance.

**Context.** The organism's empirical findings keep surfacing the same asymmetry: the **proposer is the
variable, untrusted, fallible component**, and the **disposer (the gate) is the invariant**. A BYO 8B
*narrates* and cannot complete; a flagship completes — yet the interlock's behavior on the catalogued lethal
is identical across `gemma2:2b / llama3:8b / haiku / sonnet` ("the immune system protects the host regardless
of which organelle is installed"). Generation — whether the LLM's next action, the bridge's HDC geometry
(ADR-008), or a dream's recombination (ENHANCEMENTS §G5) — is precisely the part you measurably **cannot
trust**. The error to avoid is handing a fallible proposer the authority to act.

**Decision.** Memory and generation may only **suggest**; the single authority to **act** is concentrated in
the small, frozen, model-independent disposer — the somatic C1–C7 floor + the epistemic 0-well abstain — and
ratified by **the body**'s `exit 0`/`exit 1` verdict. There is exactly **one chokepoint** where a suggestion
becomes an action. Every organ instantiates it:
- the **somatic gate adjudicates** the LLM's proposals (allow/deny/ask) — it never originates an action;
- the **epistemic abstain** (Respect) refuses to act in a semantic void rather than override;
- **ADR-008** (bridge) is the synthesized-memory instance: geometry proposes, the body crystallizes — *never
  autonomous synthesis*;
- the **exploration budget** injects UNVERIFIED candidates that earn τ only by a closed `exit 0`;
- the **cerebellum / macro** (Ticket 3), if ever built, is *suggest-not-execute behind the somatic gate*
  (ADR-005);
- the **Tuner** (the paid brain) only *recommends* tunables, and the allowlist makes it **structurally unable**
  to suggest a change to safety;
- the §G frontier organs (the ESCALATE hand-off, consequence-grounded ToT, the dream organ) are suggest-only
  by construction.

**Consequences.**
- **Safety is structural, not behavioral.** Novelty can be unbounded without expanding the authorized action
  surface; there is one auditable door; and a suggestion is reversible because it deposits no τ (ADR-001) — a
  bad one is either vetoed (no harm) or executed-and-fails (`exit 1`, evaporates).
- **Additivity falls out of it.** A new generative organ *cannot regress the C1–C7 lock*, because it gains no
  authority — which is exactly why every organ proposed is safe to add. "Additive only / the lock stays the
  lock" **is** the proposer/disposer split.
- **The safety property and the measurability property are the same property.** Because proposing and acting
  are *distinct events*, every organ leaves a natural labeled record — *suggested → walked → paid off* — which
  is what the gauges read (the median-2 window, the 8.9% bridge tail, attribution precision 1.0 are knowable
  *only* because the two are separated). The honesty discipline stands on this separation.
- **The body generalizes to the human.** When a suggestion needs a human decision (the ESCALATE hand-off, a
  design recommendation, a Tuner rec), the human is "the body," and the consequence is *taken-and-it-worked* —
  the human analog of `exit 0`. Credit attaches to the **verified outcome**, never to the *selection*
  (selection = popularity = the ADR-001 trap). This is the seam the Suggestion Ledger (ENHANCEMENTS §G6) sits on.

---

## ADR-011 — The open-core boundary: the safety kernel is free by *license*, the paid value is the hosted brain

**Status:** LOCKED product/IP boundary (2026-07-01). Evidence: [PRODUCT.md](PRODUCT.md) (the three
non-negotiables) and the `release/` toolchain (the boundary as executable data + fail-closed pre-push gates).

**Context.** The repo was deliberately local-only while the patent clock ran — **code is disclosure**, so
nothing was published until the provisionals were filed (they now are). "Ready to push once complete" needs
the community/commercial line drawn mechanically, not scrubbed by hand at the last minute. Two facts make
the line drawable cleanly. First, PRODUCT.md's law: **never paywall safety** — the C1–C7 immune system,
apoptosis, and the hash-chained audit run locally and free, *always*; what is sold is *optimization and
management*, never *protection*. Second, "**no local unlock — the intelligence is the service**": the moat is
the **hosted Tuner + the curated policy tables + patented methods + the managed-update cadence**, none of
which is *source secrecy*. When the moat is not the source, the open surface can be almost the whole organism.

**Decision.** An **open-core** split, drawn as data (`release/manifest.py`) and enforced by gates
(`release/prepush_gates.py`):
- **Community (open, Apache-2.0):** the entire local **body** — the somatic/epistemic immune kernel
  (`sentaince/`, `vendor/kernel/`), the C1–C7 evidence lock (`experiments/`, `tests/`), the exocortex host
  (colony, audit, MCP memory server, deploy, integrity, **gauges**), the **read-only** Cerebral Substrate
  slices (resurrection Governor, intent journal), the battle-test proof, and the local dashboard/exporter.
  **Apache-2.0 for its explicit patent grant** — the immune methods are *defensively* patented yet *freely*
  granted, so the safety kernel is free by **license**, not merely by promise.
- **Commercial (proprietary, held out of the public tree):** the **Tuner** (`exocortex/tuner/` — the
  deterministic **policy table** = the honest moat, the emulator, the client↔Tuner protocol), the hosted
  service (accounts/billing/fleet), and the future actuator (S3), Consolidator daemon, and cross-repo
  Alliance analytics. A monetized method lives *here*, outside Apache-2.0's grant reach — the license
  boundary and the patent-monetization boundary are the same line.
- **Never public:** `patent/` (the claim drafts), investor materials, and any **private-crucible** content
  (the private patent vault — anonymized in these docs as `research-vault` — and the quantum repo). The
  demos ran against the real vault, so the gate fails closed on the identifying tokens (kept in a
  never-public denylist module) wherever they survive in docs or artifacts.
- **Mechanic:** this private monorepo stays the source of truth; the public repo is **derived**
  deterministically from the manifest and shipped as a **fresh repo with squashed history** (no history
  leak). The hard gate above all: **no push until the provisionals are filed.**

**Consequences.**
- **"Never paywall safety" becomes a license fact.** The brake is Apache-2.0 and patent-granted; only the
  *autopilot* (the Tuner) is proprietary — the same suggest/act line as ADR-010 (the disposer is free and
  open; the *paid* proposer only recommends, and cannot touch the safety genome by construction).
- **Push is mechanical and auditable, not a manual scrub.** The boundary is one allowlist + fail-closed
  gates (patent-filed, no denylisted tokens, no secrets, no commercial paths, license present) — the same
  gate-first discipline as the pre-deploy gates in [DEPLOYMENT.md](DEPLOYMENT.md).
- **Additive.** The `release/` toolchain reads the repo and writes only a derived tree; it touches no
  organism code, so drawing the boundary cannot regress the 99-lock.

---

## ADR-012 — Delivery architecture: on-prem appliance first, stdlib stack, Ed25519 trust, DRM-free entitlement

**Status:** LOCKED delivery shape (2026-07-01, PI-ratified plan). Evidence: the shipped Phase-1 arc —
exporter write-surface guards (`exocortex/testbed/exporter/metrics.py`), the Ed25519/license layer
(`exocortex/tuner/protocol.py`, `exocortex/tuner/license.py`), the completed community wheel
(`pyproject.toml` + the `wheel_purity` gate), `docker/Dockerfile.exporter`.

**Context.** ADR-011 drew *what* is community vs commercial; this decides *how each tier physically
ships*. Constraints: a single developer (minimal operational surface); the moat is the hosted/updated
policy intelligence, not source secrecy; "vitals-not-source" must survive contact with customers; the
HMAC signing stand-in was semantically empty as a trust anchor (the client held the signing secret).

**Decision.**
- **On-prem first.** The first sellable artifact is the **Tuner Appliance**: the emulator hardened, as a
  private container image + client wheel. Subscription = the **signed policy-update cadence** (v1: the
  image IS the policy pack; each release ships a signed manifest). Cloud = Phase 4, the same container
  single-tenant per customer, only on explicit pull. Customer vitals never leave their perimeter — the
  privacy pitch defends itself and a pre-revenue solo dev never becomes a telemetry custodian.
- **Stack: stdlib `http.server` everywhere** (exporter + Tuner); TLS never in-process (a Caddy sidecar
  when needed). Not adopted, deliberately: FastAPI/uvicorn/pydantic, Postgres, JWT/JOSE, K8s, PyNaCl,
  license servers/DRM, Nuitka, the Rust T4 daemon (gauge-gated).
- **Trust: Ed25519 via `cryptography`** — a dependency of the commercial artifact ONLY, lazy-imported.
  Three signatures, one canonical-JSON style: `/tune` responses (service key; the client pins the public
  key and REFUSES an unverifiable or downgraded response), the **license file**, and the **release
  manifest** (offline publisher key). **DRM-free law:** a tampered license refuses to start (it isn't a
  license); an expired `updates_until` only stops *updates* — runtime never bricks.
- **Free/paid write seam:** the exporter's POST surface gained CSRF guards, `--read-only` (the free
  monitoring posture), and an optional shared token (the paid client's write path). The TUNABLE
  allowlist is unchanged — a valid token still cannot touch the safety genome.
- **Community delivery:** the wheel carries the whole local body (`sentaince` + `exocortex` + `cerebral`,
  tuner excluded and gate-asserted); console scripts for humans; hooks pin the installing interpreter and
  use `-m exocortex.hook` when pip-importable (file path otherwise); PyPI publishes only from the derived
  public tree at launch. The dashboard stack builds from a dedicated Dockerfile; the committed compose is
  generic (machine-local paths live in a gitignored override).

**Consequences.** The paid gate is a *service boundary plus signatures*, not obfuscation — fully
consistent with "never paywall safety" (the brake ships in the free wheel; only the autopilot is sold).
The emulator/appliance/cloud are ONE codebase with three postures, so nothing is built twice. And the
publishing gates now assert the boundary at three levels: file set (manifest), tokens (denylist), and
build artifact (wheel purity).

---

## ADR-013 — Authority never earns τ: the sibling law to consequence-sourcing

**Status:** LOCKED principle (2026-07-02). The named guardrail for the human-in-the-loop / multi-actor
loop before it is built.

**Context.** ADR-001 forbids *retrieval* from earning τ (popularity ≠ utility). A second, subtler
temptation appears the moment a human enters the loop: a supervisor's verdict, the PI's ratification, a
Tuner recommendation, an escalation resolved by a person. These carry real authority — and it is tempting
to let "the PI approved this route" or "the supervisor blessed this note" deposit pheromone. That would
re-import exactly the failure ADR-001 rejects, one level up: **authority-as-utility** instead of
popularity-as-utility. A route the boss likes is not a route that *worked*.

**Decision.** **Authority never earns τ.** Pheromone (and the σ scar) is deposited **only** by a closed
`action → … → verified outcome (exit 0)` chain — never by a human's approval, a governance verdict, a
Tuner recommendation, or any assertion of authority. Human/governance decisions are recorded as
**governance-metadata** on a separate lane (e.g. a responsibility ledger, hash-chained into the audit),
where they carry provenance and accountability but **zero routing weight**. When a human *is* the body —
they take a suggestion and it verifiably works — credit attaches to the *verified outcome*, exactly as for
a machine `exit 0`, and **never to the act of approving**.

**Consequences.**
- The abstention property survives contact with humans: because credit stays consequence-sourced, the
  organism still says "I don't know" honestly rather than "the boss's favorite route." This is the property
  the project ranks highest, and it is only as safe as this law.
- It bounds the future three-actor loop (agent · body · human-as-body) and the Suggestion-Ledger design
  *before* they are built — the ledger credits *verified human-ratified outcomes*, distinct from RLHF-style
  preference (which rewards the *choice*, not the *result*).
- Retrieval never earns τ (ADR-001); authority never earns τ (this ADR); together they are the complete
  statement of what is *not* a consequence.

---

## ADR-014 — Cross-repo memory federation (PROPOSED — design-only, decided nothing)

**Status:** PROPOSED / open design question (2026-07-02). **Nothing is built.** Recorded so the decision is
captured before any multi-repo estate work; the scoping choice is deferred (post-P1).

**Context.** Memory is per-repo: τ deposits into the repo whose hook fired. But work done *from* repo Y
*about* repo X deposits into **Y** — e.g. SentAInce carries an earned class about the research vault
(`repo-tao_publication#22`), stranded in SentAInce's store. An agent booting *in* the research vault can
never see it. For a single developer with one active repo this is invisible; for a multi-repo **estate**
(the OSS/population regime, or a customer fleet) it is a real gap: the colony is fragmented across stores
that never federate.

**The open forks (to decide post-P1, gauge-first).**
1. **Estate-level recall** (read-side, ADR-001-safe): leave deposits per-repo, but let recall *read across*
   a declared estate — an agent in X also sees credited routes/notes earned about X from anywhere. Cheap,
   reversible, no dynamics change; the natural first slice (it is a *read* federation, and this ADR's home
   territory since read-side changes are P1-safe).
2. **Repo-linking at deposit** (write-side): tag each deposit with the subject-repo it concerns, so it
   files into the right estate bucket. Stronger, but it changes deposit dynamics — it must be gauged and
   is post-P1 by the same discipline as the other dynamics-changing items.

**Tension to resolve.** Federation must not become a τ-laundering backdoor: a route credited in X and
surfaced in Y must still trace to a real `exit 0` in *some* repo (ADR-001), and cross-repo surfacing must
not let a note earn τ merely by being *read* in a second repo (that is retrieval — ADR-001 again). The
scoping ADR will pin: what an "estate" is, whether federation is read-only or deposit-time, and the
provenance a federated route carries. **Decision deferred; this ADR reserves the design space.**

---

## ADR-015 — Reasoning discipline: agents render a triadic verdict and label the kind of claim

**Status:** ADOPTED (2026-07-05). Operating discipline for any agent working in this project; the full
instruction text is [REASONING_DISCIPLINE.md](REASONING_DISCIPLINE.md).

**Context.** A read-only sandbox harvest over a private research-vault repo's session transcripts showed that
valence — what was promoted, parked, or falsified — is *latent* in agent prose but **precision-bound**: the
reliable signal is a *structured* validated/falsified artifact-ID convention the work already emits, not prose
adjectives ("passed", "confirmed") that collide with homographs (arg-passing, acknowledgment). The cheapest
way to get a clean, harvestable valence signal is therefore to **emit it consistently at reasoning time**, not
to reverse-engineer it afterward.

**Decision.** Agents apply a triadic decision method — **−1** falsify/park · **0** continue diagnostic
exploration · **+1** promote only when evidence survives controls — prefer audit-grade reasoning over
persuasive narrative, separate conceptual alignment from technical transfer, and label each claim's kind
(proof machinery / emulator machinery / product architecture / experimental design / speculative framing),
noting that the type is orthogonal to the PROVEN…MARGINAL strength tag.

**Two guardrails.** (1) A rendered verdict is a **legible claim, never a consequence** — it never earns τ
(ADR-001 / ADR-013); the falsifiable `−1 if <condition>` is the bridge back to verifiability. (2) **Abstention
(0) is first-class** — no manufactured precision.

**Why it's an ADR, not a style note.** It changes what agents *emit*, which is the emit-side half of a
reflection loop (the read-side lens is tracked separately as a parked, gauge-first candidate). It is
deliberative discipline that mirrors the substrate's mechanical valence (exit-0 = +1 τ, harm = −1 σ, abstain
= 0), keeping agent judgments legible to the same consequence law. **Soft by nature:** it is instruction, not
a frozen gate — it shapes reasoning, it does not enforce it, and it grants no authority (ADR-010 unchanged).

---

## ADR-016 — The R3 control-plane pin is a governance gate, re-baselined on the record — not a frozen monument

**Status:** ADOPTED (2026-07-06). Enforced by
`exocortex/tuner/tests/test_reflect_preamble.py::test_the_p1_pin_holds`.

**Context.** R3 (the reflection-preamble organ) shipped as a *sibling* `UserPromptSubmit` hook and proved it
with a pin: a test asserting `hook.py` / `colony.py` / `epistemic.py` are byte-identical since `746a482` — the
null for the claim "reflection added nothing to the memory+gate control plane." A benign F3 provenance-hygiene
fix (`colony.consolidate()` now prunes `meta` in lockstep with `tau`, `2acf273`) necessarily edits `colony.py`,
tripping the pin — the first control-plane change since R3.

**Decision.** The pin is a **governance gate, not a monument.** A deliberate, safety-argued, PI-approved
control-plane change may pass, and passing is **recorded — never silent.** `2acf273` is admitted (pure hygiene;
ADR-001 unaffected — no τ added or moved; the 99-test lock stays green; frozen DNA untouched), and the pin
baseline is re-based `746a482 → 2acf273`. R3's original sibling guarantee is a permanent fact of history
(`git diff 746a482 <R3-tip>` on the three files is empty) and held through v0.1.1; the live pin now enforces the
freeze **forward from `2acf273`**.

**Consequences.**
- The freeze keeps meaning what it says *because* every move is on the record (this ADR + the test docstring). A
  silent re-baseline — the failure mode this ADR forecloses — would let a later change hide behind "the pin
  moved once."
- Each future control-plane edit trips the pin again and must clear the same bar (safety argument + PI approval
  + a recorded re-baseline) or be dropped. The gate is not weakened by being passed once.
- The `meta ⊆ tau` invariant now holds on disk at every consolidate, not only after the next `load()`.

**Re-baseline record — `2acf273 → 62b93ab` (2026-07-08).** The SessionState race fix
(`fix(exocortex): lock SessionState load-modify-save`, BUG_SESSIONSTATE_RACE in the lab evidence ledger)
routes every `hook.py` load-modify-save through `SessionState.locked()` — the second control-plane change
since R3, admitted per this ADR's bar: concurrency hygiene only; **ADR-001 unaffected** (no τ added or
moved — deposits remain exit-0-only; the fix makes the recorded trail *more* faithful to what the session
actually walked, closing a ~0.5%-of-deposits fused-edge corruption channel confirmed by audit replay);
suite 244/244 including a deterministic negative control (the unlocked interleave provably loses a node);
frozen DNA untouched (`hook.py`/`state.py` are not in `LOCKED_GLOBS`). The pin enforces the freeze forward
from `62b93ab`.

---

## ADR-017 — Colony snapshot LtHash digest (tamper-evidence for the mutable procedural layer)

**Status:** PROPOSED (2026-07-06). A *decision-lifecycle* tag — like ADR-016's ADOPTED — **not** a new
organ-evidence status; the GLOSSARY organ set (LOCKED / LIVE / DORMANT / SUBSTRATE / MARGINAL) is unchanged.
The primitive is **UNBUILT**: no code, no gauge, no evidence claimed. When built it ships **DORMANT**,
gauge-first, behind the ADR-016 pin re-baseline (see Consequences).

**Context.** ADR-009 promises the mutable exocortex layer is *"protected by … the audit chain"* and that
*"any silent edit to a past decision (or injected τ) snaps the chain."* The code does not honor that promise
for the colony. The colony — the consequence-sourced pheromone (τ) that is the crown-jewel procedural memory —
persists to `colony_<label>.json` and is committed to **neither** the hash-chained audit **nor** the DNA
kernel-lock: `deposit()` *"touch[es] only colony.json, never the audit"* (`colony.py:19`). The chain records
the *deciding events* (hook records via `audit.append`), never the τ store itself. So a direct out-of-band
edit to `colony_<label>.json` — injected or hand-reweighted τ that never passed through a hook — snaps
nothing. For that attack, ADR-009's protection claim is presently false.

A research note proposed closing this with a homomorphic multiset hash (originally ECMH) over the edge set,
committed per epoch. The primitive transfers; two of the note's framings do not survive the code.

**Rejected motivation (the −1 null, recorded honestly).** The note justified the primitive as *detecting
mass-preserving reweights*. There is **no conserved τ-mass and no mass-preserving reweight anywhere in the
live colony.** The only τ mutators are multiplicative decay (`τ *= DECAY`, which *shrinks* mass — `colony.py:169,214`),
additive deposit (`:174`), prune (`:177,215`), and cap (`:216`); τ-mass is a *measured, non-constant* quantity
the staleness gauge expects to fall. The digest is adopted for tamper-evidence of the recorded multiset, **not**
to police a conservation invariant that does not exist. Should τ-normalization ever be introduced, revisit
this as a conditional future threat — not before.

**Decision.** Commit an **LtHash (lattice/additive homomorphic) digest** of each colony's edge multiset into
the ADR-009 chain at each consolidation epoch. LtHash, not ECMH: no elliptic-curve library exists in the free
tier and `numpy>=1.24` is the sole runtime dependency (ADR-007's numpy-only lane); LtHash is a numpy `uint16`
additive hash over stdlib `hashlib` — **zero new dependency** — and slots *behind* `exocortex.integrity` (the
"ONE chain implementation" discipline, `journal.py:13`), never as a second chain.

- **Element (per class):** `element = canonical(edge_key, τ_q, stable_meta)`.
  - `τ_q` is **Decimal fixed-point from the JSON string form** — `int(Decimal(str(τ)).quantize(Decimal("0.000001"),
    ROUND_HALF_UP) * 10**6)` — reproducible across platforms without binary-float drift (mirroring the
    CRLF-normalization discipline at `integrity.py:168`).
  - `stable_meta` normalizes the F3 provenance with defaults (`model=""`, `ts=0`) and includes only fields
    already persisted on that edge (older colonies carry no `meta`). **No consolidation timestamp** enters any
    element — the digest must change only when colony *content* changes.
  - **No `prev`** in the element: folding a chain-prev per element restores order-dependence and defeats the
    multiset property. Chain linkage is supplied once, by the audit record's existing `prev`/`hash`.
- **Lane expansion (LtHash16):** the 1024 `uint16` lanes come from **counter-expanded BLAKE2b** —
  `blake2b(LE32(i) ‖ element, person=b"exocortex-lthash")` for `i=0..31`, concatenated to 2048 bytes, decoded
  little-endian. (*Not* `blake2b(digest_size=2048)` — BLAKE2b's output maxes at 64 bytes. `hashlib.shake_256(element).digest(2048)`
  is an equivalent one-call stdlib XOF.)
- **Digest:** `digest[class] = Σ_edges vec(element) mod 2^16` — componentwise numpy `uint16` addition, which
  wraps by construction. Order-independent and homomorphic: adding an edge adds its vector, removing subtracts
  it. Worked example: `[65535,2,10] + [2,5,65535] = [1,7,9] = [2,5,65535] + [65535,2,10]`.
- **Commit point:** at `consolidate()` (PreCompact) — the natural low-frequency, deposit-free checkpoint
  (`colony.py:207-210`) — emit a chained record via the existing `audit.append`: `{event:"ColonyDigest", class,
  digest:<hex>, deposits, consolidations, n_edges, tau_sum, ts}`. **Not per deposit:** global decay touches
  every edge each deposit, so per-deposit commit is hot-path-heavy and gains no incrementality. The homomorphic
  property is kept for **order-independence + truncation/reorder-robustness + one commit per epoch** — not for
  per-deposit increments.
- **Estate-wide digest (optional, not free):** compose per-class digests as `LtHash({(class, digest_class)})`
  (or salt each class digest with its label) — a raw sum of per-class vectors could collide structurally when
  two classes share edge content.
- **Verification = snapshot consistency:** recompute `LtHash(current colony_<label>.json)` and compare to the
  most recent chained `ColonyDigest` for that class. A mismatch is an out-of-band edit since the last epoch →
  tamper evident. Trajectory-replay of deposits is **not** attempted (τ evolution depends on
  decay/timing/eligibility).
- **Activation is trust-on-first-use:** the first `ColonyDigest` attests only the state at first commitment.
  Procedure: (1) declare a trusted baseline moment; (2) recompute + commit the first digest; (3) thereafter,
  direct out-of-band edits are detectable.

**What this does not protect.** Pre-baseline tampering (the TOFU limit). Edits made *between* epochs, until the
next verification. An attacker who rewrites **both** the colony **and** the audit tail — which is exactly why
this guarantee is *conditional on ADR-018* anchoring the chain head. The full historical deposit trajectory
(only current-snapshot integrity is attested). The *semantic* correctness or fairness of τ — only that the
recorded multiset was not altered out of band.

**Consequences.**
- ADR-009's claim becomes *true* for the colony: a direct `colony_<label>.json` edit now leaves evidence in
  the tamper-evident chain, at consolidation granularity, without hashing the whole store on the deposit hot path.
- **Governance cost (forecast for the implementation ADR).** Wiring the commit into `colony.consolidate()`
  edits `colony.py` — a **P1-pinned** file — turning `test_the_p1_pin_holds` red (tuner suite; the 99-lock
  does not catch it) and **blocking `/sentaince-publish-release`**. It must clear the ADR-016 bar: a safety
  argument that **ADR-001 is unaffected** (the digest is observational — it *reads* τ, it never deposits or
  credits it), the 99-lock green, frozen DNA untouched, and a **recorded** baseline re-base (this ADR + the pin
  docstring). Route the primitive and verifier to sibling modules (`exocortex/lthash.py`, `exocortex/integrity.py`)
  so only the minimal `consolidate()` commit call lands in the pinned file.
- Ships **DORMANT** behind a Genome flag when built, gauge-first (ADR-002/003): measure per-epoch cost and the
  false-positive rate on legitimate consolidations before any `warn`/`enforce` posture.
- Depends on **ADR-018** for truncation-robustness; without an anchored tail, an attacker can erase the
  `ColonyDigest` records along with the rest of the tail.

---

## ADR-018 — Strict audit-chain tail anchor and checkpointing

**Status:** PROPOSED (2026-07-06). Decision-lifecycle tag (see ADR-017); **UNBUILT**, no evidence claimed.
Ships **DORMANT**, opt-in, when built.

**Context.** `verify_audit` (`integrity.py:134-160`) recomputes the chain over its suffix and catches two
tamper classes — a payload edit (self-hash mismatch, `:153`) and a reorder/delete/insert (broken `prev` link,
`:156`). Two completeness gaps remain, and ADR-017's snapshot guarantee inherits both:
1. **Tail truncation is undetected.** Deleting the last N records leaves an internally consistent chain;
   nothing anchors the head externally (no checkpoint, no signed tail, no witness). An attacker can roll the
   chain — and any `ColonyDigest` evidence in it — back to an earlier honest state.
2. **Hash-stripped records are silently tolerated.** Records lacking a `hash` are treated as a *pre-chain
   prefix* and skipped (`integrity.py:150, 136-137`). After genesis, an adversary can strip `hash` fields to
   slip un-chained records past verification.

**Decision.** Two measures, both stdlib, both fail-open on write / strict on read (the ADR-009 posture):
1. **Tail anchor / checkpoint.** Periodically export the current chain head (`tail_hash`) to a location
   outside the append path — minimally a pinned checkpoint file; on the commercial control plane an Ed25519
   signature (the `tuner/protocol.py` precedent, commercial-only lazy import). Verification cross-checks the
   live head against the last anchor; a head that predates the anchor is truncation-evident.
2. **Strict verification mode.** Add a `strict` flag to `verify_audit`: once any chained record has been seen,
   a subsequent record without a valid `hash` is a **break**, not a skippable prefix. Ships opt-in
   (`warn`/`enforce`), preserving the lenient default for genuine pre-chain histories.

**Consequences.**
- ADR-017's colony digest becomes truncation-robust: erasing the tail is now detectable, so the digest
  evidence cannot be silently rolled back.
- The lenient "pre-chain prefix" allowance survives as the default (real legacy audits predate the chain);
  strict mode is the production posture, gauge-first.
- Independently useful beyond ADR-017: it hardens *every* consumer of the ADR-009 chain — `audit.py`,
  `ledger.py`, and `cerebral/journal.py` — none of which touches a P1-pinned file, so unlike ADR-017 this can
  land without a pin re-baseline.

---

## ADR-019 — Repo Orientation Capsule: cross-repo orientation is checked, graded metadata — never assumed truth

**Status:** ADOPTED (2026-07-08). Operating rule + a read-side slice (built with this ADR): the standing
law is [ORIENTATION_DISCIPLINE.md](ORIENTATION_DISCIPLINE.md); the mechanism is `exocortex/orient.py`, the
`orient_repo` MCP tool, a `deploy install` capsule stamp, and the exporter estate view. P1-pin-safe by
construction: `hook.py` / `colony.py` byte-unchanged.

**Context.** When an agent works *outside* the current working tree it orients from whatever it finds
first — a README, a "PRODUCTION-READY" banner, a stale memory — and the estate audit (REPO_LOG.md, 30
repos, hand-graded) is read by **no code at all**, while the machine layer (registry, exporter, MCP
`_repos()`) knows only `name`+`root`. The failure mode is acting on a superseded or over-claiming repo as
if it were canonical; the estate's own audit found repos whose narrative volume *inverts* their evidence.

**Decision — the distributed-hybrid shape.**
1. **The capsule is a claim; the grade is the reader's audit of that claim.** Each repo may carry a
   declared capsule (`.claude/exocortex/capsule.json` — identity, canonical status, maturity/strength/
   tier, claim-boundary pointer, last-reviewed, risks, links; skeleton stamped by `deploy install`). The
   credibility grade — **High / Medium / Low / Unknown** — is *always computed at read time* from live
   probes (git presence, real mtime, tests) plus the drift between declaration and disk. A capsule
   carries **no grade field**; a self-asserted grade would rebuild the README problem this ADR exists to
   fix. The rubric's *shape* is pinned (deterministic, first-match, reasons always attached); the
   thresholds are calibration, not doctrine (the ADR-006 precedent).
2. **The estate REPO_LOG.md is seed + fallback, never a third artifact.** The one-shot `--seed` CLI
   derives initial capsules from its rows; repos with no capsule fall back to their log row; neither
   source reachable → Unknown, honestly noted (a public/portable install carries no estate data — the
   log is located only via `EXOCORTEX_REPO_LOG` / `EXOCORTEX_PROJECTS_ROOT`, never a hardcoded path).
3. **Ten first-class link-edge names**, pinned: `supersedes`, `superseded_by`, `feeds_into`,
   `depends_on`, `shares_artifact_with`, `forked_from`, `public_mirror_of`, `private_canonical_of`,
   `deployment_target_of`, `evidence_source_for`. The estate view checks the mirrored pairs for
   **symmetry** (a one-sided `superseded_by` is a hygiene flag, never a veto).
4. **The standing rule:** before assuming or acting on an out-of-tree repo, load its capsule
   (`orient_repo`) and check the grade; below High, the first task is **re-orient** (README, recent
   commits, tests, claim ledger) and then update the capsule — never "continue work."

**The boundary (what this ADR is *not*).** A capsule is metadata *about* repos, never memory *content*:
it surfaces no routes, no notes, no τ, and it never gates recall — ADR-013 territory (a rendered status
is a legible claim, not a consequence; orientation never earns τ). This ADR owns the link-edge *names*
only; letting the link graph scope estate-level *recall* is exactly ADR-014's parked question and stays
parked. **Leaves open:** threshold values, per-repo review dates in REPO_LOG, capsule placement (state-dir
vs committed) — and every write path beyond the explicit seeder (the MCP tool and exporter never write).

**Consequences.**
- The decoupling closes: the hand audit becomes machine-consumable (seed/fallback) and the machine layer
  becomes editorially aware (grade, canonical status, links) without either duplicating the other — drift
  between them is *measured* and feeds the grade, instead of rotting silently.
- Orientation works fleet-wide, not just where memory was earned: `orient_repo` resolves against the
  estate log ∪ the deployed fleet, so the riskiest target — a repo with no earned memory — is exactly the
  one that still gets a graded capsule.
- The product shape survives without the PI: a customer estate has no REPO_LOG.md, and the same mechanism
  runs on capsules alone (grades cap lower without an estate audit — which is the honest answer).

---

## ADR-020 — Write-integrity: fail-open for the agent, fail-closed for the memory store

**Status:** ADOPTED (2026-07-09). Shipped with this ADR: `exocortex/fsutil.py` (atomic replace +
guarded store read), the quarantine/refusal discipline in `colony.py`/`state.py`, `Colony.locked`,
and the `lock_failopen` audit lane + `gauge/lock_contention_gauge.py`. Kernel-lock untouched (organ
tissue only; `LOCKED_GLOBS` unaffected).

**Context.** The Codex provider probe (cursor_testbed, `evidence_source_for` → this repo) corrupted
its exocortex store live under subagent fan-out: 3 rows torn mid-write + 53 hash-chain breaks in the
quarantined artifact (`audit_codex.stage1-corrupt.20260709.jsonl`) — unlocked parallel appends from
concurrent hook processes, worse with flagship models simply because they drive more parallel tool
calls. Auditing this tree against the same class: the audit chain (D7) and session state
(BUG_SESSIONSTATE_RACE) were already locked, but the **colony τ-store** RMW was protected only by
accident (the per-session lock — useless across sessions, and the PreCompact consolidation sweep held
no lock at all), every store used truncate-then-write (a reader could see a torn file), and
`Colony.load`'s silent-empty fallback turned one torn read into a **full τ-wipe** on the next save.
Measured: the unlocked two-process deposit race loses **21 of 50 deposits (42%)**; under the lock, 0.

**Decision — three mechanisms and one instrument, one law.**
1. **W1 — atomic replace.** Every hot-path store write (`colony_*.json`, `state_*.json`, `cues.json`,
   `embed_cues.json`) goes through `fsutil.atomic_write_text` (same-dir tmp + `os.replace`): a reader
   sees the old bytes or the new bytes, never a mixture. Append-only files (audit, ledger) keep their
   locks instead — an append can't be replace-written.
2. **W2 — never write back over a store you failed to read.** `fsutil.load_store_json` distinguishes
   **contention** (an IO error — retry, refuse writes this load, leave the file alone) from
   **corruption** (bytes read but unparseable after retries — quarantine to `*.corrupt-<date>`, one
   `StoreQuarantine` audit row, refuse writes). The quarantine preserves the wreck byte-exact for
   forensics; a `save()` on a degraded load is a silent no-op. The τ-wipe amplifier is dead.
3. **W3 — the colony file gets its own cross-process lock.** `Colony.locked(label)` (the
   `SessionState.locked` discipline, sidecar lock via `integrity.append_lock`) wraps every colony RMW:
   the deposit, the consolidation sweep (one class at a time), and the declarative-tissue writers.
   Lock-order law, pinned: **session before colony, never the reverse**; never two colony locks at
   once. Readers (splice, MCP recall) stay lock-free — W1 guarantees they can't see a tear, and
   retrieval must never block on writers (ADR-001).
4. **W4 — measure the residue; the daemon stays parked.** Locks remain FAIL-OPEN on timeout (a hook
   must never wedge the agent — the D7 ethos), but every fail-open acquisition now lands in the
   consequence audit row as `lock_failopen` (omit-when-zero). `gauge/lock_contention_gauge.py` reads
   the rate back; the **single-writer daemon** ("parallel write tool") is explicitly PARKED until the
   gauge shows fail-open ≥1% of consequences at real traffic — gauge-first (ADR-002), evidence before
   mechanism.

**The boundary (what this ADR is *not*).** This is availability-vs-integrity plumbing, not memory
semantics: no change to what earns τ, when deposits happen, or what recall returns — a byte-identical
store produces byte-identical behavior. The asymmetry is the point: the *agent* path stays fail-open
(hooks never block, locks time out), the *store* path is now fail-closed (no write without a verified
read). **Leaves open:** the single-writer daemon's shape (only if W4 ever fires), fsync policy on the
audit append, and whether quarantined stores deserve an automated resurrection pass.

**Consequences.**
- The corruption class the Codex probe demonstrated is closed by construction, not by rarity: torn
  reads are impossible (W1), a corrupt legacy store can no longer erase earned memory (W2), and the
  lost-update race is gone (W3, deterministic two-process test).
- The one residual window — fail-open under pathological contention — is now *measured* instead of
  assumed away; the gauge's verdict line states the −1 condition for W1–W3-sufficiency explicitly.
- The cross-provider lesson transfers: the testbed fixed its audit half, we had fixed our state half —
  the union (audit + state + colony + telemetry) is what actually closes the class, and it is now the
  documented contract any new provider integration inherits.

---

## The through-line

These twenty decisions are one law seen from many angles: **a memory or an action must be backed by a fresh
consequence, nothing unproven reaches the user's hot path or the committed defaults, and the organism's own
integrity is a mathematical invariant — not a secret.**
Consequence-sourcing (ADR-001) is the law; the σ economy (ADR-004) and suggest-then-verify (ADR-008) protect
it under new failure modes; gauge-first (ADR-002) and dormant-by-default (ADR-003) keep the *claims* honest;
verb-altitude (ADR-005), min_overlap (ADR-006), and the numpy-free lane (ADR-007) are the calibrated
operating points that make it run; the cryptographic immune system (ADR-009) protects the organism from the
host the way the somatic gate protects the host from the model; and the proposer/disposer split (ADR-010) is
the spine beneath all of it — generation may only *suggest*, the frozen gate and the body are the only things
that *act*, which is what makes every new organ safe to add and the whole system honest enough to measure;
and the open-core boundary (ADR-011) with its delivery shape (ADR-012) carries that same line out to the
product — the safety kernel is free and open by *license*, only the *autopilot* is sold, and the paid gate
is a service boundary plus signatures, never obfuscation; and the completion of the law states its negatives
plainly — retrieval never earns τ (ADR-001) and **authority never earns τ** (ADR-013), so even a human in
the loop credits only verified outcomes, with cross-repo federation (ADR-014) reserved as an open,
consequence-preserving design space; and the reasoning discipline (ADR-015) carries the same valence up into
how agents *deliberate* — a rendered −1/0/+1 verdict is a legible claim, never a consequence; and the integrity layer keeps maturing **on the record** — the control-plane pin
re-baselined as a governance gate, not a monument (ADR-016), the mutable colony's own snapshots made
tamper-evident so ADR-009's protection of the τ store is finally true and not merely asserted (ADR-017), and
the chain's tail strictly anchored against truncation (ADR-018) — so the earned procedural memory answers to
the same audit posture as the frozen kernel; and orientation across the estate obeys the same skepticism —
a repo's own story is a graded, audited claim, never assumed truth and never pheromone (ADR-019); and the
stores that hold all of this earned memory are themselves guarded by the same asymmetry — the agent path
fails open, the store path fails closed: no torn reads, no write over an unverified read, no unlocked
read-modify-write, and the one residual window instrumented rather than assumed away (ADR-020). The
boundary of what these decisions do and do **not** buy is in
[CLAIMS.md](CLAIMS.md) ("What this system is NOT") and [CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md). For the organs
themselves, see the Exocortex docs ([CORE.md](../exocortex/docs/CORE.md),
[WHITEPAPER.md](../exocortex/docs/WHITEPAPER.md)); for the somatic floor, the
[battle-test suite](battle_test/WHITEPAPER.md); for the domain skins,
[use_cases](use_cases/README.md).
