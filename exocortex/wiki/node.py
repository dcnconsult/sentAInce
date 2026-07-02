"""The in-RAM data structure for a Markdown wiki — NEXT_PHASE_PLAN §6, Wave-2 Ticket 1.

Physics-first partition of a Markdown corpus into MATTER vs. EARNED STATE.

MATTER (rebuildable, derived from the source file) lives on ``ExonNode`` — the paragraph/block
atom: raw text, its Z3 phasor cache, structural address, content hash. All of it is a *cache*:
re-deriving it from the markdown is cheap and lossless, so it is NEVER the source of truth, and
re-digesting a rotted doc may rebuild it freely.

EARNED STATE (irreplaceable, consequence-sourced) lives OFF the node, in ``WikiGraph``, walled
away from the digester so retrieval can never forge it:
  * utility  tau  -> a ``Colony`` keyed by note-transition edges (reuse ``exocortex.colony``
                     verbatim). Deposited ONLY on a closed note->...->exit 0 chain. The crown jewel:
                     popularity is not utility, so reading a note must NOT pay it.
  * immunity sigma -> the scar set: NodeIds an ``exit 1``-after-use marked doc-rot / toxic.
                     Immortal; never pruned, never silently resurrected.

This split is the *structural* enforcement of consequence-sourcing: the digester writes ``text``
and ``phasor`` but physically cannot touch ``tau``/``sigma`` (they do not live on the node it sees).

Two operating lanes, two clocks:
  scalar lane (tau, sigma)  : plain dict/float/set — numpy-free, available every hook, fail-open.
  vector lane (phasor)      : a contiguous (N, M) int8 bank — materialized ONLY inside PreCompact,
                              where numpy is permitted; fed to ``tam`` / ``phase_router`` /
                              ``epistemic_gate``. The NodeId is the join key between lanes.
The per-tool hot path never imports numpy; the sleep cycle does. That boundary is load-bearing.

GROUNDING (verified 2026-06-27, do not re-assume the manifesto's version tags):
  * The bridge gate is the HDC 0-well abstain ``freqos.epistemic_gate`` (v0.55) — NOT an NLI model
    (the manifesto's "v0.93 NLI Gate" is absent here). It is a *gauge over phasor probes*, which is
    exactly why this structure exposes ``phasor_bank`` as a contiguous matrix.
  * Doc-rot starts CONSEQUENCE-ONLY (a scar on exit-1-after-use); the "does reality contradict the
    text" NLI layer is a later, optional, heavy addition — not the entry point.
  * The Hippocampus bridge (Ticket 2) is gated on the bridge-validity gauge passing FIRST. This
    structure is bridge-*ready* (phasor_ix + links) but commits to no autonomous crystallization.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # imports kept out of the numpy-free hot path
    import numpy as np

    from ..colony import Colony


# A NodeId is a stable, human-legible address: f"{relpath}#{heading_path}:{block_ix}".
# Stable across re-digests of unchanged text so earned tau/sigma survive a rebuild.
NodeId = str


@dataclass(slots=True)
class ExonNode:
    """One paragraph/block of markdown — the unit of BOTH prune (Enzymes) and bridge (Hippocampus).

    Pure rebuildable matter: every field is derivable from the source file, so a node is a *cache*,
    not state. The irreplaceable earned state (tau, sigma) lives in ``WikiGraph``, keyed by ``id``.
    """

    id: NodeId
    text: str                          # the raw block — the candidate "exon" for splicing
    heading_path: tuple[str, ...] = () # neocortical address, e.g. ("Architecture", "Colony")
    span: tuple[int, int] = (0, 0)     # (start_line, end_line) for surgical re-inject / re-digest
    links: tuple[NodeId, ...] = ()     # outgoing [[wikilinks]] resolved to NodeIds (declarative edges)
    content_hash: str = ""             # set via fingerprint(); doc-rot + tau-resurrection guard
    phasor_ix: int | None = None       # row into WikiGraph.phasor_bank; None until digested (lazy)

    def fingerprint(self) -> str:
        """Content hash of the block. A mismatch on re-digest means the text changed -> the node's
        earned tau must be re-EARNED, not carried over (the structural anti-resurrection guard)."""
        return hashlib.blake2b(self.text.encode("utf-8"), digest_size=16).hexdigest()


@dataclass
class WikiGraph:
    """The daemon's whole in-RAM corpus: many files shredded to nodes (matter), the two earned-state
    stores (tau via Colony, sigma via the scar set), and a lazily-built phasor bank for the
    sleep-cycle Hippocampus. The hot path uses only ``nodes`` / ``colony`` / ``scars`` (numpy-free);
    ``phasor_bank`` is touched only in PreCompact.
    """

    nodes: dict[NodeId, ExonNode] = field(default_factory=dict)
    colony: "Colony | None" = None                  # tau lane: note-transition pheromone (consequence-only)
    scars: set[NodeId] = field(default_factory=set) # sigma lane: immortal doc-rot / toxic marks
    phasor_bank: "np.ndarray | None" = None         # (N, M) int8 — built ONLY in PreCompact

    # ------------------------------------------------------------------ structure (numpy-free)
    def add(self, node: ExonNode) -> None:
        if not node.content_hash:
            node.content_hash = node.fingerprint()
        self.nodes[node.id] = node

    def live(self) -> list[ExonNode]:
        """Nodes that are not scarred — the candidate surface for splicing. (tau-ranking, i.e. the
        forage-by-utility ordering, is applied by the splicer against ``colony``, not here.)"""
        return [n for nid, n in self.nodes.items() if nid not in self.scars]

    def scar(self, node_id: NodeId) -> None:
        """Drop an immortal doc-rot / toxic mark (consequence path only: exit-1-after-use)."""
        self.scars.add(node_id)

    # ------------------------------------------------------- bridge lane (numpy, PreCompact only)
    def build_phasor_bank(self, encode: "Callable[[str], np.ndarray]") -> "np.ndarray | None":
        """Materialize the contiguous (N, M) Z3 phasor matrix for tam / phase_router / epistemic_gate.

        ``encode(text) -> (M,) int8 in {0,1,2}`` is the Digestive System (embed -> ``tam._phase_of``).
        Called ONLY in the PreCompact sleep cycle; numpy is imported lazily here so importing this
        module never pulls numpy onto the per-tool hot path. Scarred nodes are excluded — a bridge
        must never route through tissue immunity has already rejected.
        """
        import numpy as np

        rows = []
        for node in self.nodes.values():
            if node.id in self.scars:
                node.phasor_ix = None
                continue
            vec = encode(node.text)             # fail-open (encode_phasor returns None on failure)
            if vec is None:
                node.phasor_ix = None
                continue
            node.phasor_ix = len(rows)
            rows.append(np.asarray(vec, dtype=np.int8))
        self.phasor_bank = np.stack(rows).astype(np.int8) if rows else None
        return self.phasor_bank
