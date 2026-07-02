#!/usr/bin/env bash
# goal-notify.sh — visible desktop notification + optional sound for goal-mode.
#
# Used by the `goal-mode` skill to surface progress while the agent keeps
# working toward a completion condition. The skill calls this on each
# meaningful state change ("ping on each update") and on the ~5-minute
# heartbeat cadence, plus once when the goal is met or cleared.
#
# Cross-platform dispatch (first available wins):
#   macOS    -> osascript 'display notification ...'
#   Windows  -> PowerShell toast (BurntToast module, NotifyIcon balloon fallback)
#   other    -> graceful stderr fallback (skill still runs, no visible alert)
#
# Usage:
#   goal-notify.sh "<message>" [title] [subtitle] [sound]
#
# Defaults:
#   title    = "goal-mode"
#   subtitle = ""           (omitted from the AppleScript if empty)
#   sound    = "Glass"      (pass "none" to suppress the sound)
#
# Examples:
#   goal-notify.sh "Tests passing — 4/6 checks green"
#   goal-notify.sh "Build failed" "goal-mode" "needs attention" "Basso"
#   goal-notify.sh "Heartbeat: still working" "goal-mode" "5-min update" none
#
# Exit codes:
#   0  notification dispatched (or non-notifier no-op logged to stderr)
#   2  missing message argument

set -euo pipefail

MSG="${1:-}"
TITLE="${2:-goal-mode}"
SUBTITLE="${3:-}"
SOUND="${4:-Glass}"

if [ -z "$MSG" ]; then
  echo "goal-notify: message is required" >&2
  echo "usage: goal-notify.sh \"<message>\" [title] [subtitle] [sound]" >&2
  exit 2
fi

# Escape embedded double-quotes so the AppleScript string stays well-formed.
esc() { printf '%s' "$1" | sed 's/"/\\"/g'; }
MSG_E="$(esc "$MSG")"
TITLE_E="$(esc "$TITLE")"
SUBTITLE_E="$(esc "$SUBTITLE")"

# Build the AppleScript. Subtitle and sound clauses are optional.
script="display notification \"$MSG_E\" with title \"$TITLE_E\""
[ -n "$SUBTITLE_E" ] && script="$script subtitle \"$SUBTITLE_E\""
if [ -n "$SOUND" ] && [ "$SOUND" != "none" ]; then
  SOUND_E="$(esc "$SOUND")"
  script="$script sound name \"$SOUND_E\""
fi

# macOS — native Notification Center banner.
if command -v osascript >/dev/null 2>&1; then
  osascript -e "$script"
  exit 0
fi

# Windows (Git Bash / MSYS) — surface a real toast via PowerShell. Prefers the
# BurntToast module (persists in Action Center); falls back to a NotifyIcon
# balloon when the module is absent. Message/title are passed via env vars to
# avoid shell-quoting issues.
PS_BIN=""
command -v pwsh >/dev/null 2>&1 && PS_BIN="pwsh"
[ -z "$PS_BIN" ] && command -v powershell.exe >/dev/null 2>&1 && PS_BIN="powershell.exe"
if [ -n "$PS_BIN" ]; then
  GN_MSG="$MSG" GN_TITLE="$TITLE" GN_SUB="$SUBTITLE" GN_SOUND="$SOUND" \
  "$PS_BIN" -NoProfile -NonInteractive -Command '
    $msg=$env:GN_MSG; $title=$env:GN_TITLE; $sub=$env:GN_SUB; $sound=$env:GN_SOUND
    $body = if ($sub) { "$sub`n$msg" } else { $msg }
    try {
      Import-Module BurntToast -ErrorAction Stop
      if ($sound -eq "none") { New-BurntToastNotification -Text $title, $body -Silent | Out-Null }
      else { New-BurntToastNotification -Text $title, $body | Out-Null }
    } catch {
      Add-Type -AssemblyName System.Windows.Forms, System.Drawing
      $ni = New-Object System.Windows.Forms.NotifyIcon
      $ni.Icon = [System.Drawing.SystemIcons]::Information
      $ni.Visible = $true
      $ni.ShowBalloonTip(5000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
      Start-Sleep -Seconds 6
      $ni.Dispose()
    }
  ' 2>/dev/null || echo "goal-notify (powershell toast failed): $TITLE — $MSG" >&2
  exit 0
fi

# No osascript, no PowerShell — degrade gracefully so the skill still runs.
echo "goal-notify (no notifier, stderr fallback): $TITLE — $MSG" >&2
exit 0
