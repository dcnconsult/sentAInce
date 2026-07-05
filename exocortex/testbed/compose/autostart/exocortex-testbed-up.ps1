#Requires -Version 5
<#
  Ensure the Exocortex testbed stack (exporter + Prometheus + Grafana) is running.
  Idempotent: starts Docker Desktop if the engine is down, waits for it, then `compose up -d`.
  Invoked at logon by the "Exocortex testbed" scheduled task (see install-autostart.ps1).
  Safe to run by hand any time:  pwsh -File exocortex-testbed-up.ps1
#>
$ErrorActionPreference = 'SilentlyContinue'

# Project DIRECTORY, not a single -f file: compose must discover docker-compose.yml AND any local
# docker-compose.override.yml (an explicit -f suppresses the auto-merge, silently dropping
# machine-local mounts such as out-of-scan-root repos).
$composeDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$log     = Join-Path $env:LOCALAPPDATA 'exocortex-testbed-autostart.log'   # outside the repo
function Log($m) { "$([DateTime]::Now.ToString('s'))  $m" | Out-File -FilePath $log -Append -Encoding utf8 }

Log "ensure-up start (composeDir=$composeDir)"

# 1. Engine reachable? If not, launch Docker Desktop.
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dd = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (Test-Path $dd) { Log 'engine down -> starting Docker Desktop'; Start-Process $dd | Out-Null }
    else { Log "Docker Desktop.exe not found at $dd"; exit 1 }
}

# 2. Wait up to 5 minutes for the engine to accept commands.
$deadline = (Get-Date).AddMinutes(5)
do {
    Start-Sleep -Seconds 6
    docker info *> $null
} until ($LASTEXITCODE -eq 0 -or (Get-Date) -gt $deadline)

if ($LASTEXITCODE -ne 0) { Log 'engine not ready before deadline; giving up'; exit 1 }

# 3. Bring the stack up (idempotent — a no-op if already running).
Log 'engine ready -> docker compose up -d'
docker compose --project-directory $composeDir up -d *>> $log
Log "ensure-up done (exit $LASTEXITCODE)"
exit $LASTEXITCODE
