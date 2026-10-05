<#
Run the AMM onboarding audit the portal asked for. Safe to paste every time, from any folder:

  & ([scriptblock]::Create((irm https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/onboarding/run.ps1))) -Code <code> -Portal <portal address>

It finds your Founding Circle folder wherever it is (or downloads it to ~\amm-founding-circle the first time),
brings it up to date, then runs the audit. Only rung statuses and counts are sent to your portal.
#>
param(
    [Parameter(Mandatory = $true)][string]$Code,
    [Parameter(Mandatory = $true)][string]$Portal
)

$ErrorActionPreference = "Stop"
$RepoUrl = "https://github.com/search-atlas-group/amm-founding-circle.git"
$DefaultDir = Join-Path $HOME "amm-founding-circle"

foreach ($tool in @("git")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "$tool is not installed. Set up your coding environment first (step 1 on the Onboarding page)."
        exit 69
    }
}

function Test-Folder([string]$Path) {
    return $Path -and (Test-Path (Join-Path $Path "onboarding")) -and (Test-Path (Join-Path $Path ".git"))
}

$candidates = @($env:AMM_FOUNDING_CIRCLE_DIR, (Get-Location).Path, (Join-Path (Get-Location).Path "amm-founding-circle"), $DefaultDir,
    (Join-Path $HOME "Desktop\amm-founding-circle"), (Join-Path $HOME "Documents\amm-founding-circle"),
    (Join-Path $HOME "Developer\amm-founding-circle"), (Join-Path $HOME "Code\amm-founding-circle"))
$candidates += Get-ChildItem -Directory -ErrorAction SilentlyContinue (Join-Path $HOME "Desktop"), (Join-Path $HOME "Documents") |
    ForEach-Object { Join-Path $_.FullName "amm-founding-circle" }

$dir = $null
foreach ($c in $candidates) { if (Test-Folder $c) { $dir = $c; break } }

if (-not $dir) {
    Write-Host "Downloading the Founding Circle folder to $DefaultDir ..."
    git clone -q $RepoUrl $DefaultDir
    $dir = $DefaultDir
} else {
    Write-Host "Using your Founding Circle folder: $dir"
    git -C $dir pull --ff-only -q 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Host "Could not update it automatically (you have changes of your own there). Running the version you have." }
}

if (-not (Test-Path (Join-Path $dir "onboarding\portal.py"))) {
    Write-Host "This copy is too old and could not be updated. Run: git -C `"$dir`" pull"
    exit 1
}
& (Join-Path $dir "onboarding\onboard.ps1") -Run $Code -Portal $Portal
