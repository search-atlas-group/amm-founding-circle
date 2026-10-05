"""End-to-end tests that press keys against the real curses loop.

Every case here is a defect that reached a running fleet and was found by a
human looking at the screen. They are written against the loop rather than the
helpers on purpose: each one passed its unit tests at the time it shipped.
"""

from __future__ import annotations

import curses
import threading
import time
from types import SimpleNamespace

import pytest

from tui_harness import (
    FakeScreen,
    _stub_curses,
    bracketed_paste,
    click,
    drive,
    fleet_row,
    resize,
)


@pytest.fixture(autouse=True)
def _clean_pile():
    from scripts import shep

    shep._DONE_PILE.clear()
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_STATE.clear()
    yield
    shep._DONE_PILE.clear()
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_STATE.clear()


def _finished(shep, target, label, reason):
    shep.record_done({"target": target, "label": label, "cwd": "/tmp/repo"}, reason)


def test_the_fleet_renders_without_a_terminal(monkeypatch) -> None:
    """The harness itself: if this breaks, nothing below means anything."""
    screen = drive(monkeypatch, [fleet_row("t1", "alpha")], [ord("q")])

    assert "COMMANDER M" in screen.text()
    assert screen.line_containing("alpha") is not None


def test_clicking_the_second_agents_row_selects_it(monkeypatch) -> None:
    screen = drive(
        monkeypatch,
        [
            fleet_row("t1", "alpha", preview="output from alpha"),
            fleet_row("t2", "beta", preview="output from beta"),
        ],
        [click(2, 6), ord("q")],
    )

    assert screen.line_containing("SELECTED 2/2") is not None
    assert screen.line_containing("output from beta") is not None


def test_unsupported_mouse_event_stays_visible_without_crashing(monkeypatch) -> None:
    from scripts import shep

    class UnsupportedMouseScreen(FakeScreen):
        def getmouse(self):
            raise curses.error("terminal has no mouse protocol")

    screen = UnsupportedMouseScreen(
        keys=[click(2, shep.SHEP_TAB_Y), ord("q")],
    )
    _stub_curses(monkeypatch, screen)

    shep.run_tui(screen, initial_rows=[fleet_row("t1", "alpha")])

    assert screen.line_containing("mouse unavailable") is not None
    assert screen.line_containing("no mouse protocol") is not None


def test_resizing_redraws_at_the_new_terminal_size(monkeypatch) -> None:
    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [resize(height=20, width=60), ord("q")],
    )

    assert screen.getmaxyx() == (20, 60)
    assert screen.line_containing("alpha") is not None


def test_keyboard_selection_and_main_footer_are_wired(monkeypatch) -> None:
    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha"), fleet_row("t2", "beta")],
        [curses.KEY_DOWN, ord("q")],
    )

    assert screen.line_containing("SELECTED 2/2") is not None
    footer = screen.lines()[-1]
    assert "[j/k] select" in footer
    assert "[click] select" in footer


def test_j_k_and_arrows_move_the_public_fleet_cursor_in_both_directions(
    monkeypatch,
) -> None:
    screen = drive(
        monkeypatch,
        [
            fleet_row("t1", "alpha"),
            fleet_row("t2", "beta"),
            fleet_row("t3", "gamma"),
        ],
        [ord("j"), curses.KEY_DOWN, ord("k"), curses.KEY_UP, ord("q")],
    )

    # The intermediate frames prove both downward routes and the final frame
    # proves both upward routes returned to the original row.
    assert screen.saw("SELECTED 2/3")
    assert screen.saw("SELECTED 3/3")
    assert screen.line_containing("SELECTED 1/3") is not None


