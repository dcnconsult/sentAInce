# Exocortex Documentation

The Exocortex is an external, self-maintaining **procedural + declarative memory** for LLM agents: it
remembers the sequences of tool-actions (and the notes) that *verifiably succeeded* in a repository, forgets
the rest, and re-surfaces the right ones when a matching task recurs — all outside the model weights, via
Claude Code hooks, and readable from any MCP host via a read-only recall server.

| Document | For whom | What it covers |
|---|---|---|
| [WHITEPAPER.md](WHITEPAPER.md) | technical / research | the mechanism, the measured results, the honest negatives, reproducibility |
| [CORE.md](CORE.md) | engineers | the organism, core laws, lifecycle, module map |
| [FEATURES.md](FEATURES.md) | engineers / PM | feature list with evidence + status tags + the knob table |
| [USERS_GUIDE.md](USERS_GUIDE.md) | operators | install, wire the hook, tune the Genome, inspect, troubleshoot |

**One-line summary.** Consequence-sourcing (deposit pheromone only on `exit 0`) keeps an ant-colony-style
memory clean; a semantic cue-classifier routes paraphrased tasks to the right per-class colony; the
consolidated route — and the τ-credited declarative notes — are spliced back via `UserPromptSubmit`, and a
read-only MCP server exposes all of it to any agent host. All knobs live in `exocortex_config.json` (the
Genome). Status: research-stage, end-to-end verified on one repo + small/flagship models. The **declarative
wiki** organ is LOCKED (attribution precision 1.0 @ mo=2) but ships DORMANT by default; several further organs
(allostatic **endocrine**, **eligibility-trace** credit, the **Hippocampus bridge**, **F3 provenance/
non-stationarity**, **kernel-lock integrity**) are gauge-verified and wired but **ship dormant** — on
world-class flagship models the measured prize is null-to-modest, so any net gain is the achievement.

**The full engineering log** (every stage, measurement, and honest negative) is in
[`../MEMORY_GAUGE_DESIGN.md`](../MEMORY_GAUGE_DESIGN.md) §§1–16.
