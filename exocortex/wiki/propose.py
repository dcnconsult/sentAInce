"""The Candidate Proposer — the fast-path graze list for the Transcriptome (NEXT_PHASE_PLAN §6, Ticket 1).

Retrieval PROPOSES; τ DISPOSES. This casts a cheap, high-recall net of candidate NodeIds; precision is
bought downstream by ``splice_payload``'s τ-floor + σ-veto, so the proposer can afford to be broad. The
candidate ORDER is relevance order — the splice's exploration channel draws its bootstrap picks from the
front (the most-relevant un-tried notes first).

Four layered signals, unioned (recall) and capped at ``proposer_k``:
  1. structural spreading-activation — from the active context (notes used/verified recently), expand
     ``link_hops`` of ``[[links]]`` across the graph (the hippocampal "place field" expansion).
  2. lexical reflex — notes whose heading / doc-name tokens appear in the prompt.
  3. dense lift (OPTIONAL, embed-mode only) — HDC overlap of the prompt's phasor against the phasor bank,
     REUSING a prompt embedding already computed by the cue-classifier (never a second MiniLM load).
  4. muscle-memory floor — the top global-τ notes, so a cold prompt still offers the verified skeleton.

Layers 1/2/4 are numpy-free (the always-on path). Layer 3 is the only numpy path and is strictly opt-in
(supply ``prompt_embedding`` AND have a PreCompact-built ``phasor_bank``); without it the hot path never
touches numpy. Fail-open throughout: any error yields ``[]``.
"""

from __future__ import annotations

import math
import re

from ..colony import _SEP
from ..config import lexical_rank_enabled
from ..genome import GENOME
from .node import NodeId, WikiGraph

_D = GENOME.get("declarative", {}) or {}
PROPOSER_K = int(_D.get("proposer_k", 24))
LINK_HOPS = int(_D.get("link_hops", 1))

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
# Corpus size above which the IDF pass is skipped (see `_idf`): the build is ~28 ms per 4k nodes and one
# hook is one process, so a 194k-node vault would pay ~1.4 s per turn for rarity weighting alone.
IDF_MAX_NODES = int(_D.get("idf_max_nodes", 20000))


def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _doc_of(node_id: NodeId) -> str:
    return node_id.split("#", 1)[0]


def _index_by_doc(graph: WikiGraph) -> dict:
    """doc-name (with and without extension, lowercased) → [NodeId], for resolving [[links]] to nodes."""
    idx: dict = {}
    for nid in graph.nodes:
        doc = _doc_of(nid).lower()
        for key in (doc, doc.rsplit(".", 1)[0]):
            idx.setdefault(key, []).append(nid)
    return idx


def _resolve(idx: dict, target: str) -> list:
    t = (target or "").lower()
    return idx.get(t) or idx.get(t + ".md") or []


def _structural(graph: WikiGraph, active: list, hops: int) -> list:
    """Spreading activation: BFS the [[link]] graph outward from the active context, ``hops`` deep."""
    if not active:
        return []
    idx = _index_by_doc(graph)
    seen = set(active)
    frontier = [n for n in active if n in graph.nodes]
    out: list = []
    for _ in range(max(1, hops)):
        nxt: list = []
        for nid in frontier:
            node = graph.nodes.get(nid)
            if node is None:
                continue
            for target in node.links:
                for resolved in _resolve(idx, target):
                    if resolved not in seen:
                        seen.add(resolved)
                        out.append(resolved)
                        nxt.append(resolved)
        frontier = nxt
        if not frontier:
            break
    return out


def _surface(nid: NodeId, node) -> set:
    """A node's lexical surface — its doc-name tokens plus every heading-path token. This is the ONLY
    text the lexical layer matches against (never the block body), so it stays cheap on the hot path."""
    hay: set = set(_tokens(_doc_of(nid)))
    for h in node.heading_path:
        hay |= _tokens(h)
    return hay


def _idf(graph: WikiGraph) -> dict:
    """token → log(N / df) over the corpus's lexical surface, cached on the graph for this process.

    Rarity is the whole point: a prompt token like "run" or "summary" appears in most surfaces and
    carries almost no signal, while "endocrine" or "colony" identifies a handful of notes. Weighting by
    IDF is what stops the generic tokens from deciding the splice.

    COST CEILING: building this is one extra O(N) pass over the corpus surface — measured at ~28 ms on a
    3,980-node vault, against ``load_graph``'s ~76 ms. It scales linearly, so on the largest vault we
    measured in the estate (194,502 nodes) it would add ~1.4 s to EVERY hook. Above ``IDF_MAX_NODES`` we therefore return {} and
    the ranker falls back to uniform weights — still relevance-ordered by match count and surface
    specificity (which is what fixes the alphabetical monopoly), just without rarity weighting, and at
    zero added cost. Degrade the scoring, never the latency."""
    cached = getattr(graph, "_lex_idf", None)
    if cached is not None:
        return cached
    if len(graph.nodes) > IDF_MAX_NODES:
        idf: dict = {}
    else:
        df: dict = {}
        n = 0
        for nid, node in graph.nodes.items():
            n += 1
            for t in _surface(nid, node):
                df[t] = df.get(t, 0) + 1
        idf = {t: math.log(max(1.0, n / c)) for t, c in df.items()} if n else {}
    try:
        graph._lex_idf = idf        # WikiGraph is a non-slots dataclass; a cache attr is safe
    except Exception:
        pass                        # never let a caching failure break the proposer
    return idf


