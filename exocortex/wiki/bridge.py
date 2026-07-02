"""Provisional bridges — the Hippocampus organ's earned state (Ticket 2, slice 1; design in docs/BRIDGE_ORGAN_DESIGN.md).

A bridge is a candidate ``[[link]]`` the wiki's geometry SUGGESTS but consequence has NOT yet earned. Like τ
and σ it is earned state, so it lives OFF the digest cache — in ``state_dir/wiki_bridges.json`` — and is
written only by the organ's own lifecycle, never by the digester.

This slice ships the data model + the **0-well abstain gate** (the gauge's precision-to-1.0 step) + persistence
+ a dedup/cap/scar-respecting upsert. Synthesis (sleep), offer (splice) and verify (consequence) are later
slices. Numpy-free and fail-open — the offer/verify paths run on the hot path.

Lifecycle: ``proposed`` (synthesized in sleep) → ``offered`` (spliced for the LLM to try) → ``confirmed``
(A and D both attributed in one exit-0 → crystallize τ) | ``scarred`` (exit-1 after a walk, or
``scar_after_k_walks`` offers with no pay → immortal σ, never re-proposed).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from ..config import state_dir
from ..genome import GENOME
from .node import NodeId, WikiGraph
from .propose import _index_by_doc, _resolve

_B = (GENOME.get("declarative", {}) or {}).get("bridge", {}) or {}
TOP_K = int(_B.get("top_k", 4))
ABSTAIN_CONF = float(_B.get("abstain_conf", 0.14))      # epistemic_gate WALL_BUNDLE — the 0-well familiarity wall
ABSTAIN_MARGIN = float(_B.get("abstain_margin", 0.03))
MAX_PROVISIONAL = int(_B.get("max_provisional", 32))
OFFER_CAP = int(_B.get("offer_cap", 2))
SCAR_AFTER_K_WALKS = int(_B.get("scar_after_k_walks", 3))

PROPOSED, OFFERED, CONFIRMED, SCARRED = "proposed", "offered", "confirmed", "scarred"
_SEP = "\t"   # directed bridge key "a<TAB>d" (NodeIds never contain a tab)


@dataclass
class ProvisionalBridge:
    a: NodeId
    d: NodeId
    conf: float = 0.0
    status: str = PROPOSED
    proposed_at: str = ""        # caller-supplied stamp (the kernel path has no Date.now)
    walks: int = 0               # times offered-and-used without a clean exit-0 pay yet

    def key(self) -> str:
        return f"{self.a}{_SEP}{self.d}"


def bridge_gate(conf: float, runner_up: float = 0.0,
                *, conf_floor: float | None = None, margin: float | None = None) -> bool:
    """The 0-well abstain: KEEP a candidate only if its HDC chord sits in a CONFIDENT basin — familiarity
    above the wall AND a clear gap over the runner-up (not a 0-well tie). Returns True=keep, False=abstain.
    This is the gauge's precision-to-1.0 step (epistemic_gate v0.55 geometry, WALL_BUNDLE≈0.14)."""
    floor = ABSTAIN_CONF if conf_floor is None else conf_floor
    gap = ABSTAIN_MARGIN if margin is None else margin
    return conf >= floor and (conf - runner_up) >= gap


# --------------------------------------------------------------- persistence (earned state)
def _path():
    return state_dir() / "wiki_bridges.json"


def load_bridges() -> dict:
    """key -> ProvisionalBridge. Fail-open to empty."""
    out: dict = {}
    try:
        p = _path()
        if p.exists():
            for d in json.loads(p.read_text(encoding="utf-8")):
                b = ProvisionalBridge(
                    a=str(d["a"]), d=str(d["d"]), conf=float(d.get("conf", 0.0)),
                    status=str(d.get("status", PROPOSED)), proposed_at=str(d.get("proposed_at", "")),
                    walks=int(d.get("walks", 0)))
                out[b.key()] = b
    except Exception:
        pass
    return out


def save_bridges(bridges: dict) -> None:
    try:
        _path().write_text(json.dumps([asdict(b) for b in bridges.values()]), encoding="utf-8")
    except Exception:
        pass   # a hook must never crash the agent


