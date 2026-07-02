# Contributing to SentAInce / FreqOS

Thanks for your interest. This repo has an unusual discipline: it is an **evidence-locked organism**, and
the contribution rules exist to keep the evidence honest.

## The one rule that governs everything

`python -m pytest` collects **only `tests/`** and must stay **99 tests, 99 green** — the 69-test C1–C7
evidence lock + 30 domain-crucible/adapter tests. This suite is a *claim ledger*, not a normal test suite:
**do not add, remove, or edit anything under `tests/` or `experiments/`** unless your PR is explicitly
about re-negotiating a locked claim (open an issue first; expect scrutiny).

Everything else tests **outside** the lock, run explicitly:

```bash
python -m pytest exocortex/tests cerebral/tests release/tests battle/tests   # component suites
python -m pytest                                                             # the 99-lock (must stay 99)
```

## Where new work goes

- **Additive only.** New organs/features live in their own package (`exocortex/`, `cerebral/`, `battle/`)
  and import the locked organs (`sentaince/organism/*`, `vendor/kernel/*`) **read-only**.
- **Frozen DNA.** `sentaince/organism/*` and `vendor/kernel/*` are integrity-baselined (see
  `exocortex/integrity.py`). If a change there is truly warranted, regenerate the baseline
  (`python -m exocortex.integrity --update-baseline`) in the same commit and say why.
- **Consequence-sourcing (ADR-001) is non-negotiable.** No code path may deposit memory (τ) on retrieval,
  frequency, or human tags — only on a verified `exit 0`. Read `docs/ADR.md` before touching
  `exocortex/colony.py`, `exocortex/hook.py`, or the wiki layer.
- **Gauge-first (ADR-002).** New organs ship dormant with a falsifiable gauge and a pre-registered bar;
  a `results/<gauge>_v1/RESULTS.md` verdict is expected alongside the code.

## Practical bits

- Pure-stdlib bias: the hot path (hooks) must stay dependency-free; heavier deps are confined to leaf
  packages and lazy-imported.
- Style: match the surrounding code — long-form docstrings that say *why*, module-level constants for
  genome values, tests as executable specs.
- License: Apache-2.0 (see `LICENSE`/`NOTICE`). By contributing you agree your contribution is licensed
  under the same terms.
- Architecture questions: `docs/ADR.md` (the architecture decision records) and `docs/CLAIMS.md` (the binding evidence
  ledger — nothing may claim past it) are the ground truth.
