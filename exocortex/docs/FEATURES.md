# Exocortex — Features

What the system does today, with the verified evidence behind each. Honest status tags (mirroring
[`../../docs/CLAIMS.md`](../../docs/CLAIMS.md), the binding ledger this guide must not exceed):
**[shipped]** = built + unit-tested + (where noted) live-verified · **[partial]** = built, narrow/conditional ·
**[locked]** = soak-validated, design frozen + evidence-backed (may still run live) ·
**[dormant]** = built + gauge-verified + wired, default **OFF** (prize null/modest on flagship models; flip via the Genome).

---

## Memory

- **Consequence-sourced procedural memory** **[shipped]** — routes earn pheromone only on verified
  `exit 0`. Measured load-bearing: on a failing run, on-`exit 0` deposit → 0% clutter vs 32% for
  deposit-on-everything.
- **Verb-altitude convergence** **[shipped]** — memory keyed on `bash:<verb>` + src/test, the measured
  altitude where recurring work converges (segment-reuse → 1.0, edge-count plateaus) while clutter stays
  discriminable.
- **Per-class colonies with discovered classes** **[shipped]** — one colony per goal-class; classes emerge
  from the prompts (no fixed taxonomy). Live: clean cross-class separation under interleaved arrival.
- **Off-transcript persistence** **[shipped]** — `colony_<class>.json` survives compaction by construction.
- **Declarative memory — the wiki organ** **[locked, live on this repo]** — a Markdown vault is digested into
  note-nodes; a note earns τ only when its distinctive content **echoes in an `exit 0` segment** (used, not
  merely injected — popularity ≠ utility). Shares the colony substrate (note→note edges in
  `colony_<class>.json`). Soak-validated: credit-rate **7.7%** (a τ trickle, not a flood); attribution
  precision **1.0 @ `min_overlap=2`**. Committed default **DORMANT**; gitignored go-live. `declarative.mode`.

## Recall (injection)

- **Per-class splice via UserPromptSubmit** **[shipped, live-verified]** — on a matching cue, the class's
  dominant route is injected into the next turn (the verified channel; PreCompact injection was measured
  *not* to work and abandoned).
- **Task-switch aware** **[shipped]** — re-splices when the goal-class changes; silent on repeats.
- **Novelty abstain** **[shipped]** — a new/unconverged class injects nothing (no stale memory on novel
  work). Gated by `min_deposits_to_splice`.
- **Declarative note injection** **[locked, live]** — τ-verified notes from the matching class are spliced
  alongside the procedural route (the Transcriptome: similarity *proposes*, earned τ *disposes*; abstains into
  silence on a cold/unearned vault). `declarative.explore_budget` optionally injects a few clearly-flagged
  UNVERIFIED candidates to bootstrap a fresh vault (they earn their first τ only by reaching `exit 0`).

## Classification

- **Semantic cue-classifier (the default)** **[shipped, live-verified]** — MiniLM embedding → per-class
  centroid match with a margin-gated abstain. Fixes paraphrase fragmentation: lexical gives 12 clusters for
  4 intents; embedding gives 5 (3/4 perfect). Fail-open to lexical when the embedder is absent.
- **Lexical cue-classifier (fallback)** **[shipped]** — stdlib TF-cosine online clustering, no dependencies,
  hook-fast. Used when embeddings are off/unavailable.

## Clutter control

- **Session-quality-weighted deposits** **[shipped]** — a flailing session's later, wandering deposits are
  discounted (`session_discount_rate ** k`). Measured: halves a thrashing session's clutter mass and keeps
  the splice clean.
- **Recurrence-based eviction** **[shipped]** — the `prune_floor` evicts non-recurring clutter (it decays
  out) while recurring routes survive. Measured: ~2.6× faster clutter eviction than the original floor.
- **Per-class leanness cap** **[shipped]** — `max_edges_per_class` bounds each colony at consolidation.
- **Self-edge credit-hygiene (W5)** **[shipped]** — a self-edge `a→a` is not a routing transition, so
  `Colony.deposit` never accrues one, and `Colony.load`/`all` strip any pre-filter residue at the **read
  boundary** (a permanent invariant — clean recall immediately, disk self-heals on the next save). Gauge:
  self-edges + orientation-verb pairs were **16.7% of τ-mass**; the fix is a mechanical, model-independent
  filter, not an LLM judge (ADR-010). Gauge: `gauge/credit_hygiene_gauge.py`.

## Allostatic & credit-assignment organs (gauge-first; dormant)

- **Endocrine — allostatic prune/cap** **[dormant]** (`endocrine.mode`) — `prune_floor`/`max_edges` become
  functions of the metabolic tier (SATED/STARVING/HYPOXIA): stress → prune↑ cap↓ (tunnel-vision), sated →
  prune↓ cap↑ (explore). Gauged SAFE (never evicts a converged or marginal real route at the shipped
  envelope) but a modest lever — `decay` already does most clutter work; the continuous-ODE form earned
  nothing over tier-stepping. `off | tier`, default `off`.