# --------------------------------------------------------------- synthesis-time upsert
def upsert_candidate(bridges: dict, a: NodeId, d: NodeId, conf: float, *, stamp: str = "",
                     max_provisional: int | None = None) -> bool:
    """Register a freshly-synthesized candidate. Returns True iff a NEW provisional bridge was added.
    Respects the invariants: never resurrect a SCARRED bridge, never disturb a CONFIRMED one, never exceed
    the cap. An existing proposed/offered bridge keeps its lifecycle (only its conf refreshes)."""
    cap = MAX_PROVISIONAL if max_provisional is None else max_provisional
    key = f"{a}{_SEP}{d}"
    existing = bridges.get(key)
    if existing is not None:
        if existing.status in (SCARRED, CONFIRMED):
            return False                       # immortal verdict — never re-propose / re-disturb
        existing.conf = conf                   # refresh the geometric score; keep status/walks
        return False
    if sum(1 for b in bridges.values() if b.status in (PROPOSED, OFFERED)) >= cap:
        return False                           # at the live-provisional ceiling
    bridges[key] = ProvisionalBridge(a=a, d=d, conf=conf, status=PROPOSED, proposed_at=stamp)
    return True


# --------------------------------------------------------------- synthesis (sleep / PreCompact — numpy)
def _already_connected(graph: WikiGraph, a, d, link_index: dict) -> bool:
    """True if A and D are ALREADY joined — A's note `[[links]]` to D's doc, or they share a colony edge
    (co-walked). Such pairs need no bridge; the organ proposes only edges geometry suggests but structure
    and consequence have not yet drawn."""
    d_doc = d.id.split("#", 1)[0]
    for t in a.links:
        if any(nid.split("#", 1)[0] == d_doc for nid in _resolve(link_index, t)):
            return True
    col = getattr(graph, "colony", None)
    tau = getattr(col, "tau", None) if col is not None else None
    if tau and (f"{a.id}\t{d.id}" in tau or f"{d.id}\t{a.id}" in tau):
        return True
    return False


def synthesize(graph: WikiGraph, *, bridges: dict | None = None, top_k: int | None = None,
               stamp: str = "", conf_floor: float | None = None, margin: float | None = None) -> dict:
    """Sleep-cycle bridge synthesis over the materialized ``graph.phasor_bank`` (build it first). For each
    note A, take its top-k geometrically-nearest ELIGIBLE notes (not self, not already-connected) by the Z3
    familiarity ``|(ω^a)·conj(ω^d)|/M`` (the recall_successor metric), and emit those that clear the 0-well
    gate (a confident basin: above the wall AND distinct from the runner-up). NEVER crystallizes — only
    PROPOSES. Numpy + frozen-kernel ``OMEGA``; PreCompact only. Fail-open → bridges unchanged.

    Returns the updated bridges dict (persisted)."""
    bridges = load_bridges() if bridges is None else bridges
    try:
        import numpy as np

        from .digest import _ensure_freqos
        bank = getattr(graph, "phasor_bank", None)
        if bank is None or not _ensure_freqos():
            return bridges
        from freqos.tam import OMEGA

        ix_to_node = {n.phasor_ix: n for n in graph.nodes.values() if n.phasor_ix is not None}
        rows = sorted(ix_to_node)
        if len(rows) < 3:
            return bridges
        k = TOP_K if top_k is None else top_k
        link_index = _index_by_doc(graph)
        P = OMEGA ** np.asarray(bank, dtype=np.int64)               # (N, M) complex unit phasors
        S = np.abs(P @ P.conj().T) / bank.shape[1]                  # (N, N) Z3 familiarity in [0, 1]

        added = 0
        for ix in rows:
            a = ix_to_node[ix]
            cand = []
            for j in rows:
                if j == ix:
                    continue
                d = ix_to_node[j]
                if _already_connected(graph, a, d, link_index):
                    continue
                cand.append((float(S[ix, j]), d))
            cand.sort(key=lambda x: -x[0])
            for pos in range(min(k, len(cand))):
                conf, d = cand[pos]
                runner = cand[pos + 1][0] if pos + 1 < len(cand) else 0.0
                if not bridge_gate(conf, runner, conf_floor=conf_floor, margin=margin):
                    break                                          # sorted desc → no confident basin left for A
                added += int(upsert_candidate(bridges, a.id, d.id, conf, stamp=stamp))
        save_bridges(bridges)
        return bridges
    except Exception:
        return bridges


