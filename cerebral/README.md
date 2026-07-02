# Cerebral Substrate (`cerebral/`) — Slice 0

The slow, off-hot-path organ of the SentAInce ecosystem. Where the fast body (the Claude Code / Cursor
hooks) earns and enforces in milliseconds, the Cerebral Substrate consolidates, organizes, and paces over
minutes — the altitude at which G.A.R.D. **Governance / Alliance / Dignity** finally make sense, plus
long-term memory. It is the neocortex to the colony's basal-ganglia + the wiki's hippocampus.

**Full design:** the Cerebral Substrate design review is kept outside this repo.

## Discipline (read first)

- **Additive & READ-ONLY.** This package observes and reorganizes the *record*; it never earns τ, never
  writes a colony / session / audit, and never touches the vault it reads. Only an `exit 0` in a live body
  earns memory (ADR-001). The Substrate is a **proposer/archivist, never a disposer**.
- **The lock stays the lock.** `pytest` (which collects only `tests/`) remains the 99-test build-gate.
  This package's tests live under `cerebral/tests/` and run explicitly: `python -m pytest cerebral/tests`.
- **Gauge-first (ADR-002).** No organ is built before a gauge says the prize is real. Slice 0 is *only*
  the gauge.
- **Live = demonstration, never evidence.** A run over a real vault is a labeled demonstration; it can
  never move a locked verdict.

## Slice 0 — the TAO Resurrection Gauge

The Substrate's core mechanism is a **living ledger** with two registers: a *utility register* (pruned
colony routes, `+1/0/−1` by consequence) and an *intent register* (research threads). An **intent** is an
open loop with a TTL — it opens, and stays OPEN until its intent closes; one that goes stale past a
*reasonable timeframe* is a **crack-faller**, the resurrection target.

This gauge measures — read-only, offline — whether the intent register can surface genuinely-lost,
worth-resuming threads from a research vault. It harvests **declared** intents only (Markdown checkboxes,
task-status/manifest files, structured `ledger.json` decision labels) — never inferred from prose —
resolves dates, flags `OPEN ∧ stale`, and (once the PI labels a sample) reports
**precision @ worth-resuming**. That number gates the persistent ledger + Consolidator + Governor.

```bash
# emit the stale-open candidate list (read-only):
python -m cerebral.gauge.resurrection_gauge --vault ~/research-vault --now 2026-07-01 --json

# after labelling candidates → precision:
python -m cerebral.gauge.resurrection_gauge --vault <path> --now <ISO> --labels labels.json
```

`spaCy` is **optional** — the gauge is pure-stdlib; spaCy only enriches the `(action, anticipated_result)`
decomposition and fails open to a regex extractor when absent.

## Not in this slice (gated on the gauge)

The persistent hash-chained JSONL journal, the utility register (colony-prune observation), the
Consolidator, the Governor read-view (`strategic_status`), the SQLite→Postgres store, the containerized
daemon, and the circadian actuator — all follow-on slices, built only if this gauge clears its bar.
