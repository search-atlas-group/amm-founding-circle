<#
AMM Founding Circle — onboard this machine and see where you are on the ladder.
Windows-native entrypoint (no Git Bash / WSL required).

  .\onboarding\onboard.ps1                       scan, then open your readout
  .\onboarding\onboard.ps1 -Ask                  also answer what a scan can't see
  .\onboarding\onboard.ps1 -InstallSkills        install this repo's skills first
  .\onboarding\onboard.ps1 -Share jane-smith     write a file you can send to JD
  .\onboarding\onboard.ps1 -NoOpen               don't auto-open the readout

Everything is presence-only: it checks whether files and commands exist, never
what is inside them. Nothing is uploaded. Safe to run as many times as you like.

If PowerShell blocks this script from running, either right-click it and choose
"Run with PowerShell", or run once in this terminal:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

[CmdletBinding()]
param(
    [switch]$Ask,
    [switch]$InstallSkills,
    [string]$Share = "",
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Split-Path -Parent $Here

# --- step 0: preflight — find a python3 ------------------------------------
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
        if (Test-PyCandidate $candidate) { return $candidate }
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

Write-Host "AMM Founding Circle — ladder check"
Write-Host "repo: $Repo"
Write-Host ""

# --- step 1: skills (optional) ----------------------------------------------
if ($InstallSkills) {
    $installSh = Join-Path $Repo "skills\install.sh"
    if (Test-Path $installSh) {
        Write-Host "Installing this repo's skills..."
        $bash = Get-Command bash -ErrorAction SilentlyContinue
        if ($bash) {
            & bash $installSh
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
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Re-run this any time -- it is the same command after every change you make,"
Write-Host "or just ask your agent: `"run my AMM ladder audit`"."
Write-Host ""
Write-Host "Note: the every-2-hours auto-update (-AutoUpdate on onboard.sh) is a macOS/Linux"
Write-Host "feature for now. On Windows, just re-run this script by hand after a git pull."
