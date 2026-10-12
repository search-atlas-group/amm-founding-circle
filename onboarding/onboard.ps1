<#
AMM Founding Circle: onboard this machine and see where you are on the ladder.
Windows-native entrypoint (no Git Bash / WSL required).

  .\onboarding\onboard.ps1                       scan, then open your readout
  .\onboarding\onboard.ps1 -Ask                  also answer what a scan can't see
  .\onboarding\onboard.ps1 -InstallSkills        install this repo's skills first
  .\onboarding\onboard.ps1 -Share jane-smith     write a file you can send to JD
  .\onboarding\onboard.ps1 -NoOpen               don't auto-open the readout
  .\onboarding\onboard.ps1 -Connect -Portal <address>   link this machine to the AMM portal
  .\onboarding\onboard.ps1 -Publish [-Yes]     scan, then send your result to the portal
  .\onboarding\onboard.ps1 -Pair <code> -Portal <address>   connect with the portal's one-time code, keep listening
  .\onboarding\onboard.ps1 -Run <code> -Portal <address>   run the audit the portal asked for, once
  .\onboarding\onboard.ps1 -Listen              wait for the portal's Run audit button (Ctrl+C stops)
  .\onboarding\onboard.ps1 -Disconnect         forget the portal token

Everything is presence-only: it checks whether files and commands exist, never
what is inside them. The scan makes no network call; only -Connect and
-Publish do, and only when you type them. Safe to run as many times as you like.

If PowerShell blocks this script from running, either right-click it and choose
"Run with PowerShell", or run once in this terminal:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

[CmdletBinding()]
param(
    [switch]$Ask,
    [switch]$InstallSkills,
    [string]$Share = "",
    [switch]$NoOpen,
    [switch]$Connect,
    [switch]$Disconnect,
    [switch]$Publish,
    [switch]$Yes,
    [string]$Portal = "",
    [string]$Pair = "",
    [string]$Run = "",
    [switch]$RunSaved,
    [switch]$Listen,
    [switch]$NoBackground
)

$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Split-Path -Parent $Here

