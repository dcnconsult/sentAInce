"""Memory inventory reconciliation — a sibling ``UserPromptSubmit`` hook that tells the agent, mechanically,
when credited declarative memory is MISSING from what it was given.

Motivation: an agent can hold both the credited-note count (``memory_status``'s ``[notes:N]``) and the
notes actually delivered in view and still not notice that one is missing; whether it reconciles the two
unprompted varies by model and by how the count is explained. So the reconciliation is done mechanically
and the gap is stated, instead of hoping the model asks for the inventory and knows what it means.
(The notice's effect on agent behaviour is not a public claim; see ``docs/CLAIMS.md``.)

What it computes (pure reads — ADR-013: INFORMS, never writes):
  credited  = the declarative note anchors the goal-class colony credits (``digest.is_note_id``, the
              same rule ``memory_status`` uses for ``[notes:N]``)
  present   = credited anchors whose NodeId is in the current vault digest
  removed   = credited anchors whose file (relpath) is gone from the vault
  changed   = credited anchors whose relpath still exists but under a different content hash — the note
              was edited after it earned τ, so the credit no longer vouches for the current text
NodeId is ``{relpath}#{content-hash}`` (``wiki/digest.py``), so both cases are exact, not heuristic.

Discipline:
  * SIBLING, not an edit: registers as an ADDITIONAL ``UserPromptSubmit`` command (the R3 precedent,
    ``tuner/reflect_preamble.py``); ``hook.py``/``colony.py``/``epistemic.py`` stay byte-pinned (ADR-016).
  * NEVER WRITES: no τ, no colony/session/audit writes, no ``cues.json`` save (read-only classify), and no
    digest-cache write — the cache is read only on an exact signature match (the main hook owns it and
    its write is not atomic; a second writer racing it could tear it).
  * DORMANT BY DEFAULT: activates only when the Genome's ``declarative.inventory_notice`` is ``gap`` (emit
    only when something is missing) or ``always`` (also emit the one-line semantics when nothing is), or
    via ``EXOCORTEX_INVENTORY_NOTICE``. Requires the declarative organ to be live with a vault.
  * Fail-open, silent on any error; output budget-capped.

Registration (append to the UserPromptSubmit hooks array, after the main hook):
    python -m exocortex.wiki.inventory UserPromptSubmit --state <repo>/.claude/exocortex
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:                                     # direct-script convenience
    sys.path.insert(0, str(_ROOT))

from exocortex.wiki.digest import is_note_id                       # noqa: E402  (re-exported)

NOTICE_VERSION = "inventory_notice/1"
BUDGET_CHARS = 900
MAX_LISTED = 6
_SEP = "\t"                                                        # colony τ edge-key separator
HEADER = "[exocortex · memory inventory — mechanical reconciliation of credited vs present records]"
SEMANTICS = ("This task class has {n} credited memory record(s); credited records are normally all delivered "
             "into your context.")


def mode() -> str:
    env = os.environ.get("EXOCORTEX_INVENTORY_NOTICE")
    if env is not None:
        return env.strip().lower()
    try:
        from exocortex.genome import GENOME
        return str(GENOME.get("declarative", {}).get("inventory_notice", "off")).strip().lower()
    except Exception:
        return "off"


def credited_anchors(colony) -> list:
    """Declarative note anchors the colony credits (strict NodeId shape, ``digest.is_note_id``: a looser
    ``'.md' in nid`` rule also counts a procedural verb node like ``bash:BODY='GOVERNANCE.md`` and would
    raise a false "removed" alarm)."""
    seen: dict = {}
    for k in (getattr(colony, "tau", None) or {}):
        for nid in str(k).split(_SEP):
            if is_note_id(nid):
                seen[nid] = True
    return sorted(seen)


def reconcile(anchors: list, node_ids) -> dict:
    """Pure: classify each credited anchor against the current vault's node ids."""
    present_ids = set(node_ids)
    by_path: dict = {}
    for nid in present_ids:
        by_path.setdefault(nid.split("#", 1)[0], set()).add(nid)
    removed, changed = [], []
    for a in anchors:
        if a in present_ids:
            continue
        rel = a.split("#", 1)[0]
        (changed if rel in by_path else removed).append(rel)
    return {"credited": len(anchors), "present": len(anchors) - len(removed) - len(changed),
            "removed": sorted(set(removed)), "changed": sorted(set(changed))}


def notice(rec: dict, how: str) -> "str | None":
    gap = rec["removed"] or rec["changed"]
    if how not in ("gap", "always") or rec["credited"] == 0 or (how == "gap" and not gap):
        return None
    lines = [HEADER, SEMANTICS.format(n=rec["credited"])]
    if gap:
        def _ls(xs):
            shown = ", ".join(xs[:MAX_LISTED])
            return shown + (f" (+{len(xs) - MAX_LISTED} more)" if len(xs) > MAX_LISTED else "")
        parts = []
        if rec["removed"]:
            parts.append(f"{len(rec['removed'])} removed from the vault ({_ls(rec['removed'])})")
        if rec["changed"]:
            parts.append(f"{len(rec['changed'])} edited since they were credited ({_ls(rec['changed'])})")
        lines.append(f"Only {rec['present']} of {rec['credited']} are present: " + "; ".join(parts) + ".")
        lines.append("Memory for this task is incomplete or outdated — verify the affected conventions against "
                     "the code before relying on it.")
    text = "\n".join(lines)
    return text if len(text) <= BUDGET_CHARS else text[:BUDGET_CHARS - 1] + "…"


def _node_ids_readonly(vault: Path, ingest: str) -> list:
    """The vault's NodeIds WITHOUT writing the main hook's digest cache: read it on an exact signature
    match, else digest in memory and discard."""
    from exocortex.config import state_dir
    from exocortex.wiki import store
    files = store._md_files(vault, ingest)
    if not files:
        return []
    sig = store._signature(vault, files)
    cache = state_dir() / store._CACHE_NAME
    if cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if d.get("signature") == sig:
                return [nd["id"] for nd in d.get("nodes", []) if "id" in nd]
        except Exception:
            pass
    return [n.id for n in store._digest_vault(vault, files)]


def handle(data: dict) -> "dict | None":
    how = mode()
    if how not in ("gap", "always"):
        return None
    from exocortex.config import declarative_enabled, declarative_ingest, declarative_vault
    vault = declarative_vault()
    if not declarative_enabled() or not vault:
        return None
    from exocortex.colony import Colony
    from exocortex.cue_classifier import CueClassifier
    label = CueClassifier.load().classify(str(data.get("prompt") or "")).get("label", "_default")  # never saved
    anchors = credited_anchors(Colony.load(label))
    if not anchors:
        return None
    vp = Path(vault)
    node_ids = _node_ids_readonly(vp, declarative_ingest()) if vp.is_dir() else []
    text = notice(reconcile(anchors, node_ids), how)
    if not text:
        return None
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if not argv or argv[0] != "UserPromptSubmit":
            return 0
        if "--state" in argv:
            os.environ["EXOCORTEX_STATE_DIR"] = argv[argv.index("--state") + 1]
        out = handle(json.loads(sys.stdin.read() or "{}"))
        if out:
            print(json.dumps(out))
    except Exception:
        pass                                                         # advisory organ: never break a session
    return 0


if __name__ == "__main__":
    sys.exit(main())
