"""Provider adapter — parse + normalize Cursor hook I/O to the exocortex's internal (Claude-shaped)
contract, and serialize internal decisions back to Cursor's flat output. The per-event handlers stay
provider-agnostic; only ``hook.py:main()`` touches this. **Claude Code is the default and passes through
completely unchanged** (``detect`` returns "claude" when no Cursor markers are present).

Empirically gauged on Cursor 3.9.16 / Windows (results: ``exocortex/testbed/cursor_probe`` README):
  * the payload arrives on **stdin as UTF-8 WITH A BOM** → strip it before parse;
  * matchers are JS-regex; ``permission: "ask"`` is accepted but **not enforced** → advisory only; a hard
    veto must be ``permission: "deny"`` **plus exit code 2**;
  * injection: ``beforeSubmitPrompt.additional_context`` works same-turn but is **undocumented**;
    ``sessionStart`` + ``postToolUse`` ``additional_context`` are the documented floor — all read the same
    ``additional_context`` field, so one serializer covers them;
  * ``tool_output`` is a JSON **string** holding ``{"output","exitCode"}``; the stable model id is
    ``model_id``.
"""
from __future__ import annotations

import json
import os

# Cursor camelCase event → the exocortex's canonical (Claude) event name dispatched in main().
_CURSOR_TO_CANON = {
    "pretooluse": "PreToolUse",
    "beforeshellexecution": "PreToolUse",       # secondary shell surface → same gate
    "posttooluse": "PostToolUse",
    "posttoolusefailure": "PostToolUseFailure",
    "beforesubmitprompt": "UserPromptSubmit",
    "sessionstart": "SessionStart",
    "precompact": "PreCompact",
    "stop": "SessionEnd",                        # no handler yet → no-op (not registered for MVP)
    "sessionend": "SessionEnd",
}
_TOOL_TO_CANON = {"shell": "Bash"}               # Cursor 'Shell' → our Bash gate


def read_payload(raw: str) -> dict:
    """BOM-safe stdin parse (Cursor sends UTF-8 with a BOM). Mirrors hook.py's original fail-soft behavior:
    empty / invalid / non-dict → ``{}``. Harmless for Claude (no BOM)."""
    s = (raw or "").lstrip("﻿").strip()
    if not s:
        return {}
    try:
        d = json.loads(s)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def detect(env_pref: str, data: dict) -> str:
    """'cursor' | 'claude'. An explicit ``EXOCORTEX_PROVIDER`` wins (deploy bakes ``--provider``);
    otherwise auto-detect from the payload shape (Cursor carries ``cursor_version`` / ``conversation_id``)."""
    p = (env_pref or "").strip().lower()
    if p in ("cursor", "claude"):
        return p
    if data.get("cursor_version") or data.get("conversation_id"):
        return "cursor"
    return "claude"


def model_id(data: dict) -> str:
    """Stable head id for the F3 provenance stamp, straight from the Cursor payload (model_id is the
    consistent form: 'gpt-5.5'; 'model' varies as 'gpt-5.5'/'gpt-5.5-medium' by event)."""
    return str(data.get("model_id") or data.get("model") or "")


def cursor_transcript_path(data: dict) -> str:
    """Best path to the Cursor session transcript, for lazy-init prompt recovery: the payload's
    ``transcript_path`` if present, else the ``CURSOR_TRANSCRIPT_PATH`` env — which IS set on `preToolUse`
    even when the payload field is null (verified on 3.9.16). Returns '' unless it resolves to a real file."""
    p = str(data.get("transcript_path") or os.environ.get("CURSOR_TRANSCRIPT_PATH") or "")
    return p if p and os.path.isfile(p) else ""


def _parse_tool_output(data: dict) -> dict:
    """Cursor ``tool_output`` is a JSON STRING: ``{"output": "...", "exitCode": N}``. Return the
    ``{stdout, stderr, exitCode}`` shape ``handle_consequence`` expects."""
    raw = data.get("tool_output")
    out, code = "", None
    if isinstance(raw, str) and raw.strip():
        try:
            d = json.loads(raw)
            out, code = str(d.get("output", "")), d.get("exitCode")
        except Exception:
            out = raw
    elif isinstance(raw, dict):
        out, code = str(raw.get("output", "")), raw.get("exitCode")
    return {"stdout": out, "stderr": "", "exitCode": code}


def outcome(data: dict) -> str:
    """Cursor PostToolUse outcome from the (normalized) tool_response exit code. Defaults 'ok' if absent."""
    tr = data.get("tool_response") or {}
    code = tr.get("exitCode") if isinstance(tr, dict) else None
    if code is None:
        return "ok"
    try:
        return "ok" if int(code) == 0 else "fail"
    except (TypeError, ValueError):
        return "ok"


def normalize_in(data: dict, argv_event: str) -> tuple:
    """Map a Cursor payload onto the internal (Claude-shaped) contract. Returns ``(canonical_event, data)``.
    Mutates ``data`` in place (it is this process's only payload). Idempotent enough for one hook call."""
    ev_raw = str(data.get("hook_event_name") or argv_event or "")
    event = _CURSOR_TO_CANON.get(ev_raw.lower(), ev_raw)
    if not data.get("session_id"):                       # Cursor sends both; prefer session_id
        data["session_id"] = data.get("conversation_id") or "session"
    tn = str(data.get("tool_name") or "")
    if tn:
        data["tool_name"] = _TOOL_TO_CANON.get(tn.lower(), tn)
    if event in ("PostToolUse", "PostToolUseFailure") and "tool_response" not in data:
        data["tool_response"] = _parse_tool_output(data)
    return event, data


def serialize_out(out) -> tuple:
    """Internal decision dict → ``(cursor_output_or_None, exit_code)``. A hard veto becomes
    ``permission: "deny"`` **plus exit 2** (the explicit blocking path); 'ask' is emitted but is advisory
    (Cursor does not enforce it); 'allow'/None emit nothing meaningful. Injection → ``additional_context``."""
    if not out:
        return None, 0
    hso = out.get("hookSpecificOutput") or {}
    if "permissionDecision" in hso:
        dec = hso.get("permissionDecision")
        reason = hso.get("permissionDecisionReason", "")
        if dec == "deny":
            return {"permission": "deny", "user_message": reason, "agent_message": reason}, 2
        if dec == "ask":
            return {"permission": "ask", "user_message": reason, "agent_message": reason}, 0
        return {"permission": "allow"}, 0
    if "additionalContext" in hso:
        return {"additional_context": hso.get("additionalContext", "")}, 0
    return None, 0
