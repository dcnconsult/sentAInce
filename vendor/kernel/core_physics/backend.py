"""Hardware-target backend abstraction for the batched phi6 kinetic kernel.

The kinetic settle kernel is written once against a small, uniform op set so it
can run on NumPy (AVX2/AVX-512 via the system BLAS) or on torch tensors (CPU in
this gate; CUDA/MPS deferred). Default working dtype is float32 (FP32) per the
v0.40 engineering directive: modern CPUs process 8 FP32 FMA ops/clock in AVX2,
16 in AVX-512, so float64 halves SIMD lanes and L1/L2 locality.

Claim boundary: deterministic emulator and implementation ledger only.
"""
from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["Backend", "NumpyBackend", "TorchBackend", "NUMPY", "get_backend"]


class Backend:
    """Uniform op surface the kernel needs. Concrete subclasses bind to a library."""

    name: str
    float32: Any
    float64: Any

    # --- construction / dtype -------------------------------------------------
    def asarray(self, x, dtype):  # noqa: D102
        raise NotImplementedError

    def dtype_of(self, x, default):  # noqa: D102
        raise NotImplementedError

    def copy(self, x):  # noqa: D102
        raise NotImplementedError

    def transpose2d(self, x):  # noqa: D102
        raise NotImplementedError

    # --- allocation -----------------------------------------------------------
    def zeros_like(self, x):  # noqa: D102
        raise NotImplementedError

    def zeros_row(self, n, dtype):  # noqa: D102
        raise NotImplementedError

    def ones_bool(self, n):  # noqa: D102
        raise NotImplementedError

    def full_int(self, n, val):  # noqa: D102
        raise NotImplementedError

    # --- elementwise / reductions --------------------------------------------
    def matmul(self, a, b):  # noqa: D102
        raise NotImplementedError

    def clip(self, x, lo, hi):  # noqa: D102
        raise NotImplementedError

    def abs(self, x):  # noqa: D102
        raise NotImplementedError

    def where(self, cond, a, b):  # noqa: D102
        raise NotImplementedError

    def where_int(self, cond, scalar, arr):  # noqa: D102
        raise NotImplementedError

    def col(self, x):  # noqa: D102
        raise NotImplementedError

    def max_rows(self, x):  # noqa: D102
        raise NotImplementedError

    def mean_abs_rows(self, x):  # noqa: D102
        raise NotImplementedError

    def rows_all_equal(self, a, b):  # noqa: D102
        raise NotImplementedError

    def ternary_slice(self, x, thr):  # noqa: D102
        raise NotImplementedError

    def any(self, x) -> bool:  # noqa: D102
        raise NotImplementedError

    def to_numpy(self, x) -> np.ndarray:  # noqa: D102
        raise NotImplementedError

    # --- row compaction (integer-index gather/scatter) -----------------------
    def arange_int(self, n):  # noqa: D102
        raise NotImplementedError

    def gather(self, x, idx):  # noqa: D102
        raise NotImplementedError

    def scatter_(self, x, idx, src):  # noqa: D102
        raise NotImplementedError

    def mask_select(self, x, boolmask):  # noqa: D102
        raise NotImplementedError


