#!/usr/bin/env bash
# AMM Founding Circle — onboard this machine and see where you are on the ladder.
#
#   ./onboarding/onboard.sh                 scan, then open your readout
#   ./onboarding/onboard.sh --ask           also answer what a scan can't see
#   ./onboarding/onboard.sh --install-skills install this repo's skills first
#   ./onboarding/onboard.sh --share jane-smith   write a file you can send to JD
#   ./onboarding/onboard.sh --auto-update        keep this repo current every 2 hours
#   ./onboarding/onboard.sh --auto-update-off    stop that
#
# Everything is presence-only: it checks whether files and commands exist, never
# what is inside them. Nothing is uploaded. Safe to run as many times as you like.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PY="${PYTHON:-python3}"

ASK=0
SHARE=""
INSTALL=0
OPEN=1

usage() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ask) ASK=1 ;;
    --install-skills) INSTALL=1 ;;
    --share) SHARE="${2:-unnamed-member}"; shift ;;
    --no-open) OPEN=0 ;;
    --auto-update) bash "$HERE/install_autosync.sh"; exit $? ;;
    --auto-update-off) bash "$HERE/install_autosync.sh" --remove; exit $? ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 64 ;;
  esac
  shift
done

# --- step 0: preflight ------------------------------------------------------
if ! command -v "$PY" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
python3 is not installed.

  macOS:    xcode-select --install
  Windows:  install Python from python.org, then run this from Git Bash

That is the only thing this needs. Re-run when it is in.
EOF
  exit 69
fi

echo "AMM Founding Circle — ladder check"
echo "repo: $REPO"
echo

# --- step 1: skills (optional) ---------------------------------------------
if [[ $INSTALL -eq 1 ]]; then
  if [[ -f "$REPO/skills/install.sh" ]]; then
    echo "Installing this repo's skills…"
    bash "$REPO/skills/install.sh" || echo "  (skill install reported a problem — the scan still works)"
    echo
  else
    echo "No skills/install.sh found — skipping." && echo
  fi
fi

# --- step 2: scan -----------------------------------------------------------
cd "$HERE"
if [[ $ASK -eq 1 ]]; then
  "$PY" ladder_probe.py --ask
else
  "$PY" ladder_probe.py
fi

# --- step 3: readout --------------------------------------------------------
echo
if [[ $OPEN -eq 1 ]]; then
  "$PY" report.py --open
else
  "$PY" report.py
fi

# --- step 4: share (opt-in) -------------------------------------------------
if [[ -n "$SHARE" ]]; then
  echo
  "$PY" share.py "$SHARE"
fi

echo
echo "Re-run this any time — it is the same command after every change you make,"
echo "or just ask your agent: \"run my AMM ladder audit\"."
if ! bash "$HERE/install_autosync.sh" --status 2>/dev/null | grep -q installed; then
  echo
  echo "Tip: ./onboarding/onboard.sh --auto-update keeps this repo current every 2 hours."
fi
