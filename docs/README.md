# FreqOS / SentAInce — Documentation

A Sovereign Cognitive Entity that demotes the LLM to a stateless "prefrontal cortex" and moves safety,
memory, and alignment off the model's weights into the deterministic physics of a substrate (Z3 VSA,
Φ⁶ oscillators, thermodynamic pruning, consequence-sourced pheromone). This is the whole-organism
documentation suite.

## Start here
- **[STORY.md](STORY.md)** — SentAInce in human terms: the anatomy (immune system, muscle memory, sleep…),
  the honest numbers, and what the dashboard shows. The gentlest on-ramp.
- **[GLOSSARY.md](GLOSSARY.md)** — the biology↔CS↔code Rosetta with status tags. Read this first for the terms.
- **[CLAIMS.md](CLAIMS.md)** — the evidence ledger: what is PROVEN / LIVE / DORMANT / MARGINAL. **The source
  of truth every other doc is held to** — this project's identity is honest non-overclaiming.
- **[../README.md](../README.md)** — repo overview & quickstart.

## By audience
| You are… | Read |
|---|---|
| **Evaluating it** | [FEATURES.md](FEATURES.md) (each organ + its enable-knob) → [GLOSSARY.md](GLOSSARY.md) → [WHITEPAPER.md](WHITEPAPER.md) |
| **Installing / running it** | [USER_GUIDE.md](USER_GUIDE.md) → [OPERATIONS.md](OPERATIONS.md) (deploy/config/soak/revert) → [DEPLOYMENT.md](DEPLOYMENT.md) (packaging tiers) |
| **Going technical** | [WHITEPAPER.md](WHITEPAPER.md) → the deep-dives: [`../exocortex/docs/CORE.md`](../exocortex/docs/CORE.md), [`../exocortex/MEMORY_GAUGE_DESIGN.md`](../exocortex/MEMORY_GAUGE_DESIGN.md), [`../exocortex/docs/BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md) |
| **Reviewing security** | [SECURITY.md](SECURITY.md) → [CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md) → [`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md) |
| **Understanding the product** | [STORY.md](STORY.md) → [PRODUCT.md](PRODUCT.md) → [`use_cases/README.md`](use_cases/README.md) |
| **Contributing** | [../CONTRIBUTING.md](../CONTRIBUTING.md) → [ADR.md](ADR.md) (the *why* behind the decisions) → [CLAIMS.md](CLAIMS.md) → [GLOSSARY.md](GLOSSARY.md) |

## The suite
| Document | What it is |
|---|---|
| [STORY.md](STORY.md) | SentAInce in human terms — the anatomy, the honest numbers, the two dashboard skins |
| [WHITEPAPER.md](WHITEPAPER.md) | the full system — architecture, the biological stack, consequence-sourcing, the gauge-first method, evidence |
| [USER_GUIDE.md](USER_GUIDE.md) | install, configure, and run the whole stack end to end |
| [FEATURES.md](FEATURES.md) | each organ as a feature: what it does, its status, the knob to enable it |
| [PRODUCT.md](PRODUCT.md) | commercialization strategy: free local dashboard vs paid hosted "managed organism" (tuner consumes vitals, not source); tiers, principles, build order |
| [OPERATIONS.md](OPERATIONS.md) | runbook + the Genome config reference: deploy / soak / monitor / revert |
| [DEPLOYMENT.md](DEPLOYMENT.md) | packaging & deployment tiers (T1 pip → T2 Nuitka → T3 container → T4 Rust/MCP) + the integrity layer |
| [DEPLOY_TO_A_PROJECT.md](DEPLOY_TO_A_PROJECT.md) | runbook: install the organism into any working repo (gates, the 3 artifacts, verify + apoptosis drill; TAO worked example) |
| [SECURITY.md](SECURITY.md) | the somatic posture, threat model, defense-in-depth, the honest boundary |
| [ADR.md](ADR.md) | architecture decision records — the reasoning behind the load-bearing choices |
| [GLOSSARY.md](GLOSSARY.md) | terms & concept map (foundation) |
| [CLAIMS.md](CLAIMS.md) | claims & evidence ledger (foundation, binding) |

## Component deep-dives (authoritative for their subsystem)
- **Exocortex** (the hook control plane + memory/declarative/bridge): [`../exocortex/docs/`](../exocortex/docs/)
  — `CORE`, `WHITEPAPER`, `USERS_GUIDE`, `FEATURES`, `BRIDGE_ORGAN_DESIGN`; engineering log in
  [`../exocortex/MEMORY_GAUGE_DESIGN.md`](../exocortex/MEMORY_GAUGE_DESIGN.md).
- **Battle-test** (real LLM head + real executor in a hardened container): [`battle_test/`](battle_test/)
  — `WHITEPAPER`, `USER_GUIDE`, `DEMO_GUIDE`.
- **Domain applications** (SOC, spacecraft, manufacturing, medical, SAR, military): [`use_cases/`](use_cases/).
- **Evidence & gauge runs**: [`../results/`](../results/) — `attribution_layer2/`, `bridge_gauge_v1/`.
- **Claim boundary** (what the frozen kernel lock does/does not assert): [CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md).

> A note on scope: the top-level `docs/` tells the **whole-organism** story and cross-links the
> component docs under `exocortex/docs/` and `battle_test/`, which remain authoritative for their
> subsystems. Where a count or metric differs, **[CLAIMS.md](CLAIMS.md) is binding** (component docs may
> cite older historical figures).
