"""Deterministically materialize the PUBLIC community tree from the private monorepo (ADR-011).

Reads the repo, applies ``manifest.is_public`` to every file, and (with ``--out``) copies the public subset
to a fresh directory — the seed for the public repo's single "Initial public release" commit (squashed
history: no leak of ``patent/`` or private-crucible content from git history). Read-only w.r.t. the source;
writes only under ``--out``.

  python -m release.build_public                         # dry-run: list what ships + the gate verdict
  python -m release.build_public --out ../SentAInce-public   # materialize the public tree (after gates pass)
  python -m release.build_public --json                  # machine-readable manifest + gate report
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from release import manifest as M
from release.prepush_gates import run_gates, format_report

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _tracked_files(root: Path) -> list:
    """Repo-relative posix paths of every git-TRACKED file. Publication derives from what git would push —
    never from a disk walk, which would sweep in untracked/gitignored local artifacts (audit logs, local
    compose overrides). Fail closed: an unreadable git state is unpublishable, not a fallback."""
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"git ls-files failed (rc={r.returncode}): {r.stderr.strip()[:200]} — "
                           "cannot determine the publishable set; refusing to fall back to a disk walk")
    return [f for f in r.stdout.split("\0") if f]


def iter_public_files(root=None):
    """Every repo-relative posix path that ships to the public community repo, sorted (deterministic).
    Candidates are git-tracked files only (see ``_tracked_files``). A canonical path with a PUBLIC_VARIANT
    is included when its variant SOURCE is tracked (the private original is NEVER_PUBLIC, but the variant
    content publishes under the canonical name)."""
    root = _REPO_ROOT if root is None else Path(root)
    tracked = set(_tracked_files(root))
    out = {rel for rel in tracked if M.is_public(rel)}
    for published, src in M.PUBLIC_VARIANTS.items():
        if src in tracked:
            out.add(published)          # publish the canonical name; content comes from the variant source
    return sorted(out)


def _summary(files: list) -> dict:
    tops: dict = {}
    for rel in files:
        top = rel.split("/", 1)[0] if "/" in rel else rel
        tops[top] = tops.get(top, 0) + 1
    # what's deliberately withheld (for the report)
    withheld = sorted({p.split("/", 1)[0] for p in (M.COMMERCIAL_EXCLUDE + M.NEVER_PUBLIC)})
    return {"n_public_files": len(files), "by_top": dict(sorted(tops.items())),
            "commercial_excluded": M.COMMERCIAL_EXCLUDE, "never_public": M.NEVER_PUBLIC,
            "withheld_tops": withheld}


def build(out, root=None) -> dict:
    """Copy the public subset to ``out`` (created fresh). Returns the summary + gate report."""
    root = _REPO_ROOT if root is None else Path(root)
    files = iter_public_files(root)
    all_ok, gates = run_gates(root, files)
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel in files:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / M.variant_source(rel), dst)   # variant content publishes under the canonical name
    _regenerate_kernel_baseline(out)
    return {"out": str(out), "gates_ok": all_ok, "gates": gates, **_summary(files)}


def _regenerate_kernel_baseline(out: Path) -> None:
    """The community kernel is a TRIMMED subset (the deep research modules are held), so the committed
    ``integrity_baseline.json`` (which hashes the FULL private kernel) would report the held files as
    'missing' and fail ``verify_kernel``. Recompute the baseline over the MATERIALIZED public tree so its
    frozen-DNA lock matches what actually ships. No-op if the tree has no integrity module."""
    import subprocess
    import sys
    if not (out / "exocortex" / "integrity.py").is_file():
        return
    try:
        subprocess.run([sys.executable, "-m", "exocortex.integrity", "--update-baseline"],
                       cwd=out, capture_output=True, timeout=120, check=False)
    except Exception:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the public community tree from the private monorepo (ADR-011)")
    ap.add_argument("--out", default=None, help="materialize the public tree here (omit for a dry-run)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--force", action="store_true",
                    help="materialize even if gates FAIL (for inspection only — never push such a tree)")
    args = ap.parse_args(argv)

    root = _REPO_ROOT
    files = iter_public_files(root)
    all_ok, gates = run_gates(root, files)
    summary = _summary(files)

    if args.out and (all_ok or args.force):
        res = build(args.out, root)
        all_ok, gates = res["gates_ok"], res["gates"]

    if args.json:
        print(json.dumps({"gates_ok": all_ok, "gates": gates, "summary": summary,
                          "out": args.out if (args.out and (all_ok or args.force)) else None}, indent=2))
        return 0 if all_ok else 1

    print(f"PUBLIC BUILD (ADR-011) — {summary['n_public_files']} files ship")
    print("  by top-level:", ", ".join(f"{k}={v}" for k, v in summary["by_top"].items()))
    print("  withheld:", ", ".join(summary["withheld_tops"]))
    print()
    print(format_report(all_ok, gates), end="")
    if args.out:
        if all_ok or args.force:
            print(f"\nmaterialized → {args.out}"
                  + ("  (FORCED past failing gates — inspect only, DO NOT push)" if not all_ok else ""))
        else:
            print(f"\nNOT materialized — gates failed (use --force to inspect the tree anyway)")
    else:
        print("\n(dry-run — pass --out DIR to materialize once gates pass)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
