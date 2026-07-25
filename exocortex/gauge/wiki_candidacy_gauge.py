"""Wiki-Candidacy Gauge — WHICH repos could the declarative organ (and the bridge) actually earn keep in?

The splice-composition gauge found a contention ceiling of ≥2 in only 3/17 estate repos: everywhere else
the wiki and bridge ship dormant, so the colony injects a monologue. The obvious next move is "flip them
on elsewhere". This gauge decides whether that would produce memory or clutter, BEFORE anything is
switched on — a repo whose vault cannot be credited is a repo where the organ injects forever and earns
nothing (the Desktop longitudinal −1: a 59k-node warmed vault, 60+ exit-0 deposits, zero credited notes).

Three independent gates, each of which alone is disqualifying:

  VAULT        Does the repo have Markdown to digest at all? Counted through the organ's own
               ``store._md_files`` under BOTH inclusion boundaries (``all`` vs ``tracked``) — the gap is
               untracked/vendored noise the organ would otherwise ingest.
  CREDITABLE   Of the digested nodes, what fraction carry ≥ ``min_overlap`` salient tokens? Scored with
               ``attribute.salient_tokens`` VERBATIM — the ADR-006 asymmetry (code/path/identifier
               tokens count, prose contributes nothing). A prose-only vault is *structurally*
               uncreditable: it can be spliced forever and never earn τ.
  REACHABLE    Cold-start liveness. Structural spreading needs a prior credit; muscle-memory needs
               note-anchored τ; the dense lift is statically dormant (the hook never passes
               ``prompt_embedding``) — so **lexical reflex is the only layer that can fire cold**, and it
               fires only when a prompt token hits a doc-name/heading token. Measured against the repo's
               REAL prompt history: the cue-classifier's ``cues.json`` ``df`` (token → #prompts).

``df`` is stored STEMMED, so the vault surface is mapped into the same space with
``cue_classifier._featurize`` (verbatim). Stemming merges variants, so the reported reach is a mildly
OPTIMISTIC proxy for the raw-token overlap ``propose._lexical`` actually computes — which is the point:
a null under an optimistic proxy is a strong null.

Reach is reported as BOUNDS, never a point estimate. From per-token document frequencies alone the
union over tokens is not recoverable: the lower bound is the single best token's coverage, the upper
bound is the (capped) sum. The truth is somewhere between and this gauge does not pretend otherwise.

BRIDGE is strictly downstream: ``bridge_enabled`` requires ``declarative.mode == live``, and synthesis
needs a phasor bank (numpy/FreqOS at sleep). It is reported per repo but no repo can qualify before its
wiki does.

Read-only — digests in memory, writes no cache, never touches a target repo. Fail-open.

Denominators differ by design and are not interchangeable: the contention census above counts **17**
estate repos, this gauge's candidacy sweep counts **16**. A repo already running the organ live is not a
candidate for flipping it on, so it is surveyed for contention and excluded from candidacy.

  python -m exocortex.gauge.wiki_candidacy_gauge --repo <repo>
  python -m exocortex.gauge.wiki_candidacy_gauge --estate <projects-root>
  python -m exocortex.gauge.wiki_candidacy_gauge --estate <projects-root> --json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_MIN_OVERLAP = 2         # genome declarative.attribution.min_overlap
CREDITABLE_FLOOR = 0.30         # below this the vault is called structurally uncreditable
MIN_PROMPTS_FOR_REACH = 20      # below this, a reach RATE is noise (n=1 → "100% of prompts")
# Hot-path ceiling. Every fresh-process hook re-parses the FULL node cache and rebuilds every node, so
# cost is O(total nodes) regardless of how many notes the turn needs — the T5 re-measurement (2026-06-29):
# SentAInce 506n/40ms · COMMONS 2,038n/54ms · TAO Research 59,573n/275ms · whole TAO tracked 187,681n/3.6s.
# Above the ceiling a flip is gated on a persistent/indexed store (the MCP graduation), not on candidacy.
NODES_HOT_PATH_CEILING = 10000
MAX_FILES = 4000                # cost cap; truncation is DISCLOSED, never silent


def _json_file(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


# ------------------------------------------------------------------ vault census (organ functions, verbatim)
def vault_census(root: Path, min_overlap: int, max_files: int = MAX_FILES) -> dict:
    from exocortex.wiki.attribute import salient_tokens
    from exocortex.wiki.digest import digest_document
    from exocortex.wiki.propose import _tokens as lex_tokens
    from exocortex.wiki.store import _md_files

    try:
        files_all = _md_files(root, "all")
        files_tracked = _md_files(root, "tracked")
    except Exception:
        return {"error": "vault scan failed", "nodes": 0}
    # Census under ``tracked`` (the sane boundary) but keep BOTH counts: the genome default is
    # ``ingest: "all"``, so a naive flip would digest every rglob'd *.md — vendored/node_modules noise
    # included. The ratio is a first-class output, not a footnote.
    files = files_tracked if files_tracked else files_all
    truncated = max(0, len(files) - max_files)
    files = files[:max_files]
    bloat = (round(len(files_all) / len(files_tracked), 1)
             if files_tracked and len(files_all) > len(files_tracked) else 1.0)

    nodes = credit = 0
    surface: set = set()
    for p in files:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            doc_id = str(p.relative_to(root)).replace("\\", "/")
        except Exception:
            continue
        try:
            exons = digest_document(doc_id, raw)
        except Exception:
            continue
        surface |= lex_tokens(doc_id)
        for n in exons:
            nodes += 1
            if len(salient_tokens(getattr(n, "text", "") or "")) >= min_overlap:
                credit += 1
            for h in (getattr(n, "heading_path", ()) or ()):
                surface |= lex_tokens(str(h))
    return {"files_all": len(files_all), "files_tracked": len(files_tracked),
            "files_scanned": len(files), "files_truncated": truncated, "default_ingest_bloat": bloat,
            "ingest_used": "tracked" if files_tracked else "all (not a git repo / no tracked md)",
            "nodes": nodes, "creditable": credit,
            "creditable_frac": (round(credit / nodes, 4) if nodes else 0.0),
            "surface_tokens": len(surface), "_surface": surface}


# ------------------------------------------------------------------ cold-start reach (real prompt history)
def reach(surface: set, state_dir: Path) -> dict:
    """Would the lexical reflex — the ONLY cold-start proposer — ever fire in this repo? Intersect the
    vault's doc/heading surface with the prompt-token document frequencies the cue classifier already
    recorded. Bounds only: ``df`` cannot reconstruct the per-prompt union."""
    from exocortex.cue_classifier import _featurize

    # Two possible records, and the richer one wins — a repo that later switched classifiers leaves a
    # STALE cues.json behind (Clifford_Bridge: n=1 lexical vs 30 semantic classes), and preferring it by
    # mere presence turns one prompt into a "100% of prompts" claim.
    cues = _json_file(Path(state_dir) / "cues.json")
    df_lex = {str(k): int(v) for k, v in dict(cues.get("df", {}) or {}).items()}
    n_lex = int(cues.get("n", 0) or 0)

    # The genome default classifier is SEMANTIC (embed_cues.json: dense centroids, no token surface), so a
    # missing/thin cues.json is not a missing history. Fall back to the class LABELS — slugs the classifier
    # built from distinctive prompt tokens — weighted by each class's prompt count. Thin (a few tokens per
    # class, not the full vocabulary): it can support a CANDIDATE finding but never a "never fires" one.
    df_lab: dict = {}
    n_lab = 0
    for c in (_json_file(Path(state_dir) / "embed_cues.json").get("classes", []) or []):
        size = max(1, int(c.get("size", 1) or 1))
        for tok in _featurize(str(c.get("label", "")).split("#", 1)[0].replace("-", " ")):
            df_lab[tok] = df_lab.get(tok, 0) + size
        n_lab += size

    if n_lex and n_lex >= n_lab:
        df, n, source, thin = df_lex, n_lex, "cues.json df (full prompt vocabulary)", False
    elif n_lab:
        df, n, source, thin = df_lab, n_lab, "embed_cues.json class labels (THIN proxy — slugs only)", True
    else:
        return {"prompts": 0, "prompt_vocab": 0, "known": False, "thin": False,
                "note": "no recorded prompt history (neither cues.json nor embed_cues.json) — "
                        "reach UNKNOWN, not zero"}
    stemmed: set = set()
    for t in surface:
        stemmed |= set(_featurize(t).keys())     # same space as df (verbatim classifier tokenizer)
    hit = {t: int(df[t]) for t in (stemmed & set(df))}
    lo = max(hit.values()) if hit else 0
    hi = min(n, sum(hit.values()))
    top = sorted(hit.items(), key=lambda kv: -kv[1])[:8]
    return {"prompts": n, "prompt_vocab": len(df), "known": True, "thin": thin, "source": source,
            "surface_stemmed": len(stemmed), "hit_tokens": len(hit),
            "reach_lower": round(lo / n, 4), "reach_upper": round(hi / n, 4),
            "top_hits": top}


# ------------------------------------------------------------------ bridge (strictly downstream)
def bridge_readiness(nodes: int) -> dict:
    import importlib.util
    try:
        deps = importlib.util.find_spec("numpy") is not None
    except Exception:
        deps = False
    return {"numpy": deps, "nodes": nodes,
            "gated_by": "declarative.mode must be 'live' first (config.bridge_enabled)",
            "note": ("synthesis needs a phasor bank built at PreCompact; the organ is BUILT-but-DORMANT "
                     "pending a fatter semantic tail — it cannot be evaluated in a repo whose wiki has "
                     "never run")}


# ------------------------------------------------------------------ verdict (pre-registered)
def verdict(cfg_live: bool, v: dict, r: dict, min_overlap: int) -> dict:
    if cfg_live:
        # Already-live is NOT a pass. The hot-path ceiling still applies — the largest estate vault runs live at
        # 194,502 nodes / 118.5 MB, ~19× over, and returning early here would wave exactly that through.
        if v.get("nodes", 0) > NODES_HOT_PATH_CEILING:
            return {"flip": None, "label": "LIVE BUT OVER THE HOT-PATH CEILING",
                    "note": f"live with {v['nodes']} nodes — {v['nodes'] // NODES_HOT_PATH_CEILING}× the "
                            f"{NODES_HOT_PATH_CEILING}-node ceiling. Every fresh-process hook re-parses the "
                            "whole cache, so this is a per-turn tax on an already-running repo. Narrow "
                            "vault_path to a subtree, or wait for the persistent/indexed store."}
        return {"flip": None, "label": "ALREADY LIVE", "note": "declarative organ is already switched on"}
    if not v.get("nodes"):
        return {"flip": False, "label": "NO VAULT",
                "note": f"{v.get('files_all', 0)} md files, {v.get('nodes', 0)} digestible nodes — nothing to splice"}
    if v["nodes"] > NODES_HOT_PATH_CEILING:
        return {"flip": False, "label": "TOO HEAVY FOR THE HOT PATH",
                "note": f"{v['nodes']} nodes — every fresh-process hook re-parses the whole cache "
                        f"(O(total nodes)), so this exceeds the {NODES_HOT_PATH_CEILING}-node working "
                        "ceiling (measured: 59.5k → 275ms, 187k → 3.6s per hook). Gated on a persistent/"
                        "indexed store (MCP graduation), not on candidacy. A subtree vault_path is the "
                        "cheap workaround."}
    if v["creditable_frac"] < CREDITABLE_FLOOR:
        return {"flip": False, "label": "STRUCTURALLY UNCREDITABLE",
                "note": f"only {v['creditable_frac']:.0%} of {v['nodes']} nodes carry ≥{min_overlap} salient "
                        "tokens — a prose vault can be injected forever and never earn τ (ADR-006 asymmetry). "
                        "Flipping this on adds context cost with no path to credit."}
    if not r.get("known"):
        return {"flip": False, "label": "NO PROMPT HISTORY",
                "note": "vault is creditable but the repo has no recorded prompts — cold-start reach is "
                        "unknown; flipping blind is the Desktop −1 repeated"}
    if r["prompts"] < MIN_PROMPTS_FOR_REACH:
        return {"flip": None, "label": "UNDERPOWERED",
                "note": f"vault is creditable ({v['creditable_frac']:.0%}) but only {r['prompts']} prompt(s) "
                        f"are on record — under {MIN_PROMPTS_FOR_REACH} a reach RATE is noise, not an "
                        "estimate. Use the repo, then re-run; do not flip on a single-digit sample."}
    if r["hit_tokens"] == 0 and r.get("thin"):
        return {"flip": None, "label": "INCONCLUSIVE (THIN RECORD)",
                "note": "vault is creditable, but this repo runs the SEMANTIC classifier — the only "
                        "token record is class-label slugs, and no slug token hits the vault surface. "
                        "A few slugs failing to overlap is not evidence the prompts wouldn't. Needs a "
                        "real prompt sample before any flip."}
    if r["hit_tokens"] == 0:
        return {"flip": False, "label": "COLD-START UNREACHABLE",
                "note": f"vault surface ({r['surface_stemmed']} stemmed tokens) never intersects the "
                        f"{r['prompt_vocab']}-token prompt vocabulary over {r['prompts']} prompts — the only "
                        "layer that can fire cold (lexical reflex) never fires. Structural + muscle-memory "
                        "are bootstrap-dead; the dense lift is statically dormant."}
    bloat = v.get("default_ingest_bloat", 1.0)
    ingest_warn = ""
    if bloat >= 3.0:
        ingest_warn = (f' MUST set "ingest":"tracked" — the genome default "all" would digest '
                       f'{v["files_all"]} files vs {v["files_tracked"]} tracked ({bloat}× bloat: vendored/'
                       "build noise).")
    over = ""
    if r["reach_lower"] >= 0.50:
        over = (f" CAVEAT: reach is driven by generic tokens ("
                + ", ".join(t for t, _ in r.get("top_hits", [])[:3])
                + ") — firing on ≥50% of prompts is as much a CLUTTER risk as a liveness signal; "
                  "high reach is not the same as relevant reach.")
    thin_note = (" EVIDENCE IS THIN: reach measured from class-label slugs (semantic classifier), not a "
                 "full prompt vocabulary — treat the range as indicative only." if r.get("thin") else "")
    return {"flip": True, "label": "CANDIDATE" + (" (THIN)" if r.get("thin") else ""),
            "note": f"{v['creditable_frac']:.0%} of {v['nodes']} nodes creditable at min_overlap={min_overlap}; "
                    f"lexical reflex would fire on {r['reach_lower']:.0%}–{r['reach_upper']:.0%} of prompts "
                    f"({r['hit_tokens']} surface tokens seen in real prompts)." + thin_note + ingest_warn + over
                    + ' Flip = {"declarative":{"mode":"live","vault_path":"<root>","ingest":"tracked"}}'}


def run(repo_root, min_overlap: "int | None" = None, max_files: int = MAX_FILES) -> dict:
    root = Path(repo_root).resolve()
    sd = root / ".claude" / "exocortex"
    cfg = _json_file(root / "exocortex_config.json")
    decl = dict(cfg.get("declarative", {}) or {})
    cfg_live = str(decl.get("mode", "off")).lower() == "live" and bool(decl.get("vault_path"))
    mo = min_overlap if min_overlap is not None else int(
        (decl.get("attribution", {}) or {}).get("min_overlap", DEFAULT_MIN_OVERLAP))
    v = vault_census(root, mo, max_files)
    surface = v.pop("_surface", set())
    r = reach(surface, sd)
    return {"repo": root.name, "root": str(root), "declarative_live": cfg_live, "min_overlap": mo,
            "vault": v, "reach": r, "bridge": bridge_readiness(v.get("nodes", 0)),
            "verdict": verdict(cfg_live, v, r, mo)}


def estate(projects_root, max_files: int = MAX_FILES, extra_repos=None) -> dict:
    """Sweep a projects root (or several), plus explicitly-named repo roots. ``extra_repos`` covers estate
    members outside the projects root — the largest estate vault is one, and a root-glob silently omitted it."""
    roots = [projects_root] if isinstance(projects_root, (str, Path)) else list(projects_root or [])
    seen: set = set()
    repo_roots = []
    for r in roots:
        for sd in sorted(Path(r).glob("*/.claude/exocortex")):
            rp = sd.parent.parent
            if str(rp.resolve()) not in seen:
                seen.add(str(rp.resolve()))
                repo_roots.append(rp)
    for rp in (extra_repos or []):
        p = Path(rp)
        if (p / ".claude" / "exocortex").is_dir() and str(p.resolve()) not in seen:
            seen.add(str(p.resolve()))
            repo_roots.append(p)
    rows = []
    for rp in repo_roots:
        try:
            rows.append(run(rp, max_files=max_files))
        except Exception:
            continue
    cand = [r["repo"] for r in rows if r["verdict"]["flip"] is True]
    live = [r["repo"] for r in rows if r["declarative_live"]]
    blocked: dict = {}
    for r in rows:
        if r["verdict"]["flip"] is False or (r["verdict"]["flip"] is None and not r["declarative_live"]):
            blocked.setdefault(r["verdict"]["label"], []).append(r["repo"])
    return {"root": str(projects_root), "repos": len(rows), "already_live": live,
            "candidates": cand, "blocked": blocked, "rows": rows,
            "verdict": ({"disposition": -1, "label": "NO REPO QUALIFIES",
                         "note": "no dormant repo passes vault + creditability + cold-start reach; the wiki "
                                 "stays a 2-repo organ and the bridge, being downstream, stays unevaluable"}
                        if not cand else
                        {"disposition": 0, "label": f"{len(cand)} CANDIDATE(S)",
                         "note": "flipping is mechanically a config key, but candidacy is not evidence of "
                                 "keep — a flip is a prereg'd experiment (does credited-note count rise "
                                 "off zero?), not a rollout"})}


# ------------------------------------------------------------------ text output
def _fmt_row(res: dict, indent: str = "") -> str:
    v, r, vd = res["vault"], res["reach"], res["verdict"]
    L = [f"{indent}repo={res['repo']}{'  [DECLARATIVE LIVE]' if res['declarative_live'] else ''}",
         f"{indent}  vault : {v.get('files_tracked', 0)} tracked / {v.get('files_all', 0)} all md  →  "
         f"{v.get('nodes', 0)} nodes ({v.get('ingest_used', '?')})"]
    if v.get("files_truncated"):
        L.append(f"{indent}          !! {v['files_truncated']} files beyond the {MAX_FILES} cap NOT scanned")
    L.append(f"{indent}  credit: {v.get('creditable', 0)}/{v.get('nodes', 0)} nodes "
             f"({v.get('creditable_frac', 0):.1%}) carry ≥{res['min_overlap']} salient tokens")
    if r.get("known"):
        L.append(f"{indent}  reach : {r['hit_tokens']} of {r['surface_stemmed']} surface tokens appear in "
                 f"{r['prompts']} real prompts → {r['reach_lower']:.0%}–{r['reach_upper']:.0%} of prompts"
                 + ("  [THIN: " + r.get("source", "") + "]" if r.get("thin") else ""))
        if r.get("top_hits"):
            L.append(f"{indent}          top: " + ", ".join(f"{t}({c})" for t, c in r["top_hits"][:6]))
    else:
        L.append(f"{indent}  reach : UNKNOWN — {r.get('note', '')}")
    L.append(f"{indent}  => {vd['label']}: {vd['note']}")
    return "\n".join(L)


def _fmt(res: dict) -> str:
    if "rows" not in res:
        return "WIKI-CANDIDACY GAUGE\n" + _fmt_row(res, "  ") + "\n"
    L = ["WIKI-CANDIDACY GAUGE  (could the declarative organ earn keep if flipped on?)",
         f"  estate root={res['root']}  repos={res['repos']}  already live: "
         f"{', '.join(res['already_live']) or 'none'}", ""]
    for row in res["rows"]:
        L.append(_fmt_row(row, "  "))
        L.append("")
    L.append("SUMMARY:")
    L.append(f"  candidates: {', '.join(res['candidates']) or 'NONE'}")
    for label, repos in sorted(res["blocked"].items()):
        L.append(f"  blocked · {label:<28} {len(repos)}: {', '.join(repos)}")
    v = res["verdict"]
    L += ["", "VERDICT:", f"  disposition={v['disposition']}  {v['label']}", f"  => {v['note']}",
          "  NOTE: read-only; candidacy is a precondition, never evidence of keep."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Wiki-Candidacy Gauge — can the declarative organ earn keep here?")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="one repo root")
    g.add_argument("--estate", action="append",
                   help="projects root to sweep for */.claude/exocortex (repeatable)")
    ap.add_argument("--also", action="append", default=[],
                    help="an extra repo root to include in an --estate sweep (repeatable) — for members "
                         "outside the projects root, which a root-glob would silently omit")
    ap.add_argument("--min-overlap", type=int, default=None)
    ap.add_argument("--max-files", type=int, default=MAX_FILES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = (estate(args.estate, args.max_files, args.also) if args.estate
           else run(args.repo, args.min_overlap, args.max_files))
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
