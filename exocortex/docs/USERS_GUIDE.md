# Exocortex — User's Guide

How to enable, configure, tune, and inspect the Exocortex. Assumes the `exocortex/` package on your
`PYTHONPATH` (it self-locates the repo root). Concepts: [CORE.md](CORE.md) · Features: [FEATURES.md](FEATURES.md).

---

## 1. Requirements

- Python 3 with `numpy` (the somatic gate uses it).
- **Optional (recommended):** `sentence-transformers` for the semantic classifier (the default). Without it
  the hook fails open to the lexical classifier — no breakage, just phrasing-based clustering.
  - WSL note: the live hook runs in WSL's `python3`; install there: `pip install sentence-transformers`.

## 2. Wiring the hook (Claude Code `settings.json`)

The Exocortex is a single dispatcher invoked per event. Minimal project `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse":       [{"matcher": "*",    "hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PreToolUse --mode observe"}]}],
    "PostToolUse":      [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PostToolUse --mode observe"}]}],
    "PostToolUseFailure":[{"matcher":"Bash", "hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PostToolUseFailure --mode observe"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py UserPromptSubmit --mode observe"}]}],
    "SessionStart":     [{"hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py SessionStart --mode observe"}]}],
    "PreCompact":       [{"hooks": [{"type": "command", "command": "python3 /abs/exocortex/hook.py PreCompact --mode observe"}]}]
  }
}
```

CLI args baked into each command (Claude Code does not forward arbitrary env to hooks):
`--mode <observe|somatic|epistemic|full>`, `--audit <path>`, `--state <dir>`, `--colony <0|1>`,
`--splice <0|1>` (via `EXOCORTEX_COLONY_SPLICE`). State (colonies, classifier, session) defaults to
`<project>/.claude/exocortex/`.

The runner `exocortex/runner.py::_settings(...)` generates this block (incl. a `--wsl` variant); the
`exocortex/stream_runner.py` and `scratchpad/run_*.sh` drivers show full headless examples.

## 3. The Genome — tuning without touching code

All knobs live in **`exocortex_config.json`** (the shipped one is the verified default). To experiment,
drop your own and point to it with `EXOCORTEX_CONFIG=/path/to/your.json`, or place
`exocortex_config.json` in `$CLAUDE_PROJECT_DIR`. Search order: `$EXOCORTEX_CONFIG` →
`$CLAUDE_PROJECT_DIR` → package dir. **Precedence per knob: env var > genome JSON > built-in defaults.**
A partial file is fine — unspecified keys keep their defaults.

```json
{
  "thermodynamics":      { "prune_floor": 0.05, "deposit_base_weight": 1.0,
                           "session_discount_rate": 0.8, "weight_min": 0.1,
                           "max_edges_per_class": 32, "decay": 0.9, "min_deposits_to_splice": 2 },
  "epistemic_classifier":{ "mode": "semantic", "model": "all-MiniLM-L6-v2",
                           "abstain_threshold_cosine": 0.45, "match_margin": 0.0 },
  "somatic_gate":        { "mode": "observe" },
  "endocrine":           { "mode": "off",
                           "tiers": { "SATED":    { "prune_floor": 0.03, "max_edges_per_class": 40 },
                                      "STARVING": { "prune_floor": 0.05, "max_edges_per_class": 32 },
                                      "HYPOXIA":  { "prune_floor": 0.12, "max_edges_per_class": 16 } } },
  "eligibility_trace":   { "mode": "off", "gamma": 0.80 },
  "declarative":         { "mode": "off", "vault_path": "", "ingest": "all", "explore_budget": 0,
                           "attribution": { "min_overlap": 2 } },
  "provenance":          { "mode": "off", "recency_halflife_days": 30.0, "version_penalty": 0.5 },
  "integrity":           { "mode": "off", "audit_chain": true }
}
```

Tuning tips (measured):
- **`abstain_threshold_cosine`** — 0.30–0.45 is the verified-clean range; **0.65 fragments** paraphrases
  (defeats the semantic upgrade). Raise toward 0.45 if distinct intents are wrongly merging; lower toward
  0.30 if paraphrases of one intent are splitting.
- **`prune_floor`** — must stay **below `weight_min`** (else session-weighted deposits get pruned before
  they can be reinforced). Higher → faster clutter eviction.
