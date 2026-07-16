"""Repo Orientation Capsule — the ADR-019 cross-repo orientation layer (read-side, distributed hybrid).

When an agent works OUTSIDE the current working tree it must orient before it assumes: load the target
repo's capsule, check its credibility grade, and re-orient first when the grade is Low/Unknown. The full
standing law is docs/ORIENTATION_DISCIPLINE.md; the decision record is ADR-019.

Architecture (the distributed-hybrid shape, PI-ratified 2026-07-08):
  * The CAPSULE is a per-repo *claim* — ``.claude/exocortex/capsule.json``, stamped as a skeleton by
    ``exocortex.deploy install``, hand-updated at re-orient time. It declares identity, canonical status,
    maturity/strength/tier, claim-boundary pointer, last-reviewed date, risks, and cross-repo links.
  * The GRADE is the reader's AUDIT of that claim — computed here, at read time, from live probes (git
    presence, real mtime, tests) plus the drift between what is declared and what the disk shows. A
    self-asserted grade would rebuild the README problem this layer exists to fix, so the capsule file
    carries NO grade field and any it did carry would be ignored.
  * The estate ``REPO_LOG.md`` (outside this repo; located via ``EXOCORTEX_REPO_LOG`` or
    ``<EXOCORTEX_PROJECTS_ROOT>/REPO_LOG.md``) is SEED + FALLBACK: the one-shot ``--seed`` CLI derives
    initial capsules from its rows, and repos with no capsule fall back to their log row. Neither source
    reachable -> grade Unknown, honestly noted (a public/portable install carries no estate data).

Boundary: a capsule ORIENTS working memory only. It never earns tau, never gates recall, and is never
evidence (ADR-013 — a rendered status is a legible claim, not a consequence). The link vocabulary below is
pinned by NAME here; machine traversal of links to scope recall is ADR-014's parked question, not this
module's. Read-only except the explicit ``--seed`` CLI (the MCP tool never writes).

Stdlib-only, numpy-free; never on the hook hot path.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date
from pathlib import Path

# The ten first-class cross-repo edges (ADR-019). Pinned as names; consumption stays read-side.
EDGES = (
    "supersedes", "superseded_by", "feeds_into", "depends_on", "shares_artifact_with",
    "forked_from", "public_mirror_of", "private_canonical_of", "deployment_target_of",
    "evidence_source_for",
)
# Edges whose declarations are expected to be mirrored by the counterpart repo's capsule/log entry.
# A one-sided pair is a symmetry FLAG (surfaced by the exporter estate view), not an error.
_INVERSE = {
    "supersedes": "superseded_by", "superseded_by": "supersedes",
    "public_mirror_of": "private_canonical_of", "private_canonical_of": "public_mirror_of",
    "shares_artifact_with": "shares_artifact_with",
}

# Grade thresholds — calibration, not doctrine (ADR-019 leaves the values open; the rubric shape is pinned).
_FRESH_REVIEW_D = 30    # High requires a review at most this old
_STALE_REVIEW_D = 90    # a review older than this is Low on its own
_DRIFT_TOL_D = 7        # High tolerates at most this declared-vs-observed activity gap
_DRIFT_LIE_D = 30       # a gap beyond this means the declaration contradicts the disk -> Low
_DORMANT_D = 60         # Tier C/D with no disk activity for this long is Low

_SKIP_DIRS = {".git", ".claude", ".cursor", "node_modules", ".venv", "venv", "__pycache__",
              ".ruff_cache", ".pytest_cache", ".mypy_cache", "dist", "build"}
# The organism's own deployment footprint never counts as repo ACTIVITY: deploying into a dormant repo
# must not make it look alive (the drift signal would then flag every deploy fan-out as a contradiction).
_SKIP_FILES = {"exocortex_config.json", "AGENTS.md"}
_PROBE_DEPTH = 2        # bounded mtime walk: repo root + two levels
_PROBE_CAP = 500        # stop stat-ing after this many files — orientation, not an audit


# ----------------------------------------------------------------------------- sources: capsule + REPO_LOG
def capsule_path(root: Path) -> Path:
    return Path(root) / ".claude" / "exocortex" / "capsule.json"


def load_capsule(root: Path) -> dict | None:
    """The repo's DECLARED capsule, or None. A capsule is a claim: any 'grade'/'credibility' key someone
    smuggled into the file is dropped here so it can never masquerade as the reader's audit."""
    try:
        p = capsule_path(root)
        if not p.is_file():
            return None
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return None
        d.pop("grade", None)
        d.pop("credibility", None)
        return d
    except Exception:
        return None


