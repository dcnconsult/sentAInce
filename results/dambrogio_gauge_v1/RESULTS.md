# D'Ambrogio VoI-alignment gauge (D4) — v1 results

**Gauge:** `exocortex/gauge/dambrogio_gauge.py` · **Date:** 2026-06-30 · read-only, pure-stdlib, ADR-002.
**Command:** `python -m exocortex.gauge.dambrogio_gauge` (auto-scan `<dev-root>/*/.claude/exocortex`).
**Paper:** D'Ambrogio et al. 2026 (`../../Paper4_DAmbrogio_SentAInce_Alignment.md`, TAO-2 design-informant).

## Verdict — **vectors 1–3 CONFIRMED · β4 = POWERED NULL → PARK (data-gated)**

A *load-bearing negative* (a gauge success, not a failure — cf. the eligibility / uncertainty /
nonstationarity nulls): the colony already embodies the paper's stay-dynamics, but there is **no
directed-exploration signal for a β4 bonus to align with** on real flagship traffic, and the read is
**powered** (not an abstain). The seductive "5-line β4 patch to `_eff_tau`" has no behavioral demand.

## Data (pooled: SentAInce flagship + cursor_testbed + 2 sibling repos)
- 66 goal-classes · 535 deposits · 147 prompt-turns · 45 switches-to-already-seen-classes.
- Models stamped (F3): only `claude-opus-4-8` — **0 multi-model classes** (gpt-5.5 never reached a deposit;
  Q4 diversity is the thing the multi-model soak would populate).

## The four questions
| Q | Metric | Result | Read |
|---|--------|--------|------|
| **Q1** vectors 1–3 | β1=`DEPOSIT`=1.0 · β2=−ln`DECAY`≈**0.105** · pooled `dep↔τ` Spearman **ρ=0.597** (flagship 0.69) | **CONFIRMED** | τ rises with deposits; the colony's decay *is* multiplicative information-satiation, its deposit weight *is* attentional inertia — quantified, independently validated |
| **Q2** β4 gap | `DEI_seen=0.729` (n=45; ~5σ **above** the 0.5 null) · `DEI_all=0.251` | **NULL (powered)** | raw switching only *looks* exploratory because new tasks are 0-visit (novelty); controlled for novelty, switching is **exploitation-directed** — the opposite of directed exploration |
| **Q3** power | classes 66 ≥ 8 · switches_seen 45 ≥ 20 | **POWERED** | this is a genuine null, not an underpowered abstain |
| **Q4** diversity | 1 model, 0 multi-model classes | **LATENT** | no cross-model provenance yet → the soak's job |

## Honest caveats (load-bearing)
- **Class selection is prompt-driven** (the user picks the task), not an organism policy. So the DEI measures
  whether the *human+agent's task-selection* has VoI-directed structure a colony β4 bonus could align with —
  it cannot isolate a colony policy, and it is confounded by task novelty (handled by the seen-only DEI).
- Live single-dev data is a **labeled demonstration, not evidence** — this fit is a design-informant
  (TAO-2), must-not-exceed `CLAIMS.md`.

## D1 flip-trigger (unmet)
Build the β4 organ (dormant, on the G5 suggest-then-verify lane — never a raw `_eff_tau` boost) **only if**
`DEI_seen < 0.40` **and** powered **on population / multi-model data**. Flagship = **0.729 → do not build.**
**Retire-trigger:** re-run on the multi-model Cursor soak; if diverse task-switching there shows
`DEI_seen < 0.40`, revisit. Until then β4 stays a design-informant, parked.

## Raw
```
AGGREGATE: classes=66 deposits=535 turns=147 models=['claude-opus-4-8']
  Q1: β1=1.0 (DEPOSIT) · β2=0.1054 (-ln DECAY) · dep↔τ Spearman ρ=0.597
  Q2: DEI_seen=0.729 (switches_seen=45) · DEI_all=0.251
  Q3: powered=True   Q4: 1 model, 0 multi-model classes
VERDICT: PARK — no directed-exploration signal (DEI≈0.5+: switching is not under-exploration-directed)
```
Reproduce: `python -m exocortex.gauge.dambrogio_gauge --json`.
