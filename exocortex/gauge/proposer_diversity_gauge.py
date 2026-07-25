"""Proposer-Diversity Gauge — the before/after gate for F1 (ranked lexical) + F2 (explore rotation).

The 2026-07-24 log audit found the wiki proposer selecting by FILENAME, not relevance: ``_lexical``
returned matches in vault file order and ``proposer_k`` truncated them, so ``.claude/skills/*`` (which
sorts first) monopolised every splice — 2,313 matches for a colony question, 24 kept, none about the
colony. Across 33 live sessions only 18 distinct docs (9.5% of 189) were ever injected, and the
exploration channel re-offered the same never-credited notes every turn.

This gauge replays a REAL prompt corpus (the host's own transcripts — the prompts that actually drove
this repo) through both arms in one process and reports what changed:

  ARM A  "before"  lexical_rank=file  · explore_rotate=order   (the shipped-until-now behaviour)
  ARM B  "after"   lexical_rank=rank  · explore_rotate=rotate

  PRIMARY   distinct documents proposed, and distinct documents actually ENTERED THE EXPLORE CHANNEL
            across the corpus — the diversity the audit found collapsed.
  CONCENTRATION  share of all proposal slots taken by the single most-proposed doc, and by the top 3.
  CONTROL   credited-doc recall: of the docs that have genuinely EARNED τ in this repo, how many remain
            reachable in the proposals. Diversity bought by dropping the notes that actually work is a
            regression, not a fix — this is the metric that can falsify the change.

Write-free by construction: it calls ``splice._select`` directly and simulates the F2 offer ledger
in-memory (replaying the corpus in order, which is the only way rotation's effect is visible at all),
so the live ``wiki_offers.json`` is never touched.

  python -m exocortex.gauge.proposer_diversity_gauge --repo . --limit 200
  python -m exocortex.gauge.proposer_diversity_gauge --repo . --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from pathlib import Path

_SEP = "\t"
SKILL_PREAMBLE = re.compile(r"^\s*(Base directory for this skill|<command-name>|<local-command)", re.I)


# ------------------------------------------------------------------ the real prompt corpus
def _project_slug(repo: Path) -> str:
    """Claude Code's transcript directory name for a repo path: every non-alphanumeric run becomes a dash,
    so ``C:\\Users\\x\\Repo`` → ``C--Users-x-Repo``. Derived, not hardcoded to the C: drive — the earlier
    version stripped a literal leading "C-" and would have mangled any other drive letter."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))   # PER CHARACTER — "C:\\" → "C--", not "C-"


def load_prompts(repo: Path, limit: int = 0) -> list:
    """Real user prompts from the host's transcripts for this repo. Skill-invocation preambles and
    command echoes are dropped — they are harness text, not what a user asked, and they bias the corpus
    straight at the skill files whose dominance is the thing under test."""
    home = Path(os.path.expanduser("~")) / ".claude" / "projects"
    slug = _project_slug(repo)
    cands = sorted(glob.glob(str(home / slug / "*.jsonl")))
    load_prompts.exact_slug = bool(cands)           # disclosed by run(); a silent widening is a bug
    if not cands:
        # Slug drift → fall back to a basename match. This is DELIBERATELY reported, not silent: the
        # pattern also matches sibling repos ("SentAInce" hits "SentAInce-public"), which once inflated
        # the corpus from 340 prompts to 635 without a word.
        cands = sorted(glob.glob(str(home / f"*{repo.resolve().name}*" / "*.jsonl")))
    out: list = []
    for f in cands:
        try:
            lines = Path(f).read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for L in lines:
            if not L.strip():
                continue
            try:
                d = json.loads(L)
            except Exception:
                continue
            if d.get("type") != "user":
                continue
            c = (d.get("message") or {}).get("content")
            if isinstance(c, str):
                t = c
            elif isinstance(c, list):
                t = " ".join(x.get("text", "") for x in c
                             if isinstance(x, dict) and x.get("type") == "text")
            else:
                continue
            t = (t or "").strip()
            if len(t) > 15 and not t.startswith("<") and not SKILL_PREAMBLE.match(t):
                out.append(t)
    return out[:limit] if limit else out


