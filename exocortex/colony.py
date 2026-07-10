"""The live verb-altitude pheromone colony — consequence-sourced procedural memory for a session.

The build phase of [[rag-memory-gauge]]. The offline gauge (``gauge/analyze.py``) established the
operating point: at the **verb altitude** (bash executable + src/test file category) the colony
converges on the project's recurring procedural skeleton (segment-reuse → 1.0, memory plateaus) while
the consequence-sourcing law still discriminates clutter (frequency-null 0% vs 24%) — finer keys drift,
coarser keys lose the signal. This module is the *live* version of that colony, wired behind the hook:

  · DEPOSIT  — on a Bash **exit 0** (``PostToolUse`` ok), the path that led there (the recent
               cross-tool trail) gets pheromone. NEVER on failure — the antibody/scar side is the
               strategy-lock; this is the symmetric reflex-memory side ("always do this").
  · CONSOLIDATE — on ``PreCompact`` (the circadian "sleep"): decay once, prune sub-floor, cap to the
               strongest edges (slime-mold leanness) — then SPLICE the dense memory into the next
               context via ``additionalContext`` so the converged reflexes survive compaction.

A faithful minimal mirror of ``circle_of_fifths_rag/src/rag/stigmergic_network.py`` (same DECAY/PRUNE/
DEPOSIT), self-contained (no numpy) so the hook stays fast and fails open; the graduation build swaps
in the locked module. Persisted per-PROJECT (``state_dir()/colony.json``) → institutional memory that
accrues across sessions. STATS/observe-safe: deposits touch only ``colony.json``, never the audit.
"""
from __future__ import annotations

import contextlib
import glob
import json
import os
import re
import time
from dataclasses import dataclass, field

from .config import state_dir
from .fsutil import atomic_write_text, load_store_json
from .genome import GENOME

# Thermodynamic constants — sourced from the Genome (exocortex_config.json) so they can be re-tuned for
# longitudinal R&D without touching code. Kept as module attributes (defaults from genome.DEFAULTS) so
# tests can still monkeypatch them and `from exocortex.colony import PRUNE` keeps working.
_T = GENOME["thermodynamics"]
DECAY = _T["decay"]                       # τ multiplier per deposit (stigmergic evaporation)
DEPOSIT = _T["deposit_base_weight"]       # full-weight pheromone for a focused deposit
PRUNE = _T["prune_floor"]                 # §14 eviction lever (below WEIGHT_MIN; leverages recurrence)
CAP = _T["max_edges_per_class"]           # §14 per-class leanness ceiling (applied at consolidate)
MIN_DEPOSITS_TO_SPLICE = _T["min_deposits_to_splice"]   # abstain until a class has some repetition
SESSION_DECAY = _T["session_discount_rate"]             # §13 per-deposit activity discount (thrash catcher)
WEIGHT_MIN = _T["weight_min"]             # floor so a deep session still records *something*
_SEP = "\t"                               # edge key = "src<TAB>dst" (node names never contain a tab)

# Eligibility trace (organ 3D) — within-segment credit assignment. Module attrs (monkeypatchable) sourced
# from the Genome. "off" → uniform deposit (verified status quo); "trace" → γ^Δ recency credit. See
# [[eligibility.py]]-style gauge: gauge/eligibility_gauge.py.
_E = GENOME.get("eligibility_trace", {})
ELIG_MODE = str(_E.get("mode", "off")).lower()          # off | trace
ELIG_GAMMA = float(_E.get("gamma", 0.80))               # γ — credit ∝ γ^(steps before exit 0)

# Provenance / non-stationarity (organ F3) — stamp each deposited edge with (ts, model) and decay τ AT READOUT
# by recency (+ version-distance in "full"). Module attrs (monkeypatchable) sourced from the Genome. "off" →
# readout uses the raw τ (verified status quo); the recording lane is still inert unless a caller passes `ts`.
_P = GENOME.get("provenance", {})
PROV_MODE = str(_P.get("mode", "off")).lower()                                  # off | recency | full
PROV_HALFLIFE_S = max(1e-9, float(_P.get("recency_halflife_days", 30.0))) * 86400.0  # τ-weight half-life (s)
PROV_VERSION_PENALTY = float(_P.get("version_penalty", 0.5))                     # readout penalty for a stale model


