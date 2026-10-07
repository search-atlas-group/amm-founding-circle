# AMM Founding Circle quickstart for Windows PowerShell.
# Usage: irm https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.ps1 | iex
# The portal's Run audit command (onboarding/run.ps1) runs this first, in its own PowerShell, before the audit.
# Set AMM_NO_OPEN=1 to skip opening Borg's web page and a Herdr window (headless runs and tests).
$ErrorActionPreference = "Stop"
$ToolkitUrl = "https://github.com/search-atlas-group/amm-toolkit.git"
$FcUrl = "https://github.com/search-atlas-group/amm-founding-circle.git"
$HerdrInstallUrl = "https://herdr.dev/install.ps1"
$WarpDownloadPage = "https://www.warp.dev/download"
$WorkspaceDir = Join-Path $HOME "amm-founding-circle"
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
if (Test-Path (Join-Path $WorkspaceDir ".git")) {
    if (Invoke-Git @("-C", $WorkspaceDir, "fetch", "-q", "origin", "main")) { [void](Invoke-Git @("-C", $WorkspaceDir, "merge", "--ff-only", "-q", "origin/main")) }
} elseif (-not (Invoke-Git @("clone", "-q", $FcUrl, $WorkspaceDir))) {
    Write-WarnLine "Could not download the Founding Circle. Check your internet connection, then re-run."; exit 1
}
$env:AMM_FOUNDING_CIRCLE_DIR = $WorkspaceDir
Write-Ok "Founding Circle ready at $WorkspaceDir"
Write-Step "3/5" "Getting the AMM toolkit"
$ToolkitDir = Join-Path (Split-Path -Parent $WorkspaceDir) "amm-toolkit"
if (Test-Path (Join-Path $ToolkitDir ".git")) {
    if (Invoke-Git @("-C", $ToolkitDir, "fetch", "-q", "origin", "main")) { [void](Invoke-Git @("-C", $ToolkitDir, "merge", "--ff-only", "-q", "origin/main")) }
    Write-Ok "AMM toolkit ready"
} elseif (Invoke-Git @("clone", "-q", $ToolkitUrl, $ToolkitDir)) { Write-Ok "AMM toolkit ready" } else { Write-WarnLine "Could not download the AMM toolkit. Re-run this later." }
Write-Step "4/5" "Installing Herdr"
if (Get-Command herdr -ErrorAction SilentlyContinue) { Write-Ok "Herdr already installed" } else {
    $herdrOk = $false
    try { powershell -NoProfile -ExecutionPolicy Bypass -c "irm $HerdrInstallUrl | iex"; $herdrOk = ($LASTEXITCODE -eq 0) } catch { }
    if ($herdrOk) { Write-Ok "Herdr installed" } else { Write-WarnLine "Herdr did not install. Re-run this later." }
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
Write-WarnLine "Borg desktop is not available for Windows yet; opening the web version."
if (-not $env:AMM_NO_OPEN) {
  try { Start-Process "https://app.getborg.com" } catch { }
  if (Get-Command herdr -ErrorAction SilentlyContinue) { try { Start-Process powershell -ArgumentList "-NoExit","-Command","herdr" } catch { } }
}
if ($WarpReady -and -not $env:CI -and -not $env:AMM_UNATTENDED -and -not $env:AMM_NO_OPEN) {
  $warpExe = Join-Path $env:LOCALAPPDATA "Programs\Warp\warp.exe"
  if (Test-Path $warpExe) { Start-Process $warpExe } else { try { Start-Process warp } catch { } }
}
if (Test-Path (Join-Path $WorkspaceDir "shep\bin\shep")) { Write-Ok "SHEP is ready in $WorkspaceDir\shep\bin\shep" }
Write-Host "`nInstalled: coding environment, Herdr, Warp (terminal), SHEP. Borg opens in the browser." -ForegroundColor Green
Write-Host "`nSetup complete. Run the onboarding audit from your AMM portal." -ForegroundColor Green
