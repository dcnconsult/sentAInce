#!/usr/bin/env python3
"""Summarize a ``cursor_probe_log.jsonl`` into the P0 answers it can decide automatically, and lay out what
still needs the human's chat observation (P0-b) or a behavioral test (P0-e).

  python analyze.py                       # auto-find the newest log under ./runs/**
  python analyze.py <log.jsonl | dir>     # explicit file, or a dir to search
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import Counter, defaultdict


def _find_log(arg: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    if arg:
        if os.path.isfile(arg):
            return arg
        if os.path.isdir(arg):
            hits = glob.glob(os.path.join(arg, "**", "cursor_probe_log.jsonl"), recursive=True)
            return max(hits, key=os.path.getmtime) if hits else ""
        return ""
    # no arg: search this tool's runs/ recursively (handles runs/<project>/...), newest wins
    hits = glob.glob(os.path.join(here, "runs", "**", "cursor_probe_log.jsonl"), recursive=True)
    return max(hits, key=os.path.getmtime) if hits else ""


def _load(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    return rows


def main() -> None:
    path = _find_log(sys.argv[1] if len(sys.argv) > 1 else "")
    if not path or not os.path.isfile(path):
        print("no cursor_probe_log.jsonl found. Pass the path or a dir to search:\n"
              "  python analyze.py C:/path/to/runs/<project>/cursor_probe_log.jsonl")
        sys.exit(2)
    rows = _load(path)
    print(f"# Cursor probe analysis — {len(rows)} events\n# source: {path}\n")

    # ===== THE v2 QUESTION: where does Cursor deliver the payload? =====
    src = Counter(r.get("payload_source") for r in rows)
    print("## PAYLOAD DELIVERY — where the hook input actually arrives:")
    for k, n in src.most_common():
        print(f"   {k}: {n}")
    if set(src) <= {"NOT-FOUND", None}:
        print("   !! payload NOT delivered via stdin OR argv. Inspecting env + argv for where it hides:")
        env_keys = set()
        env_vals = {}
        argv_samples = set()
        for r in rows:
            env_keys.update(r.get("env_key_names") or [])
            env_vals.update(r.get("env_hook_values") or {})
            argv_samples.add(" ".join(r.get("full_argv") or []))
        hookish = sorted(k for k in env_keys if any(h in k.upper()
                         for h in ("CURSOR", "HOOK", "TOOL", "MODEL", "CONVERSATION", "PROMPT", "AGENT", "INPUT", "PAYLOAD")))
        print(f"   hook-shaped ENV key names present: {hookish or '(none)'}")
        if env_vals:
            print("   hook-shaped ENV values (candidate payload carriers):")
            for k, v in env_vals.items():
                print(f"     {k} = {v[:200]}")
        print(f"   full argv seen (is the payload appended as an arg?):")
        for s in list(argv_samples)[:4]:
            print(f"     {s}")
        print("   stdin samples (len/first chars):")
        for r in rows[:4]:
            print(f"     len={r.get('stdin_len')} :: {repr((r.get('stdin_sample') or '')[:80])}")
    print()

    # P0-c — which events fire
    ev = Counter((r.get("resolved_event") or r.get("argv_event")) for r in rows)
    print("## P0-c — events that FIRED:")
    for k, n in ev.most_common():
        print(f"   {k}: {n}")
    fired = " ".join(str(k).lower() for k in ev)
    missing = [e for e in ["sessionStart", "preToolUse", "postToolUse", "postToolUseFailure",
                           "beforeSubmitPrompt", "preCompact", "stop"] if e.lower() not in fired]
    print(f"   MISSING: {missing or 'none'}\n")

    # P0-d — model string
    models = Counter(str(r.get("model_field")) for r in rows if r.get("model_field"))
    print("## P0-d — exact `model` string(s):")
    print("   " + (", ".join(f"{m} (x{n})" for m, n in models.most_common())
                   or "(model field absent — depends on payload delivery above)") + "\n")

    # P0-a — matcher engine
    pre = Counter(r.get("matcher_tag") for r in rows
                  if "pretooluse" in str(r.get("resolved_event") or r.get("argv_event")).lower())
    print("## P0-a — preToolUse matcher tags that fired (Shell):")
    for k, n in pre.most_common():
        print(f"   {k}: {n}")
    tags = set(pre)
    verdict = ("no preToolUse fired" if not tags else
               "REGEX (^Shell$ matched)" if "regex" in tags else
               "GLOB (Sh*ll matched)" if "glob" in tags else
               "EXACT/literal only" if tags <= {"exact"} else "unclear")
    print(f"   => matcher engine: {verdict}\n")

    # Adapter contract
    keys = defaultdict(set)
    for r in rows:
        keys[(r.get("resolved_event") or r.get("argv_event"))].update(r.get("payload_keys") or [])
    print("## Adapter contract — payload keys per event:")
    for k in sorted(keys, key=str):
        print(f"   {k}: {sorted(keys[k]) or '(empty — no payload delivered)'}")
    print()

    # P0-b — emitted markers (human correlates with chat)
    print("## P0-b — markers EMITTED (correlate by seq/tok vs what the model echoed in chat):")
    for r in rows:
        for ch in (r.get("emitted_channels") or []):
            print(f"   seq={r.get('seq')} ev={r.get('resolved_event')} ch={ch} tok={r.get('tok')}")
    print("\n   From your saved chat replies: did agent_message / additional_context / rules_file markers")
    print("   appear, and for rules_file — same submission that wrote seq=N (same-turn) or the next (lag)?")
    print("## P0-e — failClosed: behavioral; make probe.py exit 1 on preToolUse and see if Cursor blocks.")


if __name__ == "__main__":
    main()
