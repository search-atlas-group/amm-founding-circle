#!/usr/bin/env python3
"""Auto-save Stop hook — snapshot the working repo when an agent run ends.

Wire this as a `Stop` hook in your agent runtime (Claude Code, Codex, etc.).
On every Stop event, if the folder the agent worked in is a git repo with
uncommitted changes, it makes a timestamped snapshot commit. That commit is
your rollback trail: an overnight run always leaves a step-by-step record you
can `git log` in the morning and revert any part of.

It is deliberately runtime-light: stdin is the hook payload, stdout is the hook
decision. It only reads the local payload and touches the local git repo. It
never sends anything to an external service, and it never pushes — a snapshot
is a *local* commit only. It fails open: if anything goes wrong, it lets the
agent continue rather than blocking it.

Env knobs:
  AGENT_AUTOSAVE=0            Disable auto-save entirely.
  AGENT_AUTOSAVE_PREFIX=...   Commit message prefix (default "auto-save").
  AGENT_AUTOSAVE_DIR=/path    Force the repo to snapshot (default: cwd of the
                              run, taken from the hook payload if present).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def emit(payload: dict[str, Any]) -> None:
    """Print a hook decision. `continue: True` = let the agent proceed."""
    print(json.dumps(payload, separators=(",", ":")))


def load_hook_input() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def event_name(payload: dict[str, Any]) -> str:
    # Different runtimes name the event field differently — accept them all.
    for key in ("hook_event_name", "hookEventName", "hookEvent", "event", "name"):
        val = payload.get(key)
        if val:
            return str(val)
    return ""


def working_dir(payload: dict[str, Any]) -> Path:
    forced = os.environ.get("AGENT_AUTOSAVE_DIR")
    if forced:
        return Path(forced).expanduser()
    # Runtimes pass the run's working directory under one of these keys.
    for key in ("cwd", "workingDirectory", "working_directory", "project_dir", "projectDir"):
        val = payload.get(key)
        if val:
            return Path(str(val)).expanduser()
    return Path.cwd()


def git(repo: Path, args: list[str], timeout: int = 20) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
        check=False,
    )


def is_git_repo(repo: Path) -> bool:
    try:
        result = git(repo, ["rev-parse", "--is-inside-work-tree"], timeout=8)
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def has_changes(repo: Path) -> bool:
    try:
        result = git(repo, ["status", "--porcelain"], timeout=10)
    except Exception:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def snapshot(repo: Path) -> str:
    """Stage everything and make one timestamped snapshot commit. Local only."""
    prefix = os.environ.get("AGENT_AUTOSAVE_PREFIX", "auto-save")
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"{prefix}: agent snapshot {stamp}"

    add = git(repo, ["add", "-A"], timeout=30)
    if add.returncode != 0:
        return f"stage failed: {add.stderr.strip()[:200]}"

    # Commit without touching hooks/signing so an unattended run never stalls
    # on a prompt or a failing pre-commit hook.
    commit = git(
        repo,
        ["-c", "commit.gpgsign=false", "commit", "--no-verify", "-m", message],
        timeout=30,
    )
    if commit.returncode != 0:
        return f"commit skipped: {commit.stderr.strip()[:200] or commit.stdout.strip()[:200]}"
    return f"snapshot committed: {message}"


def main() -> int:
    # Fail open on the master switch.
    if os.environ.get("AGENT_AUTOSAVE", "1") in {"0", "false", "False"}:
        emit({"continue": True})
        return 0

    payload = load_hook_input()

    # Only act on Stop-style events; ignore everything else, ignore subagents.
    event = event_name(payload).lower()
    if event and "stop" not in event:
        emit({"continue": True})
        return 0
    if payload.get("is_subagent") or payload.get("isSubagent") or event == "subagentstop":
        emit({"continue": True})
        return 0

    repo = working_dir(payload)
    try:
        if repo.exists() and is_git_repo(repo) and has_changes(repo):
            snapshot(repo)  # best-effort; result is not surfaced to the agent
    except Exception:
        # Never block the agent on an auto-save failure.
        pass

    emit({"continue": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
