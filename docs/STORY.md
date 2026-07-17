# SentAInce, in human terms

> A **SyncQutrit Research Group** product, part of the **FreqOS** software portfolio.
> This document tells the story in plain language. For the binding, qualified evidence, see
> [`CLAIMS.md`](CLAIMS.md) — nothing here exceeds it.

## The idea in one breath

SentAInce wraps an AI coding agent in a **body borrowed from biology**. Most AI "memory" rewards whatever
gets *retrieved* often — popularity as a stand-in for usefulness. That is exactly how a bolted-on knowledge
base rots: it confidently cites stale notes because they were read a lot, not because they ever helped.

SentAInce obeys **one law instead**: a memory is earned by a closed `action → success (exit 0)` chain —
**never** by being read, repeated, or bookmarked. Habits form only when work *actually succeeds*. That single
rule is why the memory stays clean, and everything below is a consequence of it.

## The anatomy — each organ and its human counterpart

| Organ | Human counterpart | What it does, plainly |
|---|---|---|
| Somatic gate / interlock | 🛡️ **Immune system** (a reflex) | Refuses catalogued lethal actions *before they run* — a reflex, not a judgment call, and independent of the model. Never sold, never web-writable. |
| Energy & metabolic tiers | 🫀 **Stamina & blood sugar** | Work costs energy; as reserves fall it grows conservative (SATED → STARVING → HYPOXIA), doing less and only what's safe. |
| The colony (τ) | 💪 **Muscle memory** | Routes that succeed get reinforced; everything else fades. A habit forms only on a verified success. |
| The declarative wiki | 📖 **The notebook** | Written notes earn trust the same way — only when *using one* led to a success. |
| Circadian consolidation | 😴 **Sleep** | On compaction the organism sleeps: every memory fades a little, the weakest are forgotten, the strongest survive. |
| Endocrine (dormant) | 🧪 **Stress hormones** | Under stress, sleep gets leaner — shipped **off**, because its own gauge rated the benefit modest. |
| Integrity + audit chain | 🧬 **DNA check & medical record** | Tampered DNA → the organism refuses to run; every decision is hash-chained, so a silent edit snaps the chain. |
| The gauges | 🔬 **The lab** | Every organ ships with the instrument that can kill it: the verdict is *real* or *parked*, honestly. |
| Cerebral Governor | 🧠 **Executive function** | Surfaces work that fell through the cracks (opened, never closed, gone silent). Read-only — it suggests, you decide. |

## The honest numbers (every one keeps its qualifier)

Honesty *is* the product. Where an organ's own gauge said the prize was modest or null, the organ ships
**off**. The lab reports both directions — that record is the differentiator, not an embarrassment.

| What | Number | The honest caveat |
|---|---|---|
| Immune system under live fire | **survival 1.000 · 0 lethal slips · N=100** | A *labeled demonstration* with a real local model — never the evidence. The evidence is the **99-test deterministic lock**. |
| Memory stays clean | clutter **0% vs 24%** | Consequence-sourcing vs a popularity-driven control (the crown-jewel gauge). |
| Notes credited only when used | precision **1.00 @ overlap≥2** | On controlled/planted tasks. At overlap 1 it drops to 0.50–0.79 — the guard is load-bearing, not decorative. |
| Notes are trusted sparingly | credit rate **~7.7%** | A trickle *by design* — the organism trusts little, and only what paid off. Held across ~3.5× more soak data. |
| Triage of stalled work | **0.63 → 0.853** | Resurrection Governor, with parent-liveness; 46 labeled items on one private vault — a labeled demonstration. |
| Habits are short | routes **median 2 steps** | Real success-streaks are brief, so the organism learns skeletons, not epics. Stated plainly, not hidden. |
| Parked organs | eligibility / endocrine / uncertainty **OFF** | Their own gauges said modest/null (e.g. uncertainty abstained 0/301; a functional-information gauge came back null, p=0.14). |

## What the dashboard shows (two skins)

The observability stack ships **two Grafana dashboards** over the same live data:

- **"SentAInce — The Organism"** *(the home page)* — the story skin. One row per organ, each in the human
  terms above, with the honest stat printed alongside its live panels. This is what a first-time visitor sees.
