#!/usr/bin/env bash
# Keep the portal connector running in the background, so the "Run audit" button
# in the portal works whenever this computer is on.
#
#   ./onboarding/install_connector.sh            install and start
#   ./onboarding/install_connector.sh --remove   stop and uninstall
#   ./onboarding/install_connector.sh --status   is it installed?
#
# The connector only waits for your own button press in your own portal session.
# It runs the same audit as onboard.sh, sends progress lines and the stripped
# result (no file paths, repo names or file contents), and does nothing else.
# macOS uses launchd, Linux a systemd user service. Re-running is safe.
# On Windows use: .\onboarding\onboard.ps1 -Pair <code> -Portal <address>
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.searchatlas.amm.connector"
PY="${PYTHON:-$(command -v python3 || true)}"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/amm-founding-circle"
mkdir -p "$CACHE" 2>/dev/null || true
AGENT_DIR="${LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
PLIST="$AGENT_DIR/$LABEL.plist"
SYSTEMD="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
UNIT="$SYSTEMD/$LABEL.service"

ACTION="install"
case "${1:-}" in
  --remove|--uninstall|--off) ACTION="remove" ;;
  --status) ACTION="status" ;;
  -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "unknown option: $1" >&2; exit 64 ;;
esac

platform() {
  case "$(uname -s)" in
    Darwin) echo macos ;;
    Linux) echo linux ;;
    *) echo unknown ;;
  esac
}
have_systemd() { command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; }

macos_install() {
  mkdir -p "$AGENT_DIR"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>$HERE/portal.py</string><string>--listen</string></array>
  <key>WorkingDirectory</key><string>$HERE</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$CACHE/connector.log</string>
  <key>StandardErrorPath</key><string>$CACHE/connector.log</string>
</dict></plist>
PLISTEOF
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  launchctl load -w "$PLIST" >/dev/null 2>&1 || { echo "Could not start the background connector. Run it in this window instead: ./onboarding/onboard.sh --listen"; return 1; }
  echo "Installed: the portal connector now runs in the background (launchd). Log: $CACHE/connector.log"
}
macos_remove() { launchctl unload "$PLIST" >/dev/null 2>&1 || true; rm -f "$PLIST"; echo "Removed the background connector."; }
macos_status() { [[ -f "$PLIST" ]] && echo "installed (launchd): $PLIST" || echo "not installed"; }

linux_install() {
  if ! have_systemd; then
    echo "No systemd user session here. Run it in a terminal instead: ./onboarding/onboard.sh --listen"
    return 1
  fi
  mkdir -p "$SYSTEMD"
  cat > "$UNIT" <<UNITEOF
[Unit]
Description=AMM portal connector
[Service]
WorkingDirectory=$HERE
ExecStart=$PY $HERE/portal.py --listen
Restart=always
RestartSec=30
[Install]
WantedBy=default.target
UNITEOF
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user enable --now "$LABEL.service" >/dev/null 2>&1 || { echo "Could not start the background connector. Run it in a terminal: ./onboarding/onboard.sh --listen"; return 1; }
  echo "Installed: the portal connector now runs in the background (systemd user service)."
}
linux_remove() {
  if have_systemd; then
    systemctl --user disable --now "$LABEL.service" >/dev/null 2>&1 || true
    rm -f "$UNIT"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
  fi
  echo "Removed the background connector."
}
linux_status() { [[ -f "$UNIT" ]] && echo "installed (systemd user service)" || echo "not installed"; }

[[ -n "$PY" ]] || { echo "python3 is not installed." >&2; exit 69; }
case "$(platform)" in
  macos) "macos_$ACTION" ;;
  linux) "linux_$ACTION" ;;
  *) echo "Background install is for macOS and Linux. On Windows use onboard.ps1 -Pair. Anywhere: ./onboarding/onboard.sh --listen"; exit 64 ;;
esac
