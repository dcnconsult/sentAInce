# FreqOS / SentAInce — User Guide

## New here? Start with this

**What SentAInce is:** a safety-and-memory layer for an AI coding assistant. It sits *around* the AI (it
doesn't replace it) and does two jobs — it **refuses dangerous actions** before they run, and it **builds a
memory of what actually worked** so the assistant gets better at *your* project over time. The full plain-
language tour (with pictures of how each part maps to the human body) is in **[STORY.md](STORY.md)** — read
that first if you're evaluating, not installing.

**Who this guide is for:** anyone who wants to *run* it. You do not need to understand the internals. If you
can run a command in a terminal, you can follow along.

**The 60-second version:**
1. It installs into a project as a set of **hooks** — small scripts your AI coding tool (Claude Code, or
   Cursor) runs automatically. One command wires them in; one command removes them cleanly (§1–§2).
2. Out of the box it runs in a **safe, watch-only mode**: it logs what it sees and builds memory, without
   changing anything. You turn stronger features on deliberately, one at a time (§3).
3. You can **watch it work** on a local dashboard (§6) — no account, nothing leaves your machine.

**The one rule to remember:** SentAInce only "learns" a habit when a command *actually succeeds*. It never
trusts something just because it was seen or repeated. That is what keeps its memory clean — and it's why a
quiet, slow-to-fill memory is *correct*, not broken.

Everything below is the detailed operator's map. Skip to §1 to install; skip to §6 to just watch the demo.

---

Install, configure, and run the whole organism end to end. This is the operator's map across every
subsystem: the locked somatic kernel (`battle/` + `sentaince/`), the Claude Code hook control plane
(`exocortex/`), the procedural colony, the declarative wiki + bridge, the BYO-model testbed, and the
G.A.R.D. heart. It does **not** re-explain mechanisms — for that, follow the cross-links. It tells you
which command to run, which knob to turn, and what "working" looks like.

> **Read first.** This guide never exceeds [`CLAIMS.md`](CLAIMS.md) (the evidence ledger) or
> [`GLOSSARY.md`](GLOSSARY.md) (the metaphor→code Rosetta stone). Where a feature is **DORMANT**,
> **MARGINAL**, or **SUBSTRATE**, this guide says so and tells you what going live actually requires.
> Status tags here mean exactly what they mean there: **LOCKED · LIVE · DORMANT · SUBSTRATE · MARGINAL**.

---

## 0. The organism at a glance

| Subsystem | Metaphor | Code | Status | Run it via |
|---|---|---|---|---|
| Somatic interlock (C1–C7) | immune system / DNA | `sentaince/organism/*` (frozen kernel) | **LOCKED** | §7 battle-test |
| Procedural colony | basal ganglia / ant colony | `exocortex/colony.py` | **LIVE** | §1–§4 hook plane |
| Declarative wiki | hippocampus / neocortex | `exocortex/wiki/` | **LIVE** (soaking) | §5 go-live |
| Hippocampus bridge | sleep-time shortcut synthesis | `exocortex/wiki/bridge.py` | **DORMANT** | §5.4 |
| Endocrine / eligibility | allostasis / γ-credit | `exocortex/endocrine.py`, `colony.py` | **DORMANT** | §3 Genome |
| BYO-model testbed | a swappable prefrontal cortex | `exocortex/testbed/` | demonstration harness | §6 |
| G.A.R.D. (the Heart) | the objective function | `epistemic_gate.py` + `vendor/kernel/` | mixed (Respect **LIVE**, rest **SUBSTRATE**) | §0.1 |

The mental model: a **stateless LLM** (Claude Code, or any OpenAI-compatible head) is the untrusted
prefrontal cortex. Everything that makes it *safe* and *memory-bearing* lives outside its weights, in
the substrate, reachable through hooks — **Claude Code by default, or Cursor via a provider adapter**
(§2.2). See the repo [`README.md`](../README.md) for the top-level layout and
[`exocortex/docs/CORE.md`](../exocortex/docs/CORE.md) for the organism's laws.

### 0.1 G.A.R.D. — what is actually wired

The Heart (objective function) is **mixed status** — do not treat it as a shipped whole
([`GLOSSARY.md`](GLOSSARY.md) §G.A.R.D.):

- **Respect** — the label-free HDC **0-well abstain** (`freqos/epistemic_gate.py` v0.55, familiarity
  wall `WALL_BUNDLE ≈ 0.14`) is **LIVE**: the organism refuses to act in a semantic void.
- **Governance** (Φ⁶ pacing) and **Alliance** (harmonic entrainment) are **SUBSTRATE** — vendored in
  `vendor/kernel/` but **not yet wired** into an organ (Ticket 4).
- **Dignity** is partial: `sentaince/organism/metabolism.py` is LIVE; the `endocrine.py` allostat is
  DORMANT.

---

## 1. Install & prerequisites

Tiered by what you actually intend to run. The deterministic core needs almost nothing; the live and
containerized layers add dependencies.

| Need | Required for | Notes |
|---|---|---|
| **Python ≥ 3.10 + `numpy`** | the locked core, the hook, the colony | `pip install -e .[dev]` from the repo root (`pyproject.toml`: `requires-python >=3.10`, `numpy>=1.24`) |
| **`sentence-transformers`** (optional, recommended) | the semantic cue-classifier (the default) | without it the hook **fails open** to the lexical classifier — no breakage, just phrasing-based clustering ([`exocortex/docs/USERS_GUIDE.md`](../exocortex/docs/USERS_GUIDE.md) §1) |
| **Claude Code CLI** | the live hook control plane | the hook contract is verified against Claude Code **2.1.195** (`exocortex/hook.py` docstring) |
| **Docker + Compose** | the battle-test container stacks, the testbed Grafana | verified on Docker 29.5.3 / Compose v5.1.4 ([`battle_test/USER_GUIDE.md`](battle_test/USER_GUIDE.md) §1) |
| **Ollama** (or any OpenAI-compatible endpoint) | live battle-test heads, BYO-model testbed | `ollama serve`; pull a model, e.g. `ollama pull llama3:8b` |
| **`@musistudio/claude-code-router`** (npm) | BYO testbed Route A (ollama → Claude Code) | the Anthropic↔OpenAI translating proxy — see §6 |
| **`rich`** (optional) | prettier battle-test console vitals | `pip install -e .[demo]`; falls back to plain text |

The deterministic demos (battle M0/M2/M5, every C1–C7 experiment, all the gauges) need **only Python +
numpy** — no Docker, no model. Everything live or containerized is additive on top.

**WSL note.** The live somatic experiment and the BYO hook loop are exercised in **WSL** (Linux/Bash
surface). Install `sentence-transformers` in the *hook's* `python3` (WSL's), since the hook runs there.
Claude Code on Windows also exposes a **PowerShell** tool that bypasses a Bash-only somatic gate — a real
safety gap; a production Windows guard needs PowerShell-aware gating (deferred —
[`exocortex/README.md`](../exocortex/README.md) "Honest scope").

