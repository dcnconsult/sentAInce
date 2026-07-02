# Credit-Funnel + Class-Consolidation Gauges — v1 results (the tuning/hardening arc)

**Gauges:** `exocortex/gauge/credit_funnel_gauge.py` · `exocortex/gauge/consolidation_gauge.py` ·
**Date:** 2026-07-01 · read-only, deterministic, ADR-002. **Ticket:** the Desktop longitudinal audit's
ranked findings #2 (research-repo declarative −1) and #3 (fragmentation), both "math-and-storage."

## Verdict 1 — the research-repo declarative −1 is a **STAGE-1 COLD-START LOCK**, not a crediting failure

The funnel gauge separates the audit's three inseparable-from-outside candidate causes. On the research
repo (private crucible): **0/64 Bash exit-0 consequences ever had a spliced note** — the funnel dies at
injection, before echo or credit can even be tested. The three-way diagnosis:

| Candidate cause | Verdict | Evidence |
|---|---|---|
| ingest coverage too narrow | **exonerated** | 59,573 nodes warmed; cache present |
| notes structurally uncreditable (prose-only) | **exonerated as blocker** | **40.1%** echo-creditable at min_overlap=2 (58% at 1) — the vault *could* credit |
| credited chains not traversing vault nodes | **refined → COLD-START LOCK** | with zero prior credits, structural spreading-activation and muscle-memory are bootstrap-dead; the **dense lift is statically dormant** (see below); the lexical reflex — the only live cold layer — never hit in 39 prompts |

**Control:** SentAInce reads a healthy funnel end-to-end (416/523 injected → 113 echo → 35/68 classes
note-anchored, vault 77.7% creditable) — the instrument reads a working pipeline correctly.

**Code-level finding (dormant-by-design, found by the gauge):** `hook.py` calls
`propose(graph, prompt, active_context)` **without `prompt_embedding`** — the proposer's dense/HDC layer
(`propose._dense`) has been statically dormant everywhere since it was built. On a conversational-prompt
research vault it is precisely the missing cold-start layer. Wiring it = a one-argument pass-through **plus**
a phasor bank build, and only pays where embed-mode runs — an organism change, so it gets its own gauge
before any wiring (BUILD-candidate, not built).

## Verdict 2 — class-merge pass: **PARK** (a load-bearing null; the organ is killed before being built)

On the live 68-class colony fleet, in the classifier's own similarity space (raw-TF cosine — the same
metric that assigns cues), the merge sweep finds **almost nothing to merge**: 2 pairs at cos≥0.50, zero at
≥0.60 — and one of the two merges joins already-converged classes and *shallows* the route (depth −2, the
muddling failure mode). **Paraphrase variants are not vector-near**, so a post-hoc centroid merge cannot
feed the starved tail. The fragmentation fix must happen at assignment time, not after.

## The root cause of fragmentation (found chasing verdict 2)

- Genome default: `epistemic_classifier.mode = "semantic"` (embed; "proved superior").
- But the local, gitignored `settings.local.json` bakes **`EXOCORTEX_EMBED: "0"`** into the hook env —
  every class on this repo was minted by the **lexical fallback**, whose own docstring admits paraphrases
  with no shared words won't merge. The fragmentation finding and this override are the same phenomenon.
- **The override is *vindicated*, not a bug:** measured cold cost of the semantic classifier in a fresh
  per-event hook process = **9.0 s** (MiniLM load; warm = 9 ms). Flipping the flag would tax every prompt
  ~9 s on the daily driver. The knob was set correctly; what was missing was knowing it is the
  fragmentation cause.
- **Structural fix = a persistent classifier process** (load once, classify in 9 ms) — exactly the
  Substrate-daemon / persistent-server direction already on the roadmap (the T5 lesson, third
  occurrence: heavy things must live off the per-event path). Until then: fragmentation is the accepted
  cost of a fast lexical hook.
- Minor, quantified: **1/90** cue clusters is system-minted (task-notification boilerplate), holding
  **19 deposits (~3%)** — real, small; a prompt-hygiene filter is an organism change, parked with its number.

## What this changes in the ranked path (Desktop audit → now)

1. **A/B outcome experiment (unchanged, still #1).** The off-arm is already free:
   `EXOCORTEX_COLONY_SPLICE=0` runs accrual-without-injection by design. Protocol: matched sessions on the
   `guide-accrue#18`-class task, splice on vs off, measure steps-to-first-exit-0 + orientation reads from
   the audit log. Not run here (needs live matched sessions).
2. **Research-repo unlock = solve the cold start**, not the crediting law. Options, each gauge-first:
   wire the dense lift (embed-mode only), or an explicit `cls=`-style deliberate seed for `wiki_active`,
   or content-level lexical indexing (costly at 59k nodes). The ADR-006 asymmetry stays untouched.
3. **Class merge: killed by gauge.** Do not build. Fragmentation routes to the persistent-classifier fix.
4. **Tool-node enrichment (audit #4): still open, needs its own gauge** — it collides with locked ADR-005
   (verb altitude, "nothing finer"), so the burden is a segment-reuse-vs-drift measurement at the finer
   altitude on real audit data, not an opinion.

## Gates / hygiene
- Both gauges read-only; nothing merged, nothing wired, no organism file touched.
- Tests: 6 (funnel) + 7 (consolidation), out of the 99-lock. **99-lock stays 99; explicit suites 241 green.**
- Live numbers above are a labeled demonstration, never evidence (per the standing law).
- `release/PROVISIONALS_FILED` added this session (provisionals filed per PI); push remains blocked by the
  denylist scrub gate — including this very document, by design.

## Reproduce
```
python -m exocortex.gauge.credit_funnel_gauge  --state-dir <repo>/.claude/exocortex
python -m exocortex.gauge.consolidation_gauge --state-dir <repo>/.claude/exocortex
```
