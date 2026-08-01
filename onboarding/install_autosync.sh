#!/usr/bin/env bash
# Install (or remove) the 2-hourly Founding Circle auto-update.
#
#   ./onboarding/install_autosync.sh            install
#   ./onboarding/install_autosync.sh --remove   uninstall
#   ./onboarding/install_autosync.sh --status   is it installed?
#
# It schedules ONE thing: `autosync.sh`, which fast-forwards your local copy of
# this repo every two hours and re-installs skills if any changed. It does not
# run the ladder audit -- that is yours to trigger, whenever you want it.
#
# macOS uses launchd, Linux/WSL uses a systemd user timer or crontab, and
# Windows Git Bash uses Task Scheduler. Re-running is safe; it replaces cleanly.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.searchatlas.amm.founding-circle-autosync"
SCRIPT="$HERE/autosync.sh"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/amm-founding-circle"
mkdir -p "$CACHE" 2>/dev/null || true
LAUNCH_AGENTS="${LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
PLIST="$LAUNCH_AGENTS/$LABEL.plist"
SYSTEMD="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
CRON_MARK="# $LABEL"

# Every two hours, at :17 — deliberately not :00. If every install in the
# cohort fired on the hour they would all hit the remote at the same instant.
CRON_LINE="17 */2 * * * /bin/bash $SCRIPT >/dev/null 2>&1 $CRON_MARK"

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
    Linux) grep -qi microsoft /proc/version 2>/dev/null && echo wsl || echo linux ;;
    MINGW*|MSYS*|CYGWIN*) echo windows ;;
    *) echo unknown ;;
  esac
}

# --- macOS ------------------------------------------------------------------
macos_install() {
  mkdir -p "$LAUNCH_AGENTS"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$SCRIPT</string></array>
  <key>StartInterval</key><integer>7200</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$CACHE/autosync.log</string>
  <key>StandardErrorPath</key><string>$CACHE/autosync.log</string>
</dict></plist>
EOF
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  launchctl load "$PLIST" >/dev/null 2>&1 || true
  echo "Installed: auto-update every 2 hours (launchd)."
}
macos_remove() {
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  echo "Removed the auto-update job."
}
macos_status() { [[ -f "$PLIST" ]] && echo "installed (launchd): $PLIST" || echo "not installed"; }

# --- Linux / WSL ------------------------------------------------------------
have_systemd() { command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; }

linux_install() {
  if have_systemd; then
    mkdir -p "$SYSTEMD"
    cat > "$SYSTEMD/$LABEL.service" <<EOF
[Unit]
Description=AMM Founding Circle auto-update
[Service]
Type=oneshot
ExecStart=/bin/bash $SCRIPT
EOF
    cat > "$SYSTEMD/$LABEL.timer" <<EOF
[Unit]
Description=AMM Founding Circle auto-update every 2 hours
[Timer]
OnCalendar=*-*-* 00/2:17:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    systemctl --user enable --now "$LABEL.timer" >/dev/null 2>&1 || true
    echo "Installed: auto-update every 2 hours (systemd timer)."
  else
    (crontab -l 2>/dev/null | grep -v "$CRON_MARK" || true; echo "$CRON_LINE") | crontab -
    echo "Installed: auto-update every 2 hours (crontab)."
  fi
}
linux_remove() {
  if have_systemd; then
    systemctl --user disable --now "$LABEL.timer" >/dev/null 2>&1 || true
    rm -f "$SYSTEMD/$LABEL.timer" "$SYSTEMD/$LABEL.service"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
  fi
  (crontab -l 2>/dev/null | grep -v "$CRON_MARK" || true) | crontab - 2>/dev/null || true
  echo "Removed the auto-update job."
}
linux_status() {
  if [[ -f "$SYSTEMD/$LABEL.timer" ]]; then echo "installed (systemd timer)"
  elif crontab -l 2>/dev/null | grep -q "$CRON_MARK"; then echo "installed (crontab)"
  else echo "not installed"; fi
}

# --- Windows (Git Bash) -----------------------------------------------------
windows_install() {
  if command -v schtasks >/dev/null 2>&1; then
    schtasks //Create //TN "$LABEL" //TR "bash \"$SCRIPT\"" //SC HOURLY //MO 2 //ST 00:17 //F >/dev/null 2>&1 \
      && echo "Installed: auto-update every 2 hours (Task Scheduler)." \
      || echo "Could not register the scheduled task — run Git Bash as administrator, or update by hand with ./onboarding/autosync.sh"
  else
    echo "schtasks not found. Update by hand with ./onboarding/autosync.sh"
  fi
}
windows_remove() { schtasks //Delete //TN "$LABEL" //F >/dev/null 2>&1 || true; echo "Removed the auto-update job."; }
windows_status() { schtasks //Query //TN "$LABEL" >/dev/null 2>&1 && echo "installed (Task Scheduler)" || echo "not installed"; }

[[ -f "$SCRIPT" ]] || { echo "cannot find $SCRIPT" >&2; exit 66; }
chmod +x "$SCRIPT" 2>/dev/null || true

case "$(platform)" in
  macos)        "macos_$ACTION" ;;
  linux|wsl)    "linux_$ACTION" ;;
  windows)      "windows_$ACTION" ;;
  *) echo "Unrecognised platform — update by hand with ./onboarding/autosync.sh"; exit 0 ;;
esac

if [[ "$ACTION" == "install" ]]; then
  cat <<'EOF'

Your copy of this repo now fast-forwards itself every 2 hours.
  - It never touches uncommitted work. If your tree is dirty, it skips.
  - It re-installs skills only if you had already installed them.
  - It does NOT run the ladder audit. That is yours to trigger:
        ./onboarding/onboard.sh
    or just ask your agent: "run my AMM ladder audit"

Turn it off any time:  ./onboarding/install_autosync.sh --remove
EOF
fi
