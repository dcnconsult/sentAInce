"""Fail-closed public projection from the private monorepo (ADR-011).

The source file set is git-tracked and allowlisted. Materialization accepts only a path that does not
exist, never removes an output directory, and emits a privacy-preserving projection receipt.

  python -m release.build_public
  python -m release.build_public --json
  python -m release.build_public --out <new-empty-target-path>
  python -m release.build_public --verify-receipt
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from release import manifest as M
from release.prepush_gates import format_report, run_gates


_REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_RECEIPT = "release/projection_receipt.json"


def _private_source(root: Path) -> bool:
    return (root / "release" / "denylist_private.py").is_file()


def _projection_source(root: Path, rel: str) -> str:
    """Resolve private variant sources, but only let an already-derived public tree use canonical data."""
    variant = M.variant_source(rel)
    if (root / variant).is_file():
        return variant
    if not _private_source(root) and (root / rel).is_file():
        return rel
    raise FileNotFoundError(f"projection source missing for {rel}: expected {variant}")


def _tracked_files(root: Path) -> list[str]:
    """Return the exact git-tracked source set; fail rather than falling back to a disk walk."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git ls-files failed (rc={result.returncode}): {result.stderr.strip()[:200]} — "
            "cannot determine the publishable set; refusing to fall back to a disk walk"
        )
    return [name for name in result.stdout.split("\0") if name]


def iter_public_files(root: str | Path | None = None) -> list[str]:
    root = _REPO_ROOT if root is None else Path(root)
    tracked = set(_tracked_files(root))
    tracked.discard(GENERATED_RECEIPT)  # generated from the projection; never self-hashed
    public = {rel for rel in tracked if M.is_public(rel)}
    for published, source in M.PUBLIC_VARIANTS.items():
        if source in tracked:
            public.add(published)
        elif not _private_source(root) and published in tracked:
            public.add(published)
    return sorted(public)


def _summary(files: list[str]) -> dict:
    tops: dict[str, int] = {}
    for rel in files:
        top = rel.split("/", 1)[0] if "/" in rel else rel
        tops[top] = tops.get(top, 0) + 1
    withheld = sorted({path.split("/", 1)[0] for path in (M.COMMERCIAL_EXCLUDE + M.NEVER_PUBLIC)})
    return {
        "n_public_files": len(files),
        "by_top": dict(sorted(tops.items())),
        "commercial_excluded": M.COMMERCIAL_EXCLUDE,
        "never_public": M.NEVER_PUBLIC,
        "withheld_tops": withheld,
    }


def _assert_new_target(out: Path) -> None:
    if out.exists():
        if (out / ".git").exists():
            raise FileExistsError(f"refusing output target containing .git: {out}")
        raise FileExistsError(f"output target must not already exist: {out}")


def _projection_digest(root: Path, files: list[str]) -> str:
    """Digest materialized bytes for a projection that has not entered Git yet."""
    digest = hashlib.sha256()
    for rel in sorted(files):
        content_hash = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        digest.update(rel.encode("utf-8") + b"\0" + content_hash.encode("ascii") + b"\0")
    return digest.hexdigest()


