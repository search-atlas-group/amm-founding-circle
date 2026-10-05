"""Regression tests for the Shep tab badges and the LOGS view."""

from __future__ import annotations

import curses
import os
import time
from pathlib import Path

import pytest

from scripts import shep


@pytest.fixture(autouse=True)
def _clean_tab_badges():
    """Badges are module state shared by every view; never leak between tests."""
    shep._TAB_BADGES.clear()
    yield
    shep._TAB_BADGES.clear()


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0s"), (59, "59s"), (60, "1m"), (3599, "59m"), (3600, "1h"),
     (86399, "23h"), (86400, "1d")],
)
def test_compact_age_uses_the_fewest_unambiguous_characters(seconds, expected) -> None:
    assert shep.compact_age(seconds) == expected


def test_tab_badge_is_empty_until_the_data_actually_loads() -> None:
    """A blank badge means "not loaded"; 0 would claim the fleet is empty."""
    assert shep.tab_badge_text("agents") == ""


def test_tab_badge_reports_count_and_freshness() -> None:
    shep.set_tab_badge("agents", 12, now=1000.0)
    assert shep.tab_badge_text("agents", now=1120.0) == "12 2m"


def test_tab_badge_marks_a_rising_count() -> None:
    shep.set_tab_badge("beads", 3, now=1000.0)
    shep.set_tab_badge("beads", 5, now=1001.0)
    assert shep.tab_badge_text("beads", now=1001.0, ascii_only=True) == "5^ 0s"
    # Unchanged or falling is not a rise — the marker must not stick.
    shep.set_tab_badge("beads", 5, now=1002.0)
    assert shep.tab_badge_text("beads", now=1002.0, ascii_only=True) == "5 0s"


def test_tab_bar_shows_logs_and_its_badge() -> None:
    shep.set_tab_badge("logs", 7)
    assert "[4] LOGS 7" in shep.shep_tab_bar(120, "agents", ascii_only=True)


def test_a_badge_never_shifts_a_tab_out_from_under_a_click() -> None:
    """Layout and hit-testing must derive from the same badged widths."""
    shep.set_tab_badge("agents", 128)
    shep.set_tab_badge("beads", 64)
    for key, _text, start, tab_width in shep.shep_tab_layout(120, ascii_only=True):
        middle = start + tab_width // 2
        assert shep.mouse_tab_target(
            middle, shep.SHEP_TAB_Y, curses.BUTTON1_CLICKED, 120, True
        ) == key


def test_tab_geometry_does_not_move_as_the_counts_and_ages_change() -> None:
    """A live number must not slide the tab out from under an aiming cursor."""
    for key, count in (("agents", 9), ("beads", 7), ("missions", 3), ("logs", 35)):
        shep.set_tab_badge(key, count, now=1_000.0)
    before = [(k, s, w) for k, _t, s, w in shep.shep_tab_layout(140, ascii_only=True)]

    # Counts grow by orders of magnitude and ages run from seconds to days.
    shep.set_tab_badge("agents", 12345, now=1_000.0 - 500_000)
    shep.set_tab_badge("beads", 0, now=1_000.0 - 99)
    after = [(k, s, w) for k, _t, s, w in shep.shep_tab_layout(140, ascii_only=True)]
    assert before == after


def test_an_oversized_badge_keeps_the_count_and_drops_the_age() -> None:
    shep.set_tab_badge("beads", 1, now=0.0)
    shep.set_tab_badge("beads", 1234567, now=0.0)
    cell = shep.tab_badge_cell("beads", now=500_000.0, ascii_only=True)
    assert len(cell) == shep.TAB_BADGE_WIDTH
    assert cell.strip() == "1234567^"


def test_load_action_log_shows_terminal_receipts_newest_first(tmp_path, monkeypatch) -> None:
    from scripts import shep_action_log

    ledger = tmp_path / "events.jsonl"
    shep_action_log.append("nudge", "intent", target="herdr:a", text="first", path=ledger)
    shep_action_log.append("nudge", "sent", target="herdr:a", text="first", path=ledger)
    shep_action_log.append("nudge", "failed", target="herdr:b", text="second", path=ledger)
    monkeypatch.setattr(shep, "action_log_load", lambda: shep_action_log.load(ledger))

    entries, error = shep.load_action_log()
    assert error is None
    # The intent receipt is dropped: it always pairs with a terminal one.
    assert [entry["lifecycle"] for entry in entries] == ["failed", "sent"]
    assert shep.tab_badge_text("logs").startswith("2")


