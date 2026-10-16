#!/usr/bin/env python3
"""PreToolUse Bash guard: no destructive git op on a dirty repo under ~/Desktop/Agentic.

WHY THIS EXISTS
---------------
On 2026-09-03 a `git filter-repo` run inside `_brain` destroyed roughly half a day of
uncommitted work. The whole response was a memory file — `feedback-commit-before-
history-rewrite.md` — and nothing mechanical. The 2026-09-04 red-team re-audit (S2-7)
found `_brain` sitting on 108 dirty tracked files with no auto-commit (`brain-sync` was
disabled 2026-09-02 by design), no snapshot in the rewrite path, and no PreToolUse
matcher anywhere on `filter-repo`, `reset --hard`, `checkout --`, `clean` or `stash`.
Its verdict: of everything in the report, fix this one first. This is that fix.

WHAT IT BLOCKS
--------------
A command that can discard uncommitted work — `git filter-repo`, `git reset --hard`,
`git checkout -- <path>` / `git restore` without `--staged`, `git clean -f/-d/-x`,
`git stash` (push/save, including the bare form) — when the repo it would run in is
BOTH under ~/Desktop/Agentic AND currently dirty by `git status --porcelain`.

A clean repo is never blocked: there is nothing to lose. A dirty repo is blocked until
the work is committed, which for a local-only repo like `_brain` is a one-line snapshot
commit and costs nothing. `_brain`'s nightly hygiene run now takes that snapshot itself,
so the steady state is clean.

The escape hatch is deliberate and narrow: set JD_ALLOW_HISTORY_REWRITE=1 in the
environment for the single call. It is not a config flag and does not persist.

Contract: exit 0 allows, exit 2 blocks with the reason on stderr. Never raises — a
guard that crashes on an unexpected payload must not wedge the session, so every
unexpected shape falls through to allow.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

GUARDED_ROOT = Path.home() / "Desktop" / "Agentic"

# Each entry: (label, compiled pattern). Patterns run against the normalised command.
DESTRUCTIVE = [
    ("git filter-repo", re.compile(r"\bgit\b[^;&|]*\bfilter-repo\b")),
    ("git filter-branch", re.compile(r"\bgit\b[^;&|]*\bfilter-branch\b")),
    ("git reset --hard", re.compile(r"\bgit\b[^;&|]*\breset\b[^;&|]*--hard\b")),
    ("git checkout -- <path>", re.compile(r"\bgit\b[^;&|]*\bcheckout\b[^;&|]*\s--\s")),
    ("git checkout .", re.compile(r"\bgit\b[^;&|]*\bcheckout\b\s+\.(\s|$)")),
    ("git restore", re.compile(r"\bgit\b[^;&|]*\brestore\b(?![^;&|]*--staged)")),
    ("git clean", re.compile(r"\bgit\b[^;&|]*\bclean\b[^;&|]*-\w*[fdx]")),
    ("git stash", re.compile(r"\bgit\b[^;&|]*\bstash\b(?![^;&|]*\b(list|show|apply|pop)\b)")),
]

# `git -C <dir>` decides which repo the command actually lands in. Without this the
# guard would check the session's cwd while the command rewrote a different repo —
# exactly how the original incident was launched, from the mothership root.
DASH_C_RE = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*-C\s+(\S+)")


def _target_dirs(cmd: str, cwd: Path) -> list[Path]:
    """Every directory this command could operate on: each `-C` target, else cwd."""
    dirs: list[Path] = []
    for m in DASH_C_RE.finditer(cmd):
        raw = m.group(1).strip("'\"")
        raw = os.path.expandvars(os.path.expanduser(raw))
        p = Path(raw)
        dirs.append(p if p.is_absolute() else (cwd / p))
    return dirs or [cwd]


def _repo_root(d: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return Path(out.stdout.strip() or ".")


def _dirty(repo: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def _under_guarded_root(p: Path) -> bool:
    try:
        p.resolve().relative_to(GUARDED_ROOT.resolve())
        return True
    except Exception:
        return False


def main() -> int:
    if os.environ.get("JD_ALLOW_HISTORY_REWRITE") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    # Valid JSON that is not an object is still an unexpected shape. Falling through
    # to allow is the only safe answer: a guard that raises here wedges every Bash
    # call in the session, which is a far worse outage than the one it prevents.
    if not isinstance(data, dict):
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = ((data.get("tool_input") or {}).get("command") or "").strip()
    if not cmd or "git" not in cmd:
        return 0

    hits = [label for label, pat in DESTRUCTIVE if pat.search(cmd)]
    if not hits:
        return 0

    cwd = Path(data.get("cwd") or os.getcwd())
    for d in _target_dirs(cmd, cwd):
        repo = _repo_root(d)
        if repo is None or not _under_guarded_root(repo):
            continue
        dirty = _dirty(repo)
        if not dirty:
            continue
        shown = "\n".join("    " + ln for ln in dirty[:10])
        more = f"\n    … and {len(dirty) - 10} more" if len(dirty) > 10 else ""
        print(
            f"BLOCKED: {hits[0]} on a DIRTY repo — {repo}\n"
            f"  {len(dirty)} uncommitted change(s) would be unrecoverable:\n"
            f"{shown}{more}\n"
            f"  On 2026-09-03 this exact shape ate half a day of work in _brain.\n"
            f"  Commit a snapshot first, then re-run:\n"
            f"    git -C {shlex.quote(str(repo))} add -A && "
            f"git -C {shlex.quote(str(repo))} commit -m 'snapshot before history rewrite'\n"
            f"  A clean repo is never blocked. To override for one call only:\n"
            f"    JD_ALLOW_HISTORY_REWRITE=1 <command>",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