def _git_index_digest(root: Path, files: list[str]) -> str:
    """Digest Git's canonical stage-0 paths, modes, and blob IDs.

    A release PR is committed from this representation. Using the index avoids making the receipt
    depend on a checkout's CRLF/LF presentation while still covering the exact tracked content.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git ls-files --stage failed (rc={result.returncode}): "
            f"{result.stderr.decode('utf-8', errors='replace').strip()[:200]}"
        )
    entries: dict[str, tuple[str, str]] = {}
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        metadata, encoded_path = raw.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        if stage == "0":
            entries[encoded_path.decode("utf-8", errors="surrogateescape").replace("\\", "/")] = (
                mode,
                object_id,
            )
    missing = sorted(set(files) - entries.keys())
    if missing:
        raise RuntimeError(f"projection paths missing from Git index: {missing[:10]}")
    digest = hashlib.sha256()
    for rel in sorted(files):
        mode, object_id = entries[rel]
        digest.update(
            rel.encode("utf-8") + b"\0" + mode.encode("ascii") + b"\0"
            + object_id.encode("ascii") + b"\0"
        )
    return digest.hexdigest()


def _git_worktree_matches_index(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "--"],
        capture_output=True,
        timeout=60,
    )
    return result.returncode == 0


def _version(root: Path) -> str:
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def _utc_now() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    now = datetime.fromtimestamp(int(epoch), timezone.utc) if epoch else datetime.now(timezone.utc)
    return now.isoformat(timespec="seconds")


def _write_receipt(
    out: Path,
    files: list[str],
    gates: list[dict],
    *,
    projection_digest: str | None = None,
    digest_format: str = "worktree-sha256-v1",
) -> dict:
    receipt = {
        "schema": 1,
        "release_version": _version(out),
        "generated_utc": _utc_now(),
        "projection_digest": projection_digest or _projection_digest(out, files),
        "digest_format": digest_format,
        "file_count": len(files),
        "gates": [{"name": gate["gate"], "ok": bool(gate["ok"])} for gate in gates],
    }
    path = out / GENERATED_RECEIPT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def verify_receipt(root: str | Path) -> dict:
    root = Path(root)
    receipt_path = root / GENERATED_RECEIPT
    if not receipt_path.is_file():
        return {"ok": False, "error": "projection receipt missing"}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    tracked = sorted(rel for rel in _tracked_files(root) if rel != GENERATED_RECEIPT)
    digest_format = receipt.get("digest_format")
    if digest_format == "git-index-blob-v1":
        actual = _git_index_digest(root, tracked)
        clean = _git_worktree_matches_index(root)
    elif digest_format == "worktree-sha256-v1":
        actual = _projection_digest(root, tracked)
        clean = True
    else:
        actual = ""
        clean = False
    ok = (
        receipt.get("schema") == 1
        and receipt.get("file_count") == len(tracked)
        and receipt.get("projection_digest") == actual
        and clean
        and all(gate.get("ok") is True for gate in receipt.get("gates", []))
    )
    return {"ok": ok, "expected": receipt.get("projection_digest"), "actual": actual,
            "digest_format": digest_format, "file_count": len(tracked)}


def build(out: str | Path, root: str | Path | None = None) -> dict:
    """Materialize once into a new path. Never deletes, replaces, or cleans an existing directory."""
    root = _REPO_ROOT if root is None else Path(root)
    out = Path(out).resolve()
    _assert_new_target(out)
    files = iter_public_files(root)
    all_ok, gates = run_gates(root, files)
    if not all_ok:
        raise RuntimeError("public projection blocked by release gates")
    out.mkdir(parents=True, exist_ok=False)
    for rel in files:
        destination = out / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / _projection_source(root, rel), destination)
    _regenerate_kernel_baseline(out)
    receipt = _write_receipt(out, files, gates)
    return {"out": str(out), "gates_ok": True, "gates": gates, "receipt": receipt, **_summary(files)}


def _regenerate_kernel_baseline(out: Path) -> None:
    if not (out / "exocortex" / "integrity.py").is_file():
        return
    import sys

    subprocess.run(
        [sys.executable, "-m", "exocortex.integrity", "--update-baseline"],
        cwd=out,
        capture_output=True,
        timeout=120,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the governed public community projection")
    parser.add_argument("--out", help="new path to create; an existing path is always refused")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verify-receipt", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_receipt:
        result = verify_receipt(_REPO_ROOT)
        print(json.dumps(result, indent=2) if args.json else result)
        return 0 if result["ok"] else 1

    files = iter_public_files(_REPO_ROOT)
    all_ok, gates = run_gates(_REPO_ROOT, files)
    summary = _summary(files)
    materialized = None
    if args.out:
        if not all_ok:
            materialized = None
        else:
            materialized = build(args.out, _REPO_ROOT)
    if args.json:
        print(json.dumps({"gates_ok": all_ok, "gates": gates, "summary": summary,
                          "materialized": materialized}, indent=2))
        return 0 if all_ok else 1
    print(f"PUBLIC BUILD (ADR-011) — {summary['n_public_files']} source files ship")
    print("  by top-level:", ", ".join(f"{key}={value}" for key, value in summary["by_top"].items()))
    print("  withheld:", ", ".join(summary["withheld_tops"]))
    print()
    print(format_report(all_ok, gates), end="")
    if args.out:
        print(f"\nmaterialized → {args.out}" if materialized else "\nNOT materialized — gates failed")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
