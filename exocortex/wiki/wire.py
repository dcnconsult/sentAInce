"""The Bloodstream — wire physical consequence (POSIX exit code) into declarative τ (NEXT_PHASE_PLAN §6, Ticket 1).

This is the crown-jewel law made executable for the declarative substrate. It reuses the procedural
``Colony`` VERBATIM as the τ lane: a wiki "note-trail" (the ordered NodeIds the LLM actually used this
segment) is exactly a colony trail, so ``edges(trail) -> Colony.deposit`` lays consequence-sourced
pheromone over note→note transitions with no new physics.

  * exit 0  → the note→…→exit-0 chain CLOSED. Deposit τ across its edges (utility EARNED by reality).
  * exit 1  → NO deposit. The unreinforced path evaporates naturally via the colony's DECAY. Per the
              standing decision, a plain POSIX exit-1 drops **no immortal σ scar**: exit-1 is the most
              common event in coding (typo / missing dep / flaky test), not a lethal consequence, and σ
              is immortal — scarring a correct note for an unrelated failure would sterilize the wiki.
              σ is reserved for the somatic lethal class or a *confirmed-repeat* doc-rot signal, dropped
              elsewhere, never here.

Numpy-free and fail-open: a hook must never crash the agent, so every path is guarded and returns a bool.
"""

from __future__ import annotations

import os
import time

from ..colony import Colony, edges
from .node import NodeId, WikiGraph


def ensure_colony(graph: WikiGraph, label: str = "_default") -> Colony:
    """Bind the graph's τ lane to the goal-class ``label``'s persisted colony (load-or-reuse). Mirrors
    the procedural per-class design — similar declarative tasks converge into the same colony."""
    if graph.colony is None or getattr(graph.colony, "label", None) != label:
        graph.colony = Colony.load(label)
    return graph.colony


def on_consequence(
    graph: WikiGraph,
    note_trail: list[NodeId],
    exit_code: int,
    *,
    label: str = "_default",
    weight: float = 1.0,
    save: bool = True,
) -> bool:
    """Bind one execution outcome to the declarative manifold. Returns True iff a τ deposit was laid.

    ``note_trail`` is the ordered list of NodeIds the LLM USED this segment (spliced + actually
    referenced) leading up to the consequence — the declarative analogue of the procedural tool-trail.
    Retrieval alone never reaches here; only a closed exit-0 chain pays τ (popularity ≠ utility).
    """
    try:
        if exit_code != 0:
            return False                                   # failure → silence → natural evaporation
        trail = [n for n in (note_trail or []) if n and n not in graph.scars]
        es = edges(trail)
        if not es:                                         # need ≥2 distinct used notes to form an edge
            return False
        col = ensure_colony(graph, label)
        col.deposit(es, float(weight),                     # ONE call: decay-all + reinforce + prune
                    ts=time.time(), model=os.environ.get("EXOCORTEX_MODEL", ""))   # F3 provenance stamp
        if save:
            col.save()
        return True
    except Exception:
        return False                                       # fail-open: never raise into the hook
