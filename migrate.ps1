<#
Consolidate the legacy sibling into the mothership. Dry-run unless -Apply is given.
An applied migration leaves temporary per-file compatibility symlinks at the old
paths. Remove those shims only after every old caller has moved to the new path.
#>
[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Force,
    [string]$Root = $(if ($env:AMM_MOTHERSHIP_ROOT) { $env:AMM_MOTHERSHIP_ROOT } else { Join-Path $HOME 'amm-mothership' })
)

$ErrorActionPreference = 'Stop'
$fc = Join-Path $Root 'founding-circle'
$work = Join-Path $Root 'work'
$archive = Join-Path $Root 'archive'
$legacy = Join-Path (Split-Path $fc -Parent) 'amm-toolkit'
$destRoot = Join-Path $work 'legacy-toolkit'
$staging = Join-Path $work '.legacy-toolkit-staging'
$manifestDir = Join-Path $Root 'migration-manifests'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
$arch = Join-Path $archive "amm-toolkit-$stamp"
while (Test-Path -LiteralPath $arch -Force) {
    $stamp = "$stamp-1"
    $arch = Join-Path $archive "amm-toolkit-$stamp"
}
$manifest = Join-Path $manifestDir "migration-$stamp.manifest"
$state = Join-Path $work '.legacy-toolkit-migration.state'
$recoveryArchive = ''
$recoveryManifest = ''
if (Test-Path -LiteralPath $state -Force) {
    $stateLines = @(Get-Content -LiteralPath $state -Force)
    $recoveryArchive = if ($stateLines.Count -gt 0) { $stateLines[0] } else { '' }
    $recoveryManifest = if ($stateLines.Count -gt 1) { $stateLines[1] } else { '' }
}

New-Item -ItemType Directory -Force -Path $Root, $manifestDir | Out-Null
$lines = @(
    'version=2',
    "mode=$(if ($Apply) { 'apply' } else { 'dry-run' })",
    "root=$Root", "founding-circle=$fc", "work=$work", "archive=$arch", "legacy=$legacy",
    'shim-lifetime=temporary; remove after old callers have moved'
)
$lines | Set-Content -LiteralPath $manifest -Encoding UTF8
Write-Host "Migration manifest: $manifest"

function Test-AnyPath([string]$Path) {
    return $null -ne (Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
}
function Test-LegacyShim([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    return $null -ne $item -and $item.LinkType
}

function Complete-Recovery([string]$ArchiveRoot, [string]$Plan = $manifest) {
    $destinationLines = @(Get-Content -LiteralPath $Plan | Where-Object { $_ -like 'destination=*' })
    foreach ($line in $destinationLines) {
        $dest = $line.Substring('destination='.Length)
        $rel = $dest.Substring($destRoot.Length + 1)
        $shim = Join-Path $ArchiveRoot $rel
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $shim) | Out-Null
        if (Test-AnyPath $shim) { Remove-Item -LiteralPath $shim -Force -Recurse }
        New-Item -ItemType SymbolicLink -Path $shim -Target $dest -ErrorAction Stop | Out-Null
    }
    if (-not (Test-AnyPath $legacy)) {
        New-Item -ItemType SymbolicLink -Path $legacy -Target $ArchiveRoot -ErrorAction Stop | Out-Null
    }
    Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue
}

if (Test-LegacyShim $legacy) {
    Write-Host 'Legacy path is already a compatibility shim; migration is complete.'
    Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue
    return
}
if (-not (Test-AnyPath $legacy) -and (Test-AnyPath $state)) {
    $recoveryArchive = (Get-Content -LiteralPath $state -Raw).Trim()
    if (Test-AnyPath $recoveryArchive) {
        Write-Host "Resuming final shim creation in archived migration: $recoveryArchive"
        if (-not $recoveryManifest -or -not (Test-Path -LiteralPath $recoveryManifest -Force)) { $recoveryManifest = $manifest }
        Complete-Recovery $recoveryArchive $recoveryManifest
        return
    }
}
if (-not (Test-AnyPath $legacy) -and -not (Test-AnyPath $staging)) {
    Write-Host 'No legacy amm-toolkit directory found; nothing to migrate.'
    return
}
if ((Test-AnyPath $legacy) -and -not (Get-Item -LiteralPath $legacy -Force).PSIsContainer) {
    throw "Legacy path is not a directory: $legacy"
}
Write-Host "Legacy source: $legacy"
Write-Host "Archive destination: $arch"
Write-Host 'Personal files are never deleted.'

# Get-ChildItem -Force is intentional: hidden member files are part of the
# manifest and migration just like visible files on macOS/Linux.
$sources = @()
$from = @()
if (Test-AnyPath $legacy) {
    $legacyFiles = @(Get-ChildItem -LiteralPath $legacy -File -Recurse -Force |
        Where-Object { $_.FullName -notlike "$(Join-Path $legacy '.git')*" })
    foreach ($file in $legacyFiles) {
        $rel = $file.FullName.Substring($legacy.Length + 1)
        if (-not (Test-AnyPath (Join-Path $staging $rel))) {
            $sources += $file.FullName
            $from += $file.FullName
        }
    }
}
if (Test-AnyPath $staging) {
    $stagedFiles = @(Get-ChildItem -LiteralPath $staging -File -Recurse -Force)
    foreach ($file in $stagedFiles) {
        $rel = $file.FullName.Substring($staging.Length + 1)
        $sources += (Join-Path $legacy $rel)
        $from += $file.FullName
    }
}

if ($sources.Count -eq 0) {
    # An interruption after the member moves but before archiving leaves an
    # empty legacy directory. Finish the recorded migration rather than making
    # a new no-op plan.
    if ($recoveryArchive -and (Test-AnyPath $state) -and (Test-AnyPath $legacy)) {
        $legacyItem = Get-Item -LiteralPath $legacy -Force
        if ($legacyItem.PSIsContainer) {
            Write-Host "Resuming archive and shim creation: $recoveryArchive"
            if (Test-AnyPath $recoveryArchive) {
                throw "Recovery archive already exists: $recoveryArchive"
            }
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $recoveryArchive) | Out-Null
            Move-Item -LiteralPath $legacy -Destination $recoveryArchive
            if (-not $recoveryManifest -or -not (Test-Path -LiteralPath $recoveryManifest -Force)) { $recoveryManifest = $manifest }
            Complete-Recovery $recoveryArchive $recoveryManifest
            Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue
            return
        }
    }
    Write-Host 'No member files found; nothing to migrate.'
    return
}