# --- step 0: preflight: find a python3 -------------------------------------
# Get-Command alone is not enough: a bare Windows install without Python ships
# a "python"/"python3" App Execution Alias stub that Get-Command finds fine but
# which just pops the Microsoft Store and exits nonzero. Actually run --version.
function Test-PyCandidate {
    param([string[]]$Invocation)
    $exe = $Invocation[0]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $false }
    try {
        $rest = @()
        if ($Invocation.Length -gt 1) { $rest = $Invocation[1..($Invocation.Length - 1)] }
        & $exe @rest --version *> $null 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-Python {
    foreach ($candidate in @(@("python3"), @("py", "-3"), @("python"))) {
        # The leading comma keeps a one-element candidate an array: PowerShell unrolls a returned
        # @("python3") to the string "python3", and $PyCmd[0] would then be "p".
        if (Test-PyCandidate $candidate) { return ,$candidate }
    }
    return $null
}

$PyCmd = Find-Python
if (-not $PyCmd) {
    Write-Host "python3 is not installed." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Install Python from https://python.org/downloads (check 'Add python.exe to PATH')"
    Write-Host "  then re-open this terminal and run this script again."
    Write-Host ""
    Write-Host "That is the only thing this needs."
    exit 69
}

function Run-Py {
    param([string[]]$PyArgs)
    if ($PyCmd.Count -gt 1) {
        & $PyCmd[0] $PyCmd[1] @PyArgs
    } else {
        & $PyCmd[0] @PyArgs
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# --- portal connection (no scan) --------------------------------------------
$ConnectorTask = "AMM portal connector"
if ($Disconnect) {
    Unregister-ScheduledTask -TaskName $ConnectorTask -Confirm:$false -ErrorAction SilentlyContinue
    Push-Location $Here
    try { Run-Py @("portal.py", "--disconnect") } finally { Pop-Location }
    exit 0
}
if ($Pair -ne "") {
    Push-Location $Here
    try {
        if ($Portal -ne "") { Run-Py @("portal.py", "--pair", $Pair, "--portal", $Portal) }
        else { Run-Py @("portal.py", "--pair", $Pair) }
    } finally { Pop-Location }
    if (-not $NoBackground) {
        try {
            # Task Scheduler does not search PATH the way this terminal does, so give it the full path. Prefer the
            # windowless pythonw/pyw beside it so a console window does not sit open at every logon.
            $exe = (Get-Command $PyCmd[0] -CommandType Application | Select-Object -First 1).Source
            $quiet = Join-Path (Split-Path -Parent $exe) ($(if ($PyCmd[0] -eq "py") { "pyw.exe" } else { "pythonw.exe" }))
            if (Test-Path $quiet) { $exe = $quiet }
            $argList = if ($PyCmd.Count -gt 1) { "$($PyCmd[1]) `"$Here\portal.py`" --listen" } else { "`"$Here\portal.py`" --listen" }
            $action = New-ScheduledTaskAction -Execute $exe -Argument $argList -WorkingDirectory $Here
            # A logon trigger for every user needs admin rights; one for this user does not.
            $me = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
            $trigger = New-ScheduledTaskTrigger -AtLogOn -User $me
            $principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited
            Register-ScheduledTask -TaskName $ConnectorTask -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
            Start-ScheduledTask -TaskName $ConnectorTask
            Write-Host "All set. Press Run audit in the portal any time this computer is on."
            exit 0
        } catch {
            Write-Host "Could not install the background connector ($($_.Exception.Message))."
        }
    }
    Write-Host "Keep this window open: it is the connector. Press Run audit in the portal."
    Push-Location $Here
    try { Run-Py @("portal.py", "--listen") } finally { Pop-Location }
    exit 0
}
if ($Run -ne "" -or $RunSaved) {
    Push-Location $Here
    try {
        $a = @("portal.py", "--run")
        if ($Run -ne "") { $a += $Run }
        if ($Portal -ne "") { $a += @("--portal", $Portal) }
        Run-Py $a
    } finally { Pop-Location }
    exit 0
}
if ($Listen) {
    Push-Location $Here
    try { Run-Py @("portal.py", "--listen") } finally { Pop-Location }
    exit 0
}
if ($Connect) {
    Push-Location $Here
    try {
        if ($Portal -ne "") { Run-Py @("portal.py", "--connect", "--portal", $Portal) }
        else { Run-Py @("portal.py", "--connect") }
    } finally { Pop-Location }
    exit 0
}

# --- publish preflight: fail before the audit if not connected ---------------
if ($Publish) {
    Push-Location $Here
    try { Run-Py @("portal.py", "--preflight") } finally { Pop-Location }
}

Write-Host "AMM Founding Circle: ladder check"
Write-Host "repo: $Repo"
Write-Host ""

# --- step 1: skills (optional) ----------------------------------------------
if ($InstallSkills) {
    $installSh = Join-Path $Repo "skills\install.sh"
    if (Test-Path $installSh) {
        Write-Host "Installing this repo's skills..."
        # A bare "bash" can resolve to WSL's System32\bash.exe, which cannot see this Windows home folder the same
        # way. Prefer the bash.exe that ships with Git for Windows, found from git.exe itself.
        $bash = $null
        $gitCmd = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($gitCmd) {
            $gitRoot = Split-Path -Parent (Split-Path -Parent $gitCmd.Source)
            foreach ($p in @("bin\bash.exe", "usr\bin\bash.exe")) {
                if (Test-Path (Join-Path $gitRoot $p)) { $bash = Join-Path $gitRoot $p; break }
            }
        }
        if (-not $bash) {
            $found = Get-Command bash -CommandType Application -ErrorAction SilentlyContinue |
                Where-Object { $_.Source -notlike "*\System32\*" -and $_.Source -notlike "*\WindowsApps\*" } | Select-Object -First 1
            if ($found) { $bash = $found.Source }
        }
        if ($bash) {
            & $bash $installSh
            if ($LASTEXITCODE -ne 0) { Write-Host "  (skill install reported a problem -- the scan still works)" }
        } else {
            Write-Host "  (skills/install.sh needs bash -- install Git for Windows, or run -InstallSkills from Git Bash instead. The scan still works without it.)"
        }
        Write-Host ""
    } else {
        Write-Host "No skills/install.sh found -- skipping."
        Write-Host ""
    }
}

# --- step 2: scan ------------------------------------------------------------
Push-Location $Here
try {
    if ($Ask) {
        Run-Py @("ladder_probe.py", "--ask")
    } else {
        Run-Py @("ladder_probe.py")
    }

    # --- step 3: readout -----------------------------------------------------
    Write-Host ""
    if (-not $NoOpen) {
        Run-Py @("report.py", "--open")
    } else {
        Run-Py @("report.py")
    }

    # --- step 4: share (opt-in) ------------------------------------------------
    if ($Share -ne "") {
        Write-Host ""
        Run-Py @("share.py", $Share)
    }

    # --- step 5: publish to the portal (opt-in) ----------------------------
    if ($Publish) {
        Write-Host ""
        if ($Yes) { Run-Py @("portal.py", "--publish", "--yes") }
        else { Run-Py @("portal.py", "--publish") }
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Re-run this any time -- it is the same command after every change you make,"
Write-Host "or just ask your agent: `"run my AMM ladder audit`"."
Write-Host ""
Write-Host "Note: the every-2-hours auto-update (-AutoUpdate on onboard.sh) is a macOS/Linux"
Write-Host "feature for now. On Windows, just re-run this script by hand after a git pull."
