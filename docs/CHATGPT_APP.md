# ChatGPT Apps / remote-MCP integration

SentAInce can expose its earned memory to ChatGPT through a read-only MCP server. This lets ChatGPT ask what a local project has already learned without letting ChatGPT earn memory, mutate memory, or act as a host-side safety veto.

## Claim boundary

This integration is **memory consume only**.

It does:

- expose earned procedural/declarative memory to ChatGPT over MCP;
- provide OpenAI-friendly `search(query)` and `fetch(id)` tools;
- annotate tools as read-only when the installed MCP SDK supports `readOnlyHint`;
- preserve ADR-001: retrieval never creates memory.

It does **not**:

- install a ChatGPT Desktop somatic veto;
- intercept arbitrary ChatGPT or desktop actions before execution;
- run shell commands, edit files, create PRs, or write issues;
- deposit tau, write sigma, mutate colony/wiki/scar/config, or persist cue-classifier state.

Only the hook-side body can earn memory from a verified `exit 0` consequence chain. ChatGPT consumes memory; it does not promote retrieval into memory.

## Entrypoints

The existing MCP server remains available for local MCP clients:

```bash
sentaince-mcp
```

The ChatGPT-focused server adds the data-only `search`/`fetch` pair and defaults to SSE transport:

```bash
python -m pip install -e .[mcp]
sentaince-chatgpt-mcp --transport sse --host 127.0.0.1 --port 8000
```

For a stdio MCP host:

```bash
sentaince-chatgpt-mcp --transport stdio
```

For a remote ChatGPT Apps connection, place the server behind a trusted tunnel or reverse proxy and use the `/sse/` endpoint exposed by the MCP transport. Bind to `0.0.0.0` only when that tunnel/proxy is the boundary you intend:

```bash
sentaince-chatgpt-mcp --transport sse --host 0.0.0.0 --port 8000
```

Environment knobs:

```bash
SENTAINCE_CHATGPT_TRANSPORT=sse
SENTAINCE_CHATGPT_HOST=127.0.0.1
SENTAINCE_CHATGPT_PORT=8000
SENTAINCE_CHATGPT_BASE_URL=sentaince://earned-memory
SENTAINCE_CHATGPT_FETCH_MAX_CHARS=20000
```

`SENTAINCE_CHATGPT_BASE_URL` is used for citation URLs in `search`/`fetch` results. The default is a private `sentaince://` URL because the underlying memory is local and may not be web-addressable. Set it to a project-controlled HTTPS base if you publish a safe public index.

## Tool surface

ChatGPT-compatible data tools:

- `search(query)` returns `{ "results": [{ "id", "title", "url" }] }`.
- `fetch(id)` returns `{ "id", "title", "text", "url", "metadata" }`.

Native read-only SentAInce tools are also exposed:

- `recall_for_prompt(prompt, repo="", cls="")`
- `recall_procedural(task, repo="", cls="")`
- `recall_notes(query, repo="", cls="")`
- `memory_status(repo="")`
- `memory_diff(repo="", mode="diff")`
- `list_repos()`
- `resurrection_candidates(repo="", now="", limit=25)`

All tools are implemented as read-only calls. If a tool returns an abstain/no-memory response, treat that as evidence absence rather than an error.

## Tests

Run the ChatGPT adapter tests with the optional MCP extra installed:

```bash
python -m pip install -e .[dev,mcp]
python -m pytest tests/test_chatgpt_mcp.py -q
```

The adapter test seeds a converged colony, calls `search` and `fetch`, then byte-compares persisted memory files before and after retrieval. The expected invariant is unchanged memory.

## Security notes

Custom MCP servers can expose private project memory to a model client. Keep the server local by default, restrict tunnel access, and do not expose private vaults to a workspace unless every authorized user is allowed to read that memory.

Do not add write/action tools to this server without a separate claim-boundary review. The first ChatGPT integration is intentionally read-only.
