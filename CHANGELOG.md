# Changelog

What changed, and what it cost us to find out. Claims here must not exceed
[`docs/CLAIMS.md`](docs/CLAIMS.md) — the binding evidence ledger.

Numbers are measured on this project's own hardware unless stated, and negative results are kept.

## [0.1.8] — 2026-07-20

A positioning and honesty pass. **No code changed** — no immune kernel, no C1–C7 lock, no hook behavior,
no API. Safe upgrade, and skippable if you only run the organism.

An outside reviewer put this project on a shelf next to named alternatives and concluded it was "not yet
ready as a primary tool." That reading was correct. Rather than argue, we wrote the shelf down ourselves.

### Added

- **`docs/LANDSCAPE.md` — where this actually sits.** Agent-safety tools are usually compared by feature
  list; the useful axis is **altitude** — where in the call path the check runs, because that decides what
  it survives. Prompt rules, detection, proxy/gateway control planes, dialog rails, and in-process
  execution refusal (us) are different layers, not competing answers. A gateway cannot see a call that
  never leaves the process; a detector that flags a command still needs something to refuse it. We are the
  refusal, and a floor is only useful if you also have the rest of the building. The page names no
  vendors — that is a claim about someone else's software, and it goes stale.
- **Host support stated plainly**, as a status table rather than a feature list: Claude Code supported;
  Cursor a soft, fail-open, user-bypassable shim; **Codex** and **Kimi Code** named as near-term targets;
  any MCP client gets the memory organ and **not** the hook gate. If your host is not in the supported
  row, you get memory and no gate — better to know before installing than after.
- **The multi-repo estate written up as what it is**: the differentiator that exists *today*. Most agent
  tooling is single-repo by construction; developers are not.

### Changed

- **The A/B result is now published in the positioning docs, not just the ledger** — 0.625 vs 0.475, a
  +15pp gap that widened on extension, **p = 0.0781 against a pre-registered gate of p ≤ 0.05, openly
  unmet**, plus the honest reason it is underpowered (short timeline, one maintainer, only 6 of 16 tasks
  able to move at all). Trending, on a real control, reported as trending. A directional result sold as a
  win would be the exact failure this project exists to avoid.
- **Commercialization material withdrawn from the public tree.** `docs/PRODUCT.md` is no longer published,
  the README's Free-vs-Paid table is replaced by a plain statement that the whole local body is
  Apache-2.0, and forward-looking product language in ADR-011/012 was softened. The decisions and the
  boundary mechanism are unchanged and nothing was superseded — both ADRs carry a dated note saying the
  wording was touched. **"Never paywall safety" survives verbatim**; it is the load-bearing law.

### Fixed

- Four dangling documentation links from the withdrawal above — two of which only surfaced by building the
  derived public tree and grepping the *artifact*. A grep over the source docs reported clean. The release
  gates also reported READY: they check secrets, license, IP disclosure, wheel purity, and worktree
  cleanliness — **not link integrity**. Another instance of the standing rule that a green gate proves the
  tree is publishable, not that it is correct.