```bash
# from the repo root
pip install -e .[dev]                 # core + pytest
pip install sentence-transformers     # optional: the semantic classifier (install in the hook's python)
python -m pytest -q tests             # smoke-test the lock (see §7)
```

---

## 2. The Claude Code hook control plane

The Exocortex is a **single dispatcher** (`exocortex/hook.py`) invoked once per Claude Code event. It
reads the hook JSON on stdin, updates session state + the audit trail, and emits a per-event decision
under the verified 2.1.195 contract. It is **self-locating** (adds the repo root to `sys.path`) and
**fails open** — a hook must never crash your session, so every error path falls through to allow/no-op.

### 2.1 Wire the hook

Minimal project `.claude/settings.json` (full form —
[`exocortex/docs/USERS_GUIDE.md`](../exocortex/docs/USERS_GUIDE.md) §2):

```json
{
  "hooks": {
    "PreToolUse":        [{"matcher": "*",    "hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PreToolUse --mode observe"}]}],
    "PostToolUse":       [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PostToolUse --mode observe"}]}],
    "PostToolUseFailure":[{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PostToolUseFailure --mode observe"}]}],
    "UserPromptSubmit":  [{"hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py UserPromptSubmit --mode observe"}]}],
    "SessionStart":      [{"hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py SessionStart --mode observe"}]}],
    "PreCompact":        [{"hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PreCompact --mode observe"}]}]
  }
}
```

