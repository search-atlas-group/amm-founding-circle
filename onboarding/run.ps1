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

function Test-Folder([string]$Path) {
    return $Path -and (Test-Path (Join-Path $Path "onboarding")) -and (Test-Path (Join-Path $Path ".git"))
}

# OneDrive's folder backup moves Desktop and Documents under %OneDrive%, so look there too.
$roots = @((Join-Path $HOME "Desktop"), (Join-Path $HOME "Documents"))
if ($env:OneDrive) { $roots += @((Join-Path $env:OneDrive "Desktop"), (Join-Path $env:OneDrive "Documents")) }
$candidates = @($env:AMM_FOUNDING_CIRCLE_DIR, (Get-Location).Path, (Join-Path (Get-Location).Path "amm-founding-circle"), $DefaultDir,
    (Join-Path $HOME "Developer\amm-founding-circle"), (Join-Path $HOME "Code\amm-founding-circle"))
foreach ($root in $roots) {
    $candidates += Join-Path $root "amm-founding-circle"
    $candidates += Get-ChildItem -Directory -ErrorAction SilentlyContinue $root |
        ForEach-Object { Join-Path $_.FullName "amm-founding-circle" }
}

$dir = $null
foreach ($c in $candidates) { if (Test-Folder $c) { $dir = $c; break } }

if (-not $dir) {
    Write-Host "Downloading the Founding Circle folder to $DefaultDir ..."
    Invoke-Git @("clone", "-q", $RepoUrl, $DefaultDir) | Out-Null
    if (-not $script:GitOk) {
        Write-Host "Could not download the Founding Circle folder. Check your internet connection, then paste this again."
        return
    }
    $dir = $DefaultDir
    $parent = Split-Path -Parent $dir
} else {
    Write-Host "Using your Founding Circle folder: $dir"
    $parent = Split-Path -Parent $dir
    # Guarantee the latest: fetch, fast-forward, then verify the folder matches GitHub's main. If something of the
    # member's own blocks the update, never run the stale copy: run a clean copy of the latest instead.
    Invoke-Git @("-C", $dir, "fetch", "-q", "origin", "main") | Out-Null
    if (-not $script:GitOk) {
        Write-Host "Could not reach GitHub to check for updates. Running the version you have."
    } else {
        Invoke-Git @("-C", $dir, "merge", "--ff-only", "-q", "origin/main") | Out-Null
        $head = Invoke-Git @("-C", $dir, "rev-parse", "HEAD")
        $latest = Invoke-Git @("-C", $dir, "rev-parse", "origin/main")
        if ($head -and $head -eq $latest) {
            Write-Host "Up to date ($($head.Substring(0,7)))."
        } else {
            Write-Host "Your folder has changes of your own that block the update, so it was left alone."
            $fresh = Join-Path ([System.IO.Path]::GetTempPath()) ("amm-fc-" + [guid]::NewGuid().ToString("N"))
            Invoke-Git @("clone", "-q", "--depth", "1", "--branch", "main", $RepoUrl, $fresh) | Out-Null
            if ($script:GitOk) {
                $dir = $fresh
                Write-Host "Running a clean copy of the latest ($($latest.Substring(0,7)))."
            } else {
                Write-Host "Could not download a clean copy. Running the version you have."
            }
        }
    }
}

# Setup check: the audit tells you what is missing and how to fix it. Nothing here stops the audit.
Write-Host "Checking your agentic setup:"
function Write-Have([string]$Name) { Write-Host "  [ok]      $Name" }
function Write-Miss([string]$Name, [string]$Fix) { Write-Host "  [missing] $Name"; Write-Host "            Fix: $Fix" }
if (Get-Command node -ErrorAction SilentlyContinue) { Write-Have "Node.js" } else { Write-Miss "Node.js" "install it from https://nodejs.org (LTS), then re-open PowerShell" }
if (Get-Command claude -ErrorAction SilentlyContinue) { Write-Have "Claude Code" } else { Write-Miss "Claude Code" "install it from the AMM toolkit setup (step 1 on the Onboarding page)" }
Write-Host "  [web]     Borg: there is no Windows app yet, use https://app.getborg.com"
$commands = Join-Path $HOME ".claude\commands"
if ((Test-Path $commands) -and (Get-ChildItem $commands -ErrorAction SilentlyContinue | Select-Object -First 1)) { Write-Have "SearchAtlas slash commands" } else { Write-Miss "SearchAtlas slash commands" "run step 1 on the Onboarding page" }
if (Test-Path (Join-Path $dir "shep\bin\shep")) { Write-Have "SHEP command deck (run it from Git Bash: ./shep/bin/shep --help)" } else { Write-Miss "SHEP command deck" "update the Founding Circle folder (paste this command again)" }
Write-Host ""

# The toolkit (slash commands, setup) lives beside the Founding Circle. Same guarantee: clone it if missing, else
# bring it up to date. It never blocks the audit.
$tk = Join-Path $parent "amm-toolkit"
if (Test-Path (Join-Path $tk ".git")) {
    Invoke-Git @("-C", $tk, "fetch", "-q", "origin", "main") | Out-Null
    if ($script:GitOk) { Invoke-Git @("-C", $tk, "merge", "--ff-only", "-q", "origin/main") | Out-Null }
    $tkHead = Invoke-Git @("-C", $tk, "rev-parse", "HEAD")
    $tkLatest = Invoke-Git @("-C", $tk, "rev-parse", "origin/main")
    if ($tkHead -and $tkHead -eq $tkLatest) { Write-Host "Toolkit up to date ($($tkHead.Substring(0,7)))." } else { Write-Host "Toolkit left as it is (your own changes, or GitHub unreachable)." }
} else {
    Write-Host "Downloading the AMM toolkit to $tk ..."
    Invoke-Git @("clone", "-q", $ToolkitUrl, $tk) | Out-Null
    if ($script:GitOk) { Write-Host "Toolkit ready." } else { Write-Host "Could not download the toolkit. The audit still runs." }
}
Write-Host ""

if (-not (Test-Path (Join-Path $dir "onboarding\portal.py"))) {
    Write-Host "This copy is too old and could not be updated. Delete it and paste the command again to download a fresh one."
    return
}
# A child PowerShell with -ExecutionPolicy Bypass: calling onboard.ps1 directly is blocked on a stock machine, whose
# execution policy (Restricted) refuses every script file.
& $PsExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $dir "onboarding\onboard.ps1") -Run $Code -Portal $Portal
