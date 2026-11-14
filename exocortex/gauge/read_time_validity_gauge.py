"""Read-Time Validity Gauge — does served memory cite repo artifacts that no longer exist? (avenue 3 / R4b)

Content identity already invalidates an EDITED or DELETED note (its id leaves the digest), but an unchanged
note whose cited path has since vanished is still served — τ-verified or as exploration. The procedural
splice is verb-altitude and can only go stale through a verb that implies an artifact (`make` → Makefile,
`./run.sh` → `bash:run.sh`). This gauge snapshots both lanes NOW:

  * Lane P census — artifact-bound verb nodes in each servable class's splice, and whether the artifact exists;
  * τ-floor census — servable classes whose strongest readout edge sits below the prune floor;
  * D1 (exploit) — τ-credited notes present in today's digest that cite a vanished path;
  * D2 (explore) — offer-weighted share of served explore blocks that cite a vanished path.

A citation is VANISHED only if no current file matches it and some ever-tracked (git) path does; anything
else unmatched is UNRESOLVED and never counted. Frozen protocol: ``results/read_time_validity_v1/PREREG.md``.
Read-only (the vault is re-digested in memory; no cache is written), stdlib + git, deterministic. Emits
numbers only; ``--audit-sheet`` writes the precision-audit sample (it quotes note text — keep it private).

  python -m exocortex.gauge.read_time_validity_gauge --repo ROOT --label L [--repo ...] [--json]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import posixpath
import random
import re
import subprocess
import time
from pathlib import Path

PRUNE = 0.05                                       # the splice floor (`node_tau`, `colony.PRUNE`)
HALFLIFE_S = 30.0 * 86400.0                        # PREREG §4: recency readout, 30-day half-life
TOP_K, MAX_PATH, MIN_DEPOSITS = 8, 6, 2
EVALUABLE = 30                                     # PREREG §5
V_PASS, V_NULL, Q_PASS = 0.05, 0.01, 0.70
AUDIT_PER_STORE, AUDIT_SEED = 20, 20261026
_SEP = "\t"

EXT = frozenset("py md json jsonl toml yaml yml txt sh ps1 bat cmd js mjs ts tsx html css csv ini cfg ipynb "
                "svg tex bib rs go c h cpp hpp sql xml".split())
SCRIPT_EXT = frozenset("sh bash ps1 bat cmd py js mjs ts rb pl".split())
MANIFESTS = {
    "make": ("makefile", "gnumakefile"), "npm": ("package.json",), "npx": ("package.json",),
    "yarn": ("package.json",), "pnpm": ("package.json",), "cargo": ("cargo.toml",), "go": ("go.mod",),
    "mvn": ("pom.xml",), "gradle": ("build.gradle", "build.gradle.kts"),
    "gradlew": ("gradlew", "build.gradle", "build.gradle.kts"), "tox": ("tox.ini",),
    "poetry": ("pyproject.toml",), "just": ("justfile", ".justfile"),
    "docker-compose": ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"),
    "terraform": (".tf",), "nox": ("noxfile.py",),
}
_PRUNE_DIRS = frozenset({".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
                         ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox"})

_TICK = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\]\(([^)\s]+)\)")
_MOD = re.compile(r"-m\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)")
_LINE = re.compile(r":L?\d+(?:-L?\d+)?$")
_DROP = frozenset("*?[]{}<>|=$%@")


# ---- citation extraction (PREREG §3) ----
def _norm(tok: str) -> str | None:
    t = tok.strip().replace("\\", "/").strip("'\"`")
    t = t.lstrip("([<").rstrip(")]>,;:!?'\".")
    if not t or "://" in t:
        return None
    t = t.split("::", 1)[0].split("#", 1)[0]
    t = _LINE.sub("", t).rstrip(":")
    while t.startswith("./"):
        t = t[2:]
    if (not t or t.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", t) or "..." in t
            or any(c in _DROP for c in t) or any(c.isspace() for c in t)):
        return None
    base = t.rstrip("/").rsplit("/", 1)[-1]
    ext = base.rsplit(".", 1)[1].lower() if "." in base.strip(".") else ""
    if "/" in t:
        return t if (ext in EXT or t.endswith("/")) else None
    return t if ext in EXT else None


def extract_citations(text: str) -> list:
    """Each citation as a tuple of candidate spellings (a module yields file + package candidates)."""
    out: list = []
    for span in _TICK.findall(text or ""):
        for tok in span.split():
            p = _norm(tok)
            if p:
                out.append((p,))
    for target in _LINK.findall(text or ""):
        p = _norm(target)
        if p:
            out.append((p,))
    for mod in _MOD.findall(text or ""):
        stem = mod.replace(".", "/")
        out.append((stem + ".py", stem + "/"))
    return list(dict.fromkeys(out))


# ---- the repo index (PREREG §3) ----
def _suffixes(rel: str) -> list:
    parts = rel.lower().strip("/").split("/")
    return ["/".join(parts[i:]) for i in range(len(parts))]


def _git_paths(root: Path) -> list:
    out: list = []
    for args in (["log", "--all", "--name-only", "--format="], ["ls-files"]):
        try:
            proc = subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(root), *args],
                                  capture_output=True, timeout=180, stdin=subprocess.DEVNULL)
            if proc.returncode == 0:
                out.extend(ln for ln in proc.stdout.decode("utf-8", errors="replace").splitlines() if ln.strip())
        except Exception:
            continue
    return out


class RepoIndex:
    """Suffix sets (lower-cased; Windows paths are case-insensitive) of what exists now and what git ever tracked."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.cur: set = set()
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS]
            rel_dir = Path(dirpath).relative_to(self.root).as_posix()
            rel_dir = "" if rel_dir == "." else rel_dir
            if rel_dir:
                self.cur.update(_suffixes(rel_dir))
            for fn in filenames:
                self.cur.update(_suffixes(f"{rel_dir}/{fn}" if rel_dir else fn))
        self.ever: set = set()
        for rel in _git_paths(self.root):
            rel = rel.strip().strip('"')
            self.ever.update(_suffixes(rel))
            parent = posixpath.dirname(rel)
            while parent:
                self.ever.update(_suffixes(parent))
                parent = posixpath.dirname(parent)

    def classify(self, cands, doc_dir: str = "") -> str | None:
        """present | vanished | unresolved; None when every candidate resolves outside the repo (dropped)."""
        keys: list = []
        for c in cands:
            for base in ([doc_dir, ""] if doc_dir else [""]):
                n = posixpath.normpath(posixpath.join(base, c.rstrip("/")))
                if n in (".", "") or n == ".." or n.startswith("../"):
                    continue
                keys.append(n)
        if not keys:
            return None
        keys = list(dict.fromkeys(keys))
        if any(k.lower() in self.cur or (self.root / k).exists() for k in keys):
            return "present"
        if any(k.lower() in self.ever for k in keys):
            return "vanished"
        return "unresolved"

    def has_ext(self, ext: str, ever: bool = False) -> bool:
        return any(s.endswith(ext) and "/" not in s for s in (self.ever if ever else self.cur))