def test_load_action_log_reports_an_empty_ledger_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(shep, "action_log_load", lambda: [])
    entries, error = shep.load_action_log()
    assert entries == [] and "no actions recorded yet" in error


def test_log_entry_line_says_what_shep_said_and_to_whom() -> None:
    line = shep.log_entry_line(
        {
            "ts": 1785970706.0,
            "action": "nudge",
            "lifecycle": "sent",
            "mode": "auto",
            "target": "herdr:w34:pH",
            "metadata": {"session": "claude", "repository": "shep"},
            "text": "Run the failing test, then fix it.",
        },
        ascii_only=True,
    )
    assert "sent" in line
    assert "[CL]" in line and "shep" in line
    assert line.endswith("Run the failing test, then fix it.")


def test_log_entry_line_falls_back_to_the_failure_reason() -> None:
    line = shep.log_entry_line(
        {"ts": 0, "action": "reap", "lifecycle": "refused", "mode": "manual",
         "target": "herdr:x", "metadata": {}, "reason": "operator is attached"},
        ascii_only=True,
    )
    assert "refused" in line
    assert line.endswith("operator is attached")
    assert "herdr:x" in line  # no metadata, so the raw target still names the session


def test_log_row_drops_the_ledgers_own_boilerplate() -> None:
    """A receipt saying only "ok" must not fill the widest column with it.

    220 of 305 real rows carried a bare "ok" and every row carried "transport
    completed", which is what made the table unreadable.
    """
    event = {"ts": 0, "action": "reap", "lifecycle": "reaped", "mode": "manual",
             "metadata": {"repository": "macdaddy"},
             "result": "ok", "reason": "transport completed"}
    assert shep.log_said(event) == ""
    line = shep.log_entry_line(event, 8, ascii_only=True)
    assert "ok" not in line and "transport" not in line
    # and no divider is left dangling with nothing after it
    assert not line.rstrip().endswith("|")


def test_log_row_keeps_a_result_that_actually_says_something() -> None:
    event = {"ts": 0, "lifecycle": "reaped", "metadata": {},
             "result": "closed; worktree kept: locked worktree"}
    assert shep.log_said(event) == "closed; worktree kept: locked worktree"


def test_log_row_marks_autonomous_actions_not_manual_ones() -> None:
    """The exceptional action is the one Shep took on its own."""
    auto = shep.log_entry_line({"ts": 0, "lifecycle": "sent", "mode": "auto",
                                "metadata": {}, "text": "go"}, 8, ascii_only=True)
    manual = shep.log_entry_line({"ts": 0, "lifecycle": "sent", "mode": "manual",
                                  "metadata": {}, "text": "go"}, 8, ascii_only=True)
    assert auto.startswith("*")
    assert not manual.startswith("*")
    assert "(manual)" not in manual  # the old renderer tagged all 297 of these


def test_log_row_hides_a_repeated_minute_so_a_run_reads_as_a_group() -> None:
    event = {"ts": 1785970706.0, "lifecycle": "sent", "metadata": {}, "text": "x"}
    stamp = time.strftime("%H:%M", time.localtime(1785970706.0))
    first = shep.log_entry_line(event, 8, None, ascii_only=True)
    repeat = shep.log_entry_line(event, 8, stamp, ascii_only=True)
    assert stamp in first
    assert stamp not in repeat
    # the column still holds its width, so nothing shifts left
    assert first.index("|") == repeat.index("|")


def test_log_outcome_colour_separates_a_failure_from_a_success() -> None:
    """A failure buried in 300 receipts is exactly what this view must surface."""
    def outcome_pair(lifecycle):
        segments = shep.log_row_segments(
            {"ts": 0, "lifecycle": lifecycle, "metadata": {}}, 8,
        )
        return next(pair for text, pair, _ in segments if lifecycle in str(text))

    assert outcome_pair("failed") == 3          # red
    assert outcome_pair("sent") == 1            # green
    assert outcome_pair("failed") != outcome_pair("sent")


