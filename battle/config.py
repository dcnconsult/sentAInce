"""Configuration for a battle-test episode.

Frozen dataclasses so an episode's parameters are explicit and reproducible. The energy numbers
mirror the deterministic regime of ``experiments/exp7_crucible.py`` (a survival reserve below which
cognition is throttled); the head config names the real LLM seam used from M1 onward.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_MODEL = "llama3.1:8b"
# Ollama's OpenAI-compatible endpoint. The same adapter targets vLLM / llama.cpp / hosted APIs by
# changing only this base_url (+ api_key) — the head stays swappable behind one Proposer.
DEFAULT_BASE_URL = "http://localhost:11434/v1"


@dataclass(frozen=True)
class HeadConfig:
    """The real-LLM head (used from M1; ignored by the M0 deterministic ScriptedProposer)."""

    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    api_key: str | None = None


@dataclass(frozen=True)
class EnergyConfig:
    """The metabolic regime. ``e0`` is the starting fuel; ``e_reserve`` is the survival floor that
    gates cognition (hypoxia). The oracle veto is energy-INDEPENDENT and never reads these."""

    e0: float = 200.0
    diagnose_cost: float = 20.0   # cost to "think" (call the head / run a novel diagnosis) per tick
    e_reserve: float = 60.0       # GearboxPolicy survival floor
    panic_cost: float = 20.0      # representative diagnosis cost defining the hypoxic regime


@dataclass(frozen=True)
class EpisodeConfig:
    # the one witnessed-harm that trains the adaptive antibody (one-shot), exactly as exp7's ANCHOR
    anchor: str = "rm -rf /backups"
    head: HeadConfig = field(default_factory=HeadConfig)
    energy: EnergyConfig = field(default_factory=EnergyConfig)
