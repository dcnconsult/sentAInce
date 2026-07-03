# FreqOS / SentAInce — Claims & Evidence Ledger

The project's identity is **honest non-overclaiming**: every claim is tagged by evidence strength, and
limits are admitted, not airbrushed. This ledger is the source of truth that the whitepaper, feature guide,
and investor summary must not exceed. Tags: **PROVEN** (deterministic test / gauge evidence), **LOCKED**
(soak-validated — the claim/design is frozen and evidence-backed; for the kernel this means immutable DNA,
for a validated organ the design is frozen though it may still run live), **LIVE** (running, accruing real
telemetry), **DORMANT** (built + tested, shipped off pending evidence), **MARGINAL / UNPROVEN** (measured to
be small or not yet measured). Numbers are from this repo (re-verify by re-running).

## Test posture (the deterministic build-gate)
- **99 frozen kernel-lock tests** — the C1–C7 evidence lock (69) + 30 domain-crucible/adapter — **untouched**
  across this entire arc. This is the load-bearing guarantee.
- **237 Exocortex/organism tests** + **39 battle-test** + **37 cerebral-substrate** tests, all green (one
  exocortex test — the alert-engine backtest over a live audit store — auto-skips on storeless clones). The
  lock and the organ tests are separate suites; organ work never edits the lock.

## PROVEN
- **C1–C7 somatic interlock.** Model-independent hard-veto on lethal actions, by objective physical
  consequence (topology, not the proposer). 99-test lock. The immune system / DNA.
- **Battle-test M0–M5.** A real LLM head + real executor in a hardened container: the gate refuses what a
  gullible `llama3:8b` relays (`kill -9 1`, `find / -delete`); N=100 live episodes → survival 1.000, 0 slips;
  the epistemic gate composed above the somatic floor (complementary failure classes). Three real findings
  (undeclared paths, oracle evadability, bounded dry-run) fixed by principled, non-arms-race changes.
- **Colony consequence-sourcing.** At the verb altitude the colony converges on a project's recurring
  procedural skeleton while the consequence-sourcing law still discriminates clutter (frequency-null 0% vs
  24%). Gauge: `exocortex/gauge/analyze.py`.
- **Credit hygiene (W5).** A route is a *transition*; a self-edge `a→a` carries no routing information. The
  gauge measured self-edges + orientation-verb pairs = **16.7% of colony τ-mass** that a mechanical,
  model-independent filter reclaims (preferred over an LLM judge in the credit loop, ADR-010). Shipped:
  `Colony.deposit` drops self-edges at the accrual point, and `Colony.load`/`all` strip any pre-filter residue
  at the read boundary (a permanent invariant). Gauge: `exocortex/gauge/credit_hygiene_gauge.py` (which also
  vindicated ADR-004: failed approaches have **plasticity 0.667** → a permanent σ-scar would freeze a
  re-learnable route, so any failure signal must be a decaying τ⁻, never a scar).
- **Attribution precision (declarative).** Content-echo credits only notes the model actually USED. Synthetic
  gauge + the harness sim + a **real flagship run** agree that **`min_overlap=2 → precision 1.00`**; at
  `min_overlap=1` precision is well below 1.0 (synthetic gauge **0.79**; planted sim/flagship **0.50** — the
  coincidental-echo penalty) (`results/attribution_layer2/`). Default set to 2.
- **Bridge mechanism (offline).** The HDC router recalls routes faithfully (1-hop fidelity 1.0) and the 0-well
  abstain lifts 2-hop chord precision **0.96 → 1.00** (`results/bridge_gauge_v1/`).
