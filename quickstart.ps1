# AMM Founding Circle quickstart for Windows PowerShell.
# Usage: irm https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.ps1 | iex
# The portal's Run audit command (onboarding/run.ps1) runs this first, in its own PowerShell, before the audit.
# Set AMM_NO_OPEN=1 to skip opening Borg's installer and a Herdr window (headless runs and tests).
$ErrorActionPreference = "Stop"
$FcUrl = "https://github.com/search-atlas-group/amm-founding-circle.git"
$HerdrInstallUrl = "https://herdr.dev/install.ps1"
$WarpDownloadPage = "https://www.warp.dev/download"
$BorgWinUrl = "https://download.getborg.com/Borg-0.0.79-win-x64.exe"
$MothershipDir = if ($env:AMM_MOTHERSHIP_ROOT) { $env:AMM_MOTHERSHIP_ROOT } else { Join-Path $HOME "amm-mothership" }
$WorkspaceDir = if ($env:AMM_WORKSPACE) { $env:AMM_WORKSPACE } else { Join-Path $MothershipDir "founding-circle" }
function Test-FcFolder([string]$Path) {
    return [bool]($Path -and (Test-Path (Join-Path $Path ".git")) -and (Test-Path (Join-Path $Path "onboarding")))
}
function Find-FcFolder {
    foreach ($candidate in @($env:AMM_WORKSPACE, (Get-Location).Path, (Join-Path (Get-Location).Path "amm-founding-circle"), (Join-Path $MothershipDir "founding-circle"))) {
        if (Test-FcFolder $candidate) { return $candidate }
    }
    $roots = @((Join-Path $HOME "Desktop"), (Join-Path $HOME "Documents"))
    $oneDrive = if ($env:OneDrive) { $env:OneDrive } else { Join-Path $HOME "OneDrive" }
    $roots += @((Join-Path $oneDrive "Desktop"), (Join-Path $oneDrive "Documents"))
    foreach ($root in $roots) {
        if (Test-FcFolder (Join-Path $root "amm-founding-circle")) { return (Join-Path $root "amm-founding-circle") }
        if (Test-Path $root) {
            foreach ($child in (Get-ChildItem -Directory -ErrorAction SilentlyContinue $root)) {
                $candidate = Join-Path $child.FullName "amm-founding-circle"
                if (Test-FcFolder $candidate) { return $candidate }
                foreach ($grandchild in (Get-ChildItem -Directory -ErrorAction SilentlyContinue $child.FullName)) {
                    $candidate = Join-Path $grandchild.FullName "amm-founding-circle"
                    if (Test-FcFolder $candidate) { return $candidate }
                }
            }
        }
    }
    foreach ($candidate in @((Join-Path $HOME "Developer\amm-founding-circle"), (Join-Path $HOME "Code\amm-founding-circle"), (Join-Path $HOME "code\amm-founding-circle"), (Join-Path $HOME "amm-founding-circle"))) {
        if (Test-FcFolder $candidate) { return $candidate }
    }
    return $null
}
function Update-Repo([string]$Path, [string]$Name) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { $dirty = & git -C $Path status --porcelain 2>$null; $statusOk = ($LASTEXITCODE -eq 0) } catch { $dirty = $null; $statusOk = $false } finally { $ErrorActionPreference = $prev }
    if (-not $statusOk -or $dirty) { Write-WarnLine "$Name at $Path has local changes or cannot be inspected; leaving it unchanged."; return }
    if (-not (Invoke-Git @("-C", $Path, "fetch", "-q", "origin", "main"))) { Write-WarnLine "$Name at $Path could not check for updates (offline or remote unavailable); using your existing copy."; return }
    if (-not (Invoke-Git @("-C", $Path, "merge", "--ff-only", "-q", "FETCH_HEAD"))) { Write-WarnLine "$Name at $Path could not fast-forward; leaving it unchanged."; return }
    Write-Ok "$Name updated at $Path"
}
function Write-Step([string]$n,[string]$m) { Write-Host "`n[$n] $m" -ForegroundColor Cyan }
function Write-Ok([string]$m) { Write-Host "  OK  $m" -ForegroundColor Green }
function Write-WarnLine([string]$m) { Write-Host "  !  $m" -ForegroundColor Yellow }
function Test-WarpInstalled { (Get-Command warp -ErrorAction SilentlyContinue) -or (Test-Path (Join-Path $env:LOCALAPPDATA "Programs\Warp\warp.exe")) }

# Git writes progress and "could not reach" to stderr. Windows PowerShell 5.1 can turn that into a stopping error.
function Invoke-Git([string[]]$GitArgs) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & git @GitArgs 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) } catch { return $false } finally { $ErrorActionPreference = $prev }
}


# A stock Windows install has App Execution Alias stubs that only open the Microsoft Store, so a command being found
# is not enough: it has to run.
function Test-Python {
    foreach ($candidate in @(@("python3"), @("py", "-3"), @("python"))) {
        if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) { continue }
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $rest = @($candidate | Select-Object -Skip 1)
            & $candidate[0] @rest --version *> $null
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch { } finally { $ErrorActionPreference = $prev }
    }
    return $false
}

