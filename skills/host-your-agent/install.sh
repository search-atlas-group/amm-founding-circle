#!/usr/bin/env bash
# ============================================================================
#  host-your-agent — installer
#
#  Two jobs, run either or both:
#    bash install.sh --hook
#        Wire the auto-save Stop hook into your agent runtime(s) so every
#        unattended run leaves a git snapshot (a rollback trail).
#
#    bash install.sh --schedule --job ./my-job.sh --at 01:00 [--minutes 45]
#        Schedule the overnight runner. Detects your OS and uses the right
#        scheduler: launchd (Mac), Task Scheduler (Windows), or cron (Linux).
#
#  Nothing runs the moment you install. It runs at the time you set.
#  Check / pause / remove instructions print at the end of each install.
# ============================================================================

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES="$HERE/templates"
RUNNER="$TEMPLATES/overnight_runner.py"
HOOK_SRC="$TEMPLATES/autosave_hook.py"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

GREEN='\033[0;32m'; DIM='\033[2m'; YELLOW='\033[0;33m'; NC='\033[0m'

DO_HOOK=0
DO_SCHEDULE=0
JOB=""
AT="01:00"
MINUTES=45

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hook)      DO_HOOK=1; shift ;;
    --schedule)  DO_SCHEDULE=1; shift ;;
    --job)       JOB="${2:-}"; shift 2 ;;
    --at)        AT="${2:-}"; shift 2 ;;
    --minutes)   MINUTES="${2:-}"; shift 2 ;;
    -h|--help)   usage 0 ;;
    *) echo "unknown flag: $1" >&2; usage 2 ;;
  esac
done

[[ -n "$PYTHON_BIN" ]] || { echo "ERROR: python3 not found. Install Python 3 first." >&2; exit 1; }
if [[ $DO_HOOK -eq 0 && $DO_SCHEDULE -eq 0 ]]; then usage 0; fi

detect_os() {
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Darwin) echo "mac" ;;
    Linux)  echo "linux" ;;
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
    *) echo "unknown" ;;
  esac
}
OS="$(detect_os)"

# ---------------------------------------------------------------------------
# --hook : install the auto-save Stop hook into Claude Code + Codex configs
# ---------------------------------------------------------------------------
install_hook() {
  echo ""
  echo "  Installing the auto-save hook"

  local claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  local codex_dir="${CODEX_HOME:-$HOME/.codex}"
  local installed=0

  for pair in "claude:$claude_dir/settings.json" "codex:$codex_dir/hooks.json"; do
    local runtime="${pair%%:*}"
    local config="${pair#*:}"
    local cfg_dir; cfg_dir="$(dirname "$config")"
    # Only patch runtimes the member actually has (their config dir exists).
    if [[ ! -d "$cfg_dir" ]]; then
      echo -e "  ${DIM}skip $runtime (no config dir at $cfg_dir)${NC}"
      continue
    fi
    local hook_dir="$cfg_dir/hooks"
    local hook_dst="$hook_dir/autosave_hook.py"
    mkdir -p "$hook_dir"
    cp "$HOOK_SRC" "$hook_dst"
    chmod 755 "$hook_dst"

    "$PYTHON_BIN" - "$config" "$hook_dst" "$PYTHON_BIN" <<'PY'
import json, shlex, sys
from pathlib import Path

config, hook_path, python_bin = sys.argv[1:4]
p = Path(config).expanduser()
data = {}
if p.exists() and p.read_text().strip():
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERROR: invalid JSON in {p}: {e}")
if not isinstance(data, dict):
    raise SystemExit(f"ERROR: top-level of {p} is not an object")

hooks = data.setdefault("hooks", {})
groups = hooks.setdefault("Stop", [])
if not isinstance(groups, list):
    raise SystemExit("ERROR: hooks.Stop must be a list")

# Idempotent: drop any prior autosave hook before re-adding.
cleaned = []
for g in groups:
    if isinstance(g, dict) and isinstance(g.get("hooks"), list):
        kept = [h for h in g["hooks"] if "autosave_hook.py" not in str(h.get("command", ""))]
        if kept:
            g = dict(g); g["hooks"] = kept; cleaned.append(g)
    else:
        cleaned.append(g)

cmd = " ".join([shlex.quote(python_bin), shlex.quote(hook_path)])
cleaned.append({"hooks": [{"type": "command", "command": cmd, "timeout": 30}]})
hooks["Stop"] = cleaned
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, indent=2) + "\n")
print(f"  patched {p}")
PY
    echo -e "  ${GREEN}✓${NC} $runtime auto-save hook wired"
    installed=1
  done

  if [[ $installed -eq 0 ]]; then
    echo -e "  ${YELLOW}No supported runtime config found${NC} (~/.claude or ~/.codex)."
    echo "  Set CLAUDE_CONFIG_DIR or CODEX_HOME and re-run, or add the hook by hand:"
    echo "    Stop hook command → $PYTHON_BIN <config>/hooks/autosave_hook.py"
  else
    echo ""
    echo -e "  ${DIM}Test it: run your agent on any git repo, let it finish,${NC}"
    echo -e "  ${DIM}then 'git log --oneline' — you'll see an 'auto-save:' commit.${NC}"
    echo -e "  ${DIM}Disable per-run with AGENT_AUTOSAVE=0.${NC}"
  fi
}

