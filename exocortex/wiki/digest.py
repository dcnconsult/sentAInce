"""The Digestive System — shred a Markdown document into ``ExonNode`` matter (NEXT_PHASE_PLAN §6, Ticket 1).

Two strictly separated halves:

  * ``digest_document`` / ``shred`` — the SURE-WIN path. Pure structural cleavage: code-fence-aware
    block splitting, heading-path tracking, ``[[wikilink]]`` extraction, stable content-identity ids.
    Dependency-light (stdlib only) and numpy-free — it builds the matter lane that the τ-forage/splice
    loop runs on without ever touching MiniLM or the kernel.

  * ``encode_phasor`` — the Z3 DIGESTION proper, for the (deferred, gauge-gated) bridge lane only.
    real MiniLM embedding -> fixed complex random projection -> ``tam._phase_of`` -> (M,) Z3 int8.
    HEAVY and SLEEP-ONLY: it lazily loads sentence-transformers and the frozen kernel, so it is called
    exclusively inside ``WikiGraph.build_phasor_bank`` during ``PreCompact``. Fail-open (returns None).

GROUNDING (verified 2026-06-27): ``tam._phase_of`` needs a COMPLEX input (it takes ``np.angle``); a raw
real MiniLM vector would collapse to ~2 phase labels. No real->Z3 adapter exists in the kernel, so the
fixed unit-circle complex projection here IS that adapter — deterministic (seeded) so the same text maps
to the same phasor across sessions, which is what makes a bridge stable enough to crystallize.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .node import ExonNode, NodeId

WIKILINK_RE = re.compile(r"\[\[(.*?)\]\]")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(slots=True)
class _Block:
    text: str
    start_line: int                 # 1-based, inclusive
    end_line: int                   # 1-based, inclusive
    heading_path: tuple[str, ...]   # the heading stack in force at this block


def shred(raw_text: str) -> list[_Block]:
    """Fascial cleavage that respects Markdown physics.

    Splits on blank lines, but SUSPENDS cleavage inside ``` / ~~~ fences (so executable code blocks —
    the RPC payloads the Cortex must emit intact — survive whole). Markdown headings (outside a fence)
    both cleave the stream and update the heading stack, which is attached to every emitted block as its
    neocortical address. Pure-heading blocks are structure, not matter → they update the stack but emit
    no node.
    """
    lines = (raw_text or "").split("\n")
    blocks: list[_Block] = []
    cur: list[str] = []
    cur_start = 0
    heading_stack: list[str] = []
    in_fence = False

    def flush(end_line: int) -> None:
        nonlocal cur, cur_start
        if cur:
            text = "\n".join(cur).strip()
            if text:
                blocks.append(_Block(text, cur_start + 1, end_line + 1, tuple(heading_stack)))
        cur = []

    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            if not cur:
                cur_start = i
            cur.append(line)
            in_fence = not in_fence
            continue

        if in_fence:                                   # inside a code block: take everything verbatim
            if not cur:
                cur_start = i
            cur.append(line)
            continue

        m = _HEADING_RE.match(line)
        if m:                                          # a heading cleaves + re-roots the stack (no node)
            flush(i - 1)
            level = len(m.group(1))
            title = m.group(2).strip()
            del heading_stack[level - 1:]
            heading_stack.append(title)
            continue

        if not line.strip():                           # blank line outside a fence → block boundary
            flush(i - 1)
            continue

        if not cur:
            cur_start = i
        cur.append(line)

    flush(len(lines) - 1)
    return blocks


def _links_of(block_text: str) -> tuple[NodeId, ...]:
    """Resolve ``[[wikilinks]]`` to bare targets, dropping ``|alias`` display text and ``#anchor`` tails."""
    out: list[str] = []
    for raw in WIKILINK_RE.findall(block_text):
        target = raw.split("|")[0].split("#")[0].strip()
        if target:
            out.append(target)
    return tuple(dict.fromkeys(out))                   # dedup, preserve order


def digest_document(doc_id: str, raw_markdown: str) -> list[ExonNode]:
    """Shred a document into ``ExonNode``s (the matter lane).

    NodeId is CONTENT-identity — ``f"{doc_id}#{hash}"`` (with a ``~n`` suffix only to disambiguate two
    byte-identical blocks in one doc). This is the structural enforcement of the crown jewel: edit a
    block's text and its id changes, so its earned τ is *re-earned*, never silently inherited; move a
    block and its id is unchanged, so τ (the claim's verified utility) follows the claim. ``span`` keeps
    document order for the splice's chronological re-entrainment.
    """
    exons: list[ExonNode] = []
    seen: dict[str, int] = {}
    for block in shred(raw_markdown):
        h = hashlib.blake2b(block.text.encode("utf-8"), digest_size=6).hexdigest()
        n = seen.get(h, 0)
        seen[h] = n + 1
        node_id: NodeId = f"{doc_id}#{h}" if n == 0 else f"{doc_id}#{h}~{n}"
        exons.append(ExonNode(
            id=node_id,
            text=block.text,
            heading_path=block.heading_path,
            span=(block.start_line, block.end_line),
            links=_links_of(block.text),
            content_hash=hashlib.blake2b(block.text.encode("utf-8"), digest_size=16).hexdigest(),
        ))
    return exons


# ----------------------------------------------------------- the Z3 digestion (sleep-only, fail-open)
_Z3_DIM = 2048                 # M — HDC hypervector width (phase_router capacity K_c ~= 0.40*M); tunable
_PROJ_SEED = 0x46524551        # "FREQ" — fixed so encoding is deterministic across sessions
_proj_cache: dict = {}


def _projection(d_in: int):
    """A fixed (M, d_in) unit-circle complex matrix — the real->phasor adapter. Built once per input dim
    and cached; seeded so the same text always lands on the same Z3 phasor (stable bridges)."""
    import numpy as np

    if d_in not in _proj_cache:
        rng = np.random.default_rng(_PROJ_SEED)
        phases = rng.uniform(0.0, 2.0 * np.pi, size=(_Z3_DIM, d_in))
        _proj_cache[d_in] = np.exp(1j * phases)
    return _proj_cache[d_in]


def _dense_embed(text: str):
    """The real MiniLM unit vector (D,), or None if the embedder is unavailable. Heavy + lazy."""
    try:
        from exocortex import embed_classifier as ec

        if not ec._embedder_available():
            return None
        import numpy as np

        v = ec._model().encode([text or ""], normalize_embeddings=True)[0]
        return np.asarray(v, dtype=float)
    except Exception:
        return None


def _ensure_freqos() -> bool:
    """Put the frozen kernel on sys.path (the gauge idiom), so ``freqos.tam`` imports. Fail-open."""
    try:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        for cand in (root / "vendor" / "kernel", root / "vendor" / "kernel" / "src"):
            if (cand / "freqos").is_dir() and str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
        return True
    except Exception:
        return False


def encode_phasor(text: str):
    """Digest one block of matter into a (M,) Z3 phasor (int8 in {0,1,2}), or None on any failure.

    SLEEP-ONLY: pulls MiniLM + the kernel. Called from ``WikiGraph.build_phasor_bank`` in PreCompact.
    Fail-open by contract — a None just leaves that node un-digested (the bridge lane stays dormant for
    it); the numpy-free forage/splice loop is unaffected.
    """
    try:
        import numpy as np

        dense = _dense_embed(text)
        if dense is None or not _ensure_freqos():
            return None
        from freqos.tam import _phase_of

        z = _projection(int(dense.shape[0])) @ dense.astype(np.float64)   # (M,) complex
        return _phase_of(z)                                              # (M,) int8 in {0,1,2}
    except Exception:
        return None