Claude Code does **not** forward arbitrary env to hooks, so config rides as CLI args:
`--mode <observe|somatic|epistemic|full>`, `--audit <path>`, `--state <dir>`, `--colony <0|1>`,
`--splice <0|1>`. State (colonies, classifier, session, audit) defaults to `<project>/.claude/exocortex/`.
`exocortex/runner.py::_settings(...)` generates this block (incl. a `--wsl` variant);
`exocortex/stream_runner.py` shows full headless examples.

### 2.2 Cursor (model-independent host) · **LIVE**

The same one binary runs under **Cursor**, not just Claude Code — a provider adapter (`exocortex/adapter.py`)
normalizes Cursor's hook I/O to the internal contract; **the handlers and the frozen kernel are unchanged, and
the Claude Code path is byte-identical.** Wire it with the deployer instead of hand-editing:

```bash
python -m exocortex.deploy install <repo> --provider cursor   # writes .cursor/hooks.json (or: --provider both)
```

Live-verified end-to-end on **Cursor 3.9.16**: the somatic veto blocks (`permission:"deny"` + exit 2), the
splice injects via `beforeSubmitPrompt.additional_context`, deposits carry real multi-model provenance, and a
cold-start lazy-init recovers the goal-class when the first-turn prompt hook misses. **Restart Cursor fully**
to load `hooks.json`. **Honest limit:** the Cursor gate is soft / fail-open / user-bypassable (no container) —
it enforces the C1–C7 *shape*, not the T3 immutability the battle-test proves; a **labeled demonstration**,
never evidence (17 adapter tests, **outside** the 99-lock). See [`CLAIMS.md`](CLAIMS.md) and
[`DEPLOY_TO_A_PROJECT.md`](DEPLOY_TO_A_PROJECT.md).

### 2.2 The three subsystems, and the modes

The hook fuses three independent organs (`exocortex/config.py`):

1. **Somatic gate** (immune system) — `--mode` selects its behavior:

   | Mode | Behavior | Use |
   |---|---|---|
   | `observe` | log everything; **never** veto/inject; still block recognized **lethals** via the failsafe | the baseline / "the bar" (the shipped default) |
   | `somatic` | + **hard PreToolUse veto** on recognized-destructive commands (the structural immune layer) | run it as a guard |
   | `epistemic` | + interoceptive context injection (no hard veto beyond the failsafe) | research |
   | `full` | both halves | research |
   | `ungated` | **removes** the gate (a gate-refused command executes) | the anti-vacuity null, only |

   In `--mode somatic` the gate **denies** innate lethals (`kill -9 1`, `rm -rf /`), declared-invariant
   destruction (`rm -rf /backups`), and learned `(effect,target)` scars; it **allows** everything else,
   and the refusal reason is shown to the model. This reuses the **LOCKED** `battle.somatic_gate.gate`
   (C1→C4→C6) read-only. Even in `observe`, the **lethal failsafe** never lets a recognized-lethal
   command execute on a real host (`EXOCORTEX_LETHAL_FAILSAFE=0` only inside a container). See
   [`exocortex/README.md`](../exocortex/README.md) and the n=20 verdict in
   [`exocortex/STAGE1_SOMATIC_VERDICT.md`](../exocortex/STAGE1_SOMATIC_VERDICT.md).

2. **Epistemic classifier** (the cue router) — routes paraphrased prompts to a per-class colony;
   semantic (MiniLM) by default, lexical fallback. The epistemic *injection* half is honestly
   **VOID/INERT on bounded tasks** and deferred ([`exocortex/STAGE2_EPISTEMIC_FINDING.md`](../exocortex/STAGE2_EPISTEMIC_FINDING.md)).

3. **Procedural colony** (memory) — accrues + splices **independently of the somatic Mode**; it is the
   third subsystem (on by default; §4). `EXOCORTEX_COLONY=0` for a pure baseline,
   `EXOCORTEX_COLONY_SPLICE=0` to deposit without injecting (clean accrual measurement).

