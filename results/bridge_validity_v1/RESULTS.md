# Bridge-validity gauge v1 — the on-body gate, and its pre-flight reading

**Run date:** 2026-07-30 · **Repo:** SentAInce (its own live store) · **Read-only.**

```bash
python -m exocortex.gauge.bridge_validity_gauge --state-dir .claude/exocortex            # structural only
python -m exocortex.gauge.bridge_validity_gauge --state-dir .claude/exocortex --vault-path .  # + geometry
```

## What this instrument is for

`bridge_gauge.py` settles the **geometry** question offline (1-hop recall fidelity 1.0; the 0-well abstain
lifts 2-hop chord precision 0.96 → 1.00) and then states the limit that has kept Ticket 2 dormant:
executable validity of a direct `A→D` is **not offline-decidable** — only the body settles whether the
skipped steps mattered.

Until 2026-07-30 that limit was moot, because the bridge was parked for a *thermodynamic* reason instead:
the ≥2-note tail read 8.9% and was judged too thin to feed a bridge. Re-measurement killed that reason
(**26.5% of 2,383 injected segments**, `results/declarative_tail_v1/`), which left this instrument as the
only thing in the way. This is it.

## The design, and the asset that expires

A bridge's lifecycle is already the experiment: `proposed` → `offered` → `confirmed` (A and D both credited
in one `exit 0`) | `scarred`. The gauge therefore runs in two phases, and the first is available **today,
with the organ still off**.

`declarative.bridge.mode` has never been anything but `off`, and no `wiki_bridges.json` has ever existed.
So **every** note→note transition in the live record was earned with no bridge ever offered: the entire
history is a clean control arm. That is a one-shot asset — it stops being clean the moment the organ is
flipped on — which is why an underpowered flip is treated here as a `−1`-adjacent mistake rather than a
cheap experiment.

The control it yields:

> **BASE RATE** — of the (A,D) pairs that were bridge *candidates* (2-hop reachable, no direct edge), what
> fraction later acquired a direct `A→D` edge **anyway**, with nothing offered?

Ordering comes from the **F3 per-edge provenance stamps** — a pair counts as spontaneously resolved only
if both legs of a 2-hop path predate the direct edge. Unstamped legacy edges are **excluded and reported**,
never assumed in either direction. (F3's readout flip on the same day is what makes this computable at all;
before it, coverage was 0%.)

## Phase A reading — 2026-07-30

| | |
|---|---|
| real note→note transitions | **522** over 83 classes |
| bridge candidates still open | **475** |
| candidates resolved spontaneously | **29** |
| excluded, ordering unknowable | 61 |
| **BASE RATE (what a live arm must beat)** | **5.75%** (n=504) |
| offers needed to detect +15pp | **~79 settled** (α=0.05, power=0.80) |

Densest classes: `55aac8a-minilm#147` (35 open / 3 resolved), `worthwhile-release#143` (27/1),
`recommend-proce#49` (24/2), `skill-injection#54` (23/1).

**A 5.75% base rate is good news for the experiment.** The body rarely makes these jumps on its own, so
there is real headroom for an offered chord to show a lift — and ~79 settled offers is reachable on this
store's traffic rather than aspirational.

## Geometry reading — and a false −1 caught in the build

Running the organ's own `synthesize(..., save=False)` over the live vault produced **32** gated proposals:

| class | count |
|---|---|
| already a real transition | 1 |
| grounded shortcut (D reachable from A) | 2 |
| **invented** (both endpoints credited, no route between them) | **0** |
| unseen endpoint (no credited history at all) | 29 |

An earlier draft of this gauge scored chords against a **single class's** edges and read **32/32
ungrounded**, which its own falsifier would have reported as a `−1` **against the organ**. Two denominator
errors were doing that work:

1. `synthesize` proposes over the **whole vault graph**, so scoring against one colony is the wrong
   denominator. Fixed to the union of note transitions across all classes.
2. A chord whose endpoint has **never been credited at all** cannot be called an invention — the vault
   holds ~2,460 nodes and only **146** notes appear anywhere in the credited record. That is a coverage
   fact about the vault, not evidence about geometry.

With both fixed, the invented count is **0 of 3 scoreable**. The honest verdict is that geometry quality
is **unscoreable on this store**, not that it is bad. Recorded because the near-miss is the useful part:
the falsifier was one denominator away from parking an organ for the wrong reason.

## Verdict

**`0` · READY-TO-FLIP (pre-flight only).** Nothing is claimed about bridge validity yet — that requires the
live arm. The instrument the organ was waiting on now exists, and it says the experiment is powered enough
to be worth running.

Next step is a **local** `declarative.bridge.mode = suggest` (gitignored, committed default stays `off`),
then re-run this gauge for the Phase-B readout.

### Pre-registered falsifier (frozen here, before the live arm opens)

- **−1, park the organ permanently** — the live confirm rate does not exceed the **5.75%** base rate above.
  A bridge that only takes credit for jumps the body would have made anyway earns nothing for its context
  cost.
- **−1** — invented proposals dominate the scoreable set (>50%).
- **0** — fewer than ~79 settled offers: not yet decidable, keep accruing.
- **+1** — confirm rate clears the base rate at that power, **on a repo whose task mix was not chosen for
  the organ**. Self-selected evidence is how the ranked-proposer efficacy claim was lost; it will not be
  accepted here either.

Quote the base rate with its date and n. The store is live, and this number will move.