def _recency_weight(ts, now: float) -> float:
    """Readout multiplier in (0, 1]: an edge's τ-weight halves every ``PROV_HALFLIFE_S`` of its age. No stamp →
    1.0 (legacy edges predate the instrument — never penalize what we cannot date); a future ts clamps to 1.0."""
    if not ts:
        return 1.0
    age = now - float(ts)
    if age <= 0:
        return 1.0
    return 0.5 ** (age / PROV_HALFLIFE_S)


def _eligibility(n: int) -> list:
    """Per-edge credit multipliers for an ``n``-edge segment, oldest→newest (organ 3D). ``ELIG_MODE`` 'off'
    → all 1.0 (uniform deposit, the verified status quo); 'trace' → ``γ^(distance-from-consequence)`` so the
    edge into the exit-0 gets full credit (γ^0) and the flail prefix fades (γ^(n-1)). A single-edge segment
    is unaffected (Δ=0). Fail-safe → uniform."""
    if ELIG_MODE != "trace" or n <= 1:
        return [1.0] * n
    return [ELIG_GAMMA ** ((n - 1) - i) for i in range(n)]


def _safe(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(label or "_default")) or "_default"


# ---- verb-altitude node keying (the gauge's validated `verb` granularity) ----
def _bash_verb(cmd: str) -> str:
    tok = (cmd or "").strip().split()
    if not tok:
        return "?"
    # D2: strip shell punctuation baked into the token (quoted/chained commands leaked fragments like
    # `qeg_regen";` into node identity, splitting τ across spurious variants of the same verb).
    verb = os.path.basename(tok[0]).strip("'\";&|()`{}")
    return verb or "?"


def _file_cat(path: str) -> str:
    b = os.path.basename(str(path or "")).lower()
    if not b:
        return "other"
    if "test" in b:
        return "test"
    return "src" if b.endswith(".py") else "other"


def verb_node(tool: str, payload: str) -> str:
    """A node at the verb altitude: a COMMAND tool → its executable verb — Bash as ``bash:``, PowerShell
    as ``ps:`` (D3; distinct namespaces, never silently merged — a `ps:` route is its own evidence, and the
    P3 replay can compare the streams); a file tool → src|test|other."""
    if tool == "Bash":
        return f"bash:{_bash_verb(payload)}"
    if tool == "PowerShell":
        return f"ps:{_bash_verb(payload)}"
    return f"{tool}:{_file_cat(payload)}"


def edges(trail: list) -> list:
    return list(zip(trail, trail[1:]))


def _strip_self_edges(tau: dict, meta: dict) -> tuple:
    """Enforce the W5 credit-hygiene law at the READ boundary. The deposit filter stops NEW self-edges (a→a),
    but pre-filter residue (or an edge restored from an old backup) only DECAYS — slowly, even in an actively
    depositing class. A self-edge is never a routing transition, so drop any on load: the consumer never sees
    them (recall/splice stay clean) and they persist OUT on the next save (deposit or PreCompact). Cheap,
    idempotent. Returns (clean_tau, clean_meta)."""
    def _is_self(k):
        a, _, b = k.partition(_SEP)
        return a == b
    tau = {k: w for k, w in tau.items() if not _is_self(k)}
    if meta:
        meta = {k: m for k, m in meta.items() if k in tau}
    return tau, meta


