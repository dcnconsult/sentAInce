# FreqOS / SentAInce — Operations Runbook

How to **deploy, configure, soak, monitor, and revert** the organism. Audience: operators. Scope: the whole
body — the somatic lock (`battle/`, `sentaince/organism/`), the procedural colony + declarative wiki + bridge
(`exocortex/`), and the BYO-model observability testbed (`exocortex/testbed/`).

This runbook does not re-derive mechanism — see [CORE.md](../exocortex/docs/CORE.md) for the architecture and
[USERS_GUIDE.md](../exocortex/docs/USERS_GUIDE.md) for the engineer's tuning detail. It does not assert
capability — [CLAIMS.md](CLAIMS.md) is ground truth and this document never exceeds it. Terms: [GLOSSARY.md](GLOSSARY.md).

## 0. Operating principles (read before touching anything)

- **Fail open.** A hook must never crash the agent; every error path falls through to allow / no-op / lexical
  fallback ([CORE.md](../exocortex/docs/CORE.md) law 3). The cost: failures are *silent* — the only way to know
  the organism is alive is that `audit.jsonl` grows (§1.4).
- **Ship dormant.** Every organ beyond the locked somatic floor and the live procedural colony defaults **OFF**
  in the Genome and is flipped on only after gauging (endocrine, eligibility, declarative, bridge — all
  `mode: off` in [`exocortex_config.json`](../exocortex/exocortex_config.json)). The committed defaults are the
  verified baseline; do not edit them in place — override locally (§3, §4).
- **Sandbox-first testbed.** Nothing in `exocortex/testbed/` touches the live hook defaults; all artifacts are
  additive ([testbed/README.md](../exocortex/testbed/README.md)).
- **Consequence-sourcing is slow on purpose.** Memory is earned only by a closed `action → … → exit 0` chain,
  never by retrieval or frequency. Expect a *trickle*, not a flood; a quiet colony on novel work is correct
  behaviour, not a fault.

## 1. Install the hooks

### 1.1 Requirements
- Python 3 with `numpy` (the somatic gate uses it).
- Optional but recommended: `sentence-transformers` for the semantic classifier (the default). Without it the
  hook fails open to the lexical TF classifier — no breakage, just phrasing-based clustering. On WSL, install
  in the same `python3` the hook runs in ([USERS_GUIDE.md](../exocortex/docs/USERS_GUIDE.md) §1).

### 1.2 Wire the dispatcher
The Exocortex is a single synchronous program (`exocortex/hook.py`) invoked once per event — **no daemon, each
event is a fresh process** ([CORE.md](../exocortex/docs/CORE.md)). Six events are wired in project
`.claude/settings.json` (or `settings.local.json`): `PreToolUse` (matcher `*`), `PostToolUse` /
`PostToolUseFailure` (matcher `Bash`), `UserPromptSubmit`, `SessionStart`, `PreCompact`. The canonical minimal
block (with the `python3` / WSL variant) is [USERS_GUIDE.md](../exocortex/docs/USERS_GUIDE.md) §2; the live
Windows wiring in this repo (`.claude/settings.local.json`) shows the concrete form, e.g.:

```json
"PostToolUse": [{ "matcher": "Bash", "hooks": [{ "type": "command",
  "command": "python C:/.../exocortex/hook.py PostToolUse --mode observe --audit C:/.../.claude/exocortex/audit.jsonl --state C:/.../.claude/exocortex" }]}]
```

CLI args baked into each command (Claude Code does not forward arbitrary env to hooks):
`--mode <observe|somatic|epistemic|full>`, `--audit <path>`, `--state <dir>`. State (colonies, classifier,
session, audit) defaults to `<project>/.claude/exocortex/`.

### 1.3 Somatic mode on install
The shipped default is `--mode observe` — the gate *logs* decisions while the colony/epistemic layers run.
The hard model-independent veto (the immune-system C1–C7 interlock) engages in `somatic` / `full`. The veto's
proof of refusal-under-fire is the battle-test (N=100 live episodes, survival 1.000, 0 slips) — see
[battle_test/WHITEPAPER.md](battle_test/WHITEPAPER.md). The somatic class is **LOCKED**; the gate's mode only
selects whether the live local hook *enforces* or merely *observes*.

