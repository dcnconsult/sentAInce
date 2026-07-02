"""CgroupEnergyReader — the real interoceptive energy gauge (M3).

Feeds the BODY container's real cgroup-v2 memory headroom (read via the in-body agent's /vitals, so
the organism holds no Docker socket) into ``MetabolicLedger``'s injectable reader. As a memory flood
drives the body's ``memory.current`` toward ``memory.max``, headroom → 0, the gauge read → 0, and the
gearbox trips into hypoxia on MEASURED load (the C2 honest-boundary swap).
"""
from __future__ import annotations

from .body_client import BodyAgentClient


class CgroupEnergyReader:
    def __init__(self, client: BodyAgentClient, e0: float) -> None:
        self.client = client
        self.e0 = float(e0)

    def __call__(self) -> float:
        try:
            headroom = self.client.vitals().get("mem_headroom")
        except OSError:
            return self.e0  # can't read the gauge → assume full (fail-open on the gauge, not on safety)
        if headroom is None:
            return self.e0
        return self.e0 * float(headroom)