@dataclass
class Colony:
    """Per-GOAL-CLASS consequence-sourced pheromone over verb-altitude decision-edges. One colony per
    discovered class (the cue-classifier's label) → similar tasks converge together; persisted as
    ``colony_<label>.json`` so the splice can surface just the matching class's memory."""

    label: str = "_default"                   # the goal-class this colony belongs to
    tau: dict = field(default_factory=dict)   # "src\tdst" -> weight
    deposits: int = 0                         # total successful-path deposits (provenance)
    meta: dict = field(default_factory=dict)  # F3 per-edge provenance: "src\tdst" -> {"ts": float, "model": str}
    consolidations: int = 0                   # circadian sleeps applied (Q1: attributes deposit-free τ decay)
    last_consolidated: float = 0.0            # epoch of the latest consolidate (same convention as meta.ts)
    # ---- write-integrity flags (ADR-020; never persisted — save() builds its dict explicitly) ----
    _load_degraded: bool = field(default=False, repr=False)   # W2: store unreadable at load → save() refuses
    _lock_failopen: bool = field(default=False, repr=False)   # W4: locked() couldn't acquire → telemetry

    # ---- the ant mechanism ----
    def deposit(self, es: list, weight: float = 1.0, prune: float | None = None,
                ts: float | None = None, model: str = "") -> None:
        """Decay all edges, reinforce the (successful) path's edges by ``weight*DEPOSIT``, prune the dust.
        Consequence-sourced: the caller deposits ONLY on a verified exit 0. ``weight`` < 1 is the
        session-quality discount (a flailing session lays weaker pheromone — its clutter is born near the
        prune floor and self-cleans fast). See `hook._deposit_weight`. ``prune`` overrides the static
        floor with the endocrine system's allostatic value (None → the static ``PRUNE``); see
        [[endocrine.py]]. The per-edge **eligibility trace** (organ 3D) weights each edge by recency to the
        consequence (``γ^Δ``; uniform when ELIG_MODE 'off') — the ah-ha crystallizes, the flail prefix fades.
        ``ts``/``model`` are the **F3 provenance** stamp (organ): when ``ts`` is given, each reinforced edge
        records ``meta[edge]={ts,model}`` so the readout can decay by recency/version-distance. ``ts=None`` (the
        default) leaves ``meta`` untouched — byte-identical to the pre-F3 deposit."""
        if not es:
            return
        floor = PRUNE if prune is None else prune
        base = max(0.0, float(weight)) * DEPOSIT
        elig = _eligibility(len(es))      # 3D credit trace (all-1.0 when 'off' → uniform, the status quo)
        for k in list(self.tau):
            self.tau[k] *= DECAY
        for (a, b), e in zip(es, elig):
            if a == b:                       # W5 credit-hygiene: a self-edge (a→a) is not a TRANSITION — the
                continue                     # gauge found self-edges = 16% of τ-mass (Read→Read, cd→cd, …).
            k = f"{a}{_SEP}{b}"              # Never deposit them; existing self-edges decay out. Decay + the
            self.tau[k] = self.tau.get(k, 0.0) + base * e   # deposit count still run (a consequence happened).
            if ts is not None:               # F3: stamp the freshly-reinforced edge (newest deposit wins)
                self.meta[k] = {"ts": float(ts), "model": str(model or "")}
        self.tau = {k: w for k, w in self.tau.items() if w >= floor}
        if self.meta:                        # keep the provenance lane in sync with the pruned τ
            self.meta = {k: m for k, m in self.meta.items() if k in self.tau}
        self.deposits += 1

    def _eff_tau(self, now: float | None = None) -> dict:
        """τ as seen by READOUT (organ F3). ``PROV_MODE`` 'off' (or no provenance recorded) → the raw τ (the
        verified status quo, no copy). 'recency'/'full' → each edge's τ scaled by its age-decay; 'full' also
        applies ``PROV_VERSION_PENALTY`` when the stamped model differs from the current one (``EXOCORTEX_MODEL``
        — empty until model-id sourcing is wired, so the version term is inert by default). Non-destructive: the
        on-disk τ is unchanged; only ranking/splice see the decayed view. Legacy unstamped edges → weight 1.0."""
        if PROV_MODE not in ("recency", "full") or not self.meta:
            return self.tau
        ref = time.time() if now is None else now
        cur_model = os.environ.get("EXOCORTEX_MODEL", "")
        out = {}
        for k, w in self.tau.items():
            m = self.meta.get(k) or {}
            w2 = w * _recency_weight(m.get("ts"), ref)
            if PROV_MODE == "full" and cur_model and m.get("model") and m.get("model") != cur_model:
                w2 *= PROV_VERSION_PENALTY
            out[k] = w2
        return out

    def consolidate(self, prune: float | None = None, cap: int | None = None) -> None:
        """The circadian sleep: one decay pass, prune sub-floor, then cap to the strongest CAP edges
        (the slime-mold keeps the network lean — weak exploratory edges are forgotten). ``prune``/``cap``
        override the static constants with the endocrine system's allostatic values (None → static
        ``PRUNE``/``CAP``) — a stressed session sleeps leaner. See [[endocrine.py]].

        NOTE (Q1, Desktop audit 2026-07-01): this is the ONE deposit-free τ writer — it runs across every
        class on PreCompact (``hook.handle_precompact``), so τ can drop ~10% (one ``DECAY`` pass) and weak
        edges can vanish while ``deposits`` stays frozen. That is designed circadian behavior, not drift;
        the ``consolidations``/``last_consolidated`` stamp makes it attributable from the store."""
        floor = PRUNE if prune is None else prune
        ceiling = CAP if cap is None else cap
        for k in list(self.tau):
            self.tau[k] *= DECAY
        self.tau = {k: w for k, w in self.tau.items() if w >= floor}
        if len(self.tau) > ceiling:
            self.tau = dict(sorted(self.tau.items(), key=lambda kv: -kv[1])[:ceiling])
        if self.meta:                        # F3: keep provenance in lockstep with the pruned/capped τ
            self.meta = {k: m for k, m in self.meta.items() if k in self.tau}   # mirror deposit(); else orphans
        self.consolidations += 1
        self.last_consolidated = time.time()

    # ---- read-out ----
    def top(self, k: int = 8) -> list:
        return sorted(self._eff_tau().items(), key=lambda kv: -kv[1])[:k]

    def dominant_path(self, max_len: int = 6) -> list:
        """A greedy widest-path walk from the strongest edge's source — the converged 'how this project
        does it' route, rendered as a procedure. Heuristic (forward-only), for the splice's readability.
        Walks the F3 recency/version-adjusted τ (``_eff_tau``; identical to raw τ when PROV_MODE 'off')."""
        et = self._eff_tau()
        if not et:
            return []
        w = {tuple(k.split(_SEP)): v for k, v in et.items()}
        cur = max(w, key=lambda e: w[e])[0]
        path = [cur]
        while len(path) < max_len:
            outs = [(b, wt) for (a, b), wt in w.items() if a == cur and b not in path]
            if not outs:
                break
            cur = max(outs, key=lambda x: x[1])[0]
            path.append(cur)
        return path

    def splice(self, k: int = 8) -> str:
        """Render the consolidated memory as an ``additionalContext`` payload — the live context the
        slime-mold splices back. ABSTAINS (empty) until the class has some repetition (the anti-clutter
        discipline: never surface an unconverged one-off as if it were a reflex)."""
        if self.deposits < MIN_DEPOSITS_TO_SPLICE:
            return ""
        top = self.top(k)
        if not top:
            return ""
        lines = [f"[exocortex · consequence-sourced procedural memory — class: {self.label}]",
                 "Routes that have led to VERIFIED success for this kind of task "
                 "(pheromone τ; deposited only on exit 0 — never on failure):"]
        for key, wt in top:
            a, b = key.split(_SEP)
            lines.append(f"  {a} → {b}   (τ={wt:.2f})")
        chain = self.dominant_path()
        if len(chain) >= 2:
            lines.append("Dominant route (greedy widest path): " + " → ".join(chain))
        lines.append(f"({self.deposits} successful-path deposits · {len(self.tau)} edges retained "
                     f"after consolidation)")
        return "\n".join(lines)

    # ---- persistence (per goal-class; mirror of SessionState) ----
    def _path(self):
        return state_dir() / f"colony_{_safe(self.label)}.json"

    def save(self) -> None:
        try:
            if getattr(self, "_load_degraded", False):
                return   # ADR-020 W2: never write back over a store we failed to read (the τ-wipe
            #              amplifier — the quarantine was already audited at load time)
            d = {"label": self.label, "tau": self.tau, "deposits": self.deposits}
            if self.meta:                    # F3: omit the lane entirely when empty → pre-F3 colonies stay byte-identical
                d["meta"] = self.meta
            if self.consolidations:          # Q1: omit-when-zero keeps never-consolidated stores byte-identical
                d["consolidations"] = self.consolidations
                d["last_consolidated"] = self.last_consolidated
            atomic_write_text(self._path(), json.dumps(d))   # ADR-020 W1: a reader never sees a torn store
        except Exception:
            pass   # a hook must never crash the agent

    def _populate(self, d: dict, label: str = "_default") -> bool:
        """Fill this instance from a parsed store dict. False (and write-refusal) on malformed fields —
        writing back a PARTIALLY parsed colony loses the unparsed remainder (same law as a torn read)."""
        try:
            self.label = str(d.get("label", label))
            self.tau = {str(k): float(v) for k, v in dict(d.get("tau", {})).items()}
            self.deposits = int(d.get("deposits", 0))
            self.meta = {str(k): dict(v) for k, v in dict(d.get("meta", {})).items()}
            self.consolidations = int(d.get("consolidations", 0))
            self.last_consolidated = float(d.get("last_consolidated", 0.0))
            self.tau, self.meta = _strip_self_edges(self.tau, self.meta)   # W5: enforce no self-edges on read
            return True
        except Exception:
            self._load_degraded = True
            return False

    @classmethod
    def load(cls, label: str = "_default") -> "Colony":
        col = cls(label=label)
        d, degraded = load_store_json(col._path())   # ADR-020 W2: unreadable → quarantined + audited
        col._load_degraded = degraded
        if isinstance(d, dict):
            col._populate(d, label)
        return col

    @classmethod
    def all(cls) -> list:
        """Every discovered class's colony (for the PreCompact consolidation sweep)."""
        out = []
        for f in glob.glob(str(state_dir() / "colony_*.json")):
            d, _ = load_store_json(f)   # degraded → skipped this sweep (quarantined, never clobbered)
            if not isinstance(d, dict):
                continue
            col = cls()
            if col._populate(d):
                out.append(col)
        return out

    @classmethod
    @contextlib.contextmanager
    def locked(cls, label: str = "_default", timeout: float = 2.0):
        """Exclusive load-modify-save critical section for this CLASS's colony file (ADR-020 W3).

        The deposit and the PreCompact consolidation sweep are cross-PROCESS read-modify-writes on
        ``colony_<label>.json`` — the session lock never protected them (two sessions share a class's
        colony, and the sweep held no lock at all: a deposit landing mid-sweep was silently
        overwritten). Same sidecar-lock discipline as the audit chain / ``SessionState.locked``, and
        the same lock-ORDER law: **session before colony, never the reverse** (the deposit path
        acquires this inside ``SessionState.locked``; the sweep takes colony locks one class at a
        time, all released before the session flag-write). FAIL-OPEN on timeout — a hook must never
        wedge the agent; the acquisition result is surfaced as ``_lock_failopen`` on the yielded
        instance for the W4 contention telemetry.

        Usage: ``with Colony.locked(label) as col: col.deposit(...); col.save()``"""
        from .integrity import append_lock
        path = cls(label=label)._path()
        with append_lock(path, timeout=timeout) as got:
            col = cls.load(label)
            col._lock_failopen = not got
            yield col
