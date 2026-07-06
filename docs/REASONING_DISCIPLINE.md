# SentAInce — Reasoning discipline (agent operating principles)

Operating instructions for any agent working in this project — human or model, in-session or on a PR. It
encodes, as a *deliberative* discipline, the same valence the substrate already records *mechanically*: a
walked `exit 0` deposits **+1** (τ), a witnessed harm writes **−1** (σ), and abstention is **0**. Reasoning in
that vocabulary keeps an agent's judgments legible to the same consequence law and reflection tools that
govern the organism (ADR-001 / ADR-013). Decision record: [ADR-015](ADR.md).

## 1. The triadic decision method

Render every disposition as one of three, and prefer the most conservative the evidence supports:

- **−1 — falsify or park.** The idea failed a control, contradicts a load-bearing null, or has no path to a
  binary-verifiable outcome. Say so plainly and stop spending on it. A −1 *informs*; it never forbids a
  future attempt (ADR-004 / ADR-013).
- **0 — continue diagnostic exploration.** Not yet decidable. This is a **first-class** answer, not a failure
  to comply — "insufficient evidence to render a verdict" is the correct output whenever it is true. Most live
  work sits here.
- **+1 — promote.** Only when the evidence **survives its controls** — a passing gauge, a surviving null, a
  reproduced result. A +1 is earned, never asserted.

## 2. Audit-grade over persuasive

Prefer reasoning a skeptic could reconstruct from named evidence over narrative that reads well. State the
load-bearing null, the control that would falsify the claim, and the boundary the claim must not exceed
([CLAIMS.md](CLAIMS.md)). Persuasiveness is not evidence; a demonstration is not a proof.

## 3. Conceptual alignment vs technical transfer

Always separate **conceptual alignment** (an external idea *rhymes* with ours) from **technical transfer** (a
method actually ports and earns its keep). Most external inputs are the former; labeling the former as the
latter is the most common way a claim inflates.

## 4. Label the kind of claim (type × strength)

State which register a claim lives in — this catches category errors before they compound:

- **proof machinery** — deterministic tests/gauges that *establish* a fact (the kernel lock, C1–C7).
- **emulator machinery** — a stand-in body used to *observe* behavior (the BYO testbed, latent rollouts).
- **product architecture** — what ships and is sold (appliance, tiers, hosted brain).
- **experimental design** — the instrument that *would* decide (a gauge, an A/B, a go-forward snapshot).
- **speculative framing** — a lens or reframe with no evidence yet (design-informants, architecture reframes).

The *type* is orthogonal to the *strength* tag (PROVEN / LOCKED / LIVE / DORMANT / MARGINAL). "Proof
machinery, DORMANT" and "speculative framing" are different cells; conflating them — e.g. treating a
speculative reframe as product architecture — is the error this label exists to prevent.

## Two guardrails (or the ritual backfires)

1. **A rendered verdict is a legible *claim*, never a *consequence*.** Emitting +1 makes a judgment consistent
   and harvestable; it does **not** upgrade self-report to evidence. Only a walked `exit 0` earns τ (ADR-001,
   unchanged). The falsifiable half — a **`−1 if <condition>`** — is the one bridge back to verifiability: it
   can be *resolved* later by a real outcome.
2. **Abstention stays first-class.** The failure mode of any verdict ritual is false precision — slapping a
   valence on things to satisfy the format, which is exactly the persuasive narrative §2 forbids. When the
   evidence isn't there, **0 — "still diagnosing"** — is the disciplined answer.
