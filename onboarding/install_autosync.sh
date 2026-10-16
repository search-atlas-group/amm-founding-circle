#!/usr/bin/env bash
# Install (or remove) the 2-hourly Founding Circle auto-update.
#
#   ./onboarding/install_autosync.sh            install
#   ./onboarding/install_autosync.sh --remove   uninstall
#   ./onboarding/install_autosync.sh --status   is it installed?
#
# It schedules two things. `autosync.sh` fast-forwards your local copy every
# two hours and re-installs skills if any changed. `nova_daily.sh` runs once a
# day: the ladder, what is in the way, and how you work, written locally. It
# uploads the ladder scan only when this machine is already connected, and it
# never uploads session text. The full ladder audit is still yours to trigger.
#
# macOS uses launchd, Linux/WSL uses a systemd user timer or crontab, and
# Windows Git Bash uses Task Scheduler. Re-running is safe; it replaces cleanly.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.searchatlas.amm.founding-circle-autosync"
DAILY_LABEL="com.searchatlas.amm.founding-circle-nova-daily"
SCRIPT="$HERE/autosync.sh"
DAILY="$HERE/nova_daily.sh"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/amm-founding-circle"
mkdir -p "$CACHE" 2>/dev/null || true
LAUNCH_AGENTS="${LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
PLIST="$LAUNCH_AGENTS/$LABEL.plist"
SYSTEMD="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
CRON_MARK="# $LABEL"
DAILY_MARK="# $DAILY_LABEL"

# Every two hours, at :17 — deliberately not :00. If every install in the
# cohort fired on the hour they would all hit the remote at the same instant.
CRON_LINE="17 */2 * * * /bin/bash $SCRIPT >/dev/null 2>&1 $CRON_MARK"
DAILY_LINE="17 7 * * * /bin/bash $DAILY >/dev/null 2>&1 $DAILY_MARK"

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
  cat > "$LAUNCH_AGENTS/$DAILY_LABEL.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$DAILY_LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$DAILY</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>17</integer></dict>
  <key>StandardOutPath</key><string>$CACHE/nova-daily.log</string>
  <key>StandardErrorPath</key><string>$CACHE/nova-daily.log</string>
</dict></plist>
EOF
  launchctl unload "$LAUNCH_AGENTS/$DAILY_LABEL.plist" >/dev/null 2>&1 || true
  launchctl load "$LAUNCH_AGENTS/$DAILY_LABEL.plist" >/dev/null 2>&1 || true
  echo "Installed: auto-update every 2 hours, and Nova's diagnostic daily at 07:17 (launchd)."
}
macos_remove() {
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  launchctl unload "$LAUNCH_AGENTS/$DAILY_LABEL.plist" >/dev/null 2>&1 || true
  rm -f "$PLIST" "$LAUNCH_AGENTS/$DAILY_LABEL.plist"
  echo "Removed the auto-update job and Nova's daily diagnostic."
}
macos_status() {
  if [[ -f "$PLIST" && -f "$LAUNCH_AGENTS/$DAILY_LABEL.plist" ]]; then echo "installed (launchd, with daily diagnostic)"
  elif [[ -f "$PLIST" ]]; then echo "installed (launchd)"
  else echo "not installed"; fi
}

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
    cat > "$SYSTEMD/$DAILY_LABEL.service" <<EOF
[Unit]
Description=Nova's daily Founding Circle diagnostic
[Service]
Type=oneshot
ExecStart=/bin/bash $DAILY
EOF
    cat > "$SYSTEMD/$DAILY_LABEL.timer" <<EOF
