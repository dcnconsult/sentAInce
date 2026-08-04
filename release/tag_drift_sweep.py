"""Advisory sweep: shipped-sounding lines citing unbuilt ADRs (the bundled-row drift class).

Born 2026-08-04 from an external falsification (public Discussion #9): GOVERNANCE.md carried
ADR-017/ADR-018 — both PROPOSED/unbuilt — inside table rows tagged SHIPPED, because a bundled row
lets an unbuilt ADR ride a shipped neighbor's tag. CLAIMS.md was honest; the mapping exceeded it.

Run manually before a release:  python release/tag_drift_sweep.py
NOT wired into the release gates (they are 8, by decision) — promoting this to a gate is an owner
decision recorded in release/manifest.py, not a side effect of this file existing.

Exit 1 if any suspect co-mention is found, so it can be promoted later without edits.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHIPPED_WORDS = ("SHIPPED", "LOCKED", "LIVE")
OK_STATUSES = {"LOCKED", "ADOPTED", "DORMANT"}  # DORMANT = built + gauged, honestly labeled


def ledger() -> dict[str, str]:
    adr = (ROOT / "docs" / "ADR.md").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^## (ADR-\d+)[^\n]*\n(?:[^\n]*\n)?\+?\*\*Status:\*\* (\w[\w-]*)", adr, re.M):
        out[m.group(1)] = m.group(2)
    return out


def main() -> int:
    status = ledger()
    suspects: list[tuple[str, int, str, str, str]] = []
    for p in sorted((ROOT / "docs").glob("*.md")):
        if p.name == "ADR.md":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if not any(w in line for w in SHIPPED_WORDS):
                continue
            for a in sorted(set(re.findall(r"ADR-\d+", line))):
                st = status.get(a, "UNTAGGED")
                if st in OK_STATUSES:
                    continue
                # A line that itself labels the ADR as proposed/unbuilt is a correct split-status row.
                lowered = line.lower()
                if st == "PROPOSED" and ("proposed" in lowered or "not built" in lowered or "unbuilt" in lowered):
                    continue
                if st == "UNTAGGED":  # pre-convention ADRs (e.g. ADR-009) — informational only
                    continue
                suspects.append((p.name, i, a, st, line.strip()[:120]))
    for s in suspects:
        print(" | ".join(map(str, s)))
    print(f"{len(suspects)} suspect co-mention(s); ledger covers {len(status)} ADRs")
    return 1 if suspects else 0


if __name__ == "__main__":
    sys.exit(main())