function Update-SessionPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($machinePath -or $userPath) {
        $env:Path = (@($env:Path, $machinePath, $userPath) | Where-Object { $_ }) -join [IO.Path]::PathSeparator
    }
}

Write-Step "1/5" "Checking prerequisites"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Write-WarnLine "Install Git for Windows first, then re-run."; exit 1 }
if (-not (Test-Python) -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-WarnLine "Python is not installed; installing it for this user with winget."
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements } catch { } finally { $ErrorActionPreference = $prev }
    Update-SessionPath
}
Write-Step "2/5" "Getting the Founding Circle"
$selected = Find-FcFolder
if ($selected) {
    $WorkspaceDir = $selected
    Update-Repo $WorkspaceDir "Founding Circle"
} else {
    [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $WorkspaceDir))
    if (-not (Invoke-Git @("clone", "-q", $FcUrl, $WorkspaceDir))) {
        Write-WarnLine "Could not download the Founding Circle. Check your internet connection, then re-run."; exit 1
    }
}
$env:AMM_FOUNDING_CIRCLE_DIR = $WorkspaceDir
Write-Ok "Selected Founding Circle folder: $WorkspaceDir"
Write-Step "3/5" "Using Founding Circle tools"
# Skills, artifacts, tools, SHEP, and onboarding all live in this one repository.
# A legacy sibling toolkit is never cloned, updated, or removed; existing files stay untouched.
$LegacyToolkit = Join-Path (Split-Path -Parent $WorkspaceDir) "amm-toolkit"
if (Test-Path $LegacyToolkit) { Write-WarnLine "Legacy AMM toolkit folder found at $LegacyToolkit; leaving it untouched. Founding Circle is now the single source of truth." }
Write-Ok "Founding Circle skills, artifacts, and tools ready at $WorkspaceDir"

Write-Step "4/5" "Installing Herdr terminal command"
if (Get-Command herdr -ErrorAction SilentlyContinue) { Write-Ok "Herdr already installed" } else {
    $herdrOk = $false
    try { powershell -NoProfile -ExecutionPolicy Bypass -c "irm $HerdrInstallUrl | iex"; $herdrOk = ($LASTEXITCODE -eq 0) } catch { }
    Update-SessionPath
    if ($herdrOk -and (Get-Command herdr -ErrorAction SilentlyContinue)) { Write-Ok "Herdr terminal command installed (run: herdr)" } else { Write-WarnLine "Herdr command is not on PATH yet. Reopen PowerShell or retry the Herdr installer." }
}
Write-Step "5/5" "Warp"
$WarpReady = $false
try {
  if (Test-WarpInstalled) { Write-Ok "Warp already installed"; $WarpReady = $true }
  elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install --id Warp.Warp -e --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -eq 0) { Write-Ok "Warp installed"; $WarpReady = $true } else { Write-WarnLine "winget could not install Warp. Get it from $WarpDownloadPage" }
  } else { Write-WarnLine "winget not found. Get Warp from $WarpDownloadPage" }
} catch { Write-WarnLine "Warp did not install ($($_.Exception.Message)). Get it from $WarpDownloadPage" }
Write-Ok "Borg for Windows is available. Downloading the desktop installer."
$BorgExe = Join-Path $HOME "Downloads\Borg-0.0.79-win-x64.exe"
$borgOk = $false
try {
  [void](New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BorgExe))
  Invoke-WebRequest -Uri $BorgWinUrl -OutFile $BorgExe -UseBasicParsing
  $borgOk = $true
  Write-Ok "Borg downloaded to $BorgExe"
} catch { Write-WarnLine "Could not download Borg for Windows. Get it from https://www.getborg.com/#download" }
if (-not $env:AMM_NO_OPEN) {
  if ($borgOk) { try { Start-Process $BorgExe } catch { Write-WarnLine "Borg downloaded but did not open. Run $BorgExe" } }
  if (Get-Command herdr -ErrorAction SilentlyContinue) { try { Start-Process powershell -ArgumentList "-NoExit","-Command","herdr" } catch { } }
}
if ($WarpReady -and -not $env:CI -and -not $env:AMM_UNATTENDED -and -not $env:AMM_NO_OPEN) {
  $warpExe = Join-Path $env:LOCALAPPDATA "Programs\Warp\warp.exe"
  if (Test-Path $warpExe) { Start-Process $warpExe } else { try { Start-Process warp } catch { } }
}
if (Test-Path (Join-Path $WorkspaceDir "shep\bin\shep")) { Write-Ok "SHEP terminal command: run from Git Bash: $WorkspaceDir\shep\bin\shep --help" }
Write-Host "`nTerminal commands: herdr (if installed), SHEP (repo-local, use Git Bash). Founding Circle skills: $WorkspaceDir\skills. Borg for Windows: $BorgExe." -ForegroundColor Green
Write-Host "`nSetup complete. Run the onboarding audit from your AMM portal." -ForegroundColor Green
