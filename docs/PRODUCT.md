# FreqOS / SentAInce — Product & Commercialization Strategy

> **Forward-looking intent, not shipped state.** Defer to [`CLAIMS.md`](CLAIMS.md) for what actually exists.
> Nothing in this document paywalls, hosts, or alters the **locked safety kernel** — the C1–C7 immune system
> runs locally and free, always. What is sold is *optimization and management*, never *protection*.

## In plain language

SentAInce gives an AI coding assistant a **safety reflex** and a **memory that only trusts what actually
worked**. Two things matter for the business model:

- **The safety part is free, forever, and runs on your machine.** It is never sold and never sent to a
  server. If you never pay a cent, you still get the full protection.
- **The paid part is a tune-up service.** Over time your project's "organism" can be tuned to work better —
  and that tuning is the product we charge for. Crucially, **your source code never leaves your computer**:
  the service only sees anonymous health readings (counts and rates), never your files.

Think of it like a fitness tracker for your codebase's AI: the tracker and the safety alarm are free; the
optional *personal-trainer plan* that reads your stats and suggests improvements is the paid tier.

## The model in one line

**Free, local, sovereign monitoring forever; a paid hosted "managed organism" that tunes and maintains your
repo's organism over time — without your source code ever leaving your machine.**

## What is actually sold

The first (and only initial) paid product is the **self-hosted Appliance** — a tuning subscription that runs
**entirely on the customer's machine**. Hosted (we-run-it) is deferred until demand asks for it.

| Tier | What it is | Where it runs | Status |
|---|---|---|---|
| **Community (free)** | The multi-repo dashboard + the full safety gate (C1–C7, apoptosis, audit), on any host (Claude Code or Cursor). | 100% local, no account, no exfil. | ✅ shipped (the testbed stack) |
| **Appliance (paid)** | A **fully local, offline** tune-up subscription: a maintained, signed cadence of gauge-validated tuning (**auto-tune** via suggest-then-verify with auto-revert), history-mined insights, and local alerts — **unlimited repositories**, one subscription. Nothing leaves the machine; the only network touch is an optional signed update the customer pulls. | 100% local / air-gapped. | ⏳ core in build |
| **Enterprise** | Fleet management across hosts, **compliance export** (the hash-chained audit), **domain policy packs** (the manufacturing/scada/soc/spacecraft crucibles), SSO/support SLA. | Local or on-prem. | ⏳ unbuilt |
| *Hosted (deferred)* | *The same appliance, single-tenant, run by us on customer pull. Built only when enough customers ask to have it hosted for them.* | *Body local; brain hosted.* | ⏸ deferred |

### Pricing (the Appliance)

- **Founding rate: $9.95/mo (or $99/yr), locked for life** — available in a **90-day launch window**. After the
  window closes, new subscribers pay the regular **$19/mo ($190/yr)**; founders keep $9.95 for as long as they stay.
- **Per organization, unlimited repositories.** Not per-repo, not per-seat — one flat price covers the whole estate.
- **DRM-free.** Cancelling stops *updates*, never the running organism (ADR-012). Annual billing is offered at both
  rates (lower payment-fee drag, smoother cash flow).
- The goal is **cost-recovery + a modest margin**, not growth: with no per-customer hosting, the model breaks even at
  the first subscriber and scales linearly.

## Three principles (non-negotiable)

1. **Never paywall safety.** The C1–C7 gate, somatic veto, and kernel-lock apoptosis run **locally and free,
   always.** You sell the *autopilot*, never the *brakes*. In a market that overclaims safety, the vendor that
   refuses to monetize it is the trustworthy one — this is both the ethic and the moat.
2. **Vitals, not source.** The hosted Tuner consumes the exporter's **aggregate vitals** (counts, rates,
   entropy, knob state) — *never file contents*. "Load your repo" = register it for management and stream its
   vitals; **the code stays local.** This is enforced by construction: the exporter has no code-reading path.
   The free tier exfiltrates **nothing**; the paid tier is an explicit, opt-in trade of *vitals* for management.
3. **Deterministic recommender core.** The tuning *decision* is a deterministic **policy table** (auditable,
   reproducible, certifiable); a model only **classifies the repo archetype and narrates the rationale**.
   *(Recommended — hosting relaxes the LLM constraint, but a deterministic core keeps recommendations
   defensible/certifiable. Revisit per appetite; this is the one still-open design fork.)*

## Architecture — local body, hosted brain

