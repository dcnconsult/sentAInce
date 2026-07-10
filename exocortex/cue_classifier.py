"""Discovered-class cue classifier — online leader clustering over prompt cues (pivot P-B).

NO fixed goal-class list: classes EMERGE by single-pass threshold clustering of the `UserPromptSubmit`
prompts. Each cue is TF-IDF-vectorized (incremental corpus stats) and assigned to the nearest cluster
centroid by cosine similarity; if it is farther than `THRESHOLD` from every centroid it SEEDS a new
class. The assigned label becomes (a) the per-class colony's key and (b) the trail's `cue:<label>` root
node (pivot P-A) — so even a one-command task forms an edge and every deposit binds to its goal-class.

A freshly-seeded class has an empty colony → the splice abstains (the anti-clutter discipline: never
inject on novel work). Stdlib-only (no numpy, no embedder) so it runs fast in the hook and fails open.
Persisted per project at ``state_dir()/cues.json``.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from .config import state_dir

THRESHOLD = 0.30   # cosine below which a cue SEEDS a new class — the class-granularity knob
_TOKEN = re.compile(r"[a-z0-9_]+")
# Minimal generic stoplist only (articles/prepositions/pronouns). Critically, the SIMILARITY uses raw
# TF, NOT TF-IDF: the recurring task-verbs ("add", "run", "test") ARE the intent signal, and IDF would
# wrongly penalize them as common while rewarding the variable content nouns. IDF is kept ONLY to pick
# distinctive LABEL words. (Lexical limit: paraphrases with no shared words won't merge — see module note.)
_STOP = frozenset(
    "a an the to of in on for and or but with then so if as at be by from into out is are was were "
    "this that these those it its do does please you your i we me my our will can could should would "
    "no not any all each one two use using".split())


def _stem(t: str) -> str:
    """Light suffix stripping so morphological variants merge (tests→test, fails→fail, running→runn)."""
    for suf, ml in (("ing", 5), ("ed", 4), ("es", 4), ("s", 3)):
        if t.endswith(suf) and len(t) > ml:
            return t[:-len(suf)]
    return t


def _featurize(text: str) -> dict:
    tf: dict = {}
    for tok in _TOKEN.findall((text or "").lower()):
        if len(tok) < 2 or tok in _STOP or tok.isdigit():
            continue
        s = _stem(tok)
        tf[s] = tf.get(s, 0) + 1
    return tf


def _slug(tokens) -> str:
    s = "-".join(tokens) or "misc"
    return re.sub(r"[^a-z0-9_-]", "", s)[:32] or "misc"


@dataclass
class CueClassifier:
    n: int = 0                                    # cues seen (corpus size)
    df: dict = field(default_factory=dict)        # token -> #cues containing it
    clusters: list = field(default_factory=list)  # each: {id, label, size, tf_sum: {tok: count}}

    # ---- vector math (stdlib): raw-TF cosine for SIMILARITY, IDF only for LABELS ----
    def _idf(self, tok: str) -> float:
        return math.log((1 + self.n) / (1 + self.df.get(tok, 0))) + 1.0

    @staticmethod
    def _cos(a: dict, b: dict) -> float:
        if not a or not b:
            return 0.0
        dot = sum(v * b.get(t, 0.0) for t, v in a.items())
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    def _centroid(self, cl: dict) -> dict:
        size = max(1, cl["size"])
        return {t: s / size for t, s in cl["tf_sum"].items()}   # mean raw TF

    def _label(self, tf: dict, cid: int) -> str:
        top = sorted(tf, key=lambda t: tf[t] * self._idf(t), reverse=True)[:2]   # most DISTINCTIVE tokens
        return f"{_slug(top)}#{cid}"

    # ---- the leader-clustering step ----
    def classify(self, prompt: str) -> dict:
        """Assign `prompt` to the nearest discovered class, or seed a new one. Mutates + returns
        ``{label, cluster_id, similarity, is_new}``. The caller persists with ``save()``."""
        tf = _featurize(prompt)
        if not tf:
            return {"label": "_misc", "cluster_id": -1, "similarity": 0.0, "is_new": False}
        self.n += 1
        for t in set(tf):
            self.df[t] = self.df.get(t, 0) + 1

        best_sim, best = 0.0, None
        for cl in self.clusters:
            sim = self._cos(tf, self._centroid(cl))   # raw-TF cosine: task-verbs drive intent similarity
            if sim > best_sim:
                best_sim, best = sim, cl

        if best is not None and best_sim >= THRESHOLD:
            for t, c in tf.items():
                best["tf_sum"][t] = best["tf_sum"].get(t, 0) + c
            best["size"] += 1
            return {"label": best["label"], "cluster_id": best["id"],
                    "similarity": round(best_sim, 3), "is_new": False}

        cid = len(self.clusters)
        label = self._label(tf, cid)
        self.clusters.append({"id": cid, "label": label, "size": 1, "tf_sum": dict(tf)})
        return {"label": label, "cluster_id": cid, "similarity": round(best_sim, 3), "is_new": True}

    # ---- persistence (per project) ----
    @staticmethod
    def _path():
        return state_dir() / "cues.json"

    def save(self) -> None:
        try:
            from .fsutil import atomic_write_text
            atomic_write_text(self._path(), json.dumps(   # ADR-020 W1: a reader never sees a torn store
                {"n": self.n, "df": self.df, "clusters": self.clusters}))
        except Exception:
            pass   # a hook must never crash the agent

    @classmethod
    def load(cls) -> "CueClassifier":
        c = cls()
        p = c._path()
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                c.n = int(d.get("n", 0))
                c.df = {str(k): int(v) for k, v in dict(d.get("df", {})).items()}
                c.clusters = list(d.get("clusters", []))
            except Exception:
                pass
        return c
