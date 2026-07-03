# Read-only memory MCP server (the retrieval entry point — consume side)

> Naming note: earlier drafts called this the "T2 entry point"; that collided with
> [DEPLOYMENT.md](DEPLOYMENT.md)'s packaging tier T2 (the Nuitka binary). Entry points
> (hooks = earn/enforce · MCP = retrieve) are ORTHOGONAL to packaging tiers.

`exocortex/mcp_server.py` exposes the organism's **earned memory** — the consequence-sourced procedural
colony + the declarative wiki — as MCP tools, so any MCP host (**Claude Desktop, Claude Code, Cursor,
Cline, …**) can RETRIEVE it. One server, every surface: this is the *consume* side.

It is the answer to "can the organism integrate with any host?" — **memory, yes; the hard somatic veto, only
where there are hooks.** An MCP server has no interception authority or per-tool exit-code callback (verified
against the docs), so the *earn + enforce* half (somatic veto + τ-on-`exit 0`) needs **hooks** — live today on
**Claude Code and Cursor** (see [DEPLOY_TO_A_PROJECT.md](DEPLOY_TO_A_PROJECT.md)); a hookless host like Claude
Desktop gets **recall only**. This server is the read side that *all* surfaces share.

## Tools
The recall tools take an optional `repo` (see *Single vs multi-repo*) and an optional `cls` (an exact
goal-class from `memory_status`). The `task`/`query` → goal-class step is a **semantic classifier**, so a
free-text probe routes opaquely; pass `cls=` to address a known class **deterministically** (it's the
reliable way to hit a positive return).

> **Brief your agent:** `python -m exocortex.deploy install` now writes an *agent bootstrap contract*
> (AGENTS.md block / `.cursor/rules`) encoding the reliable calling pattern — `memory_status` at task
> start, `recall_for_prompt(prompt, cls=…)` on known classes, and *recall is earned suggestion, never
> authority*. See the "Bootstrap your agent" section of
> [`DEPLOY_TO_A_PROJECT.md`](DEPLOY_TO_A_PROJECT.md).

| Tool | Returns |
|---|---|
| `recall_procedural(task, repo="", cls="")` | The converged tool-use route for that class — τ earned only by verified `exit 0`. Abstains until a route repeats. |
| `recall_notes(query, repo="", cls="")` | τ-verified declarative notes the work actually USED to reach `exit 0`. Surfaces a note only when `query` lexically matches one that earned τ in the class — so it abstains often, by design. Use `cls=` a `[notes]`-marked class for a reliable hit. |
| `memory_status(repo="")` | Read-only vitals: goal-classes (deposits, converged route, `[notes]` = carries declarative credit), vault size. |
| `list_repos()` | Every repo this server can reach, with its goal-class count + declarative vault — names to use as `repo`. |
| `resurrection_candidates(repo="", now="", limit=25)` | **Cerebral Substrate (Governor).** Stale OPEN research intents ("crack-fallers") in the repo's declarative vault — *declared* items (checkboxes + `ledger.json`) that opened, never closed, and went silent past a reasonable timeframe; ranked by days-silent, with dormant-paper clusters called out separately. Read-only: it surfaces, you resume/close. Composes the Cerebral S0 resurrection gauge into the shared read side; needs a declarative vault; declared-intents-only (recall is a floor). |

## The load-bearing guarantee — read-only w.r.t. memory
Retrieval over MCP **creates no memory**: the server never deposits τ, writes σ, mutates a colony/wiki/scar/
config, or persists the cue classifier. This *preserves* ADR-001 (a memory is earned only by `exit 0`, never
by retrieval) — popularity-via-retrieval is structurally impossible here. (It may write the derived
`wiki_cache.json` digest — a cache, not memory — reusing the Code side's cache when present.) Lexical only
(`EXOCORTEX_EMBED=0`): no MiniLM, fast start, minimal deps.

## Single vs multi-repo
- **Single repo:** set `EXOCORTEX_STATE_DIR=<repo>/.claude/exocortex` (+ optional `EXOCORTEX_WIKI_VAULT` /
  `EXOCORTEX_WIKI_INGEST`). The recall tools need no `repo`.
- **Multi-repo (fleet):** set `EXOCORTEX_PROJECTS_ROOT=<parent>` — every `<parent>/*/.claude/exocortex` is
  discovered, each repo's vault read from its own `exocortex_config.json`. Pass `repo=<name>` to the tools
  (or call `list_repos`); with several repos and no `repo`, the tool lists the choices.
- **Both at once** (e.g. include an out-of-root research vault *and* the rest): set BOTH —
  `EXOCORTEX_STATE_DIR=<vault>/.claude/exocortex` adds the vault, `EXOCORTEX_PROJECTS_ROOT=<dev-root>` adds
  the fleet.

**Where the memory lives:** procedural memory accrues where Bash-`exit 0` work happens — SentAInce is rich
(45 goal-classes); a research/writing vault is *procedurally* sparse (0) but its **declarative** memory
fills as its wiki soak runs. So for a procedural demo, recall `repo="SentAInce"`.

## Large vaults are non-blocking
A big declarative vault (≈ 59k nodes) takes seconds–minutes to digest on cold disk — longer
than a host's tool timeout (Claude Desktop cancels at **240 s**). So the persistent server digests each vault
**once, in a background thread** at startup and holds the graph in memory; **no tool call ever blocks on a
cold digest**. `memory_status` never digests (node count appears once warm); `recall_notes` returns a
"warming" note until the digest finishes (a few seconds), then serves instantly. Restart the server to
re-digest after large vault changes.

## Wire it into Claude Desktop
`claude_desktop_config.json` (Settings → Developer → Edit Config):
```json
{
  "mcpServers": {
    "exocortex-memory": {
      "command": "python",
      "args": ["~/projects/SentAInce/exocortex/mcp_server.py"],
      "env": {
        "EXOCORTEX_PROJECTS_ROOT": "~/projects",
        "EXOCORTEX_STATE_DIR": "~/research-vault/.claude/exocortex"
      }
    }
  }
}
```
(Use absolute paths on your machine.) This reaches the whole fleet — SentAInce (procedural-rich), the
research vault (declarative), and the rest. Restart
Desktop; the tools appear. Ask Claude to `list_repos`, then `recall_procedural(task, repo="SentAInce")`.
(Requires `mcp` in that python env: `pip install mcp`.) For one repo only, use a single `EXOCORTEX_STATE_DIR`
(+ `EXOCORTEX_WIKI_VAULT`) and omit `repo`.

## Wire it into Claude Code
```bash
claude mcp add exocortex-memory \
  --env EXOCORTEX_STATE_DIR=~/projects/SentAInce/.claude/exocortex \
  --env EXOCORTEX_WIKI_VAULT=~/projects/SentAInce \
  --env EXOCORTEX_WIKI_INGEST=tracked \
  -- python ~/projects/SentAInce/exocortex/mcp_server.py
```
On Code the hooks already inject this memory automatically; the MCP tools add *on-demand* recall (and let a
BYO/non-hook agent reach the same store).

## Scope / not yet
Read-only, lexical, stdio, single- **and** multi-repo (`list_repos` + the `repo` arg). Later: embedding
recall (semantic paraphrase matching, opt-in to stay light), a `.mcpb` Desktop Extension bundle (one-click
install), and (separately) the MCP **gateway/proxy** pattern if a partial Desktop gate is ever wanted.
