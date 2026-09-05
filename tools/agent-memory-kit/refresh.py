#!/usr/bin/env python3
"""Re-index the notes folder so new memos become searchable.

install.py copies this file to <config dir>/hooks/refresh-brain.py with your notes folder
and collection name baked in as the defaults. Safe to run from cron, launchd, Task
Scheduler, or by hand. Prints exactly one status line and exits non-zero on failure.

Overrides, command line first, then environment:
  --brain-dir DIR  / BRAIN_DIR
  --collection NAM / BRAIN_COLLECTION
  --qmd PATH       / BRAIN_QMD
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_NOTES_DIR = r"@@BRAIN_DIR@@"
DEFAULT_COLLECTION = "@@COLLECTION@@"
DEFAULT_QMD = r"@@QMD@@"
QMD_NAMES = ("qmd", "qmd.cmd", "qmd.exe", "qmd.bat")


def opt(argv, flag, env_name, default):
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return os.environ.get(env_name) or default


def find_qmd(preferred=None):
    """Installer-resolved absolute path first, then PATH, then the usual locations."""
    if preferred and not preferred.startswith("@@") and os.access(preferred, os.X_OK):
        return preferred
    for name in QMD_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for fallback in ("/opt/homebrew/bin/qmd", "/usr/local/bin/qmd"):
        if os.access(fallback, os.X_OK):
            return fallback
    return None


def qmd_env(qmd):
    """qmd is a Node script — put its own bin dir on PATH so its shebang finds node."""
    env = dict(os.environ)
    bindir = os.path.dirname(os.path.abspath(qmd))
    if bindir:
        env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    return env


def update_supports_collection(qmd):
    """True when this qmd's own help documents a collection flag for `update`.

    qmd 2.x re-indexes every collection on the machine and ignores `-c` on `update`, so
    passing it blindly would read as scoped while doing the opposite. Ask the binary.
    """
    try:
        r = subprocess.run([qmd, "--help"], capture_output=True, text=True, timeout=15,
                           env=qmd_env(qmd))
    except Exception:  # noqa: BLE001
        return False
    for line in (r.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("qmd update") and ("-c " in stripped or "--collection" in stripped):
            return True
    return False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    brain_dir = Path(opt(argv, "--brain-dir", "BRAIN_DIR", DEFAULT_NOTES_DIR)).expanduser()
    collection = opt(argv, "--collection", "BRAIN_COLLECTION", DEFAULT_COLLECTION)
    stamp = time.strftime("%Y-%m-%d %H:%M")

    qmd = find_qmd(opt(argv, "--qmd", "BRAIN_QMD", DEFAULT_QMD))
    if not qmd:
        print("FAIL refresh-brain %s — qmd not found on PATH" % stamp)
        return 1
    if not brain_dir.is_dir():
        print("FAIL refresh-brain %s — notes folder missing: %s" % (stamp, brain_dir))
        return 1
    cmd = [qmd, "update"]
    scoped = update_supports_collection(qmd)
    if scoped:
        cmd += ["-c", collection]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                           env=qmd_env(qmd))
    except Exception as e:  # noqa: BLE001
        print("FAIL refresh-brain %s — could not run qmd: %s" % (stamp, e))
        return 1
    if r.returncode != 0:
        print("FAIL refresh-brain %s — qmd update exited %d" % (stamp, r.returncode))
        return 1
    print("OK refresh-brain %s collection=%s scope=%s"
          % (stamp, collection, "collection" if scoped else "all-collections"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
