# Deploying the Organism into a Working Repo (runbook)

How to install the FreqOS/SentAInce hooks (somatic gate + colony + the integrity layer + hash-chained
audit) into any working repo, **non-invasively**. The model is **one code install** (this repo) driving
**many project deployments** — each project keeps its own gitignored runtime state. Worked example: the
hardened deploy into the private patent vault (`research-vault`, ≈10× SentAInce). See
[DEPLOYMENT.md](DEPLOYMENT.md) for the tiers
and [ADR-009](ADR.md) for why integrity is language-agnostic, not a compiled binary.

## One-command install / uninstall (recommended)

`exocortex/deploy.py` performs the five artifacts below idempotently and — critically — **reverses them
surgically**, so testing on a daily-driver repo is safe (uninstall is as simple as install):
```bash
# default posture (integrity OFF + audit chain, somatic observe, declarative off):
python -m exocortex.deploy install   <target>
# choose the host (default claude → .claude/settings.json; cursor → .cursor/hooks.json; both):
python -m exocortex.deploy install   <target> --provider cursor      # or: --provider both
# tune the posture / point the wiki at a tracked subtree:
python -m exocortex.deploy install   <target> --mode observe --declarative live --vault <target>/SUBDIR --ingest tracked
python -m exocortex.deploy status    <target>      # what's installed, modes, audit-record count
python -m exocortex.deploy uninstall <target>      # surgical revert; KEEPS accrued state data
python -m exocortex.deploy uninstall <target> --purge   # also delete .claude/exocortex/ (the data)
```
**Reversibility guarantees:** uninstall removes only hook entries that reference *this repo's* `hook.py`
(your `permissions` / MCP / foreign hooks survive), deletes only the activation `exocortex_config.json`, and
**keeps the accrued audit/colony data** unless `--purge`. **Non-invasive to git:** ignore rules go to
`.git/info/exclude` (local, never tracked) — your committed `.gitignore` is never touched — and are skipped
if already present. Install writes a one-time settings backup into the gitignored state dir. The manual
artifacts below document *what the tool does*; reach for them only to customize.

> **Upgrading an existing install:** re-run `python -m exocortex.deploy install <target>` (idempotent —
> it replaces only our hook entries). Required once after 2026-07-01 to pick up the `Bash|PowerShell`
> consequence matcher (D3) and the pinned-interpreter hook command.