- **"Exocortex testbed"** *(one click away)* — the technical instrument panel: raw gauge signals, PromQL,
  per-class convergence, the seg_len heatmap. This is what an operator tunes against.

Before either of those, the exporter itself (`:9109/` — no Docker needed; `sentaince body` opens it) shows
**the body**: one small human silhouette per repo, each organ region colored by a live thresholded vital with
its rule printed beside it (green = healthy, amber = attention, gray = deliberately dormant, dashed outline =
no data yet — nothing ever fakes green; the rules are [`COLOR_DOCTRINE.md`](COLOR_DOCTRINE.md)). Undeployed
sibling repos appear asleep with a copy-paste deploy command — deploying stays a CLI act. A browser **control
plane** (`:9109/control`) lets you tune each repo's organs, grouped by their human counterpart, with a
plain-language hint on every knob, and edit the [estate file](ESTATE.md) (the file-based multi-repo
registry). The 🛡️ immune system is shown there **read-only** and is never web-writable — you tune the
autopilot, never the brakes.

## Why "safety is never for sale"

The immune system, the metabolic governor, and the DNA/apoptosis check run **locally and free, always**.
They are never paywalled and never reachable from the web. What SentAInce sells (in the FreqOS portfolio) is
the *optimization and management* layer — the autopilot — never the *protection*. In a market that overclaims
safety, the vendor that refuses to monetize it is the trustworthy one. That is both the ethic and the moat.

## Where this grows — the vision, with its gates showing

A body that guards one repo is the seed, not the plant. The arc we're building toward is a **single
memory discipline for your whole desk** — and because this project publishes designs before code, every
step below carries its real status. A status tag is a promise about evidence, not a mood:
**SHIPPED** means it runs today · **DORMANT** means built, measured modest, off by default ·
**IN DESIGN** means actively being shaped, decisions not yet on the record ·
**PROPOSED** means designed on the record, not yet built.

| The step | Status today | What it waits on |
|---|---|---|
| One organism, many hosts — Claude Code and Cursor drive the same body; ChatGPT reads the same earned memory (read-only) | **SHIPPED** | — |
| One organism, many repos on your machine — each with its own colony, audit chain, dashboards | **SHIPPED** | — |
| Executive function — a read-only Governor that surfaces work that fell through the cracks | **SHIPPED** (suggests only) | — |
| **Cross-repo federation** — what your research repo learned, your coding repo can consult; one discipline across coding, research, and personal knowledge | **PROPOSED** ([ADR-014](ADR.md)) | a consequence-preserving design for *whose* success earns *which* repo's trust — federation must not launder popularity back in |
| **Governed fleets** — the audit chain, tamper-evident memory, and policy-bound gates plugged into emerging agent-governance standards, so companies adopt agent memory *with* corporate standards | **IN DESIGN** | an interoperability card + transport work (additive; zero change to the organism); the tamper-evidence hardening is [ADR-017/018](ADR.md), PROPOSED |
| Deeper tamper-evidence — the mutable memory itself commits digests into the hash-chained record | **PROPOSED** ([ADR-017/018](ADR.md)) | build + gauge; ships dormant first, like everything |

Two things make this vision credible rather than aspirational. First, the pattern above has already run
to completion several times: idea → gauge → verdict → ship-or-park is how every organ in the anatomy
table got its status, including the ones we switched **off**. Second, the discipline is symmetric — when
our own instruments say a feature's prize is modest, we say so in the same table where we celebrate the
wins. A roadmap you can trust is one that has parked things publicly.

**The part you can help with today:** the memory subsystem ships with read-only gauges anyone can run on
their own accrued corpus. This project's biggest open question isn't a feature — it's *how these
dynamics behave across many people's real work*, a question a single maintainer's repos cannot answer
alone. Run the gauges, post the numbers (nulls are as welcome as wins), and you're contributing to the
science, not just the software.

---

**See also:** [`CLAIMS.md`](CLAIMS.md) (the binding evidence ledger) · [`ADR.md`](ADR.md) (the
architecture decisions — eighteen and counting, each on the record) · [`../README.md`](../README.md) ·
[`QUICKSTART.md`](QUICKSTART.md) · the testbed dashboards under
[`../exocortex/testbed/`](../exocortex/testbed/README.md).
