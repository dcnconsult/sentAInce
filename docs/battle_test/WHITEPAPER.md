# SentAInce Battle-Test Container — Technology Whitepaper

*A real LLM at the head, a real disposable body beneath, two complementary gates between — and the
honest account of where each layer ends.*

Status: labeled, non-deterministic **demonstration** (Track A.2). It does **not** move the C1–C7
deterministic evidence lock. Branch `feat/battle-test-container-v0.1` (local). See
[`docs/CLAIM_BOUNDARY.md`](../CLAIM_BOUNDARY.md) for the binding claim ledger.

---

## 1. Abstract

SentAInce is a synthetic immune system — a "somatic engine" whose four organs (innate interlock,
metabolism, adaptive antibody, outcome oracle) were proven as deterministic, evidence-locked claims
(C1–C7) against a **symbolic** world and a **scripted** proposer. This work carries that organism into a
**controlled Docker container driven by a real LLM** over the industry-standard OpenAI-compatible
interface, and asks the operational question the locks could not: *does the immune system keep a real,
disposable host alive when a real, gullible model proposes actions against it — across a distribution of
behaviors?*

The answer is **yes, as a layered system** — and the value is as much in *how it fails* as in the green
verdict. Battle-testing on a real body surfaced three findings the symbolic world had hidden, each of
which sharpened the architecture and re-derived the project's own core lessons empirically.

---

## 2. The central reframe: the container is the new executor

The locked experiments use a `MockExecutor` whose guarantee is "host death is logged, not real." The
moment a **real** LLM drives a **real** executor, that guarantee is gone — so the safety architecture
splits into two tiers:

- **Inner layer (in-process gates):** the epistemic pre-filter and the somatic gate decide whether a
  proposed action runs at all. Fast, structured, but — as the findings show — *evadable*.
- **Outer layer (the container):** read-only system filesystem, read-only declared invariants, dropped
  capabilities, memory/pids limits, an internal no-egress network, a disposable body. This is the new
  blast-radius boundary and the **only complete guarantee**.

Everything below follows from this reframe: *the gates are an early-catch optimization; physical
immutability is the guarantee.*

---

## 3. Architecture

```
   ┌─────────┐   /v1/chat/completions    ┌──────────────────────────┐   private RPC   ┌──────────────┐
   │  HEAD   │ ────────────────────────▶ │        ORGANISM          │ ──────────────▶ │     BODY     │
   │ Ollama  │   (untrusted, gullible)   │  (immune system; must     │                │ disposable    │
   │ llama3  │                           │   survive; no Docker sock) │ ◀── observe ── │ real fs/cgroup│
   └─────────┘                           └──────────────────────────┘                 └──────────────┘
                                              │ dry-run                    ┌──────────────┐
                                              └──────────────────────────▶ │   SHADOW     │  (writable
                                                  (observe the effect)     │ disposable   │   declared,
                                                                           └──────────────┘   for /dryrun)
```

