"""freqos — the vendored Z3 Potts-Hopfield Triadic Associative Memory (community subset).

This community build ships only the kernel modules the SentAInce organism actually uses — the Z3 HDC
primitives (``tam``) and the holonomy/routing seam (``phase_router`` and its capacity deps). The broader
FreqOS research library (the anti-glass capacity theorems, the quantum/QHDC interface, the topology audit,
and the other associative-memory experiments) is not part of this distribution.

Submodules are imported explicitly (``from freqos.tam import ...``); this package ``__init__`` intentionally
loads nothing eagerly.

Claim boundary: deterministic emulator and implementation ledger only.
"""
from __future__ import annotations
