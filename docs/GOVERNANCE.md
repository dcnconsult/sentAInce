# Governance — what the organism gives a governed fleet

SentAInce positions as **the memory + guardrail organ for governed agent fleets**: not an agent, not a
framework — the organ you attach to the agents you already run, so that what they remember is *earned*,
what they do is *recorded*, and what they must not do is *bounded by policy you set*. Everything below is
a mechanism that exists on the record (an ADR you can read, a gauge you can re-run), not a brochure claim.

Status tags follow [STORY.md](STORY.md): **SHIPPED** runs today · **IN DESIGN** is being shaped ·
**PROPOSED** is designed on the record, not yet built.

## The mapping: corporate need → primitive on the record

| Corporate need | SentAInce primitive | Mechanism on the record | Status |
|---|---|---|---|
| **Compliance trail** — show an auditor what every agent did, when, and that nothing was rewritten | Hash-chained audit trail | The ADR-009 audit chain (one layer of the cryptographic immune system); ADR-018 strict tail anchor + checkpointing (a truncated or spliced chain fails loudly) | **SHIPPED** |
| **Tamper evidence** — prove the agent's memory wasn't edited out-of-band | Tamper-evident memory | ADR-017 colony snapshot LtHash digest over the mutable procedural layer; ADR-016 control-plane pin as a governance gate, re-baselined *on the record* — never silently | **SHIPPED** |
| **Policy-bound deployment** — roll out to a fleet without surprising anyone | Dormant defaults + allowlists | Everything ships **off** until explicitly enabled; `observe` mode audits without blocking; fail-open by construction; surgical uninstall leaves the host repo untouched | **SHIPPED** |
| **Memory that can't be poisoned by reads** — retrieval-time injection cannot become tomorrow's "knowledge" | Earned memory | ADR-001: retrieval NEVER writes — trust (τ) deposits only on a verified success (exit 0). Reading, querying, and prompting create no memory at all | **SHIPPED** |
| **Runtime command guardrail** — a reflex between the agent and a destructive command | Somatic veto | Hook-level interception with an explicit vocabulary. Honest scope: the vocabulary is Bash-shaped — on Windows hosts PowerShell commands are *audited but not vetoed* (see the exocortex README) | **SHIPPED** (scoped) |
| **Fleet directory interop** — the organ discoverable and reachable by emerging agent-governance stacks | AGNTCY / OASF surface | [`oasf-record.json`](../oasf-record.json) (OASF schema 1.0.0) describes the MCP memory server; the server speaks `stdio`, `sse`, and `streamable-http` | **SHIPPED** (record + transport) · directory listing **IN DESIGN** |

## AGNTCY interop, concretely

The read-only memory server is the consume-side surface a governed fleet talks to:

```bash
# local host (default, unchanged): stdio
python exocortex/mcp_server.py

# remote MCP on the current convention (bind stays loopback unless you say otherwise)
python exocortex/mcp_server.py --transport streamable-http --host 127.0.0.1 --port 8001
```

Two properties hold regardless of transport:

- **Read-only w.r.t. memory.** The transport changes who can *reach* the tools, never what the tools can
  *do* — no τ deposit, no note write, no classifier persistence, over any transport (ADR-001).
- **Loopback by default.** `--host 0.0.0.0` is a decision you make, behind a tunnel/proxy you trust.

The [OASF record](../oasf-record.json) is the machine-readable card for this server (skills from the OASF
taxonomy, source locator, version pinned to the release). It is data, not aspiration: if the record and
the code disagree, the record is wrong and we fix the record.

## What governance does *not* get

- **No telemetry.** Nothing phones home — not usage, not metrics, not errors. Momentum is watched from
  public surfaces (clones, discussions), never from inside your deployment.
- **No remote control.** There is no channel by which a directory, a vendor, or this project can change
  a deployed organism's behavior. Policy lives in your repo, in files you version.
- **No evidence by assertion.** A rendered verdict is a legible claim, not evidence. The gauges that back
  the rows above re-run locally (`docs/QUICKSTART.md`); a demonstration is not a proof, and the README's
  evidence lock (C1–C7) marks exactly which claims survived their controls.

## RFC

This mapping is a draft contract with people who run fleets for a living. If a row overstates, understates,
or misses your compliance reality, say so: [GitHub Discussions](https://github.com/dcnconsult/sentAInce/discussions)
— the RFC thread for this document invites exactly that falsification.