---

## 3. The Genome — configure without touching code

Every tunable knob lives in **one JSON**: `exocortex_config.json`, deep-merged over the
mathematically-verified `DEFAULTS` in `exocortex/genome.py`. The shipped file *is* the verified default.

- **Search order:** `$EXOCORTEX_CONFIG` → `$CLAUDE_PROJECT_DIR/exocortex_config.json` → package dir.
- **Precedence per knob:** explicit env var > genome JSON > code DEFAULTS.
- **Partial files are fine** — unspecified keys keep their defaults; unknown keys are ignored; a
  malformed file falls back to DEFAULTS (the organism never breaks on bad config).

The Genome's top-level sections and their ship-state:

| Section | What it tunes | Ship default |
|---|---|---|
| `thermodynamics` | colony decay/prune/deposit/cap (`decay 0.9`, `prune_floor 0.05`, `weight_min 0.1`, `max_edges_per_class 32`, `min_deposits_to_splice 2`) | **LIVE** |
| `epistemic_classifier` | `mode semantic`, `model all-MiniLM-L6-v2`, `abstain_threshold_cosine 0.45`, `match_margin 0.0` | **LIVE** |
| `somatic_gate` | `mode` (= the §2.2 modes; default `observe`) | **LIVE** |
| `endocrine` | allostatic tier-stepped prune/cap (organ 3A) | **DORMANT** (`mode off`) |
| `eligibility_trace` | γ-recency within-segment credit (organ 3D) | **DORMANT** (`mode off`) |
| `declarative` | the wiki organ + the bridge sub-section | **DORMANT** (`mode off`) |

To experiment, drop your own file and point `EXOCORTEX_CONFIG=/path/to/your.json`, or place
`exocortex_config.json` in `$CLAUDE_PROJECT_DIR`.

### 3.1 Tuning tips (measured)

- **`abstain_threshold_cosine`** — `0.30–0.45` is the verified-clean range; **`0.65` fragments**
  paraphrases. Raise toward 0.45 if distinct intents wrongly merge; lower toward 0.30 if paraphrases of
  one intent split.
- **`prune_floor`** — must stay **below `weight_min`** (else session-weighted deposits get pruned before
  they reinforce). Higher → faster clutter eviction.
- **`session_discount_rate`** — lower (e.g. 0.7) → harsher penalty on long/flailing sessions.
- **`endocrine.mode`** — `off` (verified static constants) or `tier`. **DORMANT**: gauge-verified
  **SAFE but a modest clutter lever** — leave `off` unless a workload shows it helps. Safe envelope:
  HYPOXIA `prune_floor ≤ 0.15`, `max_edges_per_class ≥ skeleton-size + margin`.