# ---- procedural lane: census (PREREG §4) ----
def _eff(tau: dict, meta: dict, now: float) -> dict:
    out = {}
    for k, w in tau.items():
        ts = (meta.get(k) or {}).get("ts")
        age = now - float(ts) if ts else 0.0
        out[k] = w * (0.5 ** (age / HALFLIFE_S) if age > 0 else 1.0)
    return out


def _dominant(eff: dict) -> list:
    """``Colony.dominant_path`` over the readout τ."""
    if not eff:
        return []
    w = {tuple(k.split(_SEP)): v for k, v in eff.items()}
    cur = max(w, key=lambda e: w[e])[0]
    path = [cur]
    while len(path) < MAX_PATH:
        outs = [(b, x) for (a, b), x in w.items() if a == cur and b not in path]
        if not outs:
            break
        cur = max(outs, key=lambda x: x[1])[0]
        path.append(cur)
    return path


def artifact_of(node: str):
    """('manifest', names) | ('script', (basename,)) | None for a non-artifact-bound node."""
    if not node.startswith(("bash:", "ps:")):
        return None
    verb = node.split(":", 1)[1].strip()
    if verb.lower() in MANIFESTS:
        return "manifest", MANIFESTS[verb.lower()]
    if "." in verb and verb.rsplit(".", 1)[1].lower() in SCRIPT_EXT:
        return "script", (verb,)
    return None


def _artifact_status(idx: RepoIndex, kind_names) -> str:
    _, names = kind_names
    if names == (".tf",):
        return "present" if idx.has_ext(".tf") else ("vanished" if idx.has_ext(".tf", ever=True) else "unresolved")
    states = [idx.classify((n,)) for n in names]
    if "present" in states:
        return "present"
    return "vanished" if "vanished" in states else "unresolved"


