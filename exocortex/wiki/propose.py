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

import re

from ..colony import _SEP
from ..genome import GENOME
from .node import NodeId, WikiGraph

_D = GENOME.get("declarative", {}) or {}
PROPOSER_K = int(_D.get("proposer_k", 24))
LINK_HOPS = int(_D.get("link_hops", 1))

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


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


def _lexical(graph: WikiGraph, prompt: str) -> list:
    """Notes whose heading-path or doc-name tokens overlap the prompt's tokens."""
    toks = _tokens(prompt)
    if not toks:
        return []
    out: list = []
    for nid, node in graph.nodes.items():
        hay: set = set(_tokens(_doc_of(nid)))
        for h in node.heading_path:
            hay |= _tokens(h)
        if hay & toks:
            out.append(nid)
    return out


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
