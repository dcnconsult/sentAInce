"""The endocrine system (organ 3A) — allostatic thermodynamics keyed by the metabolic tier.

Hormones globally re-tune the physical rules of memory based on systemic stress: under HYPOXIA the prune
floor rises and the per-class cap falls (tunnel-vision — shed exploration, stay lean); when SATED the
floor drops and the cap rises (dream — keep exploratory edges for the Hippocampus to bridge later). The
metabolic read is the interoceptive energy tier (``SessionState.tier()``) — a thrash proxy today; a real
cgroup reader is the later additive swap (the ``MetabolicLedger.reader`` was designed for it).

GAUGE-VERIFIED before wiring (``gauge/endocrine_gauge.py``, seeds 1/2/7/13): tier-stepped is SAFE — it
never evicts a converged OR a marginal real route at the shipped envelope (HYPOXIA prune=0.12 ≤ the 0.15
knee; cap=16 ≥ skeleton-size + margin). Its clutter benefit is modest (DECAY already does most of the
work), so this ships **dormant by default** (``endocrine.mode = "off"`` → the static constants) and is
flipped to ``"tier"`` once live-verified — the same ship-dormant pattern the embedding classifier used.

The colony stays a pure mechanism: the HOOK reads ``levers(tier)`` and passes ``(prune, cap)`` into
``Colony.deposit``/``consolidate`` (both default to the static module constants when given nothing — so
this is fully additive and backward compatible, and tests can still monkeypatch ``colony.PRUNE``/``CAP``).
"""
from __future__ import annotations

from .genome import GENOME


def levers(tier: str, genome: dict | None = None) -> tuple[float, int]:
    """The allostatic ``(prune_floor, max_edges)`` for a metabolic ``tier`` ("SATED"|"STARVING"|"HYPOXIA").

    ``endocrine.mode == "off"`` (or any unknown tier / malformed config) → the static colony constants,
    i.e. the verified baseline. ``"tier"`` → the per-tier values from the Genome. Fail-safe: ANY error
    falls back to the static constants — the endocrine organ must never destabilize the colony."""
    from .colony import PRUNE, CAP   # the static defaults AND the test monkeypatch surface (read live)
    g = genome if genome is not None else GENOME
    try:
        endo = g.get("endocrine", {}) or {}
        if str(endo.get("mode", "off")).lower() != "tier":
            return PRUNE, CAP
        t = (endo.get("tiers") or {}).get(tier)
        if not t:
            return PRUNE, CAP
        return float(t.get("prune_floor", PRUNE)), int(t.get("max_edges_per_class", CAP))
    except Exception:
        return PRUNE, CAP
