"""Read-only shim over the frozen ``circle_of_fifths_rc2`` substrate.

SentAInce is additive: it never modifies the kernel, never crosses lock ``0985067`` or the
organism/RAG freeze tags. Experiment 1 does not import kernel code — the interlock reuses
the *pattern* of ``effective_adjacency`` on a separate code path, not the code itself. This
shim only *locates* the sibling kernel for later phases and asserts the read-only posture.
"""
from __future__ import annotations

from pathlib import Path

KERNEL_DIRNAME = "circle_of_fifths_rc2"


def locate_kernel(start: Path | None = None) -> Path | None:
    """Return the path to the sibling frozen kernel if present, else ``None``. Never writes."""
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        candidate = parent / KERNEL_DIRNAME
        if candidate.is_dir():
            return candidate
    return None
