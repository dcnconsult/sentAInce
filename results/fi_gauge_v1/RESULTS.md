# FI_hat Decisive Gauge — v1 results

**Gauge:** `cerebral/gauge/fi_gauge.py` · **Date:** 2026-07-01 · read-only, pure-stdlib, deterministic, ADR-002.
**Command:** `python -m cerebral.gauge.fi_gauge --audit .claude/exocortex/audit.jsonl --altitude verb`
**Framing:** the [[functional-information-ledger]]'s first instrument — *"does `FI_hat` carry discriminative
power raw τ does not?"* (Design Review §, the decisive gauge; `../../SentAInce_Cerebral_Substrate_Design_Review_v1.1.md`).

## Verdict — **NULL · the denominator adds nothing at flagship traffic (permutation p = 0.14 ≥ 0.05)**

FI_hat's *only* novelty over the colony's pheromone τ is the **attempts denominator** (τ counts successes,
is blind to failures — ADR-001 deposits only on `exit 0`). The decisive test asks whether per-configuration
**reliability** (successes / attempts) separates good routes from clutter in a way the success-count alone
cannot. On the flagship's own audit log — and on the pooled SentAInce+TAO corpus — it does **not**:

- **permutation p = 0.14** (verb altitude) / **0.60** (command_key altitude): per-config reliabilities are
  **indistinguishable from one shared ~92 % base rate**. The spread of failure across routes is sampling
  noise, not signal. τ is invariant to *where* failures land; here there is no "where" to exploit.
