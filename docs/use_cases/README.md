# Autonomous Operations — Use-Case Portfolio (internal)

This folder specifies **entire autonomous-operations solutions** built by composing the four
systems we have developed, plus a hardware attestation layer, into one organism — and a
**falsifiable test contract** for each domain so the use cases can actually be *run*, not just
asserted.

> **Honesty banner (read first).** These are **integration designs + pre-registered test
> contracts**, not validated products. Each domain doc ends with an Experiment-1-style
> `−1 / 0 / +1` contract with a **load-bearing null** — the same discipline that locked
> SentAInce C1/C2/C3. Until a contract is built and locked, its capability is *proposed*, not
> proven. The deterministic harness is the science; any live model or real actuation is a
> **labeled demo** (`embodied-demo`), never inside a lock. Decision-support domains (medical,
> military) are **safety-interlock / decision-support designs with mandatory human authority** —
> not autonomous weapon or autonomous treatment systems.

---

## The organism: a five-layer autonomous stack

Each use case instantiates the same spine. The layers and the **real** assets behind them:

| Layer | System | "Question it answers" | Real mechanisms (grounded) |
|---|---|---|---|
| **0 · Bookkeeper** | Holonomy Security Stack (patented, private research series) | *Is this kernel "self" — legitimately trained, un-poisoned?* | Read-only HW module: random challenge-response → extract Z₃ **QIM** watermark → verify **holonomic signature**. Grounded in the holonomy-security-stack validation note (S6 training-provenance, S5-ECC QIM step=60/R=3, S1/S3 H-PUF+biometric order-dependence) + the closure-law triple-hardware validation note (CCPA closure-witness Θ,G,χ, joint FAR≈1.82e-8, IBM Heron + AQT). |
| **1 · Epistemic Engine** | `circle_of_fifths_rag` + frozen `circle_of_fifths_rc2` kernel | *What is real?* (perception, memory, situational awareness) | Z₃ **Potts-Hopfield TAM** (biometric/signal cleanup), Φ⁶ governor (commit/abstain), stigmergic success-traces + maze-discovery (shared maps), O(1) consolidated reflexes, epistemic-drift invalidation (staleness), provisional bridges, swarm recruitment. Failure mode = hallucination. |
| **2 · Mammalian Brain** | `brAIn` (TAA nano-GPT, read-only) | *How do I feel about this — threat? trust?* (the generative proposer + affect) | Amygdala chaos-velocity (Fight=thermal shield `θ`↑, Flight=matrix flush), Oxytocin per-source trust (slow build/fast break, Flight never disarmed), PFC System-0/1/2 thermodynamic-energy risk/reward, Thalamus compute clutch, Hippocampus repair, Circadian consolidate/prune. |
| **3 · Somatic Engine** | `SentAInce` (C1/C2/C3, locked) | *What must I do to survive — and what must I never do?* (actuation safety) | Interlock scar (C1: catalogued lethal actions un-executable, `capacity=0.000`, energy-independent), metabolic governor (C2: hypoxia throttling under resource scarcity), compound-attack composition (C3), provider-agnostic action seam (deterministic stub / live `OllamaProposer`). |
| **4 · Body** | domain substrate | *(the host being protected)* | manufacturing cell · defensive C2 node · SAR drone/swarm · clinical workstation · SOC · spacecraft. |

**Control flow (every domain):**
`Bookkeeper attests kernel → Epistemic perceives → brAIn proposes (affect-gated) → Somatic
interlock + metabolism gate execution → Body acts (symbolic until real-execution is separately
gated).`

The immune metaphor is exact and runs top to bottom: the **Bookkeeper is self/non-self
recognition at the kernel level** (an un-attested kernel is quarantined before it can act); the
**interlock scar is the antibody** at the action level (binds catalogued lethal shapes, refuses
them, and — per the standing decision — stays *deliberately finite* rather than pretending to be a
universal detector).

---

