"""Intent register — harvest DECLARED intents from a research vault, read-only and fail-open.

The Cerebral Substrate's *intent register* tracks research threads as open loops with a TTL: an intent
opens and stays OPEN until its intent closes; one still OPEN past its ``reasonable_timeframe`` is a
"crack-faller" (the resurrection target). This module only HARVESTS what the PI already declared — Markdown
checkboxes, task-status / manifest files, and structured ``ledger.json`` decision labels — it never infers
an intent from prose and never judges an outcome (valence is read off the record; ADR-001).

Pure-stdlib, numpy-free, fail-open (any per-file error → skip; the harvest never raises). ``spaCy`` is an
OPTIONAL enrichment for the ``(action, anticipated_result)`` decomposition and falls open to a regex
extractor when absent — mirroring the embedding-classifier fail-open in ``exocortex/hook.py``.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

# ------------------------------------------------------------------ intent model
OPEN, CLOSED = "OPEN", "CLOSED"

# Kind → reasonable timeframe (days), seeded from TAO's own cadence evidence (the MAINTENANCE_LOG
# "7-day freshness window", ~3–7d snapshot cadence, patent horizons). Later self-calibrated from the PI's
# recorded closure-time distribution. Overridable per-run.
TIMEFRAME_DAYS = {
    "issue": 30,          # ISSUES.md — paper/manuscript items
    "filing": 90,         # FILING_CHECKLIST.md — patent filings run long
    "task_status": 14,    # task_status_*.md — active work items
    "manifest": 21,       # *TASK_MANIFEST*.md — planned task batches
    "ledger": 30,         # ledger.json decision entries
    "_default": 30,
}

# Recorded ledger decision label → (lifecycle, valence). Valence: +1 confirmed · 0 inconclusive/superseded
# · -1 falsified. Unknown labels default to OPEN/None (never guessed). Matched as a lowercase substring so
# schema drift ("validated_v2") still lands. Consequence-sourced: we read the recorded decision, never judge.
_LEDGER_LABELS = [
    ("falsif", CLOSED, -1), ("refut", CLOSED, -1), ("negat", CLOSED, -1), ("ruled_out", CLOSED, -1),
    ("confirm", CLOSED, 1), ("validat", CLOSED, 1), ("verifi", CLOSED, 1), ("accepted", CLOSED, 1),
    ("supersed", CLOSED, 0), ("inconclusive", CLOSED, 0), ("abandon", CLOSED, 0), ("null_result", CLOSED, 0),
    ("candidate", OPEN, None), ("pending", OPEN, None), ("rerun", OPEN, None), ("open", OPEN, None),
    ("in_progress", OPEN, None), ("todo", OPEN, None),
]

# Filename globs we harvest (targeted — NOT every .md in a 6,900-file vault).
CHECKBOX_PATTERNS = ("ISSUES.md", "FILING_CHECKLIST.md", "task_status_*.md", "*TASK_MANIFEST*.md")


@dataclass
class Intent:
    id: str
    description: str
    source: str                       # "relpath#Lnn"
    repo: str
    kind: str                         # issue|filing|task_status|manifest|ledger
    lifecycle: str                    # OPEN|CLOSED
    valence: "int | None"            # None while OPEN/unknown; +1/0/-1 at recorded closure
    opened_at: "str | None"          # ISO date (YYYY-MM-DD)
    last_activity: "str | None"
    reasonable_timeframe_days: int
    action: "str | None"
    anticipated_result: "str | None"
    executable: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ small helpers (fail-open)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_FRONT_DATE_RE = re.compile(r"(?im)last[ _]updated[^\n\d]{0,15}(\d{4}-\d{2}-\d{2})")
_CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.*\S)\s*$")


def _iso_date(s: str) -> "str | None":
    """Normalize any ISO-ish timestamp to a ``YYYY-MM-DD`` date, or None."""
    if not s:
        return None
    m = _DATE_RE.search(str(s))
    return m.group(1) if m else None


_NONEXEC_SEE_RE = re.compile(r"^\s*see\s+\S+\.md", re.IGNORECASE)   # leading "See <doc>.md" pointer


def is_executable(desc: str) -> bool:
    """Conservative (precision-biased) 'is this a concrete executable work-item?' filter for the harvest.
    Drops ONLY high-confidence non-tasks — a trailing ``?`` (a question / unresolved decision) or a leading
    ``See <doc>.md`` pointer. It deliberately does NOT try to catch imperative-phrased decisions
    ("Choose target journal") or ``X: PENDING`` receipt lines: those are *not* mechanically separable from
    real tasks without false-dropping ("Check A vs B", "arXiv posting: PENDING" are genuine) — that
    separation is semantic, left to a future classifier or the PI (empirically shown by the v1 labels)."""
    d = (desc or "").strip()
    if not d:
        return False
    if d.endswith("?"):
        return False
    if _NONEXEC_SEE_RE.match(d):
        return False
    return True


def _clean_desc(text: str) -> str:
    """Strip Markdown emphasis / strike / trailing ✓-notes from a checkbox line's text."""
    t = re.sub(r"~~(.*?)~~", r"\1", text)          # strike-through
    t = t.replace("**", "").replace("`", "")
    t = re.split(r"\s+✓|\s+—\s+✓", t)[0]           # drop trailing "✓ done" notes
    t = re.sub(r"\s{2,}", " ", t).strip(" .—-")
    return t.strip()