def test_numbered_tabs_1_through_4_are_reachable_from_the_public_loop(monkeypatch) -> None:
    from scripts import shep

    calls = []

    def stub_view(name):
        def view(*_args):
            calls.append(name)
            return [], "agents"

        return view

    monkeypatch.setattr(shep, "run_beads_view", stub_view("beads"))
    monkeypatch.setattr(shep, "run_missions_view", stub_view("missions"))
    monkeypatch.setattr(shep, "run_logs_view", stub_view("logs"))

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [ord("2"), ord("3"), ord("4"), ord("1"), ord("q")],
    )

    assert calls == ["beads", "missions", "logs"]
    assert all(screen.saw(f"[{number}] {label}") for number, label in (
        ("1", "AGENTS"), ("2", "BEADS"),
        ("3", "MISSIONS"), ("4", "LOGS"),
    ))


def test_tab_clicks_cycle_the_public_loop_into_each_other_view(monkeypatch) -> None:
    from scripts import shep

    calls = []

    def stub_view(name):
        def view(*_args):
            calls.append(name)
            return [], "agents"

        return view

    monkeypatch.setattr(shep, "run_beads_view", stub_view("beads"))
    monkeypatch.setattr(shep, "run_missions_view", stub_view("missions"))
    monkeypatch.setattr(shep, "run_logs_view", stub_view("logs"))
    tabs = {key: start for key, _text, start, _width in shep.shep_tab_layout(119)}
    keys = [
        click(tabs[key] + 1, shep.SHEP_TAB_Y)
        for key in ("beads", "missions", "logs")
    ] + [ord("q")]

    drive(monkeypatch, [fleet_row("t1", "alpha")], keys)

    assert calls == ["beads", "missions", "logs"]


def test_refresh_key_shows_an_observable_receipt(monkeypatch) -> None:
    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [ord("r"), ord("q")],
    )

    assert screen.line_containing("refresh requested") is not None


def test_fake_screen_fails_loudly_when_an_event_loop_hangs() -> None:
    screen = FakeScreen(keys=[])

    with pytest.raises(AssertionError, match="loop never quit"):
        screen.getch()


def test_agents_show_the_full_fleet_beside_the_selected_session(monkeypatch) -> None:
    """A normal-width terminal must not strand the fleet below its context.

    The old stacked fallback showed only the first half of a 24-session fleet
    and put the selected session's context below that partial table. The
    side-by-side layout gives the fleet the full body height and keeps the
    selected context in the right-hand panel.
    """
    rows = [
        fleet_row(f"t{i}", f"agent-{i}", preview=f"output from {i}") for i in range(24)
    ]

    screen = drive(monkeypatch, rows, [ord("q")], height=40, width=120)

    selected_line = screen.line_containing("SELECTED 1/24")

    assert screen.line_containing("agent-23") is not None
    assert selected_line is not None
    assert selected_line.index("SELECTED") > 48
    assert screen.line_containing("output from 0") is not None


def test_startup_shows_loading_while_the_first_refresh_is_pending(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocked_collection():
        started.set()
        release.wait(1)
        return []

    from scripts import shep

    monkeypatch.setattr(shep, "collect_all", blocked_collection)
    monkeypatch.setattr(shep, "load_mission_deck", lambda **_k: ([], None))
    screen = FakeScreen(height=30, width=100, keys=[ord("q")])
    _stub_curses(monkeypatch)

    shep.run_tui(screen)
    release.set()

    assert started.is_set()
    loading_line = screen.line_containing("LOADING")
    assert loading_line is not None
    loading_at = loading_line.index("LOADING")
    assert 40 <= loading_at <= 55


def test_refresh_failure_is_rendered_and_does_not_end_the_tui(monkeypatch) -> None:
    started = threading.Event()

    def failed_collection():
        started.set()
        raise RuntimeError("collector exploded")

    from scripts import shep

    class YieldingScreen(FakeScreen):
        def getch(self):
            if self._keys and self._keys[0] == -1:
                started.wait(1)
                time.sleep(0.01)
            return super().getch()

    monkeypatch.setattr(shep, "collect_all", failed_collection)
    monkeypatch.setattr(shep, "load_mission_deck", lambda **_k: ([], None))
    screen = YieldingScreen(height=30, width=100, keys=[-1, ord("q")])
    _stub_curses(monkeypatch)

    shep.run_tui(screen)

    assert screen.line_containing("refresh failed") is not None
    assert screen.line_containing("collector exploded") is not None


def test_resize_below_minimum_is_visible_and_recovery_renders_again(monkeypatch) -> None:
    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [resize(height=10, width=30), resize(height=20, width=60), ord("q")],
    )

    # The production loop clips the full diagnostic to the narrow terminal;
    # the stable public receipt is its critical prefix.
    assert screen.saw("Terminal to")
    assert screen.line_containing("alpha") is not None


