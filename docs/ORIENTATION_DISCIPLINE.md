# SentAInce — Cross-repo orientation discipline (agent operating principles)

Operating instructions for any agent working across the estate — human or model, in-session or on a PR.
It applies the project's standing skepticism ("a large README or a COMPLETE banner is not maturity") to
the *agent's own first minutes* in an unfamiliar repo. Decision record: [ADR-019](ADR.md); the sibling
deliberative discipline is [REASONING_DISCIPLINE.md](REASONING_DISCIPLINE.md).

## 1. The rule

**When working outside the current working tree, identify the target repo's last-known state before
making assumptions or taking action.** Load its **Repo Orientation Capsule** — via the `orient_repo` MCP
tool, or `python -m exocortex.orient <name>`, or (when neither is available) the estate `REPO_LOG.md` —
and check the credibility grade *first*.

A capsule carries: repo identity and canonical status · last reviewed date · last activity (declared
*and* observed) · maturity / strength / portfolio tier · claim-boundary pointer · known risks ·
cross-repo links.

## 2. The credibility grade — the reader's audit, never a self-report

The grade is computed at read time from live disk probes plus the drift between what the repo *declares*
and what the disk *shows*. A capsule file carries no grade; one smuggled in is dropped.

- **High** — recently reviewed, git + tests present, declaration and disk agree. Orient and proceed.
- **Medium** — useful orientation, but older or partially inferred. Verify what you rely on.
- **Low** — a hard signal fired: no git, superseded, dormant Tier C/D, stale review, or the declaration
  contradicts the disk. Do not act on the repo's story.
- **Unknown** — no capsule and no estate-log row. You know nothing yet; behave accordingly.

Every grade arrives with its reasons. The thresholds are calibration (named constants in
`exocortex/orient.py`), not doctrine; the rubric shape — deterministic, first match wins, reasons always
attached — is pinned by ADR-019.

## 3. Below High, the first task is RE-ORIENT — not "continue work"

Inspect, in order: the README *as a claim, not a fact* · recent commits / activity · tests and whether
they run · the claim ledger (`docs/CLAIMS.md` or equivalent) · roadmap / open state. Then **update the
capsule** (and the estate `REPO_LOG.md` row if you are auditing) so the next agent inherits your
orientation instead of repeating it.

## 4. Cross-repo links are first-class

Ten edge names, pinned by ADR-019: `supersedes` · `superseded_by` · `feeds_into` · `depends_on` ·
`shares_artifact_with` · `forked_from` · `public_mirror_of` · `private_canonical_of` ·
`deployment_target_of` · `evidence_source_for`. Declare them in the capsule's `links` (or the REPO_LOG
`## Cross-repo links` section); the estate view flags one-sided mirrored pairs. A `superseded_by` link is
a Low-grade signal on its own — the canonical head lives elsewhere; go work there.

## Two guardrails (or the ritual backfires)

1. **Never treat a README, banner, or prior memory as current truth without checking credibility.** The
   capsule exists so orientation is *checked* metadata; skipping the check and trusting the freshest
   prose you saw is the exact failure mode this discipline forecloses.
2. **A capsule orients working memory only — it never earns τ, never gates recall, and is never
   evidence** (ADR-013: authority never earns τ; ADR-019: neither does orientation). Reading a capsule
   about repo X in repo Y moves no memory anywhere — cross-repo *recall* remains ADR-014's open,
   parked question.