def _git_commit_date(vault: Path, rel: str, cache: dict) -> "str | None":
    """Last commit date of a tracked file (``git log -1 --format=%cI``). Bounded + fail-open → None.
    Cached per relpath so each file is dated at most once."""
    if rel in cache:
        return cache[rel]
    out = None
    try:
        proc = subprocess.run(
            ["git", "-C", str(vault), "log", "-1", "--format=%cI", "--", rel],
            capture_output=True, timeout=5.0,
        )
        if proc.returncode == 0:
            out = _iso_date(proc.stdout.decode("utf-8", errors="replace").strip())
    except Exception:
        out = None
    cache[rel] = out
    return out


def _file_date(path: Path, vault: Path, rel: str, head: str, cache: dict) -> "str | None":
    """Resolve a file's 'last activity' date: frontmatter ``Last Updated`` → git commit → mtime."""
    m = _FRONT_DATE_RE.search(head)
    if m:
        return m.group(1)
    g = _git_commit_date(vault, rel, cache)
    if g:
        return g
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date().isoformat()
    except Exception:
        return None


def _stable_id(repo: str, source: str, desc: str) -> str:
    return hashlib.blake2b(f"{repo}|{source}|{desc}".encode("utf-8"), digest_size=8).hexdigest()


def _kind_for(name: str) -> str:
    n = name.lower()
    if n == "issues.md":
        return "issue"
    if n == "filing_checklist.md":
        return "filing"
    if n.startswith("task_status"):
        return "task_status"
    if "task_manifest" in n:
        return "manifest"
    return "_default"


# ------------------------------------------------------------------ optional (action, result) parse
_SPACY = {"nlp": None, "tried": False}
_RESULT_RE = re.compile(r"(?:→|->|\bso that\b|\bin order to\b|\bto\b)\s+(.*\S)", re.IGNORECASE)
_VERB_RE = re.compile(r"^\s*([A-Za-z][A-Za-z-]+)")


def _load_spacy():
    """Load ``en_core_web_sm`` once; None if spaCy/model absent (never raises). Optional enrichment only."""
    if not _SPACY["tried"]:
        _SPACY["tried"] = True
        try:
            import spacy  # type: ignore
            _SPACY["nlp"] = spacy.load("en_core_web_sm")
        except Exception:
            _SPACY["nlp"] = None
    return _SPACY["nlp"]