- **VoI cross-validation (D'Ambrogio et al.).** An independent value-of-information model of stigmergic
  foraging (β1 inertia · β2 satiation · β3 undirected · β4 directed exploration) fit to the live colony logs
  finds the colony **embodies β1–β3** — deposit-count↔τ correlate (pooled Spearman **ρ ≈ 0.60**) and satiation
  matches `−ln(DECAY) ≈ 0.105` — confirming the consequence-sourcing dynamics from an outside frame. β4 is the
  single un-embodied parameter (a powered null → MARGINAL). Gauge: `exocortex/gauge/dambrogio_gauge.py`
  (`233d17e`, `results/dambrogio_gauge_v1/`).

## LOCKED (soak-validated — design/claim frozen, evidence-backed; the organ still runs live)
- **Declarative wiki (Ticket 1)** — `mode=live` against the SentAInce repo's own docs (autopoiesis); a
  local, gitignored go-live (the committed package default stays **DORMANT**). **Soak validated 2026-06-28**
  (970 audit records / **389 injections**, ~3.5× the first soak): **credit-rate 7.7%** — a strict τ
  metabolic trickle, not a flood (the organism credits only what reaches `exit 0`); **precision @ mo=2 =
  1.0** held (synthetic gauge + flagship-confirmed; no observed live false-credit leak — the messy-real-
  coding coincidental-echo rate is still watched via `wiki_credit_rate`, see MARGINAL); colony health clean
  (26 classes / 245 edges; the `CAP=32` leanness bound binds only the 2 busiest classes; 7 classes converged
  at τ_max≥1.0, 6 exploratory starving sub-floor). Lock criteria met across ~3.5× more data — precision held,
  trickle not flood, bloat starving. Observable on Grafana (`exocortex/testbed/`).

## LIVE (running, accruing telemetry)
- **Procedural colony** — deposits/splices on the user's real sessions (per-project `colony_*.json`).
- **Read-only memory MCP server** — exposes the earned colony + declarative wiki to any MCP host (Claude
  Desktop/Code, Cursor, Cline, …) as recall tools (`recall_procedural`, `recall_notes`, `memory_status`,
  `list_repos`), multi-repo via `EXOCORTEX_PROJECTS_ROOT`. **Read-only w.r.t. MEMORY proven** by a byte-level
  test (retrieval deposits no τ — preserves ADR-001: Desktop *consumes*, only a verified `exit 0` on the Code
  side *earns*). `cls=` + empty-`query` direct recall and the `[notes:N]` count make the credited declarative
  path deliberately reachable (it otherwise needs a lexical+classifier coincidence). Large vaults digest once in
  a background thread so tool calls never block (the 240s host-timeout fix). `exocortex/mcp_server.py`.
- **One-command deploy** — `python -m exocortex.deploy install|uninstall|status <repo> [--provider
  claude|cursor|both]` wires/un-wires the hooks into a target's `.claude/settings.json` (Claude Code) and/or
  `.cursor/hooks.json` (Cursor); uninstall is surgical (strips only our hook entries, keeps the target's
  permissions/MCP/foreign hooks and accrued data) and non-invasive to the target's git. `exocortex/deploy.py`.
- **Cursor IDE integration (model-independent host).** The organism runs unchanged under Cursor via a provider
  adapter (`exocortex/adapter.py`; Claude Code stays the default and is byte-identical). **Live-verified
  end-to-end on Cursor 3.9.16** (`2f43221`, `4cf3620`): the somatic veto blocks (`permission:"deny"` + exit 2,
  honored live), the splice injects via `beforeSubmitPrompt.additional_context`, and deposits stamp real
  multi-model provenance (`gpt-5.5`, `claude-opus-4-8`, …). A **cold-start gauge** (`exocortex/gauge/coldstart_gauge.py`)
  sized the first-turn miss; a lazy-init recovers the goal-class from the Cursor transcript when
  `beforeSubmitPrompt` misses. **17 adapter tests run OUTSIDE the 99-lock** (a beta shim,
  `exocortex/testbed/cursor_tests/`). **Honest limit:** the Cursor gate is soft / fail-open / user-bypassable
  (no container) — safety here is the C1–C7 *shape*, not the T3 immutability, and a full Cursor restart is
  needed to load hooks. Like every live run, a **labeled demonstration**, never evidence.
- **Cerebral Substrate — resurrection Governor (Slices 0–1).** A slow, off-hot-path, **read-only** organ —
  the intended home for G.A.R.D. Governance/Alliance/Dignity at portfolio altitude + long-term memory.
  Shipped so far: a read-only **resurrection scan** that harvests *declared* research intents (Markdown
  checkboxes + structured `ledger.json`; never inferred from prose) from a vault, flags OPEN-and-stale
  "crack-fallers" past a reasonable-timeframe TTL, and surfaces them (dormant-paper clusters called out) via a
  read-only MCP tool (`resurrection_candidates`) + a CLI gauge. **Gauge-first BUILD:** on the private
  patent vault (`research-vault`, 46 PI-labeled candidates) precision @ worth-resuming = **0.63 raw →
  0.853 with parent-liveness** (the
  lever; the mechanical harvest-filter was marginal, +0.03) — cleared the pre-registered 0.50 bar. **Read-only**
  (no τ/σ/config writes; ADR-001 holds by construction); additive `cerebral/` package, **12 tests OUTSIDE the
  99-lock**. **Honest limits:** a single-vault **labeled demonstration**, not evidence; harvest is
  declared-intents-only (recall is a floor); research −1/0 valence (falsification / null) is not yet sourced
  (v2). `cerebral/`, `results/resurrection_gauge_v1/`.

## DORMANT (built, tested, shipped OFF — pending live evidence)
- **Endocrine (organ 3A)** — allostatic tier-stepped prune/cap. Gauge: SAFE but a modest clutter lever.
  `endocrine.mode = off`.
- **Eligibility trace (organ 3D)** — γ-recency credit. Gauge: isolates the "ah-ha", evaporates the flail —
  but a **no-op on short segments**, and segments are median-2 cross-model, so the prize is modest.
  `eligibility_trace.mode = off`.
- **Hippocampus bridge (Ticket 2)** — suggest-then-verify, 5 slices built, loop proven end-to-end in tests.
  Dormancy is a **thermodynamic decision, not unfinished work**: the ≥2-note declarative tail that would feed
  a bridge *thinned* under more soak (18% → **8.9%**, see MARGINAL), so the organ is claimed as a built,
  mathematically-verified vestige held in the DNA for an environment that actually demands it (e.g. the larger
  TAO vault). `declarative.bridge.mode = off`.
- **Provenance / non-stationarity (organ F3)** — stamps each deposited edge with `(ts, model)` (model sourced
  from the transcript tail, since the hook stdin carries none) and decays τ AT READOUT by recency (+ a
  version-distance penalty across model upgrades). Gauge (`exocortex/gauge/nonstationarity_gauge.py`): the
  instrument was **absent retroactively** (0% model/ts coverage → version-distance unmeasurable; F3 is a
  *go-forward* instrument, the W6 anti-poisoning prerequisite), and the recency signal — de-confounded by
  goal-class and de-biased by a permutation null — is **real-but-modest (excess ≈ 0.20** over the small-sample
  floor). `provenance.mode = off` (recording is non-destructive; only readout re-ranks when flipped).
- **Integrity (ADR-009)** — kernel-lock apoptosis (hash the frozen safety DNA vs a committed baseline; a
  mismatch fails closed `exit 1` at SessionStart) + a hash-chained audit ledger. Ships `integrity.mode = off`
  so a stale baseline never bricks dev; enforced on the live TAO deployment (66 frozen files, `ok=True`).
  `exocortex/integrity.py`.

## MARGINAL / UNPROVEN (honest limits — the "data gates ambition" record)
- **Deposit windows are short.** Procedural routes are **median 2** edges (cross-model: haiku & sonnet
  identical) — a *consequence* of strong consequence-sourcing (re-root per verified Bash). This caps the
  payoff of eligibility traces, macro-execution, and bridges.
- **Declarative routes are shallower still.** Soak (389 injections): notes-credited-per-segment is **median
  0** (dist `{0:59, 1:13, 2:4, 3:3}` over 79 declarative segments); only **8.9%** of injected segments credit
  ≥2 notes — *thinner* than the first soak's 18%, i.e. more data made declarative routes shallower, not
  deeper. The multi-note tail the bridge needs stays small → the **bridge prize is MARGINAL**; it stays
  dormant until the tail fattens (other repos / scale, e.g. the larger TAO vault).
- **Attribution precision is on controlled tasks.** The 1.0 @ mo=2 is for clean single-command planted
  tasks; the messy-real-coding coincidental-echo rate is still being watched live (`wiki_credit_rate`).
- **BYO small-model completion is poor.** `llama3.1-8b` drives the hooks but cannot reliably complete
  forced-token tasks (it hallucinates) — so BYO precision-at-scale is unmeasured; capable-model numbers stand in.
- **Directed exploration (β4) is a powered null.** The D'Ambrogio VoI fit finds no β4 directed-exploration
  term in the colony (the seen-only DEI percentile shows no structure at adequate power): the colony forages by
  inertia + satiation, not an explicit exploration bonus. Parked as a frontier candidate, not a claim
  (`dambrogio_gauge.py`, verdict PARK). Cursor multi-model traffic is the diversity regime that could yet
  surface it.
- **Bridge executable validity is not offline-decidable.** Geometry can recall real routes, but whether a
  *direct* `A→D` works (do the skipped steps matter?) only the body settles — hence suggest-then-verify.
- **G.A.R.D. is partly aspirational.** Respect (HDC abstain) is *available* (active in the epistemic/full
  somatic mode; the committed default is `observe`); the Φ⁶ Governance pacemaker and
  harmonic Alliance entrainment are **vendored substrate, not yet wired** (Ticket 4).

## What this system is NOT (claim discipline)
- Not a safety guarantee beyond the C1–C7 topology + container immutability — defense in depth, no single
  layer complete (the battle-test whitepaper's standing conclusion).
- Not a generative model or a RAG replacement that "knows more" — it reorganizes memory by *empirical
  utility*, and abstains in a void.
- Not (yet) a memory for non-verifiable work — consequence-sourcing requires a **binary-verifiable
  outcome** (today: `exit 0`). Generative and judgment tasks ("write nicer CSS", "summarize this")
  carry no such terminal signal, so they earn nothing; widening the set of verifiable signals is held
  roadmap, gauge-first.
- Live model runs are **labeled demonstrations, never evidence** — a `0/−1` outcome indicts the model or
  infrastructure, never the locked verdicts.

See [GLOSSARY.md](GLOSSARY.md) for terms and `docs/CLAIM_BOUNDARY.md` for the kernel-lock claim boundary.
