"""Credit-Funnel Gauge — WHERE does the declarative crediting pipeline die, per repo? (STATS)

The Desktop longitudinal audit (2026-07-01) returned a **−1 on the primary use case**: a research repo
with a 59k-node warmed vault, 60+ real exit-0 deposits, and **zero credited notes**. Three candidate
causes were named but not separable from outside. This gauge separates them, read-only, from the data the
organism already records:

  Stage 0  CONFIG     — is the declarative organ live, and on which vault/ingest?
  Stage 1  INJECTION  — of the Bash exit-0 consequences, how many closed a segment in which notes had
                        been spliced? (audit ``wiki_injected``; stamped only when nonzero)
  Stage 2  ECHO/USE   — of those, how many had a used-note echo? (audit ``wiki_used``; ADR-006
                        min_overlap salient-token echo — the precision-first law)
  Stage 3  CREDIT     — do the colonies carry note-anchored τ edges? (the ``[notes:N]`` census)

Plus the two structural analyses that explain a dead stage:
  * VAULT CREDITABILITY — % of vault nodes whose ``salient_tokens`` (code/path/identifier tokens; prose
    contributes nothing — the deliberate ADR-006 asymmetry) meet min_overlap. A prose-only vault is
    *structurally uncreditable* no matter what fires upstream.
  * PROPOSER LIVENESS — which of the four candidate layers can fire cold: structural spreading-activation
    needs a non-empty ``wiki_active`` (exists only after a first credit), muscle-memory needs
    note-anchored τ (same bootstrap), the dense lift is **statically dormant** (the live hook never
    passes ``prompt_embedding``), leaving **lexical reflex as the only cold-start layer** — a prompt
    token must hit a doc-name/heading token or nothing is ever proposed.

Read-only, pure-stdlib (+ the salient-token fn reused VERBATIM from ``wiki.attribute`` — one
implementation, no drift), deterministic, fail-open. A run over a live repo is a labeled demonstration.

  python -m exocortex.gauge.credit_funnel_gauge --state-dir .claude/exocortex
  python -m exocortex.gauge.credit_funnel_gauge --state-dir <TAO>/.claude/exocortex --json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from exocortex.wiki.attribute import salient_tokens   # the ONE salience implementation (ADR-006)

_SEP = "\t"
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")               # mirror of propose._tokens (lexical-layer surface)
DEFAULT_MIN_OVERLAP = 2                                # the gauged ADR-006 setting (genome default)


# ------------------------------------------------------------------ loading (fail-open)
def _jsonl(path: Path) -> list:
    out: list = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return out


def _json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _effective_declarative(state_dir: Path) -> dict:
    """The target repo's own declarative config (root = state_dir/../..) — never THIS repo's genome."""
    root = state_dir.parent.parent
    cfg = _json_file(root / "exocortex_config.json")
    return dict(cfg.get("declarative", {}) or {})


# ------------------------------------------------------------------ stage 1–2: the audit funnel
def audit_funnel(records: list) -> dict:
    """Consequence-anchored stage counts. ``wiki_injected``/``wiki_used`` are stamped on the PostToolUse
    consequence record only when nonzero, so absence = 0 for that segment."""
    prompts = prompts_injected = 0
    cons = inj = used = 0
    for r in records:
        ev = r.get("event", "")
        if ev == "UserPromptSubmit":
            prompts += 1
            if r.get("injected"):
                prompts_injected += 1
        elif ev == "PostToolUse" and r.get("tool") == "Bash" and r.get("outcome") == "ok":
            cons += 1
            if int(r.get("wiki_injected", 0) or 0) > 0:
                inj += 1
            if int(r.get("wiki_used", 0) or 0) > 0:
                used += 1
    return {"prompts": prompts, "prompts_ctx_injected": prompts_injected,
            "consequences": cons, "wiki_injected_gt0": inj, "wiki_used_gt0": used}


# ------------------------------------------------------------------ stage 3: the colony credit census
def colony_census(state_dir: Path) -> dict:
    classes = anchored = anchor_edges = 0
    deposits_total = 0
    for f in sorted(state_dir.glob("colony_*.json")):
        d = _json_file(f)
        if not d:
            continue
        classes += 1
        deposits_total += int(d.get("deposits", 0) or 0)
        n = sum(1 for k in dict(d.get("tau", {}) or {}) if any(".md" in nid for nid in k.split(_SEP)))
        if n:
            anchored += 1
            anchor_edges += n
    return {"classes": classes, "deposits_total": deposits_total,
            "note_anchored_classes": anchored, "note_anchor_edges": anchor_edges}


# ------------------------------------------------------------------ vault creditability census
def vault_census(state_dir: Path, min_overlap: int) -> dict:
    """From the warmed ``wiki_cache.json`` (never digests): per-node salient-token counts → what fraction
    of the vault is even *echo-able* under the ADR-006 asymmetry (prose contributes nothing). Also the
    lexical cold-start surface: the doc-name/heading token vocabulary a prompt must intersect."""
    cache = _json_file(state_dir / "wiki_cache.json")
    nodes = cache.get("nodes", []) or []
    if not nodes:
        return {"nodes": 0}
    n_credit1 = n_creditm = 0
    lex_vocab: set = set()
    by_top: dict = {}
    for nd in nodes:
        s = salient_tokens(str(nd.get("text", "")))
        if len(s) >= 1:
            n_credit1 += 1
        if len(s) >= min_overlap:
            n_creditm += 1
        nid = str(nd.get("id", ""))
        doc = nid.split("#", 1)[0]
        lex_vocab |= set(_TOKEN_RE.findall(doc.lower()))
        for h in (nd.get("heading_path", []) or []):
            lex_vocab |= set(_TOKEN_RE.findall(str(h).lower()))
        top = doc.split("/", 1)[0] if "/" in doc else "(root)"
        agg = by_top.setdefault(top, [0, 0])
        agg[0] += 1
        agg[1] += 1 if len(s) >= min_overlap else 0
    frac = round(n_creditm / len(nodes), 4)
    return {"nodes": len(nodes), "min_overlap": min_overlap,
            "creditable_at_1": n_credit1, "creditable_at_min": n_creditm,
            "creditable_frac": frac, "frac_at_1": round(n_credit1 / len(nodes), 4),
            "lexical_vocab_size": len(lex_vocab),
            "by_top": {k: {"nodes": v[0], "creditable": v[1]} for k, v in sorted(by_top.items())}}


# ------------------------------------------------------------------ proposer liveness (structural facts)
def proposer_liveness(census: dict, vault: dict) -> dict:
    """Which candidate layers CAN fire, from the recorded state. The dense lift is statically dormant:
    ``hook.py`` calls ``propose(graph, prompt, active_context)`` without ``prompt_embedding`` — a
    code-level fact, not a data one."""
    anchored = census.get("note_anchored_classes", 0) > 0
    return {
        "structural_spreading": "live" if anchored else "BOOTSTRAP-DEAD (wiki_active fills only after a first credit)",
        "muscle_memory": "live" if anchored else "BOOTSTRAP-DEAD (needs note-anchored τ; none exists)",
        "dense_lift": "STATICALLY DORMANT (hook never passes prompt_embedding)",
        "lexical_reflex": f"the ONLY cold-start layer — prompt must hit the {vault.get('lexical_vocab_size', 0)}-token doc/heading vocabulary",
    }


# ------------------------------------------------------------------ the verdict
def verdict(cfg: dict, funnel: dict, census: dict, vault: dict) -> dict:
    if str(cfg.get("mode", "off")).lower() != "live" or not cfg.get("vault_path"):
        return {"dies_at": "STAGE 0 — CONFIG", "signal": None,
                "note": "declarative organ not live on this repo (mode/vault unset) — nothing downstream can fire"}
    cons = funnel["consequences"]
    if cons == 0:
        return {"dies_at": "NO DATA", "signal": None, "note": "no Bash exit-0 consequences recorded yet"}
    if funnel["wiki_injected_gt0"] == 0:
        boot = (census.get("note_anchored_classes", 0) == 0)
        return {"dies_at": "STAGE 1 — INJECTION", "signal": False,
                "note": ("nothing is ever spliced: " +
                         ("COLD-START LOCK — with zero prior credits, structural + muscle-memory layers are "
                          "bootstrap-dead and the dense lift is statically dormant, so injection rests "
                          "entirely on the lexical reflex, which never fired. "
                          if boot else "despite existing credits, propose/splice abstained. ") +
                         f"Vault is {vault.get('creditable_frac', 0):.0%} echo-creditable at "
                         f"min_overlap={vault.get('min_overlap')} — "
                         + ("the vault could credit if injection fired; the blocker is the proposer, not salience."
                            if vault.get("creditable_frac", 0) >= 0.3 else
                            "AND the vault is mostly prose (structurally uncreditable) — two independent blockers."))}
    if funnel["wiki_used_gt0"] == 0:
        return {"dies_at": "STAGE 2 — ECHO/USE", "signal": False,
                "note": f"notes are spliced but never echo in actions (vault creditable_frac="
                        f"{vault.get('creditable_frac', 0):.0%} at min_overlap={vault.get('min_overlap')}) — "
                        "prose-only notes / non-echoing workflow; the ADR-006 asymmetry is doing exactly "
                        "what it promises (safe under-credit), so the fix is content/altitude, not the law"}
    if census.get("note_anchored_classes", 0) == 0:
        return {"dies_at": "STAGE 3 — CREDIT", "signal": False,
                "note": "used-note echoes exist but no note-anchored τ was ever deposited — investigate "
                        "the deposit path (unexpected; wire.on_consequence should have fired)"}
    return {"dies_at": "NONE — FUNNEL LIVE", "signal": True,
            "note": f"full funnel: {funnel['wiki_injected_gt0']}/{cons} consequences injected, "
                    f"{funnel['wiki_used_gt0']} with echo, {census['note_anchored_classes']} classes credited"}


def run(state_dir, min_overlap: "int | None" = None) -> dict:
    sd = Path(state_dir)
    cfg = _effective_declarative(sd)
    mo = min_overlap if min_overlap is not None else int(
        (cfg.get("attribution", {}) or {}).get("min_overlap", DEFAULT_MIN_OVERLAP))
    records = _jsonl(sd / "audit.jsonl")
    funnel = audit_funnel(records)
    census = colony_census(sd)
    vault = vault_census(sd, mo)
    return {
        "state_dir": str(sd), "repo": sd.parent.parent.name,
        "declarative_config": cfg, "audit_records": len(records),
        "funnel": funnel, "colony": census, "vault": vault,
        "proposer_liveness": proposer_liveness(census, vault),
        "verdict": verdict(cfg, funnel, census, vault),
    }


# ------------------------------------------------------------------ text output
def _fmt(res: dict) -> str:
    f, c, v = res["funnel"], res["colony"], res["vault"]
    cfg = res["declarative_config"]
    L = ["CREDIT-FUNNEL GAUGE  (where does declarative crediting die?)",
         f"  repo={res['repo']}  audit_records={res['audit_records']}",
         f"  config: mode={cfg.get('mode', 'off')}  vault={cfg.get('vault_path', '(none)')}  "
         f"ingest={cfg.get('ingest', 'all')}", "",
         f"  STAGE 1 injection : {f['wiki_injected_gt0']}/{f['consequences']} Bash exit-0 consequences had spliced notes",
         f"  STAGE 2 echo/use  : {f['wiki_used_gt0']}/{f['consequences']} had a used-note echo (min_overlap={v.get('min_overlap', '?')})",
         f"  STAGE 3 credit    : {c['note_anchored_classes']}/{c['classes']} classes note-anchored "
         f"({c['note_anchor_edges']} anchor edges; {c['deposits_total']} total deposits)",
         f"  (context: {f['prompts_ctx_injected']}/{f['prompts']} prompts got ANY injected context)", ""]
    if v.get("nodes"):
        L += [f"  VAULT: {v['nodes']} warmed nodes — {v['creditable_frac']:.1%} echo-creditable at "
              f"min_overlap={v['min_overlap']}  ({v['frac_at_1']:.1%} at 1); lexical surface = "
              f"{v['lexical_vocab_size']} doc/heading tokens"]
        tops = sorted(v["by_top"].items(), key=lambda kv: -kv[1]["nodes"])[:6]
        for k, t in tops:
            L.append(f"    {k:<28} {t['creditable']:>6}/{t['nodes']:<6} creditable")
    else:
        L.append("  VAULT: no warmed cache (wiki_cache.json absent/empty)")
    L += ["", "  PROPOSER LAYERS (cold-start liveness):"]
    for k, s in res["proposer_liveness"].items():
        L.append(f"    {k:<20} {s}")
    vd = res["verdict"]
    L += ["", "VERDICT:", f"  dies_at={vd['dies_at']}  signal={vd['signal']}", f"  => {vd['note']}",
          "  NOTE: read-only; live = demonstration, never evidence."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Credit-Funnel Gauge — where declarative crediting dies, per repo")
    ap.add_argument("--state-dir", required=True, help="the repo's .claude/exocortex directory")
    ap.add_argument("--min-overlap", type=int, default=None,
                    help="override the effective ADR-006 echo threshold (default: repo config, else 2)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = run(args.state_dir, args.min_overlap)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
