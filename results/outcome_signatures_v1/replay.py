"""R1c replay: which recorded `ok` consequences does the CURRENT `classify_outcome` now call `fail`?

Read-only over audit JSONL files. Each `PostToolUse` row stores `outcome` (the verdict at record time) and
`output` (the first 240 chars of stdout+stderr). Re-classifying that snippet with today's rules shows how many
past deposits the widened signature set would have withheld. The snippet is truncated, so this is a LOWER
bound on flips and a small sample of what they look like. Prints aggregates, plus per-rule counts with
`--show`.

  python results/outcome_signatures_v1/replay.py <audit.jsonl> [<audit.jsonl> ...] [--show]
"""
from __future__ import annotations

import collections
import json
import sys

from exocortex.hook import _EXITCODE_RE, _FAIL_MARKERS, _FAIL_RX, classify_outcome


def _rule(blob: str) -> str:
    if _EXITCODE_RE.search(blob):
        return "exit_code"
    for mk in _FAIL_MARKERS:
        if mk in blob:
            return f"marker:{mk}"
    for i, rx in enumerate(_FAIL_RX):
        if rx.search(blob):
            return f"rx{i}"
    return "?"


def replay(path: str, show: bool = False) -> dict:
    n = flips = 0
    by = collections.Counter()
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("event") != "PostToolUse" or r.get("outcome") != "ok":
            continue
        n += 1
        out = str(r.get("output") or "")
        if classify_outcome({"tool_response": {"stdout": out, "stderr": ""}}) == "fail":
            flips += 1
            rule = _rule(out)
            by[rule] += 1
            if show:
                print(f"  [{rule}] {out[:160]!r}")
    return {"recorded_ok": n, "now_fail": flips, "share": round(flips / max(1, n), 4), "by_rule": dict(by)}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--show"]
    for a in args:
        print(a.split("/")[-4] if a.count("/") >= 3 else a, json.dumps(replay(a, "--show" in sys.argv)))
