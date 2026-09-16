# R0 local trial (soak): `colony.verb_keying = working` on this repo

**Started:** 2026-09-16, PI-approved. **Frozen** in this commit, before any trial data is read beyond the
flip-time control below.
**Scope:** this repo only, via its gitignored `exocortex_config.json`. The committed package default stays
`first`. Other estate repos are unaffected; each repo resolves its own config, and the research vault was
verified to resolve `first`.
**Revert:** delete the `colony` block from that config. Behavior is then byte-identical to before.
**Flip epoch:** `1789583027` (taken after the config edit, so no first-keyed deposit counts as trial data).
Audit line at flip: 13,403.

## Readout (reproducible)

```
python -m exocortex.gauge.verb_keying_gauge --soak-state .claude/exocortex --since 1789583027 --from-line 13403
```

- **S1** `new_nav_env_share`: of edges stamped (F3 `meta.ts`) at or after the flip, the share touching a
  navigation or env command node.
- **S2** classes with post-flip edges, and how many of them have a navigation or env edge as their
  strongest post-flip edge.
- **S5** nav/env share of all stored edges and of stored τ. Old first-keyed edges should decay out.
- **S3** the red-team suite (`exocortex/tests/redteam`): no new failures. The `rt-key-1` xfail stays
  xfail, because it asserts the committed default.
- **S4** `S4_chain_from_flip.ok`: **every** chained audit record from line 13,403 onward matches its own
  self-hash and links to its predecessor. `S4_quarantine_files` must stay 0. Plain `verify_audit` is **not**
  the check: the store carries a known **historic** link break at chained-index 1252 (D7 era, before
  ADR-020), and `verify_audit` reports only the first break. The window check was controlled on a
  synthetic chain holding both an early and a late break (`test_chain_breaks_from_sees_a_break_after_an_earlier_one`).

**Baseline** (pre-flip store snapshot): 180 classes, 4,404 deposits, 1,179 edges; **S5 edge share 0.0738,
τ share 0.0379**.

**Flip-time control** (same turn): 2 post-flip command edges, 0 nav/env (**S1 = 0.0**). The turn's
`cd … && python`, `cd … && date` and `cd … && cat` commands were filed as `bash:python`, `bash:date` and
`bash:cat`. Pre-flip, the same class held `cue → bash:cd`. The knob is taking effect in the live hook.
A later reading the same day showed 11 post-flip edges, S1 = 0.0, S4 window ok (25 chained records, 0 breaks),
and 0 quarantine files.

## Decision rule (frozen)

**Evaluate when both hold:** at least **300 new depositing consequences** since the flip (audit
`PostToolUse ok` rows with `seg_len > 0`, after line 13,403) **and** at least **7 days** elapsed.

| Disposition | Condition |
|---|---|
| **+1:** propose flipping the committed default to `working` (a separate PI decision, plus re-running the CLAIMS verb-altitude figures) | S1 ≤ 0.05 **and** S2 nav-topped ≤ 5% of classes **and** S3 and S4 hold **and** S5 τ share is below baseline (0.0379) |
| **−1:** revert the local flip and investigate | S1 > 0.10 (the keying is not taking effect live), **or** any S3/S4 failure attributable to the flip |
| **0:** continue the trial | anything else |

## What this trial cannot show

It shows that the mechanism is live and that stored memory becomes cleaner. It does **not** show that
working-verb routes help an agent reach `exit 0`; efficacy stays unmeasured, as in CLAIMS. Flipping the
committed default on this evidence is an ADR-003 judgment and would need to be said as exactly that.

**Verdict:** 0 · kind: experimental-design · trial started and the flip-time control passed (S1 = 0.0 on
the first post-flip edges) · −1 if S1 > 0.10 at evaluation.