# ---------------------------------------------------------------------------
# --schedule : wire the overnight runner into the OS scheduler
# ---------------------------------------------------------------------------
require_job() {
  [[ -n "$JOB" ]] || { echo "ERROR: --schedule needs --job ./my-job.sh" >&2; exit 2; }
  JOB="$(cd "$(dirname "$JOB")" && pwd)/$(basename "$JOB")"
  [[ -f "$JOB" ]] || { echo "ERROR: job file not found: $JOB" >&2; exit 2; }
  chmod +x "$RUNNER" 2>/dev/null || true
}

hour_min() {  # "01:00" -> sets HOUR / MINUTE (strips leading zeros for launchd ints)
  HOUR="${AT%%:*}"; MINUTE="${AT##*:}"
  HOUR="$((10#$HOUR))"; MINUTE="$((10#$MINUTE))"
}

schedule_mac() {
  local label="com.youragent.overnight"
  local plist="$HOME/Library/LaunchAgents/$label.plist"
  local log_dir="$HOME/Library/Logs/youragent-overnight"
  local caff=$(( (MINUTES + 5) * 60 ))
  mkdir -p "$HOME/Library/LaunchAgents" "$log_dir"
  hour_min

  "$PYTHON_BIN" - "$TEMPLATES/com.youragent.overnight.plist.template" "$plist" \
      "$RUNNER" "$JOB" "$(dirname "$JOB")" "$HOME" "$HOUR" "$MINUTE" "$MINUTES" "$caff" <<'PY'
import sys
from pathlib import Path
tpl, out, runner, job, workdir, home, hour, minute, minutes, caff = sys.argv[1:11]
t = Path(tpl).read_text()
for k, v in {
    "__RUNNER__": runner, "__JOB__": job, "__WORKDIR__": workdir, "__HOME__": home,
    "__HOUR__": hour, "__MINUTE__": minute, "__MINUTES__": minutes, "__CAFFEINATE_SECONDS__": caff,
}.items():
    t = t.replace(k, v)
Path(out).write_text(t)
PY

  plutil -lint "$plist" >/dev/null
  launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$plist"
  launchctl enable "gui/$(id -u)/$label"

  echo -e "  ${GREEN}✓${NC} launchd agent installed: $plist"
  echo -e "  ${DIM}Runs daily at $AT for up to ${MINUTES}m (Mac stays awake via caffeinate).${NC}"
  echo ""
  echo "  Check:    launchctl print gui/$(id -u)/$label | head -20"
  echo "  Run now:  launchctl kickstart -k gui/$(id -u)/$label"
  echo "  Pause:    launchctl bootout gui/$(id -u) '$plist'"
  echo "  Logs:     $log_dir/"
}

schedule_windows() {
  local ps1="$TEMPLATES/register-task-windows.ps1"
  echo "  Registering a Windows Scheduled Task via PowerShell..."
  powershell.exe -ExecutionPolicy Bypass -File "$ps1" \
    -Runner "$RUNNER" -Job "$JOB" -At "$AT" -Minutes "$MINUTES"
}

schedule_cron() {
  local log_dir="$HOME/.local/state/youragent-overnight"
  mkdir -p "$log_dir"
  hour_min
  local line="$MINUTE $HOUR * * * /usr/bin/env python3 $RUNNER --job $JOB --minutes $MINUTES >> \"$log_dir/cron.log\" 2>&1"
  # Idempotent: drop any prior line for this runner before adding.
  ( crontab -l 2>/dev/null | grep -vF "$RUNNER" ; echo "$line" ) | crontab -
  echo -e "  ${GREEN}✓${NC} cron entry installed (runs daily at $AT):"
  echo "    $line"
  echo ""
  echo -e "  ${YELLOW}Note:${NC} cron does NOT wake a sleeping machine — use this only on an"
  echo "  always-on box. On a laptop that sleeps, use a Mac or Windows instead."
  echo "  Check:   crontab -l | grep overnight_runner"
  echo "  Run now: python3 $RUNNER --job $JOB --minutes $MINUTES"
  echo "  Remove:  crontab -l | grep -vF '$RUNNER' | crontab -"
}

install_schedule() {
  require_job
  echo ""
  echo "  Scheduling the overnight runner ($OS)"
  case "$OS" in
    mac)     schedule_mac ;;
    windows) schedule_windows ;;
    linux)   schedule_cron ;;
    *)       echo -e "  ${YELLOW}Unknown OS — falling back to cron.${NC}"; schedule_cron ;;
  esac
}

# ---------------------------------------------------------------------------
[[ $DO_HOOK -eq 1 ]] && install_hook
[[ $DO_SCHEDULE -eq 1 ]] && install_schedule

echo ""
echo -e "  ${GREEN}Done.${NC}"
echo -e "  ${DIM}Your agent is off your laptop. Read reports/overnight/<date>/index.html over coffee.${NC}"
echo ""
