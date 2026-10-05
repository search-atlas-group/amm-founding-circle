#!/usr/bin/env bash
# Run the AMM onboarding audit the portal asked for. Safe to paste every time, from any folder:
#
#   curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/onboarding/run.sh | bash -s -- <code> <portal address>
#
# It finds your Founding Circle folder wherever it is (or downloads it to ~/amm-founding-circle the first time),
# keeps it and the AMM toolkit beside it up to date (cloning the toolkit if missing), then runs the audit. The audit reads what exists on this computer, never what is inside
# your files, and sends only rung statuses and counts to your portal.
set -euo pipefail

CODE="${1:-}"
PORTAL="${2:-}"
REPO_URL="https://github.com/search-atlas-group/amm-founding-circle.git"
TOOLKIT_URL="https://github.com/search-atlas-group/amm-toolkit.git"
DEFAULT_DIR="$HOME/amm-founding-circle"

if [[ -z "$CODE" || -z "$PORTAL" ]]; then
  echo "Usage: run.sh <one-time code> <portal address>"
  echo "Press Run audit on the Onboarding page of your portal and copy the command it shows."
  exit 64
fi
# Everything happens from this one command: install anything missing, update the repos, then run the audit.
QUICKSTART="$(mktemp)"
curl -fsSL https://raw.githubusercontent.com/search-atlas-group/amm-founding-circle/main/quickstart.sh -o "$QUICKSTART"
bash "$QUICKSTART"

for tool in git python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is not installed. Do step 1 on the Onboarding page (set up your coding environment), then paste this again."; exit 69; }
done


is_folder() { [[ -d "$1/onboarding" && -d "$1/.git" ]]; }

DIR=""
for d in "${AMM_FOUNDING_CIRCLE_DIR:-}" "$PWD" "$PWD/amm-founding-circle" "$DEFAULT_DIR" \
         "$HOME"/Desktop/amm-founding-circle "$HOME"/Desktop/*/amm-founding-circle "$HOME"/Desktop/*/*/amm-founding-circle \
         "$HOME"/Documents/amm-founding-circle "$HOME"/Documents/*/amm-founding-circle \
         "$HOME"/Developer/amm-founding-circle "$HOME"/Code/amm-founding-circle "$HOME"/code/amm-founding-circle; do
  [[ -n "$d" ]] && is_folder "$d" && { DIR="$d"; break; }
done

if [[ -z "$DIR" ]]; then
  echo "Downloading the Founding Circle folder to $DEFAULT_DIR ..."
  git clone -q "$REPO_URL" "$DEFAULT_DIR"
  DIR="$DEFAULT_DIR"
  HOME_PARENT="$(dirname "$DIR")"
else
  echo "Using your Founding Circle folder: $DIR"
  HOME_PARENT="$(dirname "$DIR")"
  # Guarantee the latest: fetch, fast-forward, then verify the folder matches GitHub's main. If something of the
  # member's own blocks the update, never run the stale copy: run a clean copy of the latest instead.
  if ! git -C "$DIR" fetch -q origin main 2>/dev/null; then
    echo "Could not reach GitHub to check for updates. Running the version you have."
  else
    git -C "$DIR" merge --ff-only -q origin/main 2>/dev/null || true
    if [[ "$(git -C "$DIR" rev-parse HEAD)" == "$(git -C "$DIR" rev-parse origin/main)" ]]; then
      echo "Up to date ($(git -C "$DIR" rev-parse --short HEAD))."
    else
      echo "Your folder has changes of your own that block the update, so it was left alone."
      FRESH="$(mktemp -d)"
      LATEST="$(git -C "$DIR" rev-parse --short origin/main)"
      git -C "$DIR" archive origin/main | tar -x -C "$FRESH"
      DIR="$FRESH"
      echo "Running a clean copy of the latest ($LATEST)."
    fi
  fi
fi

# Setup check: the audit tells you what is missing and how to fix it. Nothing here stops the audit.
echo "Checking your agentic setup:"
ok()   { echo "  [ok]      $1"; }
miss() { echo "  [missing] $1"; echo "            Fix: $2"; }
command -v node   >/dev/null 2>&1 && ok "Node.js"     || miss "Node.js"     "the quickstart above should have installed it"
command -v claude >/dev/null 2>&1 && ok "Claude Code" || miss "Claude Code" "install it from the AMM toolkit setup"
if [[ "$(uname -s)" == "Darwin" ]]; then
  [[ -d /Applications/Borg.app || -d "$HOME/Applications/Borg.app" ]] && ok "Borg" || miss "Borg" "download it from step 2 on the Onboarding page (or use https://app.getborg.com)"
fi
[[ -d "$HOME/.claude/commands" ]] && ls "$HOME/.claude/commands" 2>/dev/null | grep -q . && ok "SearchAtlas slash commands" || miss "SearchAtlas slash commands" "run step 1 on the Onboarding page"
[[ -x "$DIR/shep/bin/shep" ]] && ok "SHEP command deck" || miss "SHEP command deck" "run ./shep/bin/shep --help from the Founding Circle folder"
echo

# The toolkit (slash commands, setup) lives beside the Founding Circle. Same guarantee: clone it if missing, else
# bring it up to date. It never blocks the audit.
TK="$HOME_PARENT/amm-toolkit"
if [[ -d "$TK/.git" ]]; then
  git -C "$TK" fetch -q origin main 2>/dev/null && git -C "$TK" merge --ff-only -q origin/main 2>/dev/null || true
  if [[ "$(git -C "$TK" rev-parse HEAD 2>/dev/null)" == "$(git -C "$TK" rev-parse origin/main 2>/dev/null)" ]]; then
    echo "Toolkit up to date ($(git -C "$TK" rev-parse --short HEAD))."
  else
    echo "Toolkit left as it is (your own changes, or GitHub unreachable)."
  fi
else
  echo "Downloading the AMM toolkit to $TK ..."
  git clone -q "$TOOLKIT_URL" "$TK" 2>/dev/null && echo "Toolkit ready." || echo "Could not download the toolkit. The audit still runs."
fi
echo

[[ -f "$DIR/onboarding/portal.py" ]] || { echo "This copy is too old and could not be updated. Delete it and paste the command again to download a fresh one."; exit 1; }
chmod +x "$DIR/onboarding/onboard.sh" 2>/dev/null || true
exec "$DIR/onboarding/onboard.sh" --run "$CODE" --portal "$PORTAL"