- Issues [#12](https://github.com/dcnconsult/sentAInce/issues/12) and
  [#13](https://github.com/dcnconsult/sentAInce/issues/13) closed — shipped in 0.1.7 and left open for
  three days.

## [0.1.7] — 2026-07-17

Two community-issue features and a documentation pass that finally gives the body page a face. No change
to the immune kernel, the C1–C7 lock, or hook behavior — safe upgrade.

### Added

- **`sentaince why` — the organism shows its work** ([#13](https://github.com/dcnconsult/sentAInce/issues/13)).
  A read-only renderer that reconstructs, for a recent earned habit, the exact route behind it, which past
  successes still back each step, the notebook credit, and the tamper-proof audit segment **re-verified from
  disk** (a silently edited record renders `CHAIN BROKEN`). Reachable three ways: `python -m
  exocortex.provenance`, `sentaince why`, and a **"why?"** link on the body page (`/api/provenance/<repo>`).
  It never writes anything.
- **PowerShell-aware somatic recognizer** ([#12](https://github.com/dcnconsult/sentAInce/issues/12)). The
  lethal-command vocabulary, mirrored into PowerShell idiom (cmdlet, alias, and abbreviation forms, with
  `-EncodedCommand` unwrapping). Shipped **importable but unwired** by design — the hook routing is under a
  control-plane pin and lands separately; a test asserts it stays unwired. Closes the honesty gap where
  Windows PowerShell commands were audited but not yet recognized.

### Docs

- The body page finally has **screenshots** — a working organism (every color the doctrine defines) and a
  fresh cold-start deploy (all outlines — *nothing fakes green*). The README, QUICKSTART, and STORY now lead
  with `sentaince body` as the visible payoff instead of routing new users to a Docker dashboard.
- The `sentaince` command (`status` / `body` / `why`) is documented for the first time; the quickstart uses
  the friendly console scripts.
- A real-use example of the **epistemic VERIFY** gate pausing a high-stakes action (README "See it work").
- Fixed real stale data: Python ≥ 3.10 → 3.11 (matches `pyproject`); the semantic classifier is opt-in, not
  "the default"; the repo-feeder is shipped, not "planned."
- Fixed the blank **somatic-veto demo**: the GIF rendered as a title bar over black in browsers (a disposal/
  transparency encoding fault); replaced with a flattened PNG of the same demonstration.

### Tests

- Organism suite 320 → 357 (12 body/estate/CLI + 5 provenance + 32 PowerShell-recognizer contract tests).
  The 99-test kernel lock is untouched.

## [0.1.6] — 2026-07-17

The face release. No change to the immune kernel, the C1–C7 lock, or any hook behavior — this release
gives the organism a face and a voice you don't need Docker to see.

### Added

- **The body page.** The exporter's home (`:9109/`) now draws **one human silhouette per repo**, each
  organ region colored by a live, thresholded raw vital — head = sleep, heart = stamina, chest shield =
  immune, arms = muscle memory, book = notebook. Every color prints the rule that produced it beside the
  number (the rules are [`docs/COLOR_DOCTRINE.md`](docs/COLOR_DOCTRINE.md)); organs whose own gauge said
  the prize was modest render **gray (dormant)**, and organs that simply haven't seen data render as a
  dashed outline — **nothing ever fakes green**. The knobs page moved to `/control`, one click away.
- **A bare `sentaince` command.** `sentaince status <repo>` prints the vitals voice line — the promised
  fallback for environments where the session-start `systemMessage` doesn't render — and
  `sentaince body <repo>` starts the exporter (loopback, zero dependencies) and opens the body page.
  Unknown subcommands dispatch **lazily** to the new `sentaince.commands` entry-points group, so
  third-party packages can add subcommands — and a broken plugin can never break `status` (test-pinned).
- **Onboarding from the dashboard.** Sibling git repos with no organism appear on the body page asleep,
  with a copy-paste deploy command. Deploying stays a deliberate CLI act — the web plane never executes it.
- **The estate file.** `~/.exocortex/repos.json` is now the first-class, documented multi-repo registry
  ([`docs/ESTATE.md`](docs/ESTATE.md)): a `version` key, an ignore-unknown-keys rule, and a
  preserve-unknown-keys-on-write rule (both test-pinned), plus a bounded web editor on `/control` behind
  the exporter's existing write guards. `/api/vitals` now carries `schema_version` and evolves
  additively from here.

### Tests

- 12 new contract tests (`exocortex/tests/test_body_estate_cli.py`): the cold-body negative control
  (an empty repo renders outlines, never green — this control caught and fixed a fake-green immune
  state during development), the estate round-trip rules, dormant discovery, and the lazy-plugin proof.
  Organism suite 308 → 320; the 99-test kernel lock untouched.

## [0.1.5] — 2026-07-16

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
