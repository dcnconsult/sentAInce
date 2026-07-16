"""The Genome — a single JSON config for every tuning knob of the Exocortex organism.

The thermodynamic (colony) + epistemic (classifier) + somatic (gate) parameters live here instead of
scattered module constants, so longitudinal R&D can re-tune the organism WITHOUT touching code. The
factory loader ingests ``exocortex_config.json`` (searched: ``$EXOCORTEX_CONFIG`` → ``$CLAUDE_PROJECT_DIR``
→ this package dir) and deep-merges it over the **mathematically-verified DEFAULTS** below — so a missing
or partial file falls back to the values this R&D arc established (backward compatible, fail-safe).

Precedence for a given knob: explicit env var (e.g. ``EXOCORTEX_EMBED_MATCH``) > genome JSON > DEFAULTS.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

# The verified genome — every value is the default established + measured in this arc (see
# MEMORY_GAUGE_DESIGN §§6-15). Editing exocortex_config.json overrides any subset of these.
DEFAULTS = {
    "thermodynamics": {
        "decay": 0.9,                    # τ multiplier per deposit (stigmergic evaporation)
        "prune_floor": 0.05,            # §14 eviction lever — below WEIGHT_MIN so weighted deposits survive
        "deposit_base_weight": 1.0,     # full-weight pheromone for a focused deposit
        "session_discount_rate": 0.8,   # §13 per-deposit activity discount (0.8**k) — the thrash catcher
        "weight_min": 0.1,              # floor on a session-weighted deposit
        "max_edges_per_class": 32,      # per-class leanness ceiling (consolidation CAP)
        "min_deposits_to_splice": 2,    # abstain from splicing a class until it has some repetition
    },
    "epistemic_classifier": {
        # semantic (MiniLM embedding) | lexical (TF). LEXICAL is the shipped default — semantic is
        # OPT-IN via `pip install sentaince[embed]` + mode="semantic" (or EXOCORTEX_EMBED=1).
        #
        # Why, since §15 MEASURED semantic's class separation superior (that finding stands, and the
        # 0.45 threshold below is its result): `sentence-transformers` is an EXTRA, not a runtime dep,
        # so a plain `pip install sentaince` cannot honour a "semantic" default — `available()` is False
        # and the hook silently falls through to lexical. The old default therefore meant "use MiniLM iff
        # it happens to be in your venv": unreachable for most, and an unrequested tax for anyone who has
        # torch installed for unrelated work. MEASURED on this hot path (issue #4): ~10s on EVERY prompt
        # vs 0.15s lexical — 65x, and NOT a cold-start artifact (each hook is a fresh process, so
        # `embed_classifier._MODEL`'s singleton never survives; a fully-warm second run still cost 9.8s).
        # A gauge that measured accuracy and not cost cannot settle a default. So: declare the dep, make
        # the cost opt-in, and keep the measured quality available to anyone who wants to pay for it.
        # The cold->lexical/warm->semantic PROMOTION rule (issue #4 option B) stays gauge-gated on #11 —
        # this is not that: it is a static, declared default, not a dynamic switch.
        "mode": "lexical",
        "model": "all-MiniLM-L6-v2",    # the embedding model (sentence-transformers; extra "embed")
        "abstain_threshold_cosine": 0.45,  # §15-measured: clean on realistic AND adversarial paraphrases
        #                                    (0.65 fragments; 0.30-0.45 is the verified-good range)
        "match_margin": 0.0,            # top1-top2 commit gate (0 = off)
    },
    "somatic_gate": {
        "mode": "observe",              # observe | somatic | epistemic | full | ungated (alias: enforce→somatic)
    },
    "endocrine": {
        # Allostatic thermodynamics (organ 3A) — make prune_floor/max_edges functions of the metabolic
        # tier instead of static constants. GAUGE-VERIFIED tier-stepped (gauge/endocrine_gauge.py, seeds
        # 1/2/7/13): SAFE (never evicts converged or marginal real routes) but a modest clutter lever.
        # Default "off" = the verified static constants (thermodynamics above). Flip to "tier" to make
        # the Genome alive (the embedding-default pattern: ship dormant, enable after live verification).
        "mode": "off",                  # off | tier
        "tiers": {                      # per-tier (prune_floor, max_edges); HYPOXIA = tunnel-vision.
            #                             prune ceiling ≤0.15 and cap floor ≥ skeleton-size+margin are the
            #                             gauge-measured SAFE envelope; HYPOXIA cap=16 protects every route.
            "SATED":    {"prune_floor": 0.03, "max_edges_per_class": 40},   # dream: keep exploration
            "STARVING": {"prune_floor": 0.05, "max_edges_per_class": 32},   # = the static baseline
            "HYPOXIA":  {"prune_floor": 0.12, "max_edges_per_class": 16},   # shed exploration, stay lean
        },
    },
    "eligibility_trace": {
        # Organ 3D — within-segment credit assignment. Weight each deposited edge by recency-to-consequence
        # (γ^Δ, Δ = steps before exit 0) instead of uniformly, so the "ah-ha" step that preceded success
        # crystallizes while the flailing prefix fades. GAUGE-VERIFIED (gauge/eligibility_gauge.py): isolates
        # the ah-ha + evaporates the panic — single-shot below the prune floor on a flailing/low-weight
        # session — but a NO-OP on short (≤~3-edge) segments, and the real prize is modest (median segment
        # ~2; ~22% ≥4 on the proxy corpus). Ships DORMANT: "off" → uniform deposit (the verified status quo);
        # "trace" → the γ credit trace. Flip after a natural-coding corpus shows enough long flail-then-
        # succeed segments to justify it (the audit's seg_len field captures them live).
        "mode": "off",        # off | trace
        "gamma": 0.80,        # γ eligibility decay (credit ∝ γ^steps-before-exit-0)
    },
    "provenance": {
        # Organ F3 — non-stationarity defense (the "quiet rot-killer"). Stamp each deposited edge with a
        # timestamp (+ a model-id when sourceable) and decay τ AT READOUT by recency (and, later,
        # version-distance), so a stale route that is never re-confirmed fades instead of persisting at full τ
        # forever — the only mechanism that lets reality DEMOTE a route (a partial corrective to false-success
        # amplification) and the prerequisite for W6 shared stigmergy (cross-agent trails need provenance to
        # avoid poisoning). GAUGE-VERIFIED (gauge/nonstationarity_gauge.py, results/nonstationarity_v1): the
        # instrument was ABSENT on the live store (0% model-id / per-edge-ts coverage) → version-distance is
        # UNMEASURABLE retroactively; F3 is a go-forward instrument whose first value is to START recording it.
        # Recording is NON-DESTRUCTIVE — a parallel per-edge `meta{ts,model}` lane; only the READOUT re-ranks.
        # Ships DORMANT: "off" → readout uses the raw τ (the verified status quo, byte-identical); "recency" →
        # τ readout-weight decays by edge age (half-life below); "full" adds the version-distance penalty
        # (INERT until model-id sourcing is wired — the hook stdin contract carries no model field; until then
        # all stamps share model="" → no version term fires). Legacy edges with no stamp are NEVER penalized
        # (fail-open). Re-gauge once provenance accrues (and add class-bucketing to the gauge).
        "mode": "off",                 # off | recency | full
        "recency_halflife_days": 30.0, # τ readout-weight halves every N days of edge age (conservative)
        "version_penalty": 0.5,        # readout multiplier for an edge whose stamped model != the current model
    },
    "integrity": {
        # The cryptographic immune system (ADR-009) — protect FreqOS FROM the host. Ships DORMANT so a stale
        # baseline never bricks dev. mode: off → no checks; warn → audit a frozen-DNA mismatch but continue;
        # enforce → fail-closed `exit 1` (apoptosis) on a mismatch. audit_chain hash-chains new audit records
        # (cheap, fail-open). The locked-DNA glob set is a code-level decision in integrity.py (NOT config-
        # overridable, so an attacker cannot shrink it via the Genome). See docs/ADR.md ADR-009.
        "mode": "off",                  # off | warn | enforce
        "audit_chain": True,            # hash-chain the epigenetic ledger
        "baseline": "",                 # override path to the kernel-lock baseline JSON
    },
    "declarative": {
        # The live declarative wiki organ (NEXT_PHASE_PLAN §6, Ticket 1). Ships DORMANT — the hook touches
        # the wiki only when `mode == "live"` AND a `vault_path` is set (the ship-dormant pattern: enable
        # after gauging attribution precision on the BYO testbed). `EXOCORTEX_DECLARATIVE`/`EXOCORTEX_WIKI_VAULT`
        # env vars override. When off, the live hook behaves EXACTLY as the verified procedural baseline.
        "mode": "off",                  # off | live
        "vault_path": "",               # path to the Markdown vault (empty → dormant even if mode=live)
        # T4 inclusion boundary — which *.md the organ ingests. "all" (default, verified baseline) = every
        # *.md under the vault (rglob). "tracked" = only git-tracked *.md: respects the vault's .gitignore
        # AND excludes untracked junk / submodules; falls OPEN to "all" on a non-git vault / missing git.
        # Committed default stays "all" (ADR-003 — main stays conservative); a large real vault (e.g. TAO)
        # flips to "tracked" as a LOCAL gitignored activation. EXOCORTEX_WIKI_INGEST overrides.
        "ingest": "all",                # all | tracked
        # The wiki proposer + bootstrap exploration (NEXT_PHASE_PLAN §6, Ticket 1). The splice injects
        # only τ-bearing notes (the crown jewel), which DEADLOCKS a fresh wiki: a note can't earn τ until
        # it's used, can't be used until injected, can't be injected until it has τ. The exploration budget
        # breaks it the ant-colony way — trial up to `explore_budget` SUB-FLOOR NOTES per splice,
        # clearly flagged UNVERIFIED, and let a closed exit-0 chain award them their first τ. Ships DORMANT
        # (0 → the verified status quo: splice stays pure, abstains on a cold wiki). Endocrine seam (later,
        # gauge-first, mirrors endocrine.levers): when wired, the budget scales with the metabolic tier
        # (SATED → explore more / "dream"; HYPOXIA → 0 / tunnel-vision). A flat int until then.
        # UNITS ARE NOTES, NOT BLOCKS (sizing fix, 2026-07-09): the lab's delivery-budget probe
        # (sentAInce-lab DELIVERY_BUDGET_PROBE.md) proved a block-unit budget starves multi-block notes —
        # budget=2 injected 2 of the conventions note's 8 blocks, 0/6 full deliveries; budget=8 → 6/6.
        # An admitted note now delivers all its proposed blocks atomically; `explore_block_cap` is the
        # explicit total-blocks byte bound (the one place a note may still truncate, loudly).
        "explore_budget": 0,            # # of sub-floor exploratory NOTES per splice (0 = off/dormant)
        "explore_block_cap": 32,        # total explore BLOCKS per splice — bounds payload bytes
        "max_exons": 20,                # splice injection ceiling (verified tissue)
        "proposer_k": 24,               # candidate cap the proposer returns before τ/σ filtering
        "link_hops": 1,                 # structural spreading-activation depth from the active context
        "attribution": {
            # Used-note attribution (#2): credit τ ONLY to notes whose distinctive content (code / inline
            # / path tokens) echoes in the exit-0 segment's actions — never merely because injected (that
            # would reward retrieval). Biases to PRECISION: a prose-only note has no salient tokens → never
            # action-credited (safe under-credit). `min_overlap` is the precision lever (raise to demand
            # more echo). `prose_echo` is the dormant, claim-grounded tier (scan last_assistant_message at
            # Stop, discounted weight) — only enable if action-echo under-credits. min_overlap=2 is the
            # PRECISION-FIRST setting from gauge/attribution_gauge.py (synthetic: min_overlap=1 → precision
            # 0.79 from coincidental echo on shared tokens like git/kubectl; =2 → precision 1.0, recall 0.45
            # recovered by exploration + repeat-exposure). Revalidate on real BYO runs before trusting.
            "min_overlap": 2,
            "prose_echo": False,
        },
        "bridge": {
            # Hippocampus bridge organ (Ticket 2, §6A) — SUGGEST-THEN-VERIFY. In sleep, geometry PROPOSES a
            # provisional A→D link over the wiki's semantic phasors; the 0-well abstain gates it; the LIVE
            # session walks it (A then D both used in one exit-0 segment); exit-0 CRYSTALLIZES τ, exit-1/no-pay
            # SCARS σ. NEVER autonomous crystallization. Ships DORMANT (mode off) — see
            # docs/BRIDGE_ORGAN_DESIGN.md + results/bridge_gauge_v1/ (gauge: precision 0.96→1.0 with the abstain).
            # Flip to "suggest" only after the Ticket-1 soak shows bridgeable (multi-note) declarative routes.
            "mode": "off",                  # off | suggest
            "top_k": 4,                     # candidate D's per source A at synthesis
            "abstain_conf": 0.14,           # 0-well familiarity wall (epistemic_gate WALL_BUNDLE)
            "abstain_margin": 0.03,         # min gap over the runner-up (a confident basin, not a tie)
            "max_provisional": 32,          # cap on live provisional bridges
            "offer_cap": 2,                 # max provisional bridges surfaced per splice (anti-clutter)
            "scar_after_k_walks": 3,        # offered-and-used K times with no exit-0 pay → scar
        },
    },
}

_SOMATIC_ALIAS = {"enforce": "somatic", "off": "observe"}


def _deep_merge(base: dict, over: dict) -> dict:
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        elif k in base:                 # only accept KNOWN keys (ignore typos / unknown knobs)
            base[k] = v
    return base


def _locate() -> Path | None:
    env = os.environ.get("EXOCORTEX_CONFIG")
    if env and Path(env).is_file():
        return Path(env)
    cands = []
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        cands.append(Path(proj) / "exocortex_config.json")
    cands.append(Path(__file__).resolve().parent / "exocortex_config.json")   # shipped default
    for c in cands:
        if c.is_file():
            return c
    return None


def load_genome() -> dict:
    """The verified DEFAULTS deep-merged with the located JSON (if any). Fail-safe: any error → DEFAULTS."""
    g = copy.deepcopy(DEFAULTS)
    p = _locate()
    if p is not None:
        try:
            _deep_merge(g, json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass   # malformed config must never break the organism — fall back to defaults
    sm = str(g["somatic_gate"].get("mode", "observe")).lower()
    g["somatic_gate"]["mode"] = _SOMATIC_ALIAS.get(sm, sm)
    return g


GENOME = load_genome()   # loaded once per process (each hook is a fresh process → re-reads the file)
