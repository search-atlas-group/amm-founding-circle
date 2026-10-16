#!/usr/bin/env bash
# Nova's daily diagnostic. The two-hour repo sync stays as it is; this is the
# once-a-day read: the ladder, what is in the way, and how they work.
#
# It prints locally. It uploads only the ladder scan, and only when this
# machine is already connected to the portal. Session text is never read and
# never sent.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/amm-founding-circle"
mkdir -p "$CACHE" 2>/dev/null || true
LOG="$CACHE/nova-daily.log"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') nova daily ==="
  "$PY" "$HERE/nova_insight.py" || echo "insight failed"
  echo
  "$PY" "$HERE/nova_practice.py" || echo "practice failed"
  echo
  "$PY" "$HERE/nova_insight.py" --flag || echo "flag failed"
} >>"$LOG" 2>&1

echo "Nova's daily read is in $LOG"
