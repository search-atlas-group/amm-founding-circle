#!/usr/bin/env python3
"""Shared helpers for the kit's cross-platform installer, uninstaller and tests.

Standard library only, Python 3.9+. Every function reads ``os.name`` / ``os.environ`` at
call time and accepts explicit overrides, so the Windows branches can be exercised on any
platform by passing ``windows=True`` or a fake environment mapping.
"""
import os
import shutil
import shlex
import sys
from pathlib import Path

QMD_NAMES = ("qmd", "qmd.cmd", "qmd.exe", "qmd.bat")


def is_windows(windows=None):
    """True when we should emit Windows-shaped paths and commands."""
    if windows is not None:
        return bool(windows)
    return os.name == "nt" or sys.platform.startswith("win")


def home_dir(env=None, windows=None):
    """The user's home directory, honouring USERPROFILE on Windows."""
    env = os.environ if env is None else env
    if is_windows(windows):
        h = env.get("USERPROFILE") or env.get("HOME")
    else:
        h = env.get("HOME") or env.get("USERPROFILE")
    return Path(h) if h else Path.home()


def claude_config_dir(env=None, windows=None):
    """Where Claude Code keeps settings.json, hooks, skills and commands.

    ``CLAUDE_CONFIG_DIR`` wins if set. Otherwise ``%USERPROFILE%\\.claude`` on Windows and
    ``~/.claude`` everywhere else.
    """
    env = os.environ if env is None else env
    override = env.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return home_dir(env, windows) / ".claude"


def default_notes_dir(env=None, windows=None):
    env = os.environ if env is None else env
    d = env.get("BRAIN_DIR")
    if d:
        return Path(d).expanduser()
    return home_dir(env, windows) / "brain"


def find_qmd(env=None, windows=None):
    """Absolute path to the qmd executable, or None. Finds qmd.cmd on Windows."""
    env = os.environ if env is None else env
    path = env.get("PATH")
    names = QMD_NAMES if is_windows(windows) else ("qmd",)
    for name in names:
        found = shutil.which(name, path=path)
        if found:
            return found
    return None


def find_npm(env=None, windows=None):
    env = os.environ if env is None else env
    path = env.get("PATH")
    names = ("npm", "npm.cmd", "npm.exe") if is_windows(windows) else ("npm",)
    for name in names:
        found = shutil.which(name, path=path)
        if found:
            return found
    return None


def quote(arg, windows=None):
    """Quote one argument for a settings.json hook command string."""
    arg = str(arg)
    if is_windows(windows):
        if arg and not any(c in arg for c in ' \t"'):
            return arg
        return '"%s"' % arg.replace('"', '\\"')
    return shlex.quote(arg)


def hook_command(script, args=(), python=None, windows=None):
    """Build the command string written into settings.json.

    Always absolute: the interpreter that ran the installer plus the absolute hook path,
    each quoted. No shell, no ``env VAR=value`` prefix, so the same shape works under
    cmd.exe and under a POSIX shell.
    """
    python = python or sys.executable
    parts = [quote(python, windows), quote(str(script), windows)]
    parts += [quote(a, windows) for a in args]
    return " ".join(parts)


def npm_install_hint(windows=None):
    if is_windows(windows):
        return (
            "  qmd was not found on your PATH.\n"
            "  Install Node.js from https://nodejs.org (the LTS installer), then open a NEW\n"
            "  PowerShell or Command Prompt window and run:\n\n"
            "      npm i -g qmd\n\n"
            "  Then run install.bat again."
        )
    return (
        "  qmd was not found on your PATH.\n"
        "  Install Node.js from https://nodejs.org (or `brew install node` on macOS), then run:\n\n"
        "      npm i -g qmd\n\n"
        "  Then run ./install.sh again."
    )


def say(msg=""):
    print("  %s" % msg if msg else "")


def step(msg):
    print("\n== %s" % msg)
