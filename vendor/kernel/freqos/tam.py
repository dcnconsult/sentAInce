"""Z3 Potts-Hopfield Triadic Associative Memory (TAM) + matched binary baseline.

A *native*, backprop-free associative memory: patterns are phase-encoded HDC vectors
(Z3 phase labels ``{0,1,2}`` = cube roots ``{1, omega, omega^2}``), stored Hebbian-ly,
and recalled by deterministic energy relaxation (field-settle). The matched binary
(Z2, ``{-1,+1}``) Hopfield is the *fair same-task* comparator.

Hamiltonian (SSR): ``H = -(M/2) * sum_k Re[m_k^p]`` with
``m_k = (1/M) * sum_i omega^((q_i - xi_i^k) mod 3)``.

Honest scope: recall is **O(K*M) per sweep** (p=4 is O(K^2*M)/sweep) -- comparable to a
matmul, not a complexity win. Above capacity, recall degrades (and at very high load only
a *random* stored pattern is returned). So cued recall is measured **below capacity**,
where the Z3 edge over binary is real but modest (phasor-network theory). Algorithmic
reference: ``brAIn/experiments/e1_assoc_capacity.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

OMEGA = np.exp(2j * np.pi / 3.0)


# --------------------------------------------------------------- HDC phase ops
def random_patterns(k: int, m: int, rng: np.random.Generator) -> np.ndarray:
    """K random Z3 phase patterns, shape (K, M), values in {0,1,2}."""
    return rng.integers(0, 3, size=(k, m)).astype(np.int8)


def random_binary(k: int, m: int, rng: np.random.Generator) -> np.ndarray:
    """K random binary patterns, shape (K, M), values in {-1,+1}."""
    return rng.choice(np.array([-1, 1], dtype=np.int8), size=(k, m))


def _phase_of(z: np.ndarray) -> np.ndarray:
    """Nearest Z3 phase label {0,1,2} to each complex number's angle."""
    return np.mod(np.rint(np.angle(z) / (2 * np.pi / 3.0)), 3).astype(np.int8)


