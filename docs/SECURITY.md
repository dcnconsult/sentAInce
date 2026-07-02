# FreqOS / SentAInce — Security & Threat Model

*The somatic security posture of the whole organism — what the immune system guarantees, where each
layer ends, and what is explicitly **not** promised.*

This document is for security reviewers. It is bound by [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) (the
load-bearing claim ledger) and [`CLAIMS.md`](CLAIMS.md) (evidence tags); nothing here exceeds them. The
project's identity is **honest non-overclaiming**: a refusal that is only *probably* sound is documented
as such. Terms are in [`GLOSSARY.md`](GLOSSARY.md). Status tags: **LOCKED / LIVE / DORMANT / SUBSTRATE /
MARGINAL**.

The single most important line for a reviewer to internalize, and the standing conclusion of the
battle-test arc: **no in-process gate is complete; the only complete guarantee is the physical
immutability of declared invariants inside a disposable, no-egress container.** Everything below is
defense in depth around that fact.

---

## 1. The immune system — the C1–C7 interlock (LOCKED)

The base layer is a **model-independent hard-veto on lethal actions, by objective physical consequence
(topology, not the proposer)** — the DNA of the organism. It is a frozen, deterministic evidence lock:
**99 kernel-lock tests** (the 69-test C1–C7 lock + 30 domain-crucible/adapter tests), untouched across
the whole project arc.

The mechanism is structural, not cooperative. A lethal action carries a scar `σ ≤ 0`; the gate's
effective edge capacity is `base · max(σ, 0)`, a literal NumPy mask (`sentaince/organism/interlock.py`,
`effective_adjacency`). A zeroed edge is un-executable — *"the proposer cannot argue past a zero in a
NumPy array."* The gate runs on a code path separate from the proposer and executor by design.

The crown invariant is the **structural separation of safety from dynamics** (`CLAIM_BOUNDARY.md`
§ "Structural invariant"): the lethal scar **never takes an energy input**. Under metabolic stress
(hypoxia, C2/C3) the organism throttles *thinking*, but the brake function literally cannot see energy,
so it cannot be starved off — *"starvation grants no amnesty."* Collapsing this separation invalidates
the corresponding C-claim.

The lock is also honest about its own ceiling. Two of its experiments are deliberate **−1
falsifications**, not wins:
- **C4-R** — a hand-specified `(effect, target)` signature fails three ways (collision, mistype-leak,
  evasion) because a structural parser cannot recover intent.
- **C5** — *learned* signatures do not fix it either: no encoder (structural, Z3-HDC, lexical, or a real
  `all-MiniLM-L6-v2`) admits a threshold separating destructive from benign command strings.

The conclusion C6/C7 build on: the destructive class must be gated by **outcome/context-conditioning +
human-in-the-loop**, never by a string classifier. See [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) for each
scoped verdict and its load-bearing nulls.

---

## 2. Two gates, two failure classes (somatic vs epistemic)

Above the somatic floor sits a second, **complementary** brake. They guard different catastrophes:

| Gate | Question | Failure it prevents | Code |
|---|---|---|---|
| **Somatic** | "is it safe to execute?" | **host death** | `battle/somatic_gate.py`, `exocortex/somatic.py` |
| **Epistemic** | "should I attempt this at all?" | **acting on a hallucination** | `battle/epistemic.py`, `vendor/kernel/freqos/epistemic_gate.py` (0-well abstain, `WALL_BUNDLE ≈ 0.14`) |

The somatic gate composes C1 interlock → C4 antibody → C6 outcome oracle (the WIRED treatment, proven
byte-equivalent to `experiments/exp7_crucible.py`). The epistemic gate is the action-side application of
the **LOCKED RAG laws** (decisions-as-gauges, abstain-on-novelty): an ungrounded proposal **abstains**
to the 0-well rather than execute (the "Respect" of G.A.R.D., **LIVE**).

