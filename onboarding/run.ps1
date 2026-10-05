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
$ToolkitUrl = "https://github.com/search-atlas-group/amm-toolkit.git"
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
    $parent = Split-Path -Parent $dir
} else {
    Write-Host "Using your Founding Circle folder: $dir"
    $parent = Split-Path -Parent $dir
    # Guarantee the latest: fetch, fast-forward, then verify the folder matches GitHub's main. If something of the
    # member's own blocks the update, never run the stale copy: run a clean copy of the latest instead.
    git -C $dir fetch -q origin main 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not reach GitHub to check for updates. Running the version you have."
    } else {
        git -C $dir merge --ff-only -q origin/main 2>$null
        $head = (git -C $dir rev-parse HEAD).Trim()
        $latest = (git -C $dir rev-parse origin/main).Trim()
        if ($head -eq $latest) {
            Write-Host "Up to date ($($head.Substring(0,7)))."
        } else {
            Write-Host "Your folder has changes of your own that block the update, so it was left alone."
            $fresh = Join-Path ([System.IO.Path]::GetTempPath()) ("amm-fc-" + [guid]::NewGuid().ToString("N"))
            git clone -q --depth 1 --branch main $RepoUrl $fresh
            $dir = $fresh
            Write-Host "Running a clean copy of the latest ($($latest.Substring(0,7)))."
        }
    }
}

# The toolkit (slash commands, setup) lives beside the Founding Circle. Clone it if missing, else bring it up to date.
$tk = Join-Path $parent "amm-toolkit"
if (Test-Path (Join-Path $tk ".git")) {
    git -C $tk fetch -q origin main 2>$null
    git -C $tk merge --ff-only -q origin/main 2>$null
    if ((git -C $tk rev-parse HEAD) -eq (git -C $tk rev-parse origin/main)) { Write-Host "Toolkit up to date." } else { Write-Host "Toolkit left as it is (your own changes, or GitHub unreachable)." }
} else {
    Write-Host "Downloading the AMM toolkit to $tk ..."
    git clone -q $ToolkitUrl $tk 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "Toolkit ready." } else { Write-Host "Could not download the toolkit. The audit still runs." }
}
Write-Host ""

if (-not (Test-Path (Join-Path $dir "onboarding\portal.py"))) {
    Write-Host "This copy is too old and could not be updated. Delete it and paste the command again to download a fresh one."
    exit 1
}
& (Join-Path $dir "onboarding\onboard.ps1") -Run $Code -Portal $Portal
