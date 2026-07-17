"""Consequence-provenance "why" renderer (issue #13; ENHANCEMENTS G3) — strictly a READER.

Every decision the exocortex makes is already persisted: the hash-chained ``audit.jsonl``, the
per-class ``colony_<label>.json`` with τ-weighted routes (+ F3 per-edge ``meta{ts,model}``), and
the note-credit counters on exit-0 consequences. This module reconstructs, for one decision,
the trail the organism can *prove*:

  - the deposit's step segment, rebuilt from the session's audited tool records (verb altitude,
    ``colony.verb_node`` — the same lens the colony writes through);
  - which of those edges hold τ **today**, in which goal-class colonies, with their provenance
    stamp — and, honestly, which have been pruned/decayed away since (absence is reported, never
    papered over);
  - the notebook's part: notes injected vs credited on the exit-0 consequence;
  - the medical record: the hash-chain segment covering those records, each link re-verified
    with ``integrity.chain_hash`` from bytes on disk.

No organism writes anywhere — this never touches τ, σ, state, or config (ADR-013 discipline:
a reader informs; it never earns).

CLI:
    python -m exocortex.provenance <audit.jsonl> [--session <id>] [--last N] [--state-dir DIR]

Defaults: the most recent session that contains a deposit; its last deposit (``--last N`` for
more, newest first). ``--state-dir`` defaults to the audit file's directory (where the
``colony_*.json`` stores live). Output is Markdown on stdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from exocortex.colony import verb_node
from exocortex.integrity import chain_hash

_SEP = "\t"
CONSEQUENCE_EVENTS = ("PostToolUse", "PostToolUseFailure")


# ----------------------------------------------------------------------------- readers
def read_audit(path: Path) -> list[dict]:
    out = []
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"_unparseable": line[:120]})
    return out


def read_colonies(state_dir: Path) -> dict:
    """label -> {"tau": {...}, "meta": {...}, "deposits": int} — raw store reads, no Colony import
    side-effects beyond what the exporter already does."""
    colonies = {}
    for p in sorted(Path(state_dir).glob("colony_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        label = d.get("label") or p.stem[len("colony_"):]
        colonies[label] = {"tau": d.get("tau") if isinstance(d.get("tau"), dict) else {},
                           "meta": d.get("meta") if isinstance(d.get("meta"), dict) else {},
                           "deposits": int(d.get("deposits", 0) or 0)}
    return colonies


# ----------------------------------------------------------------------------- reconstruction
def pick_session(records: list[dict], session: str | None) -> str | None:
    """An explicit session, or the most recent one that actually contains a deposit."""
    if session:
        return session
    for r in reversed(records):
        if (r.get("event") in CONSEQUENCE_EVENTS and isinstance(r.get("seg_len"), int)
                and r["seg_len"] > 0):
            return r.get("session")
    return None


def session_slice(records: list[dict], session: str) -> list[tuple[int, dict]]:
    """(audit-line-index, record) for one session, in file order."""
    return [(i, r) for i, r in enumerate(records) if r.get("session") == session]


def deposits_in(sess: list[tuple[int, dict]]) -> list[tuple[int, dict]]:
    return [(i, r) for i, r in sess
            if r.get("event") in CONSEQUENCE_EVENTS
            and isinstance(r.get("seg_len"), int) and r["seg_len"] > 0
            and r.get("outcome") == "ok"]


def segment_for(sess: list[tuple[int, dict]], dep_idx: int, seg_len: int) -> list[tuple[int, dict]]:
    """The tool-step records forming the deposit's segment: the last ``seg_len + 1`` audited tool
    steps in this session up to and including the deposit record. Rebuilt from persisted records
    at the same verb altitude the colony deposits through; the τ cross-check below makes any
    reconstruction drift *visible* instead of asserted away."""
    steps = [(i, r) for i, r in sess
             if r.get("tool") and r.get("event") in CONSEQUENCE_EVENTS and i <= dep_idx]
    return steps[-(seg_len + 1):]


def edge_evidence(colonies: dict, src: str, dst: str) -> list[dict]:
    """Everywhere this edge holds τ today."""
    key = f"{src}{_SEP}{dst}"
    out = []
    for label, c in colonies.items():
        if key in c["tau"]:
            m = c["meta"].get(key) or {}
            out.append({"class": label, "tau": c["tau"][key],
                        "ts": m.get("ts"), "model": m.get("model")})
    return sorted(out, key=lambda e: -e["tau"])


def verify_chain(seg: list[tuple[int, dict]], records: list[dict]) -> list[dict]:
    """Re-verify the chain links covering the segment's records, from bytes on disk. A record
    without chain fields is reported ``unchained`` (audit_chain off when it was written) — an
    honest state, distinct from a broken link."""
    out = []
    for i, r in seg:
        if "_unparseable" in r:
            out.append({"index": i, "state": "unparseable"})
            continue
        if not r.get("hash"):
            out.append({"index": i, "state": "unchained"})
            continue
        ok_hash = chain_hash(r, r.get("prev", "")) == r["hash"]
        prev_ok = True
        for j in range(i - 1, -1, -1):
            pr = records[j]
            if pr.get("hash"):
                prev_ok = (r.get("prev") == pr["hash"])
                break
        out.append({"index": i, "state": "ok" if (ok_hash and prev_ok) else "BROKEN",
                    "hash": r["hash"][:16], "payload_ok": ok_hash, "link_ok": prev_ok})
    return out


# ----------------------------------------------------------------------------- rendering
def _md_escape(s, limit: int = 100) -> str:
    s = str(s or "").replace("`", "'").replace("\n", " ")
    return s[:limit] + ("…" if len(s) > limit else "")


def render_deposit(records: list[dict], sess: list[tuple[int, dict]], colonies: dict,
                   dep_idx: int, dep: dict) -> str:
    lines = []
    node = verb_node(dep.get("tool", ""), dep.get("command", ""))
    lines.append(f"## Deposit @ {dep.get('ts', '?')} — `{node}` exit 0 (seg_len {dep['seg_len']})")
    lines.append(f"The verified success: `{_md_escape(dep.get('command'))}` "
                 f"(energy {dep.get('energy')}, tier {dep.get('tier')})")
    lines.append("")

    seg = segment_for(sess, dep_idx, dep["seg_len"])
    nodes = [(i, r, verb_node(r.get("tool", ""), r.get("command", ""))) for i, r in seg]
    lines.append("### The route (reconstructed from audited steps)")
    for i, r, n in nodes:
        oc = r.get("outcome") or "?"
        lines.append(f"- [{i}] `{n}` ← `{_md_escape(r.get('command'), 70)}` → {oc}")
    lines.append("")

    lines.append("### Where those edges hold τ today")
    any_edge = False
    real_edges = 0
    for (_, _, n1), (_, _, n2) in zip(nodes, nodes[1:]):
        if n1 == n2:
            lines.append(f"- `{n1}` → `{n2}`: self-edge — never stored (W5 credit hygiene: a "
                         f"repeat of the same verb is not a routing transition)")
            continue
        real_edges += 1
        ev = edge_evidence(colonies, n1, n2)
        if ev:
            any_edge = True
            for e in ev:
                stamp = ""
                if e["ts"]:
                    stamp = f", stamped ts={e['ts']}" + (f" model={e['model']}" if e["model"] else "")
                lines.append(f"- `{n1}` → `{n2}`: τ={e['tau']:.3f} in class `{e['class']}`"
                             f" ({colonies[e['class']]['deposits']} lifetime deposits{stamp})")
        else:
            lines.append(f"- `{n1}` → `{n2}`: no τ today (decayed or pruned since — the organism forgets "
                         f"honestly; this deposit still happened, the chain below proves it)")
    if not nodes[:-1]:
        lines.append("- (single-step segment — no edges)")
    if not any_edge and real_edges:
        lines.append("- note: none of the segment's edges survive in any colony — every route "
                     "decays unless success keeps re-earning it (ADR-001).")
    lines.append("")

    inj = int(dep.get("wiki_injected", 0) or 0)
    used = int(dep.get("wiki_used", 0) or 0)
    lines.append("### The notebook (declarative credit)")
    if inj:
        lines.append(f"- {inj} note(s) injected; **{used} credited** — a note is credited only when its "
                     f"salient tokens echo in the exit-0 action (attribution guard, overlap≥2).")
    else:
        lines.append("- no notes were injected on this consequence (declarative off, or nothing matched).")
    lines.append("")

    lines.append("### The medical record (hash chain, re-verified from disk)")
    for v in verify_chain(seg, records):
        if v["state"] == "ok":
            lines.append(f"- [{v['index']}] `{v['hash']}…` ✓ payload + link verified")
        elif v["state"] == "unchained":
            lines.append(f"- [{v['index']}] unchained (audit_chain was off when written)")
        elif v["state"] == "unparseable":
            lines.append(f"- [{v['index']}] ⚠ unparseable record (torn write?)")
        else:
            lines.append(f"- [{v['index']}] `{v.get('hash', '')}…` ✗ **CHAIN BROKEN** "
                         f"(payload_ok={v['payload_ok']}, link_ok={v['link_ok']}) — a silent edit snaps here")
    lines.append("")
    return "\n".join(lines)


def render(audit_path: Path, session: str | None = None, last: int = 1,
           state_dir: Path | None = None) -> str:
    audit_path = Path(audit_path)
    state_dir = Path(state_dir) if state_dir else audit_path.parent
    records = read_audit(audit_path)
    if not records:
        return f"# Provenance\n\nNo audit records at `{audit_path}`.\n"
    sid = pick_session(records, session)
    if not sid:
        return "# Provenance\n\nNo session with a deposit found in this audit store.\n"
    sess = session_slice(records, sid)
    deps = deposits_in(sess)
    colonies = read_colonies(state_dir)
    head = [f"# Provenance — session `{sid}`",
            "",
            f"Audit: `{audit_path}` ({len(records)} records; {len(sess)} in this session; "
            f"{len(deps)} deposits). Colonies read: {len(colonies)}. "
            "This is a READER — nothing below wrote anything.",
            ""]
    if not deps:
        return "\n".join(head) + "\nThis session earned no deposits — no memory was written from it.\n"
    body = [render_deposit(records, sess, colonies, i, r) for i, r in reversed(deps[-max(1, last):])]
    return "\n".join(head) + "\n" + "\n".join(body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render one decision's consequence provenance (read-only)")
    ap.add_argument("audit", nargs="?", default=None,
                    help="path to audit.jsonl (default: ./.claude/exocortex/audit.jsonl)")
    ap.add_argument("--session", default=None, help="session id (default: latest with a deposit)")
    ap.add_argument("--last", type=int, default=1, help="how many deposits to render, newest first")
    ap.add_argument("--state-dir", default=None, help="dir holding colony_*.json (default: audit's dir)")
    args = ap.parse_args(argv)
    audit = Path(args.audit) if args.audit else Path(".claude/exocortex/audit.jsonl")
    md = render(audit, session=args.session, last=args.last,
                state_dir=Path(args.state_dir) if args.state_dir else None)
    try:
        print(md)
    except UnicodeEncodeError:
        print(md.encode("ascii", "replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
