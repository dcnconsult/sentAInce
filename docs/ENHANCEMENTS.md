# FreqOS / SentAInce — Enhancement Backlog (community edition)

> **This is the community edition of the backlog.** Frontier/whitespace research directions and
> pre-release design work are tracked privately; what follows is the actionable, already-grounded list:
> known outstandings, the Wave-2 plan reconciled with what is *actually* built, testbed/observability
> items, and doc hygiene. It **must not exceed** [`CLAIMS.md`](CLAIMS.md) (the binding evidence ledger).

An item is *done* only when its falsifiable trigger fires or its artifact ships verified — never by
assertion. Items retire the same way the organism earns τ: by a closed action→…→verified-outcome chain.

**Priority:** **P0** now / load-bearing · **P1** next · **P2** soon · **P3** someday.
**Status:** ☐ open · ◐ partial · ✅ done · ⏸ parked (data-gated).

---

## A. Wave 2 plan — reconciled with reality

Here is what is *actually* true today, so the plan does not drift into overclaim (the project's "honesty is
the moat" discipline).

| Ticket (authored) | Actual state | Next action |
|---|---|---|
| **1 — Sovereign Epistemology / Obsidian wiki** | **✅ core LOCKED**; doc-rot sub-organs ☐ unbuilt. Declarative wiki: forage/splice/content-echo attribution (mo=2 → precision **1.0**), live on the SentAInce vault. The doc-rot sub-organs (epistemic-drift, dry-run paragraph-scar) are **not built** — the consequence-only scar is the entry point. | Park doc-rot until a vault demands it; test the tail on a denser vault. |
| **2 — Hippocampus (topological shortcut builder)** | **◐ built, DORMANT verified-vestige.** 5 slices, propose→offer→verify→crystallize/scar proven end-to-end in tests; offline 0.96→1.00. Held dormant: the ≥2-note declarative tail *thinned* under more soak. | Flip `suggest` only when the multi-note tail fattens **and** an on-body bridge-validity gauge passes. |
| **3 — Cerebellum (O(1) macro reflex)** | **⏸ not built (data-gated).** | Gauge macro-eligibility first; blocked on the same data gate as the eligibility trace — needs a materially fatter ≥4 `seg_len` tail. If ever built: suggest-not-execute behind the somatic gate, never autonomous. |
| **4 — Pacemaker (wiring the Heart / G.A.R.D.)** | **◐ SUBSTRATE.** Respect (HDC 0-well abstain) is LIVE. Governance (Φ⁶) + Alliance (harmonic entrainment) are **vendored, not wired**. | Wire the kinetic governor + phase-entrainment into the hook dispatcher; must respect the kernel-lock lineage. |

---

## B. Known outstandings — "data gates ambition" (from [CLAIMS.md](CLAIMS.md) MARGINAL)

These are honest, measured limits, each with the falsifiable trigger that would retire it. They are not
bugs; they are the boundary of current evidence — and this honest record is itself the differentiator.

- **P1 ⏸ Deposit windows are short.** Procedural routes **median 2** edges (cross-model: haiku ≡ sonnet);
  a *consequence* of strong consequence-sourcing (re-root per verified command). Caps the payoff of the
  eligibility trace, macros, and bridges. **Retire when:** a model/repo shows a materially fatter ≥4 tail.
  *Lengthening windows deliberately is rejected — it would dilute the crown-jewel law.*
- **P1 ⏸ Declarative routes are shallower still.** Notes-credited-per-segment **median 0**; only **8.9%**
  of injected segments credit ≥2 notes (locked soak). Keeps the **bridge prize MARGINAL**. **Retire
  when:** a larger/denser vault grows the ≥2-note tail.
- **P2 ☐ Attribution precision is on controlled tasks.** The 1.0 @ mo=2 is clean single-command planted
  tasks; the messy-real-coding coincidental-echo rate is watched live via `wiki_credit_rate` but **not yet
  a measured precision**. **Retire when:** a real-data attribution gauge is run and charted per-repo.
- **P1 ◐ BYO small-model completion is poor — empirically confirmed.** `llama3.1:8b` *drives* the hooks
  but cannot complete tool-using work: a full 8-episode feed produced **0 Bash consequences, 0 deposits**
  → the seg_len tail is unmeasurable. A definitive load-bearing negative, not an assertion. **Retire
  when:** a more capable BYO model (or a more tool-forcing harness) produces real deposits.
- **P2 ◐ G.A.R.D. is partly aspirational.** Respect LIVE; Governance + Alliance vendored-not-wired (Ticket 4).
- **P2 ⏸ Uncertainty/veto signals are null on flagship.** A flagship doing grounded coding emits almost
  none of the OOD / veto / unsafe events these organs consume (abstain 0/301; veto 1/1115). **Retire
  when:** adversarial / untrusted-BYO / security traffic shows those rates rise. Evidence:
  [`results/uncertainty_gauge_v1/RESULTS.md`](../results/uncertainty_gauge_v1/RESULTS.md).

---

## C. Testbed / observability backlog (the multi-repo stack)

Operational items on the containerized exporter + control plane + Grafana (`exocortex/testbed/`).

- **P1 ✅ `$repo` dropdown showed deleted repos.** *(Fixed.)* The variable is now an instant
  `query_result(exocortex_state_dir_present)`, so only currently-scraped repos appear.
- **P2 ◐ Dashboard + gauge wiring.** *(Largely done.)* The exporter runs the live stdlib gauges once per
  scrape → per-repo series + a global `exocortex_gauge_signal` verdict board (1=prize-real / 0=park). Two
  Grafana skins ship: **"SentAInce — The Organism"** (the story skin, default home) and **"Exocortex
  testbed"** (the technical instrument panel). Loki + Promtail stream the audit tail. **Residual:** a
  caching pass if per-scrape gauge recompute proves heavy on a large soak.
- **P1 ✅ Ports bound to `127.0.0.1`.** The LAN can't reach the control plane / Grafana; CSRF is closed and
  a `--read-only` posture + optional write token exist (see [`SECURITY.md`](SECURITY.md) §7).
- **P2 ☐ Control-page UX.** Post-set value refresh/toast; highlight knobs that differ from DEFAULTS; a
  "revert to dormant" button (delete `exocortex_config.json`).
- **P2 ☐ Exporter scale.** Per-scrape cost is O(repos) (cheap — file reads + entropy, no `load_graph`) but
  unbounded; cap / concurrent-collect when the repo count is large.
- **P1 ✅ Repo-feeder.** *(Built — `exocortex/testbed/feeder.py`.)* Drives a disposable repo and accrues
  real `seg_len` — the science check vs the flagship median-2/26%-≥4 baseline.

---

## D. Doc hygiene (keep the ledger honest)

- **P2 ✅ `ROADMAP.md` drift vs `CLAIMS.md`.** *(Synced.)* Declarative wiki now **LOCKED**; the
  testbed/Tuner rows reflect the shipped multi-repo exporter + control plane + feeder + Tuner emulator +
  the confirmed BYO limit.
- **P3 ☐ `exocortex/docs/` stale counts.** Component deep-dives carry stale test/metric counts; CLAIMS is
  authoritative (already noted in those docs). Sweep when convenient.
- **P2 ✅ Reflect the testbed control plane in `SECURITY.md`.** *(Done — §7: the write surface, the
  allowlist boundary, and the localhost assumption.)*

---

**See also:** [`ROADMAP.md`](ROADMAP.md) (phased vision + data gates) · [`CLAIMS.md`](CLAIMS.md) (the
binding ledger) · [`GLOSSARY.md`](GLOSSARY.md) · [`FEATURES.md`](FEATURES.md) (shipped features + the knob
table) · [`../exocortex/testbed/README.md`](../exocortex/testbed/README.md).
