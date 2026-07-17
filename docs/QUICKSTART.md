# Quickstart — five minutes to a safer agent

This is the shortest honest path from `pip install` to an agent with a safety reflex and an earned
memory. Works with **Claude Code** and **Cursor**, on the project of your choice. Nothing here needs an
account, sends telemetry, or phones home — the organism is 100% local, always.

## 1. Install

```bash
pip install sentaince
sentaince-deploy install /path/to/your/project
```

(`sentaince-deploy` is the friendly name; `python -m exocortex.deploy install ...` does exactly the same
thing if you prefer the explicit form.) For Cursor (or both hosts at once): add `--provider cursor` or
`--provider both`.

What this actually does — three small artifacts, all reversible:

| Artifact | What it is |
|---|---|
| `.claude/settings.local.json` | the six hooks that let the organism observe your agent's sessions |
| `exocortex_config.json` | the activation file (gitignored; delete it and the organism reverts to dormant defaults) |
| `.claude/exocortex/` | the gitignored state dir where the audit trail and earned memory accrue |

Your repo's committed files are not touched — ignore rules go into `.git/info/exclude`, which never
ships. Verify any time:

```bash
python -m exocortex.deploy status /path/to/your/project
```

## 2. Use your agent normally

That's the whole workflow. The organism ships **watch-only** (`observe` mode): it audits and remembers,
and changes nothing about your agent's behavior. In your first sessions:

- Every tool call and its outcome lands in the hash-chained audit trail
  (`.claude/exocortex/audit.jsonl`).
- When a task **verifiably succeeds** (a command exits 0), the route that led there earns a deposit in
  the colony — the muscle memory. Reading, retrying, or repeating earns nothing; only verified success
  writes memory. That one law is why the memory doesn't rot.
- After a few successful tasks of the same kind, you'll start seeing a small **earned-memory block**
  injected at the top of your prompts — the converged route for *that kind of task*, with its trust
  weights. It's advisory context for the agent, never a command.

Two honest notes, in plain terms:
- **A brand-new install remembers nothing** — the first sessions are for *earning*, not recalling. An
  empty memory on day one is correct behavior, not a bug (and the body page in step 4 shows it honestly,
  as outlines rather than green).
- **On Windows, PowerShell commands are watched but not yet blocked.** The safety veto's list of
  dangerous commands is written in the Bash shell's dialect today; PowerShell-aware blocking is on the
  way. Nothing is hidden — this is called out in the README's "honest scope" too.

## 3. Opt in to the safety veto (when you're ready)

Watch-only is the default because trust should be earned in both directions. When you want the immune
system active, set it in your project's `exocortex_config.json`:

```json
{ "somatic_gate": { "mode": "somatic" } }
```

From then on, catalogued lethal command classes are refused *before they run* — even if the model was
prompt-injected into proposing them. The gate rests on topology, not on the model's judgment. Every
hook stays fail-open on errors and timeouts: the organism never wedges your session.

## 4. Look at it — the body page

This is the fun part, and it needs no Docker:

```bash
sentaince body /path/to/your/project
```

Your browser opens on **the body page**: your repo drawn as a human silhouette, with each organ colored
by a live vital and the exact rule printed beside it.

![The body page — one silhouette per repo, organs colored by live vitals with the rule beside each color](assets/body-page.png)

- 🫀 the **heart** is stamina, 💪 the **arms** are muscle memory (earned habits), 🛡️ the **chest** is the
  immune system, 😴 the **head** is sleep, 📖 the **book** is the notebook.
- **Green** means a stated rule over a stated number — never a guess. **Gray** organs are switched off on
  purpose. **Dashed outlines** mean "no data yet" — so a fresh repo is mostly outlines, and **nothing
  ever fakes green**.
- Click **"why?"** under any repo to see the organism *show its work* — the exact steps behind its latest
  earned habits, and its tamper-proof record, re-checked in front of you. (Same thing from the terminal:
  `sentaince why /path/to/your/project`.)

Watching several repos? One file lists them all — see [`ESTATE.md`](ESTATE.md). Want trends over time
and the full history board? Bring up the Docker stack:

```bash
cd exocortex/testbed/compose && docker compose up -d --build   # then open http://localhost:3000
```

## 5. Leave cleanly (any time)

```bash
sentaince-deploy uninstall /path/to/your/project          # keeps your accrued memory
sentaince-deploy uninstall /path/to/your/project --purge  # removes everything
```

Uninstall is surgical: it removes only the organism's own hook entries and files, never yours.

---

**Next steps:** the plain-language tour is [`STORY.md`](STORY.md) · the operator's runbook is
[`DEPLOY_TO_A_PROJECT.md`](DEPLOY_TO_A_PROJECT.md) · what we do and don't claim is
[`CLAIMS.md`](CLAIMS.md) — the binding ledger nothing in this project may exceed.
