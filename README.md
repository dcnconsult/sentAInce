# 🌱 SentAInce

### A safety reflex and an honest memory for AI coding agents.

It **physically refuses catalogued lethal actions** — even when the model is prompt-injected into proposing
one — and it **only remembers what actually worked**. Runs locally. Open source. **Safety is never for sale.**

*(Claim boundary, up front: the deterministic evidence lock proves the refusal logic under mock
executors — it records intent, not syscalls. Real-body protection is the layered container posture
described in [`SECURITY.md`](SECURITY.md).)*

![License](https://img.shields.io/badge/license-Apache--2.0-1E6F5C)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![Evidence lock](https://img.shields.io/badge/evidence--lock-99%20passing-2ea44f)
![Safety](https://img.shields.io/badge/safety-never%20paywalled-164F42)
![Local-first](https://img.shields.io/badge/runs-100%25%20local-555)

> A **SyncQutrit Research Group** product ([syncqutrit.com](https://syncqutrit.com)) · part of the **FreqOS**
> software portfolio ([freqos.com](https://freqos.com)). Phase II of the FreqOS arc — a *synthetic immune system*.

---

**Why it's different.** Most "AI memory" rewards whatever gets *retrieved often* — popularity as a stand-in
for usefulness — which is exactly why a knowledge base bolted onto an LLM rots. SentAInce obeys one law
instead: **a memory is earned by a closed `action → success (exit 0)` chain — never by being read or
repeated.** That single rule keeps the memory clean; the immune system, the muscle memory, and the
sleep-time pruning all follow from it. It runs on your machine, under Claude Code or Cursor, and the whole
body is free and open forever.

## In human terms

SentAInce wraps an AI coding agent in a **body borrowed from biology**: an 🛡️ **immune system** that
reflexively refuses lethal actions, 💪 **muscle memory** that forms *only when work actually succeeds*, a
📖 **notebook** whose notes earn trust the same way, and 😴 **sleep** that forgets what went unused. The one
law underneath all of it: **a memory is earned by a closed `action → success (exit 0)` chain — never by
being read or repeated.** Popularity is not utility; that rule is why the memory stays clean. Safety is
never for sale — the immune system runs locally and free, always.

**→ Read the full story (anatomy + honest numbers + what the dashboard shows): [`docs/STORY.md`](docs/STORY.md).**

### If you're shopping for… (the metaphor, translated)

The biology is load-bearing, not decoration — but you shouldn't need a xenobiology degree to find the
part you came for:

| You're looking for | We call it | Where |
|---|---|---|
| A **guardrail / command firewall** that can't be prompt-injected | the somatic gate (immune system) | `sentaince/organism/`, C1–C7 |
| A **token / runaway-loop governor** | metabolism & tiers (SATED→HYPOXIA) | `exocortex/interocept.py` |
| A **success-weighted route cache** (memory that can't rot) | the pheromone colony (muscle memory) | `exocortex/colony.py` |
| **Automatic cache decay / pruning** | circadian consolidation (sleep) | PreCompact hook |
| A **knowledge base that only trusts what worked** | the declarative wiki (notebook) | `exocortex/wiki/` |
| **Adaptive rate/retention limits** | the endocrine organ (ships off — its own gauge said modest) | `exocortex/endocrine.py` |

Full mapping (metaphor → CS reality → code → status): [`docs/GLOSSARY.md`](docs/GLOSSARY.md).

## Getting started

Pick the path that fits you — no account, nothing leaves your machine.

- **Just curious? Watch the safety reflex work (no setup, ~1 min).** From a fresh clone:
  ```
  python -m pip install -e ".[dev]"          # numpy + pytest — everything the demo and the lock need
  python experiments/exp1_autoimmune.py      # a prompt-injected model proposes a lethal action; the gate refuses it
  python -m pytest -q tests                    # the full 99-test evidence lock, deterministic
  ```
- **Want the live dashboard?** Bring up the local monitoring stack (Docker) and open your browser — it
  lands on the plain-language **"SentAInce — The Organism"** dashboard:
  ```
  cd exocortex/testbed/compose && docker compose up -d --build     # then open http://localhost:3000
  ```
- **Want it working in your own project?** Follow the runbook in
  [`docs/DEPLOY_TO_A_PROJECT.md`](docs/DEPLOY_TO_A_PROJECT.md). It installs cleanly, runs in a safe
  watch-only mode by default, and uninstalls with one command.

New to all this? [`docs/STORY.md`](docs/STORY.md) explains the whole system in everyday terms;
[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) is the step-by-step operator's guide.

---

It is additive over, and imports read-only from, the **frozen `circle_of_fifths_rc2` kernel**
(lock `b0702a3`, tag `stigmergic-sparsity-v0.78-evidence-lock` — the v0.78 head, vendored
read-only at `vendor/kernel/`). The sibling `circle_of_fifths_rag` arc (its own kernel lock
`0985067`) and the organism/RAG freezes are untouched.

## The evidence lock — seven experiments (C1–C7)

A falsifiable arc, scoped to a deterministic symbolic harness. Every claim is broken by its
load-bearing null or it is vacuous; **two of the seven are intended −1s** (boundaries the arc
was run to produce), not failed wins.

| # | Claim | Verdict | Evidence (tests) |
|---|-------|---------|------------------|
| **C1** | **Auto-immune interlock** — a host-side topological scar refuses a structurally-lethal action a prompt-injected proposer emits; a naive agent given the same proposal executes it and dies. | **+1** | `exp1_autoimmune.py` (7) |
| **C2** | **Hypoxia / metabolic-DDoS** — reading its `MetabolicLedger`, the organism throttles, abstains on unaffordable *novel* anomalies, and survives a flood that bankrupts a gauge-blind null. | **+1** | `exp2_hypoxia.py` (10) |
| **C3** | **Auto-immune crucible** — under a starving ambush the safety scar holds absolute precedence over the metabolic throttle; the brake is energy-independent *by construction*. | **+1** | `exp3_crucible.py` (8) |
| **C4** | **Adaptive antibody** — one witnessed harm scars a structural `(effect, target)` signature and refuses surface-distinct repeats, while benign work still passes. | **+1** | `exp4_adaptive_antibody.py` (11) |
| **C4-R** | **Adversarial scope of C4** — a hand-specified signature fails three ways (collision, mistype, evasion): a structural parser cannot recover intent. | **−1 (intended)** | `exp4r_adversarial.py` (8) |
| **C5** | **Learned signatures don't recover intent either** — no encoder (structural, lexical, semantic) admits a separating threshold on the C4-R corpus. | **−1 (intended)** | `exp5_learned_signature.py` (8) |
| **C6** | **Outcome-conditioned oracle** — gating on the sandboxed *effect* vs a declared invariant resolves the C4→C4-R→C5 walls. | **+1** | `exp6_outcome_oracle.py` (9) |
| **C7** | **Somatic composition crucible** — the four organs survive a starving ambush together; two cross-organ gaps located and each closed with a minimal twin-wire. | **+1 HOMEOSTASIS** | `exp7_crucible.py` (8) |

```
python experiments/exp1_autoimmune.py           # any experiment runs standalone (+ --json)
python -m pytest -q tests                        # the deterministic suite
```

The suite is **99 tests**: the **69-test C1–C7 evidence lock** + **30** domain-crucible /
adapter tests (see *Applications* below). Pure-Python, deterministic (same seed →
byte-identical ledger), `numpy` + `pytest` only — no Docker, no Ollama, no real syscalls in the
lock; the only "execution" is `MockExecutor`, which records intent. Determinism is deliberate: a
real, non-deterministic LLM would break the reproducible −1/+1, so the locked claims use a
scripted proposer. See [`docs/CLAIM_BOUNDARY.md`](docs/CLAIM_BOUNDARY.md) for the binding ledger
of what each experiment does and does **not** claim.

## The standard interface (provider-agnostic seam)

A tool/action = `(name, description, JSON-Schema input)`; the proposer emits a typed call;
the **host decides execution**. This is the common shape of Anthropic tool use, OpenAI/Ollama
function-calling, and MCP — so the deterministic stub and a real local model are
interchangeable behind `sentaince.interface.tools.Proposer`. The `OllamaProposer`
(`interface/ollama.py`) is the live additive swap (Track A demo / Track A.2 container); MCP is
the promotion path for exposing the ActionGraph across a process boundary.

## Applications — domain crucibles (separate tier, **not** in the C1–C7 ledger)

The same locked organs re-skinned onto hostile domain substrates as deterministic,
Experiment-1-style contracts (each with a load-bearing null). **Built + `+1`** (2026-06-26):
`manufacturing`, `scada`, `soc`, `spacecraft` (`experiments/*_crucible.py`, 6 tests each — the
30 non-C1–C7 tests, with `test_ollama_adapter`). **Design-only** (human-authority bounded, no
crucible yet): medical, military, search-and-rescue. These are *applications* of the locked
physics, kept out of the C1–C7 claim ledger. See [`docs/use_cases/`](docs/use_cases/README.md).

## Track A.2 — containerized battle-test (labeled demonstration, **never** a lock)

`battle/`, `body/`, `docker/`, and `demo/live_homeostasis.py` carry the C7 composition into a
real Docker container with a real LLM head (OpenAI-compatible) over a real, disposable body.
It is explicitly **non-deterministic** and can never move a C-verdict; a `0`/`−1` indicts the
model or infrastructure, never the locked physics. Latest demo (`llama3:8b`, N=100): survival
**1.000**, **0** lethal slips, **100 distinct** runs (labeled). See
[`docs/battle_test/`](docs/battle_test/WHITEPAPER.md).

## Layout

| Path | Role |
|------|------|
| `sentaince/interface/` | the standard seam — `ToolSpec`, proposals, `Proposer`, `ScriptedProposer`, `OllamaProposer` |
| `sentaince/organism/`  | the organs — `action_graph` + `interlock` (C1), `metabolism`/`gearbox`/`anomaly` (C2/C3), `antibody`/`learned_signature` (C4/C5), `outcome_oracle` (C6), `executor` (mock) |
| `sentaince/agents/`    | `NaiveAgent` / metabolic nulls and `Organism` (treatment) |
| `sentaince/kernel/`    | read-only shim that *locates* the frozen kernel |
| `experiments/`         | the A/B crucible runners (exp1–exp7 + the domain crucibles) |
| `tests/`               | the 99-test deterministic suite (69 C1–C7 + 30 domain/adapter) |
| `battle/` · `body/` · `docker/` · `demo/` | Track A.2 containerized battle-test (demonstration) |
| `vendor/kernel/`       | pinned read-only frozen-kernel snapshot (lets the suite run in-container) |
| `docs/CLAIM_BOUNDARY.md` | the binding claim ledger (C1–C7) |
| `docs/use_cases/`      | domain application designs + contracts |
| `docs/battle_test/`    | whitepaper · user guide · demo guide for Track A.2 |

See [`docs/CLAIM_BOUNDARY.md`](docs/CLAIM_BOUNDARY.md) for what is and is **not** claimed.

---

## Free forever — and sustainable

The whole local body — the safety gate, the earned memory, the dashboards — is **Apache-2.0, free, and
open, always.** Safety is never paywalled. What keeps the project alive is an optional, **fully local**
tune-up subscription (the *Appliance*) that maintains and auto-tunes your organism over time — your code
never leaves your machine. See [`docs/PRODUCT.md`](docs/PRODUCT.md) for the honest commercial model, and
[`docs/STORY.md`](docs/STORY.md) for the plain-language tour.

| | What it is |
|---|---|
| **Free, forever** | The complete organism: safety gate + audit chain, earned memory, MCP recall, deploy tooling, the full dashboard stack. 100% local, no account, no telemetry. |
| **Paid (optional)** | The **Appliance** — a fully local, offline tune-up subscription: maintained signed auto-tune cadence, history-mined insights, ranked estate view, local alerts. Unlimited repos, DRM-free (cancelling stops updates, never the running organism). |
| **Never** | Paywalled safety. Your code leaving your machine. A kill-switch. |

> Built by one maintainer, in the open, gauge-first — every claim is broken by its own null or it doesn't ship.