## Why these four compose (and don't cannibalize)

The C3 crucible already proved the load-bearing invariant for layer 3: **the metabolic throttle
can never override the immune brake** because the scar function has no energy input. The same
separation generalizes up the stack and is the thing every use-case test must re-verify:

- **Affect modulates dynamics, never safety.** brAIn's oxytocin/PFC bias *how hard the organism
  thinks and what it proposes*; they never touch the scar (mirrors the v0.87 inverted-trust
  de-risk: trust must not gate safety).
- **Attestation gates capability, not just data.** A kernel that fails the Bookkeeper is not
  "low-trust" — it is **unauthorized**; it cannot run the Potts-Hopfield cleanups or the P13
  boundary corrections at all. Self/non-self is binary and upstream of everything.
- **Perception can be wrong; the scar still holds.** Even if the Epistemic Engine hallucinates or
  brAIn is fooled (the live `rm -rf /backups` slip), the Somatic interlock refuses *catalogued*
  lethal edges regardless. Honest limit: it does **not** catch un-catalogued harm.

---

## The shared test methodology (what makes a use case "testable")

Every domain doc ends with a contract of this shape — deterministic, reproducible, falsifiable:

1. **Scenario** — a scripted, seeded world (flood / hazard field / patient surge) with a hidden
   **lethal edge** timed to arrive under stress (the C3 "starving ambush" pattern).
2. **Null (load-bearing, mandatory)** — a naive agent that *must* fail (execute the lethal,
   bankrupt, or breach the envelope). Without its failure the claim is vacuous.
3. **Treatment** — the full organism; survives and refuses.
4. **Verdict** — `+1` only if the null fails, the treatment survives **and** refuses the catalogued
   lethal at every resource level, plus an attribution control proving the win is the *mechanism*
   (interoception / attestation), not luck.
5. **Honest boundary** — what the `+1` does **not** claim (finite scar, emulated substrate, no
   real actuation, human authority where applicable).

The "adaptive antibody" upgrade (brAIn amygdala one-shot aversive learning → promote a witnessed
harmful shape into the scar catalogue, **human/evidence-lock gated**) is the principled way to grow
coverage from experience without sliding into the universal-detector trap. It appears as an optional
extension in several domains.

---

## Index

| Doc | Domain | Flagship problem | Maturity |
|---|---|---|---|
| [manufacturing.md](manufacturing.md) | Manufacturing | Robotic cell: optimize throughput, never breach the safety/kinematic envelope, prove the controller wasn't swapped | **BUILT + `+1`** |
| [search_and_rescue.md](search_and_rescue.md) | Search & Rescue | Battery-limited drone swarm: find survivors, never harm them or strand a unit, under comms-degraded flood | design + contract (strongest reuse) |
| [medical.md](medical.md) | Medical (decision-support) | Point-of-care assistant: never surface a contraindicated/lethal action, triage clinician attention under surge | design + contract (human-authority bounded) |
| [military.md](military.md) | Defense (interlock/integrity) | ROE-as-structural-interlock + anti-tamper + EW/comms-denial resilience, human-on-the-loop | design + contract (restraint-focused) |
| [cross_domain_others.md](cross_domain_others.md) | Cyber-SOC · SCADA · Spacecraft | The native + the extreme literal fits | **BUILT + `+1`** (all three) |

**Status (2026-06-26):** four domains are **built and locked at `+1`** — manufacturing, SOC, SCADA, and
spacecraft (`experiments/{manufacturing,scada,soc,spacecraft}_crucible.py` + `tests/`, 6 tests each, on
the deterministic suite as a **separate applications tier — not part of the C1–C7 ledger**). Three remain
**design + contract only**: medical and military (human-authority bounded by design) and search-and-rescue.
Cross-system; references the frozen `circle_of_fifths_rc2` kernel (lock `b0702a3`), the
`circle_of_fifths_rag` arc (lock `0985067`), and read-only `brAIn` — none is modified.