class NumpyBackend(Backend):
    name = "numpy"
    float32 = np.float32
    float64 = np.float64

    def asarray(self, x, dtype):
        return np.asarray(x, dtype=dtype)

    def dtype_of(self, x, default):
        dt = getattr(x, "dtype", None)
        return dt if dt is not None and np.issubdtype(dt, np.floating) else default

    def copy(self, x):
        return np.array(x, copy=True)

    def transpose2d(self, x):
        return x.T

    def zeros_like(self, x):
        return np.zeros_like(x)

    def zeros_row(self, n, dtype):
        return np.zeros(n, dtype=dtype)

    def ones_bool(self, n):
        return np.ones(n, dtype=bool)

    def full_int(self, n, val):
        return np.full(n, val, dtype=np.int64)

    def matmul(self, a, b):
        return a @ b

    def clip(self, x, lo, hi):
        return np.clip(x, lo, hi)

    def abs(self, x):
        return np.abs(x)

    def where(self, cond, a, b):
        return np.where(cond, a, b)

    def where_int(self, cond, scalar, arr):
        return np.where(cond, scalar, arr)

    def col(self, x):
        return x[:, None]

    def max_rows(self, x):
        return np.max(x, axis=-1)

    def mean_abs_rows(self, x):
        return np.mean(np.abs(x), axis=-1)

    def rows_all_equal(self, a, b):
        return np.all(a == b, axis=-1)

    def ternary_slice(self, x, thr):
        return (x > thr).astype(x.dtype) - (x < -thr).astype(x.dtype)

    def any(self, x) -> bool:
        return bool(np.any(x))

    def to_numpy(self, x) -> np.ndarray:
        return np.asarray(x)

    def arange_int(self, n):
        return np.arange(n, dtype=np.int64)

    def gather(self, x, idx):
        return x[idx]

    def scatter_(self, x, idx, src):
        x[idx] = src
        return x

    def mask_select(self, x, boolmask):
        return x[boolmask]


class TorchBackend(Backend):
    name = "torch"

    def __init__(self) -> None:
        import torch  # imported lazily so torch stays an optional dependency

        self._t = torch
        self.float32 = torch.float32
        self.float64 = torch.float64

    def asarray(self, x, dtype):
        t = self._t
        if isinstance(x, t.Tensor):
            return x.to(dtype)
        return t.as_tensor(np.asarray(x), dtype=dtype)

    def dtype_of(self, x, default):
        t = self._t
        if isinstance(x, t.Tensor) and x.dtype in (t.float32, t.float64):
            return x.dtype
        return default

    def copy(self, x):
        return x.clone()

    def transpose2d(self, x):
        return x.transpose(0, 1)

    def zeros_like(self, x):
        return self._t.zeros_like(x)

    def zeros_row(self, n, dtype):
        return self._t.zeros(n, dtype=dtype)

    def ones_bool(self, n):
        return self._t.ones(n, dtype=self._t.bool)

    def full_int(self, n, val):
        return self._t.full((n,), val, dtype=self._t.int64)

    def matmul(self, a, b):
        return a @ b

    def clip(self, x, lo, hi):
        return self._t.clamp(x, lo, hi)

    def abs(self, x):
        return self._t.abs(x)

    def where(self, cond, a, b):
        return self._t.where(cond, a, b)

    def where_int(self, cond, scalar, arr):
        return self._t.where(cond, self._t.full_like(arr, scalar), arr)

    def col(self, x):
        return x.unsqueeze(1)

    def max_rows(self, x):
        return self._t.max(x, dim=-1).values

    def mean_abs_rows(self, x):
        return self._t.mean(self._t.abs(x), dim=-1)

    def rows_all_equal(self, a, b):
        return self._t.all(a == b, dim=-1)

    def ternary_slice(self, x, thr):
        return (x > thr).to(x.dtype) - (x < -thr).to(x.dtype)

    def any(self, x) -> bool:
        return bool(self._t.any(x))

    def to_numpy(self, x) -> np.ndarray:
        return x.detach().cpu().numpy()

    def arange_int(self, n):
        return self._t.arange(int(n), dtype=self._t.int64)

    def gather(self, x, idx):
        return x[idx]

    def scatter_(self, x, idx, src):
        x[idx] = src
        return x

    def mask_select(self, x, boolmask):
        return x[boolmask]


NUMPY = NumpyBackend()


def get_backend(name: str = "numpy") -> Backend:
    """Return a backend instance by name. ``"torch"`` requires the torch extra."""
    key = name.lower()
    if key == "numpy":
        return NUMPY
    if key == "torch":
        return TorchBackend()
    raise ValueError(f"unknown backend {name!r}; expected 'numpy' or 'torch'")
