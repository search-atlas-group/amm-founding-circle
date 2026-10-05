#!/usr/bin/env python3
"""Run Shep's read-only deterministic TUI and real-PTY QA gate."""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTY_STARTUP_NEEDLES = (
    b"SHEP",
    b"COMMANDER",
    b"Codex atlas-build",
    b"[click] select",
)
PTY_INPUTS = (
    ("click second demo row", b"\x1b[M #'", b"selected Claude review-gate"),
    ("keyboard down", b"j", b"No progress signal received."),
    ("keyboard up", b"k", b"Waiting for operator approval."),
    ("fixture refresh", b"r", b"refresh requested"),
    ("clean quit", b"q", None),
)
PTY_SGR_CLICK = b"\x1b[<0;3;7M"
PTY_READ_ONLY_INPUTS = frozenset(
    {b"\x1b[M #'", PTY_SGR_CLICK, b"j", b"k", b"r", b"q"}
)


class QaFailure(RuntimeError):
    """One self-QA stage failed."""


def pty_inputs_for_output(output: bytes) -> tuple[tuple[str, bytes, bytes | None], ...]:
    """Use the mouse encoding that curses enabled for this PTY.

    Linux ncurses advertises SGR mode (1006), while the macOS terminal stack
    used by local QA enables only the older X10 protocol. Sending the wrong
    form makes curses return the leading Escape as a quit key.
    """

    if b"\x1b[?1006" not in output:
        return PTY_INPUTS
    label, _x10_payload, needle = PTY_INPUTS[0]
    return ((label, PTY_SGR_CLICK, needle), *PTY_INPUTS[1:])


def run_checked(label: str, argv: list[str]) -> None:
    print(f"==> {label}", flush=True)
    result = subprocess.run(argv, cwd=ROOT, check=False)
    if result.returncode:
        raise QaFailure(f"{label} failed with exit code {result.returncode}")


def _read_pty(master_fd: int, output: bytearray, wait: float) -> bool:
    """Read available PTY bytes; return False after the slave closes."""

    ready, _, _ = select.select([master_fd], [], [], wait)
    if not ready:
        return True
    try:
        chunk = os.read(master_fd, 65536)
    except OSError as exc:
        if exc.errno == errno.EIO:
            return False
        raise
    if not chunk:
        return False
    output.extend(chunk)
    return True


def _await_output(
    master_fd: int,
    output: bytearray,
    needle: bytes,
    deadline: float,
    start: int = 0,
) -> None:
    while needle not in output[start:] and time.monotonic() < deadline:
        if not _read_pty(master_fd, output, 0.1):
            break
    if needle not in output[start:]:
        tail = bytes(output[-1000:]).decode("utf-8", errors="replace")
        raise QaFailure(
            f"PTY demo did not render {needle.decode()!r}; output tail={tail!r}"
        )


def _wait_for_exit(pid: int, master_fd: int, output: bytearray, deadline: float) -> int:
    while time.monotonic() < deadline:
        _read_pty(master_fd, output, 0.05)
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited == pid:
            return os.waitstatus_to_exitcode(status)
    raise QaFailure("PTY demo did not exit after the quit key")


def _poll_pty_child(pid: int, deadline: float, poll_seconds: float) -> bool:
    """Reap ``pid`` with non-blocking waits until ``deadline``."""

    while True:
        try:
            waited, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return True
        if waited == pid:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(poll_seconds, remaining))


def cleanup_pty_child(
    pid: int, *, grace_seconds: float = 1.0, poll_seconds: float = 0.05
) -> bool:
    """Terminate a PTY child without ever blocking the QA process.

    A well-behaved child exits during the SIGTERM grace period. A stuck child
    is escalated to SIGKILL, then polled for one more bounded grace period.
    """

    poll_seconds = max(poll_seconds, 0.001)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    if _poll_pty_child(pid, time.monotonic() + grace_seconds, poll_seconds):
        return True

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if _poll_pty_child(pid, time.monotonic() + grace_seconds, poll_seconds):
        return True
    raise QaFailure("PTY demo child did not exit after SIGKILL")


def run_pty_smoke() -> None:
    """Drive the real curses entrypoint against isolated ``--demo`` fixtures."""

    print("==> PTY demo smoke", flush=True)
    output = bytearray()
    pid = 0
    master_fd = -1
    reaped = False
    with tempfile.TemporaryDirectory(prefix="shep-qa-") as isolated_home:
        try:
            pid, master_fd = pty.fork()
            if pid == 0:
                environment = {
                    "HOME": isolated_home,
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                    "PATH": os.environ.get("PATH", os.defpath),
                    "TERM": "xterm-256color",
                }
                os.chdir(ROOT)
                os.execve(
                    sys.executable,
                    [sys.executable, "scripts/shep.py", "--demo"],
                    environment,
                )

            # Keep the full header visible so the refresh action has an
            # observable receipt instead of being hidden behind the compact
            # narrow-terminal summary.
            fcntl.ioctl(master_fd, termios_tiocswinsz(), struct.pack("HHHH", 40, 180, 0, 0))
            deadline = time.monotonic() + 10
            # Curses may insert an attribute escape between the two title
            # tokens, so assert the visible identity rather than raw adjacency.
            # The footer is emitted at the end of the first complete frame;
            # waiting for it keeps a fast CI parent from injecting mouse bytes
            # while the child is still initializing curses input handling.
            for needle in PTY_STARTUP_NEEDLES:
                _await_output(master_fd, output, needle, deadline)

            for label, payload, needle in pty_inputs_for_output(bytes(output)):
                if payload not in PTY_READ_ONLY_INPUTS:
                    raise QaFailure(f"PTY input is outside the read-only allowlist: {label}")
                if label == "fixture refresh":
                    time.sleep(1.1)
                output_start = len(output)
                os.write(master_fd, payload)
                if needle is not None:
                    _await_output(master_fd, output, needle, deadline, output_start)
                else:
                    _read_pty(master_fd, output, 0.15)

            exit_code = _wait_for_exit(pid, master_fd, output, deadline)
            reaped = True
            if exit_code != 0:
                raise QaFailure(f"PTY demo exited with code {exit_code}")
        finally:
            if master_fd >= 0:
                os.close(master_fd)
            if pid > 0 and not reaped:
                cleanup_pty_child(pid)
    print("PTY demo smoke passed: identity rendered and demo exited cleanly")


def termios_tiocswinsz() -> int:
    """Resolve the platform's PTY window-size ioctl lazily."""

    import termios

    return termios.TIOCSWINSZ


def main() -> int:
    try:
        run_checked(
            "test inventory",
            [sys.executable, "tools/verify_test_inventory.py"],
        )
        run_checked(
            "deterministic TUI tests",
            [sys.executable, "-m", "pytest", "-q", "tests/test_shep_tui.py"],
        )
        run_pty_smoke()
    except (OSError, QaFailure) as exc:
        print(f"self-QA failed: {exc}", file=sys.stderr)
        return 1
    print("Shep read-only self-QA passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