# --------------------------------------------------------------- offer (UserPromptSubmit — numpy-free)
def offer(graph: WikiGraph, bridges: dict, candidate_ids, *, offer_cap: int | None = None) -> tuple:
    """Surface provisional bridges whose SOURCE A the proposer raised this turn — the third splice channel
    (beside verified exons and exploratory tissue). Marks each surfaced bridge ``offered`` and returns
    ``(payload, endpoint_ids)``; the caller adds BOTH endpoints (A and D) to the turn's attribution surface
    so a 'walk' (A and D both used in one exit-0) is detectable downstream. Numpy-free, fail-open."""
    try:
        cap = OFFER_CAP if offer_cap is None else offer_cap
        cset = set(candidate_ids or [])
        live = [b for b in bridges.values()
                if b.status in (PROPOSED, OFFERED) and b.a in cset
                and b.a in graph.nodes and b.d in graph.nodes
                and b.a not in graph.scars and b.d not in graph.scars]
        live.sort(key=lambda b: -b.conf)
        live = live[:max(0, cap)]
        if not live:
            return "", []
        parts = ["<!-- provisional bridges (UNVERIFIED shortcuts — a [[link]] crystallizes ONLY if walking "
                 "A⇢D pays exit 0) -->"]
        endpoints: list = []
        for b in live:
            a_node, d_node = graph.nodes[b.a], graph.nodes[b.d]
            ah = " / ".join(a_node.heading_path) if a_node.heading_path else b.a
            dh = " / ".join(d_node.heading_path) if d_node.heading_path else b.d
            parts.append(f"<!-- bridge (PROVISIONAL) · {ah} ⇢ {dh} · conf={b.conf:.2f} -->\n{d_node.text}")
            b.status = OFFERED
            endpoints.extend([b.a, b.d])
        return "\n\n".join(parts), endpoints
    except Exception:
        return "", []


# --------------------------------------------------------------- verify (PostToolUse — numpy-free)
def verify(graph: WikiGraph, bridges: dict, used, exit_code: int, *, label: str = "_default",
           weight: float = 1.0) -> tuple:
    """Close the loop on a consequence. A provisional bridge is WALKED when BOTH endpoints are in ``used``
    (attributed this segment). On a walk:
      * exit 0 → CRYSTALLIZE — deposit τ on the real ``a→d`` colony edge (now consequence-backed), status
        ``confirmed`` (future synthesis sees it co-walked and won't re-propose).
      * exit 1 → a non-paying walk; increment ``walks`` and SCAR (immortal, never re-proposed) once it has
        failed ``scar_after_k_walks`` times — patient, like the no-σ-on-a-single-exit-1 law (a good bridge
        shouldn't die on one incidental failure).
    Returns ``(n_crystallized, n_scarred)``. Numpy-free, fail-open — never raises into the hook."""
    try:
        from ..colony import Colony
        u = set(used or [])
        crystal: list = []
        n_cryst = n_scar = 0
        for b in bridges.values():
            if b.status != OFFERED:
                continue
            if not (b.a in u and b.d in u):
                continue                                    # offered but not walked this segment
            if exit_code == 0:
                b.status = CONFIRMED
                crystal.append((b.a, b.d))
                n_cryst += 1
            else:
                b.walks += 1
                if b.walks >= SCAR_AFTER_K_WALKS:
                    b.status = SCARRED
                    n_scar += 1
        if crystal:
            col = getattr(graph, "colony", None) or Colony.load(label)
            col.deposit(crystal, float(weight))             # the bridge becomes a real, earned colony edge
            col.save()
        return n_cryst, n_scar
    except Exception:
        return 0, 0