def test_clicking_a_finished_row_does_not_kill_the_tui(monkeypatch) -> None:
    """A recalled row carries index=None because its pane is gone. The Enter
    path guarded for that; the mouse path assigned it straight to `selected`,
    so the next rows[selected] raised TypeError past a handler that catches only
    curses.error -- and curses.wrapper re-raised, taking the whole app down."""
    from scripts import shep

    _finished(shep, "%9", "builder-9", "tests green, MR open")
    monkeypatch.setattr(
        curses,
        "getmouse",
        lambda: (0, 2, shep.SHEP_TAB_Y + 2, 0, curses.BUTTON1_CLICKED),
        raising=False,
    )

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [curses.KEY_MOUSE, ord("q")],
    )

    assert "alpha" in screen.text()


def test_the_context_panel_describes_the_row_the_queue_cursor_is_on(
    monkeypatch,
) -> None:
    """The panel is driven by the fleet cursor, and follow_pending cannot move
    that cursor onto a session whose pane has exited. So arrowing onto a
    recalled row left the panel showing another session's live output under the
    recalled one's name."""
    from scripts import shep

    _finished(shep, "%9", "builder-9", "tests green, MR open")

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha", preview="alpha is still working")],
        # tab focuses the queue; the only queue row is the recalled one.
        [ord("\t"), ord("q")],
    )
    text = screen.text()

    assert "builder-9" in text
    assert "pane has since closed" in text
    # The live session's output must not be sitting under the recalled name.
    assert "alpha is still working" not in text


def test_finished_work_is_not_announced_as_waiting_on_you(monkeypatch) -> None:
    """Observed live: "PENDING · 24 waiting on you" where all twenty-four were
    completed sessions and nothing was blocked."""
    from scripts import shep

    for i in range(24):
        _finished(shep, f"%{i}", f"builder-{i}", "done")

    screen = drive(monkeypatch, [fleet_row("t1", "alpha")], [ord("q")])
    title = screen.line_containing("PENDING")

    assert title is not None
    assert "24 waiting on you" not in title
    assert "nothing waiting" in title
    assert "24 finished" in title


def test_a_held_draft_is_announced_as_waiting_on_you(monkeypatch) -> None:
    """The other half: the queue keys on a held event, and only the headless
    sweep used to write one, so a draft the TUI held was rendered HELD: in the
    table and was absent from the queue built to collect it."""
    from scripts import shep

    shep.record_nudge_event("t1", "held", "Run make ship and fix it.", "opaque target")

    screen = drive(monkeypatch, [fleet_row("t1", "alpha")], [ord("q")])
    title = screen.line_containing("PENDING")

    assert "1 waiting on you" in title
    assert screen.line_containing("APPROVE") is not None


def test_held_nudge_waits_for_explicit_queue_approval(monkeypatch) -> None:
    from scripts import shep

    shep.record_nudge_event("t1", "held", "Run make ship.", "requires approval")
    sent = []
    monkeypatch.setattr(
        shep,
        "send_nudge",
        lambda *_args, **_kwargs: sent.append(True) or (True, "sent"),
    )

    screen = drive(monkeypatch, [fleet_row("t1", "alpha")], [ord("\t"), ord("q")])

    assert sent == []
    assert screen.line_containing("APPROVE") is not None