## Pre-deploy gates (clear all before installing)
| Gate | How to check |
|---|---|
| Code repo local-only (and patent clock clean) | `git remote -v` → none; no public push |
| Frozen-DNA baseline current | `python -m exocortex.integrity --verify` → `ok=True` (**full checkout only** — a `pip install` has no `vendor/kernel/`, so this reports 56 missing by construction, not tampering) |
| Code repo working tree clean | `git status --short` empty |
| Target is a git repo | `<target>/.git` exists |
| No existing hooks to clobber | target `.claude/settings*.json` has no `hooks` key (else **merge**, don't overwrite) |
| Target `.gitignore` covers runtime state | else add it (artifact 1) |

## The five artifacts (all gitignored or marker-delimited / non-destructive)
**1. Append to `<target>/.gitignore`:**
```
# Exocortex organism runtime state (per-project) + local activation config — never committed
.claude/exocortex/
/exocortex_config.json
```

**2. `<target>/exocortex_config.json`** (gitignored; the genome finds it via `CLAUDE_PROJECT_DIR`). Default
posture — integrity **off** + audit chain ON; somatic **observe** initially (record, don't block — escalate
to `somatic`/`full` after a clean soak); declarative **off** unless the repo is small (the scale rule below):

> **Why integrity ships `off` (fixed 2026-07-16 — it used to ship `enforce`, and that was a bug).**
> The kernel-lock baseline covers `vendor/kernel/**`, which is **not in the PyPI wheel** (`pyproject`
> ships `sentaince`/`exocortex`/`cerebral` only). So 56 of the baseline's 66 entries are structurally
> absent for a `pip install`, `verify_kernel()` returns `ok=False`, and `enforce` fires the apoptosis —
> **`exit 1` on every SessionStart**, which is not caught by the fail-open. Confirmed in a clean venv:
> SessionStart `1 → 0` and memory only splices after the fix. **`enforce` is for a full checkout that
> actually carries `vendor/kernel/`** — opt in there with `--integrity enforce`. This restores the
> Genome's own default and its stated reason: *"Ships DORMANT so a stale baseline never bricks dev."*

```json
{
  "integrity": { "mode": "off", "audit_chain": true },
  "somatic_gate": { "mode": "observe" },
  "declarative": { "mode": "off" }
}
```

**3. Merge a `hooks` block into `<target>/.claude/settings.local.json`** (preserve existing keys). Generate
the canonical 6-event block with the proven generator instead of hand-writing it:
```python
from exocortex.runner import _settings; from pathlib import Path; import json
T = Path(r"<target>")
hooks = _settings(T/".claude"/"exocortex"/"audit.jsonl", T/".claude"/"exocortex", "observe")["hooks"]
d = json.loads((T/".claude"/"settings.local.json").read_text()); d["hooks"] = hooks
(T/".claude"/"settings.local.json").write_text(json.dumps(d, indent=2))
```
Each command calls **this repo's `hook.py` by absolute path** (it self-bootstraps its `sys.path`); state
writes to `<target>/.claude/exocortex/`. Integrity verifies **this repo's** frozen DNA wherever invoked.
**For Cursor**, `deploy --provider cursor` writes `.cursor/hooks.json` instead (via `runner._cursor_settings()`,
matcher `Shell`, `--provider cursor` baked onto each command); a full Cursor restart loads it. The provider
adapter (`exocortex/adapter.py`) normalizes Cursor's I/O — the handlers and the frozen kernel are unchanged.

**4. The agent bootstrap contract** — deploy also writes a short rules block telling the agent HOW to use
the earned memory (provider `claude` → a marker-delimited block in `<target>/AGENTS.md`, never clobbering
your content; provider `cursor` → `.cursor/rules/exocortex-bootstrap.mdc`, `alwaysApply`). Uninstall
removes exactly our block/file. Why it exists: cold semantic routing **abstains on novel phrasing by
design**, so an unbriefed agent concludes "the memory is empty." The contract closes that gap.

**5. The recall skill** (provider `claude`/`both`) — deploy installs
`<target>/.claude/skills/sentaince-recall/SKILL.md`, a model-invocable skill teaching the recall
workflow (`memory_status` → `recall_for_prompt(cls=…)` → `recall_notes`) and the law (earned
suggestion never authority; an abstention on a novel task is a correct answer; recall never writes).
The contract (artifact 4) states the law once per repo; the skill surfaces it *at task time* — two
independent host integrations observed models use the memory tools markedly better with a skill
present. Ownership is marker-based: a same-named skill you wrote yourself is never overwritten
(deploy warns and skips), and uninstall removes only our marked file, pruning the empty dirs.

## Bootstrap your agent (what the contract says — copy-paste if you skipped deploy)

```markdown
At the start of a task:
1. Call memory_status — see which goal-classes carry earned routes; [notes:N] marks classes
   with τ-credited notes.
2. If the task matches a known class, call recall_for_prompt(prompt, cls="<class>") — the
   deterministic positive path (skips classifier guesswork on cold phrasing).
3. Treat everything recalled as earned suggestion, never authority — verify in code before
   relying on it. On a novel task an empty recall is correct behavior (abstain), not a failure.
4. After verified success the hooks deposit automatically; MCP tools never write memory.
```

Two honest disclosures belong next to it: your gate **mode** (`somatic` refuses catalogued lethals;
`observe` records without blocking), and on Windows the PowerShell scope note (the veto vocabulary is
Bash-shaped — PowerShell commands are audited but not vetoed; see `exocortex/README.md` "Honest scope").

## Verify the deploy (before handing off / going live)
```bash
# the genome as the target hook will see it:
CLAUDE_PROJECT_DIR=<target> python -c "from exocortex.genome import load_genome; g=load_genome(); print(g['integrity']['mode'], g['somatic_gate']['mode'], g['declarative']['mode'])"
# runtime state is ignored in the target:
(cd <target> && git check-ignore .claude/exocortex/x exocortex_config.json)
# a clean SessionStart from target context (kernel intact → exit 0, audit begins chaining):
echo '{"session_id":"smoke"}' | CLAUDE_PROJECT_DIR=<target> python <repo>/exocortex/hook.py SessionStart --mode observe --audit <target>/.claude/exocortex/audit.jsonl --state <target>/.claude/exocortex
python -m exocortex.integrity --verify-audit <target>/.claude/exocortex/audit.jsonl   # chain intact
# APOPTOSIS DRILL: tamper a frozen file → the SessionStart above exits 1 + records an IntegrityViolation → restore.
```

## Wire it to the testbed dashboard (monitor + tweak)

Once deployed, surface the new repo on the Grafana dashboard and the browser control plane
(`exocortex/testbed/compose/`). The exporter labels every series `repo="<name>"` and discovers repos
**fresh on every scrape**, so registration is usually *nothing to do*.

**A. Target lives under the scan root** (your dev root, e.g. `~/projects` — i.e. `EXOCORTEX_PROJECTS_ROOT`):
the exporter **auto-scans** `<root>/*/.claude/exocortex` — the repo appears in Grafana's `$repo` dropdown
within ~15 s with **no restart, no edit**. Just make sure the stack is up:
```bash
docker compose -f exocortex/testbed/compose/docker-compose.yml up -d   # (autostart keeps it up across reboots)
```
Verify it registered:
```bash
curl -s http://localhost:9109/api/repos    # the target's name should be listed
```

**B. Target lives ELSEWHERE** (outside the scan root): the container can only see what is mounted, so two
moves are needed —
1. make the path visible: either point `EXOCORTEX_PROJECTS_ROOT` at a common parent that contains it, **or**
   add a bind-mount for it under `services.exporter.volumes` in `docker-compose.yml`; then `up -d` again.
2. add it to the **central registry** `~/.exocortex/repos.json` (mounted read-only; re-read every scrape, no
   restart) using the path **as the container sees it**:
   ```json
   { "repos": [ { "name": "MyRepo", "root": "/projects/MyRepo" } ] }
   ```

**Tweak from the browser** (`http://localhost:9109/`): this runbook ships the target with `declarative: off`
(the scale rule); for a small repo you can flip `declarative.mode → live` and tune the `thermodynamics.*` /
organ knobs per repo from the control page. The change writes the target's `exocortex_config.json` and takes
effect on its next hook. The **safety genome** (`integrity.*`, `somatic_gate.*`, `audit_chain`) is shown
🔒 read-only and is **never web-writable** — escalate `somatic_gate` to `somatic`/`full` by hand after a clean
soak (per artifact 2), not from the browser.

**Keep it running across reboots** (one-time, per host): register the logon task that ensures the stack —
```powershell
pwsh -File exocortex/testbed/compose/autostart/install-autostart.ps1   # uninstall-autostart.ps1 to undo
```

## `research-vault` — worked example (deployed + verified)
- Artifacts written: `.gitignore` (+ runtime ignores), `exocortex_config.json` (enforce / observe / off),
  `.claude/settings.local.json` (6-event hooks merged alongside its existing `permissions` / MCP keys).
- Verified: genome loads `enforce / observe / off`; runtime state gitignored; clean SessionStart → `exit 0`;
  audit chain intact; **apoptosis drill PASSED** — tampering a frozen file made the vault's SessionStart
  fail-closed (`exit 1`, an `IntegrityViolation` record chained into its audit), and restore returned it to
  healthy.
- Declarative left **off**: the full vault is 344k nodes / 2.1 s per hook — too big for the hot path (the
  scale rule).

## Caveats
- **Coupling:** with `enforce`, a target session **halts (apoptosis)** if this repo's *frozen* DNA drifts
  (`sentaince/organism/*` + `vendor/kernel/*`). The mutable layer (colony, wiki) is **not** in the baseline,
  so normal development won't halt the target. After any legitimate frozen change: `--update-baseline`.
- **Scale rule (declarative):** keep a wiki vault to hundreds–low-thousands of nodes; a whole large repo as a
  vault lags every hook. Point at a subfolder, leave declarative off, or set **`declarative.ingest:
  "tracked"`** (env: `EXOCORTEX_WIKI_INGEST=tracked`) so the organ digests only git-**tracked** `*.md` —
  this respects the vault's `.gitignore`, drops untracked/submodule junk, and reads the git index instead of
  walking the tree (on `research-vault`: 3,947 tracked vs 6,889 total `.md`, and ~4× faster discovery per hook).
  Committed default stays `"all"` (ADR-003); `"tracked"` falls open to `"all"` on a non-git vault.
- **Non-invasive + no exfil:** the hooks are local Python, write only to the gitignored state dir, and send
  nothing off-host. All MiniLM use — the wiki note-embeddings **and** the semantic cue-classifier — runs
  fully local; nothing leaves the host.
- **Classifier cold-start (hot path):** "MiniLM off" above scopes to the *wiki* embedder only. The
  **cue-classifier** still loads MiniLM on `UserPromptSubmit` whenever `epistemic_classifier.mode =
  "semantic"` (the genome default), independent of `declarative` — a cold first prompt can stall tens of
  seconds (torch + model load), enough to trip a host hook-timeout, which drops that turn's earned-memory
  recall injection (the `PreToolUse` somatic gate is unaffected). Keep MiniLM off the hot path with
  `epistemic_classifier.mode = "lexical"` (or `EXOCORTEX_EMBED=0`), or raise the generated hooks' `timeout`
  to keep `semantic`.

## Revert (instant)
`python -m exocortex.deploy uninstall <target>` (surgical; keeps accrued data — add `--purge` to drop it).
Manual equivalent: delete `<target>/exocortex_config.json` (→ dormant defaults) and remove the exocortex
hook entries from `<target>/.claude/settings.local.json`.
