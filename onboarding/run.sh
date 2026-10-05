#!/usr/bin/env bash
# Run the AMM onboarding audit the portal asked for. Safe to paste every time, from any folder:
#
#   curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/onboarding/run.sh | bash -s -- <code> <portal address>
#
# It finds your Founding Circle folder wherever it is (or downloads it to ~/amm-founding-circle the first time),
# brings it up to date, then runs the audit. The audit reads what exists on this computer, never what is inside
# your files, and sends only rung statuses and counts to your portal.
set -euo pipefail

CODE="${1:-}"
PORTAL="${2:-}"
REPO_URL="https://github.com/search-atlas-group/amm-founding-circle.git"
DEFAULT_DIR="$HOME/amm-founding-circle"

if [[ -z "$CODE" || -z "$PORTAL" ]]; then
  echo "Usage: run.sh <one-time code> <portal address>"
  echo "Press Run audit on the Onboarding page of your portal and copy the command it shows."
  exit 64
fi
for tool in git python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is not installed. Do step 1 on the Onboarding page (set up your coding environment), then paste this again."; exit 69; }
done

# Setup check: the audit tells you what is missing and how to fix it. Nothing here stops the audit.
echo "Checking your agentic setup:"
ok()   { echo "  [ok]      $1"; }
miss() { echo "  [missing] $1"; echo "            Fix: $2"; }
command -v node   >/dev/null 2>&1 && ok "Node.js"     || miss "Node.js"     "run step 1 on the Onboarding page"
command -v claude >/dev/null 2>&1 && ok "Claude Code" || miss "Claude Code" "run step 1 on the Onboarding page"
if [[ "$(uname -s)" == "Darwin" ]]; then
  [[ -d /Applications/Borg.app || -d "$HOME/Applications/Borg.app" ]] && ok "Borg" || miss "Borg" "install it from step 2 on the Onboarding page"
fi
[[ -d "$HOME/.claude/commands" ]] && ls "$HOME/.claude/commands" 2>/dev/null | grep -q . && ok "SearchAtlas slash commands" || miss "SearchAtlas slash commands" "run step 1 on the Onboarding page"
echo

is_folder() { [[ -d "$1/onboarding" && -d "$1/.git" ]]; }

DIR=""
for d in "${AMM_FOUNDING_CIRCLE_DIR:-}" "$PWD" "$PWD/amm-founding-circle" "$DEFAULT_DIR" \
         "$HOME"/Desktop/amm-founding-circle "$HOME"/Desktop/*/amm-founding-circle \
         "$HOME"/Documents/amm-founding-circle "$HOME"/Documents/*/amm-founding-circle \
         "$HOME"/Developer/amm-founding-circle "$HOME"/Code/amm-founding-circle "$HOME"/code/amm-founding-circle; do
  [[ -n "$d" ]] && is_folder "$d" && { DIR="$d"; break; }
done

if [[ -z "$DIR" ]]; then
  echo "Downloading the Founding Circle folder to $DEFAULT_DIR ..."
  git clone -q "$REPO_URL" "$DEFAULT_DIR"
  DIR="$DEFAULT_DIR"
else
  echo "Using your Founding Circle folder: $DIR"
  if ! git -C "$DIR" pull --ff-only -q 2>/dev/null; then
    echo "Could not update it automatically (you have changes of your own there). Running the version you have."
  fi
fi

[[ -f "$DIR/onboarding/portal.py" ]] || { echo "This copy is too old and could not be updated. Run: git -C \"$DIR\" pull"; exit 1; }
chmod +x "$DIR/onboarding/onboard.sh" 2>/dev/null || true
exec "$DIR/onboarding/onboard.sh" --run "$CODE" --portal "$PORTAL"