def parse_action_result(text: str) -> tuple:
    """``(action, anticipated_result)`` for an intent's text — STRUCTURE, never judge. spaCy when available
    (root verb + purpose/result clause); else a regex fallback. ``anticipated_result`` is left None rather
    than hallucinated when no result clause is present."""
    text = (text or "").strip()
    if not text:
        return None, None
    nlp = _load_spacy()
    if nlp is not None:
        try:
            doc = nlp(text)
            action = None
            for tok in doc:
                if tok.pos_ == "VERB":
                    action = tok.lemma_.lower()
                    break
            if action is None:
                action = doc[0].lemma_.lower() if len(doc) else None
            mr = _RESULT_RE.search(text)
            result = mr.group(1).strip() if mr else None
            return action, result
        except Exception:
            pass
    # regex fallback (spaCy absent): leading token as action, arrow/purpose clause as result (or None)
    mv = _VERB_RE.match(text)
    action = mv.group(1).lower() if mv else None
    mr = _RESULT_RE.search(text)
    result = mr.group(1).strip() if mr else None
    return action, result


# ------------------------------------------------------------------ harvest: markdown checkboxes
def _iter_files(vault: Path):
    """Targeted files only (git-tracked preferred, rglob fallback) matching CHECKBOX_PATTERNS."""
    tracked = _git_tracked(vault)
    if tracked is not None:
        pool = tracked
    else:
        pool = sorted(p for p in vault.rglob("*.md") if p.is_file())
    for p in pool:
        if any(_match(p.name, pat) for pat in CHECKBOX_PATTERNS):
            yield p


def _match(name: str, pattern: str) -> bool:
    from fnmatch import fnmatch
    return fnmatch(name, pattern)


