#!/usr/bin/env bash
# Consolidate the legacy sibling into the mothership. Dry-run unless --apply is given.
# An applied migration leaves temporary per-file compatibility shims at the old
# paths. Remove those shims only after every old caller has moved to the new path.
set -euo pipefail

ROOT="${AMM_MOTHERSHIP_ROOT:-$HOME/amm-mothership}"
APPLY=0
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --force) FORCE=1 ;;
    --root)
      [[ $# -ge 2 ]] || { echo "--root needs a path" >&2; exit 64; }
      ROOT="$2"; shift ;;
    -h|--help)
      echo "Usage: migrate.sh [--apply] [--force] [--root PATH]"
      echo "Dry-run writes a manifest under ROOT/migration-manifests and moves nothing."
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 64 ;;
  esac
  shift
done

FC="$ROOT/founding-circle"
WORK="$ROOT/work"
ARCHIVE="$ROOT/archive"
LEGACY="$(dirname "$FC")/amm-toolkit"
DEST_ROOT="$WORK/legacy-toolkit"
STAGING="$WORK/.legacy-toolkit-staging"
MANIFEST_DIR="$ROOT/migration-manifests"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCH="$ARCHIVE/amm-toolkit-$STAMP"
while [[ -e "$ARCH" || -L "$ARCH" ]]; do
  STAMP="${STAMP}-1"
  ARCH="$ARCHIVE/amm-toolkit-$STAMP"
done
MANIFEST="$MANIFEST_DIR/migration-$STAMP.manifest"
STATE="$WORK/.legacy-toolkit-migration.state"
RECOVERY_ARCH=""
RECOVERY_MANIFEST=""
if [[ -s "$STATE" ]]; then
  mapfile -t STATE_LINES < "$STATE"
  RECOVERY_ARCH="${STATE_LINES[0]:-}"
  RECOVERY_MANIFEST="${STATE_LINES[1]:-}"
fi

mkdir -p "$ROOT" "$MANIFEST_DIR"
{
  echo "version=2"
  echo "mode=$([[ $APPLY == 1 ]] && echo apply || echo dry-run)"
  echo "root=$ROOT"
  echo "founding-circle=$FC"
  echo "work=$WORK"
  echo "archive=$ARCH"
  echo "legacy=$LEGACY"
  echo "shim-lifetime=temporary; remove after old callers have moved"
} > "$MANIFEST"
echo "Migration manifest: $MANIFEST"

finish_shims() {
  local archive_root="$1" dest rel shim
  for dest in "${DESTS[@]}"; do
    [[ -e "$dest" || -L "$dest" ]] || continue
    rel="${dest#"$DEST_ROOT"/}"
    shim="$archive_root/$rel"
    mkdir -p "$(dirname "$shim")"
    [[ ! -e "$shim" && ! -L "$shim" ]] || rm -rf -- "$shim"
    ln -s "$dest" "$shim"
    echo "shim=$LEGACY/$rel -> $dest" >> "$MANIFEST"
  done
}
recover_shims() {
  local archive_root="$1" manifest_file="$2" dest rel shim
  while IFS= read -r dest; do
    rel="${dest#"$DEST_ROOT"/}"
    shim="$archive_root/$rel"
    [[ -e "$dest" || -L "$dest" ]] || continue
    mkdir -p "$(dirname "$shim")"
    [[ ! -e "$shim" && ! -L "$shim" ]] || rm -rf -- "$shim"
    ln -s "$dest" "$shim"
  done < <(sed -n 's/^destination=//p' "$manifest_file")
}


if [[ -L "$LEGACY" ]]; then
  echo "Legacy path is already a compatibility shim; migration is complete."
  rm -f "$STATE" 2>/dev/null || true
  exit 0
fi
if [[ ! -e "$LEGACY" && ! -d "$STAGING" ]]; then
  if [[ -n "$RECOVERY_ARCH" && -d "$RECOVERY_ARCH" ]]; then
    echo "Resuming final shim creation in archived migration: $RECOVERY_ARCH"
    [[ -n "$RECOVERY_MANIFEST" && -f "$RECOVERY_MANIFEST" ]] || RECOVERY_MANIFEST="$MANIFEST"
    recover_shims "$RECOVERY_ARCH" "$RECOVERY_MANIFEST"
    ln -s "$RECOVERY_ARCH" "$LEGACY"
    rm -f "$STATE"
    exit 0
  fi
  echo "No legacy amm-toolkit directory found; nothing to migrate."
  exit 0
fi
if [[ -e "$LEGACY" && ! -d "$LEGACY" ]]; then
  echo "Legacy path is not a directory: $LEGACY" >&2
  exit 1
fi

echo "Legacy source: $LEGACY"
echo "Archive destination: $ARCH"
echo "Personal files are never deleted."

# Build the complete plan before the first move. find includes dot files; .git is
# archived with the old tree but is not treated as a member file. A fixed staging
# directory lets a rerun recover files after an interrupted process.
SOURCES=()
FROM=()
if [[ -d "$LEGACY" ]]; then
  while IFS= read -r -d '' source; do
    rel="${source#$LEGACY/}"
    [[ -e "$STAGING/$rel" || -L "$STAGING/$rel" ]] && continue
    SOURCES+=("$source")
    FROM+=("$source")
  done < <(
    find "$LEGACY" -mindepth 1 \
      \( -path "$LEGACY/.git" -o -path "$LEGACY/.git/*" \) -prune -o \
      \( -type f -o -type l \) -print0 | sort -z
  )
fi
if [[ -d "$STAGING" ]]; then
  while IFS= read -r -d '' staged; do
    rel="${staged#$STAGING/}"
    SOURCES+=("$LEGACY/$rel")
    FROM+=("$staged")
  done < <(find "$STAGING" -mindepth 1 \( -type f -o -type l \) -print0 | sort -z)
fi
if [[ ${#SOURCES[@]} -eq 0 ]]; then
  # An interruption after the member moves but before archiving leaves an empty
  # legacy directory. Finish that recorded migration instead of treating it as
  # a fresh no-op.
  if [[ -n "$RECOVERY_ARCH" && -s "$STATE" && -d "$LEGACY" ]]; then
    echo "Resuming archive and shim creation: $RECOVERY_ARCH"
    mkdir -p "$(dirname "$RECOVERY_ARCH")"
    [[ ! -e "$RECOVERY_ARCH" && ! -L "$RECOVERY_ARCH" ]] || { echo "Recovery archive already exists: $RECOVERY_ARCH" >&2; exit 1; }
    mv -- "$LEGACY" "$RECOVERY_ARCH"
    [[ -n "$RECOVERY_MANIFEST" && -f "$RECOVERY_MANIFEST" ]] || RECOVERY_MANIFEST="$MANIFEST"
    recover_shims "$RECOVERY_ARCH" "$RECOVERY_MANIFEST"
    ln -s "$RECOVERY_ARCH" "$LEGACY"
    rm -f "$STATE"
    exit 0
  fi
  echo "No member files found; nothing to migrate."
  exit 0
fi

DESTS=()
BACKUPS=()
COLLISIONS=()
for i in "${!SOURCES[@]}"; do
  source="${SOURCES[$i]}"
  from="${FROM[$i]}"
  rel="${source#$LEGACY/}"
  dest="$DEST_ROOT/$rel"
  backup="none"
  if [[ -e "$dest" || -L "$dest" ]]; then
    backup="$dest.backup-$STAMP"
    n=0
    while [[ -e "$backup" || -L "$backup" ]]; do
      n=$((n + 1))
      backup="$dest.backup-$STAMP-$n"
    done
    COLLISIONS+=("$dest")
  fi
  # A non-directory parent is also a collision, even when the final path is new.
  parent="$(dirname "$dest")"
  while [[ "$parent" != "$DEST_ROOT" ]]; do
    if [[ -e "$parent" || -L "$parent" ]] && [[ ! -d "$parent" || -L "$parent" ]]; then
      COLLISIONS+=("$parent (parent of $dest)")
      break
    fi
    parent="$(dirname "$parent")"
  done
  DESTS+=("$dest")
  BACKUPS+=("$backup")
  {
    echo "source=$source"
    echo "destination=$dest"
    echo "backup=$backup"
  } >> "$MANIFEST"
done

# Dry-run is read-only except for its manifest directory and manifest file.
if [[ $APPLY != 1 ]]; then
  echo "Dry run only. The manifest directory was written at $MANIFEST_DIR. Re-run with --apply to move files and create the shim."
  exit 0
fi

if [[ ${#COLLISIONS[@]} -gt 0 && $FORCE != 1 ]]; then
  echo "Destination collision under $DEST_ROOT; migration aborted before moving anything:" >&2
  printf '  %s\n' "${COLLISIONS[@]}" >&2
  echo "Re-run with --force to back up existing destination entries with timestamp suffixes." >&2
  exit 1
fi

mkdir -p "$WORK"
printf '%s\n%s\n' "$ARCH" "$MANIFEST" > "$STATE"

# First move every source into staging. Nothing is removed from the legacy tree
# until all source moves have succeeded. The second phase renames staged entries
# into place, which makes an interruption recoverable rather than stranded.
mkdir -p "$STAGING"
for i in "${!SOURCES[@]}"; do
  from="${FROM[$i]}"
  rel="${SOURCES[$i]#$LEGACY/}"
  staged="$STAGING/$rel"
  if [[ "$from" != "$staged" && ( -e "$from" || -L "$from" ) ]]; then
    mkdir -p "$(dirname "$staged")"
    mv -- "$from" "$staged"
  fi
done

for i in "${!DESTS[@]}"; do
  dest="${DESTS[$i]}"
  backup="${BACKUPS[$i]}"
  staged="$STAGING/${dest#"$DEST_ROOT"/}"
  # A rerun after a successful staged-to-final rename has nothing left to do.
  if [[ ! -e "$staged" && ! -L "$staged" ]]; then continue; fi
  if [[ -e "$dest" || -L "$dest" ]]; then
    if [[ $FORCE != 1 ]]; then
      echo "Destination appeared during migration: $dest" >&2
      echo "Staged files remain in $STAGING; review them before retrying." >&2
      exit 1
    fi
    mv -- "$dest" "$backup"
    echo "backup=$dest -> $backup" >> "$MANIFEST"
  fi
  mkdir -p "$(dirname "$dest")"
  mv -- "$staged" "$dest"
done

# Archive whatever remains of the old tree, then expose the archive as the old
# root. Each archived member path becomes a symlink into work/legacy-toolkit.
mkdir -p "$ARCHIVE"
if [[ -d "$LEGACY" ]]; then mv -- "$LEGACY" "$ARCH"; fi
finish_shims "$ARCH"
if [[ -n "$RECOVERY_MANIFEST" && -f "$RECOVERY_MANIFEST" ]]; then
  recover_shims "$ARCH" "$RECOVERY_MANIFEST"
fi
[[ -e "$LEGACY" || -L "$LEGACY" ]] || ln -s "$ARCH" "$LEGACY"
rmdir "$STAGING" 2>/dev/null || true
rm -f "$STATE"

echo "Migration applied. Per-file compatibility shims remain at $LEGACY temporarily and point into $DEST_ROOT."
echo "Keep the shims until old absolute-path callers are updated; then remove the old shim and archive manually."
