"""Exp 5 — learned-signature scars (the principled response to C4-R).

C4-R proved a hand-specified ``(effect, target)`` taxonomy cannot separate destructive *intent*
from benign *structure*. The response: stop hand-specifying the signature and induce it from the
harm distribution — embed each action as a vector, scar the *neighbourhood* of witnessed-harm
vectors, refuse iff similarity to the nearest toxin ≥ τ. The open question is whether ANY learnable
metric separates intent where the parser could not.

Three encoders, on one axis (similarity-to-nearest-learned-toxin), so they are directly comparable:

* ``StructuralEncoder`` — the C4 baseline, lifted onto the same axis (similarity 1.0 iff identical
  ``(effect, target)`` signature, else 0.0). The thing we are trying to beat.
* ``HDCEncoder`` — the kernel's own Z3 phasor VSA (``freqos.tam``, imported **read-only**): a
  bag-of-tokens hypervector, phasor-overlap similarity. Deterministic, lockable.
* ``FloatEncoder`` — wraps any RAG ``Embedder`` (the real ``SentenceTransformerEmbedder`` for the
  semantic arm, or the deterministic ``HashingEmbedder`` lexical null); cosine similarity.

The separability question for an encoder: does there exist a τ that refuses every truly-toxic probe
while passing every benign one — i.e. is ``min(sim of should-refuse) > max(sim of should-pass)``?
The *margin* between those is the verdict signal; a non-positive margin means the bands overlap and
no threshold separates intent from structure in that metric.
"""
from __future__ import annotations

import hashlib
import re
import sys
from typing import Protocol, runtime_checkable

import numpy as np

from ..kernel import locate_kernel

# Locate + import the frozen kernel's Z3 VSA, read-only (never modified, no lock crossed).
_kernel = locate_kernel()
if _kernel is not None:
    _src = str((_kernel / "src").resolve())
    if _src not in sys.path:
        sys.path.insert(0, _src)
from freqos.tam import OMEGA, bundle, random_patterns  # noqa: E402  (kernel HDC, read-only)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(command: str) -> list[str]:
    """Lowercased alphanumeric tokens — splits paths so /var/log → {var, log}."""
    return _TOKEN_RE.findall(command.lower())


@runtime_checkable
class Encoder(Protocol):
    name: str

    def encode(self, command: str): ...

    def similarity(self, a, b) -> float: ...


class StructuralEncoder:
    """The C4 hand-specified signature, lifted onto the similarity axis (1.0 iff same signature)."""

    name = "structural"

    def __init__(self) -> None:
        from .antibody import signature_of
        self._sig = signature_of

    def encode(self, command: str):
        return self._sig(command)

    def similarity(self, a, b) -> float:
        return 1.0 if a == b else 0.0


class HDCEncoder:
    """Bag-of-tokens Z3 hypervector over the kernel's phasor VSA. Deterministic (blake2b item seeds)."""

    name = "hdc_z3"

    def __init__(self, dim: int = 512) -> None:
        self.dim = int(dim)

    def _item(self, token: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")
        rng = np.random.default_rng(seed % (2**32))
        return random_patterns(1, self.dim, rng)[0]

    def encode(self, command: str) -> np.ndarray:
        toks = tokenize(command) or [""]
        return bundle(np.stack([self._item(t) for t in toks]))

    def similarity(self, a, b) -> float:
        delta = (a.astype(np.int64) - b.astype(np.int64)) % 3
        return float(abs(np.mean(OMEGA ** delta)))


class FloatEncoder:
    """Wrap a RAG ``Embedder`` (row-normalised float vectors); cosine similarity."""

    def __init__(self, embedder) -> None:
        self._e = embedder
        self.name = getattr(embedder, "name", "float")

    def encode(self, command: str) -> np.ndarray:
        return np.asarray(self._e.embed([command])[0], dtype=np.float64)

    def similarity(self, a, b) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
        return float(np.dot(a, b) / denom)


class LearnedAntibody:
    """A scar = the set of witnessed-harm vectors; refuse iff sim-to-nearest-toxin ≥ τ."""

    def __init__(self, encoder: Encoder) -> None:
        self.encoder = encoder
        self._toxic: list = []

    def witness(self, command: str) -> None:
        self._toxic.append(self.encoder.encode(command))

    def max_similarity(self, command: str) -> float:
        if not self._toxic:
            return 0.0
        v = self.encoder.encode(command)
        return max(self.encoder.similarity(v, t) for t in self._toxic)

    def scarred(self, command: str, tau: float) -> bool:
        return self.max_similarity(command) >= tau


def separability(encoder: Encoder, witness: list[str], should_refuse: list[str],
                 should_pass: list[str]) -> dict:
    """Learn the toxins, then measure whether any τ separates should-refuse from should-pass.

    Returns the per-probe similarities, the separating margin (min refuse − max pass; > 0 ⇒ a τ
    exists), and the worst offenders (closest benign, farthest toxin) that define the overlap.
    """
    ab = LearnedAntibody(encoder)
    for cmd in witness:
        ab.witness(cmd)
    refuse_sims = {c: ab.max_similarity(c) for c in should_refuse}
    pass_sims = {c: ab.max_similarity(c) for c in should_pass}
    min_refuse = min(refuse_sims.values())
    max_pass = max(pass_sims.values())
    return {
        "encoder": encoder.name,
        "self_sim": round(max(ab.max_similarity(c) for c in witness), 4),
        "min_refuse": round(min_refuse, 4),
        "max_pass": round(max_pass, 4),
        "margin": round(min_refuse - max_pass, 4),
        "separable": bool(min_refuse > max_pass),
        "hardest_toxin": min(refuse_sims, key=lambda c: refuse_sims[c]),
        "hardest_toxin_sim": round(min(refuse_sims.values()), 4),
        "closest_benign": max(pass_sims, key=lambda c: pass_sims[c]),
        "closest_benign_sim": round(max(pass_sims.values()), 4),
        "refuse_sims": {c: round(s, 4) for c, s in refuse_sims.items()},
        "pass_sims": {c: round(s, 4) for c, s in pass_sims.items()},
    }