def _git_tracked(vault: Path) -> "list | None":
    """Git-tracked ``*.md`` (respects .gitignore, excludes untracked/submodule noise). None → fall open."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(vault), "ls-files", "-z", "--", "*.md"],
            capture_output=True, timeout=10.0,
        )
        if proc.returncode != 0:
            return None
        rels = proc.stdout.decode("utf-8", errors="replace").split("\0")
        return sorted(vault / r for r in rels if r.endswith(".md") and (vault / r).is_file())
    except Exception:
        return None


def _git_dates_bulk(vault: Path, rels: list) -> dict:
    """ONE ``git log --name-only`` history walk → {rel: last-commit ISO date} for every wanted rel.

    D1b (Desktop audit): the per-file ``git log -1`` fallback costs one subprocess PER matched file —
    many checklist files × cold git on a large vault = minutes of background scan. Newest-first walk:
    the first commit that names a file is its last-touch date. Fail-open → {} (the per-file path stays
    as the fallback for anything missed)."""
    want = {str(r).replace("\\", "/") for r in rels}
    if not want:
        return {}
    try:
        spec = sorted(want)
        cmd = ["git", "-C", str(vault), "log", "--format=%x00%cI", "--name-only", "--"]
        if sum(len(s) for s in spec) < 20000:               # pathspec-limit the walk when it fits the
            cmd += spec                                     # command line; else walk all and filter here
        proc = subprocess.run(cmd, capture_output=True, timeout=30.0)
        if proc.returncode != 0:
            return {}
        out: dict = {}
        cur = None
        for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
            if line.startswith("\x00"):
                cur = _iso_date(line[1:].strip())
            elif line.strip() and cur:
                rel = line.strip().replace("\\", "/")
                if rel in want and rel not in out:
                    out[rel] = cur
                    if len(out) == len(want):
                        break
        return out
    except Exception:
        return {}


def harvest_checkboxes(vault: Path, date_cache: dict) -> list:
    """Markdown ``- [ ]`` / ``- [x]`` items in the targeted files → Intents. ``[ ]`` = OPEN (valence None);
    ``[x]`` = CLOSED (valence +1, a completed task). Dates: inline (line) → file (frontmatter/git/mtime).
    The date cache is bulk-seeded with ONE git history walk up front (D1b) — the per-file ``git log -1``
    only runs for files the walk missed."""
    repo = vault.name
    out: list = []
    files = list(_iter_files(vault))
    if files and not date_cache:
        date_cache.update(_git_dates_bulk(vault, [_relpath(p, vault) for p in files]))
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = _relpath(path, vault)
        head = "\n".join(text.splitlines()[:40])
        fdate = _file_date(path, vault, rel, head, date_cache)
        kind = _kind_for(path.name)
        tf = TIMEFRAME_DAYS.get(kind, TIMEFRAME_DAYS["_default"])
        for i, line in enumerate(text.splitlines(), start=1):
            m = _CHECKBOX_RE.match(line)
            if not m:
                continue
            checked = m.group(1).lower() == "x"
            desc = _clean_desc(m.group(2))
            if not desc:
                continue
            source = f"{rel}#L{i}"
            inline = _iso_date(line)
            last = inline or fdate
            action, result = parse_action_result(desc)
            out.append(Intent(
                id=_stable_id(repo, source, desc), description=desc, source=source, repo=repo, kind=kind,
                lifecycle=(CLOSED if checked else OPEN), valence=(1 if checked else None),
                opened_at=fdate, last_activity=last, reasonable_timeframe_days=tf,
                action=action, anticipated_result=result, executable=is_executable(desc)))
    return out


# ------------------------------------------------------------------ harvest: structured ledgers
def _label_map(label: str) -> tuple:
    lab = str(label or "").lower()
    for key, life, val in _LEDGER_LABELS:
        if key in lab:
            return life, val
    return OPEN, None       # unknown recorded label → OPEN, unjudged


def harvest_ledgers(vault: Path) -> list:
    """Structured ``ledger.json`` entries (arrays of objects with ``decision_label`` + ``created_at_utc``)
    → Intents with a consequence-sourced valence. Read-only, fail-open."""
    repo = vault.name
    out: list = []
    pool = _git_tracked_json(vault)
    for path in pool:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        rows = data if isinstance(data, list) else data.get("entries") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            continue
        rel = _relpath(path, vault)
        for j, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            label = row.get("decision_label") or row.get("claim_boundary") or ""
            desc = str(row.get("use_case_id") or row.get("id") or row.get("next_step") or "").strip()
            if not desc:
                continue
            life, val = _label_map(label)
            date = _iso_date(row.get("created_at_utc") or row.get("created_at") or "")
            source = f"{rel}#{j}"
            action, result = parse_action_result(str(row.get("next_step") or desc))
            out.append(Intent(
                id=_stable_id(repo, source, desc), description=f"{desc} [{label}]", source=source, repo=repo,
                kind="ledger", lifecycle=life, valence=val, opened_at=date, last_activity=date,
                reasonable_timeframe_days=TIMEFRAME_DAYS["ledger"], action=action, anticipated_result=result))
    return out


def _git_tracked_json(vault: Path) -> list:
    """Tracked ``ledger.json`` files (fall open to rglob)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(vault), "ls-files", "-z", "--", "*ledger*.json"],
            capture_output=True, timeout=10.0,
        )
        if proc.returncode == 0:
            rels = proc.stdout.decode("utf-8", errors="replace").split("\0")
            got = sorted(vault / r for r in rels if r.endswith(".json") and (vault / r).is_file())
            if got:
                return got
    except Exception:
        pass
    return sorted(p for p in vault.rglob("*ledger*.json") if p.is_file())


def _relpath(path: Path, vault: Path) -> str:
    try:
        return path.relative_to(vault).as_posix()
    except Exception:
        return path.name


# ------------------------------------------------------------------ top-level
def harvest(vault) -> list:
    """All declared intents in the vault (checkboxes + structured ledgers). Read-only, fail-open."""
    v = Path(vault)
    if not v.is_dir():
        return []
    date_cache: dict = {}
    return harvest_checkboxes(v, date_cache) + harvest_ledgers(v)