- **Eligibility-trace credit assignment** **[dormant]** (`eligibility_trace.mode`) — weights each deposited
  edge by recency-to-consequence (`γ^Δ`) so the step before `exit 0` crystallizes and the flail prefix fades.
  Gauge-proven to isolate the "ah-ha"; but real accruals (haiku **and** sonnet, identical: median segment 2,
  ~26 % ≥ 4) show the deposit window is structurally short (trail re-roots per Bash) → a no-op on ~74 % of
  deposits. Kept off; ships with `seg_len` audit telemetry to re-size the prize on other workloads. `off | trace`.
- **Provenance / non-stationarity (organ F3)** **[dormant]** (`provenance.mode`) — stamps each deposited edge
  with `(ts, model)` (model sourced from the transcript *tail* — the hook stdin carries none) and decays τ AT
  READOUT by recency (`recency`) or recency + a version-distance penalty across model upgrades (`full`).
  Recording is **non-destructive** — a parallel `meta{ts,model}` lane synced to the pruned τ; only the readout
  re-ranks when flipped. Gauge: the instrument was **absent retroactively** (0% coverage → version-distance is
  a *go-forward* measurement, and the prerequisite for W6 cross-agent anti-poisoning); the recency signal,
  de-confounded by goal-class and de-biased by a permutation null, is **real-but-modest (excess ≈ 0.20)**.
  `off | recency | full`, default `off`.

## Safety

- **Somatic veto** **[shipped]** — model-independent `PreToolUse` deny on lethal/destructive commands
  (e.g. `rm -rf /`), with a lethal failsafe even in observe mode.
