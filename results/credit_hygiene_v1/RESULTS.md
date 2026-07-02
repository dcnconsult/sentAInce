# Credit-Hygiene Gauge v1 — W5 credit-pollution · W4 failure-ledger

**Gauge:** `exocortex/gauge/credit_hygiene_gauge.py` (stdlib, read-only, fail-open). **Run:**
`python -m exocortex.gauge.credit_hygiene_gauge --state-dir <repo>/.claude/exocortex [--json]`.
**Discipline:** gauge-first (ADR-002) — measure two of the highest-claimed hook-integration ideas (the
2026-06-30 Desktop self-audit) on the EXISTING audit + colony, before building any hook or organ.

**Data:** live SentAInce state (549 colony τ-edges across 49 classes; 377 Bash consequences, 33 failures).

---

## W5 — credit pollution → **SIGNAL = True (real but MODEST); fix is MECHANICAL, not a judge**

`exit 0` blesses orientation noise. A route is a *transition*; a self-edge `a→a` carries no routing
information, and orientation-verb pairs (`cd/ls/pwd/cat/echo`) are pure navigation.

| metric | value |
|---|---|
| τ-mass that is routing-noise (self + orientation pairs) | **16.7%** (16.6% of edges) |
| self-edges | 89 edges / **τ 24.68** (e.g. `Edit:other→Edit:other` 2.62, `Read:other→Read:other` 1.63) |
| orientation pairs (cd/ls/pwd/cat/echo) | 33 edges / τ 5.04 |
| most-polluted classes | `md-doc#19` 47%, `wiki_credit_rate-add#10` 43%, `optimization-improvement#34` 39% |

**Verdict:** a **mechanical deposit-filter** (drop `a→a` self-edges, down-weight orientation verbs) reclaims
~17% of τ-mass **model-independently** — preferred over an LLM judge in the credit loop, which would break
the frozen, model-independent disposer (ADR-001/010) and cost an LLM call per turn. **Self-edges are the bulk
(τ 24.68 of ~29.7 reclaimable)** → dropping self-edges is the single highest-value move. Pair with the
**dormant eligibility trace (organ 3D)**, which already γ-discounts the orientation prefix. Modest (17%), but
free and on-thesis. **Recommendation: ship the self-edge/orientation filter; flip the eligibility trace.**

## W4 — failure ledger → **SIGNAL = True on recurrence, but ADR-004 EMPIRICALLY VINDICATED → decaying-only**

| metric | value |
|---|---|
| failure rate | 33/377 = **8.75%** |
| distinct failed command-keys | 12 |
| recurrence (same verb-altitude approach fails >1×) | **0.571** |
| recurrence (exact command fails >1×) | 0.417 |
| **plasticity_rate (failed keys that ALSO succeed later)** | **0.667** |
| max consecutive-fail streak | 2 |

**The load-bearing finding:** failures *do* recur (57% at verb altitude) — so a "this failed before" signal
has data to work with — **BUT 2 of every 3 failed approaches later succeed.** A permanent **σ-scar would
freeze a re-learnable route in 67% of cases** — which is exactly the plasticity ADR-004 ("no immortal σ on a
plain `exit 1`") was written to protect. **The gauge confirms ADR-004 empirically.** So the only safe form of
W4 is a **decaying τ⁻** (evaporates), never a scar — and even that is **prize-bounded by the high plasticity**
(most failures are transient and self-resolve). A soft, in-session version already exists (the interoceptive
strategy-lock). **Recommendation: build only as a decaying τ⁻, ship dormant, expect modest payoff; re-run on
adversarial/BYO traffic (F2 was gauged null on flagship — same regime).**

---

## Bottom line

Both ideas have *signal* on real data, both are *modest* on single-dev flagship traffic, and both have a
**fix the project's laws already point at**: W5 → a mechanical filter (not a judge), W4 → a decaying τ⁻ (not a
scar). Neither needs a hook to build or to gauge — the data was already in the audit + colony. The biggest,
cheapest win is the **self-edge deposit-filter** (reclaims the bulk of the 17%, one-line change, model-
independent). The deeper W-roadmap residuals (non-stationarity → F3; false-success amplification, the only
real ceiling) are untouched by either and remain the honest limits. See
[[exocortex-hook-integration-roadmap]] and `docs/ENHANCEMENTS.md`.
