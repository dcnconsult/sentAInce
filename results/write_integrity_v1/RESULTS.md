# Write-integrity arc (ADR-020, W1–W4) — evidence bank

**Date:** 2026-07-09 · **Provenance:** cursor_testbed Codex-probe corruption artifact
(`audit_codex.stage1-corrupt.20260709.jsonl`: 3 torn rows + 53 chain breaks under subagent fan-out)
→ audit of this tree → W1–W4 hardening. Tests: `exocortex/tests/test_write_integrity.py` (10).

## The bite check (the race is real)

Two processes × 25 deposits into the same colony class:

| pattern | deposits survived | lost |
|---|---|---|
| unlocked `load → deposit → save` (pre-W3, the old `hook.py` path) | **29/50** | **21 (42%)** |
| `Colony.locked` RMW (W3) | **50/50** | 0 |

The unlocked run is the scratchpad reproduction (not committed); the locked run is the deterministic
regression test `test_lost_deposit_race_two_processes`, plus `test_sweep_vs_deposit_no_lost_updates`
for the consolidation-sweep race (20/20 deposits + 20/20 consolidations survive).

## Gauge baseline (`baseline_2026-07-09.json`, live store, pre-arc traffic)

- audit lines **7091** · **torn lines 5** · chain **broken at chained-index 1252** — our own
  production store carries the same tearing/fork signatures the Codex probe hit. The exposure was
  real here, not just in the testbed; the damage predates this arc (W1 makes new tears impossible,
  the chain break is D7-era history and stays in the record — the chain is tamper-*evident*, not
  self-healing).
- consequences **1532** · `lock_failopen` rows **0** — **vacuous today** (the field ships with this
  arc; no pre-arc row can carry it). The verdict below is honest only as "no contention evidence
  yet"; the meaningful read is the NEXT gauge run after real flagship-fan-out traffic.

**Verdict:** 0 · kind: experimental-design · daemon question undecidable until post-arc traffic
accrues; re-run `python -m exocortex.gauge.lock_contention_gauge` after ~1k new consequences.
−1 for W1–W3-only if fail-open rate ≥ 1% of consequences; +1 (daemon stays parked) if it holds ~0.