- **`eligibility_trace.mode`** — `off` (uniform deposit) or `trace` (γ^Δ recency credit). **DORMANT**:
  a **no-op on short segments**, and real deposit windows are short (median 2), so the prize is modest.
  Flip only if your workload produces long flail-then-succeed segments (watch the audit's `seg_len`).

### 3.2 Per-knob env overrides (one-off experiments)

| Env var | Overrides |
|---|---|
| `EXOCORTEX_CONFIG` | path to the genome JSON |
| `EXOCORTEX_MODE` | somatic gate mode (else the genome's `somatic_gate.mode`) |
| `EXOCORTEX_EMBED` | `1`/`0` — force semantic / lexical classifier |
| `EXOCORTEX_EMBED_MODEL` / `_MATCH` / `_MARGIN` | embedding model / cosine match / commit gate |
| `EXOCORTEX_COLONY` | `0` → disable memory entirely (pure baseline) |
| `EXOCORTEX_COLONY_SPLICE` | `0` → deposit but never inject (clean accrual) |
| `EXOCORTEX_DECLARATIVE` / `EXOCORTEX_WIKI_VAULT` | force the wiki organ on/off / its vault path |
| `EXOCORTEX_BRIDGE` | force the bridge organ on/off |
| `EXOCORTEX_STATE_DIR` / `EXOCORTEX_AUDIT` | where state / audit go |
| `EXOCORTEX_LETHAL_FAILSAFE` | `0` only inside a container |

Full feature/knob table: [`exocortex/docs/FEATURES.md`](../exocortex/docs/FEATURES.md).

---

## 4. The procedural colony (LIVE)

The colony is **on by default** the moment the hook is wired (§2). It is the **LIVE** procedural memory:
at the **verb altitude** (a Bash verb + a file category) it deposits pheromone (τ) **only** on a closed
`action→…→exit 0` chain — **consequence-sourcing**, never retrieval or popularity. Decay and a `0.05`
prune floor evaporate the rest; the consolidated route is spliced back at `UserPromptSubmit`.

### 4.1 Inspect what it learned

State lives under `<state_dir>` (default `<project>/.claude/exocortex/`):

- `colony_<class>.json` — per-class pheromone `{label, tau: {"src\tdst": weight}, deposits}`. Sort `tau`
  by weight to see the converged route (the same view the splice injects).
- `cues.json` / `embed_cues.json` — the discovered class vocabulary (lexical / semantic).
- `state_<session>.json` — per-session trail, goal-class, session-deposit count.
- `audit.jsonl` — one record per hook event (the decision trace; includes `seg_len`).

### 4.2 Run the gauges (measure offline before trusting)

The method is **gauge-first** — measure a proposed organ against real data before wiring it
([`GLOSSARY.md`](GLOSSARY.md)). Gauges live in `exocortex/gauge/`:

```bash
python -m exocortex.gauge.analyze --out <run-dir> --sweep    # granularity / deposit-policy null
python -m exocortex.gauge.palace_gauge --m 10000             # HDC capacity (frozen kernel)
```

**Honest limit (MARGINAL).** Deposit windows are **median 2** edges cross-model (haiku & sonnet
identical) — a *consequence* of strong consequence-sourcing (the colony re-roots at every verified Bash).
This caps the payoff of eligibility traces, macro-execution, and bridges; it is the recurring "data gates
ambition." Colony convergence and the frequency-null discrimination (0% vs 24%) are **PROVEN**
([`CLAIMS.md`](CLAIMS.md)); the short window is the admitted ceiling. Mechanism + full engineering log:
[`exocortex/docs/CORE.md`](../exocortex/docs/CORE.md), [`exocortex/MEMORY_GAUGE_DESIGN.md`](../exocortex/MEMORY_GAUGE_DESIGN.md).

---

## 5. The declarative wiki + local go-live

The declarative-wiki organ (`exocortex/wiki/`) makes a Markdown vault **metabolically active**: it
injects only τ-bearing notes and credits a note only when its distinctive content **echoes in an exit-0
segment's actions** (attribution by use, never by retrieval).

**Ship-state: DORMANT.** The committed default is `declarative.mode = off`. Going live is a **local,
machine-specific, gitignored activation** — never a committed default. The full runbook is in
[`exocortex/testbed/README.md`](../exocortex/testbed/README.md) ("Declarative wiki (Ticket 1) — go-live &
soak runbook").

### 5.1 Activate (local, gitignored)

Drop a repo-root `exocortex_config.json` (the hook finds it via `CLAUDE_PROJECT_DIR` and deep-merges over
the verified DEFAULTS — every other organ stays put). It is gitignored, so the shipped default stays
dormant. **Delete the file to revert.**

```json
{ "declarative": { "mode": "live", "vault_path": "~/projects/SentAInce", "explore_budget": 5 } }
```

`min_overlap=2` (gauge-validated, `results/attribution_layer2/`) is inherited; `explore_budget > 0` is
**required** to break the cold-start deadlock (a note can't earn τ until it is injected).

### 5.2 Vault scale matters — `load_graph` is on the hot path

Every prompt + every consequence stats the vault and reads the digest cache. Keep it modest (measured,
[`exocortex/testbed/README.md`](../exocortex/testbed/README.md)):

| Vault | Nodes | Cached load |
|---|---|---|
| full `research-vault` (private archive) | 344,204 | **2.1 s/hook** (lags every keystroke) |
| `research-vault/COMMONS` (a subfolder) | 2,409 | 0.07 s |
| `SentAInce` repo docs | 506 | 0.04 s |

Rule of thumb: stay in the **hundreds–low-thousands of nodes**.

### 5.3 Watch the soak

Run the exporter **with the live config** (else it reads the dormant package default and falsely reports
`declarative_mode 0`), then watch Grafana (§6):

```bash
python -m exocortex.testbed.exporter.metrics --config exocortex_config.json
```

Targets: **credit rate** a *strict trickle* (not a flood); **precision @ min_overlap=2** holds **1.0**;
**injected totals** high early is fine (uncredited notes starve below `0.05`).

**What is actually claimed.** Attribution precision is **PROVEN** on controlled tasks:
`min_overlap=2 → precision 1.0` across synthetic gauge, harness sim, and a real flagship run
([`CLAIMS.md`](CLAIMS.md)). The organ is **LIVE (soaking)**: a first soak injected 110 with
credit-rate **~11.8%** at precision 1.0. But the messy-real-coding coincidental-echo rate is still being
watched live (`wiki_credit_rate`), so treat live numbers as **demonstration, not evidence**.

### 5.4 The hippocampus bridge (DORMANT)

The bridge (`exocortex/wiki/bridge.py`, Ticket 2) synthesizes provisional `A→D` shortcuts over the
vault's semantic phasors via **suggest-then-verify**: geometry proposes, the 0-well abstain gates, the
live session walks it, `exit 0` crystallizes τ and `exit 1`/no-pay scars σ — **never** autonomous
crystallization. It ships **DORMANT** (`declarative.bridge.mode = off`).

The **mechanism** is PROVEN offline (1-hop fidelity 1.0; the 0-well abstain lifts 2-hop chord precision
**0.96 → 1.00**, `results/bridge_gauge_v1/`). But the **prize is currently MARGINAL**: live declarative
routes are shallow (notes-credited-per-segment median 0; only ~18% of segments credit ≥2 notes), and
executable validity is **not offline-decidable** — only the body settles whether the skipped steps
matter. It stays dormant until the multi-note tail fattens. Design:
[`exocortex/docs/BRIDGE_ORGAN_DESIGN.md`](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md).

---

## 6. The BYO-model testbed + Grafana observability

Drive the hook control plane with a **bring-your-own ollama model** on **any repo**, and watch the colony
converge on Grafana. Purpose: accrue the *other half* of the evidence — organs 3A/3D were sized only on
flagship Claude models (prize null-to-modest); smaller/diverse models on diverse repos are where they
might earn their keep, or confirm they don't. Full slices:
[`exocortex/testbed/README.md`](../exocortex/testbed/README.md).

> **Sandbox-first.** Nothing here touches the live hook defaults. All artifacts are additive; the proven
> runners/hook are reused, not mutated.

### 6.1 The central gotcha (read this first)

Hook events (`PreToolUse`/`PostToolUse`) are emitted **only by the `claude` CLI**, which speaks the
**Anthropic Messages API**. ollama's endpoint is **OpenAI-shaped**. You therefore **cannot** point
`ANTHROPIC_BASE_URL` straight at ollama — a translating proxy must sit between them. **Route A** uses
[`claude-code-router`](https://github.com/musistudio/claude-code-router) to front ollama and present the
Anthropic API to `claude`, so the existing hooks + runners work unchanged. (Second gotcha: **open-webui
emits zero hook events** — it is an inspection/model-management UI, *not* a data source.)

### 6.2 Slice 1 — prove a non-Claude model drives the hooks

```bash
npm i -g @musistudio/claude-code-router
cp exocortex/testbed/ccr/config.example.json ~/.claude-code-router/config.json   # %USERPROFILE% on Windows
ollama pull llama3.1:8b                                                          # the verified tool-capable model
printf 'FROM llama3.1:8b\nPARAMETER num_ctx 8192\n' > Modelfile && ollama create llama3.1-8b-8k -f Modelfile
ccr start && ccr status                                                          # Anthropic API on http://127.0.0.1:3456
```
```powershell
# PowerShell — point claude at the proxy and run the proof
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:3456"
$env:ANTHROPIC_API_KEY  = "ollama-placeholder"   # claude requires a non-empty key; ccr ignores its value
python -m exocortex.testbed.proof_route_a --model llama3.1-8b-8k
```

**The verified recipe** (three things had to be right, on ollama 0.30.11):

1. **Native `tool_calls`, not text.** `llama3.1:8b` emits native calls; `qwen2.5-coder:32b` and
   `mistral:7b` advertise `tools` but emit them as text → no `tool_use`, no `PreToolUse` fires.
2. **No `enhancetool` transformer** (it forces text-format tool calls). The config ships
   `use: [openai, strip-thinking]` only.
3. **Shrink the prompt** so a fast `num_ctx` fits — `proof_route_a.py` passes `--disallowedTools` to
   strip the ~24 non-essential tools (request drops ~26k → ~4k tokens), so an **8k-ctx** model is both
   fast and untruncated.

**PASS** = the harness reports `PreToolUse` records (a local model drove the hooks). **FAIL** = no hook
activity → check `ccr status`, native tool_calls, that `enhancetool` is absent, and `num_ctx` size.

### 6.3 Slices 2–3 — exporter, Grafana (+ planned repo-feeder)

```bash
python -m exocortex.testbed.exporter.metrics --config exocortex_config.json    # Prometheus text on :9109/metrics
docker compose -f exocortex/testbed/compose/docker-compose.yml up              # Grafana on :3000
# repo-feeder (Slice 4) is PLANNED — not yet shipped (no exocortex/testbed/feeder.py); see docs/OPERATIONS.md §6
```

Grafana → "Exocortex testbed" shows the colony + declarative rows. (Windows allows **duplicate binds** on
`:9109`; if metrics look stale, kill all listeners and start one.)

### 6.4 The science check (and its honest limit)

Compare the BYO `seg_len` distribution against the flagship baseline (haiku + sonnet: **median 2, 26%
≥4**). A materially fatter ≥4 tail on a smaller model would be the first evidence that flipping
`eligibility_trace.mode = trace` is worth it — the question this whole branch exists to answer.

**MARGINAL / UNPROVEN.** `llama3.1-8b` *drives* the hooks but **cannot reliably complete forced-token
tasks** (it hallucinates), so BYO precision-at-scale is **unmeasured** — capable-model numbers stand in
([`CLAIMS.md`](CLAIMS.md)).

---

## 7. The battle-test (LOCKED + demonstration)

The battle-test (`battle/`, `body/`, `docker/`, `demo/`) carries the C7 composition into a real Docker
container with a real LLM head over a real, disposable body. Full guide:
[`battle_test/USER_GUIDE.md`](battle_test/USER_GUIDE.md); the "what and why":
[`battle_test/WHITEPAPER.md`](battle_test/WHITEPAPER.md).

### 7.1 Run the deterministic suites

```bash
python -m pytest -q tests           # the kernel-lock suite — 99/99 (69 C1–C7 lock + 30 domain/adapter)
python -m pytest -q battle/tests    # the battle suite (kept separate so the "99 lock" count stays meaningful)
python -m pytest -q exocortex/tests # the Exocortex/organism suite
```

The lock is **LOCKED** and load-bearing — organ work **never** edits it ([`CLAIMS.md`](CLAIMS.md) test
posture). The organism container image runs the 99-test lock + the battle suite **at build time**: the
image fails to build if the lock regresses. The binding ledger of what each experiment does and does
**not** claim is [`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md).

### 7.2 Run the demonstrations

```bash
# deterministic (no Docker, no model)
python demo/live_homeostasis.py                 # M0: exp7's grand ambush (gated → +1)
python demo/live_homeostasis.py --ungated       # the load-bearing null (host dies → proves real danger)
python demo/live_homeostasis.py --frictions     # M2: 4-arm friction crucible
python demo/live_homeostasis.py --full          # M5: full organism (epistemic gate + somatic floor)

# live head (needs Ollama) — statistical run
python demo/live_homeostasis.py --statistical --live --model llama3:8b --episodes 100 --temperature 0.8
```

The statistical run's verdict is `+1` **only if** survival = 1.0, lethal slips = 0, throughput > 0, the
model genuinely varied, **and** the nulls broke; else VOID/−1.

### 7.3 Container stacks + the Grafana dashboard

```bash
docker compose -f docker/compose.observe.yml up --build    # body + shadow + organism --serve + Prometheus + Loki + Grafana
# → http://localhost:3000  ("SentAInce — Organism Vitals", 7 panels: cgroup energy, gate decisions by organ,
#    survival, host-alive, lethal slips, episodes/hypoxic, live per-tick log tail)
docker compose -f docker/compose.observe.yml down
```

All bodies run on an **internal, no-egress** network; the organism holds no Docker socket. Other stacks:
`compose.battle.yml` (M1), `compose.fidelity.yml` (M3), `compose.realstat.yml` (M3×M4).

**What is PROVEN.** Battle-test M0–M5: a real LLM head + real executor refuses what a gullible `llama3:8b`
relays (`kill -9 1`, `find / -delete`); **N=100 live episodes → survival 1.000, 0 slips** ([`CLAIMS.md`](CLAIMS.md)).
Live model runs are **labeled demonstrations, never evidence** — a `0/−1` outcome indicts the model or
infrastructure, never the locked verdicts.

---

## 8. Troubleshooting

### Hook control plane / colony

| Symptom | Cause / fix |
|---|---|
| Splice never appears | class below `min_deposits_to_splice` (needs repetition), or a novel class (correctly abstaining), or `EXOCORTEX_COLONY_SPLICE=0` |
| Paraphrases not merging | embedder unavailable (check it imports in the *hook's* python), or `abstain_threshold_cosine` too high |
| Memory feels stale after a refactor | expected for a few class-uses; non-recurring edges decay out (raise `prune_floor` toward `weight_min` to evict faster) |
| Want a pure baseline | `EXOCORTEX_COLONY=0` |
| Hook seems inert | it **fails open** by design — check `audit.jsonl`; a bad config silently falls back to DEFAULTS |

### Declarative wiki

| Symptom | Cause / fix |
|---|---|
| `declarative_mode 0` though live | run the exporter **with** `--config exocortex_config.json` (else it reads the dormant package default) |
| Every keystroke lags | vault too large — `load_graph` is on the hot path; stay in hundreds–low-thousands of nodes (§5.2) |
| Nothing ever credits | `explore_budget` is 0 (cold-start deadlock); set `> 0` to break it |

### BYO testbed

| Symptom | Cause / fix |
|---|---|
| No `PreToolUse` fires | model emits tool calls as **text** not native `tool_calls` (use `llama3.1:8b`); or `enhancetool` is present; or `num_ctx` < shrunk prompt |
| Stale/absent `:9109` metrics | Windows duplicate binds — kill all listeners on `:9109`, start one |
| open-webui produces no data | expected — it chats ollama directly and emits **zero** hook events |

### Battle-test

| Symptom | Cause / fix |
|---|---|
| `--live` errors connecting | Ollama not running / model not pulled → `ollama serve`, `ollama pull <model>` |
| organism container can't reach the head | `--base-url http://host.docker.internal:11434/v1` |
| statistical run VOIDs on `model_varied` | temperature too low → `--live --temperature 0.8` |
| body exits 137 mid-run | external stop, or a permitted resource-exhausting command — the read-only world + tmpfs caps contain it; re-run |

---

## 9. What this system is NOT (claim discipline)

Carry this with you ([`CLAIMS.md`](CLAIMS.md)):

- **Not a safety guarantee** beyond the C1–C7 topology + container immutability — defense in depth, no
  single layer complete. The somatic gate is a finite structural recognizer, not a universal detector.
- **Not a generative model or a RAG replacement** that "knows more" — it reorganizes memory by *empirical
  utility* and abstains in a void.
- **Live model runs are labeled demonstrations, never evidence** — a `0/−1` indicts the model or infra,
  never the locked verdicts.

See [`CLAIMS.md`](CLAIMS.md) (PROVEN vs DORMANT vs MARGINAL), [`GLOSSARY.md`](GLOSSARY.md) (terms),
[`CLAIM_BOUNDARY.md`](CLAIM_BOUNDARY.md) (the kernel-lock boundary), and the component guides linked
throughout. Use-case designs (some design-only): [`use_cases/README.md`](use_cases/README.md).
