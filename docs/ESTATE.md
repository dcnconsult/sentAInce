# The estate file — file-based multi-repo management

> One file names every repo the observability stack watches. It is the **source of truth**;
> the exporter's web form (`:9109/control`) is just an editor for it.

## Location and precedence

- Default: `~/.exocortex/repos.json` — used automatically by the exporter when present.
- Override: `sentaince-exporter --registry <file>`.
- Repos **inside** a `--scan-root` need no entry at all (auto-discovered by their deployed
  `.claude/exocortex/`). Estate entries are for repos *outside* the scan roots, or to pin a
  custom name. On a name collision the estate entry wins.

## The contract (version 1)

```json
{
  "version": 1,
  "repos": [
    { "name": "my-repo", "root": "C:/work/my-repo" },
    { "name": "research", "root": "D:/vaults/research", "tags": ["writing"], "display": "Research vault" }
  ]
}
```

- `version` — contract version, currently `1`. Bumped only for a breaking change (none
  planned; the contract evolves **additively**).
- `repos[].name` — stable identifier (defaults to the folder name). `root` — the repo's
  filesystem root. `tags`, `display` — optional, reserved for grouping and prettier labels.
- A bare JSON **list** of entries is the accepted legacy form.

**The two reader rules (binding for every consumer):**

1. **Ignore unknown keys** — top-level and per-entry. The estate file is a shared contract
   that downstream tools may extend with their own keys; an unknown key is never an error.
2. **Preserve unknown keys on write** — any tool that edits the file must round-trip keys it
   doesn't understand verbatim (the exporter's web editor does).

## Web editing

`GET /api/estate` returns the file as JSON; `POST /api/estate` with
`{"action": "add"|"remove", "entry": {...}}` edits it. Writes sit behind the same guards as
every other exporter write: refused entirely under `--read-only`, JSON-content-type +
loopback-origin CSRF checks, optional `--token`. The editor only ever writes the documented
entry keys and never touches keys it doesn't know.

Deploying an organism into a repo is **not** an estate operation and is never done from the
web — it stays a deliberate CLI act: `python -m exocortex.deploy install <path>`.
