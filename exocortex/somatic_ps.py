"""PowerShell-aware somatic recognizer — the NON-PINNED half (issue #12).

The somatic veto vocabulary is Bash-shaped; on Windows hosts PowerShell commands are audited
but not vetoed (the disclosed "Honest scope"). This module translates the existing veto
vocabulary — kill-PID-1, wipe-the-root-fs, flush-the-firewall, host shutdown, fork bomb — to
PowerShell idiom: cmdlet forms, alias forms (``rm``/``del``/``ri``/``kill``/``spps``), common
parameter abbreviations, and ``-EncodedCommand`` unwrapping.

**Deliberately importable-but-UNWIRED.** The routing edit in ``hook.py`` is under the ADR-016
control-plane pin and is explicitly out of scope here; tests drive this module directly
(``exocortex/tests/test_somatic_ps.py`` pins the unwired state). Like the C1 list it mirrors,
recognition is structural — regex over the command's shape, never a judgment call — and the
scar list is a closed vocabulary: additions belong in review, not in config.

Honest scope of the recognizer itself: parameter abbreviations are matched for the common
explicit spellings (``-Recurse``/``-r``, ``-Force``/``-fo``); more exotic-but-legal prefixes
(``-Recur``) are not enumerated. Splatting, variable indirection (``& $cmd``), and
``Invoke-Expression`` of computed strings are structurally unrecognizable by ANY static
vocabulary — that residual is exactly why the audited-not-vetoed disclosure stays in place
until the outcome oracle covers it.
"""
from __future__ import annotations

import base64
import re

from sentaince.organism.action_graph import Risk, classify as classify_bash

# ---------------------------------------------------------------------------- encoded unwrap
_ENCODED = re.compile(r"-(?:EncodedCommand|enc|ec|e)\s+([A-Za-z0-9+/=]{8,})", re.IGNORECASE)
_MAX_UNWRAP_DEPTH = 3


def unwrap(command: str, max_depth: int = _MAX_UNWRAP_DEPTH) -> str:
    """Decode ``powershell -EncodedCommand <b64>`` layers (UTF-16LE, bounded depth) and return
    the fully unwrapped text with each decoded layer APPENDED — the recognizer then sees both
    the wrapper and the payload. Decode failures are ignored (the wrapper text still stands)."""
    text = str(command or "")
    for _ in range(max_depth):
        m = _ENCODED.search(text)
        if not m:
            break
        try:
            decoded = base64.b64decode(m.group(1), validate=True).decode("utf-16-le", "strict")
        except Exception:
            break
        text = text[:m.start()] + " " + decoded + " " + text[m.end():]
    return text


# ---------------------------------------------------------------------------- the PS scar list
# Segment = up to a pipe/semicolon/newline — flags must belong to the same command invocation.
_SEG = r"[^|;\n]*"
# Root-fs targets: bare / or \, a bare drive root (C:\ or C:/), or $env:SystemDrive\.
_ROOT = r"(?:['\"]?(?:[A-Za-z]:)?[\\/]\*?['\"]?(?=\s|$)|\$env:SystemDrive[\\/]?)"
_RECURSE = r"-r(?:ecurse)?\b"
_FORCE = r"-fo(?:rce)?\b"

PS_SCARS: tuple[tuple[str, re.Pattern], ...] = (
    # 1) kill PID 1 / euthanize a host-critical process
    ("kill/pid1", re.compile(
        rf"\b(?:Stop-Process|spps|kill)\b{_SEG}-Id\s+1\b", re.IGNORECASE)),
    ("kill/critical-process", re.compile(
        rf"\b(?:Stop-Process|spps|kill)\b{_SEG}-Name\s+['\"]?(?:wininit|csrss|lsass|smss)\b",
        re.IGNORECASE)),
    ("kill/pid1-taskkill", re.compile(
        r"\btaskkill(?:\.exe)?\b[^|;\n]*/pid\s+1\b", re.IGNORECASE)),
    # 2) wipe the root fs
    ("destroy/rootfs", re.compile(
        rf"\b(?:Remove-Item|ri|rm|rmdir|rd|del|erase)\b(?={_SEG}{_RECURSE})(?={_SEG}{_FORCE}){_SEG}{_ROOT}",
        re.IGNORECASE)),
    ("destroy/format-systemdrive", re.compile(
        rf"\bFormat-Volume\b{_SEG}-DriveLetter\s+['\"]?C\b", re.IGNORECASE)),
    ("destroy/clear-disk", re.compile(r"\bClear-Disk\b", re.IGNORECASE)),
    ("destroy/format-c", re.compile(r"\bformat(?:\.com)?\s+C:", re.IGNORECASE)),
    # 3) flush the firewall
    ("firewall/flush-rules", re.compile(
        r"\bRemove-NetFirewallRule\b(?![^|;\n]*-(?:DisplayName|Name|DisplayGroup|PolicyStore))",
        re.IGNORECASE)),
    ("firewall/netsh-flush", re.compile(
        r"\bnetsh\s+advfirewall\s+(?:reset\b|firewall\s+delete\s+rule\s+name=all)", re.IGNORECASE)),
    ("firewall/disable-profile", re.compile(
        r"\bSet-NetFirewallProfile\b[^|;\n]*-Enabled\s+(?:\$?false|0)\b", re.IGNORECASE)),
    # 4) host shutdown / reboot
    ("shutdown/cmdlet", re.compile(r"\b(?:Stop-Computer|Restart-Computer)\b", re.IGNORECASE)),
    ("shutdown/exe", re.compile(r"\bshutdown(?:\.exe)?\s+/(?:s|r|p)\b", re.IGNORECASE)),
    # 5) fork bomb (unbounded self-spawn)
    ("forkbomb/while-true", re.compile(
        r"while\s*\(\s*\$true\s*\)[^\n]*Start-Process\b[^\n]*(?:powershell|pwsh|cmd)",
        re.IGNORECASE)),
    ("forkbomb/for-ever", re.compile(
        r"for\s*\(\s*;\s*;\s*\)[^\n]*Start-Process\b", re.IGNORECASE)),
)


# ---------------------------------------------------------------------------- API (mirrors somatic.py)
def match_scar(command: str) -> str | None:
    """The name of the first PS scar the (unwrapped) command matches, or None — the
    audit/telemetry label, parity with ``somatic.sig_label``."""
    text = unwrap(command)
    for name, pat in PS_SCARS:
        if pat.search(text):
            return name
    return None


def classify_ps(command: str) -> Risk:
    """LETHAL iff the unwrapped command matches a PS scar — or the Bash-shaped C1 list (an
    encoded/`wsl`-wrapped Bash lethal is still lethal). Structure only, same contract as
    ``action_graph.classify``."""
    text = unwrap(command)
    if any(pat.search(text) for _, pat in PS_SCARS):
        return Risk.LETHAL
    return classify_bash(text)


def is_lethal_ps(command: str) -> bool:
    """True iff the command is recognized lethal in PowerShell idiom (or unwraps to a
    recognized Bash lethal). The PS mirror of ``somatic.is_lethal``."""
    return classify_ps(command) is Risk.LETHAL