### 1.4 Verify the install
Run any Bash tool call in a Claude Code session, then confirm `<project>/.claude/exocortex/audit.jsonl` gained
records. After repeated work in one goal-class, `colony_<class>.json` appears. To inspect what was learned, sort
a colony's `tau` by weight — the dominant edges are exactly what the splice injects
([USERS_GUIDE.md](../exocortex/docs/USERS_GUIDE.md) §5).

## 2. Genome config reference (every knob, default, meaning)

All knobs live in one JSON, [`exocortex_config.json`](../exocortex/exocortex_config.json), deep-merged over the
mathematically-verified `DEFAULTS` in [`genome.py`](../exocortex/genome.py). **Precedence per knob: env var >
genome JSON > code DEFAULTS.** Search order: `$EXOCORTEX_CONFIG` → `$CLAUDE_PROJECT_DIR/exocortex_config.json` →
package dir. The merge accepts **known keys only** (typos / unknown knobs are ignored), and a malformed file
falls back to DEFAULTS — the organism cannot be broken by a bad config.

### `thermodynamics` — the colony (LIVE)
| Knob | Default | Meaning |
|---|---|---|
| `decay` | `0.9` | τ multiplier applied on every deposit AND on each PreCompact consolidation (stigmergic evaporation — consolidation decays deposit-free; the store's `consolidations`/`last_consolidated` stamp attributes it). |
| `prune_floor` | `0.05` | eviction floor; **must stay below `weight_min`** or weighted deposits get pruned before reinforcement. Higher → faster clutter eviction. |
| `deposit_base_weight` | `1.0` | full-weight pheromone for a focused deposit. |
| `session_discount_rate` | `0.8` | per-deposit activity discount (`0.8**k`); the thrash catcher. Lower (e.g. 0.7) → harsher penalty on flailing sessions. |
| `weight_min` | `0.1` | floor on a session-weighted deposit. |
| `max_edges_per_class` | `32` | per-class leanness CAP (consolidation). |
| `min_deposits_to_splice` | `2` | abstain from splicing a class until it has repetition. |

### `epistemic_classifier` — the cue router (LIVE)
| Knob | Default | Meaning |
|---|---|---|
| `mode` | `"semantic"` | `semantic` (MiniLM embedding) \| `lexical` (TF). |
| `model` | `"all-MiniLM-L6-v2"` | the sentence-transformers embedding model. |
| `abstain_threshold_cosine` | `0.45` | novelty-abstain cosine. Measured: **0.30–0.45 verified-clean; 0.65 fragments** paraphrases. Raise toward 0.45 if distinct intents merge; lower toward 0.30 if one intent splits. |
| `match_margin` | `0.0` | top1−top2 commit gate (0 = off). |

### `somatic_gate` (LOCKED class; mode selects enforcement)
| Knob | Default | Meaning |
|---|---|---|
| `mode` | `"observe"` | `observe` \| `somatic` \| `epistemic` \| `full` \| `ungated` (alias `enforce`→`somatic`, `off`→`observe`). |

### `endocrine` — organ 3A, **DORMANT**
| Knob | Default | Meaning |
|---|---|---|
| `mode` | `"off"` | `off` = static `thermodynamics` constants (verified baseline) \| `tier` = allostatic prune/cap off the metabolic tier. |
| `tiers.SATED` | `{prune_floor 0.03, max_edges 40}` | dream — keep exploration. |
| `tiers.STARVING` | `{0.05, 32}` | = the static baseline. |
| `tiers.HYPOXIA` | `{0.12, 16}` | tunnel-vision — shed exploration, stay lean. |

Status: gauge-verified **SAFE** but a **modest** clutter lever ([CLAIMS.md](CLAIMS.md) DORMANT). Safe envelope:
HYPOXIA `prune_floor` ≤ 0.15, `max_edges_per_class` ≥ skeleton-size + margin.

### `eligibility_trace` — organ 3D, **DORMANT**
| Knob | Default | Meaning |
|---|---|---|
| `mode` | `"off"` | `off` = uniform deposit (verified status quo) \| `trace` = γ^Δ recency credit within a segment. |
| `gamma` | `0.80` | credit ∝ `γ^(steps-before-exit-0)`. |

Status: math proven (isolates the "ah-ha", evaporates the flail prefix) but a **no-op on short segments**, and
deposit windows are structurally short (cross-model **median 2**, ~26% ≥4) because the trail re-roots at every
verified Bash — so the prize is modest ([CLAIMS.md](CLAIMS.md)). Watch the live `seg_len` tail (§5) before
flipping.

### `declarative` — the wiki organ (Ticket 1), **DORMANT** by committed default
| Knob | Default | Meaning |
|---|---|---|
| `mode` | `"off"` | `off` \| `live` (touches the wiki only when `live` **and** `vault_path` set). |
| `vault_path` | `""` | path to the Markdown vault (empty → dormant even if `mode=live`). |
| `explore_budget` | `0` | sub-floor exploratory exons per splice; `>0` breaks the cold-start deadlock (a note can't earn τ until injected). |
| `max_exons` | `20` | splice injection ceiling. |
| `proposer_k` | `24` | candidate cap before τ/σ filtering. |
| `link_hops` | `1` | structural spreading-activation depth. |
| `attribution.min_overlap` | `2` | distinct salient tokens that must echo in an `exit 0` action to credit a note. Gauge: `=1` precision 0.79 (coincidental echo) → `=2` **precision 1.0**, recall 0.45. |
| `attribution.prose_echo` | `false` | dormant claim-grounded credit tier. |
| `bridge.*` | `mode "off"` | hippocampus bridge (Ticket 2), **DORMANT** + **MARGINAL** prize. `top_k 4`, `abstain_conf 0.14` (0-well familiarity wall), `abstain_margin 0.03`, `max_provisional 32`, `offer_cap 2`, `scar_after_k_walks 3`. See [BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md). |

### Per-knob env overrides (one-off experiments)
`EXOCORTEX_CONFIG` (genome path), `EXOCORTEX_EMBED` (1/0 force semantic/lexical), `EXOCORTEX_EMBED_MODEL`,
`EXOCORTEX_EMBED_MATCH`, `EXOCORTEX_EMBED_MARGIN`, `EXOCORTEX_COLONY` (`0` → disable memory entirely),
`EXOCORTEX_COLONY_SPLICE` (`0` → deposit but never inject), `EXOCORTEX_MODE`, `EXOCORTEX_STATE_DIR` /
`EXOCORTEX_AUDIT`, `EXOCORTEX_DECLARATIVE` / `EXOCORTEX_WIKI_VAULT` (full table: [USERS_GUIDE.md](../exocortex/docs/USERS_GUIDE.md) §4).

## 3. Enabling an organ (dormant → live)

The discipline is explicit and gated: **gauge offline → wire dormant → size the prize on a real accrual → flip
only if the bar is cleared** ([CORE.md](../exocortex/docs/CORE.md)). Each organ is a strict no-op until its flag
is set, so flipping is reversible and the baseline is preserved.

- **Endocrine** — set `endocrine.mode: "tier"`. Leave `off` unless a workload shows the static `decay` is
  insufficient; the gauge says the gain is modest.
- **Eligibility trace** — set `eligibility_trace.mode: "trace"`. Justified only if your workload produces long
  flail-then-succeed segments (a materially fatter `exocortex_seg_len` ≥4 tail vs the median-2 baseline — §5).
- **Bridge** — set `declarative.bridge.mode: "suggest"`. **Keep dormant**: the live soak shows the multi-note
  routes the bridge needs are real but small, so the prize is currently MARGINAL ([CLAIMS.md](CLAIMS.md)).

Do these via a **local** override, not by editing the committed Genome — either `EXOCORTEX_CONFIG=/path/your.json`
or the repo-root drop-in below.

## 4. Declarative wiki go-live + one-command revert

Going live is a **local, machine-specific activation — never a committed default** ([testbed/README.md](../exocortex/testbed/README.md)).

**Activate.** Drop a repo-root `exocortex_config.json`. The hook finds it via `$CLAUDE_PROJECT_DIR` and
deep-merges it over the verified DEFAULTS — every other organ stays put. It is gitignored (`/exocortex_config.json`),
so the shipped default stays dormant:

```json
{ "declarative": { "mode": "live", "vault_path": "~/projects/SentAInce", "explore_budget": 5 } }
```

`min_overlap=2` (gauge-validated) is inherited; `explore_budget > 0` is required to break the cold-start
deadlock.

**Revert (one command).** Delete the file:
```bash
rm exocortex_config.json
```
The committed DEFAULTS (declarative `off`) resume on the next hook process. There is no migration and no state
to unwind — the colony/wiki state under `.claude/exocortex/` is inert when the organ is off.

## 5. The exporter + Grafana soak

### 5.1 Exporter (Slice 2)
Read-only Prometheus text computed from the live artifacts (`audit.jsonl`, `colony_*.json`, the Genome);
stdlib-only, no new deps ([testbed/exporter/metrics.py](../exocortex/testbed/exporter/metrics.py)).
```bash
python -m exocortex.testbed.exporter.metrics --config exocortex_config.json   # serve :9109/metrics
python -m exocortex.testbed.exporter.metrics --once                            # print once (smoke/CI)
```
Flags: `--state-dir` (default `<repo>/.claude/exocortex`), `--port` (`9109`), `--host` (`0.0.0.0`), `--config`
(sets `EXOCORTEX_CONFIG`). The offline attribution-precision gauge is computed **in-process** and served every
scrape (no cron); drop `<state>/attribution_gauge.json` to override with a real-data run.

### 5.2 Observability stack (Slice 3)
Prometheus + Grafana run in containers; the exporter and any model run **native on the host** (the native-first
decision). Prometheus scrapes the host via `host.docker.internal:9109` at a 15s interval.
```bash
docker compose -f exocortex/testbed/compose/docker-compose.yml up -d
docker compose -f exocortex/testbed/compose/docker-compose.yml down   # tear down
```
- Grafana → `http://localhost:3000` (anonymous Admin, login form disabled) → dashboard **"Exocortex testbed"**.
- Prometheus → `http://localhost:9090`.

### 5.3 What to watch during a soak
| Metric | Read it as |
|---|---|
| `exocortex_seg_len` (histogram, buckets 1,2,3,4,5,8,16) | the **3D prize-sizer** — compare the ≥4 tail to the flagship baseline (median 2, 26% ≥4). |
| `exocortex_wiki_credit_rate` (`used/injected`) | want a **strict trickle**, not a flood (τ only on a note→…→`exit 0` chain). |
| `exocortex_attribution_precision{min_overlap="2"}` | the crown-jewel gauge — must hold **1.0**. |
| `exocortex_wiki_injected_total` | high early is fine (the lexical intake fan); uncredited nodes starve below 0.05. |
| `exocortex_colony_entropy{class}` | lower = more converged/peaked. |
| `exocortex_consequences{outcome}`, `exocortex_deposits` | live `ok/fail` and successful deposits. |
| `exocortex_config_declarative_mode` | sanity check the exporter loaded the **live** config (else 0 — see §6). |

Observed first snapshots (SentAInce-repo vault, live): a first-meal of 40 injected / 3 used → credit rate
≈ 7.5% with precision 1.0 ([testbed/README.md](../exocortex/testbed/README.md)); a first soak of 110 injected,
credit-rate ~11.8%, precision @ mo=2 = 1.0 ([CLAIMS.md](CLAIMS.md) LIVE). Both are **labeled live telemetry,
not locked evidence** — lock Ticket 1 only once a real soak confirms the pattern and bloat starves.

### 5.4 BYO-model data source (Route A)
Hook events are emitted **only by the `claude` CLI** (Anthropic Messages API); ollama is OpenAI-shaped, so a
translating proxy ([`claude-code-router`](../exocortex/testbed/README.md)) must sit between them. Slice 1 is
proven: `llama3.1:8b` drives all six hooks via `proof_route_a.py`. Full recipe + the verified ccr config:
[testbed/README.md](../exocortex/testbed/README.md).

## 6. Operational gotchas

- **Run the exporter WITH `--config`.** Without it the exporter reads the dormant *package* default and reports
  `exocortex_config_declarative_mode 0` even while the wiki is live — a false negative
  ([testbed/README.md](../exocortex/testbed/README.md)).
- **Windows allows duplicate binds on `:9109`.** If metrics look stale/absent, you may have multiple silent
  listeners. Kill all and start one:
  ```bash
  Get-NetTCPConnection -LocalPort 9109 -State Listen | %{ Stop-Process -Id $_.OwningProcess -Force }
  ```
- **Vault scale — a whole archive is too big.** `load_graph` runs on the hot path (every prompt + every consequence).
  The full private research archive (`research-vault`: 6118 files, **344,204 nodes**) costs **~2.1 s/hook** (206 MB cache) and
  lags every keystroke. Stay in the **hundreds–low-thousands of nodes** (a subfolder or the repo's own docs
  load in ~0.04–0.07 s). Table: [testbed/README.md](../exocortex/testbed/README.md).
- **BYO tool-calling is finicky.** The model must emit **native** `tool_calls` (llama3.1:8b does; qwen2.5-coder
  / mistral emit tool calls as text → no `PreToolUse` fires). Do **not** add the `enhancetool` transformer (it
  breaks native calls), and shrink the prompt with `--disallowedTools` so a fast `num_ctx` fits.
- **open-webui emits zero hook events** — it chats ollama directly; it is an inspection/model-management UI,
  **not** a data source. Only the `claude` CLI loop produces hook data.
- **Silent by design.** Because hooks fail open, a misconfigured hook produces no error — only a flat
  `audit.jsonl`. If nothing is accruing, re-check the `settings.json` paths and that the hook's `python` has its
  deps (§1.1).
- **`feeder` (Slice 4) is planned, not shipped.** The testbed README references
  `python -m exocortex.testbed.feeder`, but that module is not yet in the package — drive repos via the
  `claude` CLI / `proof_route_a.py` for now.

## 7. Revert / rollback quick reference

| Goal | Action |
|---|---|
| Disable the declarative wiki | delete repo-root `exocortex_config.json` (§4). |
| Revert an organ flip | set its `mode` back to `off` (or delete the local override). |
| Disable memory entirely (pure baseline) | `EXOCORTEX_COLONY=0`. |
| Deposit but never inject (clean accrual) | `EXOCORTEX_COLONY_SPLICE=0`. |
| Remove the Exocortex completely | delete the `hooks` block from `.claude/settings.json`. |
| Tear down the observability stack | `docker compose -f exocortex/testbed/compose/docker-compose.yml down`. |

Colony/wiki state lives under `<project>/.claude/exocortex/` and is gitignored; deleting it resets all learned
memory without affecting the locked somatic class or the committed Genome.

---

**See also:** [CLAIMS.md](CLAIMS.md) (what is proven vs dormant vs unproven) · [GLOSSARY.md](GLOSSARY.md) ·
[CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md) (the kernel-lock boundary) · [CORE.md](../exocortex/docs/CORE.md) ·
[USERS_GUIDE.md](../exocortex/docs/USERS_GUIDE.md) · [FEATURES.md](../exocortex/docs/FEATURES.md) ·
internal design notes · [BRIDGE_ORGAN_DESIGN.md](../exocortex/docs/BRIDGE_ORGAN_DESIGN.md) ·
[testbed/README.md](../exocortex/testbed/README.md) · [battle_test/WHITEPAPER.md](battle_test/WHITEPAPER.md) ·
[use_cases/README.md](use_cases/README.md).
