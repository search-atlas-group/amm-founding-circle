#!/usr/bin/env python3
"""connection_check.py — ground-truth liveness check for an unattended agent.

Silence is not success. This does NOT ask your agent "are you ok?" (a broken
agent will happily say yes). It runs the checks YOU listed in checks.json — each
one a plain command that exits 0 when the connection is healthy and non-zero when
it's down — and classifies each connection from that real result plus, for a
"run" check, whether its output actually MOVED since last time.

It prints one line per connection:  <name> <STATE> | <evidence>
and exits with the WORST state's code, so a shell loop can branch on $? with no
text parsing:

  0   ALL_OK       every connection healthy
  10  STALLED      a "run" check is alive but its output hasn't moved past the stall window
  20  NEEDS_INPUT  a check reported it's blocked waiting on you (exit code 20)
  40  DOWN         a connection failed its check (login expired, endpoint dead, process gone)
  50  UNKNOWN      a check could not be determined (fail-safe — re-check, don't assume)

Precedence (worst wins): NEEDS_INPUT(20) > DOWN(40) > STALLED(10) > UNKNOWN(50) > ALL_OK(0).
DOWN and NEEDS_INPUT are "you" states; STALLED/UNKNOWN are "watch again" states.

It writes a tiny status page each run (see status_page.py) and, when a
connection newly drops or newly needs you, fires a desktop notification. It
NEVER edits your files, pushes git, or sends anything external. It redacts
anything that looks like a secret before printing or writing.

Usage (the watch loop calls this for you; you also run it by hand once to test):
  python3 connection_check.py --config checks.json --status-page ./status.html
  python3 connection_check.py --config checks.json --quiet        # no desktop ping
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# STATE -> exit code. Higher-severity "you" states are surfaced first in precedence.
OK, STALLED, NEEDS_INPUT, DOWN, UNKNOWN = "ALL_OK", "STALLED", "NEEDS_INPUT", "DOWN", "UNKNOWN"
STATE_CODE = {OK: 0, STALLED: 10, NEEDS_INPUT: 20, DOWN: 40, UNKNOWN: 50}
# Worst-wins ordering when several connections have different states.
PRECEDENCE = [NEEDS_INPUT, DOWN, STALLED, UNKNOWN, OK]

SECRET_RE = re.compile(r"(?i)(token|api[_-]?key|password|secret|bearer|authorization)[=:\s]+\S+")


def redact(text: str, limit: int = 240) -> str:
    """Collapse whitespace and mask anything that smells like a credential."""
    cleaned = SECRET_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def state_dir() -> Path:
    """Where we remember the previous run's states + progress fingerprints."""
    base = Path(os.environ.get("CONNECTION_MONITOR_STATE", Path.home() / ".connection-monitor"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def run_check(command: str, cwd: Path, timeout: int) -> tuple[int, str]:
    """Run one member-supplied check command. Never raises; a crash is UNKNOWN."""
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    try:
        result = subprocess.run(
            command, cwd=str(cwd), shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, env=env, check=False,
        )
        return result.returncode, (result.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "check timed out"
    except Exception as exc:  # any OS-level failure is a can't-tell, not a crash
        return 125, f"could not run check: {exc}"


def progress_fingerprint(watch_path: Path) -> str:
    """Newest recent file mtime under a folder — real work moves files forward.

    A "run" check uses this to distinguish a live run (output changing) from a
    stalled one (alive but frozen). Capped so a huge tree can't stall the check.
    """
    if not watch_path.exists():
        return ""
    if watch_path.is_file():
        try:
            return str(int(watch_path.stat().st_mtime))
        except OSError:
            return ""
    newest = 0.0
    seen = 0
    for root, dirs, files in os.walk(watch_path):
        # skip churny/generated dirs so their noise doesn't fake "progress"
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}]
        for name in files:
            try:
                mtime = os.stat(os.path.join(root, name)).st_mtime
            except OSError:
                continue
            newest = max(newest, mtime)
            seen += 1
            if seen >= 5000:  # bounded: never crawl an unbounded tree
                return f"{int(newest)}:capped"
    return str(int(newest)) if newest else ""


def classify(check: dict, cwd: Path, prior: dict, now: float) -> tuple[str, str, dict]:
    """Classify one connection.

    Returns (STATE, evidence, memo) where memo carries what next run needs:
      memo["fp"]        content fingerprint (detects whether output MOVED)
      memo["moved_at"]  wall-clock epoch of the last time the fingerprint changed
    `prior` is the previous run's memo for this connection ({} on first sight).
    Keeping the fingerprint (identity) and moved_at (timing) as SEPARATE fields
    is deliberate: a file mtime is not a wall-clock now(), so conflating them
    made a steady run look like it was always "moving".
    """
    kind = check.get("kind", "login")  # "login" | "endpoint" | "process" | "run"
    command = check.get("command", "")
    timeout = int(check.get("timeout", 30))
    prev_fp = prior.get("fp", "")
    prev_moved = prior.get("moved_at")

    # A "run" check is special: it must be alive AND making progress.
    if kind == "run":
        watch = check.get("watch_path")
        stall_min = int(check.get("stall_minutes", 15))
        fp = progress_fingerprint(Path(watch).expanduser()) if watch else ""
        rc, out = (0, "") if not command else run_check(command, cwd, timeout)
        if command and rc == 20:
            return NEEDS_INPUT, redact(out) or "run is blocked waiting on you", {"fp": fp, "moved_at": prev_moved}
        if command and rc not in (0,):
            return DOWN, redact(out) or f"run check exited {rc}", {"fp": fp, "moved_at": prev_moved}
        if not watch:
            memo = {"fp": fp, "moved_at": prev_moved}
            return (OK, "run check passed", memo) if command else (UNKNOWN, "run check has no command or watch_path", memo)
        if not fp:
            return UNKNOWN, f"nothing found under {watch} yet", {"fp": fp, "moved_at": prev_moved}
        if prev_fp and fp == prev_fp:
            # Output has NOT moved since last check. Time the freeze from moved_at.
            moved_at = prev_moved if prev_moved is not None else now
            frozen = now - moved_at
            if frozen >= stall_min * 60:
                return STALLED, f"output under {watch} unchanged for {int(frozen // 60)}m (>= {stall_min}m)", {"fp": fp, "moved_at": moved_at}
            return OK, f"output steady; last moved {int(frozen // 60)}m ago", {"fp": fp, "moved_at": moved_at}
        # Fingerprint changed (or first sight): output moved now.
        return OK, "output moving", {"fp": fp, "moved_at": now}

    # login / endpoint / process checks: exit code is ground truth.
    if not command:
        return UNKNOWN, "no check command configured", prior
    rc, out = run_check(command, cwd, timeout)
    if rc == 0:
        return OK, redact(out) or "healthy", prior
    if rc == 20:
        return NEEDS_INPUT, redact(out) or "check reports it needs you", prior
    if rc in (124, 125):
        return UNKNOWN, redact(out) or "check could not be determined", prior
    return DOWN, redact(out) or f"check exited {rc}", prior


def worst(states: list[str]) -> str:
    for candidate in PRECEDENCE:
        if candidate in states:
            return candidate
    return OK


def notify(title: str, message: str, quiet: bool) -> None:
    """Best-effort desktop ping. Never fails the run if no notifier exists."""
    if quiet:
        return
    msg = redact(message, 180)
    try:
        if sys.platform == "darwin" and shutil.which("osascript"):
            script = f'display notification {json.dumps(msg)} with title {json.dumps(title)}'
            subprocess.run(["osascript", "-e", script], check=False, timeout=10)
        elif shutil.which("notify-send"):  # Linux
            subprocess.run(["notify-send", title, msg], check=False, timeout=10)
        elif sys.platform.startswith("win") and shutil.which("powershell"):
            ps = (
                "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null;"
                f"[System.Windows.Forms.MessageBox]::Show({json.dumps(msg)}, {json.dumps(title)})"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, timeout=10)
    except Exception:
        pass  # a missing notifier must never break the watch


def load_prev(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ground-truth liveness check for an unattended agent.")
    p.add_argument("--config", required=True, help="Path to checks.json (see checks.example.json).")
    p.add_argument("--status-page", default="./status.html", help="Where to write the local status page.")
    p.add_argument("--dir", default=".", help="Folder to run check commands in (default: current dir).")
    p.add_argument("--quiet", action="store_true", help="Do not fire desktop notifications (used during warm-up).")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 2
    try:
        checks = json.loads(config_path.read_text(encoding="utf-8")).get("checks", [])
    except Exception as exc:
        print(f"ERROR: could not read {config_path}: {redact(str(exc))}", file=sys.stderr)
        return 2

    cwd = Path(args.dir).expanduser().resolve()
    now = time.time()
    memory_path = state_dir() / (hashlib.sha1(str(config_path).encode()).hexdigest()[:12] + ".json")
    prev = load_prev(memory_path)
    prev_states = prev.get("states", {})
    prev_memos = prev.get("memos", {})

    rows: list[dict] = []
    states: list[str] = []
    new_memos: dict[str, dict] = {}

    for check in checks:
        name = check.get("name", "unnamed")
        state, evidence, memo = classify(check, cwd, prev_memos.get(name, {}), now)
        new_memos[name] = memo
        rows.append({"name": name, "state": state, "evidence": evidence})
        states.append(state)
        print(f"{name} {state} | {evidence}")

        # Change-driven notify: ping when a connection NEWLY drops or NEWLY needs you,
        # or NEWLY recovers. Same-state repeats stay quiet (the loop also gates this).
        was = prev_states.get(name)
        if state in (DOWN, NEEDS_INPUT) and was not in (DOWN, NEEDS_INPUT):
            notify("Agent connection down", f"{name}: {evidence}", args.quiet)
        elif state == OK and was in (DOWN, NEEDS_INPUT):
            notify("Agent connection back up", f"{name} recovered", args.quiet)

    overall = worst(states) if states else UNKNOWN

    # Persist for next run's change detection + honest stall timing.
    memory_path.write_text(
        json.dumps({
            "states": {r["name"]: r["state"] for r in rows},
            "memos": new_memos,
            "overall": overall,
            "checked_at": int(now),
        }, indent=2),
        encoding="utf-8",
    )

    # Render the status page (import lazily so the checker still works if it's absent).
    try:
        import status_page  # noqa: PLC0415 — optional, colocated
        status_page.render(Path(args.status_page).expanduser(), rows, overall)
    except Exception:
        # Fall back to a minimal inline page so the member always has something to glance at.
        _fallback_status_page(Path(args.status_page).expanduser(), rows, overall)

    return STATE_CODE.get(overall, 50)


def _fallback_status_page(path: Path, rows: list[dict], overall: str) -> None:
    color = {OK: "#137333", DOWN: "#a50e0e", NEEDS_INPUT: "#b06000",
             STALLED: "#b06000", UNKNOWN: "#5f6368"}
    body = "".join(
        f"<tr><td>{r['name']}</td><td style='color:{color.get(r['state'], '#5f6368')}'>"
        f"{r['state']}</td><td>{r['evidence']}</td></tr>" for r in rows
    )
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(
        "<!doctype html><meta charset='utf-8'>"
        f"<title>Connection status — {overall}</title>"
        "<style>body{font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;max-width:720px;"
        "margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;width:100%}"
        "td{padding:.4rem .6rem;border-bottom:1px solid #e0e0e0}</style>"
        f"<h1>Connection status: {overall}</h1><p>Last check {stamp}</p>"
        f"<table>{body}</table>",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
