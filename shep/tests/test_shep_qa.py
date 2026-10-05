from __future__ import annotations

import signal
import sys

from tools import shep_qa


def test_default_qa_runs_inventory_deterministic_tui_and_pty(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        shep_qa,
        "run_checked",
        lambda label, argv: calls.append((label, argv)),
    )
    monkeypatch.setattr(
        shep_qa,
        "run_pty_smoke",
        lambda: calls.append(("PTY demo smoke", None)),
    )

    assert shep_qa.main() == 0
    assert calls == [
        (
            "test inventory",
            [sys.executable, "tools/verify_test_inventory.py"],
        ),
        (
            "deterministic TUI tests",
            [sys.executable, "-m", "pytest", "-q", "tests/test_shep_tui.py"],
        ),
        ("PTY demo smoke", None),
    ]


def test_pty_smoke_inputs_are_navigation_refresh_and_quit_only() -> None:
    assert shep_qa.PTY_INPUTS == (
        ("click second demo row", b"\x1b[M #'", b"selected Claude review-gate"),
        ("keyboard down", b"j", b"No progress signal received."),
        ("keyboard up", b"k", b"Waiting for operator approval."),
        ("fixture refresh", b"r", b"refresh requested"),
        ("clean quit", b"q", None),
    )


def test_pty_smoke_waits_for_a_complete_frame_before_mouse_input() -> None:
    assert shep_qa.PTY_STARTUP_NEEDLES == (
        b"SHEP",
        b"COMMANDER",
        b"Codex atlas-build",
        b"[click] select",
    )


def test_pty_smoke_matches_the_mouse_encoding_enabled_by_curses() -> None:
    sgr_inputs = shep_qa.pty_inputs_for_output(b"\x1b[?1006;1000h")
    x10_inputs = shep_qa.pty_inputs_for_output(b"\x1b[?1000h")

    assert sgr_inputs[0][1] == b"\x1b[<0;3;7M"
    assert x10_inputs[0][1] == b"\x1b[M #'"
    assert sgr_inputs[1:] == x10_inputs[1:]


def test_pty_cleanup_reaps_after_sigterm_without_blocking(monkeypatch) -> None:
    now = [0.0]
    waits = iter(((0, 0), (4242, 0)))
    calls = []

    monkeypatch.setattr(shep_qa.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        shep_qa.time,
        "sleep",
        lambda seconds: now.__setitem__(0, now[0] + seconds),
    )
    monkeypatch.setattr(
        shep_qa.os,
        "kill",
        lambda pid, sig: calls.append(("kill", pid, sig)),
    )
    monkeypatch.setattr(
        shep_qa.os,
        "waitpid",
        lambda pid, options: calls.append(("waitpid", pid, options)) or next(waits),
    )

    assert shep_qa.cleanup_pty_child(4242, grace_seconds=1.0, poll_seconds=0.1)
    assert ("kill", 4242, signal.SIGTERM) in calls
    assert all(call[2] == shep_qa.os.WNOHANG for call in calls if call[0] == "waitpid")


def test_pty_cleanup_escalates_to_sigkill_after_bounded_grace(monkeypatch) -> None:
    now = [0.0]
    waits = iter(((0, 0), (0, 0), (0, 0), (4242, 0)))
    signals = []

    monkeypatch.setattr(shep_qa.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        shep_qa.time,
        "sleep",
        lambda seconds: now.__setitem__(0, now[0] + seconds),
    )
    monkeypatch.setattr(
        shep_qa.os,
        "kill",
        lambda pid, sig: signals.append((pid, sig)),
    )

    def waitpid(pid, options):
        assert options == shep_qa.os.WNOHANG
        return next(waits)

    monkeypatch.setattr(shep_qa.os, "waitpid", waitpid)

    assert shep_qa.cleanup_pty_child(4242, grace_seconds=0.2, poll_seconds=0.1)
    assert signals == [
        (4242, signal.SIGTERM),
        (4242, signal.SIGKILL),
    ]