def test_queue_enter_approves_a_held_nudge_and_shows_receipt(monkeypatch) -> None:
    from scripts import shep

    shep.record_nudge_event("t1", "held", "Run make ship.", "requires approval")
    sent = []
    monkeypatch.setattr(
        shep,
        "send_nudge",
        lambda row, text, **_kwargs: sent.append((row["target"], text))
        or (True, "transport receipt"),
    )

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [ord("\t"), curses.KEY_ENTER, ord("q")],
    )

    assert sent == [("t1", "Run make ship.")]
    assert screen.line_containing("sent: Run make ship.") is not None


def test_queue_approval_failure_stays_visible_with_failure_receipt(monkeypatch) -> None:
    from scripts import shep

    shep.record_nudge_event("t1", "held", "Run make ship.", "requires approval")
    monkeypatch.setattr(
        shep,
        "send_nudge",
        lambda *_args, **_kwargs: (False, "bridge offline"),
    )

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [ord("\t"), curses.KEY_ENTER, ord("q")],
    )

    assert screen.line_containing("failed: bridge offline") is not None
    assert screen.line_containing("APPROVE") is not None


def test_queue_focus_shows_the_full_action_reason_in_the_context_panel(
    monkeypatch,
) -> None:
    from scripts import shep

    shep.record_nudge_event(
        "t1",
        "held",
        "Run make ship and fix it.",
        "opaque target in Makefile",
    )

    screen = drive(monkeypatch, [fleet_row("t1", "alpha")], [ord("\t"), ord("q")])

    action_line = screen.line_containing("ACTION QUEUE")
    assert action_line is not None
    assert "APPROVE" in action_line
    assert screen.line_containing("held because: opaque target in Makefile") is not None


def test_session_navigation_ascends_list_detail_and_input_one_level(monkeypatch) -> None:
    from scripts import shep

    sent = []
    monkeypatch.setattr(
        shep,
        "capture_pane",
        lambda *_a, **_k: "agent output\n",
    )
    monkeypatch.setattr(
        shep,
        "send_session_key",
        lambda row, key: sent.append((row["target"], key)) or (True, "x"),
    )

    drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [
            curses.KEY_RIGHT,
            "i",
            curses.KEY_LEFT,
            ord("i"),
            ord("x"),
            27,
            curses.KEY_LEFT,
            ord("q"),
        ],
    )

    assert sent == [("t1", ord("x"))]


def test_enter_opens_detail_and_left_returns_to_the_agents_list(monkeypatch) -> None:
    from scripts import shep

    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [curses.KEY_ENTER, curses.KEY_LEFT, ord("q")],
    )

    assert screen.saw("agent output")
    assert screen.saw("[i] interact")
    assert screen.line_containing("SELECTED 1/1") is not None


def test_escape_leaves_interactive_mode_before_left_ascends_detail(
    monkeypatch,
) -> None:
    from scripts import shep

    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")

    screen = drive(
        monkeypatch,
        [fleet_row("t1", "alpha")],
        [curses.KEY_ENTER, ord("i"), 27, curses.KEY_LEFT, ord("q")],
    )

    assert screen.saw("INTERACTIVE")
    assert screen.saw("[i] interact")
    assert screen.line_containing("SELECTED 1/1") is not None


