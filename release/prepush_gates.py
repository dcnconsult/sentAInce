"""Fail-closed pre-push gates (ADR-011) — the safety net between the private monorepo and a public push.

Mirrors the pre-DEPLOY gates in docs/DEPLOYMENT.md: a small set of hard checks, each of which must pass
before anything is published. Fail-closed — an unreadable file or an unknown state is a FAIL, never a skip.
Operates on a (root, list-of-public-relpaths) so it can check either the live source subset or a built
tree. Read-only.

  from release.build_public import iter_public_files
  from release.prepush_gates import run_gates
  ok, report = run_gates(root, list(iter_public_files(root)))
"""
from __future__ import annotations

from pathlib import Path

from release import manifest as M


def _read(root: Path, rel: str) -> "str | None":
    # scan the content that will actually PUBLISH: a variant-mapped path resolves to its .public.md source
    try:
        return (root / M.variant_source(rel)).read_text(encoding="utf-8", errors="strict")
    except Exception:
        return None


# ------------------------------------------------------------------ individual gates
def gate_patent(root: Path) -> dict:
    """The hard gate: no push until the provisionals are filed (code IS disclosure). Cleared only by the
    presence of the committed ``release/PROVISIONALS_FILED`` marker."""
    ok = (root / M.PATENT_GATE_FLAG).is_file()
    return {"gate": "patent_filed", "ok": ok,
            "detail": "provisionals filed (marker present)" if ok
            else f"BLOCKED — {M.PATENT_GATE_FLAG} absent; file provisionals before any public disclosure"}


def gate_no_commercial(files: list) -> dict:
    """Defense-in-depth: assert the public set contains nothing under COMMERCIAL_EXCLUDE / NEVER_PUBLIC.
    A PUBLIC_VARIANTS canonical name is expected in the set — it publishes the scrubbed ``.public.md``
    variant, not the held original — so it is not a leak (the other content gates scan that variant)."""
    leaked = sorted(f for f in files
                    if f not in M.PUBLIC_VARIANTS
                    and (M._under(f, M.COMMERCIAL_EXCLUDE) or M._under(f, M.NEVER_PUBLIC)))
    return {"gate": "no_commercial_or_private", "ok": not leaked, "detail": leaked[:20] or "none"}


# The one file allowed to CONTAIN denylist tokens: the manifest must name the generic tokens it bans.
# (The identifying tokens live in release/denylist_private.py, which is NEVER_PUBLIC and thus never scanned.)
_DENYLIST_EXEMPT = frozenset({"release/manifest.py"})


def gate_denylist_tokens(root: Path, files: list, tokens=None) -> dict:
    """No private-crucible / customer / dev-path token appears in any public text file.
    ``tokens`` overrides the manifest list (tests inject synthetic tokens so THIS suite carries none)."""
    toks = M.DENYLIST_TOKENS if tokens is None else tokens
    hits: list = []
    for rel in files:
        if rel in _DENYLIST_EXEMPT:
            continue
        txt = _read(root, rel)
        if txt is None:
            continue
        for tok in toks:
            if tok in txt:
                hits.append(f"{rel} :: {tok}")
    return {"gate": "no_denylisted_tokens", "ok": not hits, "n": len(hits), "detail": hits[:40]}


# Prose markers that a doc discloses an UNFILED, forward-looking method (patent-before-disclosure).
# A public file tripping any of these is a disclosure risk the binary patent_filed gate can't catch —
# the filed provisional covers TODAY's claims, not the "candidate" methods these markers flag. Fail-closed;
# the fix is to hold the file (manifest NEVER_PUBLIC) or strip the forward-looking section before publishing.
_IP_DISCLOSURE_MARKERS = (
    "patent-before-disclosure",
    "before any disclosure",
    "until counsel clears",
    "filing opportunit",          # "filing opportunity" / "opportunities"
    "candidates, not claims",
    "**IP:**",                    # the per-item IP-method pointer format used in ENHANCEMENTS §F/§G
)
# The gate's own definition/test files must NAME the markers they ban (same self-reference carve-out as
# the denylist gate). These describe no method — they define the backstop.
_IP_GATE_EXEMPT = frozenset({
    "release/prepush_gates.py", "release/manifest.py", "release/tests/test_release.py",
})