def _colonies(state: Path) -> list:
    out = []
    for f in sorted(state.glob("colony_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and isinstance(d.get("tau"), dict):
            out.append(d)
    return out


def procedural_census(cols: list, idx: RepoIndex, now: float) -> dict:
    servable = floor = bound_classes = 0
    status = collections.Counter()
    for d in cols:
        tau = d.get("tau") or {}
        if int(d.get("deposits", 0) or 0) < MIN_DEPOSITS or not tau:
            continue
        servable += 1
        eff = _eff(tau, d.get("meta") or {}, now)
        if max(eff.values()) < PRUNE:
            floor += 1
        nodes = set(_dominant(eff))
        for k, _ in sorted(eff.items(), key=lambda kv: -kv[1])[:TOP_K]:
            nodes.update(k.split(_SEP))
        bound = [(n, artifact_of(n)) for n in sorted(nodes) if artifact_of(n)]
        if bound:
            bound_classes += 1
        for _, ka in bound:
            status[_artifact_status(idx, ka)] += 1
    return {"servable_classes": servable, "classes_with_artifact_bound_node": bound_classes,
            "artifact_nodes": dict(status),
            "tau_floor_classes": floor,
            "tau_floor_share": round(floor / servable, 4) if servable else None}


# ---- declarative lanes (PREREG §4) ----
def _config(root: Path) -> dict:
    try:
        c = json.loads((root / "exocortex_config.json").read_text(encoding="utf-8"))
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def credited_notes(cols: list) -> dict:
    """note id → max over classes of its summed incident raw τ, kept when ≥ the splice floor."""
    from exocortex.wiki.digest import is_note_id
    best: dict = {}
    for d in cols:
        per: dict = collections.defaultdict(float)
        for k, w in (d.get("tau") or {}).items():
            for nid in set(k.split(_SEP)):
                if is_note_id(nid):
                    per[nid] += float(w)
        for nid, w in per.items():
            best[nid] = max(best.get(nid, 0.0), w)
    return {n: w for n, w in best.items() if w >= PRUNE}


def digest_now(root: Path, decl: dict) -> list:
    """Today's digest, in memory (never writes the wiki cache)."""
    from exocortex.wiki.store import _digest_vault, _md_files
    vault = Path(decl.get("vault_path") or root)
    files = _md_files(vault, str(decl.get("ingest", "all")), exclude=list(decl.get("exclude") or []))
    return _digest_vault(vault, files)


def _block_scan(node, idx: RepoIndex, tally: collections.Counter) -> list:
    doc_dir = posixpath.dirname(node.id.partition("#")[0])
    vanished = []
    for cands in extract_citations(node.text):
        st = idx.classify(cands, doc_dir)
        if st is None:
            continue
        tally[st] += 1
        if st == "vanished":
            vanished.append(cands[0])
    return vanished


def declarative_lanes(cols: list, idx: RepoIndex, nodes: list, offers: dict) -> tuple:
    by_id = {n.id: n for n in nodes}
    by_doc: dict = collections.defaultdict(list)
    for n in nodes:
        by_doc[n.id.partition("#")[0]].append(n)
    scan: dict = {}
    t0 = collections.Counter()
    for n in nodes:
        scan[n.id] = _block_scan(n, idx, t0)
    flagged: list = []

    cred = credited_notes(cols)
    d1 = [nid for nid in cred if nid in by_id]
    v1 = [nid for nid in d1 if scan[nid]]
    t1 = collections.Counter()
    for nid in d1:
        _block_scan(by_id[nid], idx, t1)
    wsum = sum(cred[n] for n in d1)
    flagged += [(nid, c) for nid in v1 for c in scan[nid]]
    D1 = {"credited_ids": len(cred), "present": len(d1), "orphans": len(cred) - len(d1),
          "evaluable": len(d1) >= EVALUABLE, "citations": dict(t1),
          "V1": round(len(v1) / len(d1), 4) if d1 else None,
          "V1_tau_weighted": round(sum(cred[n] for n in v1) / wsum, 4) if wsum else None}

    present_docs = {d: c for d, c in offers.items() if d in by_doc}
    t2 = collections.Counter()
    num = up = 0.0
    for doc, cnt in present_docs.items():
        blocks = by_doc[doc]
        bad = [b for b in blocks if scan[b.id]]
        for b in blocks:
            _block_scan(b, idx, t2)
        num += cnt * len(bad) / len(blocks)
        up += cnt * bool(bad)
        flagged += [(b.id, c) for b in bad for c in scan[b.id]]
    tot = sum(present_docs.values())
    D2 = {"offered_docs": len(offers), "present_docs": len(present_docs),
          "gone_docs": len(offers) - len(present_docs),
          "gone_offers": sum(c for d, c in offers.items() if d not in by_doc),
          "evaluable": len(present_docs) >= EVALUABLE, "citations": dict(t2),
          "V2": round(num / tot, 4) if tot else None, "U2": round(up / tot, 4) if tot else None}

    D0 = {"blocks": len(nodes), "citations": dict(t0),
          "share_blocks_citing_vanished": round(sum(1 for v in scan.values() if v) / len(nodes), 4) if nodes else None}
    return {"D1": D1, "D2": D2, "D0": D0}, list(dict.fromkeys(flagged)), by_id


def run_store(root: Path, now: float | None = None) -> tuple:
    root = Path(root)
    now = time.time() if now is None else now
    state = root / ".claude" / "exocortex"
    cols = _colonies(state)
    idx = RepoIndex(root)
    out = {"procedural": procedural_census(cols, idx, now), "declarative": None}
    cfg = _config(root)
    decl = cfg.get("declarative") or {}
    live = str(decl.get("mode", "off")).lower() == "live"
    explore = int(decl.get("explore_budget", 0) or 0)
    serving = live and (explore > 0 or bool(credited_notes(cols)))
    out["declarative_serving"] = serving
    flagged, by_id = [], {}
    if serving:
        try:
            offers = json.loads((state / "wiki_offers.json").read_text(encoding="utf-8")) if explore > 0 else {}
        except Exception:
            offers = {}
        out["declarative"], flagged, by_id = declarative_lanes(cols, idx, digest_now(root, decl),
                                                               {str(k): int(v) for k, v in offers.items()})
    return out, flagged, by_id


def passes(store: dict) -> bool:
    d = store.get("declarative") or {}
    return any((d.get(k) or {}).get("evaluable") and (d[k].get(v) or 0) >= V_PASS
               for k, v in (("D1", "V1"), ("D2", "V2")))


def verdict(stores: dict, precision: float | None = None) -> dict:
    """PREREG §5. ``precision`` = the hand-audited Q (None until the audit is done)."""
    pops = []
    for s in stores.values():
        d = s.get("declarative") or {}
        pops += [d[k].get(v) or 0.0 for k, v in (("D1", "V1"), ("D2", "V2")) if (d.get(k) or {}).get("evaluable")]
    passing = [lab for lab, s in stores.items() if passes(s)]
    if len(passing) >= 2 and precision is None:
        return {"disposition": None, "pending": "precision audit", "passing": passing, "evaluable_populations": len(pops)}
    if len(passing) >= 2 and precision is not None and precision >= Q_PASS:
        disp = 1
    elif pops and all(v < V_NULL for v in pops):
        disp = -1
    else:
        disp = 0
    return {"disposition": disp, "passing": passing, "evaluable_populations": len(pops), "precision": precision}


def audit_sample(flagged: list, k: int = AUDIT_PER_STORE, seed: int = AUDIT_SEED) -> list:
    pool = sorted(flagged)
    return pool if len(pool) <= k else sorted(random.Random(seed).sample(pool, k))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-Time Validity Gauge — served memory citing vanished artifacts")
    ap.add_argument("--repo", action="append", default=[], help="repo root (repeatable)")
    ap.add_argument("--label", action="append", default=[], help="label per --repo")
    ap.add_argument("--now", type=float, default=None, help="readout epoch (default: now)")
    ap.add_argument("--precision", type=float, default=None, help="hand-audited Q (PREREG §5)")
    ap.add_argument("--audit-sheet", default=None, help="write the PRIVATE precision-audit sample here")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    labels = a.label + [f"store{i}" for i in range(len(a.label), len(a.repo))]
    stores, sheet = {}, []
    for lab, root in zip(labels, a.repo):
        stores[lab], flagged, by_id = run_store(Path(root), a.now)
        if passes(stores[lab]):
            for nid, cit in audit_sample(flagged):
                sheet.append({"store": lab, "note": nid, "citation": cit, "text": by_id[nid].text})
    out = {"stores": stores, "verdict": verdict(stores, a.precision)}
    if a.audit_sheet:
        Path(a.audit_sheet).write_text(json.dumps(sheet, indent=1, ensure_ascii=False), encoding="utf-8")
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for lab, s in stores.items():
            print(lab, json.dumps(s))
        print("verdict", out["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
