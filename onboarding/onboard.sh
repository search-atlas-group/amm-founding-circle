#!/usr/bin/env bash
# AMM Founding Circle — onboard this machine and see where you are on the ladder.
#
#   ./onboarding/onboard.sh                 scan, then open your readout
#   ./onboarding/onboard.sh --ask           also answer what a scan can't see
#   ./onboarding/onboard.sh --install-skills install this repo's skills first
#   ./onboarding/onboard.sh --share jane-smith   write a file you can send to JD
#   ./onboarding/onboard.sh --connect --portal <address>   link this machine to the AMM portal
#   ./onboarding/onboard.sh --publish [--yes]   scan, then send your result to the portal
#   ./onboarding/onboard.sh --pair <code> --portal <address>   connect with the portal's one-time code, keep listening
#   ./onboarding/onboard.sh --run <code> --portal <address>   run the audit the portal asked for, once
#   ./onboarding/onboard.sh --listen            wait for the portal's Run audit button (Ctrl+C stops)
#   ./onboarding/onboard.sh --disconnect        forget the portal token and stop the background connector
#   ./onboarding/onboard.sh --auto-update        keep this repo current every 2 hours
#   ./onboarding/onboard.sh --auto-update-off    stop that
#
# Everything is presence-only: it checks whether files and commands exist, never
# what is inside them. The scan makes no network call; only --connect and
# --publish do, and only when you type them. Safe to run as many times as you like.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PY="${PYTHON:-python3}"

ASK=0
SHARE=""
INSTALL=0
OPEN=1
CONNECT=0
DISCONNECT=0
PUBLISH=0
YES=0
PORTAL=""
PAIR=""
LISTEN=0
RUN=0
RUNCODE=""
BACKGROUND=1

usage() { sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ask) ASK=1 ;;
    --install-skills) INSTALL=1 ;;
    --share) SHARE="${2:-unnamed-member}"; shift ;;
    --no-open) OPEN=0 ;;
    --connect) CONNECT=1 ;;
    --disconnect) DISCONNECT=1 ;;
    --publish) PUBLISH=1 ;;
    --yes) YES=1 ;;
    --portal) PORTAL="${2:-}"; shift ;;
    --pair) PAIR="${2:-}"; shift ;;
    --listen) LISTEN=1 ;;
    --run) RUN=1; if [[ -n "${2:-}" && "${2:-}" != --* ]]; then RUNCODE="$2"; shift; fi ;;
    --no-background) BACKGROUND=0 ;;
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

# --- portal connection (no scan) -------------------------------------------
if [[ $DISCONNECT -eq 1 ]]; then
  bash "$HERE/install_connector.sh" --remove >/dev/null 2>&1 || true
  cd "$HERE" && exec "$PY" portal.py --disconnect
fi
if [[ -n "$PAIR" ]]; then
  cd "$HERE"
  if [[ -n "$PORTAL" ]]; then "$PY" portal.py --pair "$PAIR" --portal "$PORTAL" || exit $?; else "$PY" portal.py --pair "$PAIR" || exit $?; fi
  if [[ $BACKGROUND -eq 1 ]] && bash "$HERE/install_connector.sh"; then
    echo "All set. Press Run audit in the portal any time this computer is on."
    exit 0
  fi
  echo "Keep this window open: it is the connector. Press Run audit in the portal."
  exec "$PY" portal.py --listen
fi
if [[ $RUN -eq 1 ]]; then
  cd "$HERE"
  ARGS=(portal.py --run)
  [[ -n "$RUNCODE" ]] && ARGS+=("$RUNCODE")
  [[ -n "$PORTAL" ]] && ARGS+=(--portal "$PORTAL")
  exec "$PY" "${ARGS[@]}"
fi
if [[ $LISTEN -eq 1 ]]; then
  cd "$HERE" && exec "$PY" portal.py --listen
fi
if [[ $CONNECT -eq 1 ]]; then
  cd "$HERE"
  if [[ -n "$PORTAL" ]]; then exec "$PY" portal.py --connect --portal "$PORTAL"; fi
  exec "$PY" portal.py --connect
fi

# --- publish preflight: fail before the audit if not connected -------------
if [[ $PUBLISH -eq 1 ]]; then
  (cd "$HERE" && "$PY" portal.py --preflight) || exit $?
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

# --- step 5: publish to the portal (opt-in) -------------------------------
if [[ $PUBLISH -eq 1 ]]; then
  echo
  if [[ $YES -eq 1 ]]; then
    "$PY" portal.py --publish --yes || exit $?
  else
    "$PY" portal.py --publish || exit $?
  fi
fi

echo
echo "Re-run this any time — it is the same command after every change you make,"
echo "or just ask your agent: \"run my AMM ladder audit\"."
if ! bash "$HERE/install_autosync.sh" --status 2>/dev/null | grep -q installed; then
  echo
  echo "Tip: ./onboarding/onboard.sh --auto-update keeps this repo current every 2 hours."
fi
