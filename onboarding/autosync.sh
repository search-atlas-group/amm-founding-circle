#!/usr/bin/env bash
# Keep your local Founding Circle copy current.
#
# Runs on a schedule (installed by install_autosync.sh) or by hand. It only ever
# fast-forwards: if you have local changes or your branch has diverged, it stops
# and leaves everything exactly as it was. It will never discard your work.
#
#   ./onboarding/autosync.sh          pull, then re-install skills if anything changed
#   ./onboarding/autosync.sh --check  say whether you are behind, change nothing
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
# The log lives OUTSIDE the repo on purpose. Writing it inside would leave the
# working tree permanently dirty, and the dirty-tree guard below would then
# block every future pull -- the job would silently disable itself after one run.
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/amm-founding-circle"
mkdir -p "$CACHE" 2>/dev/null || true
LOG="$CACHE/autosync.log"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
say() { echo "$*"; log "$*"; }

cd "$REPO"

command -v git >/dev/null 2>&1 || { say "autosync: git not found, nothing to do"; exit 0; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { say "autosync: not a git repo"; exit 0; }

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Never touch a working tree with uncommitted changes. A member may be mid-edit
# on their own copy; silently stashing or resetting that would be unforgivable.
if [[ -n "$(git status --porcelain)" ]]; then
  say "autosync: you have local changes — skipping the pull so nothing of yours is lost"
  exit 0
fi

git fetch --quiet origin "$BRANCH" 2>/dev/null || { say "autosync: could not reach the remote (offline?)"; exit 0; }

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "$LOCAL")"
if [[ "$LOCAL" == "$REMOTE" ]]; then
  log "autosync: already current ($BRANCH)"
  [[ $CHECK_ONLY -eq 1 ]] && echo "Founding Circle is up to date."
  exit 0
fi

BEHIND="$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)"
if [[ $CHECK_ONLY -eq 1 ]]; then
  echo "Founding Circle is $BEHIND commit(s) behind. Run ./onboarding/autosync.sh to update."
  exit 0
fi

if ! git merge-base --is-ancestor HEAD "origin/$BRANCH" 2>/dev/null; then
  say "autosync: your branch has diverged from the remote — leaving it alone, sort it by hand"
  exit 0
fi

if ! git merge --ff-only "origin/$BRANCH" --quiet 2>/dev/null; then
  say "autosync: fast-forward failed — leaving your copy untouched"
  exit 0
fi

say "autosync: updated $BRANCH by $BEHIND commit(s)"

# Re-install skills so a new or changed skill is actually usable. Only when the
# member already installed them once -- we never install on a machine that
# never opted in.
if [[ -f "$REPO/skills/install.sh" ]] && [[ -n "$(ls -A "$HOME/.claude/skills" 2>/dev/null || true)" ]]; then
  if bash "$REPO/skills/install.sh" >>"$LOG" 2>&1; then
    log "autosync: skills re-installed"
  else
    log "autosync: skill re-install reported a problem (see above)"
  fi
fi

# Tell them, quietly. No report is regenerated here -- the ladder audit is
# something they run when they want it, not something that surprises them.
NEW="$(git log --oneline "$LOCAL..HEAD" --format='%s' | head -3 | sed 's/^/  • /')"
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$BEHIND update(s) pulled. Run ./onboarding/onboard.sh for a fresh ladder audit.\" with title \"AMM Founding Circle\"" 2>/dev/null || true
fi
say "what changed:"
printf '%s\n' "$NEW" | tee -a "$LOG"
