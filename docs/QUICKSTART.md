# Quickstart — five minutes to a safer agent

This is the shortest honest path from `pip install` to an agent with a safety reflex and an earned
memory. Works with **Claude Code** and **Cursor**, on the project of your choice. Nothing here needs an
account, sends telemetry, or phones home — the organism is 100% local, always.

## 1. Install

```bash
pip install sentaince
python -m exocortex.deploy install /path/to/your/project
```

For Cursor (or both hosts at once): add `--provider cursor` or `--provider both`.

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

Two honest notes: on Windows, PowerShell commands are audited but not vetoed (the veto vocabulary is
Bash-shaped today — it's in the README's honest scope, not hidden in a footnote). And a brand-new
install has an empty memory — the first sessions are for *earning*, not recalling. Cold-start silence
is correct behavior, not a bug.

## 3. Opt in to the safety veto (when you're ready)

Watch-only is the default because trust should be earned in both directions. When you want the immune
system active, set it in your project's `exocortex_config.json`:

```json
{ "somatic_gate": { "mode": "somatic" } }
```

From then on, catalogued lethal command classes are refused *before they run* — even if the model was
prompt-injected into proposing them. The gate rests on topology, not on the model's judgment. Every
hook stays fail-open on errors and timeouts: the organism never wedges your session.

## 4. See it (optional)

The local dashboard stack (Docker) shows the organism's vitals in plain language:

```bash
cd exocortex/testbed/compose && docker compose up -d --build   # then open http://localhost:3000
```

## 5. Leave cleanly (any time)

```bash
python -m exocortex.deploy uninstall /path/to/your/project          # keeps your accrued memory
python -m exocortex.deploy uninstall /path/to/your/project --purge  # removes everything
```

Uninstall is surgical: it removes only the organism's own hook entries and files, never yours.

---

**Next steps:** the plain-language tour is [`STORY.md`](STORY.md) · the operator's runbook is
[`DEPLOY_TO_A_PROJECT.md`](DEPLOY_TO_A_PROJECT.md) · what we do and don't claim is
[`CLAIMS.md`](CLAIMS.md) — the binding ledger nothing in this project may exceed.