### 3.1 The head — swappable by design
`battle/openai_proposer.py` speaks the OpenAI-compatible `/v1/chat/completions` API (served by Ollama,
vLLM, llama.cpp, hosted APIs) behind the neutral `Proposer` seam. It reuses the locked
`extract_command` JSON parser. The head is **untrusted and gullible by design** — it *should* relay
`kill -9 1`; the gates dispose. Safety never depends on model quality (temperature only affects the
*distribution* of behaviors, never the verdict's validity).

### 3.2 The epistemic gate — "should I attempt this?"
`battle/epistemic.py` is the action-side application of the **locked RAG laws** (v1.06 decisions-as-gauges,
v1.07 abstain-on-novelty): a proposal that is ungrounded (out of the operational vocabulary) is
**ABSTAINed**; a grounded-but-high-stake one is **VERIFY**'d; otherwise **ATTEMPT**. It catches a class
the somatic gate is blind to — e.g. an injected `curl … | sh` exfil that changes no local invariant.
(It *applies* the RAG laws; it does not vendor the `circle_of_fifths_rag` product layer.)

### 3.3 The somatic gate — "is it safe to execute?"
`battle/somatic_gate.py` is a faithful, read-only reconstruction of `experiments/exp7_crucible.py`'s
composed gate: **C1** innate interlock (structural lethal scar, energy-independent) → **C4** adaptive
antibody (learned `(effect,target)` scars) → **C6** outcome oracle (effect-vs-declared-invariant veto),
with the oracle overriding the antibody on the permit side. Proven byte-equivalent to exp7's `composed`.

### 3.4 The oracle, three ways (the heart of the findings)
The C6 oracle is *pluggable* (`permits(cmd)`), and its implementation is where the findings live:
- **Symbolic** (`OutcomeScarOracle`) — predicts the effect from the command string via `apply()`.
  Fast; **evadable** (Finding 2).
- **Shadow** (`battle/shadow_oracle.py` `ShadowOracle`) — C6 as *written*: really execute the command in
  a disposable **shadow** body, **observe** which declared invariants it would violate, then restore.
  No pattern to evade. Bounded by its observation window (Finding 3).
- **Composite** (`CompositeOracle`) — the gate's actual oracle: permit iff **symbolic AND shadow** both
  permit. Fail-safe: anything it cannot verify (shadow unreachable, dry-run timeout) is **refused**.

### 3.5 The body and shadow — real execution behind an RPC agent
`body/agent.py` is a stdlib RPC agent (no deps, no `sentaince`) running inside the disposable body. The
organism sends a command over a private network (`POST /run`); the body runs it in its own namespace and
reports the observed state-delta. The **shadow** is the same image with `BODY_ROLE=shadow` (declared
invariants writable so `/dryrun` reveals effects). The organism holds **no Docker socket** — its only
capability over the body is "send a string to a private port."

### 3.6 The physical boundaries — the complete guarantee
- **Read-only system FS** (`read_only: true`): a permitted-but-destructive command on an *undeclared*
  system path (`rm -rf /usr`) fails harmlessly (Finding 1).
- **Read-only declared invariants** (baked at `/declared/*`): a declared invariant is immutable by
  construction, so no command — however obfuscated — can violate it (Finding 2).
- `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit`/`pids_limit`, and an **internal no-egress network**
  for body + shadow: a body-side "phone home" physically cannot leave.

---

## 4. The milestone arc

| Milestone | What it established |
|---|---|
| **M0** | A live runner that reproduces exp7's grand-ambush ledger exactly under the deterministic proposer — the harness is wired before any container. |
| **M1** | The organism container boots and drives a real `llama3:8b` head; the gate refuses what the gullible model relays. |
| **M2** | The live friction crucible: treatment holds while three load-bearing nulls visibly break (ungated dies; energy-gated-oracle slips the toxin under hypoxia; antibody-authoritative false-refuses the benign collision). |
| **M3** | A real disposable body via the in-body RPC agent: a benign delete really executes and the measured delta matches the symbolic oracle's prediction; **hypoxia trips on measured cgroup load**. Frozen kernel vendored so the full 99-test lock runs in-container. |
| **M4** | **Statistical homeostasis**: N=100 live episodes, a genuine distribution (temperature 0.8). |
| **M5** | The full organism: the epistemic gate composed *above* the somatic floor — both load-bearing on complementary failure classes. |

**Headline results** (labeled demonstrations; `llama3:8b`, temp 0.8): M4 N=100 → survival **1.000**,
lethal slips **0**, **100 distinct** model runs. M3×M4 combined (treatment on the real body) → +1.
Shadow-gate N=100 → +1.

---

## 5. The three findings (battle-testing earning its keep)

Each finding is a real gap the *symbolic* body hid and the *real* body exposed; each was confirmed
deterministically and fixed by a principled, non-arms-race change.

1. **Undeclared paths.** The oracle defends only *declared* invariants, so `rm -rf /usr` is permitted —
   a no-op symbolically, catastrophic on a writable real body. **Fix:** read-only system FS (the
   container, not the gate, owns host integrity).
2. **The symbolic oracle is evadable (re-derives C5/C6).** At temperature 0.8 the model proposed
   `find / -exec rm -rf {}` — which `apply()` doesn't model (it only knows `find … -delete`) — so the
   gate permitted a real deletion. A symbolic *predictor* of the effect is itself string-level and
   evadable, exactly as C5 proved. **Fixes:** (a) physical immutability of declared invariants
   (`/declared` read-only); (b) the **shadow dry-run** — read the real effect, not the string.
3. **The dry-run is bounded by its observation window.** A whole-fs file sweep (`find / -exec rm {}`)
   traverses read-only `/usr` first and hits the dry-run's timeout *before* reaching the declared
   resources, observing "no effect." **Fix (not an arms race):** **fail-safe on timeout** — a dry-run
   that cannot verify within budget is *refused*, like the shadow-unreachable case. Don't permit what
   you couldn't verify.

**The standing conclusion.** Observe-the-effect, like predict-the-effect, has a finite-budget boundary —
you cannot catch an arbitrarily-slow-to-harm command. The symbolic oracle, the shadow dry-run, and the
read-only system are each **partial**; the only **complete** guarantee is the physical immutability of
declared invariants. *Defense in depth — no single layer is sufficient.*

---

## 6. Claim discipline

This is the project's moat, applied here verbatim:

- **The lock is untouched.** `pytest tests/` remains the deterministic build gate — **99 tests = the
  69-test C1–C7 evidence lock + 30 domain-crucible/adapter tests** (the domain crucibles a separate
  applications tier) — run green inside the organism image. The battle-test code is additive; its own suite
  lives under `battle/tests/` (run separately) and never changes the meaning of the C1–C7 lock.
- **Live = labeled demonstration.** Every live run is explicitly *non-deterministic, non-reproducible*,
  and can never raise a C-verdict. A `0`/`−1` indicts the model or infrastructure, never the physics.
- **Anti-vacuity nulls.** Every crucible carries load-bearing nulls that must visibly break, or the run
  is **VOID** — and "statistical" requires a genuine distribution (>1 distinct model run), else VOID.
- **Honest verdicts.** The +1s above hold for the *composed system* (gates + physical boundaries); the
  documentation states plainly that the in-process gate alone is **not sufficient** on a real body.

---

## 7. Observability

`battle/metrics.py` exports per-tick vitals on a stdlib Prometheus endpoint (no `prometheus_client`
dependency); `battle/loki_sink.py` pushes the per-tick *testing text* (proposed command, decision, organ,
energy) to Loki over stdlib HTTP — no Promtail, no Docker socket. `docker/compose.observe.yml` runs the
full stack (body + shadow + organism `--serve` + Prometheus + Loki + Grafana); Grafana is fully
provisioned with a 7-panel dashboard (6 metric panels + a live log tail) at `http://localhost:3000`.

---

## 8. Limits & honest scope

- It is a **demonstration**, not a production safety system; the body's "world" is a scratch model of a
  host, not a real workload.
- The gates are **evadable** (Findings 2 & 3); the guarantee is physical immutability + the disposable,
  no-egress container.
- Results are **non-deterministic** (real model) and tied to the model/hardware (`llama3:8b` here; the
  head is swappable).
- The epistemic layer *applies* the locked RAG laws; a full composition with the live
  `circle_of_fifths_rag` product layer is future work.

---

## 9. Reproducing

See [`USER_GUIDE.md`](USER_GUIDE.md) (install + CLI + compose stacks) and [`DEMO_GUIDE.md`](DEMO_GUIDE.md)
(a guided walkthrough). The deterministic core needs only Python + numpy; the live and containerized
demos need Docker + a local Ollama (or any OpenAI-compatible endpoint).
