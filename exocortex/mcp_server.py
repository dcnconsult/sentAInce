"""Exocortex memory — a READ-ONLY MCP server (the retrieval entry point — the consume side).

Exposes the organism's *earned* memory (the consequence-sourced procedural colony + declarative wiki) as
MCP tools, so any MCP host — Claude **Desktop**, Claude **Code**, Cursor, Cline, … — can RETRIEVE it. One
server, both surfaces: this is the *consume* side. The Claude Code hooks remain the *earn + enforce* side
(somatic veto + τ deposit on `exit 0`), which MCP structurally cannot do (verified: an MCP server has no
interception authority and no per-tool exit-code callback).

READ-ONLY w.r.t. MEMORY — the load-bearing guarantee:
  * NEVER deposits τ, writes σ, mutates a colony/wiki/scar/config, or persists the cue classifier.
  * Retrieval over MCP therefore CANNOT create memory — which *preserves* ADR-001 (no popularity-via-
    retrieval). Desktop consumes; only a verified `exit 0` (Code side) earns.
  * It MAY (re)use the derived wiki digest cache (`wiki_cache.json`) — a cache, not memory.

NON-BLOCKING on large vaults — a large declarative vault (e.g. a research archive = 59k nodes) takes seconds–
minutes to digest on cold disk, which would exceed a host's tool-call timeout (Claude Desktop cancels at
240 s). So this PERSISTENT server digests each vault ONCE in a BACKGROUND thread and holds the graph in
memory; tool calls never block on a cold digest. `memory_status` never digests at all. Lexical only
(forces ``EXOCORTEX_EMBED=0``): no MiniLM, fast start.

Repo selection: ``EXOCORTEX_STATE_DIR`` = one repo; ``EXOCORTEX_PROJECTS_ROOT`` = scan a parent for many;
set both to include an out-of-root repo plus the fleet. Pass ``repo=<name>`` to the tools (see ``list_repos``).
Run (stdio). Requires the ``mcp`` SDK (`pip install mcp`).
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
from pathlib import Path

# self-bootstrap sys.path (like hook.py / runner.py) so `exocortex.*` imports when run by absolute path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# read-only server: force the lexical lane (no embedder → no MiniLM, no classifier .save())
os.environ["EXOCORTEX_EMBED"] = "0"

from mcp.server.fastmcp import FastMCP   # noqa: E402

mcp = FastMCP("exocortex-memory")
_LOCK = threading.RLock()          # REENTRANT: _enter holds it across a call body that re-acquires it
                                   # (via _ensure_warm); a plain Lock would self-deadlock. Serializes the
                                   # per-call EXOCORTEX_STATE_DIR scoping + the _GRAPHS map.
_GRAPHS: dict = {}                 # (vault, ingest) -> (signature, WikiGraph) — the persistent in-memory cache
_WARMING: set = set()             # keys with a background digest in flight (avoid duplicate warms)
_SEP = "\t"                        # colony τ edge-key separator (mirror of colony._SEP)


def _note_anchors(colony) -> list:
    """The DECLARATIVE note anchors a colony credits — node ids containing '.md', ranked by incident τ. These
    are the deliberately-recallable notes: ``memory_status`` counts them (``[notes:N]``) and ``recall_notes``
    (an explicit ``cls`` + empty ``query``) returns them directly, bypassing the lexical proposer. Procedural
    verb-nodes (``Read:src``, ``bash:pytest``) carry no '.md' → excluded. Read-only."""
    inc: dict = {}
    for k, w in (getattr(colony, "tau", None) or {}).items():
        for nid in k.split(_SEP):
            if ".md" in nid:
                inc[nid] = inc.get(nid, 0.0) + float(w)
    return sorted(inc.items(), key=lambda kv: -kv[1])


# ----------------------------------------------------------------- repo discovery + read-only scoping
def _repos() -> list:
    out: dict = {}
    sd = os.environ.get("EXOCORTEX_STATE_DIR")
    if sd:
        root = Path(sd).parent.parent
        out[root.name] = {"name": root.name, "state_dir": Path(sd), "root": root}
    proot = os.environ.get("EXOCORTEX_PROJECTS_ROOT")
    if proot and Path(proot).is_dir():
        for child in sorted(Path(proot).iterdir()):
            sdc = child / ".claude" / "exocortex"
            if sdc.is_dir():
                out.setdefault(child.name, {"name": child.name, "state_dir": sdc, "root": child})
    if not out:
        sdc = Path(_ROOT) / ".claude" / "exocortex"
        if sdc.is_dir():
            out[Path(_ROOT).name] = {"name": Path(_ROOT).name, "state_dir": sdc, "root": Path(_ROOT)}
    return list(out.values())


def _repo_decl(r: dict) -> tuple:
    decl = {}
    try:
        cp = r["root"] / "exocortex_config.json"
        if cp.is_file():
            decl = json.loads(cp.read_text(encoding="utf-8")).get("declarative", {}) or {}
    except Exception:
        decl = {}
    return (os.environ.get("EXOCORTEX_WIKI_VAULT") or decl.get("vault_path") or "",
            os.environ.get("EXOCORTEX_WIKI_INGEST") or decl.get("ingest") or "all")


def _resolve_repo(repo: str, repos: list):
    """Pick the repo dict for a caller-supplied name. Read-only (name resolution only). Tolerant, in
    priority order so a partial/case-off name still lands when it is UNambiguous: exact → case-insensitive
    exact → unique case-insensitive prefix → unique case-insensitive substring. Ambiguous or absent → None
    (the caller then returns `_ambiguous`, which lists the candidates). Empty name → the sole repo if there
    is exactly one. This fixes the papercut where e.g. `memory_status("acme")` hard-missed a repo actually
    named `Acme_Research`."""
    if not repo:
        return repos[0] if len(repos) == 1 else None
    exact = next((x for x in repos if x["name"] == repo), None)
    if exact:
        return exact
    low = repo.lower()
    ci = [x for x in repos if x["name"].lower() == low]
    if len(ci) == 1:
        return ci[0]
    pre = [x for x in repos if x["name"].lower().startswith(low)]
    if len(pre) == 1:
        return pre[0]
    sub = [x for x in repos if low in x["name"].lower()]
    if len(sub) == 1:
        return sub[0]
    return None


@contextlib.contextmanager
def _enter(repo: str):
    with _LOCK:
        repos = _repos()
        r = _resolve_repo(repo, repos)
        prev = os.environ.get("EXOCORTEX_STATE_DIR")
        if r is not None:
            os.environ["EXOCORTEX_STATE_DIR"] = str(r["state_dir"])
        try:
            yield r, repos
        finally:
            if prev is None:
                os.environ.pop("EXOCORTEX_STATE_DIR", None)
            else:
                os.environ["EXOCORTEX_STATE_DIR"] = prev


def _ambiguous(repo: str, repos: list) -> str:
    names = ", ".join(r["name"] for r in repos) or "(none)"
    return (f"(repo '{repo}' not found — available: {names})" if repo
            else f"(multiple repos have memory — pass repo= one of: {names}; or call list_repos)")


def _classify_readonly(prompt: str) -> str:
    """Route a query to its goal-class WITHOUT persisting (`classify()` mutates only in memory; we never
    `save()`, so `cues.json` is untouched). Fail-open to ``_default``."""
    try:
        from exocortex.cue_classifier import CueClassifier
        return CueClassifier.load().classify(prompt or "").get("label", "_default")
    except Exception:
        return "_default"


# ----------------------------------------------------------------- vault graph: digest-once, in-memory, non-blocking
def _digest_cached(vault: str, ingest: str, state_dir: Path):
    """Digest a vault to a WikiGraph (nodes only — no colony/scars, no global env), reusing the on-disk
    ``wiki_cache.json`` when its signature matches (the live hook keeps it warm). Cold misses re-digest and
    rewrite the cache. Returns (graph, signature). Heavy on a cold large vault → always called off-thread."""
    from exocortex.wiki import store
    from exocortex.wiki.node import WikiGraph
    p = Path(vault)
    files = store._md_files(p, ingest)
    sig = store._signature(p, files)
    nodes = None
    cache = Path(state_dir) / store._CACHE_NAME
    if cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("signature") == sig:
                nodes = [store._node_from_dict(nd) for nd in d.get("nodes", [])]
        except Exception:
            nodes = None
    if nodes is None:
        nodes = store._digest_vault(p, files)
        try:
            cache.write_text(json.dumps({"signature": sig, "nodes": [store._node_to_dict(n) for n in nodes]}),
                             encoding="utf-8")
        except Exception:
            pass
    g = WikiGraph()
    for n in nodes:
        g.add(n)
    return g, sig


def _warm(vault: str, ingest: str, state_dir: Path) -> None:
    key = (vault, ingest)
    try:
        g, sig = _digest_cached(vault, ingest, state_dir)
        with _LOCK:
            _GRAPHS[key] = (sig, g)
    except Exception:
        pass
    finally:
        with _LOCK:
            _WARMING.discard(key)


def _ensure_warm(vault: str, ingest: str, state_dir: Path):
    """Return the cached graph if present; else kick a BACKGROUND digest (once) and return None. Never blocks."""
    key = (vault, ingest)
    with _LOCK:
        cached = _GRAPHS.get(key)
        if cached:
            return cached[1]
        if key not in _WARMING:
            _WARMING.add(key)
            threading.Thread(target=_warm, args=(vault, ingest, state_dir), daemon=True).start()
    return None


def _warming_note(vault: str, ingest: str) -> str:
    """A progress-bearing 'warming' string for `memory_status`. Reads only the CHEAP file list
    (`store._md_files` = one `git ls-files` or an rglob + no body reads), so the busy state is attributable
    ('warming — digesting ~N .md files in the background') instead of an opaque black box. Read-only; never
    digests. Falls back to the plain note if the count can't be taken."""
    try:
        from exocortex.wiki import store
        n = len(store._md_files(Path(vault), ingest))
        return f"warming — digesting ~{n} .md files in the background; node count after digest"
    except Exception:
        return "warming — node count after digest"


