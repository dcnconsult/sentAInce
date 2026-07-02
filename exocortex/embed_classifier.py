"""Embedding cue-classifier — semantic goal-class matching with a margin-gated novelty-abstain (P-B upgrade).

Replaces the lexical TF classifier's *phrasing*-similarity with *semantic* similarity, so paraphrased
recurrences of one goal ("run the unit tests" / "execute the spec suite") MERGE instead of fragmenting —
the §10/§12 lexical limit. A local MiniLM embedding → L2-normalised dense vector; a new cue is matched to
the nearest per-class centroid by cosine with the v0.69 `ssr_rag._retrieve` ABSTAIN logic (top-1 overlap +
top1−top2 margin): high overlap → route to that class; a semantic void → seed a NEW class.

VERIFY-AGAINST-THE-KERNEL (honest deviation from the plan): the directed Z3 bridge
(`whiten_capacity.quantile_z3` → `ssr_rag._retrieve`) was MEASURED to collapse MiniLM's class separation —
intra/inter cosine gap 0.367 → 0.029 — because ternary-quantising a 384-d continuous embedding destroys the
geometry. So the match runs on the DENSE vector and reuses the kernel's overlap+margin *abstain mechanism*,
not its Z3 codes. (Re-examine if a higher-resolution VSA encoding is found.)

Heavy deps (sentence-transformers); therefore OPT-IN via ``EXOCORTEX_EMBED=1``. Absent / failed import →
the hook falls back to the lexical `CueClassifier`. Persisted per project at ``state_dir()/embed_cues.json``.
"""
from __future__ import annotations

import json
import os

from .config import state_dir
from .cue_classifier import _featurize, _slug   # reuse the tokenizer just for a human-readable label
from .genome import GENOME

# Knobs from the Genome (exocortex_config.json), with env-var override taking precedence.
_E = GENOME["epistemic_classifier"]
_MODEL_NAME = os.environ.get("EXOCORTEX_EMBED_MODEL") or _E["model"]
MATCH = float(os.environ.get("EXOCORTEX_EMBED_MATCH") or _E["abstain_threshold_cosine"])  # cosine ≥ → same class
MARGIN = float(os.environ.get("EXOCORTEX_EMBED_MARGIN") or _E["match_margin"])            # top1−top2 commit gate

_MODEL = None   # process-singleton (each hook is a fresh process; this warms within a process only)


def _embedder_available() -> bool:
    """True iff a local embedder is importable. Cheap (no model load)."""
    try:
        import numpy  # noqa: F401
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def _model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(_MODEL_NAME)
    return _MODEL


def _label(prompt: str, cid: int) -> str:
    tf = _featurize(prompt)
    top = sorted(tf, key=lambda t: tf[t], reverse=True)[:2]
    return f"{_slug(top)}#{cid}"


class EmbeddingCueClassifier:
    """Semantic per-class centroids; online leader-match with a margin-gated abstain (mirror of the lexical
    `CueClassifier` API so the hook can swap it in transparently)."""

    def __init__(self) -> None:
        self.dim = 0
        self.classes: list = []   # each: {id, label, size, sum: [floats]}  (centroid = sum / size)

    @staticmethod
    def available() -> bool:
        return _embedder_available()

    # ---- vectors ----
    def _embed(self, prompt: str):
        import numpy as np
        v = _model().encode([prompt or ""], normalize_embeddings=True)[0]
        return np.asarray(v, dtype=float)

    def classify(self, prompt: str) -> dict:
        import numpy as np
        v = self._embed(prompt)
        self.dim = int(v.shape[0])
        if not self.classes:
            return self._seed(prompt, v)
        cents = np.array([c["sum"] for c in self.classes], dtype=float)
        cents /= (np.linalg.norm(cents, axis=1, keepdims=True) + 1e-9)
        sims = cents @ v                                   # cosine to each centroid (v already unit)
        order = np.argsort(-sims)
        s1 = float(sims[order[0]])
        s2 = float(sims[order[1]]) if sims.size > 1 else 0.0
        if s1 >= MATCH and (s1 - s2) >= MARGIN:           # MATCH — the paraphrase shares the trail
            cl = self.classes[order[0]]
            cl["sum"] = (np.asarray(cl["sum"], float) + v).tolist()
            cl["size"] += 1
            return {"label": cl["label"], "cluster_id": cl["id"],
                    "similarity": round(s1, 3), "is_new": False}
        return self._seed(prompt, v)                       # ABSTAIN — semantic void → new class

    def _seed(self, prompt: str, v) -> dict:
        cid = len(self.classes)
        label = _label(prompt, cid)
        self.classes.append({"id": cid, "label": label, "size": 1, "sum": v.tolist()})
        return {"label": label, "cluster_id": cid, "similarity": 0.0, "is_new": True}

    # ---- persistence ----
    @staticmethod
    def _path():
        return state_dir() / "embed_cues.json"

    def save(self) -> None:
        try:
            self._path().write_text(json.dumps({"dim": self.dim, "classes": self.classes}),
                                    encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def load(cls) -> "EmbeddingCueClassifier":
        c = cls()
        p = c._path()
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                c.dim = int(d.get("dim", 0))
                c.classes = list(d.get("classes", []))
            except Exception:
                pass
        return c