- **`session_discount_rate`** — lower (e.g. 0.7) → harsher penalty on long/flailing sessions.
- **`endocrine.mode`** — `off` (the verified default: static `thermodynamics` constants) or `tier` (allostatic:
  the `endocrine.tiers` table drives `prune_floor`/`max_edges` off the live metabolic tier). Gauge-verified
  SAFE but a modest lever; leave `off` unless a workload shows it helps. Safe envelope: HYPOXIA `prune_floor`
  ≤ 0.15, `max_edges_per_class` ≥ skeleton-size + margin.
- **`eligibility_trace.mode`** — `off` (the verified default: uniform deposit) or `trace` (γ^Δ recency credit
  within a segment). A no-op on short segments; real accruals show deposit windows are short (median 2), so it
  stays `off` unless your workload produces long flail-then-succeed segments (watch the audit's `seg_len`).
- **`declarative.mode`** — `off` (procedural only) or `live` (the wiki organ; **also set `vault_path`** to a
  Markdown vault, else it stays dormant). `ingest`: `all` (every `*.md`) or `tracked` (git-tracked only).
  `attribution.min_overlap` is the precision lever (**2** → attribution precision 1.0; 1 admits coincidental
  echo). `explore_budget` > 0 injects that many flagged-UNVERIFIED bootstrap notes per splice (0 = pure/abstain).
- **`provenance.mode`** (organ F3) — `off` (raw-τ readout, the verified status quo) / `recency` (decay the
  readout by edge age, half-life `recency_halflife_days`) / `full` (+ a `version_penalty` when a stamped edge's
  model ≠ the current one). Recording the `(ts, model)` stamp is always on once a deposit supplies it; only the
  *readout* changes when you flip the mode. Leave `off` until a soak shows genuinely stale/cross-model routes.
- **`integrity.mode`** — `off` / `warn` (audit a frozen-DNA mismatch, continue) / `enforce` (fail-closed `exit 1`
  apoptosis at SessionStart). After any legitimate edit to a frozen kernel file, run
  `python -m exocortex.integrity --update-baseline` or the next session refuses to start. The exocortex layer is
  **not** frozen DNA, so editing the organ never trips it.

## 4. Per-knob env overrides (one-off experiments)

| Env var | Overrides |
|---|---|
| `EXOCORTEX_CONFIG` | path to the genome JSON |
| `EXOCORTEX_EMBED` | `1`/`0` — force semantic / lexical classifier |
| `EXOCORTEX_EMBED_MODEL` | embedding model name |
| `EXOCORTEX_EMBED_MATCH` | the cosine match threshold |
| `EXOCORTEX_EMBED_MARGIN` | top1−top2 commit gate |
| `EXOCORTEX_COLONY` | `0` → disable memory entirely (pure baseline) |
| `EXOCORTEX_COLONY_SPLICE` | `0` → deposit but never inject (clean accrual observation) |
| `EXOCORTEX_MODE` | somatic gate mode (else the genome's `somatic_gate.mode`) |
| `EXOCORTEX_STATE_DIR` / `EXOCORTEX_AUDIT` | where state / audit go |
| `EXOCORTEX_MODEL` | F3 provenance: pin the deposit's model-id (else sourced from the transcript tail) |
| `EXOCORTEX_DECLARATIVE` / `EXOCORTEX_WIKI_VAULT` | declarative organ on/off · the Markdown vault path |
| `EXOCORTEX_WIKI_INGEST` | `all` / `tracked` (git-tracked `*.md` only) |
| `EXOCORTEX_PROJECTS_ROOT` | MCP server: scan a parent dir for many repos (the fleet) |

## 5. Inspecting what it learned

State lives under `<state_dir>` (default `<project>/.claude/exocortex/`):

- `colony_<class>.json` — per-class pheromone: `{label, tau: {"src\tdst": weight}, deposits}`, plus an optional
  F3 `meta: {"src\tdst": {ts, model}}` provenance lane (omitted when empty → pre-F3 colonies stay byte-identical).
  Declarative note→note edges share this file (the wiki organ reuses the colony substrate).
- `cues.json` / `embed_cues.json` — the discovered class vocabulary (lexical / semantic).
- `state_<session>.json` — per-session trail, goal-class, session-deposit count.
- `audit.jsonl` — one record per hook event (the decision trace; hash-chained when `integrity.audit_chain`).
- `wiki_cache.json` — the derived vault digest (a cache, not memory; rebuilt on a signature mismatch).

To see a class's converged route, sort its `tau` by weight (the dominant edges) — the same view the splice
injects.

## 6. Running experiments (the gauges)

- **Granularity / deposit-policy null:** `python -m exocortex.gauge.analyze --out <run-dir> --sweep`
  (offline, over a logged run).
- **HDC capacity (frozen kernel):** `python -m exocortex.gauge.palace_gauge --m 10000`.
- **Organ gauges (each writes a verdict under `results/`):** `credit_hygiene_gauge` (W5 self-edge/orientation
  τ-mass · W4 failure plasticity), `uncertainty_gauge` (G1/F2/F1 veto/abstain rates), `nonstationarity_gauge`
  (F3 provenance coverage + de-confounded/de-biased drift), `endocrine_gauge`, `eligibility_gauge`,
  `bridge_gauge`, `attribution_gauge`. All run `python -m exocortex.gauge.<name>` over the live state (read-only,
  numpy-free); `--json` for machine-readable output.
- **Live accrual/convergence:** see `scratchpad/run_accrue.sh`, `run_pc.sh`, `run_embed_live.sh` for the
  detached-worktree + headless-`claude` pattern (deposit-on / splice-off for clean measurement).

## 7. The memory MCP server (read-only recall for any host)

`exocortex/mcp_server.py` is a stdio MCP server that exposes the earned memory to any MCP host (Claude Desktop,
Claude Code, Cursor, Cline, BYO) — **read-only w.r.t. memory** (querying never deposits τ; only the Code hook
earns). Tools: `recall_procedural(task)`, `recall_notes(query)`, `memory_status()`, `list_repos()`.

- **Requires** the `mcp` SDK: `pip install mcp` (in the host's python).
- **Single repo:** set `EXOCORTEX_STATE_DIR=<repo>/.claude/exocortex` (+ `EXOCORTEX_WIKI_VAULT` for notes).
- **Fleet:** set `EXOCORTEX_PROJECTS_ROOT=<parent>` to scan `<parent>/*/.claude/exocortex`; pass `repo=<name>`
  to the tools (ambiguous → it lists names). Claude Code: `claude mcp add exocortex-memory python /abs/exocortex/mcp_server.py`.
  Claude Desktop: a `claude_desktop_config.json` entry with `command` + the env above (see
  [`../../docs/MCP_SERVER.md`](../../docs/MCP_SERVER.md)).
- **Deliberate recall (the reliable positive path):** `memory_status` marks classes with credited declarative
  notes `[notes:N]`; call `recall_notes(cls="<class>", query="")` to get those notes **directly** (an empty
  `query` with an explicit `cls` bypasses the lexical proposer + the semantic classifier). `cls=` works on
  `recall_procedural` too. A large vault digests once in the background — the first call may return "warming".

## 8. One-command deploy (`exocortex/deploy.py`)

Wire the hooks into any target repo without hand-editing `settings.json`:

```bash
python -m exocortex.deploy install   <repo> [--mode observe] [--declarative live --vault <path> --ingest tracked]
python -m exocortex.deploy status    <repo>
python -m exocortex.deploy uninstall <repo>            # surgical; keeps your other settings + accrued data
python -m exocortex.deploy uninstall <repo> --purge    # also delete the accrued state
```

Uninstall removes **only** our hook entries (your permissions/MCP/foreign hooks survive), and install is
**non-invasive to the target's git** (ignore rules go to `.git/info/exclude`, a one-time `.exocortex.bak` of
`settings.local.json`). Posture (mode, declarative, integrity) lives in the target's gitignored
`exocortex_config.json`; delete it to revert to the dormant defaults.

## 9. Troubleshooting

- **Splice never appears** — the class may be below `min_deposits_to_splice` (needs repetition), or it's a
  novel class (correctly abstaining), or `EXOCORTEX_COLONY_SPLICE=0`.
- **Paraphrases not merging** — embedder unavailable (check it imports in the *hook's* python), or
  `abstain_threshold_cosine` too high.
- **Memory feels stale after a refactor** — expected for a few class-uses; non-recurring edges decay out
  (raise `prune_floor` toward `weight_min` to evict faster).
- **Want a pure baseline** — `EXOCORTEX_COLONY=0`.