def repo_log_path() -> Path | None:
    """Locate the estate REPO_LOG.md: ``EXOCORTEX_REPO_LOG`` wins; else ``<EXOCORTEX_PROJECTS_ROOT>/
    REPO_LOG.md``. None when neither resolves — the portable/public case, which must degrade honestly."""
    p = os.environ.get("EXOCORTEX_REPO_LOG")
    if p and Path(p).is_file():
        return Path(p)
    proot = os.environ.get("EXOCORTEX_PROJECTS_ROOT")
    if proot:
        cand = Path(proot) / "REPO_LOG.md"
        if cand.is_file():
            return cand
    return None


def _iso(s):
    try:
        return date.fromisoformat(str(s).strip())
    except Exception:
        return None


def parse_repo_log(path: Path) -> dict:
    """Parse the hand-audited estate log (tolerantly — it is prose-first, machine-second):
      * header ``Audited: **YYYY-MM-DD**`` -> the estate-wide last-reviewed date,
      * the Master-ranking table rows -> per-repo {last_activity, maturity, strength, tier, status},
      * an optional ``## Cross-repo links`` section of ``- `SRC` edge `DST```` bullets -> link triples.
    Returns {"audited", "rows", "links"}; unreadable -> empty dict (callers treat as absent)."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    m = re.search(r"Audited:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*", text)
    audited = _iso(m.group(1)) if m else None
    rows: dict = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")][1:-1]
        if len(cells) < 8 or not cells[0].isdigit():
            continue
        name = cells[1].strip("*` ")
        rows[name] = {
            "name": name,
            "last_activity": _iso(cells[2]),
            "maturity": cells[4], "strength": cells[5],
            "tier": (re.sub(r"[^A-Za-z]", "", cells[6]) or "")[:1].upper() or None,
            "status": cells[7],
        }
    links = []
    sect = re.split(r"^##\s+Cross-repo links\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(sect) == 2:
        body = re.split(r"^##\s", sect[1], maxsplit=1, flags=re.MULTILINE)[0]
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith(("-", "*")):
                continue
            toks = line.lstrip("-* ").split("—")[0].replace("`", "").split()
            if len(toks) >= 3 and toks[1] in EDGES:
                links.append((toks[0], toks[1], toks[2]))
    return {"audited": audited, "rows": rows, "links": links}


def load_log() -> dict:
    p = repo_log_path()
    return parse_repo_log(p) if p else {}


# ----------------------------------------------------------------------------- live probes (the disk's word)
def probe(root) -> dict:
    """What the disk actually shows, right now — the half of the grade no declaration can fake. Bounded
    and cheap by design (orientation must never turn into a scan): depth-limited mtime walk, file cap,
    volatile dirs skipped (`.claude/` excluded from activity, matching the REPO_LOG audit convention)."""
    out = {"exists": False, "git_present": False, "tests_present": False,
           "state_dir_present": False, "capsule_present": False, "last_activity": None, "files_seen": 0}
    if not root:
        return out
    root = Path(root)
    if not root.is_dir():
        return out
    out["exists"] = True
    out["git_present"] = (root / ".git").exists()
    out["state_dir_present"] = (root / ".claude" / "exocortex").is_dir()
    out["capsule_present"] = capsule_path(root).is_file()
    latest, seen = 0.0, 0
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        if len(d.parts) - base_depth >= _PROBE_DEPTH:
            dirnames[:] = []
        else:
            dirnames[:] = [n for n in dirnames if n not in _SKIP_DIRS]
        if d.name == "tests" or any(f.startswith("test_") and f.endswith(".py") for f in filenames):
            out["tests_present"] = True
        for f in filenames:
            if f in _SKIP_FILES:
                continue
            try:
                latest = max(latest, (d / f).stat().st_mtime)
            except OSError:
                continue
            seen += 1
            if seen >= _PROBE_CAP:
                break
        if seen >= _PROBE_CAP:
            break
    out["files_seen"] = seen
    if latest:
        out["last_activity"] = date.fromtimestamp(latest)
    return out


# ----------------------------------------------------------------------------- merge + grade (reader-side)
def _declared(name: str, capsule: dict | None, log: dict) -> dict:
    """One declared view: capsule fields win over the repo's REPO_LOG row (the capsule is the repo's own,
    fresher claim); the log supplies what the capsule lacks (notably declared last-activity + status prose).
    ``source`` records provenance so the render can say where each assertion came from."""
    row = (log.get("rows") or {}).get(name) or {}
    cap = capsule or {}
    links = [(name, e.get("edge"), e.get("target")) for e in cap.get("links", [])
             if isinstance(e, dict) and e.get("edge") in EDGES and e.get("target")]
    links += [t for t in (log.get("links") or []) if t[0] == name and t not in links]
    status = str(row.get("status") or "")
    superseded = (str(cap.get("canonical_status") or "").lower() == "superseded"
                  or any(e == "superseded_by" for _, e, _ in links)
                  or "supersed" in status.lower())     # the cerebral/intents.py ledger-label convention
    return {
        "name": name,
        "source": ("capsule+repo_log" if cap and row else "capsule" if cap else
                   "repo_log" if row else None),
        "canonical_status": cap.get("canonical_status") or ("superseded" if superseded else None),
        "maturity": cap.get("maturity") or row.get("maturity"),
        "strength": cap.get("strength") or row.get("strength"),
        "tier": cap.get("tier") or row.get("tier"),
        "claim_boundary": cap.get("claim_boundary"),
        "last_reviewed": (_iso(cap.get("last_reviewed")) if cap.get("last_reviewed")
                          else (log.get("audited") if row else None)),   # the estate audit date vouches
                                                                         # only for repos it actually rowed
        "declared_activity": row.get("last_activity"),
        "known_risks": [r for r in cap.get("known_risks", []) if r],
        "status": status,
        "links": links,
        "superseded": superseded,
    }


def grade(declared: dict, probed: dict, today: date) -> tuple[str, list[str]]:
    """The reader's audit of the declaration — deterministic, first match wins, every grade carries its
    reasons (no bare letters). Unknown = nothing declared anywhere; Low = a hard stale/contradiction
    signal; High = fresh review + healthy disk + declaration and disk agree; else Medium."""
    if not declared.get("source"):
        return "Unknown", ["no capsule and no REPO_LOG row — orient by hand (README, commits, tests), "
                           "then seed a capsule"]
    reasons: list[str] = []
    review_age = (today - declared["last_reviewed"]).days if declared.get("last_reviewed") else None
    live = probed.get("last_activity")
    live_age = (today - live).days if live else None
    drift = None
    if live and declared.get("declared_activity"):
        drift = abs((live - declared["declared_activity"]).days)
    low = []
    if probed.get("exists") and not probed.get("git_present"):
        low.append("no git — history unverifiable")
    if declared.get("superseded"):
        low.append("superseded — the canonical head lives elsewhere")
    if declared.get("tier") in ("C", "D") and live_age is not None and live_age > _DORMANT_D:
        low.append(f"Tier {declared['tier']} dormant ({live_age}d since disk activity)")
    if review_age is not None and review_age > _STALE_REVIEW_D:
        low.append(f"review stale ({review_age}d old)")
    if drift is not None and drift > _DRIFT_LIE_D:
        low.append(f"declaration contradicts disk (activity drift {drift}d)")
    if low:
        return "Low", low
    if (review_age is not None and review_age <= _FRESH_REVIEW_D
            and probed.get("git_present") and probed.get("tests_present")
            and (drift is None or drift <= _DRIFT_TOL_D)):
        return "High", [f"reviewed {review_age}d ago; git + tests present"
                        + (f"; drift {drift}d" if drift is not None else "")]
    if not probed.get("exists"):
        reasons.append("root not reachable — live probes unavailable (grade capped)")
    if review_age is None:
        reasons.append("no review date declared")
    elif review_age > _FRESH_REVIEW_D:
        reasons.append(f"review {review_age}d old")
    if probed.get("exists") and not probed.get("tests_present"):
        reasons.append("no tests found at shallow depth")
    if drift is not None and drift > _DRIFT_TOL_D:
        reasons.append(f"activity drift {drift}d")
    return "Medium", reasons or ["orientation useful but partially inferred"]


def orient(name: str, root, log: dict | None = None, today: date | None = None) -> dict:
    """Build the full reader-side view for one repo: declared claim + live probe + audited grade."""
    log = load_log() if log is None else log
    today = today or date.today()
    cap = load_capsule(root) if root else None
    declared = _declared(name, cap, log or {})
    probed = probe(root)
    g, reasons = grade(declared, probed, today)
    return {"name": name, "declared": declared, "probe": probed, "grade": g, "reasons": reasons,
            "log_reachable": bool(log)}


# ----------------------------------------------------------------------------- estate: link symmetry
def symmetry_flags(links: list[tuple]) -> list[str]:
    """One-sided declarations among the mirrored edge pairs (X: `superseded_by` Y without Y: `supersedes`
    X). A flag is a hygiene signal for the estate view — the graph disagrees with itself — never a veto."""
    have = set(links)
    flags = []
    for src, edge, dst in links:
        inv = _INVERSE.get(edge)
        if inv and (dst, inv, src) not in have:
            flags.append(f"{src} {edge} {dst} — counterpart missing ({dst} {inv} {src})")
    return flags


def estate_links(repos: list[dict], log: dict | None = None) -> list[tuple]:
    """Union of every reachable capsule's declared links + the REPO_LOG links section. ``repos`` entries
    need only {'name','root'} (the exporter/MCP repo-record shape)."""
    log = load_log() if log is None else log
    links = list(log.get("links") or [])
    for r in repos:
        root = r.get("root")
        cap = load_capsule(root) if root else None
        for e in (cap or {}).get("links", []):
            if isinstance(e, dict) and e.get("edge") in EDGES and e.get("target"):
                t = (r["name"], e["edge"], e["target"])
                if t not in links:
                    links.append(t)
    return links


# ----------------------------------------------------------------------------- estate: the side-by-side view
def estate_repos(projects_root, log: dict | None = None) -> list[dict]:
    """Every orientable repo: the DEPLOYED fleet (has ``.claude/exocortex/``) UNION the estate-log rows.

    The union is the point (the ``orient_repo`` precedent): the riskiest orientation target is precisely
    the repo with NO earned memory, which a fleet scan alone cannot see. Log-only roots are guessed under
    ``projects_root``; absent → root=None and the probes degrade honestly to a declared-only view."""
    log = load_log() if log is None else log
    proot = Path(projects_root) if projects_root else None
    out: dict[str, dict] = {}
    if proot and proot.is_dir():
        for child in sorted(proot.iterdir()):
            try:
                if (child / ".claude" / "exocortex").is_dir():
                    out[child.name] = {"name": child.name, "root": child}
            except OSError:
                continue
    for name in (log.get("rows") or {}):
        if name not in out:
            out[name] = {"name": name, "root": (proot / name) if proot else None}
    return [out[k] for k in sorted(out)]


def estate(projects_root, log: dict | None = None, today: date | None = None) -> dict:
    """Orient every repo in the estate, side by side, plus the link graph and its symmetry flags.

    Read-only and stdlib-only, like the rest of this module. Cost is one bounded ``probe()`` per repo
    (depth/file-capped) — fine for a CLI, never for the hook hot path."""
    log = load_log() if log is None else log
    today = today or date.today()
    repos = estate_repos(projects_root, log)
    views = [orient(r["name"], r["root"], log, today) for r in repos]
    links = estate_links(repos, log)
    return {"views": views, "links": links, "flags": symmetry_flags(links),
            "log_reachable": bool(log)}


# ----------------------------------------------------------------------------- render (for the MCP tool)
def render(view: dict) -> str:
    d, p = view["declared"], view["probe"]
    g = view["grade"]
    lines = [f"Repo Orientation Capsule — {view['name']}",
             f"  credibility: {g.upper()}  ({'; '.join(view['reasons'])})"]
    ident = " · ".join(x for x in (d.get("canonical_status"), d.get("maturity"), d.get("strength"),
                                   f"Tier {d['tier']}" if d.get("tier") else None) if x)
    if ident:
        lines.append(f"  identity: {ident}")
    lr = d.get("last_reviewed")
    da, la = d.get("declared_activity"), p.get("last_activity")
    lines.append(f"  last reviewed: {lr or '(never declared)'}"
                 f" · activity declared {da or '?'} / observed {la or '?'}")
    if d.get("claim_boundary"):
        lines.append(f"  claim boundary: {d['claim_boundary']}")
    if d.get("status"):
        lines.append(f"  status (REPO_LOG): {d['status']}")
    for r in d.get("known_risks", []):
        lines.append(f"  risk: {r}")
    for _src, edge, dst in d.get("links", []):
        lines.append(f"  link: {edge} -> {dst}")
    lines.append(f"  sources: {d.get('source') or 'none'}"
                 + ("" if view.get("log_reachable") else
                    "  [REPO_LOG not reachable — set EXOCORTEX_REPO_LOG or EXOCORTEX_PROJECTS_ROOT; "
                    "a portable install carries no estate data]"))
    if g in ("Medium", "Low", "Unknown"):
        lines.append("  [rule] Orientation only — never treat this capsule, a README, or prior memory as "
                     "current truth. Grade is not High: RE-ORIENT first (README, recent commits, tests, "
                     "claim ledger), then update the capsule. A capsule never earns tau (ADR-013/019).")
    return "\n".join(lines)


def render_estate(view: dict) -> str:
    """The estate, side by side — every repo's declared identity next to its reader-computed grade.

    Deliberately listed in NAME order, not graded order: the free view shows every organism side by
    side; *ranking the estate by what needs attention* is the paid rollup (``tuner/estate.py``). This
    renderer states each grade and lets the reader judge — it never prioritises."""
    views = sorted(view["views"], key=lambda v: v["name"].lower())
    rows = []
    for v in views:
        d = v["declared"]
        ident = " · ".join(x for x in (d.get("canonical_status"), d.get("maturity"),
                                       f"Tier {d['tier']}" if d.get("tier") else None) if x) or "—"
        rows.append((v["grade"], v["name"], ident,
                     str(d.get("last_reviewed") or "never"),
                     str(v["probe"].get("last_activity") or "?")))
    w = [max(len(r[i]) for r in ([("grade", "repo", "identity", "reviewed", "activity")] + rows))
         for i in range(5)]
    out = [f"Estate orientation — {len(views)} repo(s) (ADR-019; orientation only, never memory)", ""]
    hdr = ("grade", "repo", "identity", "reviewed", "activity")
    out.append("  " + "  ".join(h.ljust(w[i]) for i, h in enumerate(hdr)))
    out.append("  " + "  ".join("-" * w[i] for i in range(5)))
    for r in rows:
        out.append("  " + "  ".join(str(r[i]).ljust(w[i]) for i in range(5)))

    counts = {}
    for v in views:
        counts[v["grade"]] = counts.get(v["grade"], 0) + 1
    out += ["", "  grades: " + " · ".join(f"{k} {counts[k]}" for k in ("High", "Medium", "Low", "Unknown")
                                          if k in counts)]
    if view["flags"]:
        out += ["", f"  link hygiene — {len(view['flags'])} one-sided edge(s) (a flag, never a veto):"]
        out += [f"    - {f}" for f in view["flags"]]
    if not view.get("log_reachable"):
        out += ["", "  [REPO_LOG not reachable — set EXOCORTEX_REPO_LOG or EXOCORTEX_PROJECTS_ROOT; a "
                    "portable install carries no estate data. Grades cap lower without an estate audit — "
                    "that is the honest answer, not a defect (ADR-019).]"]
    if any(v["grade"] != "High" for v in views):
        out += ["", "  [rule] Below High → RE-ORIENT before acting on that repo (README, recent commits, "
                    "tests, claim ledger), then update its capsule. Orientation never earns tau "
                    "(ADR-013/019)."]
    return "\n".join(out)


# ----------------------------------------------------------------------------- seeder (the ONE writer)
_SKELETON = {"capsule_version": 1, "name": None, "canonical_status": None, "maturity": None,
             "strength": None, "tier": None, "claim_boundary": None, "last_reviewed": None,
             "known_risks": [], "links": []}


def skeleton(name: str) -> dict:
    d = json.loads(json.dumps(_SKELETON))
    d["name"] = name
    return d


def seed(projects_root, log: dict | None = None, force: bool = False) -> list[str]:
    """One-shot: derive an initial capsule.json for every DEPLOYED repo (has ``.claude/exocortex/``) under
    ``projects_root`` from its REPO_LOG row + links. Explicit CLI only — the MCP tool and the exporter
    never call this. Existing capsules are kept unless --force (hand edits outrank the seed)."""
    log = load_log() if log is None else log
    written = []
    proot = Path(projects_root)
    for name, row in (log.get("rows") or {}).items():
        root = proot / name
        if not (root / ".claude" / "exocortex").is_dir():
            continue
        cp = capsule_path(root)
        if cp.exists() and not force:
            continue
        status = str(row.get("status") or "").lower()
        cap = skeleton(name)
        cap.update({
            "canonical_status": ("superseded" if "supersed" in status
                                 else "mirror" if "mirror" in status else "canonical"),
            "maturity": row.get("maturity"), "strength": row.get("strength"), "tier": row.get("tier"),
            "claim_boundary": "docs/CLAIMS.md" if (root / "docs" / "CLAIMS.md").is_file() else None,
            "last_reviewed": (log.get("audited") or date.today()).isoformat(),
            "links": [{"edge": e, "target": dst} for src, e, dst in (log.get("links") or [])
                      if src == name],
        })
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(cap, indent=2) + "\n", encoding="utf-8")
        written.append(str(cp))
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="exocortex.orient",
                                 description="Repo Orientation Capsule (ADR-019): view a repo's capsule "
                                             "+ reader-computed credibility grade, or --seed initial "
                                             "capsules from the estate REPO_LOG.")
    ap.add_argument("name", nargs="?", help="repo to orient on (prints the rendered capsule)")
    ap.add_argument("--root", default=None, help="repo root (default: <projects-root>/<name>)")
    ap.add_argument("--projects-root", default=os.environ.get("EXOCORTEX_PROJECTS_ROOT"),
                    help="estate parent dir (default: EXOCORTEX_PROJECTS_ROOT)")
    ap.add_argument("--estate", action="store_true",
                    help="orient the whole estate side by side (deployed fleet + REPO_LOG rows)")
    ap.add_argument("--seed", action="store_true", help="write initial capsule.json files for deployed "
                                                        "repos from REPO_LOG rows (the one write path)")
    ap.add_argument("--force", action="store_true", help="with --seed: overwrite existing capsules")
    a = ap.parse_args(argv)
    if a.projects_root:
        os.environ.setdefault("EXOCORTEX_PROJECTS_ROOT", a.projects_root)
    log = load_log()
    if a.estate:
        if not a.projects_root and not log:
            print("--estate needs --projects-root (or EXOCORTEX_PROJECTS_ROOT), or a reachable REPO_LOG")
            return 2
        print(render_estate(estate(a.projects_root, log)))
        return 0
    if a.seed:
        if not a.projects_root:
            print("--seed needs --projects-root (or EXOCORTEX_PROJECTS_ROOT)")
            return 2
        if not log:
            print("REPO_LOG not reachable — nothing to seed from")
            return 2
        written = seed(a.projects_root, log, force=a.force)
        print(f"seeded {len(written)} capsule(s):")
        for w in written:
            print(f"  {w}")
        return 0
    if not a.name:
        ap.print_help()
        return 2
    root = Path(a.root) if a.root else (Path(a.projects_root) / a.name if a.projects_root else None)
    print(render(orient(a.name, root, log)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