def corrupt(phase: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    """Randomize a fraction ``frac`` of components to a uniform random phase {0,1,2}."""
    return _corrupt(np.asarray(phase).astype(np.int8), frac, rng, lambda n: rng.integers(0, 3, n))


def corrupt_binary(state: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    """Randomize a fraction ``frac`` of components to a uniform random sign {-1,+1}."""
    return _corrupt(np.asarray(state).astype(np.int8), frac, rng, lambda n: rng.choice([-1, 1], n))


def _corrupt(arr: np.ndarray, frac: float, rng, draw) -> np.ndarray:
    out = arr.copy()
    flat = out.reshape(-1, out.shape[-1])
    n = int(round(frac * flat.shape[-1]))
    if n:
        for row in flat:
            idx = rng.choice(flat.shape[-1], size=n, replace=False)
            row[idx] = np.asarray(draw(n), dtype=np.int8)
    return flat.reshape(out.shape)


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """HDC bind = phase addition mod 3 (complex multiply of cube roots)."""
    return ((np.asarray(a) + np.asarray(b)) % 3).astype(np.int8)


def permute(a: np.ndarray, shift: int = 1) -> np.ndarray:
    """HDC permute = cyclic shift along the last axis."""
    return np.roll(a, shift, axis=-1)


def bundle(phases: np.ndarray) -> np.ndarray:
    """HDC bundle = phasor-sum majority of stacked phase vectors -> phase labels."""
    z = np.exp(2j * np.pi * np.asarray(phases) / 3.0).sum(axis=0)
    return _phase_of(z)


# --------------------------------------------------------------- the memory
@dataclass
class RecallResult:
    state: np.ndarray  # recalled state(s): phase {0,1,2} (z3) or {-1,1} (binary)
    sweeps: np.ndarray  # per-cue sweeps to convergence
    overlap: np.ndarray  # per-cue overlap to its target in [0,1]
    success: np.ndarray  # per-cue overlap >= threshold
    flops: float  # total field-settle FLOPs (analytic)


class TAM:
    """Associative memory; ``kind='z3'`` (complex Potts) or ``'binary'`` (Z2 Hopfield)."""

    def __init__(self, kind: str = "z3") -> None:
        if kind not in ("z3", "binary"):
            raise ValueError("kind must be 'z3' or 'binary'")
        self.kind = kind
        self.patterns: np.ndarray | None = None
        self._enc: np.ndarray | None = None  # (K, M) complex (z3) or +-1 float (binary)

    def store(self, patterns: np.ndarray) -> None:
        """Hebbian storage: z3 patterns in {0,1,2}; binary patterns in {-1,+1}."""
        p = np.asarray(patterns).astype(np.int8)
        self.patterns = p
        self._enc = (OMEGA**p) if self.kind == "z3" else p.astype(np.float64)

    def _enc_state(self, state: np.ndarray) -> np.ndarray:
        if self.kind == "z3":
            return OMEGA ** np.asarray(state)
        return np.asarray(state, dtype=np.float64)

    def _overlaps(self, s_enc: np.ndarray) -> np.ndarray:
        """m_k = (1/M) conj(xi) . s  -> (B, K)."""
        assert self._enc is not None, "call store() first"
        return (s_enc @ np.conjugate(self._enc).T) / self._enc.shape[1]

    def energy(self, state: np.ndarray, p: int = 2) -> np.ndarray:
        """SSR energy H = -(M/2) sum_k Re[m_k^p] per cue."""
        assert self._enc is not None, "call store() first"
        m = self._overlaps(self._enc_state(np.atleast_2d(state)))
        return -0.5 * self._enc.shape[1] * np.real(m**p).sum(axis=1)

    def recall(
        self,
        cue: np.ndarray,
        p: int = 2,
        max_sweeps: int = 64,
        target: np.ndarray | int | None = None,
        threshold: float = 0.9,
    ) -> RecallResult:
        """Relax corrupted cue(s) to a fixed point via deterministic field-settle."""
        assert self._enc is not None, "call store() first"
        xi = self._enc
        k, m_dim = xi.shape
        state = np.atleast_2d(cue).astype(np.int8 if self.kind == "z3" else np.int64).copy()
        b = state.shape[0]

        conv = np.full(b, max_sweeps, dtype=np.int64)
        done = np.zeros(b, dtype=bool)
        for sweep in range(1, max_sweeps + 1):
            s_enc = self._enc_state(state)
            m = self._overlaps(s_enc)  # (B, K)
            if p == 2:
                field = m @ xi  # (B, M)
            else:
                loo = m[:, :, None] - (np.conjugate(xi)[None] * s_enc[:, None, :]) / m_dim
                field = np.einsum("bkm,km->bm", np.abs(loo) ** (p - 2) * loo, xi)
            new = _phase_of(field) if self.kind == "z3" else np.where(np.real(field) >= 0, 1, -1)
            changed = np.any(new != state, axis=1)
            conv[(~changed) & (~done)] = sweep
            done |= ~changed
            state = new
            if done.all():
                break

        if target is None:
            tgt = np.zeros(b, np.int64)
        else:
            tgt = np.atleast_1d(np.asarray(target)).astype(np.int64)
        ov = np.abs(self._overlaps(self._enc_state(state))[np.arange(b), tgt])
        const = 8 if self.kind == "z3" else 2  # complex ~4x real arithmetic per MAC
        flops = float(const * k * m_dim * int(conv.sum()))
        return RecallResult(state, conv, ov, ov >= threshold, flops)


def success_rate(
    m: int, k: int, kind: str, p: int, corrupt_frac: float, n_probe: int, rng, max_sweeps: int = 64
) -> tuple[float, float]:
    """(mean cued-recall success, mean sweeps) for K random patterns in an M-neuron TAM."""
    if kind == "z3":
        pats = random_patterns(k, m, rng)
        cue_fn = corrupt
    else:
        pats = random_binary(k, m, rng)
        cue_fn = corrupt_binary
    tam = TAM(kind)
    tam.store(pats)
    idx = rng.integers(0, k, size=n_probe)
    cues = cue_fn(pats[idx], corrupt_frac, rng)
    res = tam.recall(cues, p=p, max_sweeps=max_sweeps, target=idx)
    return float(np.mean(res.success)), float(np.mean(res.sweeps))
