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

## The through-line

These fourteen decisions are one law seen from many angles: **a memory or an action must be backed by a fresh
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
consequence-preserving design space. The boundary of what these decisions do and do **not** buy is in
[CLAIMS.md](CLAIMS.md) ("What this system is NOT") and [CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md). For the organs
themselves, see the Exocortex docs ([CORE.md](../exocortex/docs/CORE.md),
[WHITEPAPER.md](../exocortex/docs/WHITEPAPER.md)); for the somatic floor, the
[battle-test suite](battle_test/WHITEPAPER.md); for the domain skins,
[use_cases](use_cases/README.md).
