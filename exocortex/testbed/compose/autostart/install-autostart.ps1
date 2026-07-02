#Requires -Version 5
<#
  Register a per-user logon Scheduled Task that keeps the Exocortex testbed stack up across reboots.
  Runs as the current interactive user (no elevation needed for a self-scoped logon task).
  Undo with uninstall-autostart.ps1.
#>
$ErrorActionPreference = 'Stop'

$script = (Resolve-Path (Join-Path $PSScriptRoot 'exocortex-testbed-up.ps1')).Path
$name   = 'Exocortex testbed'
$user   = "$env:USERDOMAIN\$env:USERNAME"

$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force `
    -Description 'Start/ensure the Exocortex testbed (exporter + Prometheus + Grafana) at logon.' | Out-Null

Write-Output "Registered scheduled task '$name' -> runs '$script' at logon for $user."
Write-Output "Test now:  Start-ScheduledTask -TaskName '$name'   (or just run exocortex-testbed-up.ps1)"