def _lexical(graph: WikiGraph, prompt: str) -> list:
    """Notes whose heading-path or doc-name tokens overlap the prompt's tokens.

    F1 (2026-07-24 log audit): this used to return matches in vault FILE order, which meant
    ``propose``'s ``proposer_k`` cap did all the selecting — and it selected ALPHABETICALLY, so
    ``.claude/skills/*`` monopolised every splice while genuinely relevant notes were truncated away
    (2,313 matches → 24 kept, none of them the ones the prompt was about). Ranked mode scores each match
    by summed IDF over the matched tokens, normalised by sqrt(|surface|) so a note with a long heading
    path cannot win on breadth alone. Ties break on corpus position, so the order stays deterministic.
    Set ``lexical_rank="file"`` (or ``EXOCORTEX_LEXICAL_RANK=0``) to restore the old behaviour exactly."""
    toks = _tokens(prompt)
    if not toks:
        return []
    if not lexical_rank_enabled():
        out: list = []
        for nid, node in graph.nodes.items():
            if _surface(nid, node) & toks:
                out.append(nid)
        return out
    idf = _idf(graph)
    scored: list = []
    for pos, (nid, node) in enumerate(graph.nodes.items()):
        hay = _surface(nid, node)
        matched = hay & toks
        if not matched:
            continue
        # Uniform weight 1.0 when the IDF map is absent (corpus over the cost ceiling) — the ranking then
        # reduces to match-count over surface specificity, which still beats file order outright.
        score = sum(idf.get(t, 1.0) for t in matched) / math.sqrt(len(hay) or 1)
        scored.append((-score, pos, nid))
    scored.sort()
    return [nid for _s, _p, nid in scored]


def _muscle_memory(graph: WikiGraph, k: int) -> list:
    """The top global-τ notes — the organism's verified skeleton, for a cold/irrelevant prompt."""
    col = graph.colony
    if col is None or not getattr(col, "tau", None):
        return []
    out: list = []
    seen: set = set()
    for edge, _w in col.top(max(1, k) * 2):
        for nid in edge.split(_SEP):
            if nid in graph.nodes and nid not in seen:
                seen.add(nid)
                out.append(nid)
                if len(out) >= k:
                    return out
    return out


def _dense(graph: WikiGraph, prompt_embedding, k: int) -> list:
    """OPTIONAL numpy lift: HDC overlap of the prompt phasor vs the phasor bank, reusing an already-
    computed prompt embedding. Returns [] (fail-open) without a bank / kernel / numpy."""
    try:
        bank = getattr(graph, "phasor_bank", None)
        if bank is None:
            return []
        import numpy as np

        from .digest import _ensure_freqos, _projection

        if not _ensure_freqos():
            return []
        from freqos.tam import _phase_of

        emb = np.asarray(prompt_embedding, dtype=float)
        q = _phase_of(_projection(emb.shape[0]) @ emb)        # prompt phasor (M,)
        sims = (np.asarray(bank) == q).mean(axis=1)           # (N,) Z3-label overlap
        order = np.argsort(-sims)[: max(1, k)]
        ix_to_id = {n.phasor_ix: nid for nid, n in graph.nodes.items() if n.phasor_ix is not None}
        return [ix_to_id[int(i)] for i in order if int(i) in ix_to_id]
    except Exception:
        return []


def propose(
    graph: WikiGraph,
    prompt: str = "",
    active_context: list | None = None,
    *,
    k: int | None = None,
    hops: int | None = None,
    prompt_embedding=None,
) -> list:
    """Union the relevance signals into an ordered, de-duped, σ-filtered candidate list (cap ``k``).

    Order = structural → lexical → dense → muscle-memory (most-relevant first; the floor last). Pass
    ``prompt_embedding`` only in embed-mode (reuse the classifier's vector) to enable the dense lift.
    """
    try:
        cap = PROPOSER_K if k is None else k
        depth = LINK_HOPS if hops is None else hops
        ordered: list = []
        seen: set = set()

        def add(ids):
            for nid in ids:
                if nid in graph.nodes and nid not in seen and nid not in graph.scars:
                    seen.add(nid)
                    ordered.append(nid)

        add(_structural(graph, active_context or [], depth))
        add(_lexical(graph, prompt))
        if prompt_embedding is not None:
            add(_dense(graph, prompt_embedding, cap))
        add(_muscle_memory(graph, cap))
        return ordered[:cap]
    except Exception:
        return []