$destinations = @()
$backups = @()
$collisions = @()
for ($i = 0; $i -lt $sources.Count; $i++) {
    $rel = $sources[$i].Substring($legacy.Length + 1)
    $dest = Join-Path $destRoot $rel
    $backup = 'none'
    if (Test-AnyPath $dest) {
        $backup = "$dest.backup-$stamp"
        $n = 0
        while (Test-AnyPath $backup) {
            $n++
            $backup = "$dest.backup-$stamp-$n"
        }
        $collisions += $dest
    }
    $parent = Split-Path -Parent $dest
    while ($parent -and $parent -ne $destRoot) {
        $parentItem = Get-Item -LiteralPath $parent -Force -ErrorAction SilentlyContinue
        if ($parentItem -and (-not $parentItem.PSIsContainer -or $parentItem.LinkType)) {
            $collisions += "$parent (parent of $dest)"
            break
        }
        $parent = Split-Path -Parent $parent
    }
    $destinations += $dest
    $backups += $backup
    $lines += "source=$($sources[$i])"
    $lines += "destination=$dest"
    $lines += "backup=$backup"
}
$lines | Set-Content -LiteralPath $manifest -Encoding UTF8

if (-not $Apply) {
    Write-Host "Dry run only. The manifest directory was written at $manifestDir. Re-run with -Apply to move files and create the shims."
    return
}
if ($collisions.Count -gt 0 -and -not $Force) {
    Write-Error "Destination collision under $destRoot; migration aborted before moving anything:"
    $collisions | ForEach-Object { Write-Error "  $_" }
    Write-Error 'Re-run with -Force to back up existing destination entries with timestamp suffixes.'
    return
}

Set-Content -LiteralPath $state -Value "$arch`n$manifest" -Encoding UTF8

# First move every source into staging. Nothing is removed from the legacy tree
# until all source moves have succeeded. The second phase renames staged entries
# into place, so an interruption can be resumed without losing a file.
New-Item -ItemType Directory -Force -Path $staging | Out-Null
for ($i = 0; $i -lt $sources.Count; $i++) {
    $staged = Join-Path $staging $sources[$i].Substring($legacy.Length + 1)
    if ($from[$i] -ne $staged -and (Test-AnyPath $from[$i])) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $staged) | Out-Null
        Move-Item -LiteralPath $from[$i] -Destination $staged
    }
}
for ($i = 0; $i -lt $destinations.Count; $i++) {
    $dest = $destinations[$i]
    $staged = Join-Path $staging $dest.Substring($destRoot.Length + 1)
    if (-not (Test-AnyPath $staged)) { continue }
    if (Test-AnyPath $dest) {
        if (-not $Force) {
            throw "Destination appeared during migration: $dest. Staged files remain in $staging."
        }
        Move-Item -LiteralPath $dest -Destination $backups[$i]
        Add-Content -LiteralPath $manifest -Value "backup=$dest -> $($backups[$i])"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Move-Item -LiteralPath $staged -Destination $dest
}

# Archive the old root, then put a symlink at its original location. Every
# archived member path is itself a symlink into work/legacy-toolkit, preserving
# old absolute paths without duplicating the file.
New-Item -ItemType Directory -Force -Path $archive | Out-Null
if (Test-AnyPath $legacy) { Move-Item -LiteralPath $legacy -Destination $arch }
for ($i = 0; $i -lt $destinations.Count; $i++) {
    $dest = $destinations[$i]
    $rel = $dest.Substring($destRoot.Length + 1)
    $shim = Join-Path $arch $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $shim) | Out-Null
    if (Test-AnyPath $shim) { Remove-Item -LiteralPath $shim -Force -Recurse }
    try {
        New-Item -ItemType SymbolicLink -Path $shim -Target $dest -ErrorAction Stop | Out-Null
    } catch {
        throw "Could not create compatibility symlink $shim -> $dest. Enable Windows Developer Mode or create symlinks with the required privilege."
    }
    Add-Content -LiteralPath $manifest -Value "shim=$legacy/$rel -> $dest"
}
if (-not (Test-AnyPath $legacy)) {
    try {
        New-Item -ItemType SymbolicLink -Path $legacy -Target $arch -ErrorAction Stop | Out-Null
    } catch {
        New-Item -ItemType Junction -Path $legacy -Target $arch | Out-Null
    }
}
Remove-Item -LiteralPath $staging -Force -Recurse -ErrorAction SilentlyContinue
if ($recoveryManifest -and (Test-Path -LiteralPath $recoveryManifest -Force)) {
    Complete-Recovery $arch $recoveryManifest
}
Remove-Item -LiteralPath $state -Force -ErrorAction SilentlyContinue
Write-Host "Migration applied. Per-file compatibility symlinks remain at $legacy temporarily and point into $destRoot."
Write-Host 'Keep the shims until old absolute-path callers are updated; then remove the old shim and archive manually.'