def _prewarm_all() -> None:
    """At startup, kick a background digest of every configured repo's vault so the first recall is instant."""
    try:
        for r in _repos():
            vault, ingest = _repo_decl(r)
            if vault:
                _ensure_warm(vault, ingest, r["state_dir"])
    except Exception:
        pass


# ----------------------------------------------------------------- intent register: warm-once, non-blocking (D1)
_INTENTS: dict = {}            # (vault, now_iso) -> resurrection-gauge result dict (in-memory ONLY —
#                                the server stays read-only w.r.t. every store; persistence lives host-side
#                                with the cerebral S2 journal, not here)
_INTENTS_WARMING: set = set()  # keys with a background scan in flight


def _warm_intents(vault: str, now_iso: str) -> None:
    """Run the resurrection gauge OFF the request path. The gauge takes the vault path explicitly (no env,
    no _enter) so this thread never touches _LOCK during the scan — the D1 wedge was the maiden scan running
    synchronously INSIDE _enter(), blocking every other endpoint behind the RLock past the host's ~240 s
    tool budget. The scan itself is BOUNDED (D1b): the harvest filters to CHECKBOX_PATTERNS filenames
    BEFORE any git call (one bulk `git ls-files`, then at most one cached `git log -1` per *matched* file
    without a frontmatter date) — vault node count does not multiply subprocesses, so warming completes in
    seconds even on a ~350k-node vault."""
    key = (vault, now_iso)
    try:
        from cerebral.gauge.resurrection_gauge import run as _run
        res = _run(vault, now_iso)
        with _LOCK:
            _INTENTS[key] = res
    except Exception:
        pass
    finally:
        with _LOCK:
            _INTENTS_WARMING.discard(key)


