"""PowerShell-aware somatic recognizer (issue #12) — the non-pinned half.

Drives ``exocortex/somatic_ps.py`` DIRECTLY (it is importable-but-unwired by design; the
hook.py routing is under the ADR-016 pin and out of scope). Covers each of the five scar
families in PS idiom, alias + abbreviation forms, ``-EncodedCommand`` unwrapping, and the
must-NOT-fire benign controls — plus a guard that the module stays unwired.

OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_somatic_ps.py
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex import somatic_ps as S                                    # noqa: E402


LETHAL = [
    # kill PID 1 / host-critical process
    "Stop-Process -Id 1 -Force",
    "spps -Id 1",
    "kill -Id 1",
    "Stop-Process -Name lsass",
    "taskkill /pid 1 /f",
    # wipe root fs (cmdlet + aliases + abbreviations)
    "Remove-Item -Recurse -Force /",
    "Remove-Item -Recurse -Force C:\\",
    r"ri -r -fo C:\*",
    "rm -Force -Recurse /",
    r"Remove-Item -Recurse -Force $env:SystemDrive\\",
    "Format-Volume -DriveLetter C",
    "Clear-Disk -Number 0",
    # firewall flush
    "Remove-NetFirewallRule",
    "netsh advfirewall reset",
    "Set-NetFirewallProfile -All -Enabled false",
    # host shutdown
    "Stop-Computer -Force",
    "Restart-Computer",
    "shutdown.exe /r /t 0",
    # fork bomb
    "while ($true) { Start-Process powershell }",
]

BENIGN = [
    "Get-ChildItem -Recurse -Force .",
    "Remove-Item -Recurse -Force .\\build",          # a project subdir, not the root
    "Stop-Process -Id 4821",                         # some app, not PID 1
    "Stop-Process -Name notepad",
    "Remove-NetFirewallRule -DisplayName 'My App'",  # a NAMED rule, not a flush
    "Set-NetFirewallProfile -Enabled true",
    "Restart-Service -Name Spooler",                 # a service, not the computer
    "git status",
]
# NOTE: `Write-Output 'shutdown the meeting'` is NOT in BENIGN — the shared Bash C1 list matches
# the bare word `shutdown` anywhere (a deliberately conservative innate scar), and classify_ps
# falls through to it. That over-trigger is existing kernel behavior this module inherits, not
# something the PS half should silently override; narrowing C1 is a separate, pinned decision.


@pytest.mark.parametrize("cmd", LETHAL)
def test_lethal_ps_is_recognized(cmd):
    assert S.is_lethal_ps(cmd) is True, cmd
    assert S.match_scar(cmd) is not None, cmd


@pytest.mark.parametrize("cmd", BENIGN)
def test_benign_ps_is_not_vetoed(cmd):
    assert S.is_lethal_ps(cmd) is False, cmd
    assert S.match_scar(cmd) is None, cmd


def test_encoded_command_is_unwrapped_and_caught():
    payload = "Stop-Computer -Force"
    b64 = base64.b64encode(payload.encode("utf-16-le")).decode("ascii")
    cmd = f"powershell -EncodedCommand {b64}"
    assert S.is_lethal_ps(cmd) is True
    assert S.match_scar(cmd) == "shutdown/cmdlet"


def test_encoded_short_alias_forms_unwrap():
    payload = "Remove-Item -Recurse -Force /"
    b64 = base64.b64encode(payload.encode("utf-16-le")).decode("ascii")
    for flag in ("-enc", "-ec"):
        assert S.is_lethal_ps(f"pwsh {flag} {b64}") is True, flag


def test_bash_lethal_still_lethal_through_the_ps_classifier():
    """A wsl/bash lethal routed through the PS classifier is not laundered benign — it falls
    through to the C1 Bash list."""
    assert S.is_lethal_ps("wsl rm -rf /") is True


def test_scar_label_is_stable_for_telemetry():
    assert S.match_scar("Remove-Item -Recurse -Force /") == "destroy/rootfs"
    assert S.match_scar("Stop-Process -Id 1") == "kill/pid1"


def test_module_is_wired_into_the_pretooluse_gate():
    """ADR-021 (2026-07-22): the recognizer is WIRED — the routing edit cleared the ADR-016 bar
    (safety argument + PI approval + recorded pin re-baseline). Inverts the former
    ``test_module_is_unwired_hook_does_not_import_it``, which pinned the pre-wiring state."""
    hook_src = (_ROOT / "exocortex" / "hook.py").read_text(encoding="utf-8")
    assert "somatic_ps" in hook_src
    assert "is_lethal_ps" in hook_src


def test_wiring_is_the_somatic_half_only():
    """Scope pin: PowerShell gets the somatic veto, NOT the epistemic layer or energy accounting —
    those stay Bash-only. Guards against the wiring quietly widening later."""
    hook_src = (_ROOT / "exocortex" / "hook.py").read_text(encoding="utf-8")
    ps_block = hook_src.split('if tool != "Bash":', 1)[1].split('cmd = _bash_command(data)', 1)[0]
    assert "epi.assess" not in ps_block
    assert "SessionState.load" not in ps_block
