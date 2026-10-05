# AMM Founding Circle quickstart for Windows PowerShell.
# Usage: irm https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.ps1 | iex
$ErrorActionPreference = "Stop"
$ToolkitUrl = "https://github.com/search-atlas-group/amm-toolkit.git"
$FcUrl = "https://github.com/search-atlas-group/amm-founding-circle.git"
$HerdrInstallUrl = "https://herdr.dev/install.ps1"
$WorkspaceDir = Join-Path $HOME "amm-founding-circle"
function Write-Step([string]$n,[string]$m) { Write-Host "`n[$n] $m" -ForegroundColor Cyan }
function Write-Ok([string]$m) { Write-Host "  OK  $m" -ForegroundColor Green }
function Write-WarnLine([string]$m) { Write-Host "  !  $m" -ForegroundColor Yellow }

Write-Step "1/4" "Checking prerequisites"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Write-WarnLine "Install Git for Windows first, then re-run."; exit 1 }
Write-Step "2/4" "Getting the Founding Circle"
if (Test-Path (Join-Path $WorkspaceDir ".git")) { git -C $WorkspaceDir fetch -q origin main; git -C $WorkspaceDir merge --ff-only -q origin main } else { git clone -q $FcUrl $WorkspaceDir }
$env:AMM_FOUNDING_CIRCLE_DIR = $WorkspaceDir
Write-Ok "Founding Circle ready at $WorkspaceDir"
Write-Step "3/4" "Getting the AMM toolkit"
$ToolkitDir = Join-Path (Split-Path -Parent $WorkspaceDir) "amm-toolkit"
if (Test-Path (Join-Path $ToolkitDir ".git")) { git -C $ToolkitDir fetch -q origin main; git -C $ToolkitDir merge --ff-only -q origin main } else { git clone -q $ToolkitUrl $ToolkitDir }
Write-Ok "AMM toolkit ready"
Write-Step "4/4" "Installing Herdr"
if (Get-Command herdr -ErrorAction SilentlyContinue) { Write-Ok "Herdr already installed" } else { powershell -ExecutionPolicy Bypass -c "irm $HerdrInstallUrl | iex"; Write-Ok "Herdr installed" }
Write-WarnLine "Borg desktop is not available for Windows yet; use https://app.getborg.com"
Write-Host "`nSetup complete. Run the onboarding audit from your AMM portal." -ForegroundColor Green
