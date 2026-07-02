"""Used-note attribution — credit declarative τ only to notes the model actually USED (NEXT_PHASE_PLAN §6, Ticket 1 / #2).

The crown jewel's hardest case: between injecting a note (UserPromptSubmit splice) and observing exit-0
(PostToolUse), "use" is unobservable — the model's cognition is opaque. We can only read PROXIES from the
hook contract. The design principle is an ASYMMETRY: a false negative (missing a real use) merely slows
learning; a false positive (crediting an un-used note) reimports semantic dilution. So attribution biases
hard to PRECISION — when in doubt, do not credit.

PRIMARY = content echo, anchored to consequence. A note is "used" iff its DISTINCTIVE content materialized
in a consequence-bearing ACTION of the exit-0 segment (the commands/edits the model actually ran — the same
reality the procedural colony already credits). "Distinctive" = code (fenced or inline) + path/identifier
tokens; NOT plain prose. A purely conceptual note has no salient tokens → it is never action-credited →
safely under-credited. Coincidental echo is self-cleaning (DECAY + prune evaporate weakly-reinforced
notes); only SYSTEMATIC over-credit (whole-injection) corrupts the law, and that is exactly what this
avoids — we never credit a note merely because it was injected.

REJECTED: whole-injection credit (rewards retrieval). DEMOTED to a dormant, discounted, optional tier:
the citation/prose echo (``last_assistant_message`` at Stop) — claim-grounded, not reality-grounded.

Numpy-free and fail-open: this runs at PostToolUse (the hot path).
"""

from __future__ import annotations

import re

from ..genome import GENOME
from .node import WikiGraph
from .wire import on_consequence

_D = (GENOME.get("declarative", {}) or {}).get("attribution", {}) or {}
MIN_OVERLAP = int(_D.get("min_overlap", 1))     # # of distinctive tokens that must echo to count as "used"

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_RE = re.compile(r"`([^`\n]+)`")
_IDENT_RE = re.compile(r"[A-Za-z0-9][\w./\-]{2,}")   # path / dotted-name / flag / identifier, len ≥ 3

# Common code/markdown/English tokens that carry no attribution signal even when "structured".
_STOP = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your", "use", "run",
    "com", "org", "www", "http", "https", "md", "txt", "see", "via", "etc", "e.g", "i.e",
}


def _idents(text: str) -> set:
    # strip surrounding punctuation so "src/main.py." matches a clean "src/main.py" in the action
    out: set = set()
    for t in _IDENT_RE.findall(text or ""):
        t = t.strip("./-_").lower()
        if len(t) >= 3:
            out.add(t)
    return out


def salient_tokens(text: str) -> set:
    """The distinctive, action-echoable tokens of a note. High-signal sources (code fences + inline
    `code`) contribute every identifier; plain prose contributes ONLY structured tokens (containing
    ``. _ / -`` — paths, dotted names, flags). Plain English words are dropped — a prose-only note has an
    empty salient set and is therefore never action-credited (the safe under-credit)."""
    text = text or ""
    toks: set = set()
    for fence in _FENCE_RE.findall(text):              # fenced code — every identifier is salient
        toks |= _idents(fence)
    for inline in _INLINE_RE.findall(text):            # inline `code` — likewise
        toks |= _idents(inline)
    body = _INLINE_RE.sub(" ", _FENCE_RE.sub(" ", text))
    for t in _idents(body):                            # prose — only structured tokens
        if any(c in t for c in "._/-"):
            toks.add(t)
    return {t for t in toks if t not in _STOP and len(t) >= 3}


def attribute_used(
    graph: WikiGraph,
    injected_ids,
    action_text: str,
    *,
    min_overlap: int | None = None,
) -> list:
    """The notes among ``injected_ids`` whose salient content echoes in ``action_text`` (the commands /
    edits the model actually executed this segment). Returns the used NodeIds. Fail-open → []."""
    try:
        need = MIN_OVERLAP if min_overlap is None else min_overlap
        acts = _idents(action_text)
        if not acts:
            return []
        used: list = []
        for nid in dict.fromkeys(injected_ids or []):     # dedup, preserve order
            if nid in graph.scars:
                continue
            node = graph.nodes.get(nid)
            if node is None:
                continue
            if len(salient_tokens(node.text) & acts) >= need:
                used.append(nid)
        return used
    except Exception:
        return []


def deposit_attributed(
    graph: WikiGraph,
    injected_ids,
    action_text: str,
    exit_code: int,
    *,
    cue: str,
    label: str = "_default",
    weight: float = 1.0,
    min_overlap: int | None = None,
    save: bool = True,
) -> list:
    """The consequence entry point: on exit-0, attribute the used notes and deposit declarative τ on the
    cue-rooted trail (``[cue] + used`` → ``wire.on_consequence``), so even one used note forms an edge.
    On exit-1 nothing is credited (the unreinforced notes evaporate; no immortal σ — the standing law).
    Returns the used NodeIds (empty on failure / exit-1 / no echo)."""
    try:
        if exit_code != 0:
            return []
        used = attribute_used(graph, injected_ids, action_text, min_overlap=min_overlap)
        if not used:
            return []
        on_consequence(graph, [cue, *used], exit_code=0, label=label, weight=weight, save=save)
        return used
    except Exception:
        return []
