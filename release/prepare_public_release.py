"""Prepare a generated release branch in a fresh clone without staging ambient files.

This command builds the governed projection, clones public ``main`` into a path that must not exist,
updates only explicit tracked projection paths, verifies the exact index, and commits the branch. Pushing
and opening the protected pull request remain explicit maintainer actions.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from release.build_public import (
    GENERATED_RECEIPT,
    _git_index_digest,
    _write_receipt,
    build,
    iter_public_files,
    verify_receipt,
)


def _git(root: Path, *args: str, capture: bool = False) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=capture, text=True, check=True)
    return result.stdout.strip() if capture else ""


def _chunks(items: list[str], size: int = 50):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def prepare(public_repo: str, branch: str, checkout: str | Path, message: str) -> dict:
    checkout = Path(checkout).resolve()
    if checkout.exists():
        raise FileExistsError(f"checkout path must not already exist: {checkout}")
    checkout.parent.mkdir(parents=True, exist_ok=True)
    source_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="sentaince_projection_") as temp:
        projection = Path(temp) / "projection"
        result = build(projection, source_root)
        subprocess.run(["git", "clone", public_repo, str(checkout)], check=True)
        _git(checkout, "checkout", "-b", branch, "origin/main")

        projected = set(iter_public_files(source_root)) | {GENERATED_RECEIPT}
        existing = set(_git(checkout, "ls-files", "-z", capture=True).split("\0")) - {""}
        removed = sorted(existing - projected)
        for chunk in _chunks(removed):
            _git(checkout, "rm", "--", *chunk)
        for rel in sorted(projected):
            destination = checkout / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(projection / rel, destination)
        for chunk in _chunks(sorted(projected)):
            _git(checkout, "add", "--", *chunk)

        receipt_files = sorted(projected - {GENERATED_RECEIPT})
        canonical_digest = _git_index_digest(checkout, receipt_files)
        result["receipt"] = _write_receipt(
            checkout,
            receipt_files,
            result["gates"],
            projection_digest=canonical_digest,
            digest_format="git-index-blob-v1",
        )
        _git(checkout, "add", "--", GENERATED_RECEIPT)

        indexed = set(_git(checkout, "ls-files", "-z", capture=True).split("\0")) - {""}
        if indexed != projected:
            raise RuntimeError(
                f"public index differs from projection: missing={sorted(projected-indexed)[:10]} "
                f"extra={sorted(indexed-projected)[:10]}"
            )
        verification = verify_receipt(checkout)
        if not verification["ok"]:
            raise RuntimeError(f"canonical projection receipt did not verify: {verification}")
        _git(checkout, "commit", "-m", message)
        commit = _git(checkout, "rev-parse", "HEAD", capture=True)
    return {"checkout": str(checkout), "branch": branch, "commit": commit,
            "projection_digest": result["receipt"]["projection_digest"], "files": len(projected)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a governed public release branch")
    parser.add_argument("--public-repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--message", default="Harden governed public releases")
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.public_repo, args.branch, args.checkout, args.message), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
