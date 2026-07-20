# BYO-model Exocortex testbed

Drive the Exocortex (the Claude Code hook control plane) with a **bring-your-own ollama model** on
**any repo**, and watch the colony converge on a **Grafana dashboard**. The point is to accrue the
*other half* of the evidence: organs 3A (endocrine) and 3D (eligibility trace) were sized only on
flagship Claude models (prize null-to-modest). Smaller/diverse models on diverse repos are where they
might earn their keep — or confirm they don't.

> **Sandbox-first.** Nothing here touches the live hook defaults (`.claude/settings.local.json`,
> `exocortex_config.json`). All artifacts are additive; the proven runners/hook are reused, not mutated.

## The central gotcha (read this first)

Segment data comes from Claude Code hook events (`PreToolUse`/`PostToolUse`), emitted **only by the
`claude` CLI**, which speaks the **Anthropic Messages API**. ollama's endpoint is **OpenAI-shaped**.
You therefore **cannot** point `ANTHROPIC_BASE_URL` straight at ollama — a translating proxy must sit
between them. **Route A** (what this testbed uses): [`claude-code-router`](https://github.com/musistudio/claude-code-router)
fronts ollama and presents the Anthropic API to `claude`, so the existing hooks + runners work unchanged.

A second, smaller gotcha (Slice 5): **open-webui chats ollama directly and emits zero hook events** —
it is an inspection/model-management tool, *not* a data source. Only the `claude` CLI loop (the proof
harness / repo-feeder) produces hook data.

---

## Slice 1 — prove a non-Claude model drives the hooks

### 1. Install the proxy
```bash
npm i -g @musistudio/claude-code-router
```

### 2. Configure it for ollama
Copy the example config into place and confirm your model is pulled:
```bash
cp exocortex/testbed/ccr/config.example.json ~/.claude-code-router/config.json   # %USERPROFILE% on Windows
ollama pull llama3.1:8b   # the verified tool-capable model (see "Three hard-won fixes" below)
```

### 3. Pick a model + context window (verified recipe)
Three things had to be right before a local model would actually fire the hooks — all verified on
ollama 0.30.11:

1. **Model must emit *native* `tool_calls`, not text.** `llama3.1:8b` does. `qwen2.5-coder:32b` and
   `mistral:7b` *advertise* the `tools` capability but emit tool calls as **text** (`<tools>{…}</tools>`)
   in this ollama → Claude Code never sees a `tool_use`, no `PreToolUse` fires. `llama3.2:3b` emits
   native calls for one tool in isolation but is too weak under the full harness.
2. **No `enhancetool` transformer.** It forces text-format tool calls and reparses them, which *breaks*
   native tool calling. The config ships `use: [openai, strip-thinking]` only.
3. **Shrink the prompt so a small/fast `num_ctx` fits.** Claude Code sends ~30 built-in tool defs
   (~26k tokens) — too big for a fast context window; an over-large `num_ctx` is too slow on modest HW
   (a 32k-ctx turn timed out). `proof_route_a.py` passes `--disallowedTools` to strip the ~24
   non-essentials → request drops to ~4k tokens, and an **8k-ctx** model is both fast and untruncated.

Bake the context window into a derived model (no re-download; doesn't restart your ollama):
```bash
printf 'FROM llama3.1:8b\nPARAMETER num_ctx 8192\n' > Modelfile && ollama create llama3.1-8b-8k -f Modelfile
```
(then set `Router.default` to `ollama,llama3.1-8b-8k`). Alternatively raise the server-wide default with
`OLLAMA_CONTEXT_LENGTH=8192` and restart ollama.

### 4. Start the router
```bash
ccr start            # serves the Anthropic API on http://127.0.0.1:3456
ccr status           # confirm it's up
```

### 5. Point `claude` at the proxy and run the proof
```bash
# PowerShell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:3456"
$env:ANTHROPIC_API_KEY  = "ollama-placeholder"   # claude requires a non-empty key; ccr ignores its value
python -m exocortex.testbed.proof_route_a --model llama3.1-8b-8k
```
**PASS** (verified) = the harness reports `PreToolUse` records — a local model just drove the six hooks
with real tool use. **FAIL** = no hook activity → check `ccr status`, the model (native tool_calls?),
that `enhancetool` is absent, and that `num_ctx` ≥ the (disallowed-shrunk) prompt size.

---

## Slices 2–5 (see the plan)
- **2 — exporter:** `python -m exocortex.testbed.exporter.metrics` → Prometheus text on `:9109/metrics`
  (works against existing audit data immediately). Now **multi-repo** — see below.
- **3 — observability:** `docker compose --project-directory exocortex/testbed/compose up -d` → Grafana on `:3000`.
- **4 — repo-feeder:** ✅ built — `python -m exocortex.testbed.feeder --episodes N` drives a disposable repo
  to accrue real vitals (the science check). See "Slice 4" below.
- **5 — open-webui (optional):** ollama inspection UI; **not** a hook data source (see gotcha above).

## Multi-repo observability + browser control plane

The stack is **three self-healing containers** — the metrics exporter is no longer a fragile native
process (it died on the host's first reboot). One `docker compose up -d` and it stays up.

```bash
docker compose --project-directory exocortex/testbed/compose up -d
#   Body:       http://localhost:9109/         — one silhouette per repo, organs colored by live vitals
#   Control:    http://localhost:9109/control  — tweak each repo's organs in the browser (anatomy-skinned)
#   Grafana:    http://localhost:3000          — lands on "SentAInce — The Organism" (the story skin)
#   Prometheus: http://localhost:9090
```

> **No Docker? Still get the body.** `sentaince body [repo-path]` (or plain
> `python -m exocortex.testbed.exporter.metrics --scan-root <projects-root>`) serves the same body page +
> `/api/vitals` on loopback with zero dependencies — the compose stack only adds Grafana/Prometheus/Loki
> history on top.

> **The `-f` trap.** Don't bring the stack up with `docker compose -f …/docker-compose.yml up -d`: an
> explicit `-f` loads *only* that file and **silently suppresses the auto-merge of a local
> `docker-compose.override.yml`** — the stack comes up missing your machine-local mounts, and any repo
> that depends on them reads all-zero (`exocortex_state_dir_present 0`). Run compose from the compose
> directory, or pass `--project-directory` as above, so both files are discovered. After editing the
> override, re-run `up -d` (which *recreates* changed containers) — a plain restart never re-reads
> compose files.

### Two dashboard skins (same live data)

Grafana provisions **two** dashboards from `grafana/dashboards/`:

- **`organism.json` — "SentAInce — The Organism"** *(the default home page)*: the **story skin**. One row
  per organ in human terms (🛡️ immune system, 🫀 stamina, 💪 muscle memory, 📖 the notebook, 😴 sleep,
  🔬 the lab, 📜 the medical record), each with a plain-language panel *and* its honest CLAIMS-backed stat.
  This is what a first-time visitor sees (`GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH`). See
  [`../../../docs/STORY.md`](../../../docs/STORY.md).
- **`exocortex.json` — "Exocortex testbed"** *(one click away in the dashboard list)*: the **technical
  instrument panel** — raw gauge verdict board, per-class convergence, the seg_len heatmap, live audit tail.
  This is what an operator tunes against.

The exporter's own pages are likewise skinned. The **body page** (`:9109/`) draws one SVG organism per
repo — organ regions colored by thresholded raw vitals with the rule printed beside every color
([`../../../docs/COLOR_DOCTRINE.md`](../../../docs/COLOR_DOCTRINE.md)); parked organs render gray, unfed
organs render as dashed outlines (nothing fakes green), and undeployed sibling git repos appear asleep with
a copy-paste deploy command. The **control plane** (`:9109/control`) groups knobs by their human counterpart
with a plain-language hint on each, edits the [estate file](../../../docs/ESTATE.md), and the 🛡️ immune
system (`integrity`/`somatic_gate`/audit chain) is shown 🔒 read-only — **never web-writable**.

**Keep it up across reboots** (one-time per host): `restart: unless-stopped` brings the containers back
*if* Docker is running, so register the logon task that also starts Docker Desktop + ensures the stack:
```powershell
pwsh -File exocortex/testbed/compose/autostart/install-autostart.ps1   # uninstall-autostart.ps1 to undo
```

**How repos are discovered.** The exporter mounts the projects root (your dev root, e.g. `~/projects`;
override `EXOCORTEX_PROJECTS_ROOT`) and **auto-scans** `<root>/*/.claude/exocortex` every scrape.
Deploy the organism into any repo under that root and it appears in Grafana's `$repo` dropdown within 15 s —
**no restart, no per-repo port, no Prometheus edit**. Every metric carries a `repo="<name>"` label.

- **The estate file** (`~/.exocortex/repos.json`, mounted read-only; contract in
  [`../../../docs/ESTATE.md`](../../../docs/ESTATE.md)) is the *override*: add a repo **outside** the scan
  root, or pin a custom display name. Auto-scan covers the common case; the estate file covers the rest.
  Re-read every scrape — edit and save (by hand or via the `/control` form), no restart.

  **A repo outside the scan root needs BOTH halves** — the registry *names* it, a mount *makes it
  readable*. Registering alone yields a repo whose every series is zero (`exocortex_state_dir_present 0`
  is the tell). Host paths never belong in the committed compose file, so the mount goes in a
  machine-local `docker-compose.override.yml` next to `docker-compose.yml` (gitignored; auto-merged when
  compose runs from that directory — see the `-f` trap above). Mount only what the exporter reads — the
  `.claude` state dir and the activation config, read-only:
  ```yaml
  # docker-compose.override.yml (machine-local, never committed)
  services:
    exporter:
      volumes:
        - "/path/to/MyRepo/.claude:/projects-ext/MyRepo/.claude:ro"
        - "/path/to/MyRepo/exocortex_config.json:/projects-ext/MyRepo/exocortex_config.json:ro"
  ```
  then register it **by its in-container path** in `~/.exocortex/repos.json`:
  ```json
  { "repos": [ { "name": "MyRepo", "root": "/projects-ext/MyRepo" } ] }
  ```
  Recreate the stack (`docker compose --project-directory exocortex/testbed/compose up -d`) and the repo's
  real vitals appear under `repo="MyRepo"` within one scrape.
- **History** is Prometheus's job, not Grafana's: the stack gives Prometheus a named volume + **1-year
  retention**, so the stream survives container recreation (`down -v` to wipe it).
- **One synthetic series stays global:** the offline attribution-precision gauge is repo-independent, so it
  is emitted **once without a `repo` label** — stamping a synthetic `1.0` onto a never-measured repo would be
  a false claim. A repo gets a *per-repo* precision only when it has a planted `attribution_gauge.json`.

**Tweak each repo from the browser** (`http://localhost:9109/`): a row per repo with its tunable organ
knobs (`declarative.mode/explore_budget`, `eligibility_trace.mode/gamma`, `endocrine.mode`, the
`thermodynamics.*` knobs). A change writes that repo's `exocortex_config.json` and takes effect on its next
hook invocation (the Genome re-reads the file per process).

> **The safety genome is never web-writable.** A server-side allowlist (`TUNABLE_SCHEMA` in
> `exporter/metrics.py`) is the *only* surface that can be written. `integrity.*`, `somatic_gate.*`, and
> `audit_chain` are shown 🔒 read-only and refused with `403` — a browser kill-switch on the immune system
> would be a self-inflicted hole. Writing the go-live config does **not** trip kernel-lock apoptosis (it is
> not in the frozen-DNA baseline).

**Native single-repo mode** still works for smoke/CI:
`python -m exocortex.testbed.exporter.metrics --state-dir <dir> --once`.

## Slice 4 — the repo-feeder (the fuel pump)

`feeder.py` drives a **disposable** repo through the six hooks for N episodes of scripted, tool-forcing
tasks (Write/Edit + a Bash verify each), so real vitals accrue — the fuel the dashboard charts.

```bash
# flagship baseline (8 episodes against a fresh disposable repo the exporter auto-discovers):
python -m exocortex.testbed.feeder --episodes 8
# BYO model via ccr (set ANTHROPIC_BASE_URL=http://127.0.0.1:3456 first):
python -m exocortex.testbed.feeder --episodes 8 --model llama3.1-8b-8k
# create + wire the repo only, no model calls (inspection / CI):
python -m exocortex.testbed.feeder --setup-only
```

**Safety:** the feeder runs a real agent that **edits files and commits**, so it only touches a repo it
created (marked `.exo_feeder`) unless you pass `--force`. The default target is a fresh `_feed_<label>`
under the projects root, so it shows up in Grafana's `$repo` dropdown automatically. Delete the dir to
remove it. *Verified end-to-end:* a 1-episode flagship run fired the hooks (3 PreToolUse, 1 verified
consequence → 1 deposit, seg_len 3) and the vitals appeared under `repo="_feed_…"`.

## Science check
The feeder summary prints the **`seg_len` ≥4 tail** vs the flagship baseline (haiku + sonnet: **median 2,
26% ≥4**). A materially fatter ≥4 tail on a smaller/diverse model is the first evidence that flipping
`eligibility_trace.mode = trace` (organ 3D) is worth it — the exact dormant-organ flip-trigger the Tuner
would later automate. That's the question this whole branch exists to answer.

## Declarative wiki (Ticket 1) — go-live & soak runbook

The declarative-wiki organ ships **dormant** (`exocortex/exocortex_config.json` → `declarative.mode=off`).
Going live is a **local, machine-specific activation** — never a committed default.

**1. Activate (local, gitignored).** Drop a repo-root `exocortex_config.json` (the hook finds it via
`CLAUDE_PROJECT_DIR` and deep-merges it over the verified DEFAULTS — every other organ stays put). It is
gitignored (`/exocortex_config.json`), so the shipped default stays dormant. **Delete the file to revert.**
```json
{ "declarative": { "mode": "live", "vault_path": "~/projects/SentAInce", "explore_budget": 5 } }
```
`min_overlap=2` (gauge-validated, `results/attribution_layer2/`) is inherited; `explore_budget>0` is required
to break the cold-start deadlock (a note can't earn τ until it's injected).

**2. Vault scale matters — `load_graph` runs on the hot path** (every prompt + every consequence stats the
vault and reads the digest cache). Keep it modest. Measured:

| vault | files | nodes | cached load | cache |
|---|---|---|---|---|
| full `research-vault` (private archive) | 6118 | **344,204** | **2.1 s/hook** ❌ | 206 MB |
| `research-vault/COMMONS` (subfolder) | 62 | 2,409 | 0.07 s | 3.1 MB |
| `research-vault/SEEDS` (subfolder) | 40 | 1,860 | 0.07 s | 1.1 MB |
| `SentAInce` repo docs | ~30 | 506 | 0.04 s | 0.4 MB |

Rule of thumb: stay in the **hundreds–low-thousands of nodes**. A 344k-node archive lags every keystroke.

**3. Bring up the containerized stack** (the exporter reads each repo's live `exocortex_config.json`
automatically — drop the file at the repo root and it is picked up; no `--config` flag needed):
```bash
docker compose --project-directory exocortex/testbed/compose up -d
```
The exporter auto-scans every repo under the mounted projects root and labels each series `repo="<name>"`.
(The old native single-repo `--config` invocation and the Windows `:9109` duplicate-bind gotcha are
obsolete — the container owns the port. For a quick CI smoke without Docker:
`python -m exocortex.testbed.exporter.metrics --state-dir .claude/exocortex --once`.)

**4. Watch Grafana** (`:3000` → "Exocortex testbed" → pick the repo in the `$repo` dropdown → Declarative-wiki row):
- **credit rate** — want a *strict trickle*, not a flood (τ earned only by a note→…→`exit 0` chain).
- **precision @ min_overlap=2** — must hold **1.0** (auto-computed in-process; the crown-jewel gauge).
- **injected totals** — high early is fine (the lexical intake fan); uncredited nodes starve below `0.05`.

**First-meal telemetry observed** (SentAInce-repo vault, live): 40 injected / 3 used → **credit rate ≈ 7.5%**
(a healthy trickle), precision 1.0 — wide-net injection, isolated consequence-sourced credit, no autoimmune
leak. Lock Ticket 1 once a real soak confirms the pattern holds and bloat starves.