def test_wispr_bracketed_paste_reaches_the_pane_with_spaces_intact(monkeypatch) -> None:
    from scripts import shep

    sent = []
    screen = FakeScreen(
        keys=bracketed_paste("dictated  text\nwith  repeated   spaces ✅")
        + ["\x1b", curses.KEY_LEFT],
    )
    _stub_curses(monkeypatch, screen)
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")
    monkeypatch.setattr(
        shep,
        "_run",
        lambda argv, **_kwargs: sent.append((argv, _kwargs))
        or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    shep.run_session_view(screen, fleet_row("t1", "alpha"), False, interactive=True)

    assert [call[0][-1] for call in sent] == [
        "dictated  text\nwith  repeated   spaces ✅"
    ]
    assert screen.saw("input sent")


def test_session_view_reads_unicode_text_and_reserves_escape(monkeypatch) -> None:
    from scripts import shep

    class WideInputScreen(FakeScreen):
        def getch(self):
            raise AssertionError("interactive input must use get_wch")

        def get_wch(self):
            if not self._keys:
                raise AssertionError("loop never quit")
            return self._keys.pop(0)

    sent = []
    screen = WideInputScreen(keys=["✅", "\x1b", curses.KEY_LEFT])
    _stub_curses(monkeypatch, screen)
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")
    monkeypatch.setattr(
        shep,
        "send_session_key",
        lambda row, key: sent.append(key) or (True, key),
    )

    shep.run_session_view(
        screen, fleet_row("t1", "alpha"), False, interactive=True
    )

    assert sent == ["✅"]


def test_session_transport_failure_is_visible_without_crashing(monkeypatch) -> None:
    from scripts import shep

    screen = FakeScreen(
        keys=bracketed_paste("dictated  text\nwith Unicode ✅")
        + ["\x1b", curses.KEY_LEFT],
    )
    _stub_curses(monkeypatch, screen)
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")

    def failed_transport(*_args, **_kwargs):
        raise RuntimeError("Wispr bridge unavailable")

    monkeypatch.setattr(shep, "_run", failed_transport)

    shep.run_session_view(
        screen, fleet_row("t1", "alpha"), False, interactive=True
    )

    assert screen.line_containing("input unavailable") is not None
    assert screen.line_containing("Wispr bridge unavailable") is not None


def test_every_write_stays_inside_the_terminal(monkeypatch) -> None:
    """FakeScreen raises on an out-of-bounds addstr, which is what proves
    safe_addstr is actually in front of every write rather than most of them.
    A narrow terminal is where that guard earns its keep."""
    from scripts import shep

    _finished(shep, "%9", "builder-9", "a reason long enough to need clipping")
    shep.record_nudge_event("t1", "held", "Run make ship.", "opaque target")

    for width, height in ((40, 14), (60, 20), (200, 60)):
        screen = drive(
            monkeypatch,
            [fleet_row("t1", "alpha")],
            [ord("\t"), ord("q")],
            width=width,
            height=height,
        )
        assert screen.lines()


def test_fake_screen_rejects_a_write_that_crosses_the_right_edge() -> None:
    screen = FakeScreen(height=2, width=4)

    with pytest.raises(curses.error, match="addstr out of bounds"):
        screen.addstr(0, 3, "xx")


def test_fake_screen_counts_wide_and_combining_unicode_as_terminal_cells() -> None:
    screen = FakeScreen(height=1, width=4)

    screen.addstr(0, 0, "界e\u0301")
    screen.addstr(0, 3, "x")

    assert screen.lines() == ["界e\u0301x"]
    with pytest.raises(curses.error, match="addstr out of bounds"):
        screen.addstr(0, 3, "界")


# --- The other three tabs ----------------------------------------------------

from tui_harness import drive_beads, drive_logs, drive_missions, mission  # noqa: E402


def test_the_missions_deck_renders_its_rows(monkeypatch) -> None:
    screen, (missions, _tab) = drive_missions(
        monkeypatch,
        [mission("m1", "bug-hunter", "close bh-1")],
        [ord("q")],
    )

    assert "SUGGESTED MISSIONS" in screen.text()
    assert screen.line_containing("bug-hunter") is not None
    assert len(missions) == 1


def test_missions_never_closes_a_session_from_its_stale_snapshot(
    monkeypatch,
) -> None:
    """This replaces a test that asserted the reap handler must EXIST, which
    pinned a defect in place: the handler closed live sessions that were doing
    work. `rows` is the fleet as it looked when the tab opened and is never
    refreshed, RUNNING comes from a worktree directory that survives the close
    so the deck can never acknowledge it, and the second press re-resolved a
    pane id that herdr may since have recycled.

    Asserted as behaviour, not as the absence of a key: pressing [x] must not
    reach reap_session, and must say where closing actually works."""
    from scripts import shep

    monkeypatch.setattr(
        shep,
        "reap_session",
        lambda *_a, **_k: pytest.fail("the deck must not close a session"),
    )

    screen, _ = drive_missions(
        monkeypatch,
        [mission("m1")],
        [ord("x"), ord("q")],
    )

    assert screen.line_containing("AGENTS tab") is not None


def test_the_missions_footer_only_advertises_keys_it_answers(monkeypatch) -> None:
    """The dead-end that started this: the view printed "reap it first to
    relaunch" while having no reap at all. Whatever the footer offers has to be
    a key the loop actually handles."""
    import re

    import inspect

    screen, _ = drive_missions(monkeypatch, [mission("m1")], [ord("q")])
    footer = screen.lines()[-1]
    source = inspect.getsource(shep_module().run_missions_view)

    advertised = set(re.findall(r"\[([a-z])\]", footer))
    handled = set(re.findall(r"""ord\(["']([a-z])["']\)""", source))
    # enter/l/j/k and the tab digits are matched separately by the loop.
    assert advertised - handled - {"1", "2", "3", "4"} == set()


def shep_module():
    from scripts import shep

    return shep


def test_regen_reports_a_shrinking_deck(monkeypatch) -> None:
    """ "same N missions (backlog unchanged)" over an empty screen was the
    worst case: it advised dismissing one of the nothing shown."""
    from scripts import shep

    decks = iter([[mission("a"), mission("b"), mission("c")], []])
    monkeypatch.setattr(shep, "load_mission_deck", lambda **_k: (next(decks), None))
    monkeypatch.setattr(shep, "mission_is_running", lambda _m: False)
    screen = _drive_raw(monkeypatch, [ord("r"), ord("q")])

    text = screen.text()
    assert "3 gone" in text
    assert "backlog unchanged" not in text


def _drive_raw(monkeypatch, keys):
    """run_missions_view with load_mission_deck already stubbed by the caller."""
    from scripts import shep

    from tui_harness import FakeScreen, _stub_curses

    screen = FakeScreen(height=40, width=120, keys=list(keys))
    _stub_curses(monkeypatch)
    shep.run_missions_view(screen, False, [])
    return screen


def test_the_logs_view_renders_the_ledger(monkeypatch) -> None:
    entry = {
        "ts": 1785999625.0,
        "lifecycle": "reaped",
        "target": "t1",
        "metadata": {"repository": "shep", "session": "alpha"},
        "result": "closed",
    }

    screen, (entries, _tab) = drive_logs(monkeypatch, [entry], [ord("q")])

    assert "shep" in screen.text()
    assert len(entries) == 1


def test_the_logs_view_survives_an_empty_ledger(monkeypatch) -> None:
    screen, (entries, _tab) = drive_logs(monkeypatch, [], [ord("q")])

    assert entries == []
    assert screen.lines()


def test_mouse_events_are_reusable_across_tab_drivers(monkeypatch) -> None:
    _screen, (_entries, tab) = drive_logs(
        monkeypatch,
        [],
        [click(18, shep_module().SHEP_TAB_Y)],
    )

    assert tab == "beads"


def test_clicking_the_second_log_row_selects_that_entry(monkeypatch) -> None:
    entries = [
        {"ts": 2.0, "lifecycle": "sent", "target": "t1", "metadata": {}},
        {"ts": 1.0, "lifecycle": "failed", "target": "t2", "metadata": {}},
    ]

    screen, _result = drive_logs(
        monkeypatch,
        entries,
        [-1, click(2, shep_module().SHEP_TAB_Y + 3), ord("q")],
    )

    assert screen.line_containing("selected t2") is not None


def test_clicking_the_second_mission_row_launches_that_mission(monkeypatch) -> None:
    shep = shep_module()
    launched = []
    monkeypatch.setattr(
        shep,
        "launch_mission_by_id",
        lambda mission_id, **_kwargs: launched.append(mission_id)
        or (True, "started"),
    )

    drive_missions(
        monkeypatch,
        [mission("m1"), mission("m2")],
        [-1, click(2, shep.SHEP_TAB_Y + 6), curses.KEY_ENTER, ord("Y"), ord("q")],
    )

    assert launched == ["m2"]


def test_tab_cycles_focus_between_bead_missions_and_backlog(monkeypatch) -> None:
    shep = shep_module()
    beads = [
        {"id": "b1", "title": "one", "status": "open", "priority": 1, "repo": "r"},
        {"id": "b2", "title": "two", "status": "open", "priority": 1, "repo": "r"},
    ]
    launched = []
    monkeypatch.setattr(
        shep,
        "launch_mission_by_id",
        lambda mission_id, **_kwargs: launched.append(mission_id)
        or (True, "started"),
    )

    screen, _result = drive_beads(
        monkeypatch,
        beads,
        missions=[mission("m1"), mission("m2")],
        keys=[
            -1,
            ord("\t"),
            ord("j"),
            ord("\t"),
            ord("j"),
            curses.KEY_ENTER,
            ord("Y"),
            ord("q"),
        ],
    )

    assert launched == ["m2"]
    assert screen.line_containing("launched: started") is not None


def test_the_beads_view_renders_the_backlog(monkeypatch) -> None:
    bead = {
        "id": "bh-1",
        "title": "fix the thing",
        "status": "open",
        "priority": 0,
        "repo": "bug-hunter",
    }

    screen, _ = drive_beads(monkeypatch, [bead], keys=[ord("q")])

    assert screen.line_containing("bh-1") is not None


def test_clicking_the_second_bead_row_targets_that_bead(monkeypatch) -> None:
    shep = shep_module()
    beads = [
        {"id": "b1", "title": "one", "status": "open", "priority": 1, "repo": "r"},
        {"id": "b2", "title": "two", "status": "open", "priority": 1, "repo": "r"},
    ]
    closed = []
    monkeypatch.setattr(
        shep,
        "_build_beads_view",
        lambda force=False: (
            beads,
            None,
            [],
            {"b1": "stale", "b2": "stale"},
            "stubbed",
        ),
    )
    monkeypatch.setattr(
        shep,
        "close_bead",
        lambda bead, reason: closed.append(bead["id"]) or (True, "closed"),
    )

    screen = FakeScreen(
        keys=[-1, click(2, shep.SHEP_TAB_Y + 6), ord("x"), ord("x"), ord("q")]
    )
    _stub_curses(monkeypatch, screen)

    shep.run_beads_view(screen, False)

    assert closed == ["b2"]


def test_every_tab_stays_inside_a_narrow_terminal(monkeypatch) -> None:
    """FakeScreen raises rather than clipping, so this fails on any write that
    skipped safe_addstr — the guard is only worth something everywhere."""
    bead = {"id": "bh-1", "title": "t", "status": "open", "priority": 0, "repo": "r"}
    entry = {"ts": 1.0, "lifecycle": "reaped", "target": "t1", "metadata": {}}

    for width, height in ((40, 14), (72, 24)):
        drive_missions(
            monkeypatch, [mission("m1")], [ord("q")], width=width, height=height
        )
        drive_logs(monkeypatch, [entry], [ord("q")], width=width, height=height)
        drive_beads(monkeypatch, [bead], keys=[ord("q")], width=width, height=height)