def test_log_rows_stay_ascii_and_aligned_in_a_colourless_terminal() -> None:
    events = [
        {"ts": 0, "lifecycle": "sent", "mode": "auto",
         "metadata": {"session": "claude", "repository": "shep"}, "text": "go"},
        {"ts": 0, "lifecycle": "reaped", "metadata": {"repository": "macdaddy"}},
        {"ts": 0, "lifecycle": "weird-new-thing", "metadata": {}, "target": "t"},
        {},  # a truncated ledger row must not take the view down
    ]
    lines = [shep.log_entry_line(e, 8, ascii_only=True) for e in events]
    for line in lines:
        assert line.isascii(), f"unicode leaked into ascii mode: {line!r}"
    # every row puts its first divider in the same column
    assert len({line.index("|") for line in lines}) == 1


def test_log_rows_stay_aligned_with_the_header_in_unicode_mode() -> None:
    """A wide gutter glyph (⚡ is two cells) once pushed every auto row one
    column right of the header — the whole ledger is auto receipts, so the
    entire table sat off its own grid.
    """
    events = [
        {"ts": 0, "lifecycle": "sent", "mode": "auto",
         "metadata": {"session": "claude", "repository": "shep"}, "text": "go"},
        {"ts": 0, "lifecycle": "reaped", "mode": "manual",
         "metadata": {"repository": "macdaddy"}, "result": "done"},
    ]
    repo_width = shep.log_repo_width(events)

    def divider_columns(line):
        columns, used = [], 0
        for char in line:
            if char == "│":
                columns.append(used)
            used += shep._text_columns(char)
        return columns

    header = divider_columns(shep.log_header_line(repo_width))
    for event in events:
        assert divider_columns(shep.log_entry_line(event, repo_width)) == header


def test_log_repo_column_is_sized_to_the_data_and_clamped() -> None:
    short = shep.log_repo_width([{"metadata": {"repository": "ab"}}])
    long = shep.log_repo_width(
        [{"metadata": {"repository": "mission-commander-2aae0b36-and-then-some"}}]
    )
    assert short == shep.LOG_REPO_MIN_WIDTH
    assert long == shep.LOG_REPO_MAX_WIDTH
    assert shep.log_repo_width([]) == shep.LOG_REPO_MIN_WIDTH



@pytest.mark.skipif(
    bool(os.environ.get("SHEP_TELEMETRY_CHANNEL")),
    reason="operator has explicitly opted into a telemetry channel",
)
def test_clickup_telemetry_is_off_unless_explicitly_opted_in() -> None:
    """Autonomous nudges must not DM the operator by default."""
    assert shep.CLICKUP_TELEMETRY_CHANNEL == ""


def test_log_badge_refreshes_only_when_the_ledger_actually_changed(
    tmp_path, monkeypatch
) -> None:
    """The badge must go live on its own without re-reading an idle ledger."""
    ledger = tmp_path / "events.jsonl"
    ledger.write_text("")
    reads = []
    monkeypatch.setattr(shep, "action_ledger_path", lambda: ledger)
    monkeypatch.setattr(shep, "action_log_load", lambda: reads.append(1) or [])
    shep._LOG_LEDGER_MTIME["at"] = None

    shep.refresh_log_badge()
    shep.refresh_log_badge()
    assert len(reads) == 1  # unchanged ledger is a stat, not a read

    os.utime(ledger, (0, 0))
    shep.refresh_log_badge()
    assert len(reads) == 2


def test_log_badge_refresh_survives_a_missing_ledger(monkeypatch) -> None:
    monkeypatch.setattr(shep, "action_ledger_path", lambda: Path("/nope/missing.jsonl"))
    monkeypatch.setattr(shep, "action_log_load", lambda: pytest.fail("must not read"))
    shep._LOG_LEDGER_MTIME["at"] = None
    shep.refresh_log_badge()  # a fleet refresh must never die on a missing ledger
