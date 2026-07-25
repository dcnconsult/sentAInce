# Proposer-Diversity Gauge v1 — the F1/F2 before-after gate (ranked lexical · explore rotation)

**Gauge:** `exocortex/gauge/proposer_diversity_gauge.py` (stdlib, read-only, fail-open). **Run:**
`python -m exocortex.gauge.proposer_diversity_gauge --repo <repo> [--limit N] [--json]`.
**Discipline:** gauge-first (ADR-002) — the 2026-07-24 log audit found the wiki proposer selecting in
filename order, so the fix was gated on a measured before/after with a **pre-registered falsifier** rather
than on the fix looking obviously right.

**Write-free by construction:** the gauge calls `splice._select` directly and simulates the F2 offer ledger
in memory, replaying the corpus in order (the only way rotation's effect is observable). The live
`wiki_offers.json` is never touched, and no τ is deposited.

**Data:** this repo's own live vault (2,305 nodes / 105 distinct documents) replayed against its real prompt
history — **344 prompts** recovered from the host's transcripts, `explore_budget=5`.

---

## The two arms

| arm | `lexical_rank` | `explore_rotate` |
|---|---|---|
| **before** | `file` (vault file order) | `order` (first-N, no memory) |
| **after** | `rank` (IDF-weighted surface overlap) | `rotate` (least-offered-first) |

## Result — **GATE MET**

| metric | before | after | |
|---|---|---|---|
| distinct documents **proposed** | 51 | **104** of 105 | primary |
| distinct documents **entering the explore channel** | 44 | **104** | primary |
| top-doc share of all proposal slots | 29.0% | **6.0%** | concentration |
| top-3 share of all proposal slots | 58.0% | **17.9%** | concentration |
| **credited-doc recall** (docs that earned τ, still reachable) | 22/30 = **73.3%** | 29/30 = **96.7%** | **control / falsifier** |

The control is the metric that could have sunk the change. Diversity bought by dropping the notes that
actually earn τ would be a regression dressed as an improvement; instead recall rose alongside diversity.

## Attribution — four arms, not two

| arm | distinct docs explored | Δ |
|---|---|---|
| before (`file` + `order`) | 44 | — |
| **F1 only** (`rank` + `order`) | 101 | **+57** |
| **F2 only** (`file` + `rotate`) | 51 | +7 |
| after (`rank` + `rotate`) | 104 | +3 on top of F1 |

**F1 is the fix.** Ranking decides which documents exist to be explored at all. F2's solo ceiling is the
un-ranked pool, so it should be judged by its on-top-of-F1 delta (+3), not its solo figure (+7).

## Honest limits

- **This is a retrieval-quality result, not an outcome claim.** It measures which documents get offered,
  not whether offering them causes more work to reach `exit 0`. The efficacy question is open — see
  `docs/CLAIMS.md` MARGINAL.
- **The figures move with the store, and are not reproducible to the digit.** Both the prompt corpus and
  the credited-document set are living: replaying later sweeps a larger corpus against a larger τ-set. An
  earlier run of this gauge at **340 prompts** read the control as 81% → 96% against a smaller credited
  set; the numbers above are the **2026-07-25 snapshot at 344 prompts / 30 credited docs**. The
  *direction* and the attribution split have been stable across runs; the exact percentages should be
  read as of their snapshot, never quoted as a fixed constant.
- **Single repo.** One vault, one prompt history, one task mix — and a task mix that includes the sessions
  that built the fix. A second repo with an unrelated task mix is the natural next control.
- Recall is computed over documents that have *already* earned τ, which is itself a product of the old
  filename-ordered proposer. It measures that the fix does not lose what the organ had learned; it cannot
  speak for documents the old proposer never surfaced to begin with.

**Verdict: +1 · GATE MET · kind: experimental-design.** Ship F1 and F2 on. −1 if a replay on a second repo
with a non-wiki task mix shows credited-doc recall falling below the before-arm baseline.