# ------------------------------------------------------------------ ground truth: what has EARNED τ
def credited_docs(state_dir: Path) -> set:
    """Documents carrying real earned τ — derived from the colonies' edge keys (a note id contains '#')."""
    docs: set = set()
    for f in sorted(state_dir.glob("colony_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for edge in (d.get("tau") or {}):
            for nid in str(edge).split(_SEP):
                if "#" in nid and ".md" in nid:
                    docs.add(nid.partition("#")[0])
    return docs


# ------------------------------------------------------------------ one arm
def run_arm(graph, prompts: list, *, rank: bool, rotate: bool, budget: int, cap: int, floor: float) -> dict:
    """Replay the corpus IN ORDER through one configuration. The offer ledger is simulated in memory so
    rotation's cross-prompt effect is visible without touching the live store."""
    from exocortex.wiki.propose import propose
    from exocortex.wiki.splice import _select

    os.environ["EXOCORTEX_LEXICAL_RANK"] = "1" if rank else "0"
    os.environ["EXOCORTEX_EXPLORE_ROTATE"] = "1" if rotate else "0"
    graph._lex_idf = None                            # arm-independent, but rebuild so timing is honest

    offers: dict = {}
    proposed: dict = {}
    explored: dict = {}
    slots = explore_slots = 0
    import exocortex.wiki.splice as SP
    orig = SP._offers
    SP._offers = lambda: offers                      # inject the simulated ledger (no disk)
    try:
        for p in prompts:
            cands = propose(graph, prompt=p)
            for nid in cands:
                doc = nid.partition("#")[0]
                proposed[doc] = proposed.get(doc, 0) + 1
                slots += 1
            _top, ex = _select(graph, cands, floor, cap, budget)
            seen_docs = []
            for n in ex:
                doc = n.id.partition("#")[0]
                explored[doc] = explored.get(doc, 0) + 1
                explore_slots += 1
                if doc not in seen_docs:
                    seen_docs.append(doc)
            for doc in seen_docs:                    # what the live path persists after a splice
                offers[doc] = offers.get(doc, 0) + 1
    finally:
        SP._offers = orig
        os.environ.pop("EXOCORTEX_LEXICAL_RANK", None)
        os.environ.pop("EXOCORTEX_EXPLORE_ROTATE", None)

    top = sorted(proposed.items(), key=lambda kv: -kv[1])
    return {"prompts": len(prompts),
            "distinct_docs_proposed": len(proposed),
            "distinct_docs_explored": len(explored),
            "proposal_slots": slots, "explore_slots": explore_slots,
            "top_doc_share": round(top[0][1] / slots, 4) if slots else 0.0,
            "top3_doc_share": round(sum(c for _d, c in top[:3]) / slots, 4) if slots else 0.0,
            "top_docs": top[:8], "_proposed": set(proposed)}


def run(repo, limit: int = 0) -> dict:
    repo = Path(repo).resolve()
    os.environ.setdefault("CLAUDE_PROJECT_DIR", str(repo))
    from exocortex.colony import PRUNE
    from exocortex.config import declarative_vault
    from exocortex.wiki.splice import EXPLORE_BUDGET, MAX_EXONS
    from exocortex.wiki.store import load_graph

    prompts = load_prompts(repo, limit)
    graph = load_graph(declarative_vault())
    if graph is None or not graph.nodes:
        return {"error": "no wiki graph (declarative organ not live / vault empty)", "repo": repo.name}
    budget = EXPLORE_BUDGET or 5      # gauge the channel even where the repo ships it dormant
    earned = credited_docs(repo / ".claude" / "exocortex")

    # Four arms, not two — otherwise "F1+F2 helped" cannot distinguish a real F2 contribution from F1
    # carrying the whole effect. The isolating arms are the attribution control.
    arms = {}
    for key, rank, rot in (("before", False, False), ("rank_only", True, False),
                           ("rotate_only", False, True), ("after", True, True)):
        arm = run_arm(graph, prompts, rank=rank, rotate=rot, budget=budget, cap=MAX_EXONS, floor=PRUNE)
        reach = earned & arm.pop("_proposed")
        arm["credited_docs_total"] = len(earned)
        arm["credited_docs_reached"] = len(reach)
        arm["credited_recall"] = round(len(reach) / len(earned), 4) if earned else None
        arms[key] = arm
    return {"repo": repo.name, "nodes": len(graph.nodes),
            "docs_in_vault": len({n.partition("#")[0] for n in graph.nodes}),
            "prompts": len(prompts), "explore_budget": budget,
            "corpus_exact_slug": bool(getattr(load_prompts, "exact_slug", True)),
            **arms, "verdict": verdict(arms["before"], arms["after"]),
            "attribution": attribution(arms)}


def attribution(arms: dict) -> dict:
    """Which fix did what. F1 moves the PROPOSAL pool (and therefore the explore pool downstream of it);
    F2 can only rotate within whatever pool it is given, so its solo effect is bounded by the baseline
    pool size — the honest way to read a small rotate-only delta."""
    b, r1, r2, d = arms["before"], arms["rank_only"], arms["rotate_only"], arms["after"]
    return {
        "F1_rank_explored_delta": r1["distinct_docs_explored"] - b["distinct_docs_explored"],
        "F2_rotate_explored_delta_solo": r2["distinct_docs_explored"] - b["distinct_docs_explored"],
        "F2_rotate_explored_delta_on_top_of_F1": d["distinct_docs_explored"] - r1["distinct_docs_explored"],
        "reading": ("F1 is the fix — it decides which docs exist to explore at all; F2 is additive and "
                    "its solo ceiling is the un-ranked pool, so judge it by the on-top-of-F1 delta"),
    }


def verdict(b: dict, a: dict) -> dict:
    """Pre-registered gate: F1+F2 pass only if BOTH diversity axes rise AND credited-doc recall does not
    fall. Diversity bought by dropping the notes that have actually earned their keep is a regression."""
    dp = a["distinct_docs_proposed"] - b["distinct_docs_proposed"]
    de = a["distinct_docs_explored"] - b["distinct_docs_explored"]
    dr = (a["credited_recall"] or 0) - (b["credited_recall"] or 0)
    if dr < 0:
        return {"disposition": -1, "label": "REGRESSION — relevance traded for novelty",
                "note": f"credited-doc recall fell {b['credited_recall']:.0%} → {a['credited_recall']:.0%}; "
                        "the ranking is surfacing new tissue by dropping notes that already earn τ"}
    if dp <= 0 and de <= 0:
        return {"disposition": -1, "label": "NO EFFECT",
                "note": "neither proposal nor explore diversity moved — the cap was not the mechanism"}
    return {"disposition": 1, "label": "GATE MET",
            "note": f"distinct docs proposed {b['distinct_docs_proposed']}→{a['distinct_docs_proposed']} "
                    f"({dp:+d}), explored {b['distinct_docs_explored']}→{a['distinct_docs_explored']} "
                    f"({de:+d}), concentration {b['top_doc_share']:.0%}→{a['top_doc_share']:.0%}, "
                    f"credited-doc recall {b['credited_recall']:.0%}→{a['credited_recall']:.0%} "
                    f"({dr:+.0%} — the control held)"}


def _fmt(r: dict) -> str:
    if r.get("error"):
        return f"PROPOSER-DIVERSITY GAUGE\n  {r['repo']}: {r['error']}\n"
    b, a = r["before"], r["after"]
    rows = [("distinct docs PROPOSED", "distinct_docs_proposed"),
            ("distinct docs EXPLORED", "distinct_docs_explored"),
            ("top-doc share of slots", "top_doc_share"),
            ("top-3 doc share", "top3_doc_share"),
            ("credited-doc recall", "credited_recall")]
    L = ["PROPOSER-DIVERSITY GAUGE  (F1 ranked lexical + F2 explore rotation)",
         f"  repo={r['repo']}  vault={r['nodes']} nodes / {r['docs_in_vault']} docs  "
         f"prompts={r['prompts']} (real transcripts)  explore_budget={r['explore_budget']}"
         + ("" if r.get("corpus_exact_slug", True) else
            "\n  !! transcript slug did not match — corpus came from a BASENAME glob and may include "
            "sibling repos"), "",
         f"  {'metric':<26}{'BEFORE':>10}{'AFTER':>10}   delta",
         f"  {'-'*26}{'-'*10}{'-'*10}   -----"]
    for label, key in rows:
        x, y = b.get(key), a.get(key)
        if isinstance(x, float) and x <= 1.0 and "share" in key or key == "credited_recall":
            L.append(f"  {label:<26}{x:>9.0%}{y:>10.0%}   {(y-x):+.0%}")
        else:
            L.append(f"  {label:<26}{x:>10}{y:>10}   {y-x:+d}")
    L += ["", "  most-proposed docs BEFORE:"]
    for d, c in b["top_docs"][:5]:
        L.append(f"    {c:>5}  {d}")
    L += ["  most-proposed docs AFTER:"]
    for d, c in a["top_docs"][:5]:
        L.append(f"    {c:>5}  {d}")
    at = r["attribution"]
    L += ["", "  ATTRIBUTION (distinct docs EXPLORED):",
          f"    F1 ranked lexical            {at['F1_rank_explored_delta']:+d}",
          f"    F2 rotation, alone           {at['F2_rotate_explored_delta_solo']:+d}",
          f"    F2 rotation, on top of F1    {at['F2_rotate_explored_delta_on_top_of_F1']:+d}",
          f"    => {at['reading']}"]
    v = r["verdict"]
    L += ["", "VERDICT:", f"  disposition={v['disposition']:+d}  {v['label']}", f"  => {v['note']}",
          "  NOTE: replay over real prompts; write-free (the live offer ledger is never touched)."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Proposer-Diversity Gauge — before/after gate for F1+F2")
    ap.add_argument("--repo", default=".", help="repo root (its transcripts supply the prompt corpus)")
    ap.add_argument("--limit", type=int, default=0, help="cap the corpus (0 = all prompts)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    r = run(args.repo, args.limit)
    print(json.dumps({k: v for k, v in r.items()}, indent=2, default=str) if args.json else _fmt(r),
          end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
