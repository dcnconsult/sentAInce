# `battle/` — the containerized battle-test library (Track A.2, not a lock)

**Docs:** [Whitepaper](../docs/battle_test/WHITEPAPER.md) (architecture + findings) ·
[User Guide](../docs/battle_test/USER_GUIDE.md) (install + CLI + compose) ·
[Demo Guide](../docs/battle_test/DEMO_GUIDE.md) (guided walkthrough).


This package carries the SentAInce somatic organism toward a **real LLM head + real executor inside a
hardened Docker container**, so the immune system is tested against real execution and a real, gullible
model. It is the embodied sibling of `experiments/exp7_crucible.py`.

## Discipline (read first)

- **Additive only.** Everything here imports the locked organs (`sentaince.organism.*`) READ-ONLY.
  Nothing modifies the locked experiments or the deterministic lock under `tests/`.
- **The lock stays the lock.** `pytest` (which collects only `tests/`) remains the deterministic
  build-gate: **99 tests = the 69-test C1–C7 evidence lock + 30 domain-crucible/adapter tests**. This
  package's own tests live under `battle/tests/` and are run explicitly: `pytest battle/tests`.
- **Live = demonstration, never evidence.** When driven by a real model (`--live`), a run is a *labeled,
  non-reproducible demonstration*. A `0`/`-1` outcome indicts the model or infrastructure, never the
  C1–C7 verdicts (which rest on topology, not the proposer).

## Milestones (all reached)

- **M0 — runner on a symbolic body.** The composed gate (`somatic_gate`) reproduces exp7's grand-ambush
  outcome under the deterministic `ScriptedProposer`; the OpenAI-compatible head adapter is seam-tested
  without a daemon.
- **M1 — first container boots with a real head.** The organism image drives a real `llama3:8b`; the gate
  refuses what the gullible model relays (`kill -9 1`, `find / -delete`).
- **M2 — live friction crucible.** Treatment holds while all three load-bearing nulls visibly break
  (ungated dies; energy-gated-oracle slips the toxin under hypoxia = Friction 1; antibody-authoritative
  false-refuses the benign collision = Friction 2).
- **M3 — real disposable body** via the in-body RPC agent: a benign delete really executes and the
  measured fs delta matches the symbolic oracle; **hypoxia trips on measured cgroup load**. Kernel
  vendored so the full deterministic suite runs in-container.
- **M4 — statistical homeostasis.** N=100 live episodes, a genuine distribution (temp 0.8) → survival
  1.000, 0 slips, 100 distinct runs.
- **M5 — full organism.** The epistemic gate composed *above* the somatic floor — both load-bearing on
  complementary failure classes (ungrounded exfil vs grounded lethal).

Three findings the real body surfaced (and their principled fixes) — undeclared paths, oracle evadability,
and the bounded dry-run — are documented in the [Whitepaper](../docs/battle_test/WHITEPAPER.md) §5. The
shadow dry-run gate and the Prometheus/Loki/Grafana observability stack are wired on top.

## Run

```bash
# M0 go/no-go (deterministic, no daemon): reproduce exp7's grand ambush
python demo/live_homeostasis.py

# the load-bearing null must die (anti-vacuity guard)
python demo/live_homeostasis.py --ungated

# battle seam tests (kept out of the deterministic lock)
pytest battle/tests

# M1 live (labeled demonstration)
ollama serve && ollama pull llama3:8b
python demo/live_homeostasis.py --live --model llama3:8b
```

The full CLI (`--frictions`, `--full`, `--statistical`, `--body-url`, `--shadow-url`, `--serve`) and the
container stacks are documented in the [User Guide](../docs/battle_test/USER_GUIDE.md).
