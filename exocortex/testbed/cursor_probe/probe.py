#!/usr/bin/env python3
"""Cursor hook PROBE (v2) — a read-only measurement instrument for the model-independent IDE arc (P0-a..e).

NOT an organ. Imports nothing from ``exocortex`` — stdlib only, fail-open, fast. It does two things:

  1. LOCATES + LOGS the payload Cursor sends for every hook event. v1 found stdin EMPTY on Windows, so v2
     captures ALL delivery channels — stdin, full argv, and environment — to discover WHERE Cursor puts the
     payload (→ the adapter contract + P0-d the exact ``model`` string + P0-c which events fire on Windows).
  2. EMITS a uniquely-tagged ``EXO-PROBE`` marker through each candidate injection channel and rewrites an
     ``alwaysApply`` rules file, so a human can observe in the chat WHICH markers the model sees and WHEN
     (→ P0-b: dynamic-rules rewrite timing + the ``agent_message`` question). Injection does not depend on
     stdin, so P0-b is decidable from this run regardless of the payload-delivery issue.

Every run appends one JSON line to --log and exits 0 no matter what. Analysed by analyze.py; procedure in
README.md. SECRET-SAFE: env *values* are logged only for hook-shaped keys and never for KEY/TOKEN/SECRET ones.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid

# env keys whose VALUE we log (likely payload carriers) ...
_ENV_VALUE_HINTS = ("CURSOR", "HOOK", "TOOL", "MODEL", "CONVERSATION", "GENERATION",
                    "PROMPT", "WORKSPACE", "AGENT", "INPUT", "PAYLOAD")
# ... unless the key also looks like a secret (then name-only)
_ENV_SECRET_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")


def _arg(flag: str, default: str = "") -> str:
    a = sys.argv[2:]
    if flag in a:
        try:
            return a[a.index(flag) + 1]
        except IndexError:
            return default
    return default


def _next_seq(state_path: str) -> int:
    seq = 0
    try:
        if os.path.isfile(state_path):
            seq = int(json.loads(open(state_path, encoding="utf-8").read()).get("seq", 0))
    except Exception:
        seq = 0
    seq += 1
    try:
        open(state_path, "w", encoding="utf-8").write(json.dumps({"seq": seq}))
    except Exception:
        pass
    return seq


def _marker(seq: int, channel: str, event: str, tag: str, tok: str) -> str:
    return (f"EXO-PROBE | seq={seq} | ch={channel} | ev={event} | tag={tag or '-'} "
            f"| ts={time.strftime('%Y-%m-%dT%H:%M:%S')} | tok={tok}")


def _write_rules(rules_path: str, marker: str) -> bool:
    try:
        os.makedirs(os.path.dirname(rules_path), exist_ok=True)
        body = ("---\n"
                "description: EXO-PROBE dynamic rules-file timing test (auto-generated)\n"
                "alwaysApply: true\n"
                "---\n"
                f"{marker}\n"
                "When asked to list EXO-PROBE lines, echo the line above verbatim.\n")
        open(rules_path, "w", encoding="utf-8").write(body)
        return True
    except Exception:
        return False


def _json_from(s: str):
    s = (s or "").lstrip("﻿").strip()   # Cursor sends UTF-8 WITH A BOM on Windows; strip it before parse
    if s.startswith("{") and s.endswith("}"):
        try:
            d = json.loads(s)
            return d if isinstance(d, dict) else None
        except Exception:
            return None
    return None


def _scan_argv_for_payload(argv: list):
    """Cursor may pass the payload as a JSON argv arg (or a path to a JSON file). Find either."""
    for a in argv:
        d = _json_from(a)
        if d is not None:
            return d, "argv-json"
    for a in argv:
        try:
            if a and os.path.isfile(a) and a.lower().endswith(".json"):
                d = _json_from(open(a, encoding="utf-8").read())
                if d is not None:
                    return d, f"argv-file:{os.path.basename(a)}"
        except Exception:
            pass
    return None, ""


def _scan_env():
    """Return (value_map, all_key_names). Values only for hook-shaped, non-secret keys."""
    vals, names = {}, []
    for k, v in os.environ.items():
        names.append(k)
        ku = k.upper()
        if any(h in ku for h in _ENV_VALUE_HINTS) and not any(s in ku for s in _ENV_SECRET_HINTS):
            vals[k] = (v or "")[:2000]
    return vals, sorted(names)


def main() -> None:
    argv_event = sys.argv[1] if len(sys.argv) > 1 else ""
    full_argv = list(sys.argv)
    log_path = _arg("--log") or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "runs", "cursor_probe_log.jsonl")
    rules_path = _arg("--rules")
    tag = _arg("--tag")
    deny_mode = "--deny" in sys.argv   # TEST: preToolUse returns permission:deny + EXIT 2 — does Cursor honor it?
    state_path = os.path.join(os.path.dirname(log_path), "probe_state.json")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
    except Exception:
        pass

    # --- locate the payload across ALL delivery channels (the v2 question) ---
    try:
        stdin_raw = sys.stdin.read()
    except Exception:
        stdin_raw = ""
    stdin_data = _json_from(stdin_raw)
    argv_data, argv_src = _scan_argv_for_payload(full_argv[2:])
    env_vals, env_keys = _scan_env()

    if stdin_data is not None:
        payload, source = stdin_data, "stdin"
    elif argv_data is not None:
        payload, source = argv_data, argv_src
    else:
        payload, source = {}, "NOT-FOUND"

    payload_event = str(payload.get("hook_event_name") or "")
    event = payload_event or argv_event
    ev_l = (event or argv_event).lower()
    seq = _next_seq(state_path)
    tok = uuid.uuid4().hex[:8]

    out: dict = {}
    emitted: list = []
    exit_code = 0
    if "pretooluse" in ev_l:
        if deny_mode:
            mk = _marker(seq, "deny", event, tag, tok)
            out = {"permission": "deny", "user_message": mk, "agent_message": mk}
            emitted.append("deny"); exit_code = 2   # the explicit blocking path
        else:
            out = {"permission": "allow", "agent_message": _marker(seq, "agent_message", event, tag, tok)}
            emitted.append("agent_message")
    elif "sessionstart" in ev_l:
        out = {"additional_context": _marker(seq, "additional_context", event, tag, tok)}
        emitted.append("additional_context")
        if rules_path and _write_rules(rules_path, _marker(seq, "rules_file", event, tag, tok)):
            emitted.append("rules_file")
    elif "posttooluse" in ev_l:
        out = {"additional_context": _marker(seq, "additional_context", event, tag, tok)}
        emitted.append("additional_context")
    elif "beforesubmitprompt" in ev_l:
        out = {"additional_context": _marker(seq, "additional_context?", event, tag, tok)}
        emitted.append("additional_context?")
        if rules_path and _write_rules(rules_path, _marker(seq, "rules_file", event, tag, tok)):
            emitted.append("rules_file")
    elif "precompact" in ev_l:
        out = {"additional_context": _marker(seq, "additional_context?", event, tag, tok)}
        emitted.append("additional_context?")

    rec = {
        "seq": seq, "tok": tok, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "argv_event": argv_event, "payload_hook_event_name": payload_event, "resolved_event": event,
        "matcher_tag": tag,
        # --- payload delivery diagnostics (the v2 core) ---
        "payload_source": source,                 # stdin | argv-json | argv-file:* | NOT-FOUND
        "stdin_len": len(stdin_raw or ""),
        "stdin_sample": (stdin_raw or "")[:500],
        "full_argv": full_argv,
        "env_hook_values": env_vals,              # values for hook-shaped, non-secret keys
        "env_key_names": env_keys,                # ALL env key names (names only)
        # --- parsed payload (from wherever it was found) ---
        "payload_keys": sorted(payload.keys()),
        "model_field": payload.get("model"),
        "tool_name": payload.get("tool_name"),
        "conversation_id": payload.get("conversation_id"),
        "cwd": payload.get("cwd"),
        "workspace_roots": payload.get("workspace_roots"),
        "cursor_version": payload.get("cursor_version"),
        "emitted_channels": emitted,
        "exit_code": exit_code,
        "stdout_emitted": out or None,
        "raw_payload": payload,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

    if out:
        try:
            sys.stdout.write(json.dumps(out))
        except Exception:
            pass
    sys.exit(exit_code)   # fail-open (0) by default; EXIT 2 only in --deny test mode (preToolUse block)


if __name__ == "__main__":
    main()
