#!/usr/bin/env bash
# AMM Founding Circle quickstart: one command for the full member setup.
#
# Usage from any folder:
#   curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.sh | bash
#
# It installs the AMM coding environment, clones and updates this Founding Circle repo and the AMM toolkit beside it,
# installs Herdr, downloads the Borg Mac installer, and installs Warp (the terminal). SHEP is included in this repo. The onboarding audit then
# finds this copy automatically.
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
step(){ printf "\n%s[%s]%s %s\n" "$CYAN" "$1" "$NC" "$2"; }
ok(){ printf "  ${GREEN}✓${NC}  %s\n" "$1"; }
warn(){ printf "  ${YELLOW}!${NC}  %s\n" "$1"; }
fail(){ printf "  ${YELLOW}✗${NC}  %s\n" "$1" >&2; exit 1; }

TOOLKIT_URL="https://github.com/search-atlas-group/amm-toolkit.git"
FC_URL="https://github.com/search-atlas-group/amm-founding-circle.git"
HERDR_INSTALL_URL="https://herdr.dev/install.sh"
BORG_DMG_URL="https://download.getborg.com/Borg-0.0.79-mac-arm64.dmg"
WARP_DMG_URL="https://app.warp.dev/download?package=dmg"   # official; 302s to releases.warp.dev/stable/<version>/Warp.dmg
WARP_DOWNLOAD_PAGE="https://www.warp.dev/download"
WORKSPACE_DIR="${AMM_WORKSPACE:-$HOME/amm-founding-circle}"

# Warp: the terminal. Returns non-zero on failure; the caller warns and continues.
warp_app_path(){
  for p in "${AMM_SYSTEM_APPS_DIR:-/Applications}/Warp.app" "$HOME/Applications/Warp.app"; do [[ -d "$p" ]] && { printf "%s" "$p"; return 0; }; done
  return 1
}
install_warp(){
  if [[ "$(uname -s)" == "Darwin" ]]; then
    if warp_app_path >/dev/null; then ok "Warp already installed"; return 0; fi
    if command -v brew >/dev/null 2>&1; then
      brew install --cask warp && { ok "Warp installed"; return 0; }
      warn "brew could not install Warp; trying the direct download."
    fi
    local tmp dmg mnt dest rc=0
    tmp="$(mktemp -d)"; dmg="$tmp/Warp.dmg"; mnt="$tmp/mnt"; mkdir -p "$mnt"
    local sys="${AMM_SYSTEM_APPS_DIR:-/Applications}"
    if [[ -w "$sys" ]]; then dest="$sys"; else dest="$HOME/Applications"; mkdir -p "$dest"; fi
    if curl -L --fail --silent --show-error "$WARP_DMG_URL" -o "$dmg" \
       && hdiutil attach -nobrowse -readonly -quiet -mountpoint "$mnt" "$dmg"; then
      ditto "$mnt/Warp.app" "$dest/Warp.app" || rc=1
      hdiutil detach -quiet "$mnt" || true
    else
      rc=1
    fi
    rm -rf "$tmp"
    [[ $rc -eq 0 ]] && { ok "Warp installed in $dest"; return 0; }
    return 1
  else
    if command -v warp-terminal >/dev/null 2>&1; then ok "Warp already installed"; return 0; fi
    warn "Warp is not auto-installed on Linux. Install it from $WARP_DOWNLOAD_PAGE (deb, rpm, AppImage)."
    return 0
  fi
}
# Open Warp like a member would; skipped when unattended, under CI, or with no GUI.
open_warp(){
  [[ "$(uname -s)" == "Darwin" ]] || return 0
  [[ -z "${CI:-}" && -z "${AMM_UNATTENDED:-}" && -z "${AMM_NO_OPEN:-}" ]] || return 0
  local app; app="$(warp_app_path)" || return 0
  open "$app" >/dev/null 2>&1 || true
}
# Keep discovery in the downloaded quickstart too, so the audit and standalone setup agree.
is_fc_folder(){ [[ -d "$1/.git" && -d "$1/onboarding" ]]; }
find_fc_folder(){
  local d root
  [[ -n "${AMM_WORKSPACE:-}" ]] && is_fc_folder "$AMM_WORKSPACE" && { printf '%s\n' "$AMM_WORKSPACE"; return; }
  for d in "$PWD" "$PWD/amm-founding-circle"; do
    is_fc_folder "$d" && { printf '%s\n' "$d"; return; }
  done
  for root in "$HOME/Desktop" "$HOME/Documents" "${OneDrive:-${ONEDRIVE:-$HOME/OneDrive}}/Desktop" "${OneDrive:-${ONEDRIVE:-$HOME/OneDrive}}/Documents"; do
    for d in "$root/amm-founding-circle" "$root"/*/amm-founding-circle "$root"/*/*/amm-founding-circle; do
      is_fc_folder "$d" && { printf '%s\n' "$d"; return; }
    done
  done
  for d in "$HOME/Developer/amm-founding-circle" "$HOME/Code/amm-founding-circle" "$HOME/code/amm-founding-circle" "$HOME/amm-founding-circle"; do
    is_fc_folder "$d" && { printf '%s\n' "$d"; return; }
  done
  return 1
}
update_repo(){
  local dir="$1" name="$2"
  if [[ -n "$(git -C "$dir" status --porcelain)" ]]; then
    warn "$name at $dir has local changes; leaving it unchanged. Save your work before updating."
  elif ! git -C "$dir" fetch -q origin main; then
    warn "$name at $dir could not check for updates (offline or remote unavailable); using your existing copy."
  elif ! git -C "$dir" merge --ff-only -q FETCH_HEAD; then
    warn "$name at $dir could not fast-forward; leaving it unchanged. Resolve the branch before updating."
  else
    ok "$name updated at $dir"
  fi
}
install_claude_commands(){
  local source="$1/commands" dest="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/commands"
  [[ -d "$source" ]] || { warn "Toolkit slash commands unavailable at $source; install them after the toolkit is downloaded."; return; }
  mkdir -p "$dest" || { warn "Cannot create Claude commands folder $dest; leaving existing files alone."; return; }
  python3 - "$source" "$dest" <<'PY'
import hashlib
import pathlib
import shutil
import sys

source, dest = map(pathlib.Path, sys.argv[1:])
installed = updated = preserved = 0
for item in sorted(source.glob("*.md")):
    target = dest / item.name
    receipt = dest / (".amm-managed-" + item.name + ".sha256")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if target.exists():
        if not target.is_file() or not receipt.is_file() or receipt.read_text().strip() != digest(target):
            preserved += 1
            continue
        if digest(target) == digest(item):
            continue
        updated += 1
    else:
        installed += 1
    shutil.copy2(item, target)
    receipt.write_text(digest(target) + "\n")
print(f"Claude slash commands in {dest}: {installed} added, {updated} updated, {preserved} existing files preserved.")
PY
}
if (return 0 2>/dev/null); then [[ "${AMM_QUICKSTART_LIB:-}" == 1 ]] && return 0; fi

