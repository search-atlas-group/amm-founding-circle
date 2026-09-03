#!/usr/bin/env python3
"""SessionEnd hook (OPT-IN): drop a handoff stub so the notes folder fills itself.

Writes one dated stub per session into <notes>/memory/handoffs/ recording the session id,
the working directory, and the end reason. It records only metadata the runtime already
hands the hook — never transcript content, never file bodies.

The stub is a prompt to the next session, not a finished memo: open it, replace the
placeholder body with what actually happened, and delete it if the session was not worth
remembering. Empty stubs are cheap; a wrong memo is not.

Cross-platform: paths are built with pathlib and files are written as UTF-8 without a BOM.
Silent on every error. Installed only when install.py is run with --handoff-hook.

Notes folder, command line first, then environment:
  --brain-dir DIR / BRAIN_DIR   (default: ~/brain, or %USERPROFILE%\\brain on Windows)
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path


def notes_root(argv):
    for i, a in enumerate(argv):
        if a == "--brain-dir" and i + 1 < len(argv):
            return Path(argv[i + 1]).expanduser()
    env = os.environ.get("BRAIN_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / "brain"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        data = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    if not isinstance(data, dict):
        return 0

    outdir = notes_root(argv) / "memory" / "handoffs"
    try:
        outdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return 0

    now = datetime.datetime.now()
    sid = re.sub(r"[^A-Za-z0-9]", "", str(data.get("session_id") or "nosession"))[:8]
    cwd = data.get("cwd") or os.getcwd()
    project = re.sub(r"[^a-z0-9]+", "-", Path(cwd).name.lower()).strip("-") or "session"
    slug = "handoff-%s-%s-%s" % (project, now.strftime("%Y-%m-%d"), sid)
    path = outdir / (slug + ".md")
    if path.exists():
        return 0

    body = (
        "---\n"
        "name: %s\n"
        "description: DRAFT handoff stub for %s on %s. Replace this line with what the "
        "session actually decided, or delete the file.\n"
        "type: project\n"
        "date: %s\n"
        "---\n\n"
        "Session %s ended in `%s` (reason: %s).\n\n"
        "**Why:** <replace: what this session was for>\n"
        "**How to apply:** <replace: what the next session should pick up, or delete this "
        "file>\n"
    ) % (slug, project, now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"),
         sid, cwd, data.get("reason") or "unknown")

    try:
        path.write_text(body, encoding="utf-8", newline="\n")
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
