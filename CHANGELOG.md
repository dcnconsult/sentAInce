# Changelog

What changed, and what it cost us to find out. Claims here must not exceed
[`docs/CLAIMS.md`](docs/CLAIMS.md) — the binding evidence ledger.

Numbers are measured on this project's own hardware unless stated, and negative results are kept.

## [0.1.5] — unreleased

The honesty release. Three of these are bugs that only ever manifested **outside** the development
repo — which is exactly why they survived four releases.

### Fixed

- **The organism was dead on arrival for every `pip install` user.** `deploy install` defaulted to
  `integrity=enforce`, but the kernel-lock baseline covers `vendor/kernel/**`, which **is not in the
  wheel**. So 56 of its 66 entries were structurally absent, `verify_kernel()` returned `ok=False`, and
  the apoptosis fired — **`exit 1` on every single SessionStart**, with empty stderr. Memory never
  initialised. `UserPromptSubmit` still returned 0, so it *looked* alive while never waking up.
  Confirmed in a clean venv: SessionStart `1 → 0`, and session state is now seeded.
  Integrity ships **`off`**, restoring the Genome's own default and its stated reason — *"Ships DORMANT
  so a stale baseline never bricks dev."* `--integrity enforce` still works for a full checkout that
  actually carries `vendor/kernel/`.
- **Every prompt paid a ~10 second tax.** The `semantic` cue-classifier was the default, and each hook
  is a fresh process — so MiniLM reloaded *on every prompt*, not just the first. Measured **10.15 s →
  0.125 s** (a fully-warm second run still cost 9.81 s, which is how we know it was never a cold-start
  problem). `lexical` is now the default; **`semantic` is opt-in** and, for the first time, actually
  installable: `pip install sentaince[embed]`. Its measured accuracy advantage is unchanged and one
  config key away. See [#4](https://github.com/dcnconsult/sentAInce/issues/4).
- **Hooks were being killed at 30 s.** The settings generator never emitted a `timeout`, so hand-set
  values were stripped on every re-deploy and hooks fell back to the host default — surfacing as
  *"hook timed out after 30s — output discarded"*. Now emitted explicitly.

### Added

- **The organism can finally talk to you.** It had no user-facing channel at all: everything it emitted
  went to the *model*, and the one visible event — a refusal — fires about **once per 1,100 tool calls**.
  A working install and a broken install produced identical observations. SessionStart now says so:

  ```
  🧬 sentaince: mode=observe · 1266 routes earned
  🧬 sentaince: mode=observe · no routes yet — earning starts on your first exit 0
  ```

  Rare and earned — once per session, never chatty. It changes nothing about your agent's behaviour;
  the model doesn't even see it.
- **The estate view — every repo, side by side.** Memory is earned per-repo and never crosses between
  them, but *orientation* travels:

  ```bash
  python -m exocortex.orient --estate --projects-root /path/to/your/projects
  ```

  Each repo gets a **credibility grade** (High / Medium / Low / Unknown) computed at read time from live
  probes — git, tests, real mtime — and the drift between what a repo *declares* and what the disk
  *shows*. A capsule carries no grade of its own: a repo cannot vouch for itself. File-based,
  stdlib-only, read-only. No database, no daemon.

### Changed

- Docs that claimed `semantic` was the default are corrected — including one file that contradicted
  itself, saying "the default" in prose while its own table said `lexical`.
- The README now leads with the 30-second, no-install demo instead of burying it below the fold.

### Internal

- A test now pins `genome.py` DEFAULTS against the shipped `exocortex_config.json` mirror. The classifier
  fix looked applied and did nothing for an hour because the shipped config silently won — two sources of
  default truth drift, so now it's a failing test instead of a mystery.

## [0.1.4] — 2026-07-09

Write-integrity (ADR-020): fail-open for the agent, fail-closed for the memory store. The unlocked
two-process deposit race lost **21 of 50 deposits (42%)**; under the lock, zero. Atomic replace,
quarantine-not-clobber, and a cross-process colony lock.

## [0.1.3] and earlier

See the [GitHub Releases](https://github.com/dcnconsult/sentAInce/releases) page.
