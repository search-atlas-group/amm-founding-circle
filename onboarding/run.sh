#!/usr/bin/env bash
# Run the AMM onboarding audit the portal asked for. Safe to paste every time, from any folder:
#
#   curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/onboarding/run.sh | bash -s -- <code> <portal address>
#
# It finds your Founding Circle folder wherever it is (or downloads it to ~/amm-mothership/founding-circle the first time),
# keeps that Founding Circle copy current when safe, then runs the audit. It never creates a sibling toolkit folder. The audit reads what exists on this computer, never what is inside
# your files, and sends only rung statuses and counts to your portal.
set -euo pipefail

CODE="${1:-}"
PORTAL="${2:-}"
REPO_URL="https://github.com/search-atlas-group/amm-founding-circle.git"
DEFAULT_DIR="$HOME/amm-mothership/founding-circle"

if [[ -z "$CODE" || -z "$PORTAL" ]]; then
  echo "Usage: run.sh <one-time code> <portal address>"
  echo "Press Run audit on the Onboarding page of your portal and copy the command it shows."
  exit 64
fi
# Everything happens from this one command: install anything missing, update the repos, then run the audit.
QUICKSTART="$(mktemp)"
curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.sh -o "$QUICKSTART"
# Discover before setup, not after it has had a chance to clone a duplicate.
AMM_QUICKSTART_LIB=1 source "$QUICKSTART"
DIR="$(find_fc_folder || true)"
if [[ -n "$DIR" ]]; then
  echo "Selected Founding Circle folder: $DIR"
  export AMM_WORKSPACE="$DIR"
fi
bash "$QUICKSTART"

for tool in git python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is not installed. Do step 1 on the Onboarding page (set up your coding environment), then paste this again."; exit 69; }
done

DIR="$(find_fc_folder || true)"
[[ -n "$DIR" ]] || { echo "No valid Founding Circle clone found after setup; no folders were removed."; exit 1; }
echo "Running audit from selected Founding Circle folder: $DIR"
# The parent of the selected clone is the mothership parent; this is where a legacy
# sibling would have lived. Keep it explicit so cleanup never targets the clone.
HOME_PARENT="$(dirname "$DIR")"
# A local edit blocks fast-forwarding. Never overwrite it and never run a stale
# audit when a fresh origin/main is available: use an isolated archive instead.
if [[ -d "$DIR/.git" && -n "$(git -C "$DIR" status --porcelain 2>/dev/null)" ]]; then
  if git -C "$DIR" fetch -q origin main 2>/dev/null && git -C "$DIR" rev-parse --verify origin/main >/dev/null 2>&1; then
    FRESH="$(mktemp -d)"
    git -C "$DIR" archive origin/main | tar -x -C "$FRESH"
    DIR="$FRESH"
    echo "Local work was preserved; running the audit from a clean updated copy instead: $DIR"
  else
    echo "Local work is preserved, but no cached updated copy is available; audit will use the existing folder."
  fi
fi

# Setup check: the audit tells you what is missing and how to fix it. Nothing here stops the audit.
echo "Checking your agentic setup:"
ok()   { echo "  [ok]      $1"; }
miss() { echo "  [missing] $1"; echo "            Fix: $2"; }
command -v node   >/dev/null 2>&1 && ok "Node.js"     || miss "Node.js"     "the quickstart above should have installed it"
command -v claude >/dev/null 2>&1 && ok "Claude Code" || miss "Claude Code" "run the Founding Circle setup again"
if [[ "$(uname -s)" == "Darwin" ]]; then
  [[ -d /Applications/Borg.app || -d "$HOME/Applications/Borg.app" ]] && ok "Borg" || miss "Borg" "download it from step 2 on the Onboarding page (or use https://app.getborg.com)"
fi
# (`claude plugin install searchatlas`), which never touches that folder. Either one counts.
has_sa_commands() {
  local cfg="${CLAUDE_CONFIG_DIR:-$HOME/.claude}" f out
  [[ -n "$(ls -A "$cfg/commands" 2>/dev/null)" ]] && return 0
  for f in "$cfg/plugins/installed_plugins.json" "$HOME/.claude/plugins/installed_plugins.json"; do
    [[ -f "$f" ]] && grep -qi searchatlas "$f" && return 0
  done
  command -v claude >/dev/null 2>&1 || return 1
  out="$(claude plugin list </dev/null 2>/dev/null || true)"   # captured first: grep -q on a pipe trips pipefail
  grep -qi searchatlas <<<"$out"
}
has_sa_commands && ok "SearchAtlas slash commands" || miss "SearchAtlas slash commands" "run step 1 on the Onboarding page"
[[ -x "$DIR/shep/bin/shep" ]] && ok "SHEP command deck" || miss "SHEP command deck" "run ./shep/bin/shep --help from the Founding Circle folder"
echo

# All AMM skills, artifacts, and tools are in the selected Founding Circle clone.
# Never create, update, delete, or merge a sibling toolkit folder.
LEGACY_TOOLKIT="$HOME_PARENT/amm-toolkit"
[[ -e "$LEGACY_TOOLKIT" ]] && echo "Legacy AMM toolkit folder left untouched: $LEGACY_TOOLKIT"

[[ -f "$DIR/onboarding/portal.py" ]] || { echo "This copy lacks onboarding/portal.py. Keep the folder; back up local work and seek help updating it. No folder was deleted."; exit 1; }
chmod +x "$DIR/onboarding/onboard.sh" 2>/dev/null || true
exec "$DIR/onboarding/onboard.sh" --run "$CODE" --portal "$PORTAL"
