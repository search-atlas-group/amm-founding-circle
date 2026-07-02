# Register the overnight runner as a Windows Scheduled Task.
# The installer calls this for you on Windows, but you can run it directly too:
#
#   powershell -ExecutionPolicy Bypass -File register-task-windows.ps1 `
#       -Runner "C:\path\to\overnight_runner.py" `
#       -Job "C:\path\to\my-job.sh" `
#       -At "01:00" `
#       -Minutes 45
#
# Remove it later with:
#   Unregister-ScheduledTask -TaskName "YourAgentOvernight" -Confirm:$false

param(
    [Parameter(Mandatory = $true)][string]$Runner,
    [Parameter(Mandatory = $true)][string]$Job,
    [string]$At = "01:00",
    [int]$Minutes = 45,
    [string]$TaskName = "YourAgentOvernight"
)

$ErrorActionPreference = "Stop"

# Find python — prefer the launcher, fall back to python3/python on PATH.
$python = (Get-Command py -ErrorAction SilentlyContinue)?.Source
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue)?.Source }
if (-not $python) { $python = (Get-Command python -ErrorAction SilentlyContinue)?.Source }
if (-not $python) { throw "python not found on PATH. Install Python 3 first." }

$args = "`"$Runner`" --job `"$Job`" --minutes $Minutes"
$action  = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -Daily -At $At

# WakeToRun so a sleeping machine wakes for the run; keep it bounded.
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes ($Minutes + 5)) `
    -DontStopOnIdleEnd

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Runs your overnight agent job on a schedule (host-your-agent skill)." | Out-Null

Write-Host "Registered scheduled task '$TaskName' — runs daily at $At for up to $Minutes min."
Write-Host "Check it:   Get-ScheduledTask -TaskName $TaskName"
Write-Host "Run now:    Start-ScheduledTask -TaskName $TaskName"
Write-Host "Remove it:  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
