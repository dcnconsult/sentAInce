"""SentAInce Cerebral Substrate (Slice 0) — the additive, off-hot-path organ that will wire G.A.R.D.
Governance / Alliance / Dignity at portfolio altitude and hold long-term memory.

Everything here is ADDITIVE and READ-ONLY with respect to the organism: it observes and reorganizes the
*record*, but it never earns τ, never writes a colony / session / audit, and never touches the vault it
reads. Only an ``exit 0`` in a live body still earns memory (ADR-001). Nothing in this package modifies
the locked organs or the 99-test deterministic lock under ``tests/`` — this package's own tests live under
``cerebral/tests/`` and are run explicitly (``python -m pytest cerebral/tests``), mirroring ``battle/``.

Slice 0 scope (this commit): **gauge-first (ADR-002)**. Before building the persistent living ledger, the
Consolidator, the Governor, or any actuator, this ships ONE read-only offline gauge — the *TAO Resurrection
Gauge* — that measures whether the intent register can surface genuinely-lost, worth-resuming research
threads. The number it produces (precision @ worth-resuming) gates every downstream Substrate slice. A live
run over a real vault is a **labeled demonstration, never evidence**.

Design: ``../SentAInce_Cerebral_Substrate_Design_Review_v1.1.md`` (outside the repo, pre-counsel).
"""
