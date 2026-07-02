"""Cerebral Substrate gauges — read-only, pure-stdlib, fail-open offline instruments (ADR-002).

Run explicitly (never collected by the 99-lock; ``pyproject testpaths=["tests"]``):

    python -m cerebral.gauge.resurrection_gauge --vault <path> --now <ISO> --json
"""
