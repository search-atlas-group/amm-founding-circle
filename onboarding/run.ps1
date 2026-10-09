<#
Run the AMM onboarding audit the portal asked for. Safe to paste every time, from any folder:

  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/onboarding/run.ps1))) -Code <code> -Portal <portal address>

It installs anything missing (quickstart.ps1), finds your Founding Circle folder wherever it is (or downloads it to
~\amm-founding-circle the first time), keeps it and the AMM toolkit beside it up to date, then runs the audit. Only
rung statuses and counts are sent to your portal.

This runs as a pasted script block, not a file, so it stops with "return", never "exit": exit here would close the
member's PowerShell window before they could read why.
#>
param(
    [Parameter(Mandatory = $true)][string]$Code,
    [Parameter(Mandatory = $true)][string]$Portal
)

$ErrorActionPreference = "Stop"
$RawBase = "https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main"
$RepoUrl = "https://github.com/search-atlas-group/amm-founding-circle.git"
$ToolkitUrl = "https://github.com/search-atlas-group/amm-toolkit.git"
$DefaultDir = Join-Path $HOME "amm-founding-circle"

# Run git without letting its stderr stop the script. Windows PowerShell 5.1 turns any stderr line from a native
# command into an error record when stderr is redirected, and with ErrorActionPreference Stop that ends the run, even
# for a fetch that merely could not reach GitHub. Sets $script:GitOk from the exit code and returns stdout.
function Invoke-Git([string[]]$GitArgs) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & git @GitArgs 2>$null
        $script:GitOk = ($LASTEXITCODE -eq 0)
    } catch {
        $out = $null
        $script:GitOk = $false
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($out) { return ($out | Out-String).Trim() }
    return ""
}

# The PowerShell that is running this (powershell.exe or pwsh), so child scripts run on the same one. -ExecutionPolicy
# Bypass on the child is what lets a script file run on a stock Windows machine, whose policy is Restricted.
function Get-PowerShellExe {
    $self = (Get-Process -Id $PID).Path
    if ($self -and ((Split-Path -Leaf $self) -match '^(powershell|pwsh)(\.exe)?$')) { return $self }
    if (Get-Command pwsh -ErrorAction SilentlyContinue) { return "pwsh" }
    return "powershell"
}
$PsExe = Get-PowerShellExe

foreach ($tool in @("git")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "$tool is not installed. Install Git for Windows from https://git-scm.com/download/win, re-open PowerShell, then paste this again."
        return
    }
}

# Discover before setup; otherwise setup may create a duplicate at ~\amm-founding-circle.
function Test-Folder([string]$Path) {
    return [bool]($Path -and (Test-Path (Join-Path $Path "onboarding")) -and (Test-Path (Join-Path $Path ".git")))
}
function Find-Folder {
    foreach ($c in @($env:AMM_WORKSPACE, (Get-Location).Path, (Join-Path (Get-Location).Path "amm-founding-circle"))) {
        if (Test-Folder $c) { return $c }
    }
    $roots = @((Join-Path $HOME "Desktop"), (Join-Path $HOME "Documents"))
    $oneDrive = if ($env:OneDrive) { $env:OneDrive } else { Join-Path $HOME "OneDrive" }
    $roots += @((Join-Path $oneDrive "Desktop"), (Join-Path $oneDrive "Documents"))
    foreach ($root in $roots) {
        if (Test-Folder (Join-Path $root "amm-founding-circle")) { return (Join-Path $root "amm-founding-circle") }
        if (Test-Path $root) {
            foreach ($child in (Get-ChildItem -Directory -ErrorAction SilentlyContinue $root)) {
                $c = Join-Path $child.FullName "amm-founding-circle"
                if (Test-Folder $c) { return $c }
                foreach ($grandchild in (Get-ChildItem -Directory -ErrorAction SilentlyContinue $child.FullName)) {
                    $c = Join-Path $grandchild.FullName "amm-founding-circle"
                    if (Test-Folder $c) { return $c }
                }
            }
        }
    }
    foreach ($c in @((Join-Path $HOME "Developer\amm-founding-circle"), (Join-Path $HOME "Code\amm-founding-circle"), (Join-Path $HOME "code\amm-founding-circle"), $DefaultDir)) {
        if (Test-Folder $c) { return $c }
    }
    return $null
}
$dir = Find-Folder
if ($dir) { $env:AMM_WORKSPACE = $dir; Write-Host "Selected Founding Circle folder: $dir" }

