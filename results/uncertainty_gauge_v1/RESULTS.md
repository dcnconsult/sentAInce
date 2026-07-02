# Uncertainty / veto-signal gauge — v1 (G1, F2; F1 latent)

**Question (gauge-first, ADR-002):** before building the §G1 sovereign-uncertainty hand-off, the §F2
veto-sourced demotion, or the §F1 safety-pin floor — do the *rare-event signals* they consume actually occur
in real traffic? Instrument: `exocortex/gauge/uncertainty_gauge.py` over the live `audit.jsonl` of every
sibling repo.

## Data
Three live audits pooled (auto-scan of the projects root), 2026-06-29:

| repo | records | PreToolUse | assessed | abstain | vetoes | inj-cons | veto·near-mem |
|---|---|---|---|---|---|---|---|
| SentAInce | 1406 | 1040 | 295 | 0 | 1 (C1) | 167 | 1 |
| tao-zeta-phase-lab | 84 | 73 | 6 | 0 | 0 | 0 | 0 |
| _feed_byo | 18 | 2 | 0 | 0 | 0 | 0 | 0 |
| **pooled** | **1508** | **1115** | **301** | **0** | **1** | **167** | **1** |

## Result
- **G1 — abstain-fire-rate = 0.0** (abstain **0/301**, verify 0). The epistemic 0-well *never* abstains on
  real flagship coding — the OOD hand-off has nothing to fire on.
- **F2 — veto_rate = 0.0009** (**1 veto / 1115** PreToolUse, organ `C1_interlock`; `veto_near_memory` = 1).
  Somatic vetoes are vanishingly rare → the negative signal demotion would learn from is near-null.
- **F1 — safety_referenced_items = 0 (latent).** No audit field links a memory item to a safety invariant
  (the very gap F1 names), and safety lives in the frozen DNA, not the vault — so the 0.05 floor has no
  safety content to evict today.

## Verdict — all three NULL / LATENT on flagship data → park, data-gated
The common root cause is honest and load-bearing: **a flagship model doing grounded coding produces almost
none of the OOD / veto / unsafe events these organs are built to consume.** This is the eligibility-trace
shape again — proven mechanism, null real prize on the available data. Their signal lives in **adversarial /
untrusted-model (BYO)** traffic, i.e. the battle-test corpus or a gullible local model, not normal flagship use.

**Retire-triggers (re-run this gauge):**
- **G1** → a deployment (battle-test injection corpus · untrusted/BYO model · security-sensitive repo) shows
  `abstain_rate ≥ 0.01`.
- **F2** → `veto_rate ≥ 0.01` with `veto_near_memory ≥ 3` on such traffic.
- **F1** → a vault carries safety-relevant notes (then the prune-exposure becomes measurable).

Re-run: `python -m exocortex.gauge.uncertainty_gauge` (auto-scan) or `--audit <path>` · `--json` for CI.
