# Changelog

What changed, and what it cost us to find out. Claims here must not exceed
[`docs/CLAIMS.md`](docs/CLAIMS.md) — the binding evidence ledger.

Numbers are measured on this project's own hardware unless stated, and negative results are kept.

## [0.1.9] — 2026-07-22

The safety floor stops being Bash-only, the organism learns to report its own dose, and three claims
we had been making get withdrawn by our own re-analysis. **The kernel is untouched** — 99 frozen tests,
C1–C7 lock, no API change. The one behavioral change is a gate that refuses *more*, never less.

### Added

- **🛡️ The somatic veto now covers PowerShell (ADR-021).** An audit of **16,623 live records across 10
  repos** found the gate evaluating Bash 3,362/3,362 and **every other tool 0** — including **828
  PowerShell calls**. On a Windows host PowerShell *is* the shell, so the refusal floor that is this
  product's whole thesis did not cover the platform's primary command channel. It does now, under the
  same mode semantics as Bash: cmdlet forms, alias forms (`ri`/`spps`/`del`), parameter abbreviations,
  and `-EncodedCommand` payloads unwrapped before matching. Coverage of *mutating* tool calls rises
  **46% → 57%**. That is a coverage number, not a harm-prevention claim: it says the channel is no
  longer dark, nothing more. The change can only ever turn an `allow` into a `deny`.
  **The residual is disclosed, not closed** — splatting, variable indirection (`& $cmd`), and
  `Invoke-Expression` over computed strings are unrecognizable to *any* static vocabulary.
- **📊 `sentaince status --full` — the self-evidencing usage report.** The organism's one visible event
  is a refusal, which fires roughly once per thousand tool calls, so a working install and a broken one
  look identical from the outside (the 0.1.5 DOA arc is that scar). This answers the question the vitals
  line doesn't: *is it doing anything for me, and how much?* Two numbers — **memory contribution** (share
  of prompts where an earned route existed to splice) and **somatic coverage** (share of mutating tool
  calls the floor actually evaluated). Read-only, stdlib-only, reads your own repo's audit log; nothing
  is written and no telemetry exists. **It reports dose, never effect**, and the footer says so.
- **📁 File writes are formally out of the somatic floor's scope (ADR-022).** Write/Edit are 3,074 of the
  ungated calls, and the honest reason they stay ungated is that a write has no *shape* to recognize —
  the same call is a fix or a wipe depending on content the gate cannot judge. Recorded as a **negative
  decision** so "Write/Edit are ungated" stops reading as an open gap forever.

### Corrected

- **We re-analyzed our own A/B result and lost the secondaries.** The guide-accrue A/B's headline stands
  — paired ON/OFF, 50/80 vs 38/80, **p = 0.0781 against a pre-registered gate of p ≤ 0.05 that remains
  openly unmet** — but a re-analysis holding the *secondary* measures to the same paired test as the
  primary found that none of them survive it:
  - The **"cleaner on out-of-scope writes" claim is withdrawn.** Pooled across runs it looked
    significant (5 vs 15, p = 0.0147); paired by task it is **p = 0.25**, the whole asymmetry sits in
    **2 of 16 tasks**, and **every out-of-scope run in the corpus was a failed run**. It was a
    restatement of the success result on two tasks, not independent corroboration of it.
  - The **output-token efficiency advantage is withdrawn** — pooling success-only runs across arms with
    different success *compositions* manufactured it (−8.3% pooled → **−0.3% paired, p = 0.80**).
    Wall-clock survives pairing (−12.6%) but at **p = 0.21**, so it is stated as directional and
    unpowered, never as a win.
  - **"The gap widened when we extended the run" is corrected to "the gap stayed stable."** The
    cumulative series is 12.5 / 15.6 / 12.5 / 14.1 / 15.0 pp — the R=3 baseline was a local minimum, so
    the "widening" was a two-point read of a wobbling series. The honest claim is stability across a 5×
    increase in runs. This wording shipped in the 0.1.8 notes and in `docs/LANDSCAPE.md`; both are fixed.
  - **A protocol deviation is now on the record:** 3 of 80 ON-arm runs used `claude-opus-4-8` rather than
    the pinned `claude-fable-5`, all on one task, none in the OFF arm. Dropping them: +14.84pp,
    **p = 0.0781 — unchanged**. It did not move the result; it was still a defect not to disclose it.
  - Minor: the battery had **5** saturated tasks, not 6 (the sixth was a mid-range tie). The
    "only 6 of 16 tasks could move" power argument is unaffected.

  Net: **success rate is the only signal that A/B produced**, and it is trending, gate-unmet, and
  parked. No public claim rested on the withdrawn secondaries. The full numbered amendment is on the
  private study record (the 160-run corpus is not published).

- **Seven places in the docs said PowerShell wasn't vetoed, after we had shipped the veto.** This is the
  inverse of the usual failure — the documentation *understated* the product — but a false statement
  about a safety guarantee is a defect in the one artifact class that cannot have them, and a Windows
  user reading the install banner would have believed they were unprotected when they were not. The
  worst offender was the **bootstrap text written into your repo's own agent context**, so the agent
  itself was told the channel was ungated. All corrected, each one naming the residual before the
  coverage. Found by the clean-venv smoke test, which prints the banner a real installer sees.

### Fixed

- **A release gate blocked on our own study artifact.** `results/class_fragmentation_v1/replay.py`
  hardcoded a maintainer-specific transcript path, which tripped the denylist gate and made the replay
  unreproducible for anyone else. It now derives the path from the repo you are standing in, so the
  harness runs against *your* corpus.
- `docs/CLAIMS.md`'s organism test count refreshed 357 → **370** (the ledger nothing may exceed cannot
  itself be stale). Suites this release: **99** frozen kernel-lock · **370** organism · **49** battle ·
  **37** cerebral-substrate.

### Docs

- **A negative result kept, as usual: the classifier upgrade we expected to win, lost.** Replaying 37
  real transcripts through both classifiers cold, judged by *consequence* (do the prompts a class groups
  actually lead to the same downstream work?) rather than by eye: the **shipped lexical classifier is
  the best measured option**, the semantic variant is **falsified** as an upgrade — it cut class count by
  fusing 24 unrelated classes on conversational register — and the persistent-classifier daemon is
  **retired** with no prize behind it. Class fragmentation is not shown to be a defect.
  (`results/class_fragmentation_v1/`)
- **`docs/LANDSCAPE.md` gains "earned memory vs retrieved memory."** Graph-structured memory is a healthy
  and growing line of work, and the framing is right. The one axis we differ on: that memory is usually
  **retrieved from** and judged by a proxy; ours is **earned into**, and retrieval alone changes nothing.
  Same substrate, opposite discharge. We have not proven the earned version pays off — that is the A/B
  above, still parked at 0.

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
  +15pp gap ~~that widened on extension~~ [**corrected 2026-07-22 → "that stayed stable"; see
  Unreleased → Corrected**], **p = 0.0781 against a pre-registered gate of p ≤ 0.05, openly
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
