#!/usr/bin/env python3
# Stop hook. Nudge JD to write a memory file if session has been active but no
# _brain/memory/ file has been touched recently. Cooldown prevents nag fatigue.

import json, os, sys, time
from pathlib import Path

COOLDOWN_FILE = Path('/tmp/jd-memory-reminder-last')
COOLDOWN_S = 2 * 3600           # at most one reminder every 2h
STALE_THRESHOLD_S = 90 * 60     # memory considered stale after 90min of no edits
MEMORY_DIR = Path(os.environ.get("HARNESS_BRAIN") or "/Users/eillacs/Desktop/Agentic/_brain") / "memory"

try:
    # Cooldown check
    if COOLDOWN_FILE.exists() and time.time() - COOLDOWN_FILE.stat().st_mtime < COOLDOWN_S:
        sys.exit(0)

    if not MEMORY_DIR.is_dir():
        sys.exit(0)

    latest_mtime = max((f.stat().st_mtime for f in MEMORY_DIR.glob('*.md')), default=0)
    if time.time() - latest_mtime < STALE_THRESHOLD_S:
        sys.exit(0)  # memory was just touched — no nudge

    COOLDOWN_FILE.touch()
    print(json.dumps({
        'systemMessage': (
            'Memory-update reminder: no _brain/memory/ file touched in ~90min. '
            'If anything new was learned this session (user pref, project decision, '
            'surprising fact), capture it as a memo per CLAUDE.md auto-memory rules. '
            'Next reminder in 2h.'
        )
    }))
except Exception:
    pass

sys.exit(0)