[Unit]
Description=Nova's diagnostic, once a day
[Timer]
OnCalendar=*-*-* 07:17:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    systemctl --user enable --now "$DAILY_LABEL.timer" >/dev/null 2>&1 || true
    echo "Installed: auto-update every 2 hours, and Nova's diagnostic daily at 07:17 (systemd)."
  else
    (crontab -l 2>/dev/null | grep -v "$CRON_MARK" | grep -v "$DAILY_MARK" || true; echo "$CRON_LINE"; echo "$DAILY_LINE") | crontab -
    echo "Installed: auto-update every 2 hours, and Nova's diagnostic daily at 07:17 (crontab)."
  fi
}
linux_remove() {
  if have_systemd; then
    systemctl --user disable --now "$LABEL.timer" >/dev/null 2>&1 || true
    systemctl --user disable --now "$DAILY_LABEL.timer" >/dev/null 2>&1 || true
    rm -f "$SYSTEMD/$LABEL.timer" "$SYSTEMD/$LABEL.service" "$SYSTEMD/$DAILY_LABEL.timer" "$SYSTEMD/$DAILY_LABEL.service"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
  fi
  (crontab -l 2>/dev/null | grep -v "$CRON_MARK" | grep -v "$DAILY_MARK" || true) | crontab - 2>/dev/null || true
  echo "Removed the auto-update job and Nova's daily diagnostic."
}
linux_status() {
  if [[ -f "$SYSTEMD/$LABEL.timer" && -f "$SYSTEMD/$DAILY_LABEL.timer" ]]; then echo "installed (systemd, with daily diagnostic)"
  elif [[ -f "$SYSTEMD/$LABEL.timer" ]]; then echo "installed (systemd timer)"
  elif crontab -l 2>/dev/null | grep -q "$DAILY_MARK"; then echo "installed (crontab, with daily diagnostic)"
  elif crontab -l 2>/dev/null | grep -q "$CRON_MARK"; then echo "installed (crontab)"
  else echo "not installed"; fi
}

# --- Windows (Git Bash) -----------------------------------------------------
windows_install() {
  if command -v schtasks >/dev/null 2>&1; then
    schtasks //Create //TN "$LABEL" //TR "bash \"$SCRIPT\"" //SC HOURLY //MO 2 //ST 00:17 //F >/dev/null 2>&1 \
      && echo "Installed: auto-update every 2 hours (Task Scheduler)." \
      || echo "Could not register the scheduled task — run Git Bash as administrator, or update by hand with ./onboarding/autosync.sh"
    schtasks //Create //TN "$DAILY_LABEL" //TR "bash \"$DAILY\"" //SC DAILY //ST 07:17 //F >/dev/null 2>&1 \
      && echo "Installed: Nova's diagnostic daily at 07:17 (Task Scheduler)." \
      || echo "Could not register Nova's daily diagnostic."
  else
    echo "schtasks not found. Update by hand with ./onboarding/autosync.sh"
  fi
}
windows_remove() {
  schtasks //Delete //TN "$LABEL" //F >/dev/null 2>&1 || true
  schtasks //Delete //TN "$DAILY_LABEL" //F >/dev/null 2>&1 || true
  echo "Removed the auto-update job and Nova's daily diagnostic."
}
windows_status() { schtasks //Query //TN "$DAILY_LABEL" >/dev/null 2>&1 && echo "installed (Task Scheduler, with daily diagnostic)" || { schtasks //Query //TN "$LABEL" >/dev/null 2>&1 && echo "installed (Task Scheduler)" || echo "not installed"; }; }

[[ -f "$SCRIPT" ]] || { echo "cannot find $SCRIPT" >&2; exit 66; }
chmod +x "$SCRIPT" 2>/dev/null || true
chmod +x "$DAILY" 2>/dev/null || true

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
  - After a pull it repairs Hermes quietly: installs it if it is missing,
    keeps the Founding Circle skills on its path, and never opens a window.
  - Once a day, at 07:17, Nova reads the ladder, what is in the way, and how
    you work, and writes it to ~/.cache/amm-founding-circle/nova-daily.log.
    If this machine is connected to the portal, that same run uploads the
    ladder scan. It never uploads session text.
  - It does NOT run the ladder audit. That is yours to trigger:
        ./onboarding/onboard.sh
    or just ask your agent: "run my AMM ladder audit"

Turn it off any time:  ./onboarding/install_autosync.sh --remove
EOF
fi