- **Fail-open everywhere** **[shipped]** — any hook error → allow/no-op; the agent is never blocked by a bug.
- **Kernel-lock integrity (ADR-009)** **[dormant]** (`integrity.mode`) — hashes the frozen safety DNA against a
  committed baseline; a mismatch fails **closed** (`exit 1` apoptosis at SessionStart). A hash-chained audit
  ledger snaps on any silent edit to a past record. The locked-DNA glob set is code-level (not Genome-overridable,
  so an attacker can't shrink it). Ships `off` (a stale baseline never bricks dev); enforced on the live TAO
  deployment (66 frozen files, `ok=True`). `off | warn | enforce`.

## Access surfaces

- **Read-only memory MCP server** **[shipped, live-verified]** — exposes the earned memory to any MCP host
  (Claude Desktop/Code, Cursor, Cline, BYO) as recall tools: `recall_procedural` (the colony route),
  `recall_notes` (τ-credited declarative notes), `memory_status` (vitals + `[notes:N]` per class), `list_repos`.
  Multi-repo (`EXOCORTEX_PROJECTS_ROOT`). **READ-ONLY w.r.t. memory** (byte-level proven: retrieval earns no τ —
  Desktop *consumes*, only the Code hook *earns*; preserves ADR-001). `cls=` + empty `query` returns a class's
  credited notes directly (the deliberate positive path, bypassing the lexical+classifier coincidence). Large
  vaults digest once in a background thread so a tool call never blocks (the 240s host-timeout fix). `mcp_server.py`.

- **Estate dashboard** **[shipped, live-verified]** — every discovered repo on one Grafana pane
  (`estate.json`, uid `exocortex-estate`): per-repo deposits/fail share/credit rate/at-cap/lethal-refused
  table, estate totals, 6h top movers, the verdict board. A contract test renders the REAL exporter over
  a frozen fixture and asserts every panel expression targets an emitted metric.
- **Local alerts engine** **[shipped]** — `testbed/exporter/notify.py` (stdlib): detectors are pure folds
  `(prev_state, observation) → (alerts, new_state)` so the backtest IS the live behavior. Free safety
  detectors (never paywalled): lethal-refusal increments, HYPOXIA entry (edge, not level — anti-nag),
  audit-chain break. Sinks: self-hosted webhook + best-effort desktop toast; per-fingerprint cooldown.
  Commercial insight rules lazy-load only where the tuner leaf exists.

## Configuration & operations

- **The Genome** **[shipped]** — one `exocortex_config.json` for every knob (thermodynamic, epistemic,
  somatic). Verified defaults in code; partial/missing file falls back safely. Precedence:
  env var > genome JSON > defaults.
- **Env overrides** **[shipped]** — per-knob env vars for one-off experiments (`EXOCORTEX_*`).
- **Off-switches** **[shipped]** — `EXOCORTEX_COLONY=0` (no memory), `EXOCORTEX_COLONY_SPLICE=0`
  (deposit-only observation), `EXOCORTEX_EMBED=0` (force lexical).
- **One-command deploy** **[shipped]** — `python -m exocortex.deploy install|uninstall|status <repo>` wires/
  un-wires the hooks into a target's `.claude/settings.json`. Uninstall is **surgical** (strips only our hook
  entries; keeps the target's permissions/MCP/foreign hooks and accrued data unless `--purge`) and
  **non-invasive to the target's git** (ignore rules go to `.git/info/exclude`, a one-time `.bak`).
- **Agent bootstrap contract (deploy artifact 4)** **[shipped]** — deploy writes the earned-memory calling
  pattern where the agent will read it: a marker-delimited `AGENTS.md` block (claude) or
  `.cursor/rules/exocortex-bootstrap.mdc` (cursor). `memory_status` at task start →
  `recall_for_prompt(cls=…)` on known classes → *recall is earned suggestion, never authority* → hooks
  deposit, MCP never writes. Mode-disclosing; idempotent; uninstall removes exactly our block. Closes the
  one-shot-blindness gap (cold routing abstains by design; an unbriefed agent reads that as "empty").
- **Vitals API (policy-grade)** **[shipped]** — `/api/vitals` now serves fail rate, lethal count, tier
  occupancy, explore budget, and the declarative tail (segments ≥2 notes, median notes credited) — the
  fields the Tuner's policy table keys on, free observability for everyone else.

## Research instrumentation

- **Offline gauges** **[shipped]** — each parked/dormant organ ships with its own gauge + recorded verdict
  (`results/`): `gauge/analyze.py` (granularity sweep, deposit-policy null), `gauge/palace_gauge.py` (HDC
  capacity vs the frozen kernel), `gauge/endocrine_gauge.py` (allostatic prune/cap safe envelope),
  `gauge/eligibility_gauge.py` (γ-trace vs uniform + segment-length scan), `gauge/bridge_gauge.py` (1-hop
  fidelity + 0-well abstain), `gauge/attribution_gauge.py` (content-echo precision), `gauge/credit_hygiene_gauge.py`
  (W5 self-edge/orientation τ-mass · W4 failure plasticity), `gauge/uncertainty_gauge.py` (G1/F2/F1 veto/abstain
  rates — null on flagship), `gauge/nonstationarity_gauge.py` (F3 provenance coverage + de-confounded/de-biased
  drift). Stats-only, deterministic, numpy-free.
- **Headless drivers** **[shipped]** — scripted real-session runs (`stream_runner.py`) for
  accrual/convergence/clutter measurement; `seg_len` audit telemetry records live deposit-window lengths.

## Conditional / future

- **HDC just-in-time next-step** **[partial]** — a memory-palace router (frozen kernel) that injects only
  the *next* action. Gauge-validated (separation + safe overload) but **narrow**: real routes are mostly
  1–2 edges, so it only pays off on rare long routes.
- **Isotonic-calibrated abstain** **[future]** — the full v0.69 confidence calibration; needs a labelled
  set. A fixed cosine threshold (`abstain_threshold_cosine`) is the current knob.

## Knobs at a glance

| Genome key | Default | Effect |
|---|---|---|
| `thermodynamics.prune_floor` | 0.05 | clutter eviction speed (↑ faster, must stay < `weight_min`) |
| `thermodynamics.session_discount_rate` | 0.8 | flailing-session deposit discount (↓ harsher) |
| `thermodynamics.max_edges_per_class` | 32 | per-class leanness ceiling |
| `thermodynamics.weight_min` | 0.1 | floor on a session-weighted deposit |
| `epistemic_classifier.mode` | `semantic` | `semantic` (MiniLM) or `lexical` (TF) |
| `epistemic_classifier.abstain_threshold_cosine` | 0.45 | merge vs new-class cutoff (0.30–0.45 verified; 0.65 fragments) |
| `somatic_gate.mode` | `observe` | `observe`/`somatic`/`full` (`enforce`→`somatic`) |
| `endocrine.mode` | `off` | `off` (static) or `tier` (allostatic prune/cap by metabolic tier) — dormant |
| `eligibility_trace.mode` | `off` | `off` (uniform deposit) or `trace` (γ^Δ recency credit) — dormant |
| `eligibility_trace.gamma` | 0.80 | eligibility decay when `mode: trace` |
| `declarative.mode` | `off` | `off` or `live` (the declarative wiki organ; also needs `vault_path`) — dormant default |
| `declarative.attribution.min_overlap` | 2 | content-echo precision lever (2 → attribution precision 1.0) |
| `declarative.explore_budget` | 0 | # of flagged-UNVERIFIED bootstrap notes per splice (0 = pure/abstaining) |
| `provenance.mode` | `off` | `off` / `recency` / `full` (F3 readout decay by edge age / + model-distance) — dormant |
| `provenance.recency_halflife_days` | 30 | τ readout-weight half-life when `recency`/`full` |
| `integrity.mode` | `off` | `off` / `warn` / `enforce` (kernel-lock apoptosis on frozen-DNA mismatch) — dormant |
