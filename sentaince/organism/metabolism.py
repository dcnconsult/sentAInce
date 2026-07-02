"""MetabolicLedger — a finite energy pool with an interoceptive gauge read.

The organism spends energy to act (cheap reflex, expensive diagnosis) and reads its own
gauge before deciding. ``E`` is the fuel; ``alive`` is ``E > 0`` (compute bankruptcy = death).
The reader is injectable: the default reads the internal pool deterministically; a real
``docker stats`` reader is a later additive swap (Phase II.b), mapping host CPU/RAM/Time onto
the same gauge. Energy is the v1.02 metabolism remapped from RAG depth to host resources.
"""
from __future__ import annotations

from typing import Callable


class MetabolicLedger:
    """A finite energy pool. ``spend`` drains it; ``energy`` is the interoceptive read."""

    def __init__(self, e0: float = 1.0, reader: Callable[[], float] | None = None) -> None:
        self.e0 = float(e0)
        self._e = float(e0)
        self._reader = reader  # None → read the internal pool (deterministic)

    @property
    def E(self) -> float:
        return self._e

    def energy(self) -> float:
        """Interoceptive gauge read (the organism looking at its own fuel)."""
        return float(self._reader()) if self._reader is not None else self._e

    def spend(self, cost: float) -> None:
        self._e -= float(cost)

    def recharge(self, amount: float) -> None:
        """Add energy (e.g. solar input). The metabolic primitive handles regen, not just drain."""
        self._e += float(amount)

    @property
    def alive(self) -> bool:
        return self._e > 0.0
