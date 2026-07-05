# Codex Interface Feasibility Verdict

Date: 2026-07-04

> Feasibility precursor to the provider-probe spec — see
> [`docs/CODEX_PROVIDER_PROBE.md`](../../docs/CODEX_PROVIDER_PROBE.md). The `FINDINGS.md` evidence packet in
> this directory is produced later, once the live probe runs.

## Verdict

Codex should be able to interface with SentAInce without the ChatGPT Secure MCP Tunnel workspace/organization
blocker.

Codex has two local integration surfaces that map directly onto SentAInce's existing architecture:

- Local lifecycle hooks for gate, audit, splice, and consolidation behavior.
- Local MCP server configuration for read-only earned-memory recall.

This is not the same deployment substrate as ChatGPT Apps. The ChatGPT failure mode was connector visibility
across OpenAI Platform organization, ChatGPT workspace, tunnel ID, runtime key, and permissions. Codex local
CLI/app/IDE configuration instead loads project/user config on the connected host and can start local MCP
servers directly.

## Evidence

- Codex hooks are enabled by default and can be declared in `~/.codex/hooks.json`, `~/.codex/config.toml`,
  `<repo>/.codex/hooks.json`, or `<repo>/.codex/config.toml`. Project hooks require the normal Codex trust
  review flow, not ChatGPT workspace tunnel association.
- Codex hook events cover the main SentAInce control loop: `PreToolUse`, `PostToolUse`, `PreCompact`,
  `PostCompact`, `UserPromptSubmit`, and `SessionStart`.
- Codex matchers cover `Bash`, `apply_patch`, and MCP tool names, which is enough for a first provider probe.
- Codex MCP supports both local STDIO servers and streamable HTTP servers in `config.toml`, including localhost
  examples. The existing SentAInce MCP server can therefore be exposed without Secure MCP Tunnel.
- Codex remote access, when used, operates through the connected host's projects, files, credentials,
  permissions, plugins, local tools, and MCP setup. That means the local integration remains host-local even
  when steered from another Codex surface.

Primary docs checked:

- https://developers.openai.com/codex/hooks
- https://developers.openai.com/codex/mcp
- https://developers.openai.com/codex/remote-connections
- https://developers.openai.com/codex/app/local-environments

## SentAInce Fit

The existing `exocortex/hook.py` already emits a Claude-shaped `hookSpecificOutput` contract. Codex's
`PreToolUse` contract accepts the same `permissionDecision: "deny"` shape for blocking and the same
`additionalContext` shape for model-visible context. That makes a Codex provider additive rather than a
rewrite.

The current `exocortex/adapter.py` only knows `claude` and `cursor`, so the PR should add a `codex` provider
instead of treating Codex as Claude by accident. Codex-specific normalization should explicitly handle:

- `SessionStart` input fields and session identifiers.
- `PreToolUse`/`PostToolUse` `tool_name`, `tool_input`, `tool_response`, and `tool_use_id`.
- `PermissionRequest` as a separate event if we choose to participate in approval prompts.
- `PostCompact`, which SentAInce does not currently register.

## Caveats

- Codex runs multiple matching command hooks concurrently. A SentAInce hook can block the actual tool call, but
  it cannot prevent other matching hooks for the same event from starting.
- Codex docs say `PostToolUse` does not intercept all shell calls yet, especially richer `unified_exec` paths.
  This limits consequence observation until measured against real Codex traffic.
- `PostToolUse` cannot undo side effects; it can only replace feedback/model-visible output after a tool has run.
- `permissionDecision: "ask"` is parsed but not supported for `PreToolUse`; a Codex adapter should avoid emitting
  ask decisions as authoritative safety behavior.
- Project-local hooks still require Codex trust review. That is materially simpler than ChatGPT tunnel/workspace
  setup, but it is still a user-facing install step.

## Decision

Proceed toward a Codex PR, but make it a measured provider probe first.

Do not claim complete somatic boundary support until live Codex hook evidence proves:

- A planted lethal `Bash` or PowerShell-equivalent command is denied before execution.
- `apply_patch` events are observed and either gated or deliberately scoped out.
- MCP tool calls are observed by hook matchers when configured.
- `PostToolUse` contains enough output/status data for consequence classification.
- `UserPromptSubmit` and `SessionStart` inject/seed context as expected.
- `PreCompact` and `PostCompact` fire with `manual` and/or `auto` trigger data.

## Score

- Codex local MCP recall path: +1
- Codex local hook substrate: +1 for feasibility
- Codex as promoted SentAInce provider: 0 until live hook probe passes
- Same blocker as ChatGPT Secure MCP Tunnel: no

## Product Implication

Codex is the better near-term OpenAI integration target for local SentAInce than ChatGPT Apps. It aligns with
local-first hooks and local MCP, and it avoids the ChatGPT workspace/tunnel association blocker. The PR should be
framed as a Codex provider probe with acceptance tests and evidence capture, not as a polished average-user
install path yet.
