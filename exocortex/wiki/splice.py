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
    atomically: the delivery-budget probe (DELIVERY_BUDGET_PROBE, 2026-07-08) showed a
    block-unit budget delivers the first blocks of a multi-block note — truncated tissue that cannot
    satisfy the task, cannot earn τ, and reads as noise to the tuner. Total exploration bytes stay bounded
    by ``explore_block_cap`` blocks (the one stated place a note may still truncate — at the cap, loudly
    documented, not silently at budget).

Numpy-free and fail-open.
"""

from __future__ import annotations

from ..colony import PRUNE, _SEP
from ..config import explore_rotate_enabled
from ..genome import GENOME
from .node import ExonNode, NodeId, WikiGraph

_D = GENOME.get("declarative", {}) or {}
EXPLORE_BUDGET = int(_D.get("explore_budget", 0))     # dormant by default (0 → splice stays pure)
MAX_EXONS = int(_D.get("max_exons", 20))
EXPLORE_BLOCK_CAP = int(_D.get("explore_block_cap", 32))  # total explore blocks per splice (byte bound)


def _offers() -> dict:
    """The persisted per-note explore-offer counts (F2). Imported lazily so ``splice`` keeps no import
    cycle with ``store`` and a missing/corrupt ledger simply reads as 'nothing offered yet'."""
    try:
        from .store import load_offers
        return load_offers()
    except Exception:
        return {}


def _record_offers(explore_nodes: list, graph: WikiGraph, floor: float) -> None:
    """Bump the offer count for every NOTE just admitted to the exploration channel, and drop the counter
    for any note that has since earned τ (it has graduated out of the explore pool — its history of
    failed offers is no longer interesting). Fail-open: bookkeeping never breaks a splice.

    (This re-reads the ledger that ``_select`` just read. Deliberate: the file is sub-KB, the two reads
    cost ~0.1 ms against a ~76 ms ``load_graph``, and threading the dict through would buy nothing
    measurable at the price of a wider signature.)

    SEMANTICS, deliberate: the ledger is GLOBAL while τ is PER-CLASS (the splice loads
    ``colony_<class>.json``). So a note that earns τ in ANY class has its offer history cleared for ALL of
    them — a note that proved useful somewhere gets a fresh hearing everywhere. The alternative (a ledger
    per class) would re-fatigue the same note independently in each of 146 classes, which is the behaviour
    F2 exists to stop."""
    if not explore_nodes:
        return
    try:
        from .store import load_offers, save_offers
        offers = load_offers()
        for n in explore_nodes:
            doc = n.id.partition("#")[0]
            offers[doc] = offers.get(doc, 0) + 1
        # Graduated notes: derive the τ-bearing docs from the COLONY's edge keys (small — thousands), never
        # by scanning graph.nodes (TAO carries 194k of them; that scan would be a new hot-path cost).
        colony = graph.colony
        earned: set = set()
        for edge in (getattr(colony, "tau", None) or {}):
            for nid in edge.split(_SEP):
                if "#" in nid:
                    earned.add(nid.partition("#")[0])
        for doc in earned:
            offers.pop(doc, None)                       # graduated — forget the failed-offer history
        save_offers(offers)
    except Exception:
        pass


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
        # Eligible sub-floor blocks, grouped by NOTE, keeping each note's first proposer position.
        eligible: dict[str, list] = {}
        doc_pos: dict[str, int] = {}
        for pos, nid in enumerate(cands):
            if nid in graph.scars or nid in chosen:
                continue
            node = graph.nodes.get(nid)
            if node is None or node_tau(colony, nid) >= floor:
                continue                                        # only genuinely un-earned tissue explores
            doc = nid.partition("#")[0]                         # NodeId = relpath#heading:ix → the note
            eligible.setdefault(doc, []).append(node)
            doc_pos.setdefault(doc, pos)

        # F2: admission ORDER. "order" = the pre-fix behaviour (proposer order, no memory) which re-offered
        # the same never-credited notes every turn. "rotate" = least-offered-first, so tissue that has
        # repeatedly failed to earn τ sinks below fresher candidates. Nothing is banned: when every note is
        # equally tired the order is still the proposer's, so exploration never stalls.
        docs = sorted(eligible, key=lambda d: doc_pos[d])
        if docs and explore_rotate_enabled():
            ledger = _offers()                                  # one read per splice; reused on write
            docs.sort(key=lambda d: (ledger.get(d, 0), doc_pos[d]))

        for doc in docs[:budget]:                               # budget counts notes, not blocks
            for node in eligible[doc]:
                if len(explore_nodes) >= EXPLORE_BLOCK_CAP:
                    break                                       # the stated byte bound — never silent
                explore_nodes.append(node)                      # every proposed block of an admitted note
        explore_nodes.sort(key=lambda n: (n.span[0] if n.span else 0, n.id))
    return top, explore_nodes


def splice_with_ids(
    graph: WikiGraph,
    candidate_node_ids,
    *,
    max_exons: int | None = None,
    tau_floor: float | None = None,
    explore: int | None = None,
    record_offers: bool = True,
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
        # Only the LIVE hook path keeps the ledger. `splice_payload` (the read-only MCP surface, and every
        # test that renders a payload) passes record_offers=False — otherwise merely RENDERING a splice
        # mutates the organism's state, which is the same "retrieval must not pay" law the τ lane obeys.
        if explore_nodes and record_offers and explore_rotate_enabled():
            _record_offers(explore_nodes, graph, floor)
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
    return splice_with_ids(graph, candidate_node_ids, max_exons=max_exons, tau_floor=tau_floor,
                           explore=explore, record_offers=False)[0]   # rendering must not mutate state