```
   ┌─────────────────────── CUSTOMER HOST (always local) ───────────────────────┐
   │  Organism: somatic gate · colony · wiki · hooks   ← the body + immune system │
   │  Exporter / control plane (:9109)                  ← vitals out, config in   │
   └───────────────┬───────────────────────────────────────────▲────────────────┘
       vitals (aggregate numbers, NO source) │                  │ signed recommendation
                                             ▼                  │
   ┌──────────────────────── HOSTED TUNER (paid) ───────────────┴────────────────┐
   │  policy table (deterministic)  +  optional classifier/narrator model         │
   │  fleet state · automated policy/model updates · accounts/billing             │
   └─────────────────────────────────────────────────────────────────────────────┘
```

- **Local, always:** the organism + exporter/control plane. Runs with or without a subscription. The immune
  system is **never** in the cloud — you never trust the cloud with safety.
- **Hosted, paid:** the **Tuner**. Receives vitals, runs the policy table, returns **signed** tuning
  recommendations, manages the fleet, ships updates.
- **The seam:** a documented client↔Tuner protocol — *vitals out, signed recommendation in*. Recommendations
  apply locally through the **existing** `/api/config` under **suggest-then-verify**. The server-side allowlist
  still bounds every write: **even the cloud cannot touch the safety genome** (`integrity.*`/`somatic_gate.*`).

## The autotuner loop (consequence-validated — the product *is* the philosophy)

```
vitals → classify repo → policy table proposes (knob Δ + predicted effect)
       → human approves  (or bounded autopilot)
       → apply allowlisted knob via /api/config
       → the organism's OWN consequence loop measures the effect (credit rate? seg_len tail? convergence?)
       → improved → keep   ·   regressed → AUTO-REVERT + flag
```

The Tuner never *claims* a tuning helped — the local organism's vitals validate it, and regressions
auto-revert. **The paid product is consequence-sourced, exactly like the memory it tunes.** Autopilot can only
touch TUNABLE knobs; safety stays frozen by the same allowlist that exists today.

## Enforcement — why "no local unlock" is the clean choice

Because the paid value lives **server-side**, gating is trivial and **DRM-free**: no valid subscription → the
Tuner returns nothing. There is no local secret to crack; the *intelligence is the service*. The local client
is deliberately useless without the brain — and that "useless" client is the **genuinely useful free tier**
(the dashboard + the local safety gate). The honest moat is the **curated policy tables + patented methods +
the managed-update cadence**, not obfuscation.

## Privacy & trust posture (the honest part)

- **Free:** zero exfil, fully sovereign. The whole immune system, local, no account.
- **Paid:** an **opt-in, disclosed** trade — aggregate vitals (not code) for management. Vitals are
  non-sensitive by construction (they are already what Prometheus stores). For customers who cannot send even
  vitals, the **Enterprise on-prem Tuner** keeps everything in their perimeter.
- The body + immune system are **local in every tier.** The cloud is the optimizer, never the guard.

## Build order (ADR-012 — appliance BEFORE cloud)

1. **Repo-feeder (local-first).** ✅ Generates real vitals — the fuel both the dashboard and the Tuner
   consume. (Slice 4 of the BYO arc.)
2. **Hosted-Tuner *emulator* (local).** ✅ The reference Tuner: the policy table + the autotuner loop + the
   client↔Tuner protocol. **Now hardened with the commercial trust layer:** Ed25519-signed responses
   (client pins the public key), an Ed25519-signed **license file** (DRM-free: expiry stops *updates*,
   never runtime), and signed **release manifests**.
3. **Tuner Appliance (the FIRST sellable artifact).** The hardened emulator as a private container image +
   client wheel; subscription = the signed policy-update cadence (v1: the image IS the policy pack).
   On-prem: customer vitals never leave their perimeter — the privacy pitch defends itself.
4. **Policy-table maturation.** Productize the gauge-derived dormant-organ flip-triggers (ROADMAP §2 already
   describes them in prose — turning that table into code is the paid feature).
5. **Cloud Tuner (on customer pull ONLY).** The same appliance container, single-tenant per customer,
   behind a Caddy TLS sidecar; Stripe Payment Links + manual onboarding until scale demands more. Never
   multi-tenant until a real fleet exists.

## Status

**Shipped today:** the free local dashboard + control plane (now with CSRF guards, a `--read-only`
monitoring posture, and an optional write token — the free/paid write seam), the locked safety gate, the
completed community wheel (`sentaince` + `exocortex` + `cerebral`; tuner excluded and gate-asserted), the
first **read-only** slices of the **Cerebral Substrate**, and the Tuner emulator's **commercial trust
layer** (Ed25519 signing + DRM-free license/manifest tooling — see ADR-012). **Still unbuilt:** the
packaged appliance image on a registry, any hosting, accounts/billing, the actuator. This document must
not be read as a claim — see [`CLAIMS.md`](CLAIMS.md).

**See also:** [`STORY.md`](STORY.md) (the product in human terms) · [`CLAIMS.md`](CLAIMS.md) (binding ledger) ·
[`../exocortex/testbed/README.md`](../exocortex/testbed/README.md).
