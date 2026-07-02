#Requires -Version 5
<#
  Remove the "Exocortex testbed" logon Scheduled Task. The containers keep their restart policy
  (restart: unless-stopped) until you run `docker compose ... down`.
#>
$name = 'Exocortex testbed'
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Output "Removed scheduled task '$name'."
} else {
    Write-Output "No scheduled task '$name' found (nothing to do)."
}
