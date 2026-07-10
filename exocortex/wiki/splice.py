"""The Transcriptome Spliceosome — exon injection by earned τ, with bootstrap exploration (NEXT_PHASE_PLAN §6, Ticket 1).

The RNAi step: given candidate notes (from the proposer), use τ as the SURVIVAL FILTER (slime-mold
evaporation below the prune floor + the σ Liver veto), keep the strongest, then RE-ENTRAIN to document
order so the stateless Cortex receives coherent context instead of a τ-ranked Frankenstein.

Laws encoded here:
  * Retrieval proposes; τ disposes. Similarity only nominates candidates; what gets injected is decided by
    consequence-earned τ. Popularity (cosine) never becomes utility — the crown jewel.
  * Abstain into silence. With no verified tissue (and no exploration), the splice returns "" — the truest
    0-well behavior; we never speak unverified declarative memory into the void.
  * Bootstrap by exploration (dormant by default). The τ-floor deadlocks a fresh wiki (a note can't earn τ
    until used, used until injected, injected until it has τ). When ``explore_budget`` > 0, trial up to
    that many SUB-FLOOR NOTES (documents) per splice — clearly flagged UNVERIFIED, admitted in the order
    their first block appears in the proposer's relevance order — so a closed exit-0 chain can award them
    their first τ. Ant-colony exploratory edges, made auditable: exploration is an explicit, bounded,
    labelled channel, never a silent lowering of the floor.
  * Never a partial note. The budget counts NOTES, and an admitted note's proposed blocks inject
    atomically: the delivery-budget probe (sentAInce-lab, DELIVERY_BUDGET_PROBE.md, 2026-07-08) showed a
    block-unit budget delivers the first blocks of a multi-block note — truncated tissue that cannot
    satisfy the task, cannot earn τ, and reads as noise to the tuner. Total exploration bytes stay bounded
    by ``explore_block_cap`` blocks (the one stated place a note may still truncate — at the cap, loudly
    documented, not silently at budget).

Numpy-free and fail-open.
"""

from __future__ import annotations

from ..colony import PRUNE, _SEP
from ..genome import GENOME
from .node import ExonNode, NodeId, WikiGraph

_D = GENOME.get("declarative", {}) or {}
EXPLORE_BUDGET = int(_D.get("explore_budget", 0))     # dormant by default (0 → splice stays pure)
MAX_EXONS = int(_D.get("max_exons", 20))
EXPLORE_BLOCK_CAP = int(_D.get("explore_block_cap", 32))  # total explore blocks per splice (byte bound)


def node_tau(colony, node_id: NodeId) -> float:
    """A note's earned utility = Σ τ over the colony edges incident to it. Per-edge τ is the colony's
    native unit; a note inherits the consequence that flowed THROUGH it (as source or destination of a
    verified transition). Fail-safe to 0.0 (→ abstain) when there is no colony / no pheromone."""
    if colony is None or not getattr(colony, "tau", None):
        return 0.0
    total = 0.0
    for k, w in colony.tau.items():
        a, _, b = k.partition(_SEP)
        if a == node_id or b == node_id:
            total += w
    return total


def _render(node: ExonNode, tau: float, kind: str = "exon") -> str:
    head = " / ".join(node.heading_path) if node.heading_path else node.id
    return f"<!-- {kind} · {head} · τ={tau:.2f} -->\n{node.text}"


def _select(graph: WikiGraph, candidate_node_ids, floor: float, cap: int, budget: int):
    """The selection physics, shared by ``splice_payload`` and ``splice_with_ids``. Returns
    ``(top, explore_nodes)`` — the τ-verified exploit set (τ-ranked, capped, then re-entrained to doc
    order) and the sub-floor exploration set. ``budget`` admits whole NOTES (documents) in proposer
    order; an admitted note contributes ALL its proposed sub-floor blocks (note-atomic delivery — the
    delivery-budget sizing law), bounded overall by ``EXPLORE_BLOCK_CAP``."""
    colony = graph.colony
    cands = list(dict.fromkeys(candidate_node_ids or []))       # dedup, preserve proposer relevance order

    surviving: list[tuple[float, int, ExonNode]] = []
    for nid in cands:
        if nid in graph.scars:                                  # σ Liver veto (toxic / rotted tissue)
            continue
        node = graph.nodes.get(nid)
        if node is None:
            continue
        tau = node_tau(colony, nid)
        if tau < floor:                                         # slime-mold: sub-floor matter evaporated
            continue
        surviving.append((tau, node.span[0] if node.span else 0, node))
    surviving.sort(key=lambda x: -x[0])                         # 1) τ survival filter — strongest first
    top = surviving[:cap]
    chosen = {n.id for _, _, n in top}
    top.sort(key=lambda x: (x[1], x[2].id))                     # 2) chronological re-entrainment — doc order

    explore_nodes: list[ExonNode] = []
    if budget > 0:
        admitted: dict[str, None] = {}                          # NOTE (doc) keys, insertion-ordered
        for nid in cands:
            if len(explore_nodes) >= EXPLORE_BLOCK_CAP:
                break                                           # the stated byte bound — never silent
            if nid in graph.scars or nid in chosen:
                continue
            node = graph.nodes.get(nid)
            if node is None or node_tau(colony, nid) >= floor:
                continue                                        # only genuinely un-earned tissue explores
            doc = nid.partition("#")[0]                         # NodeId = relpath#heading:ix → the note
            if doc not in admitted:
                if len(admitted) >= budget:
                    continue                                    # budget counts notes, not blocks
                admitted[doc] = None
            explore_nodes.append(node)                          # every proposed block of an admitted note
        explore_nodes.sort(key=lambda n: (n.span[0] if n.span else 0, n.id))
    return top, explore_nodes


def splice_with_ids(
    graph: WikiGraph,
    candidate_node_ids,
    *,
    max_exons: int | None = None,
    tau_floor: float | None = None,
    explore: int | None = None,
) -> tuple[str, list]:
    """Like ``splice_payload`` but also returns the NodeIds ACTUALLY injected (exploit + explore) — the
    attribution surface (only a note the model could see may later be credited). Returns ("", [])
    on abstain / error."""
    try:
        floor = PRUNE if tau_floor is None else tau_floor
        cap = MAX_EXONS if max_exons is None else max_exons
        budget = EXPLORE_BUDGET if explore is None else explore
        top, explore_nodes = _select(graph, candidate_node_ids, floor, cap, budget)
        if not top and not explore_nodes:
            return "", []
        parts = [_render(n, tau) for tau, _, n in top]
        if explore_nodes:
            parts.append("<!-- exploratory tissue (UNVERIFIED — earns τ only by leading to exit 0) -->")
            parts.extend(_render(n, 0.0, kind="explore") for n in explore_nodes)
        ids = [n.id for _, _, n in top] + [n.id for n in explore_nodes]
        return "\n\n".join(parts), ids
    except Exception:
        return "", []                                           # fail-open: never break the prompt


def splice_payload(
    graph: WikiGraph,
    candidate_node_ids,
    *,
    max_exons: int | None = None,
    tau_floor: float | None = None,
    explore: int | None = None,
) -> str:
    """Splice the consequence-verified declarative tissue for ``candidate_node_ids`` into a context
    payload, optionally appending up to ``explore`` sub-floor exploratory NOTES — each delivered
    note-atomically, never as a partial note (default: the dormant Genome
    ``declarative.explore_budget``). Returns "" (abstain) when nothing survives and nothing is
    explored."""
    return splice_with_ids(graph, candidate_node_ids,
                           max_exons=max_exons, tau_floor=tau_floor, explore=explore)[0]