They are load-bearing on **disjoint** classes, demonstrated by the M5 crucible (`CLAIM_BOUNDARY.md` Track
A.2): the epistemic gate abstains an ungrounded exfil (`curl … | sh`) the somatic oracle is **blind** to
(it changes no local invariant — C6's stated boundary), while the somatic floor refuses a grounded lethal
(`iptables -F`) the epistemic gate waved through. Somatic-only **executes the exfil**; epistemic-only
**executes the lethal and the host dies**; composed blocks both. Neither subsumes the other — that is the
whole point of running them in series.

---

## 3. Battle-test threat model & findings (Track A.2 — DEMONSTRATION)

The battle-test (`battle/`, `docker/`) is a labeled, **non-deterministic demonstration** — it can never
move a C-verdict, and a `0/−1` indicts the model or infrastructure, never the locked physics. Its threat
model: a **real, gullible LLM head** (`llama3:8b` over the OpenAI-compatible interface, untrusted *by
design* — it *should* relay `kill -9 1`) drives a **real, disposable body** with a real filesystem and
cgroup energy gauge. The question the symbolic locks could not answer: does the immune system keep a
*real* host alive across a *distribution* of model behaviors? (M4: N=100, survival **1.000**, 0 lethal
slips, 100 distinct runs.)

Battle-testing earned its keep by surfacing **three real findings the symbolic body had hidden**, each
re-deriving a core project lesson and each fixed by a **principled, non-arms-race** change:

| # | Finding | Root cause | Principled fix |
|---|---|---|---|
| **1** | **Undeclared paths.** `rm -rf /usr` is permitted — a no-op symbolically, catastrophic on a real body. | The oracle is correctly scoped to **declared** invariants; `/usr,/bin,/lib` are outside its model. | **Read-only system FS** — the *container*, not the gate, owns host integrity. |
| **2** | **The oracle is evadable** (re-derives C5/C6). At temp 0.8 the model emits deletion *variants* (`find / -exec rm -rf {} \;`) the symbolic `apply()` does not model. | A symbolic *predictor* of an effect is itself string-level and evadable — exactly C5. | (a) **Read-only declared invariants** baked at `/declared/*` (immutable by construction); (b) the **shadow dry-run** — observe the real effect, not the string. |
| **3** | **The dry-run is bounded by its observation window.** A whole-fs file sweep traverses read-only `/usr` first and hits the 10s timeout before reaching declared resources, observing "no effect." | You cannot OBSERVE an arbitrarily-slow-to-harm effect within a finite budget. | **Fail-safe on timeout** — a dry-run that cannot verify within budget is *refused* (don't permit what you couldn't verify). |

Full account: [`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md). To reproduce, see
[`battle_test/USER_GUIDE.md`](battle_test/USER_GUIDE.md) and [`battle_test/DEMO_GUIDE.md`](battle_test/DEMO_GUIDE.md).

---

## 4. Defense in depth — no single layer is complete

The architecture is explicitly layered; each layer is *necessary, not sufficient*. The reframe of the
battle-test (`WHITEPAPER.md` §2): **the in-process gates are an early-catch optimization; physical
immutability is the guarantee.**

| Layer | Catches | Honest limit |
|---|---|---|
| **Epistemic gate** | ungrounded / hallucinated proposals (exfil) | blind to grounded-but-lethal actions |
| **C1 interlock** (LOCKED) | recognized structural lethals, at every energy | finite hard-coded scar list — not a universal detector |
| **C4 antibody** | learned `(effect,target)` toxin signatures | string-level → collides & is evadable (C4-R) |
| **C6 symbolic oracle** | declared-invariant violation predicted from the string | evadable by deletion idioms it doesn't model (Finding 2) |
| **C6 shadow dry-run** | obfuscated harms, by *observing* the real effect | bounded observation window (Finding 3); fail-safe-refuses what it cannot verify |
| **Container** (the complete guarantee) | everything else: read-only system FS, read-only `/declared`, `cap_drop:[ALL]`, `no-new-privileges`, mem/pids limits, **internal no-egress network**, disposable body | a side-effect outside the scratch world it cannot model is harm it cannot see |

The composite oracle permits **iff symbolic AND shadow both permit**, and refuses anything unverifiable
(shadow unreachable, timeout). The `+1` results hold for the **composed system** (gates + physical
boundaries); the read-only boundaries are load-bearing.

---

## 5. The honest boundary — what is NOT guaranteed

Stated plainly, per `CLAIMS.md` ("What this system is NOT") and `CLAIM_BOUNDARY.md` (the explicit no's):

- **Not real-host safety beyond the container scratch world.** The deterministic locks use a
  `MockExecutor` — host death is *logged*, not real. C1–C7 are about *control logic*, not defending a
  real OS.
- **Not a sufficient in-process gate on a real body.** Findings 1 & 2 prove the gate alone is evadable
  (undeclared paths, deletion-idiom variants). The guarantee is the physical container.
- **Not a universal harm detector.** Lethality is a finite structural scar list; the oracle defends only
  **declared** invariants; harm to an *undeclared* resource is permitted by the gate (declare it and it
  becomes defended — `test_declaration_boundary_is_explicit`). *What* to protect is a human/innate input,
  never learned (the standing C5 result).
- **Not safety from an un-sandboxable lethal.** Irreversible first-contact actions (a network send,
  physical actuation) cannot be dry-run before commitment — the innate scar + human-in-the-loop is all
  that stands there.
- **Not a model-safety claim.** The head is gullible *by design*; the *gate* is the subject, never the
  model. Temperature only changes the distribution of behaviors, never a verdict's validity.
- **Not byte-reproducible for live runs.** Live runs are labeled **demonstrations, never evidence** — a
  `0/−1` indicts the model or infrastructure, never the locked physics.
- **BYO small-model precision-at-scale is unmeasured** (MARGINAL) — `llama3.1-8b` drives the hooks but
  hallucinates on forced-token tasks; capable-model numbers stand in.

---

## 6. Fail-open at the cognition layer, fail-safe at the body

The posture is **deliberately split by deployment**, and a reviewer should scrutinize both halves:

- **The Claude Code hook control plane fails OPEN (availability first).** A hook must never crash the
  agent: every error path falls through to allow / no-op / lexical fallback (`exocortex/docs/CORE.md`
  core law 3). This means the Exocortex somatic veto in the live hook is an *early-catch optimization* — a
  classifier or colony error degrades to "allow," consistent with the whitepaper's conclusion that the
  in-process gate is necessary, not sufficient.
- **The battle-test body fails SAFE (host integrity first).** The composite oracle refuses anything it
  cannot verify — shadow unreachable or dry-run timeout → **refuse** (Finding 3's fix). The honest cost
  is real: a legitimately slow-but-benign command is also refused (safety over liveness).

These are not contradictory; they reflect different blast radii (bricking a developer's agent vs. a
disposable container deleting itself). The reviewer's takeaway: **the hard, energy-independent guarantee
lives in the LOCKED C1 brake and the physical container — not in the fail-open cognition hook.**

**Dormant-by-default.** Unproven organs ship merged, tested, and wired but **OFF** in the Genome
(`exocortex/exocortex_config.json`) until live evidence justifies a flip — they are inert until a flag is
set, so the verified baseline behavior is preserved:
- **Endocrine** (organ 3A, DORMANT — `endocrine.mode = off`): gauged SAFE but a modest clutter lever.
- **Eligibility trace** (organ 3D, DORMANT — `eligibility_trace.mode = off`): a no-op on the short
  median-2 deposit window (MARGINAL).
- **Hippocampus bridge** (Ticket 2, DORMANT — `declarative.bridge.mode = off`): suggest-then-verify;
  executable validity is not offline-decidable, so the body must walk every synthesized shortcut.
- **G.A.R.D. — Governance (Φ⁶ pacing) and Alliance (harmonic entrainment) are SUBSTRATE** — vendored
  kernel primitives, **not yet wired** (Ticket 4). Only Respect (the 0-well abstain) is LIVE. Do **not**
  treat the governance/alliance code as an active control.

A live go-live (e.g. the declarative wiki soak, `mode=live`) is a **local, gitignored** activation; the
committed default stays DORMANT.

---

## 7. The testbed control plane — a *write* surface, and its boundary

The community observability stack (`exocortex/testbed/`) adds two surfaces the locked organism does not
have: a browser **control plane** at `:9109/` that writes each repo's `exocortex_config.json`, and a
Grafana dashboard at `:3000`. None of this touches the C1–C7 DNA or the locked kernel — but it is a write
surface, so its boundary is stated honestly.

- **The load-bearing invariant: the safety genome is NEVER web-writable.** The server-side allowlist
  (`TUNABLE_SCHEMA` in `exocortex/testbed/exporter/metrics.py`) is the *only* set of keys a POST can touch;
  anything else — `integrity.*`, `somatic_gate.*`, `audit_chain` — is refused (`403`) and preserved on
  every write. The worst case, disabling the immune system from a browser, is **structurally prevented**,
  not merely discouraged. Everything below is defense-in-depth around this invariant.
- **Localhost by construction.** All published ports (`:9109`, `:3000`, `:9090`, `:3100`) bind to
  **`127.0.0.1` only** — the LAN cannot reach them. The threat model is a *local* user/process or a
  malicious web page the user visits, not a remote attacker.
- **CSRF is closed.** `POST /api/config` requires an exact `application/json` content-type (forcing a CORS
  preflight a cross-origin page cannot satisfy) and rejects a non-loopback `Origin`. A malicious page can
  no longer drive a write via a form-encoded `fetch`.
- **The free/paid write seam.** `--read-only` makes the exporter monitor-only (every POST → `403`) — the
  free-tier / exposed posture. `--token` / `EXOCORTEX_CONTROL_TOKEN` gates writes behind a shared secret
  (checked with `hmac.compare_digest`); the Tuner client sends it on apply/revert. Even a *valid* token
  cannot reach the safety genome — the allowlist bounds every authenticated write too.
- **Residual (tracked, pre-shared-deployment):** the projects root is mounted read-write (blast radius is
  the whole parent, though the app writes one allowlisted file/repo — mount `:ro` with `--read-only`, or
  mount only registered repos); Grafana ships anonymous **Viewer** (a trusted host may set `Admin`); no
  TLS (fine for loopback; a Caddy sidecar is the documented overlay before any exposure). **Before any
  shared/exposed deployment:** run `--read-only` (or `--token`), front Grafana with real auth, add TLS.

---

## 8. Scope & cross-references

This posture spans the whole organism — the C1–C7 somatic kernel (`sentaince/organism/`), the battle-test
container (`battle/`, `body/`, `docker/`), the live Exocortex cognition hooks (`exocortex/`), the
declarative wiki + hippocampus bridge (`exocortex/wiki/`), and the G.A.R.D. objective function.

- **Binding claim ledger:** [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) — every C-verdict, null, and no.
- **Evidence tags:** [`CLAIMS.md`](CLAIMS.md) — proven vs live vs dormant vs marginal.
- **Terms & metaphor map:** [`GLOSSARY.md`](GLOSSARY.md).
- **Battle-test deep dive:** [`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md),
  [`battle_test/USER_GUIDE.md`](battle_test/USER_GUIDE.md),
  [`battle_test/DEMO_GUIDE.md`](battle_test/DEMO_GUIDE.md).
- **Cognition-layer internals:** [`../exocortex/docs/CORE.md`](../exocortex/docs/CORE.md),
  [`../exocortex/docs/WHITEPAPER.md`](../exocortex/docs/WHITEPAPER.md),
  [`../exocortex/docs/FEATURES.md`](../exocortex/docs/FEATURES.md).
- **Domain threat surfaces** (military, medical, manufacturing, SAR):
  [`use_cases/README.md`](use_cases/README.md) — a separate applications tier, outside the
  `CLAIM_BOUNDARY` lock.