- **84 % of all failures are mechanical noise** — `cd` path-slash typos (Windows `\` vs `/`), `echo`, `ls` —
  not "this route is a bad idea." The genuinely route-bearing verbs (`git` 50/51, `python` 45/47, `find`
  16/17, `grep` 15/16) all succeed 95–97 %, exactly where τ already ranks them.
- **Spearman(τ-analog k, reliability p̂) = −0.13**: reliability re-ranks configs almost *orthogonally* to τ —
  which looks like FI adds information, but the permutation test shows that re-ranking is **not real** (p=0.14),
  and where it does demote (`ls`, `echo`, `cd`) it demotes noise. This is precisely why the shuffle null is
  the decisive test and Spearman alone would have misled.

**This is the "better *language*, not a new mechanism" arm of the pre-registered either/or** (the memory's
"If no → FI is a better language for what τ already does"). **The win is real anyway:** the gauge *built* the
attempts/failure denominator the roadmap parked for a year ([[exocortex-hook-integration-roadmap]] W4;
ADR-004 decaying τ⁻) into a working, tested instrument — and gave it an honest, reproducible null. It also
**sizes the [[oss-community-strategy]] thesis quantitatively**: single-dev traffic is structurally too
low-variance (11 powered configs, one shared success rate) to make the denominator pay.

## Data (SentAInce `audit.jsonl`, verb altitude — a **live** log of the session, counts as-of run)
- **~2906 records** → **535 Bash consequences** with an `ok|fail` outcome (493 ok / 42 fail overall).
- **33 configs** at the verb altitude; **11 powered** (n ≥ 5): 500 attempts / 459 successes.
- **45 failures** among powered configs; **38 (84 %) on noise verbs** (`cd` 23, `echo` 10, `ls` 3).
- Base success rate (powered) = **0.918**; dispersion `T_obs` = 0.0022; permutation p = **0.14** (R=2000, seed=0).

| Altitude | configs | powered | perm p | Spearman(k, p̂) | verdict |
|---|---|---|---|---|---|
| **verb** (`bash:git`) | 33 | 11 | **0.14** | −0.13 | NULL |
| **command_key** (`git add`) | 110 | 11 | **0.60** | −0.04 | NULL |
| **pooled** (SentAInce+TAO, verb) | 37 | 11 | **0.14** | +0.12 | NULL |

## The questions
| Q | Metric | Result | Read |
|---|--------|--------|------|
| **Q1** does the denominator exist? | 535 attempts / 42 failures attributable per config | **YES (built)** | the audit is the sole live denominator (τ has none) — the gauge instantiates it; W4 no longer vaporware |
| **Q2** is it powered? | 11 configs clear n≥5; median attempts/key = 1 | **THIN** | borderline — the single-dev regime barely powers a homogeneity test |
| **Q3** does reliability vary beyond chance? | permutation p = 0.14 (verb) / 0.60 (key) | **NO** | one shared ~92 % coin explains the spread; no route-quality heterogeneity |
| **Q4** does it beat τ? | Spearman ≈ 0 re-rank, but null-indistinguishable; 84 % of failures = noise | **NO** | FI_hat = a better language for τ here, not a new organ |

## Honest caveats (load-bearing)
- **Live = demonstration, never evidence.** A labeled run over one growing log, not a locked verdict; the
  C1–C7 lock rests on topology, not on this. The audit **grows as the session runs** (this session's own
  commands append), so exact record/attempt counts are as-of the run — the NULL is robust across them.
- **The denominator is noise-dominated, not merely thin.** Even with more traffic, 84 % of the current
  failure mass is `cd`/`echo`/`ls` mechanical noise. A useful FI_hat needs failures that encode *route
  quality* (a genuinely bad approach that fails), which this corpus barely contains. Filtering noise verbs
  would shrink the already-thin denominator further — the honest read is **regime**, not filter.
- **Altitude (Amendment 1) was tested, not assumed.** Both the coarse `verb` and the fine `command_key`
  reference classes give NULL; coarsening to gain power did not manufacture signal. The equivalence-relation
  problem is real but is not the blocker here — the *base data* is homogeneous.
- **The intent register cannot feed FI_hat yet.** The −1/0 (falsified/inconclusive) valence lives in
  `MAINTENANCE_LOG`/FAL registers unparsed in v1 (resurrection Q3) — all closed intents read +1, i.e. no
  denominator. So the procedural audit is the *only* live source, and it is null. (Amendment 2 axis: dormant.)
- **KT (add-½) smoothing + a power-gate + a frequency-matched permutation null** are all applied — the
  estimator hygiene the framing demanded (no un-smoothed 0/1 certainties; abstain when underpowered; test
  against the project's own shuffle discipline, `gauge/analyze.py`).
- **Read-only + additive.** New `cerebral/gauge/fi_gauge.py` + tests + this doc only; the 99-lock stays 99;
  `cerebral` suite 23/23. No existing file modified.

## What it means for the Substrate (consequence)
- **Do NOT build a τ⁻ / FI_hat organ off flagship traffic.** The denominator is not yet a lever here; τ
  (numerator, consequence-sourced) remains the right procedural signal at this scale.
- **Ship the gauge *with* the failure-ledger, dormant, with a retire-trigger.** When traffic diversifies —
  the population / OSS regime, or a BYO-model testbed generating genuinely-bad routes — re-fire this exact
  gauge; a permutation p < 0.05 there flips NULL → BUILD without new code. FI_hat's value is
  regime-dependent, and this gauge is the detector.
- **Adopt FI_hat as the paper/IP *language*** (Szostak/Hazen estimator, agnostic on the "law of increasing
  FI") — a better vocabulary for what consequence-sourcing already does, with the moat = the earned data,
  not the theory. The null does not weaken the framing; it bounds the *claim* (CLAIMS.md must-not-exceed).

## Retire / revisit triggers
Re-run and re-decide when **any** holds: (a) ≥ ~30 powered configs at verb altitude (population regime);
(b) a corpus where < 50 % of failures are noise verbs (real route-quality failures present); (c) the intent
register's −1/0 valence becomes parseable (FAL/`MAINTENANCE_LOG`) → a *second* denominator to test.

## Raw
See `raw_verb.txt` (full run). Reproduce:
```
python -m cerebral.gauge.fi_gauge --audit .claude/exocortex/audit.jsonl --altitude verb            # headline
python -m cerebral.gauge.fi_gauge --audit .claude/exocortex/audit.jsonl --altitude command_key     # fine altitude
python -m cerebral.gauge.fi_gauge --audit A.jsonl --audit ~/research-vault/.../audit.jsonl          # pooled
```
Deterministic: audit path(s) as args, seeded permutation (seed 0, R=2000), no wall clock.
```
VERDICT (verb): label=NULL  signal=False  p_value=0.14  powered=11
  => per-config reliabilities indistinguishable from one shared base rate → FI_hat is a better *language*
     for what τ already does, not a new mechanism (at flagship traffic).
```
