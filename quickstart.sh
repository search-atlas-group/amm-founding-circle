#!/usr/bin/env bash
# AMM Founding Circle quickstart: one command for the full member setup.
#
# Usage from any folder:
#   curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.sh | bash
#
# It installs the AMM coding environment, clones and updates this Founding Circle repo and the AMM toolkit beside it,
# installs Herdr, and downloads the Borg Mac installer. SHEP is included in this repo. The onboarding audit then
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
WORKSPACE_DIR="${AMM_WORKSPACE:-$HOME/amm-founding-circle}"

step "1/5" "Checking prerequisites"
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

step "2/5" "Getting the Founding Circle"
if [[ -d "$WORKSPACE_DIR/.git" ]]; then
  git -C "$WORKSPACE_DIR" fetch -q origin main 2>/dev/null || true
  git -C "$WORKSPACE_DIR" merge --ff-only -q origin/main 2>/dev/null || true
else
  git clone -q "$FC_URL" "$WORKSPACE_DIR"
fi
ok "Founding Circle ready at $WORKSPACE_DIR"
export AMM_FOUNDING_CIRCLE_DIR="$WORKSPACE_DIR"

step "3/5" "Getting the AMM toolkit"
TOOLKIT_DIR="$(dirname "$WORKSPACE_DIR")/amm-toolkit"
if [[ -d "$TOOLKIT_DIR/.git" ]]; then
  git -C "$TOOLKIT_DIR" fetch -q origin main 2>/dev/null || true
  git -C "$TOOLKIT_DIR" merge --ff-only -q origin main 2>/dev/null || true
else
  git clone -q "$TOOLKIT_URL" "$TOOLKIT_DIR"
fi
ok "AMM toolkit ready"

step "4/5" "Installing Herdr"
if command -v herdr >/dev/null 2>&1; then
  ok "Herdr already installed"
else
  curl -fsSL "$HERDR_INSTALL_URL" | sh
  ok "Herdr installed"
fi

step "5/5" "Borg"
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

cat <<DONE

${BOLD}Setup complete.${NC}
The AMM onboarding audit can now find everything it needs.
Run it from your portal, or from this folder:
  $WORKSPACE_DIR/onboarding/onboard.sh --publish

DONE