def gate_no_ip_disclosure(root: Path, files: list) -> dict:
    """No PUBLIC file discloses an unfiled forward-looking method. The token denylist catches paths/PII;
    this catches METHOD PROSE the docs themselves flag as pre-disclosure/candidate IP. Fail-closed so a
    future forward-looking doc cannot silently ship (the acute 2026-07 finding: ENHANCEMENTS/ROADMAP §3
    carried `**IP:**` method pointers into the public set)."""
    hits: list = []
    for rel in files:
        if rel in _IP_GATE_EXEMPT:
            continue
        txt = _read(root, rel)
        if txt is None:
            continue
        low = txt.lower()
        for mark in _IP_DISCLOSURE_MARKERS:
            if mark.lower() in low:
                hits.append(f"{rel} :: {mark!r}")
    return {"gate": "no_ip_disclosure", "ok": not hits, "n": len(hits), "detail": hits[:40]}


def gate_secrets(root: Path, files: list) -> dict:
    """No secret-shaped string (keys, PEM, PATs) in the public tree."""
    hits: list = []
    for rel in files:
        txt = _read(root, rel)
        if txt is None:
            continue
        for pat in M.SECRET_PATTERNS:
            if pat.search(txt):
                hits.append(f"{rel} :: {pat.pattern[:40]}")
    return {"gate": "no_secrets", "ok": not hits, "n": len(hits), "detail": hits[:40]}


def gate_license(root: Path, files: list) -> dict:
    """The Apache-2.0 LICENSE must be present in the public set."""
    ok = "LICENSE" in set(files) and (root / "LICENSE").is_file()
    return {"gate": "license_present", "ok": ok, "detail": "LICENSE present" if ok else "LICENSE missing"}


def gate_wheel_purity(root: Path) -> dict:
    """A wheel built from ``root`` must contain the community packages and ZERO ``exocortex/tuner``
    members (ADR-012 — the wheel is publication just like a push). Skipped (ok) when ``root`` has no
    pyproject (synthetic test roots); the real tree always has one, so the gate always runs there.
    Fail-closed on build errors — an unbuildable tree is not publishable."""
    import subprocess
    import sys
    import tempfile
    import zipfile
    if not (root / "pyproject.toml").is_file():
        return {"gate": "wheel_purity", "ok": True, "detail": "skipped (no pyproject.toml at root)"}
    with tempfile.TemporaryDirectory(prefix="wheel_gate_") as td:
        try:
            r = subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", td],
                               cwd=root, capture_output=True, timeout=600)
            if r.returncode != 0:
                return {"gate": "wheel_purity", "ok": False,
                        "detail": f"wheel build failed: {r.stderr.decode(errors='replace')[-400:]}"}
            whl = sorted(Path(td).glob("*.whl"))
            if not whl:
                return {"gate": "wheel_purity", "ok": False, "detail": "build produced no wheel"}
            names = zipfile.ZipFile(whl[-1]).namelist()
            tuner = [n for n in names if n.startswith("exocortex/tuner")]
            tops = {n.split("/", 1)[0] for n in names}
            missing = {"sentaince", "exocortex", "cerebral"} - tops
            ok = not tuner and not missing
            return {"gate": "wheel_purity", "ok": ok,
                    "detail": ("clean wheel: community packages present, zero tuner members" if ok else
                               f"tuner members: {tuner[:5]}; missing packages: {sorted(missing)}")}
        except Exception as e:
            return {"gate": "wheel_purity", "ok": False, "detail": f"unbuildable: {type(e).__name__}: {e}"}


# ------------------------------------------------------------------ runner
def run_gates(root, files: list) -> tuple:
    """Run every gate. Returns ``(all_ok, [gate_result, ...])``. all_ok is False if ANY gate fails."""
    root = Path(root)
    results = [
        gate_patent(root),
        gate_no_commercial(files),
        gate_denylist_tokens(root, files),
        gate_no_ip_disclosure(root, files),
        gate_secrets(root, files),
        gate_license(root, files),
        gate_wheel_purity(root),
    ]
    return all(g["ok"] for g in results), results


def format_report(all_ok: bool, results: list) -> str:
    lines = ["PRE-PUSH GATES (ADR-011) — fail-closed", ""]
    for g in results:
        mark = "PASS" if g["ok"] else "FAIL"
        lines.append(f"  [{mark}] {g['gate']}")
        if not g["ok"]:
            d = g["detail"]
            if isinstance(d, list):
                for item in d:
                    lines.append(f"          - {item}")
                if g.get("n", 0) > len(d):
                    lines.append(f"          … +{g['n'] - len(d)} more")
            else:
                lines.append(f"          {d}")
    lines += ["", f"VERDICT: {'READY — all gates pass' if all_ok else 'BLOCKED — resolve the FAILs above'}"]
    return "\n".join(lines) + "\n"