# Everything happens from this one command: install anything missing, update the repos, then run the audit.
$quickstart = Join-Path ([System.IO.Path]::GetTempPath()) ("amm-quickstart-" + [guid]::NewGuid().ToString("N") + ".ps1")
try {
    Invoke-RestMethod "$RawBase/quickstart.ps1" -OutFile $quickstart
    & $PsExe -NoProfile -ExecutionPolicy Bypass -File $quickstart
    if ($LASTEXITCODE -ne 0) { Write-Host "Setup reported a problem (above). The audit still runs." }
} catch {
    Write-Host "Could not run setup ($($_.Exception.Message)). The audit still runs."
} finally {
    Remove-Item $quickstart -ErrorAction SilentlyContinue
}
# quickstart may have just installed Python or Git; pick up the new PATH without reopening the window.
$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($machinePath -or $userPath) {
    $env:Path = (@($env:Path, $machinePath, $userPath) | Where-Object { $_ }) -join [IO.Path]::PathSeparator
}

$dir = Find-Folder
if (-not $dir) {
    Write-Host "No valid Founding Circle clone found after setup. No folders were removed."
    return
}
Write-Host "Running audit from selected Founding Circle folder: $dir"
$parent = Split-Path -Parent $dir

# Setup check: the audit tells you what is missing and how to fix it. Nothing here stops the audit.
Write-Host "Checking your agentic setup:"
function Write-Have([string]$Name) { Write-Host "  [ok]      $Name" }
function Write-Miss([string]$Name, [string]$Fix) { Write-Host "  [missing] $Name"; Write-Host "            Fix: $Fix" }
if (Get-Command node -ErrorAction SilentlyContinue) { Write-Have "Node.js" } else { Write-Miss "Node.js" "install it from https://nodejs.org (LTS), then re-open PowerShell" }
if (Get-Command claude -ErrorAction SilentlyContinue) { Write-Have "Claude Code" } else { Write-Miss "Claude Code" "install it from the AMM toolkit setup (step 1 on the Onboarding page)" }
Write-Host "  [web]     Borg: there is no Windows app yet, use https://app.getborg.com"
$commandsRoot = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME ".claude" }
$commands = Join-Path $commandsRoot "commands"
if ((Test-Path $commands) -and (Get-ChildItem $commands -ErrorAction SilentlyContinue | Select-Object -First 1)) { Write-Have "SearchAtlas slash commands" } else { Write-Miss "SearchAtlas slash commands" "run step 1 on the Onboarding page" }
if (Test-Path (Join-Path $dir "shep\bin\shep")) { Write-Have "SHEP command deck (run it from Git Bash: ./shep/bin/shep --help)" } else { Write-Miss "SHEP command deck" "update the Founding Circle folder (paste this command again)" }
Write-Host ""

# Quickstart has already found or installed the toolkit beside the selected clone.
$tk = Join-Path $parent "amm-toolkit"
if (Test-Path (Join-Path $tk ".git")) { Write-Host "Toolkit folder: $tk" } else { Write-Host "Toolkit unavailable beside $dir; audit will still run." }
Write-Host ""

if (-not (Test-Path (Join-Path $dir "onboarding\portal.py"))) {
    Write-Host "This copy lacks onboarding/portal.py. Keep the folder; back up local work and seek help updating it. No folder was deleted."
    return
}
# A child PowerShell with -ExecutionPolicy Bypass: calling onboard.ps1 directly is blocked on a stock machine, whose
# execution policy (Restricted) refuses every script file.
& $PsExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dir "onboarding\onboard.ps1") -Run $Code -Portal $Portal
