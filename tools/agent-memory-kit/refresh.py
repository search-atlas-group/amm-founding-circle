#!/usr/bin/env python3
"""Re-index the notes folder so new memos become searchable.

install.py copies this file to <config dir>/hooks/refresh-brain.py with your notes folder
and collection name baked in as the defaults. Safe to run from cron, launchd, Task
Scheduler, or by hand. Prints exactly one status line and exits non-zero on failure.

Overrides, command line first, then environment:
  --brain-dir DIR  / BRAIN_DIR
  --collection NAM / BRAIN_COLLECTION
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_NOTES_DIR = r"@@BRAIN_DIR@@"
DEFAULT_COLLECTION = "@@COLLECTION@@"
QMD_NAMES = ("qmd", "qmd.cmd", "qmd.exe", "qmd.bat")


def opt(argv, flag, env_name, default):
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return os.environ.get(env_name) or default


def find_qmd():
    for name in QMD_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for fallback in ("/opt/homebrew/bin/qmd", "/usr/local/bin/qmd"):
        if os.access(fallback, os.X_OK):
            return fallback
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    brain_dir = Path(opt(argv, "--brain-dir", "BRAIN_DIR", DEFAULT_NOTES_DIR)).expanduser()
    collection = opt(argv, "--collection", "BRAIN_COLLECTION", DEFAULT_COLLECTION)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    qmd = find_qmd()
    if not qmd:
        print("FAIL refresh-brain %s — qmd not found on PATH" % stamp)
        return 1
    if not brain_dir.is_dir():
        print("FAIL refresh-brain %s — notes folder missing: %s" % (stamp, brain_dir))
        return 1
    try:
        r = subprocess.run([qmd, "update"], capture_output=True, text=True, timeout=1800)
    except Exception as e:  # noqa: BLE001
        print("FAIL refresh-brain %s — could not run qmd: %s" % (stamp, e))
        return 1
    if r.returncode != 0:
        print("FAIL refresh-brain %s — qmd update exited %d" % (stamp, r.returncode))
        return 1
    print("OK refresh-brain %s collection=%s" % (stamp, collection))
    return 0


if __name__ == "__main__":
    sys.exit(main())