def _ensure_intents_warm(vault: str, now_iso: str):
    """Return the cached intent-register scan if present; else kick ONE background scan and return None.
    Never blocks. Keyed (vault, now-date) so a new day re-scans; same-day calls are instant."""
    key = (vault, now_iso)
    with _LOCK:
        cached = _INTENTS.get(key)
        if cached is not None:
            return cached
        if key not in _INTENTS_WARMING:
            _INTENTS_WARMING.add(key)
            threading.Thread(target=_warm_intents, args=(vault, now_iso), daemon=True).start()
    return None


def _bounded(fn, timeout: float, *args):
    """Run ``fn(*args)`` with a hard wall-clock deadline; ``(False, None)`` on timeout. D1b (Desktop
    audit): two maiden `resurrection_candidates` replies parked ≥240 s on the post-fix build and exhausted
    the host's worker pool — wherever the park hides (lock, filesystem, import machinery), the reply path
    must RECYCLE ITS WORKER. On timeout the orphaned thread finishes (or dies) on its own; the reply
    returns a busy note instead of never returning."""
    box: dict = {}

    def _run():
        try:
            box["v"] = fn(*args)
        except Exception as e:
            box["e"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return False, None
    if "e" in box:
        raise box["e"]
    return True, box.get("v")


# ----------------------------------------------------------------- tools
def recall_procedural(task: str, repo: str = "", cls: str = "") -> str:
    """Recall the consequence-sourced PROCEDURAL memory — the converged tool-use route this project follows
    for a task like `task`. τ was earned ONLY by a verified `exit 0` chain, never by retrieval. Read-only;
    fast. `repo`: which repo (omit if only one). `cls`: target an EXACT goal-class from `memory_status`
    (bypasses the semantic classifier — use it to address a known route deterministically)."""
    try:
        with _enter(repo) as (r, repos):
            if r is None:
                return _ambiguous(repo, repos)
            from exocortex.colony import Colony
            label = cls or _classify_readonly(task)
            payload = Colony.load(label).splice()
            return payload or (f"(no converged procedural memory in [{r['name']}] for task class [{label}] "
                               f"— the colony abstains until a route repeats to exit 0)")
    except Exception as e:
        return f"(recall_procedural unavailable: {type(e).__name__})"


def recall_notes(query: str, repo: str = "", cls: str = "") -> str:
    """Recall the consequence-sourced DECLARATIVE memory — notes the work actually USED to reach `exit 0`
    (τ-verified only; surfaces a note only when `query` lexically matches a note that EARNED τ in the
    matched class — so it abstains often, by design). Read-only; querying never earns τ. A large vault is
    digested ONCE in the background: if still warming this returns a 'warming' note. `repo`: which repo.
    `cls`: target an EXACT goal-class from `memory_status` (classes marked `[notes:N]` carry N credited notes).
    **Pass `cls` with an EMPTY `query` to get that class's τ-credited notes DIRECTLY** — the reliable positive
    path (no lexical guessing); a non-empty `query` lexically matches within the targeted class instead."""
    try:
        with _enter(repo) as (r, repos):
            if r is None:
                return _ambiguous(repo, repos)
            vault, ingest = _repo_decl(r)
            if not vault:
                return f"(repo [{r['name']}] has no declarative vault configured)"
            graph = _ensure_warm(vault, ingest, r["state_dir"])   # in-memory; non-blocking
            if graph is None:
                return (f"(declarative memory for [{r['name']}] is warming in the background — a large vault "
                        f"digests once; ask again in a few seconds)")
            if not graph.nodes:
                return "(declarative vault empty or unreadable)"
            from exocortex.colony import Colony
            from exocortex.wiki.propose import propose
            from exocortex.wiki.splice import splice_payload
            from exocortex.wiki.store import _load_scars
            graph.colony = Colony.load(cls or _classify_readonly(query))   # label-specific τ lane (cheap)
            graph.scars = _load_scars()
            if cls and not query.strip():
                # DELIBERATE recall: an explicit class + empty query → return that class's τ-credited notes
                # DIRECTLY, bypassing the lexical proposer (which needs a query that happens to match a credited
                # note). The reliable positive path: memory_status flags [notes:N] classes; this returns those N.
                # Still consequence-pure — reads only earned τ, renders only credited notes (no exploration).
                cands = [nid for nid, _ in _note_anchors(graph.colony)]
            else:
                cands = propose(graph, prompt=query, active_context=[])
            text = splice_payload(graph, cands, explore=0)          # τ-verified only; NO exploration
            return text or ("(no τ-verified notes matched — declarative memory abstains until notes are "
                            "credited by exit 0)")
    except Exception as e:
        return f"(recall_notes unavailable: {type(e).__name__})"


def _credited_notes_hint(prompt: str, repo: str) -> str:
    """D6 support: when the lexical notes-query misses, say whether the prompt's CLASS actually carries
    credited notes (and how to get them) instead of silent omission. Fail-open → empty."""
    try:
        with _enter(repo) as (r, _repos_):
            if r is None:
                return ""
            from exocortex.colony import Colony
            label = _classify_readonly(prompt)
            n = len(_note_anchors(Colony.load(label)))
            if n:
                return (f"(note: class [{label}] carries {n} τ-credited note(s) the lexical query missed — "
                        f"call recall_notes(cls=\"{label}\", query=\"\") or recall_for_prompt(..., "
                        f"cls=\"{label}\") to retrieve them directly)")
            return ""
    except Exception:
        return ""


def recall_for_prompt(prompt: str, repo: str = "", cls: str = "") -> str:
    """One-call recall for an agent at the START of a task — the converged consequence-sourced PROCEDURAL
    route PLUS any τ-verified DECLARATIVE notes for `prompt`. A convenience wrapper over `recall_procedural`
    + `recall_notes` (a model that calls one tool still gets both — designed for Cursor/`.cursor/rules`
    bootstraps). Read-only; retrieval NEVER earns τ (ADR-001 preserved). `repo`: which repo (omit if one).
    `cls`: target an EXACT goal-class from `memory_status` — the deterministic bootstrap path: the class's
    route AND its τ-credited notes are returned DIRECTLY (no semantic classify, no lexical guessing)."""
    try:
        proc = recall_procedural(task=prompt, repo=repo, cls=cls)
        # with an explicit class, empty query = the deliberate direct path (that class's credited notes);
        # without one, the prompt is a legitimate lexical query (the original behavior)
        notes = recall_notes(query="" if cls else prompt, repo=repo, cls=cls)
        parts = [p for p in (proc, notes) if p and not p.lstrip().startswith("(")]   # drop abstain/notices
        if not parts:
            return ("(no earned memory for this task yet — proceed; the colony learns from your verified "
                    "successes)")
        out = "\n\n".join(parts)
        if not cls and notes.lstrip().startswith("("):        # D6: notes abstained — surface, don't omit
            hint = _credited_notes_hint(prompt, repo)
            if hint:
                out += "\n\n" + hint
        return out
    except Exception as e:
        return f"(recall_for_prompt unavailable: {type(e).__name__})"


def memory_status(repo: str = "") -> str:
    """Read-only vitals of a repo's EARNED memory: procedural goal-classes (deposits + converged route) and
    the declarative vault. NEVER digests (so it can't block on a large vault) — node count shows once the
    vault has warmed. `repo`: which repo (omit if only one)."""
    try:
        with _enter(repo) as (r, repos):
            if r is None:
                return _ambiguous(repo, repos)
            from exocortex.colony import Colony
            cols = Colony.all()
            lines = [f"Exocortex earned memory — repo [{r['name']}] @ {r['state_dir']}",
                     f"procedural goal-classes: {len(cols)}"]
            for c in sorted(cols, key=lambda c: -c.deposits)[:10]:
                chain = c.dominant_path()
                route = " → ".join(chain) if len(chain) >= 2 else "(unconverged)"
                n_notes = len(_note_anchors(c))               # τ-credited declarative notes → recall_notes(cls=…, "")
                notes = f" [notes:{n_notes}]" if n_notes else ""
                lines.append(f"  · {c.label}{notes}: {c.deposits} deposits, {len(c.tau)} edges — {route}")
            vault, ingest = _repo_decl(r)
            if not vault:
                lines.append("declarative vault: (not configured)")
            else:
                cached = _GRAPHS.get((vault, ingest))
                if cached:
                    lines.append(f"declarative vault: {vault} ({len(cached[1].nodes)} nodes, ingest={ingest})")
                else:
                    _ensure_warm(vault, ingest, r["state_dir"])   # kick warm for next time; don't block
                    lines.append(f"declarative vault: {vault} (ingest={ingest}; {_warming_note(vault, ingest)})")
            return "\n".join(lines)
    except Exception as e:
        return f"(memory_status unavailable: {type(e).__name__})"


def list_repos() -> str:
    """List every repo with earned Exocortex memory this server can reach, with its procedural goal-class
    count and declarative vault. Use a returned name as the `repo` argument of the recall tools."""
    try:
        with _LOCK:
            repos = _repos()
        if not repos:
            return "(no repos with earned memory — set EXOCORTEX_STATE_DIR or EXOCORTEX_PROJECTS_ROOT)"
        lines = ["Repos with earned Exocortex memory:"]
        for r in repos:
            n = len(list(r["state_dir"].glob("colony_*.json")))
            vault, ingest = _repo_decl(r)
            decl = f"; declarative vault={Path(vault).name} (ingest={ingest})" if vault else "; no vault"
            lines.append(f"  · {r['name']}: {n} procedural goal-classes{decl}")
        return "\n".join(lines)
    except Exception as e:
        return f"(list_repos unavailable: {type(e).__name__})"


def resurrection_candidates(repo: str = "", now: str = "", limit: int = 25) -> str:
    """Cerebral Substrate (Governor) — the stale OPEN research intents ("crack-fallers") in this repo's
    declarative vault: work-items that opened, never closed, and went silent past a reasonable timeframe.
    Ranked by days-silent, with dormant-paper clusters called out separately (a whole paper gone quiet →
    consider closing the cluster, not resuming each). READ-ONLY: harvests DECLARED intents only (Markdown
    checkboxes + structured `ledger.json`), never inferred from prose; it surfaces, you resume/close.
    `repo`: which repo (omit if only one). `now`: reference date ISO (defaults today). `limit`: top-N.
    A large vault is scanned ONCE in the background: if still warming this returns a 'warming' note (the
    same non-blocking contract as `recall_notes` — a maiden call never hangs the server). The whole reply
    path runs under a hard watchdog (D1b): whatever blocks, the worker recycles and you get a busy note —
    this tool can no longer park a reply."""
    try:
        # D1b warming-first: EVERYTHING vault-dependent (repo resolve, config read, cache probe, the
        # formatter import) runs inside the watchdog; the warming/busy note needs none of it to return.
        def _resolve_and_probe():
            with _enter(repo) as (r, repos):      # brief: resolve repo + vault only (config reads)
                if r is None:
                    return ("ambiguous", _ambiguous(repo, repos))
                vault, _ = _repo_decl(r)
                name = r["name"]
            if not vault:
                return ("novault", f"(repo [{name}] has no declarative vault configured — resurrection "
                                   f"needs a vault; set declarative.vault_path or EXOCORTEX_WIKI_VAULT)")
            from datetime import date
            now_iso = now or date.today().isoformat()
            res = _ensure_intents_warm(vault, now_iso)   # non-blocking; scan runs OFF the lock (D1)
            if res is None:
                return ("warming", f"(intent register for [{name}] is warming in the background — a "
                                   f"large vault scans once per day; ask again in a minute)")
            from cerebral.gauge.resurrection_gauge import format_candidates
            return ("ok", format_candidates(res, top=int(limit)))

        done, out = _bounded(_resolve_and_probe, 8.0)
        if not done or out is None:
            return ("(the Governor's reply path is busy — the intent register may be warming; the reply "
                    "worker was recycled rather than parked (D1b watchdog). Ask again in a minute)")
        return out[1]
    except Exception as e:
        return f"(resurrection_candidates unavailable: {type(e).__name__})"


# ----------------------------------------------------------------- memory_diff: lock a baseline, see what changed
_MEM_BASELINES: dict = {}   # repo-name -> snapshot dict. IN-MEMORY ONLY (read-only w.r.t. every store).


def _snapshot_colonies() -> dict:
    """A compact, comparable snapshot of the CURRENT colony state for the entered repo: per goal-class
    {edges, deposits, consolidations, tau_max, notes}. Built from `Colony.all()` (reads `colony_*.json`
    only) — no write, no digest. `_enter` must already be active so the state dir is scoped."""
    from exocortex.colony import Colony
    snap = {}
    for c in Colony.all():
        snap[c.label] = {
            "edges": len(c.tau),
            "deposits": int(c.deposits),
            "consolidations": int(getattr(c, "consolidations", 0)),
            "tau_max": round(max(c.tau.values()), 4) if c.tau else 0.0,
            "notes": len(_note_anchors(c)),
        }
    return snap


def _diff_snapshots(base: dict, cur: dict) -> list:
    """Pure function → a human-readable delta list between two `_snapshot_colonies` dicts. Mirrors the
    shape of `cerebral.journal.diff`: NEW / GONE classes, and per surviving class the non-zero deltas in
    deposits / edges / notes / consolidations. Read-only (operates on dicts)."""
    out = []
    for label in sorted(set(cur) - set(base)):
        d = cur[label]
        out.append(f"NEW class {label}: {d['deposits']} deposits, {d['edges']} edges, {d['notes']} notes")
    for label in sorted(set(base) - set(cur)):
        out.append(f"GONE class {label} (was {base[label]['deposits']} deposits)")
    for label in sorted(set(base) & set(cur)):
        b, c = base[label], cur[label]
        parts = []
        for k in ("deposits", "edges", "notes", "consolidations"):
            if c[k] != b[k]:
                parts.append(f"{k} {b[k]}→{c[k]} ({c[k]-b[k]:+d})")
        if c["tau_max"] != b["tau_max"]:
            parts.append(f"tau_max {b['tau_max']}→{c['tau_max']}")
        if parts:
            out.append(f"{label}: " + ", ".join(parts))
    return out


def memory_diff(repo: str = "", mode: str = "diff") -> str:
    """Audit primitive — lock a baseline of a repo's EARNED memory, then see exactly what changed since.
    READ-ONLY (snapshots `colony_*.json`; never writes a store, never digests). Two modes:
    `mode="snapshot"` locks the current per-class state (deposits/edges/notes/consolidations/tau_max) as the
    in-memory baseline; `mode="diff"` (default) reports the delta vs the locked baseline (auto-locking one on
    the first call). Replaces the manual 'lock baseline → re-read → diff by hand' audit protocol.
    `repo`: which repo (omit if only one; case/prefix-tolerant)."""
    try:
        with _enter(repo) as (r, repos):
            if r is None:
                return _ambiguous(repo, repos)
            name = r["name"]
            cur = _snapshot_colonies()
        with _LOCK:
            base = _MEM_BASELINES.get(name)
            if mode == "snapshot" or base is None:
                _MEM_BASELINES[name] = cur
                total = sum(v["deposits"] for v in cur.values())
                lead = "baseline locked" if mode == "snapshot" else "no baseline yet — locked one now"
                return (f"[{name}] {lead}: {len(cur)} classes, {total} total deposits. "
                        f"Do some work, then call memory_diff(repo=\"{name}\") to see the delta.")
        deltas = _diff_snapshots(base, cur)
        if not deltas:
            return f"[{name}] no change since the baseline ({len(cur)} classes)."
        return f"[{name}] changes since baseline:\n" + "\n".join(f"  · {d}" for d in deltas)
    except Exception as e:
        return f"(memory_diff unavailable: {type(e).__name__})"


# register as MCP tools while keeping the functions directly callable (for tests / reuse)
for _fn in (recall_procedural, recall_notes, recall_for_prompt, memory_status, memory_diff, list_repos,
            resurrection_candidates):
    mcp.tool()(_fn)


def main() -> None:
    threading.Thread(target=_prewarm_all, daemon=True).start()   # digest vaults off the request path
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
