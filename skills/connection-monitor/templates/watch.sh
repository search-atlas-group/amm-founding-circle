#!/usr/bin/env bash
# watch.sh — the persistent watch loop for your always-on agent.
#
# Arms a quiet-until-it-matters monitor over the connections listed in your
# checks.json. It calls connection_check.py on an ADAPTIVE cadence (5 min at
# first, easing to 10, never more than 15 minutes between checks so a break
# can't hide for long), emits ONLY on a real change, and escalates in BOUNDED
# steps so it never floods you and never watches a dead thing forever.
#
# It reads the checker's EXIT CODE (not its text) to decide what to do:
#   0  ALL_OK       every connection healthy      -> stay quiet
#   10 STALLED      a run is frozen               -> attention (bounded)
#   20 NEEDS_INPUT  a check is blocked on you      -> attention (you)
#   40 DOWN         a connection dropped           -> attention (you)
#   50 UNKNOWN      couldn't tell                  -> re-check; only escalate if it PERSISTS
#
# UNKNOWN is a transient fail-safe: one is noise, three in a row (~15 min) is real.
#
# It NEVER edits files, pushes git, or sends anything external. The only thing it
# does on a drop is (optionally) run your ONE recovery command once, then notify.
#
# Usage:
#   bash watch.sh --config checks.json --status-page ./status.html
#   bash watch.sh --config checks.json --recover "your-relogin-command"   # optional single nudge
#
# Stop it with Ctrl-C, or hand it to host-your-agent to keep it alive off your laptop.

# --- retry-loop-safety --------------------------------------------------------
# This loop is intentionally bounded and non-storming:
#   * cadence floor 300s / ceiling 900s (never a hot spin, never a hidden gap);
#   * change-only emission (no per-tick spam);
#   * a DOWN/NEEDS_INPUT failure is announced ONCE and then goes quiet until it
#     changes (no re-ping flood);
#   * the recovery nudge fires AT MOST ONCE per distinct failure episode;
#   * UNKNOWN escalates only after 3 consecutive (~15 min).
# Do NOT wrap this in an outer auto-retry — that would defeat the bounds above.
# -----------------------------------------------------------------------------

set -u

CONFIG=""
STATUS_PAGE="./status.html"
RECOVER=""
CHECK_DIR="."

while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)       CONFIG="$2"; shift 2 ;;
    --status-page)  STATUS_PAGE="$2"; shift 2 ;;
    --recover)      RECOVER="$2"; shift 2 ;;
    --dir)          CHECK_DIR="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$CONFIG" ]; then
  echo "ERROR: --config checks.json is required" >&2
  exit 2
fi
if [ ! -f "$CONFIG" ]; then
  echo "ERROR: config not found: $CONFIG" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHECKER="$SCRIPT_DIR/connection_check.py"
if [ ! -f "$CHECKER" ]; then
  echo "ERROR: connection_check.py not found next to watch.sh" >&2
  exit 2
fi

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "ERROR: python3 not found on PATH" >&2
  exit 2
fi

# One check pass. Prints the checker's lines; returns its exit code.
poll() {
  "$PY" "$CHECKER" --config "$CONFIG" --status-page "$STATUS_PAGE" --dir "$CHECK_DIR"
  return $?
}

state_word() {
  case "$1" in
    0)  echo "ALL_OK" ;;
    10) echo "STALLED" ;;
    20) echo "NEEDS_INPUT" ;;
    40) echo "DOWN" ;;
    50) echo "UNKNOWN" ;;
    *)  echo "UNKNOWN" ;;
  esac
}

now() { date +%H:%M; }

# Baseline. One startup line, then change-only.
out="$(poll)"; rc=$?
prev_rc=$rc
prev_word="$(state_word "$rc")"
echo "[start $(now)] overall=$prev_word (rc=$rc)"
echo "$out" | sed 's/^/    /'

unknown_streak=0
recovered_nudge_for=""   # tracks the failure episode we've already nudged, so we nudge only ONCE

i=0
while true; do
  # Adaptive cadence: 5 min for the first ~6 checks, then 10 min; ceiling 15.
  if [ "$i" -lt 6 ]; then
    sleep 300
  else
    sleep 600
  fi
  i=$((i + 1))

  out="$(poll)"; rc=$?
  word="$(state_word "$rc")"

  # Track consecutive UNKNOWN so a lone one stays noise but a persistent one escalates.
  if [ "$rc" -eq 50 ]; then
    unknown_streak=$((unknown_streak + 1))
  else
    unknown_streak=0
  fi

  # Clear the one-shot nudge memory once we're healthy again, so the NEXT
  # distinct failure episode is allowed exactly one nudge of its own.
  if [ "$rc" -eq 0 ]; then
    recovered_nudge_for=""
  fi

  # Change-only: if nothing changed AND we're not sitting on a persistent UNKNOWN, stay quiet.
  if [ "$word" = "$prev_word" ] && [ "$unknown_streak" -lt 3 ]; then
    prev_rc=$rc; prev_word=$word
    continue
  fi

  case "$rc" in
    40|20)  # DOWN or NEEDS_INPUT — a real "you" state.
      echo "[ATTENTION $(now)] overall=$word (rc=$rc)"
      echo "$out" | sed 's/^/    /'
      # Bounded escalation: try the ONE recovery nudge, but only once per episode.
      if [ -n "$RECOVER" ] && [ "$recovered_nudge_for" != "$word" ]; then
        echo "[nudge $(now)] running recovery once: (command hidden)"
        # shellcheck disable=SC2086
        ( eval "$RECOVER" ) >/dev/null 2>&1 || true
        recovered_nudge_for="$word"
      fi
      ;;
    10)  # STALLED — attention, but a run-progress state, not necessarily you.
      echo "[STALLED $(now)] overall=$word (rc=$rc)"
      echo "$out" | sed 's/^/    /'
      ;;
    50)  # UNKNOWN — only shout if it has persisted.
      if [ "$unknown_streak" -ge 3 ]; then
        echo "[ATTENTION $(now)] persistent UNKNOWN x$unknown_streak — can't verify liveness"
        echo "$out" | sed 's/^/    /'
      else
        echo "[change $(now)] overall=$word (transient; streak=$unknown_streak)"
      fi
      ;;
    0)   # Recovered / all healthy.
      echo "[recovered $(now)] overall=ALL_OK — connections back to healthy"
      ;;
    *)
      echo "[change $(now)] overall=$word (rc=$rc)"
      ;;
  esac

  prev_rc=$rc
  prev_word=$word
done