step "1/6" "Checking prerequisites"
command -v git >/dev/null 2>&1 || fail "Install Git first (macOS: xcode-select --install), then re-run."
if ! command -v python3 >/dev/null 2>&1; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    warn "python3 is not installed; starting Apple's developer tools install."
    xcode-select --install 2>/dev/null || true
    until command -v python3 >/dev/null 2>&1; do sleep 10; done
    ok "python3 installed"
  else
    fail "Install python3 first, then re-run."
  fi
else
  ok "python3 ready"
fi

step "2/6" "Getting the Founding Circle"
SELECTED_DIR="$(find_fc_folder || true)"
if [[ -n "$SELECTED_DIR" ]]; then
  WORKSPACE_DIR="$SELECTED_DIR"
  update_repo "$WORKSPACE_DIR" "Founding Circle"
elif [[ -e "$WORKSPACE_DIR" ]]; then
  fail "The default folder $WORKSPACE_DIR already exists but is not a valid Founding Circle clone. Leave it intact and choose a folder manually."
else
  git clone -q "$FC_URL" "$WORKSPACE_DIR" || fail "Could not download Founding Circle to $WORKSPACE_DIR. Check the connection and retry."
fi
ok "Selected Founding Circle folder: $WORKSPACE_DIR"
export AMM_FOUNDING_CIRCLE_DIR="$WORKSPACE_DIR"

step "3/6" "Getting the AMM toolkit"
TOOLKIT_DIR="$(dirname "$WORKSPACE_DIR")/amm-toolkit"
if [[ -d "$TOOLKIT_DIR/.git" ]]; then
  update_repo "$TOOLKIT_DIR" "AMM toolkit"
elif [[ -e "$TOOLKIT_DIR" ]]; then
  warn "Toolkit path $TOOLKIT_DIR exists but is not a Git clone; leaving it intact."
elif ! git clone -q "$TOOLKIT_URL" "$TOOLKIT_DIR"; then
  warn "Could not download the toolkit beside $WORKSPACE_DIR. Retry when online."
else
  ok "AMM toolkit ready at $TOOLKIT_DIR"
fi
install_claude_commands "$TOOLKIT_DIR"

step "4/6" "Installing Herdr terminal command"
if command -v herdr >/dev/null 2>&1; then
  ok "Herdr already installed"
else
  if curl -fsSL "$HERDR_INSTALL_URL" | sh && command -v herdr >/dev/null 2>&1; then
    ok "Herdr terminal command installed (run: herdr)"
  else
    warn "Herdr command is not on PATH yet. Reopen your terminal or retry the Herdr installer."
  fi
fi

step "5/6" "Borg"
if [[ -d "/Applications/Borg.app" || -d "$HOME/Applications/Borg.app" ]]; then
  ok "Borg already installed"
else
  mkdir -p "$HOME/Downloads"
  BORG_DMG="$HOME/Downloads/Borg-0.0.79-mac-arm64.dmg"
  curl -L --fail --silent --show-error "$BORG_DMG_URL" -o "$BORG_DMG"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    open "$BORG_DMG"
    ok "Borg installer opened; drag Borg into Applications"
  else
    ok "Borg downloaded to $BORG_DMG"
  fi
fi

step "6/6" "Warp"
if install_warp; then
  WARP_NOTE="Warp (terminal): ready"
  open_warp
else
  warn "Warp did not install. Get it from $WARP_DOWNLOAD_PAGE when you can; everything else is set up."
  WARP_NOTE="Warp (terminal): not installed, get it from $WARP_DOWNLOAD_PAGE"
fi

printf "
%sEnvironment ready.%s
" "$BOLD" "$NC"
printf "  Terminal commands: Herdr (run: herdr if installed), SHEP (run: %s/shep/bin/shep --help).\n  Claude slash commands: %s/commands.\n  %s\n" "$WORKSPACE_DIR" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "$WARP_NOTE"
