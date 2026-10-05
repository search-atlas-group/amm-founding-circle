"""Regression tests for the Shep terminal renderer."""

from __future__ import annotations

import curses
import inspect
import datetime
import json
import subprocess
import sys
import termios
import threading
import time
import os
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import shep
from tui_harness import FakeScreen, _stub_curses, bracketed_paste, fleet_row


@pytest.fixture(autouse=True)
def _mission_engine_installed(tmp_path_factory, monkeypatch):
    """Point the installed-skills guard at files that exist.

    load_mission_deck() early-returns "mission engine skills not installed" when
    the real skill scripts are absent from disk, before reaching the
    _generate_deck the deck tests patch. That made 11 tests pass only on a
    machine with the mission-engine skills installed and fail on CI. Tests that
    want the not-installed branch patch a constant back to a missing path.
    """
    installed = tmp_path_factory.mktemp("mission-skills")
    for const in ("MISSION_SENSE_SCRIPT", "MISSION_RECOMMEND_SCRIPT"):
        script = installed / f"{const.lower()}.py"
        script.touch()
        monkeypatch.setattr(shep, const, script)


def test_resolve_herdr_ctl_prefers_source_managed_skill(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SHEP_HERDR_CTL", raising=False)
    source = tmp_path / "Sync/.agent-config/skills-shared/herdr/scripts/herdr_ctl.py"
    legacy = tmp_path / ".claude/skills/herdr/scripts/herdr_ctl.py"
    source.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    source.touch()
    legacy.touch()

    assert shep._resolve_herdr_ctl(tmp_path) == source


def test_resolve_herdr_ctl_falls_back_to_legacy_install(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SHEP_HERDR_CTL", raising=False)
    legacy = tmp_path / ".claude/skills/herdr/scripts/herdr_ctl.py"
    legacy.parent.mkdir(parents=True)
    legacy.touch()

    assert shep._resolve_herdr_ctl(tmp_path) == legacy


def test_resolve_herdr_ctl_supports_explicit_override(tmp_path, monkeypatch) -> None:
    override = tmp_path / "custom/herdr_ctl.py"
    monkeypatch.setenv("SHEP_HERDR_CTL", os.fspath(override))

    assert shep._resolve_herdr_ctl(tmp_path) == override


def test_collect_warp_finds_live_direct_shells_and_marks_them_read_only(tmp_path, monkeypatch) -> None:
    ps = "\n".join(
        (
            "100 1 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable --finish-update",
            "200 100 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable terminal-server --parent-pid=100",
            "300 200 ttys001 S+ 00:10 -zsh -g --no_rcs",
            "400 300 ttys001 S+ 00:09 /opt/homebrew/bin/codex --dangerously-bypass",
            "500 1 ttys002 Ss 00:10 /bin/zsh",
        )
    )

    def fake_run(argv, **_kwargs):
        if argv[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=ps, stderr="")
        if argv[0] == "lsof":
            return SimpleNamespace(
                returncode=0, stdout="p300\nfcwd\nn/tmp/warp-repo\n", stderr="",
            )
        raise AssertionError(f"unexpected subprocess: {argv}")

    monkeypatch.setattr(shep, "_run", fake_run)
    monkeypatch.setenv("SHEP_WARP_SQLITE_DB", str(tmp_path / "no-warp.sqlite"))
    monkeypatch.delenv("SHEP_WARP_SIDECAR", raising=False)

    rows = shep.collect_warp()

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "warp"
    assert row["target"] == "warp:300"
    assert row["label"] == "codex"
    assert row["session_label"] == "codex@warp-repo"
    assert row["cwd"] == "/tmp/warp-repo"
    assert row["status"] == "live-ro"
    assert row["read_only"] is True
    assert "TTY ttys001" in row["context"]
    assert "codex" in row["context"]
    assert "activity unavailable" in row["context"]
    assert "LIVE RO" in shep.status_badge(row)
    assert shep.status_display(row) == "~ live ro"


def test_warp_session_label_prefers_title_then_repo_then_tty() -> None:
    assert shep._warp_session_label("claude", "/tmp/linkgraph", "ttys001", 1, "amm repo") == "amm repo"
    assert shep._warp_session_label("claude", "/tmp/linkgraph", "ttys001", 1) == "claude@linkgraph"
    assert shep._warp_session_label("claude", str(Path.home()), "ttys009", 2) == "claude@ttys009"
    assert shep._warp_session_label("claude", "-", "??", 3) == "warp-3"



def test_collect_warp_applies_a_live_sidecar_identity_without_enabling_control(
    tmp_path, monkeypatch
) -> None:
    ps = "\n".join(
        (
            "100 1 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable --finish-update",
            "200 100 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable terminal-server",
            "300 200 ttys001 S+ 00:10 -zsh -g --no_rcs",
        )
    )
    sidecar = tmp_path / "sessions.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema": "shep-warp-sidecar/v1",
                "captured_at_s": time.time(),
                "sessions": [
                    {"pid": 300, "session_uuid_hex": "0011223344556677"}
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_run(argv, **_kwargs):
        if argv[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=ps, stderr="")
        if argv[0] == "lsof":
            return SimpleNamespace(
                returncode=0, stdout="p300\nfcwd\nn/tmp/warp-repo\n", stderr=""
            )
        raise AssertionError(f"unexpected subprocess: {argv}")

    monkeypatch.setattr(shep, "_run", fake_run)
    monkeypatch.setenv("SHEP_WARP_SIDECAR", str(sidecar))
    monkeypatch.setenv("SHEP_WARP_SQLITE_DB", str(tmp_path / "no-warp.sqlite"))
    monkeypatch.delenv("SHEP_WARP_SQLITE_TRANSCRIPTS", raising=False)

    row = shep.collect_warp()[0]

    assert row["status"] == "identified"
    assert row["warp_observation_status"] == "identified"
    assert row["warp_session_uuid"] == "0011223344556677"
    assert row["read_only"] is True
    assert "identified read-only" in row["context"]
    assert shep.send_nudge(row, "continue", audit=False) == (
        False,
        "warp sessions are read-only in this tool",
    )


def test_collect_warp_keeps_live_status_when_sidecar_degrades(
    tmp_path, monkeypatch
) -> None:
    ps = "\n".join(
        (
            "100 1 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable --finish-update",
            "200 100 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable terminal-server",
            "300 200 ttys001 S+ 00:10 -zsh -g --no_rcs",
        )
    )
    sidecar = tmp_path / "sessions.json"
    sidecar.write_text("{not json", encoding="utf-8")

    def fake_run(argv, **_kwargs):
        if argv[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=ps, stderr="")
        if argv[0] == "lsof":
            return SimpleNamespace(
                returncode=0, stdout="p300\nfcwd\nn/tmp/warp-repo\n", stderr=""
            )
        raise AssertionError(f"unexpected subprocess: {argv}")

    monkeypatch.setattr(shep, "_run", fake_run)
    monkeypatch.setenv("SHEP_WARP_SIDECAR", str(sidecar))
    monkeypatch.setenv("SHEP_WARP_SQLITE_DB", str(tmp_path / "no-warp.sqlite"))
    monkeypatch.delenv("SHEP_WARP_SQLITE_TRANSCRIPTS", raising=False)

    row = shep.collect_warp()[0]

    assert row["status"] == "live-ro"
    assert row["warp_observation_status"] == "unobserved"
    assert row["warp_reason"] == "sidecar_unreadable"
    assert "LIVE RO" in shep.status_badge(row)



def _write_warp_fixture_db(path: Path, panes: list) -> None:
    """Minimal Warp SQLite fixture with optional tabs/titles and block text."""
    import sqlite3

    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE tabs (
            id INTEGER PRIMARY KEY NOT NULL,
            window_id INTEGER NOT NULL,
            custom_title TEXT
        );
        CREATE TABLE pane_nodes (
            id INTEGER PRIMARY KEY NOT NULL,
            tab_id INTEGER NOT NULL,
            parent_pane_node_id INTEGER,
            flex FLOAT,
            is_leaf BOOLEAN NOT NULL
        );
        CREATE TABLE pane_leaves (
            pane_node_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            is_focused BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (pane_node_id, kind)
        );
        CREATE TABLE terminal_panes (
            id INTEGER PRIMARY KEY NOT NULL,
            kind TEXT NOT NULL DEFAULT 'terminal',
            uuid BLOB NOT NULL UNIQUE,
            cwd TEXT,
            is_active BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE TABLE blocks (
            id INTEGER PRIMARY KEY,
            pane_leaf_uuid BLOB NOT NULL,
            stylized_command BLOB NOT NULL,
            stylized_output BLOB NOT NULL,
            pwd TEXT,
            exit_code INTEGER NOT NULL,
            did_execute BOOLEAN NOT NULL,
            completed_ts DATETIME,
            start_ts DATETIME
        );
        """
    )
    connection.execute("PRAGMA user_version = 0")
    for index, pane in enumerate(panes, start=1):
        pane_id = bytes.fromhex(pane["uuid_hex"])
        connection.execute(
            "INSERT INTO tabs (id, window_id, custom_title) VALUES (?, 1, ?)",
            (index, pane.get("custom_title")),
        )
        connection.execute(
            "INSERT INTO pane_nodes (id, tab_id, is_leaf) VALUES (?, ?, 1)",
            (index, index),
        )
        connection.execute(
            "INSERT INTO pane_leaves (pane_node_id, kind, is_focused) VALUES (?, 'terminal', 1)",
            (index,),
        )
        connection.execute(
            "INSERT INTO terminal_panes (id, uuid, cwd, is_active) VALUES (?, ?, ?, 1)",
            (index, pane_id, pane["cwd"]),
        )
        for block in pane.get("blocks", []):
            ts = block.get("ts", datetime.datetime.now(datetime.timezone.utc).isoformat())
            connection.execute(
                """
                INSERT INTO blocks (
                    pane_leaf_uuid, stylized_command, stylized_output, pwd,
                    exit_code, did_execute, completed_ts, start_ts
                ) VALUES (?, ?, ?, ?, 0, 1, ?, ?)
                """,
                (
                    pane_id,
                    block.get("command", "echo").encode(),
                    block.get("output", "").encode(),
                    pane["cwd"],
                    ts,
                    ts,
                ),
            )
    connection.commit()
    connection.close()


def test_collect_warp_resolves_unique_cwd_to_pane_status_and_title(
    tmp_path, monkeypatch
) -> None:
    ps = "\n".join(
        (
            "100 1 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable --finish-update",
            "200 100 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable terminal-server",
            "300 200 ttys001 S+ 00:10 -zsh -g --no_rcs",
            "400 300 ttys001 S+ 00:09 /opt/homebrew/bin/claude",
        )
    )
    db = tmp_path / "warp.sqlite"
    _write_warp_fixture_db(
        db,
        [
            {
                "uuid_hex": "00112233445566778899aabbccddeeff",
                "cwd": "/tmp/unique-linkgraph",
                "custom_title": "amm repo",
                "blocks": [
                    {
                        "command": "ls",
                        "output": "README.md\nsrc\n",
                        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }
                ],
            }
        ],
    )

    def fake_run(argv, **_kwargs):
        if argv[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=ps, stderr="")
        if argv[0] == "lsof":
            return SimpleNamespace(
                returncode=0,
                stdout="p300\nfcwd\nn/tmp/unique-linkgraph\n",
                stderr="",
            )
        raise AssertionError(f"unexpected subprocess: {argv}")

    monkeypatch.setattr(shep, "_run", fake_run)
    monkeypatch.setenv("SHEP_WARP_SQLITE_DB", str(db))
    monkeypatch.delenv("SHEP_WARP_SIDECAR", raising=False)
    monkeypatch.delenv("SHEP_WARP_SCHEMA_FINGERPRINT", raising=False)
    monkeypatch.delenv("SHEP_WARP_SQLITE_TRANSCRIPTS", raising=False)

    row = shep.collect_warp()[0]

    assert row["status"] == "shell"
    assert row["session_label"] == "amm repo"
    assert row["warp_correlation"] == "cwd"
    assert row["read_only"] is True
    assert "activity unavailable" not in row["context"]
    assert "Warp native shell" not in row["context"]
    assert shep.send_nudge(row, "continue", audit=False)[0] is False


def test_collect_warp_leaves_ambiguous_cwd_as_live_ro(tmp_path, monkeypatch) -> None:
    ps = "\n".join(
        (
            "100 1 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable --finish-update",
            "200 100 ?? S 00:10 /Applications/Warp.app/Contents/MacOS/stable terminal-server",
            "300 200 ttys001 S+ 00:10 -zsh -g --no_rcs",
            "301 200 ttys002 S+ 00:10 -zsh -g --no_rcs",
        )
    )
    db = tmp_path / "warp.sqlite"
    _write_warp_fixture_db(
        db,
        [
            {
                "uuid_hex": "00112233445566778899aabbccddeeff",
                "cwd": "/Users/developer",
                "blocks": [{"command": "pwd", "output": "/Users/developer\n"}],
            },
            {
                "uuid_hex": "ffeeddccbbaa99887766554433221100",
                "cwd": "/Users/developer",
                "blocks": [{"command": "pwd", "output": "/Users/developer\n"}],
            },
        ],
    )

    def fake_run(argv, **_kwargs):
        if argv[0] == "ps":
            return SimpleNamespace(returncode=0, stdout=ps, stderr="")
        if argv[0] == "lsof":
            return SimpleNamespace(
                returncode=0,
                stdout="p300\nfcwd\nn/Users/developer\np301\nfcwd\nn/Users/developer\n",
                stderr="",
            )
        raise AssertionError(f"unexpected subprocess: {argv}")

    monkeypatch.setattr(shep, "_run", fake_run)
    monkeypatch.setenv("SHEP_WARP_SQLITE_DB", str(db))
    monkeypatch.delenv("SHEP_WARP_SIDECAR", raising=False)
    monkeypatch.delenv("SHEP_WARP_SCHEMA_FINGERPRINT", raising=False)

    rows = shep.collect_warp()
    assert len(rows) == 2
    assert {row["status"] for row in rows} == {"live-ro"}
    assert all(row.get("warp_reason") == "ambiguous_cwd" for row in rows)
    assert all("activity unavailable" in row["context"] for row in rows)


def test_warp_pane_state_reports_working_from_agent_chrome() -> None:
    text = "\n".join(
        (
            "╭──────────────────────────────────╮",
            "│ working on the patch             │",
            "╰──────────────────────────────────╯",
            "esc to interrupt",
        )
    )
    status, _cues, context = shep._warp_pane_state(text, "warp:1")
    assert status == "working"
    assert "esc to interrupt" in context or "working on the patch" in context



def test_warp_rows_cannot_send_or_reap(monkeypatch) -> None:
    row = {
        "source": "warp", "target": "warp:300", "read_only": True,
    }
    monkeypatch.setattr(
        shep, "_run", lambda *_a, **_k: pytest.fail("Warp must have no control transport")
    )

    assert shep.send_nudge(row, "continue", audit=False) == (
        False, "warp sessions are read-only in this tool",
    )
    assert shep.reap_session(row, audit=False) == (
        False, "warp sessions are read-only in this tool",
    )


def _display_width(text: str) -> int:
    return sum(
        0
        if unicodedata.combining(char)
        else 2
        if unicodedata.east_asian_width(char) in {"F", "W"}
        else 1
        for char in text
    )


class _WidthCheckingScreen:
    def __init__(self, width: int) -> None:
        self.width = width
        self.rendered = ""

    def addstr(self, _y: int, x: int, text: str, _attr: int) -> None:
        if x + _display_width(text) > self.width:
            raise curses.error("addwstr() returned ERR")
        self.rendered = text


_KEY_N = ord("n")


class _InputScreen:
    def __init__(self, key=_KEY_N, keys=None) -> None:
        self.key = key
        self.keys = iter(keys or [])
        self.timeouts = []
        self.rendered = []

    def timeout(self, milliseconds: int) -> None:
        self.timeouts.append(milliseconds)

    def getch(self) -> int:
        return self.key

    def get_wch(self):
        return next(self.keys)

    def addstr(self, *_args) -> None:
        self.rendered.append(_args)

    def move(self, *_args) -> None:
        pass

    def refresh(self) -> None:
        pass


class _WidthCheckingInputScreen(_InputScreen):
    def __init__(self, width: int, keys=None) -> None:
        super().__init__(keys=keys)
        self.width = width
        self.overflowed = False

    def addstr(self, _y: int, x: int, text: str, *_attrs) -> None:
        if x + _display_width(text) > self.width:
            self.overflowed = True
            raise curses.error("addwstr() returned ERR")
        self.rendered.append((_y, x, text, *_attrs))


class _RefreshErrorScreen:
    def refresh(self) -> None:
        raise curses.error("wrefresh() returned ERR")


def test_blocking_getch_waits_indefinitely_then_restores_polling() -> None:
    screen = _InputScreen()

    assert shep.blocking_getch(screen) == ord("n")
    assert screen.timeouts == [-1, shep.KEY_POLL_MS]


def test_reap_confirmation_repeats_the_reap_key() -> None:
    assert shep.confirms_with_same_key(ord("x"), ord("x"))
    assert not shep.confirms_with_same_key(ord("y"), ord("x"))


def test_blocking_edit_line_changes_prefilled_text() -> None:
    screen = _InputScreen(keys=[curses.KEY_LEFT, curses.KEY_BACKSPACE, "X", "\n"])

    assert shep.blocking_edit_line(screen, 1, "nudge> ", "draft", 40) == "draXt"
    assert screen.timeouts == [-1, shep.KEY_POLL_MS]


def test_blocking_edit_line_accepts_clean_replacement_from_empty_input() -> None:
    screen = _InputScreen(keys=list("Use the clean replacement.") + ["\n"])

    assert shep.blocking_edit_line(screen, 1, "nudge> ", "", 60) == (
        "Use the clean replacement."
    )


def test_blocking_edit_line_escape_cancels() -> None:
    screen = _InputScreen(keys=["\x1b"])

    assert shep.blocking_edit_line(screen, 1, "nudge> ", "draft", 40) is None


def test_blocking_edit_line_never_draws_wide_text_past_terminal_width() -> None:
    screen = _WidthCheckingInputScreen(
        width=10,
        keys=[curses.KEY_LEFT, "\x1b"],
    )

    assert shep.blocking_edit_line(screen, 1, "nudge> ", "✅ab", 10) is None
    assert screen.overflowed is False


def test_safe_refresh_ignores_resize_race() -> None:
    shep.safe_refresh(_RefreshErrorScreen())


def test_ui_colors_degrade_cleanly_without_terminal_color(monkeypatch) -> None:
    monkeypatch.setattr(curses, "start_color", lambda: None)
    monkeypatch.setattr(curses, "has_colors", lambda: False)
    monkeypatch.setattr(shep, "_UI_COLORS_READY", True)

    shep.init_ui_colors()

    assert shep._UI_COLORS_READY is False
    assert shep._ui_pair(1) == 0


def test_themes_normalize_cycle_and_support_mono() -> None:
    assert shep.normalize_theme("OCEAN") == "ocean"
    assert shep.normalize_theme("not-a-theme") == "classic"
    assert shep.next_theme("classic") == "ocean"
    assert shep.next_theme("mono") == "classic"

    shep.init_ui_colors("mono")
    assert shep._ACTIVE_THEME == "mono"
    assert shep._UI_COLORS_READY is False


def test_bulk_nudge_candidates_only_includes_safe_or_panel_cleared() -> None:
    rows = [
        {"target": "herdr:w1:p1", "label": "safe", "status": "idle",
         "context": "the next task is the regression test"},
        {"target": "herdr:w1:p2", "label": "held", "status": "idle",
         "context": "waiting for review"},
        {"target": "herdr:w1:p3", "label": "verified", "status": "idle",
         "context": "the finished branch is ready"},
    ]
    planned = {
        "herdr:w1:p1": "Continue with the regression test.",
        "herdr:w1:p2": "Email the customer now.",
        "herdr:w1:p3": "Git push the finished branch.",
    }
    verified = {"herdr:w1:p3": (planned["herdr:w1:p3"], True)}

    candidates, held = shep.bulk_nudge_candidates(rows, planned, verified)

    assert [(row["label"], text) for row, text in candidates] == [
        ("safe", planned["herdr:w1:p1"]),
        ("verified", planned["herdr:w1:p3"]),
    ]
    assert held == 1


def test_bulk_nudge_candidates_holds_stale_draft_for_working_session() -> None:
    row = {"target": "herdr:w1:p1", "label": "resumed", "status": "working"}
    planned = {row["target"]: "Continue with the current task."}

    candidates, held = shep.bulk_nudge_candidates([row], planned, {})

    assert candidates == []
    assert held == 1


def test_bulk_nudge_candidates_accepts_interactive_context_snapshot() -> None:
    row = {
        "target": "herdr:w1:p1",
        "label": "interactive",
        "status": "idle",
        # This is the cleaned context copied from the asynchronous pane
        # capture before the interactive fleet queue is rendered.
        "context": "pytest: the regression test is next",
    }
    planned = {
        row["target"]: "Continue with the regression test."
    }

    candidates, held = shep.bulk_nudge_candidates([row], planned, {})

    assert candidates == [(row, planned[row["target"]])]
    assert held == 0


def test_nudge_revalidation_rejects_changed_context_and_resumed_work() -> None:
    original = "Tests passed.\nWaiting at prompt."
    expected = shep.nudge_context_fingerprint(original)

    assert shep.nudge_revalidation_reason(
        {"status": "idle"}, expected, original
    ) is None
    assert shep.nudge_revalidation_reason(
        {"status": "idle"}, expected, "Running one shell command."
    ) == "session context changed"
    assert shep.nudge_revalidation_reason(
        {"status": "working"}, expected, original
    ) == "session is now working"


def test_classify_risk_recognizes_commit_and_push_as_push() -> None:
    assert shep.classify_risk("commit and push") == (
        "push",
        "pushes, deploys, or touches prod",
    )


def test_classify_risk_recognizes_natural_language_merge_action() -> None:
    assert shep.classify_risk("Continue and merge this in.")[0] == "merge"


def test_canonical_nudge_lexicon_matches_the_risk_sensor() -> None:
    for category, phrase in shep.canonical_nudge_phrases().items():
        assert shep.classify_risk(phrase)[0] == category


def test_nudge_row_text_shows_lifecycle_and_text(monkeypatch) -> None:
    row = {
        "target": "herdr:w1:p1",
        "context": "the regression test is next",
    }
    planned = {"herdr:w1:p1": "Continue with the regression test."}

    assert shep.nudge_row_text(row, planned, {}, set(), set()) == (
        "READY: Continue with the regression test."
    )
    assert shep.nudge_row_text(
        row,
        planned,
        {},
        set(),
        set(),
        {"scores": {"operational": 62}},
        "operational",
    ) == "HELD: Continue with the regression test."
    assert shep.nudge_row_text(row, planned, {}, set(), {"herdr:w1:p1"}) == (
        "VERIFYING: Continue with the regression test."
    )

    planned.clear()
    monkeypatch.setitem(
        shep._NUDGE_EVENTS,
        "herdr:w1:p1",
        {"status": "sent", "text": "Continue now.", "detail": "", "at": 1.0},
    )
    assert shep.nudge_row_text(row, planned, {}, set(), set()) == (
        "SENT: Continue now."
    )


def test_nudge_result_message_shows_submitted_text_instead_of_transport_glyph() -> None:
    assert shep.nudge_result_message(
        True, "Continue with the regression test.", "✅"
    ) == "sent: Continue with the regression test."
    assert shep.nudge_result_message(
        False, "Continue with the regression test.", "pane unavailable"
    ) == "failed: pane unavailable"


def test_nudge_abstention_message_explains_why_no_candidate_was_generated() -> None:
    assert shep.nudge_draft_skip_detail(True) == (
        "no actionable next step in visible work"
    )
    assert shep.nudge_draft_skip_detail(False) == (
        "Markdown engine returned no candidate"
    )


def test_sent_nudge_uses_success_color() -> None:
    assert shep.nudge_color_pair_id("SENT: Continue now.") == 1
    assert shep.nudge_color_pair_id("READY: Continue now.") == 4
    assert shep.nudge_color_pair_id("DRAFTING") == 4
    assert shep.nudge_color_pair_id("HELD: Review this first.") == 3
    assert shep.nudge_color_pair_id("-") == 0


def test_visual_identity_helpers_keep_plain_text_labels() -> None:
    assert shep.source_badge("herdr") == "Herdr"
    assert shep.source_badge("tmux") == "tmux"
    assert shep.agent_badge(
        {"source": "herdr", "label": "Codex"}
    ) == "[CX] Codex"
    assert shep.agent_badge(
        {"source": "herdr", "label": "Claude Code"}
    ) == "[CL] Claude Code"
    assert shep.agent_badge(
        {"source": "tmux", "label": "raw-session"}
    ) == "[T] raw-session"
    assert shep.agent_badge(
        {"source": "tmux", "label": "raw-session"}, source_visible=True
    ) == "raw-session"
    assert shep.agent_badge_token(
        {"source": "herdr", "label": "Codex"}
    ) == "[CX]"
    assert shep.agent_badge_pair_id(
        {"source": "herdr", "label": "Codex"}
    ) == 6
    assert shep.agent_badge_pair_id(
        {"source": "herdr", "label": "Claude"}
    ) == 7


def test_status_and_fleet_summary_are_legible_without_color() -> None:
    rows = [
        {"status": "working"},
        {"status": "idle"},
        {"status": "stalled"},
    ]
    assert shep.status_display(rows[0]) == "> working"
    assert shep.status_display(rows[2]) == "! stalled"
    assert shep.status_color_pair_id(rows[1]) == 1
    assert shep.fleet_summary(rows) == (
        "◆M◆ Commander M · SHEP · 3 sessions · "
        "1 active · 1 idle · 1 attention"
    )


def test_commander_m_identity_is_fixed_and_not_runtime_configurable(
    monkeypatch,
) -> None:
    assert shep.commander_m_brand() == "◆M◆ Commander M"
    assert shep.terminal_too_small_message(39, 15) == (
        "◆M◆ Commander M · Terminal too small (39x15). "
        "Resize to at least 40x16 to use shep."
    )

    monkeypatch.setattr(shep, "COMMANDER_M_INSIGNIA", "")
    monkeypatch.setattr(shep, "COMMANDER_M_NAME", "Not Shep")
    assert shep.commander_m_brand() == "◆M◆ Commander M"


def test_selected_nudge_detail_persists_text_and_time(monkeypatch) -> None:
    row = {"target": "herdr:w1:p1"}
    monkeypatch.setitem(
        shep._NUDGE_EVENTS,
        row["target"],
        {"status": "sent", "text": "Run the focused tests.", "at": 1.0},
    )
    detail = shep.nudge_event_detail(row)
    assert detail.startswith("last nudge · SENT ")
    assert detail.endswith(": Run the focused tests.")
    monkeypatch.setitem(
        shep._NUDGE_EVENTS,
        row["target"],
        {"status": "drafting", "text": "", "at": 1.0},
    )
    assert shep.nudge_event_detail(row) is None


def test_lifecycle_cues_require_explicit_close_and_terminal_status() -> None:
    text = (
        "All scoped work is committed.\n"
        "SAFE_TO_CLOSE: tests pass and nothing is left hanging.\n"
        "NEW_MISSION: Audit the next independent subsystem.\n"
    )

    assert shep.lifecycle_cues("done", text) == {
        "reap_ready": True,
        "reap_reason": "SAFE_TO_CLOSE: tests pass and nothing is left hanging.",
        "continuation": "Audit the next independent subsystem.",
    }
    assert shep.lifecycle_cues("working", text)["reap_ready"] is False
    assert shep.lifecycle_cues(
        "done", "Yes, safe to close. Nothing is left hanging."
    )["reap_ready"] is True
    assert shep.lifecycle_cues(
        "done", "Tell me when it is safe to close."
    )["reap_ready"] is False
    assert shep.lifecycle_cues(
        "done",
        "If clean, end your reply with exactly 'SAFE_TO_CLOSE: <why nothing is left hanging>'.",
    )["reap_ready"] is False


def test_new_user_request_after_safe_close_revokes_reap_readiness() -> None:
    text = (
        "SAFE_TO_CLOSE: profile registration is complete.\n"
        "\n"
        "› the profile disappeared, please recover it\n"
        "\n"
        "  gpt-5.6-luna high · ~/repo\n"
    )

    cues = shep.lifecycle_cues("idle", text)

    assert cues["reap_ready"] is False
    assert cues["reap_reason"] is None


def test_our_own_close_request_echoed_back_is_not_a_close_signal() -> None:
    """The pane showing our ask is transport proof, not the agent answering it."""
    shep._NUDGE_STATE.clear()
    target = "herdr:w9:p2"
    ask = "SAFE_TO_CLOSE: say why nothing is left hanging."
    shep.remember_nudge(shep._nudge_state(target), ask)

    # Verbatim on screen, and wrapped mid-word at the pane width, as herdr does.
    assert shep.lifecycle_cues("done", ask, target=target)["reap_ready"] is False
    wrapped = "SAFE_TO_CLOSE: say why nothi\nng is left hanging."
    assert shep.lifecycle_cues("done", wrapped, target=target)["reap_ready"] is False

    # Without the state there is nothing to subtract, which is what let it through.
    assert shep.lifecycle_cues("done", ask)["reap_ready"] is True
    shep._NUDGE_STATE.clear()


def test_the_agents_own_close_reply_still_reaps() -> None:
    """Suppressing our echo must not suppress the answer we asked for."""
    shep._NUDGE_STATE.clear()
    target = "herdr:w9:p3"
    shep.remember_nudge(
        shep._nudge_state(target), "SAFE_TO_CLOSE: say why nothing is left hanging."
    )

    cues = shep.lifecycle_cues(
        "done",
        "SAFE_TO_CLOSE: say why nothing is left hanging.\n"
        "SAFE_TO_CLOSE: MR !66 is green and nothing is left hanging.\n",
        target=target,
    )
    assert cues["reap_ready"] is True
    assert cues["reap_reason"] == (
        "SAFE_TO_CLOSE: MR !66 is green and nothing is left hanging."
    )
    shep._NUDGE_STATE.clear()


def test_a_repeating_key_cannot_reap_the_same_pane_twice(monkeypatch) -> None:
    """One held key produced 138 closes on a single pane; the debounce ends that."""
    shep._REAPED.clear()
    calls = []
    monkeypatch.setattr(shep, "_run", lambda argv, **_k: calls.append(argv) or SimpleNamespace(
        returncode=0, stdout="closed", stderr=""))
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(shep, "remove_mission_worktree", lambda _cwd: (True, ""))
    row = {"source": "herdr", "target": "herdr:w1:p1"}

    assert shep.reap_session(row, audit=False) == (True, "closed")
    assert shep.reap_session(row, audit=False) == (True, "already closed")
    assert len(calls) == 1, "the second press must not reach the transport"

    # The window is short on purpose: herdr reuses pane ids for new sessions.
    shep._REAPED["herdr:w1:p1"] = time.time() - shep.REAP_DEBOUNCE_SECONDS - 1
    assert shep.reap_session(row, audit=False) == (True, "closed")
    assert len(calls) == 2
    shep._REAPED.clear()


def test_close_memory_outlives_a_pane_missing_from_one_listing(tmp_path) -> None:
    """Losing close_requested re-arms the ask, which is the bug it exists to stop."""
    shep._NUDGE_STATE.clear()
    asked = shep._nudge_state("herdr:w1:p1")
    asked["close_requested"] = True
    shep._nudge_state("herdr:w1:p2")["attempt"] = 2
    path = tmp_path / "state.json"

    # Neither pane is in this pass's listing.
    assert shep.save_nudge_state(set(), path=path) is True
    saved = json.loads(path.read_text())["nudge"]

    assert "herdr:w1:p1" in saved, "an asked pane must remember it was asked"
    assert saved["herdr:w1:p1"]["close_requested"] is True
    assert "herdr:w1:p2" not in saved, "everything else is still garbage collected"
    shep._NUDGE_STATE.clear()


def test_reap_session_uses_owning_transport(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="closed", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    assert shep.reap_session(
        {"source": "herdr", "target": "herdr:w1:p1"}
    ) == (True, "closed")
    assert calls[0][-2:] == ["close", "herdr:w1:p1"]


def test_reap_removes_the_mission_worktree_so_it_can_relaunch(
    tmp_path, monkeypatch
) -> None:
    """Mission ids are deterministic — an orphaned worktree blocks it forever."""
    root = tmp_path / "qa-worktrees"
    worktree = root / "macdaddy" / "mission-macdaddy-f5be3807"
    worktree.mkdir(parents=True)
    monkeypatch.setattr(shep, "QA_WORKTREE_ROOT", root)
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="closed", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    ok, detail = shep.reap_session(
        {"source": "herdr", "target": "herdr:w1:p1", "cwd": str(worktree)}
    )

    assert ok
    assert "worktree removed: mission-macdaddy-f5be3807" in detail
    assert calls[-1] == [
        "git", "-C", str(worktree), "worktree", "remove", "--force", str(worktree)
    ]


def test_reap_never_removes_a_primary_checkout(tmp_path, monkeypatch) -> None:
    """The single guard that keeps a reap from deleting a real repo."""
    monkeypatch.setattr(shep, "QA_WORKTREE_ROOT", tmp_path / "qa-worktrees")
    primary = tmp_path / "forge-repos" / "macdaddy"
    primary.mkdir(parents=True)
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="closed", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    ok, detail = shep.reap_session(
        {"source": "herdr", "target": "herdr:w1:p1", "cwd": str(primary)}
    )

    assert (ok, detail) == (True, "closed")
    assert not any("worktree" in argument for call in calls for argument in call)
    assert primary.exists()


def test_reap_reports_a_worktree_it_could_not_remove(tmp_path, monkeypatch) -> None:
    """Silence here would look like a clean reap and leave the mission blocked."""
    root = tmp_path / "qa-worktrees"
    worktree = root / "macdaddy" / "mission-1"
    worktree.mkdir(parents=True)
    monkeypatch.setattr(shep, "QA_WORKTREE_ROOT", root)

    def fake_run(argv, **_kwargs):
        if argv[0] == "git":
            return SimpleNamespace(returncode=1, stdout="", stderr="locked worktree")
        return SimpleNamespace(returncode=0, stdout="closed", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    ok, detail = shep.reap_session(
        {"source": "herdr", "target": "herdr:w1:p1", "cwd": str(worktree)}
    )

    assert ok
    assert "worktree kept: locked worktree" in detail


def test_failed_reap_leaves_the_worktree_alone(tmp_path, monkeypatch) -> None:
    """The pane is still alive — removing its worktree would destroy live work."""
    root = tmp_path / "qa-worktrees"
    worktree = root / "macdaddy" / "mission-1"
    worktree.mkdir(parents=True)
    monkeypatch.setattr(shep, "QA_WORKTREE_ROOT", root)
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=1, stdout="", stderr="pane busy")

    monkeypatch.setattr(shep, "_run", fake_run)

    ok, _detail = shep.reap_session(
        {"source": "herdr", "target": "herdr:w1:p1", "cwd": str(worktree)}
    )

    assert not ok
    assert not any(call[0] == "git" for call in calls)


def test_spawn_continuation_starts_fresh_herdr_session(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="started", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)
    monkeypatch.setattr(shep, "_continuation_command", lambda _row: "claude")
    row = {
        "source": "herdr",
        "label": "claude",
        "workspace_id": "w1",
        "cwd": "/tmp/project",
    }

    assert shep.spawn_continuation(row, "Audit the next subsystem.") == (
        True,
        "started",
    )
    argv = calls[0]
    assert argv[2:4] == ["session", "start"]
    assert argv[argv.index("--space") + 1] == "w1"
    assert argv[argv.index("--prompt") + 1] == "Audit the next subsystem."


def test_safe_addstr_clips_wide_status_text_to_terminal_columns() -> None:
    screen = _WidthCheckingScreen(width=12)

    shep.safe_addstr(
        screen,
        0,
        0,
        "sent: ✅ accepted",
        curses.A_DIM,
        max_width=11,
    )

    assert screen.rendered.startswith("sent: ✅")
    assert _display_width(screen.rendered) <= 11


def test_table_layout_uses_readable_responsive_columns() -> None:
    for width in (40, 59, 60, 79, 109, 110, 140):
        layout = shep.table_layout(width)
        rendered, _positions = shep.format_table_line(
            layout,
            {
                "source": "herdr",
                "session": "mission-long-session-name",
                "status": "REAP READY",
                "nudge": "READY: Continue with verification and commit.",
                "activity": "READY: Continue with verification and commit.",
                "repo": "project",
            },
        )
        assert _display_width(rendered) == width

    assert "repo" not in {key for key, _label, _width in shep.table_layout(109)}
    assert "repo" in {key for key, _label, _width in shep.table_layout(110)}


def test_narrow_layouts_still_show_activity_from_the_real_row_values() -> None:
    """The render site must fill every layout's activity column, whatever its key.

    This asserts against table_row_values (what the TUI actually passes) rather
    than a hand-written dict — feeding both keys by hand is what let the narrow
    layouts render a blank context column unnoticed.
    """
    row = {"source": "herdr", "id": "s1", "cwd": "/tmp/mb-mgmt", "context": "running tests"}
    # Distinctive short token: must not collide with any other column's text,
    # and must survive truncation into the narrowest (width 40) activity cell.
    activity = "CTXTOKEN running tests"
    for width in (40, 59, 60, 79, 109, 110, 140):
        layout = shep.table_layout(width)
        source_visible = any(key == "source" for key, _label, _width in layout)
        rendered, _positions = shep.format_table_line(
            layout,
            shep.table_row_values(row, activity, "REAP READY", source_visible=source_visible),
        )
        activity_keys = {key for key, _label, _width in layout} & {"activity", "nudge"}
        assert activity_keys, f"width {width} has no activity column at all"
        assert "CTXTOKEN" in rendered, f"width {width} rendered a blank activity cell"


# The SESSION column used to render the agent badge, which is near-constant
# across a fleet — measured live, 21 of 22 panes showed the identical
# "[CL] claude", so the column said nothing about WHICH session you were
# looking at. The herdr tab label was collected but never displayed.

def test_session_column_shows_the_tab_label_not_the_agent() -> None:
    row = {
        "source": "herdr", "id": "%1", "cwd": "/tmp/shep",
        "label": "claude",                    # the agent
        "session_label": "mr conflicts",      # the herdr tab
    }
    values = shep.table_row_values(row, "ctx", "idle")
    assert values["session"] == "mr conflicts"
    assert values["agent"] == "[CL] claude"


def test_session_falls_back_to_the_agent_when_a_pane_has_no_tab_label() -> None:
    # tmux panes carry no herdr tab label; the cell must never render empty.
    row = {"source": "tmux", "id": "%9", "cwd": "/tmp/repo", "label": "mb"}
    assert shep.table_row_values(row, "ctx", "idle")["session"] == "mb"
    assert shep.session_name({"source": "tmux", "id": "%9"}) == ""
    assert shep.table_row_values(
        {"source": "tmux", "id": "%9", "cwd": "/tmp/repo"}, "ctx", "idle"
    )["session"] == "-"


def test_session_sits_immediately_left_of_the_nudge() -> None:
    keys = [key for key, _label, _width in shep.table_layout(140)]
    assert keys.index("session") == keys.index("activity") - 1


def test_nudge_absorbs_extra_width_instead_of_repo() -> None:
    """REPO used to take every leftover column.

    On a 200-wide terminal that meant ~110 characters of whitespace trailing a
    13-character repo name while the nudge text stayed clipped at 42.
    """
    def widths(width):
        return {key: w for key, _label, w in shep.table_layout(width)}

    narrow, wide = widths(110), widths(200)
    assert wide["repo"] == narrow["repo"], "repo must be fixed width"
    assert wide["activity"] - narrow["activity"] == 90, "nudge takes the growth"
    # And the repo column stays small enough to be a name, not a gutter.
    assert wide["repo"] <= 16


def test_repo_and_activity_summary_keep_full_paths_out_of_the_table() -> None:
    assert shep.repo_name("/workspaces/searchatlas-eng/mb-mgmt/") == "mb-mgmt"
    assert shep.repo_name("-") == "-"
    assert shep.pane_context_summary("\x1b[31mworking on focused test\x1b[0m\n") == (
        "working on focused test"
    )
    assert shep.table_activity_text(
        {"context": "running focused tests"}, "-"
    ) == "running focused tests"
    assert shep.table_activity_text(
        {"context": "running focused tests"}, "READY: Continue"
    ) == "READY: Continue · running focused tests"


def test_table_line_has_separators_and_terminal_safe_ellipsis() -> None:
    layout = shep.table_layout(80)
    rendered, positions = shep.format_table_line(
        layout,
        {
            "source": "herdr",
            "session": "✅ very long session name",
            "status": "working",
            "nudge": "READY: a deliberately long instruction that must be clipped cleanly",
        },
    )

    assert rendered.count(shep.TABLE_SEPARATOR) == len(layout) - 1
    assert _display_width(rendered) == 80
    assert "…" in rendered
    assert positions["nudge"][0] > positions["status"][0]


def test_table_row_at_y_maps_clicks_through_scroll_offset() -> None:
    assert shep.table_row_at_y(5, top=7, table_height=5, row_count=20) == 7
    assert shep.table_row_at_y(9, top=7, table_height=5, row_count=20) == 11
    assert shep.table_row_at_y(4, top=7, table_height=5, row_count=20) is None
    assert shep.table_row_at_y(10, top=7, table_height=5, row_count=20) is None


def test_mouse_selection_uses_primary_click_and_respects_table_bounds() -> None:
    assert shep.mouse_selected_row(
        7, curses.BUTTON1_CLICKED, top=3, table_height=5, row_count=20
    ) == 5
    assert shep.mouse_selected_row(
        7, curses.BUTTON3_CLICKED, top=3, table_height=5, row_count=20
    ) is None


def test_shep_tab_hit_testing_routes_only_primary_clicks() -> None:
    assert shep.mouse_tab_target(
        2, shep.SHEP_TAB_Y, curses.BUTTON1_CLICKED, 80
    ) == "agents"
    assert shep.mouse_tab_target(
        15, shep.SHEP_TAB_Y, curses.BUTTON1_CLICKED, 80
    ) == "beads"
    assert shep.mouse_tab_target(
        30, shep.SHEP_TAB_Y, curses.BUTTON1_CLICKED, 80
    ) == "missions"
    assert shep.mouse_tab_target(
        15, shep.SHEP_TAB_Y, curses.BUTTON3_CLICKED, 80
    ) is None
    assert shep.mouse_tab_target(
        15, shep.SHEP_TAB_Y - 1, curses.BUTTON1_CLICKED, 80
    ) is None


def _beads_tree(tmp_path, **repos):
    """Build a fake forge-repos tree; each value is a list of raw JSONL lines."""
    for name, lines in repos.items():
        beads_dir = tmp_path / "group" / name / ".beads"
        beads_dir.mkdir(parents=True)
        if lines is not None:
            (beads_dir / "issues.jsonl").write_text("\n".join(lines) + "\n")
    return tmp_path


def _issue(id_, status="open", priority=1, **over):
    return json.dumps(
        {"id": id_, "title": f"{id_} title", "status": status, "priority": priority, **over}
    )


@pytest.fixture(autouse=True)
def _clear_beads_repo_cache():
    """The repo scan is TTL-cached module-wide; a stale entry would leak between tests."""
    shep._BEADS_REPO_CACHE.update(at=0.0, repos=[])
    with shep._BEADS_VIEW_LOCK:
        shep._BEADS_VIEW_CACHE.update(
            beads=None, error=None, missions=None, prune={},
            triage_note="triage pending", at=0.0,
        )
    yield
    shep._BEADS_REPO_CACHE.update(at=0.0, repos=[])
    with shep._BEADS_VIEW_LOCK:
        shep._BEADS_VIEW_CACHE.update(
            beads=None, error=None, missions=None, prune={},
            triage_note="triage pending", at=0.0,
        )


def _use_tree(monkeypatch, root):
    monkeypatch.setattr(shep, "BEADS_ROOT", root)


def test_discover_finds_every_repo_holding_beads(monkeypatch, tmp_path) -> None:
    """The curated 4-repo file hid 60 real workspaces; discovery is by scan now."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")], beta=[_issue("b-1")])
    _use_tree(monkeypatch, root)

    found = shep.discover_beads_repos()

    assert sorted(Path(r).name for r in found) == ["alpha", "beta"]


def test_discover_never_descends_into_a_repo(monkeypatch, tmp_path) -> None:
    """Without the early return this walks node_modules and takes minutes."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    nested = root / "group" / "alpha" / "node_modules" / "pkg" / ".beads"
    nested.mkdir(parents=True)
    (nested / "issues.jsonl").write_text(_issue("junk-1") + "\n")
    _use_tree(monkeypatch, root)

    found = shep.discover_beads_repos()

    assert [Path(r).name for r in found] == ["alpha"]


def test_discover_caches_the_scan_because_it_dominates_a_load(monkeypatch, tmp_path) -> None:
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    _use_tree(monkeypatch, root)
    shep.discover_beads_repos()

    _beads_tree(root / "later", beta=[_issue("b-1")])

    assert [Path(r).name for r in shep.discover_beads_repos()] == ["alpha"]


def test_load_beads_reads_every_repo_priority_first(monkeypatch, tmp_path) -> None:
    root = _beads_tree(
        tmp_path,
        alpha=[_issue("a-1", priority=2)],
        beta=[_issue("b-1", priority=0)],
    )
    _use_tree(monkeypatch, root)

    beads, error = shep.load_beads()

    assert error is None
    assert [(b["repo"], b["id"]) for b in beads] == [("beta", "b-1"), ("alpha", "a-1")]


def test_load_beads_counts_a_twice_cloned_repo_once(monkeypatch, tmp_path) -> None:
    """linkgraph-static is checked out under two group dirs, so the same bead was
    listed twice under an identical repo label. Keep the freshest record only."""
    for group, updated in (("linkgraph", "2026-07-01T00:00:00Z"), ("web-dev", "2026-08-01T00:00:00Z")):
        beads_dir = tmp_path / group / "dup-repo" / ".beads"
        beads_dir.mkdir(parents=True)
        (beads_dir / "issues.jsonl").write_text(
            _issue("d-1", updated_at=updated, title=f"from {group}") + "\n"
        )
    _use_tree(monkeypatch, tmp_path)

    beads, error = shep.load_beads()

    assert error is None
    assert [(b["repo"], b["id"]) for b in beads] == [("dup-repo", "d-1")]
    assert beads[0]["title"] == "from web-dev"  # the stale checkout must lose


def test_load_beads_never_shells_out_to_bd(monkeypatch, tmp_path) -> None:
    """One `bd` call spins an embedded Dolt DB (~1s); 64 of them is a minute."""
    _use_tree(monkeypatch, _beads_tree(tmp_path, alpha=[_issue("a-1")]))
    monkeypatch.setattr(
        shep, "_run", lambda *_a, **_k: pytest.fail("load_beads must not spawn a subprocess")
    )

    beads, _error = shep.load_beads()

    assert [b["id"] for b in beads] == ["a-1"]


def test_load_beads_shows_only_work_that_is_still_open(monkeypatch, tmp_path) -> None:
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1", status="open"),
        _issue("a-2", status="in_progress"),
        _issue("a-3", status="closed"),
    ])
    _use_tree(monkeypatch, root)

    beads, _error = shep.load_beads()

    assert sorted(b["id"] for b in beads) == ["a-1", "a-2"]


def test_load_beads_skips_a_bad_line_without_losing_the_repo(monkeypatch, tmp_path) -> None:
    """One corrupt row must not blank out the other 700 beads."""
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1"), "{not json", "", _issue("a-2"),
    ])
    _use_tree(monkeypatch, root)

    beads, error = shep.load_beads()

    assert sorted(b["id"] for b in beads) == ["a-1", "a-2"]
    assert error is None


def test_bead_age_reads_every_stamp_shape_the_export_emits() -> None:
    now = 1_800_000_000.0
    day = 86400.0
    assert shep.bead_age("2026-09-12T18:04:11.123456Z", now=now) == shep.compact_age(
        now - datetime.datetime(
            2026, 9, 12, 18, 4, 11, 123456, tzinfo=datetime.timezone.utc
        ).timestamp()
    )
    stamp = datetime.datetime.fromtimestamp(now - 3 * day, datetime.timezone.utc)
    assert shep.bead_age(stamp.isoformat().replace("+00:00", "Z"), now=now) == "3d"
    assert shep.bead_age(stamp.isoformat(), now=now) == "3d"  # +00:00 offset
    assert shep.bead_age(
        stamp.replace(microsecond=0).isoformat().replace("+00:00", ""), now=now
    ) == "3d"  # no fraction, no offset -> assumed UTC


def test_bead_age_says_question_mark_rather_than_inventing_a_zero() -> None:
    for value in ("", "   ", None, "not-a-date", "2026-13-45T99:99:99Z", 17):
        assert shep.bead_age(value, now=1_800_000_000.0) == "?"


def test_read_repo_beads_carries_created_at_alongside_updated_at(tmp_path) -> None:
    beads_dir = tmp_path / "alpha" / ".beads"
    beads_dir.mkdir(parents=True)
    beads_dir.joinpath("issues.jsonl").write_text(
        _issue("a-1", created_at="2026-09-01T00:00:00Z",
               updated_at="2026-09-27T00:00:00Z") + "\n"
        + _issue("a-2") + "\n"
    )

    rows, error = shep.read_repo_beads(tmp_path / "alpha")

    assert error is None
    by_id = {row["id"]: row for row in rows}
    assert by_id["a-1"]["created_at"] == "2026-09-01T00:00:00Z"
    assert by_id["a-1"]["updated_at"] == "2026-09-27T00:00:00Z"
    assert by_id["a-2"]["created_at"] == ""  # absent stamp must not KeyError


def test_bead_row_shows_both_ages_before_the_title() -> None:
    now = time.time()
    created = datetime.datetime.fromtimestamp(
        now - 14 * 86400, datetime.timezone.utc
    ).isoformat().replace("+00:00", "Z")
    updated = datetime.datetime.fromtimestamp(
        now - 3 * 86400, datetime.timezone.utc
    ).isoformat()

    line = shep.bead_row({
        "repo": "alpha", "id": "a-1", "status": "open", "priority": 2,
        "title": "fix the thing", "created_at": created, "updated_at": updated,
    })

    assert "c:14d u:3d" in line
    assert line.index("c:14d") < line.index("fix the thing")


def test_bead_row_renders_a_bead_with_no_timestamps_at_all() -> None:
    line = shep.bead_row(
        {"repo": "alpha", "id": "a-1", "status": "open", "priority": 2, "title": "t"},
        prune_reason="stale",
    )

    assert "c:? u:?" in line
    assert line.endswith("· PRUNE: stale")


def test_beads_message_appends_the_freshest_update_age() -> None:
    now = 1_800_000_000.0
    updated = datetime.datetime.fromtimestamp(
        now - 3 * 3600, datetime.timezone.utc
    ).isoformat().replace("+00:00", "Z")
    beads = [
        {"repo": "alpha", "updated_at": "2020-01-01T00:00:00Z"},
        {"repo": "beta", "updated_at": updated},
    ]

    assert shep._beads_message(beads, None, now=now) == (
        "2 open beads across 2 repos · newest update 3h ago"
    )
    assert shep._beads_message(
        [{"repo": "alpha", "updated_at": ""}], None, now=now
    ) == "1 open beads across 1 repos"
    assert shep._beads_message(beads, "boom", now=now) == "boom"


def test_load_beads_skips_rows_missing_required_fields(monkeypatch, tmp_path) -> None:
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1"),
        json.dumps({"id": "a-2", "status": "open", "priority": 1}),      # no title
        json.dumps({"id": "", "title": "t", "status": "open", "priority": 1}),
        json.dumps({"id": "a-4", "title": "t", "status": "open", "priority": True}),
    ])
    _use_tree(monkeypatch, root)

    beads, _error = shep.load_beads()

    assert [b["id"] for b in beads] == ["a-1"]


def test_load_beads_tolerates_a_repo_with_no_export_yet(monkeypatch, tmp_path) -> None:
    """A .beads/ without issues.jsonl is a fresh workspace, not an error."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")], beta=None)
    _use_tree(monkeypatch, root)

    beads, error = shep.load_beads()

    assert [b["id"] for b in beads] == ["a-1"]
    assert error is None


def test_load_beads_keeps_healthy_repos_when_one_repo_fails(monkeypatch, tmp_path) -> None:
    """One unreadable workspace must not blank the whole fleet-wide list."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")], beta=[_issue("b-1")])
    _use_tree(monkeypatch, root)
    real_open = open

    def flaky_open(path, *a, **k):
        if "beta" in str(path):
            raise OSError(13, "Permission denied")
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", flaky_open)

    beads, error = shep.load_beads()

    assert [b["id"] for b in beads] == ["a-1"]
    assert "beta" in error and "Permission denied" in error


def test_load_beads_reports_a_root_with_no_repos(monkeypatch, tmp_path) -> None:
    _use_tree(monkeypatch, tmp_path)

    beads, error = shep.load_beads()

    assert beads == []
    assert "no repos with a .beads/ found" in error


def test_load_beads_is_unlimited_by_default(monkeypatch, tmp_path) -> None:
    """The point of the tab is to see everything; a silent cap would hide work."""
    root = _beads_tree(tmp_path, alpha=[_issue(f"a-{i}") for i in range(60)])
    _use_tree(monkeypatch, root)

    beads, _error = shep.load_beads()

    assert len(beads) == 60
    assert len(shep.load_beads(limit=10)[0]) == 10


# --- Bead missions ----------------------------------------------------------


def _delivery(monkeypatch, tmp_path, *repos):
    """Point the delivery allowlist at `repos` and stub the git probes it makes."""
    listing = tmp_path / "delivery-repos.txt"
    listing.write_text("\n".join(str(repo) for repo in repos) + "\n")
    monkeypatch.setattr(shep, "MISSION_REPOS_FILE", listing)

    def fake_run(cmd, **_kw):
        # launchable_repos probes rev-parse; repo_default_branch probes
        # origin/HEAD and then a local develop.
        if "symbolic-ref" in cmd:
            return SimpleNamespace(returncode=0, stdout="origin/main\n", stderr="")
        if "--verify" in cmd:  # no local develop in these fixtures
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout=".git\n", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)
    return listing


def _dep(depends_on, type_="blocks"):
    return {"issue_id": "x", "depends_on_id": depends_on, "type": type_}


def test_a_ready_bead_becomes_a_mission_that_closes_it(monkeypatch, tmp_path) -> None:
    """The deck's first question is which open bead could be closed right now."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1", priority=0)])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    missions, error = shep.bead_missions()

    assert error is None
    assert [m["id"] for m in missions] == ["a-1"]
    assert missions[0]["bead_id"] == "a-1"
    assert shep.mission_kind_label(missions[0]) == "BEAD"


def test_a_blocked_bead_never_reaches_the_deck(monkeypatch, tmp_path) -> None:
    """Launching work whose blocker is still open just wastes a worktree."""
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1", dependencies=[_dep("a-2")]),
        _issue("a-2", status="open"),
    ])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    missions, _error = shep.bead_missions()

    assert [m["id"] for m in missions] == ["a-2"]


def test_a_closed_blocker_no_longer_holds_a_bead_back(monkeypatch, tmp_path) -> None:
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1", dependencies=[_dep("a-2")]),
        _issue("a-2", status="closed"),
    ])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    missions, _error = shep.bead_missions()

    assert [m["id"] for m in missions] == ["a-1"]


def test_belonging_to_an_open_epic_is_not_being_blocked(monkeypatch, tmp_path) -> None:
    """Most beads are children of an open epic; counting that as a blocker
    would empty the deck of nearly the whole backlog."""
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1", dependencies=[_dep("a-epic", type_="parent-child")]),
        _issue("a-epic", status="open"),
    ])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    missions, _error = shep.bead_missions()

    assert "a-1" in [m["id"] for m in missions]


def test_a_blocker_we_cannot_see_does_not_hide_the_work(monkeypatch, tmp_path) -> None:
    """An edge into another repo's export is invisible here — treating it as
    blocking would silently drop real, launchable work."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1", dependencies=[_dep("other-9")])])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    missions, _error = shep.bead_missions()

    assert [m["id"] for m in missions] == ["a-1"]


def test_bead_missions_come_only_from_the_delivery_repos(monkeypatch, tmp_path) -> None:
    """SAFETY INVARIANT: these write code, and the repos file is the only guard."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")], product=[_issue("p-1", priority=0)])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    missions, _error = shep.bead_missions()

    assert [m["id"] for m in missions] == ["a-1"]


def test_the_bead_deck_leads_with_the_highest_priority_work(monkeypatch, tmp_path) -> None:
    root = _beads_tree(
        tmp_path,
        alpha=[_issue("a-1", priority=3)],
        beta=[_issue("b-1", priority=0)],
    )
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha", root / "group" / "beta")

    missions, _error = shep.bead_missions()

    assert [m["id"] for m in missions] == ["b-1", "a-1"]
    assert missions[0]["momentum_score"] > missions[1]["momentum_score"]
    assert missions[-1]["momentum_score"] > shep.MISSION_MIN_SCORE


def test_a_bead_mission_satisfies_the_launch_goal_contract(monkeypatch, tmp_path) -> None:
    """launch.py rejects a goal_mode mission that misses any of these, so a
    bead mission that drifts from them is a mission that can never start."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    mission = shep.bead_missions()[0][0]

    assert mission["goal_mode"] is True
    assert mission["santa_required"] is True
    assert mission["goal_runtime"] == "codex-gw"
    assert set(mission["required_skills"]) >= {
        "mission-launch", "herdr", "goal-mode", "sdlc-protocol", "santa-method",
    }
    assert mission["id"] in mission["goal_condition"]
    assert mission["launch_spec"].strip()


def test_a_bead_mission_is_not_done_until_the_bead_is_closed(monkeypatch, tmp_path) -> None:
    """Shipping the code and leaving the bead open puts the deck straight back
    where it started, so closing it is part of the exit, not a nicety."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    mission = shep.bead_missions()[0][0]
    exit_line = mission["launch_spec"].split("### Exit Condition\n")[1].splitlines()[0]

    assert "a-1" in exit_line and "CLOSED" in exit_line
    assert "bd close a-1" in mission["launch_spec"]
    assert "close a-1" in mission["goal_condition"]


def test_a_long_bead_description_cannot_blow_the_goal_budget(monkeypatch, tmp_path) -> None:
    """launch.py submits the spec inside one native `/goal`, which Claude caps at
    4000 characters. Over the line the goal never registers and the launcher dies
    *after* creating a bead, a worktree and a pane — so the bead's own prose is
    trimmed to fit, and the parts the mission exists for are never what is cut."""
    root = _beads_tree(tmp_path, alpha=[
        _issue("a-1", description="D" * 9000, acceptance_criteria="C" * 9000),
    ])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    mission = shep.bead_missions()[0][0]

    assert len(mission["launch_spec"]) <= shep.BEAD_SPEC_MAX_CHARS
    assert "### Exit Condition" in mission["launch_spec"]
    assert "bd close a-1" in mission["launch_spec"]


def test_a_bead_spec_does_not_restate_the_launcher_s_own_contract(
    monkeypatch, tmp_path
) -> None:
    """launch.py injects the skills list, the guarded builder lane, dual Santa
    review and the credential-safety protocol into this same prompt. Saying it
    twice bought nothing and cost the budget that broke every launch."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    spec = shep.bead_missions()[0][0]["launch_spec"]

    assert "### Execution Contract" not in spec
    assert "santa-method" not in spec


def test_the_goal_runtime_follows_the_launcher_s_gateway_override() -> None:
    """A pool-wide 429 on codex-gw kills every launch at /goal registration, and
    launch.py exposes MISSION_GOAL_ROUTER_RUNTIME to point the fleet at a healthy
    gateway. launch.py rejects a mission whose goal_runtime disagrees with it, so
    shep hardcoding the default made it the one thing that could not follow.

    Read in a subprocess because the constant is resolved at import, exactly as
    launch.py resolves its own — reloading the module here would disturb the
    caches every other test shares.
    """
    read = (
        "import sys; sys.path.insert(0, '.'); from scripts import shep; "
        "print(shep.BEAD_GOAL_RUNTIME)"
    )
    root = str(Path(__file__).resolve().parent.parent)

    def runtime(value):
        env = {**os.environ, "MISSION_GOAL_ROUTER_RUNTIME": value}
        return subprocess.run(
            [sys.executable, "-c", read], cwd=root, env=env,
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    assert runtime("kimi-gw") == "kimi-gw"
    assert runtime("") == "codex-gw"  # unset falls back, never to an empty runtime


def test_a_bead_mission_never_sends_the_agent_to_a_worktree_for_beads(
    monkeypatch, tmp_path
) -> None:
    """The Beads database lives in the primary checkout; `bd close` run inside
    the mission's worktree finds no database and the bead stays open."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")

    spec = shep.bead_missions()[0][0]["launch_spec"]

    assert "primary checkout" in spec


def test_a_full_bead_deck_skips_the_expensive_sense_sweep(
    monkeypatch, tmp_path
) -> None:
    """sense.py shells out to bd/git per repo (~2 min); with the deck already
    full of real closable work, running it buys nothing.

    Spread across enough repos to actually fill the deck. One repo cannot any
    more: MISSION_DECK_PER_PROJECT caps each project's share, so a single
    backlog with twelve ready beads now yields three and leaves the rest of the
    deck to the other sources — which is the point of the cap, and means "full"
    has to mean full of *varied* work for this test to be testing anything.
    """
    per_repo = shep.MISSION_DECK_PER_PROJECT
    repos = {
        f"repo{n}": [
            _issue(f"r{n}-{i}", priority=0) for i in range(per_repo)
        ]
        for n in range(shep.MISSION_DECK_TOP // per_repo)
    }
    root = _beads_tree(tmp_path, **repos)
    _delivery(monkeypatch, tmp_path, *[root / "group" / name for name in repos])
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda *a, **k: pytest.fail("a full bead deck must not run sense/recommend"),
    )

    missions, error = shep.load_mission_deck(force=True)

    assert error is None
    assert len(missions) == shep.MISSION_DECK_TOP
    assert all(m.get("bead_id") for m in missions)


def test_one_busy_backlog_cannot_take_the_whole_deck(monkeypatch, tmp_path) -> None:
    """The live deck sat at five bug-hunter beads for days.

    bead_missions sorts every repo's ready beads into one global list and slices
    the top N, so a single backlog with enough ready work took every slot — and
    because the build and research top-ups only run when beads leave room, it
    also silently suppressed both other sources. Capping each project's share is
    what leaves that room.
    """
    root = _beads_tree(
        tmp_path,
        busy=[_issue(f"b-{i}", priority=0) for i in range(shep.MISSION_DECK_TOP)],
        quiet=[_issue("q-1", priority=1)],
    )
    _delivery(
        monkeypatch, tmp_path,
        root / "group" / "busy", root / "group" / "quiet",
    )

    missions, _error = shep.bead_missions(shep.MISSION_DECK_TOP)

    from_busy = [m for m in missions if m["bead_id"].startswith("b-")]
    assert len(from_busy) == shep.MISSION_DECK_PER_PROJECT
    # The lower-priority bead from the quiet repo still gets a slot, which is
    # the whole benefit: without the cap it never appeared at all.
    assert any(m["bead_id"] == "q-1" for m in missions)


def test_beads_outrank_inferred_build_missions_on_the_same_repo(
    monkeypatch, tmp_path
) -> None:
    """A written-down bead beats a next step sense.py guessed at, and the repo
    must not occupy two slots for the same work."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1")])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda repos, mode, top, min_score=None: (
            ([{"id": "guessed", "project_name": "alpha"}], None)
            if mode == "implementation" else ([], None)
        ),
    )

    missions, _error = shep.load_mission_deck(force=True)

    assert [m["id"] for m in missions] == ["a-1"]


def test_an_empty_bead_backlog_is_not_reported_as_an_error(
    monkeypatch, tmp_path
) -> None:
    """"No ready beads" is the steady state of a healthy backlog; banner-ing it
    would make a working deck look broken."""
    root = _beads_tree(tmp_path, alpha=[_issue("a-1", status="closed")])
    _delivery(monkeypatch, tmp_path, root / "group" / "alpha")
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda repos, mode, top, min_score=None: (
            ([{"id": "b1", "project_name": "alpha"}], None)
            if mode == "implementation" else ([], None)
        ),
    )

    missions, error = shep.load_mission_deck(force=True)

    assert error is None
    assert [m["id"] for m in missions] == ["b1"]


def test_commander_header_is_branded_counted_and_cell_safe() -> None:
    rows = [
        {"status": "working"},
        {"status": "idle"},
        {"status": "stalled"},
        {"status": "done", "reap_ready": True},
    ]

    header = shep.commander_header(rows, 80, refresh_age=3)

    assert len(header) == 3
    assert all(_display_width(line) == 80 for line in header)
    assert "COMMANDER M" in header[0]
    assert "FLEET 04" in header[1]
    assert "RUN 01" in header[1]
    assert "ALERT 01" in header[1]
    assert "REAP 01" in header[1]


def test_ascii_mode_removes_decorative_unicode_but_keeps_meaning() -> None:
    rows = [{"status": "working"}, {"status": "error"}]
    header = shep.commander_header(rows, 48, ascii_only=True)
    rendered, _ = shep.format_table_line(
        shep.table_layout(48),
        {
            "session": "worker",
            "status": shep.status_badge(rows[0], True),
            "nudge": "ready",
        },
        ascii_only=True,
    )

    assert "[M] COMMANDER M" in header[0]
    assert all(line.isascii() for line in header)
    assert rendered.isascii()
    assert "[WORKING]" in rendered
    assert shep.panel_rule("CONTEXT · worker — ready", 48, True).isascii()
    assert shep.command_footer(80, message="done … ✓", ascii_only=True).isascii()
    assert shep._ascii_text("pane says … ‘ready’ ✓").isascii()


def test_ascii_mode_can_be_requested_or_inferred_from_limited_term() -> None:
    assert shep.use_ascii_ui({"SHEP_ASCII": "1", "TERM": "xterm"})
    assert shep.use_ascii_ui({"TERM": "dumb"})
    assert not shep.use_ascii_ui({"TERM": "xterm-256color"})


def test_status_badges_are_semantic_without_color() -> None:
    assert "WORKING" in shep.status_badge({"status": "working"})
    assert "IDLE" in shep.status_badge({"status": "idle"})
    assert "ATTENTION" in shep.status_badge({"status": "stalled"})
    assert "ERROR" in shep.status_badge({"status": "error"})
    assert "LIVE RO" in shep.status_badge({"status": "live-ro"})
    assert "REAP READY" in shep.status_badge(
        {"status": "done", "reap_ready": True}
    )


def test_panel_rule_fits_narrow_terminal() -> None:
    for ascii_only in (False, True):
        line = shep.panel_rule("CONTEXT / worker", 40, ascii_only)
        assert _display_width(line) == 40


def test_narrow_header_and_footer_keep_critical_information() -> None:
    rows = [
        {"status": "working"},
        {"status": "idle"},
        {"status": "stalled"},
        {"status": "done", "reap_ready": True},
    ]
    header = shep.commander_header(rows, 39)
    footer = shep.command_footer(39)

    assert all(_display_width(line) == 39 for line in header)
    assert all(
        label in header[1]
        for label in ("FLEET04", "RUN01", "IDLE02", "!01", "REAP01")
    )
    assert _display_width(footer) == 39
    assert all(key in footer for key in ("[j/k]", "[n]", "[r]", "[q]"))


def test_command_footer_advertises_intent_direction_when_space_allows() -> None:
    assert "[i] intent" in shep.command_footer(120)


def test_command_footer_advertises_mouse_selection_when_space_allows() -> None:
    assert "[click]" in shep.command_footer(120)


def test_command_footer_advertises_answering_when_space_allows() -> None:
    assert "[A] answer" in shep.command_footer(160)
    assert "[i] intent" in shep.command_footer(120)  # never at the cost of the old keys


def test_medium_widths_never_clip_counters_or_core_keys() -> None:
    rows = [
        {"status": "working"},
        {"status": "idle"},
        {"status": "stalled"},
        {"status": "done", "reap_ready": True},
    ]
    for width in (60, 61, 69, 70, 79):
        header = shep.commander_header(rows, width)
        footer = shep.command_footer(width, safe=2, held=1, drafting=1)

        assert all(label in header[1] for label in ("FLEET", "RUN", "IDLE", "REAP"))
        assert all(key in footer for key in ("[j/k]", "[n]", "[r]", "[q]"))
        assert _display_width(footer) == width


def test_ascii_expansion_uses_rendered_segment_width() -> None:
    first = shep._ascii_text("…")
    second_x = shep._text_columns(first)

    assert first == "..."
    assert second_x == 3


def test_intent_candidate_enforces_claude_style_constraints() -> None:
    assert shep.validate_intent_candidate("Continue with the focused tests") == (
        "Continue with the focused tests"
    )
    assert shep.validate_intent_candidate("push it") == "push it"
    assert shep.validate_intent_candidate("Continue?") is None
    assert shep.validate_intent_candidate("Great work, continue") is None
    assert shep.validate_intent_candidate("one") is None
    # A normal multi-sentence engine draft is accepted; only over-length is not.
    assert shep.validate_intent_candidate(
        "Run the focused tests. Then push the branch."
    ) == "Run the focused tests. Then push the branch."
    assert shep.validate_intent_candidate("word " * 40) is None


def test_markdown_nudge_engine_reads_the_whole_fleet_state(monkeypatch) -> None:
    prompts = []

    def fake_run(args, **_kwargs):
        prompts.append(args[-1])
        # returncode included because the real subprocess.run always sets it.
        # Without it the stub only passed by riding the blanket `except
        # Exception`, so the test proved the prompt was rendered and then
        # silently exercised the crash path rather than the success path.
        return SimpleNamespace(stdout="NO_NUDGE", returncode=0)

    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(shep.subprocess, "run", fake_run)
    row = {"target": "worker", "label": "worker", "status": "stalled"}
    other = {
        "target": "reviewer", "label": "reviewer", "status": "idle",
        "context": "MR !42 is waiting for review",
    }

    shep.llm_draft_nudge(
        row,
        ["pytest failed in test_sessions.py"],
        stalled_for=900,
        fleet_rows=[row, other],
    )

    assert len(prompts) == 1
    prompt = prompts[0]
    assert prompt.startswith("# Shep nudge engine")
    assert '"target": "worker"' in prompt
    assert '"state": "stalled for 15 minutes"' in prompt
    assert "pytest failed in test_sessions.py" in prompt
    assert '"target": "reviewer"' in prompt
    assert "MR !42 is waiting for review" in prompt
    assert "Reuse exact files, commands, errors, and identifiers" in prompt
    assert "NO_NUDGE" in prompt
    assert "earlier nudge text as no usable work" in prompt
    assert "no later agent result" in prompt
    assert "no_visible_work" in prompt
    assert "starting with SAFE_TO_CLOSE" in prompt
    assert "never write that reason yourself" in prompt.lower()
    assert "CANONICAL NUDGE LEXICON" not in prompt
    assert "NEW_MISSION" not in prompt


def test_missing_markdown_nudge_engine_fails_closed(tmp_path) -> None:
    assert shep.load_nudge_engine(tmp_path / "missing.md") is None
    assert shep.render_nudge_engine_prompt(
        {"target": "worker", "status": "idle"},
        ["pytest failed"],
        engine_text="",
    ) is None


@pytest.mark.parametrize(
    ("status", "stalled_for", "expected"),
    [
        ("idle", None, "waiting"),
        ("done", None, "complete"),
        ("stalled", 900, "stalled for 15 minutes"),
    ],
)
def test_nudge_assessed_state_is_small_and_actionable(status, stalled_for, expected) -> None:
    assert shep.nudge_assessed_state({"status": status}, stalled_for) == expected


def test_read_only_verification_is_a_safe_continuation() -> None:
    assert shep.classify_risk(
        "Verify the strategy config imports after the package split."
    )[0] == "safe_continuation"


def test_grounded_run_and_inspect_instructions_are_safe_continuations() -> None:
    assert shep.classify_risk("Run pytest and inspect the first failure.")[0] == (
        "safe_continuation"
    )


def test_plain_language_push_instruction_requires_review() -> None:
    assert shep.classify_risk(
        "Push the two commits to the remote branch so review can proceed."
    )[0] == "push"


def test_operational_abstention_is_not_replaced_by_generic_nag() -> None:
    row = {"status": "idle"}
    recent = ["All work is complete."]

    assert shep.operational_candidate_or_fallback(
        "NO_NUDGE", row, recent
    ) is None
    assert shep.operational_candidate_or_fallback(None, row, recent) is None


def test_candidate_assessment_parses_scores_and_computes_winner() -> None:
    candidates = {
        "operational": "Continue with the regression test.",
        "intent": "Run the focused tests",
    }
    assessment = shep.parse_candidate_assessment(
        '{"scores":{"operational":81,"intent":74},"winner":"intent",'
        '"rationale":"Operational is more concrete."}',
        candidates,
    )

    assert assessment == {
        "scores": {"operational": 81, "intent": 74},
        "winner": "operational",
        "rationale": "Operational is more concrete.",
        "source": "model",
    }


def test_candidate_assessment_fallback_is_explainable_and_deterministic() -> None:
    candidates = {
        "operational": "Continue with the next task.",
        "intent": "Continue with the tests",
    }

    first = shep.fallback_candidate_assessment(candidates)
    second = shep.fallback_candidate_assessment(candidates)

    assert first == second
    assert first["winner"] == "intent"
    assert first["scores"] == {"operational": 72, "intent": 74}
    assert first["source"] == "fallback"
    assert first["rationale"]


def test_select_candidate_honors_explicit_choice_then_recommendation() -> None:
    candidates = {
        "operational": "Continue with the regression test.",
        "intent": "Run the focused tests",
    }
    assessment = {"winner": "operational"}

    assert shep.select_candidate(candidates, assessment) == (
        "operational", candidates["operational"]
    )
    assert shep.select_candidate(candidates, assessment, "intent") == (
        "intent", candidates["intent"]
    )
    assert shep.select_candidate(candidates, assessment, "unknown") == (
        None, None
    )


def test_select_candidate_abstains_below_quality_floor_unless_human_chooses() -> None:
    candidates = {
        "operational": "Before wrapping, run tests and merge this in.",
        "intent": None,
    }
    assessment = {
        "winner": "operational",
        "scores": {"operational": 62, "intent": 0},
    }

    assert shep.select_candidate(candidates, assessment) == (None, None)
    assert shep.select_candidate(
        candidates, assessment, requested="operational"
    ) == ("operational", candidates["operational"])


def test_bulk_nudge_candidates_holds_human_selected_low_quality_draft() -> None:
    row = {"target": "herdr:w1:p1", "status": "idle"}
    planned = {row["target"]: "Continue with generic wrap-up."}
    assessments = {
        row["target"]: {
            "scores": {"operational": 62, "intent": 0},
            "winner": "operational",
        }
    }

    candidates, held = shep.bulk_nudge_candidates(
        [row], planned, {}, assessments, {row["target"]: "operational"}
    )

    assert candidates == []
    assert held == 1


def test_bulk_send_never_merges_engine_candidates_or_bypasses_risk_gate() -> None:
    row = {
        "target": "herdr:w1:p1",
        "label": "candidate",
        "status": "idle",
        "context": "the regression test is next",
    }
    candidates = {
        "operational": "Continue with the regression test.",
        "intent": "Run the focused tests",
    }
    _engine, selected = shep.select_candidate(
        candidates, {"winner": "operational"}
    )

    sendable, held = shep.bulk_nudge_candidates(
        [row], {row["target"]: selected}, {}
    )
    assert sendable == [(row, candidates["operational"])]
    assert held == 0

    sendable, held = shep.bulk_nudge_candidates(
        [row], {row["target"]: "Email the customer now."}, {}
    )
    assert sendable == []
    assert held == 1


def test_clean_context_lines_drops_claude_code_statusline_chrome() -> None:
    """Regression: a CC status bar must never reach the nudge drafter — it
    produced `Saw: "⚠ 4 MCP servers need authentication ... ← 2 agents"`."""
    pane = (
        "I'm here — nothing running on my end.\n"
        "⚠ 4 MCP servers need authentication · run /mcp\n"
        "Opus 5 (1M context) | med | Search Atlas | ContextQ:--\n"
        "Eff:-- | 5h:4% ↻12:20a | 7d:15%\n"
        "▶▶ auto mode on (shift+tab to cycle) · ← 2 agents\n"
        "✻ Brewed for 11s"
    )

    lines = shep.clean_context_lines(pane)

    assert lines == ["I'm here — nothing running on my end."]


def test_clean_context_lines_drops_gateway_and_remote_mode_chrome() -> None:
    pane = (
        "codex-gw ▸ pool gpt-5.6-sol medium memory pilot\n"
        "for options\n"
        "Eff:--\n"
        "Opus 5 | med | mb-mgmt | 52% | ContextQ:--\n"
        "Press space (or Ctrl-T) to switch to local mode • Ctrl-C to exit\n"
    )

    assert shep.clean_context_lines(pane) == []


def test_clean_context_lines_keeps_real_output_near_statusline_numbers() -> None:
    pane = (
        "Ran 24 tests in 5s — all green\n"
        "fixed the auth regression in client.py"
    )

    lines = shep.clean_context_lines(pane)

    assert lines == [
        "Ran 24 tests in 5s — all green",
        "fixed the auth regression in client.py",
    ]


def test_selected_context_requests_the_full_session_view_scrollback(monkeypatch) -> None:
    captured = {}

    def fake_capture(source, target, lines, ansi):
        captured.update(source=source, target=target, lines=lines, ansi=ansi)
        return "recent session output\n"

    monkeypatch.setattr(shep, "capture_pane", fake_capture)

    preview = shep.get_pane_context({"source": "tmux", "target": "%7"})

    assert preview == "recent session output\n"
    assert captured == {
        "source": "tmux",
        "target": "%7",
        "lines": shep.SESSION_VIEW_LINES,
        "ansi": True,
    }


def test_loading_panel_is_a_small_graphical_status_card() -> None:
    lines = shep.loading_panel_lines(2, ascii_only=True)

    assert len(lines) == 3
    assert lines[0].startswith("+") and lines[0].endswith("+")
    assert "LOADING" in lines[1]
    assert lines[2] == lines[0]
    assert len(lines[0]) == len(lines[1])


# --- Mission deck ------------------------------------------------------------


def test_merge_decks_puts_build_missions_first() -> None:
    build = [{"project_name": "a", "mission_kind": "delivery"}]
    research = [{"project_name": "b", "mission_kind": "research"}]

    merged = shep.merge_decks(build, research, top=5)

    assert [m["project_name"] for m in merged] == ["a", "b"]


def test_merge_decks_dedupes_project_already_covered_by_a_build_mission() -> None:
    build = [{"project_name": "a", "mission_kind": "delivery"}]
    research = [
        {"project_name": "a", "mission_kind": "research"},
        {"project_name": "b", "mission_kind": "research"},
    ]

    merged = shep.merge_decks(build, research, top=5)

    assert [m["project_name"] for m in merged] == ["a", "b"]


def test_merge_decks_respects_the_top_cap() -> None:
    build = [{"project_name": f"b{i}"} for i in range(3)]
    research = [{"project_name": f"r{i}"} for i in range(10)]

    merged = shep.merge_decks(build, research, top=5)

    assert len(merged) == 5
    assert [m["project_name"] for m in merged][:3] == ["b0", "b1", "b2"]


def test_merge_decks_never_exceeds_top_with_build_missions_alone() -> None:
    build = [{"project_name": f"b{i}"} for i in range(9)]

    assert len(shep.merge_decks(build, [], top=5)) == 5


def test_mission_kind_label_distinguishes_code_writing_from_research() -> None:
    assert shep.mission_kind_label({"mission_kind": "research"}) == "RESEARCH"
    assert shep.mission_kind_label({"mission_kind": "delivery"}) == "BUILD"
    # An unlabelled mission must never be shown as the safe/read-only kind.
    assert shep.mission_kind_label({}) == "BUILD"


def test_mission_teaser_is_silent_when_no_missions_are_cached() -> None:
    assert shep.mission_teaser([]) == ""


def test_mission_teaser_reports_the_count_and_hotkey() -> None:
    teaser = shep.mission_teaser([{"id": "x"}, {"id": "y"}], ascii_only=True)

    assert "2 missions ready" in teaser
    assert "[M]" in teaser


def test_load_mission_deck_cache_only_never_shells_out(tmp_path, monkeypatch) -> None:
    """The startup teaser must not pay the sense.py cost."""
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "absent.json")

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("cache-only load must not shell out")

    monkeypatch.setattr(shep, "_run", explode)

    assert shep.load_mission_deck(force=False, allow_generate=False) == ([], None)


def test_load_mission_deck_serves_a_fresh_cache_without_regenerating(
    tmp_path, monkeypatch
) -> None:
    cache = tmp_path / "deck.json"
    cache.write_text('{"missions": [{"id": "m1"}]}')
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", cache)
    monkeypatch.setattr(shep, "_run", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

    missions, error = shep.load_mission_deck(force=False)

    assert error is None
    assert [m["id"] for m in missions] == ["m1"]


def test_load_mission_deck_regenerates_a_stale_cache(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "deck.json"
    cache.write_text('{"missions": [{"id": "stale"}]}')
    os.utime(cache, (0, 0))  # far older than MISSION_DECK_TTL
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", cache)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda repos, mode, top, min_score=None: (
            ([{"id": "fresh", "project_name": "a"}], None) if mode == "implementation"
            else ([], None)
        ),
    )

    missions, error = shep.load_mission_deck(force=False)

    assert error is None
    assert [m["id"] for m in missions] == ["fresh"]


def test_load_mission_deck_tops_up_a_thin_build_deck_with_research(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    calls = []

    def fake_generate(repos, mode, top, min_score=None):
        calls.append(mode)
        if mode == "implementation":
            return [{"id": "b1", "project_name": "a", "mission_kind": "delivery"}], None
        return (
            # Enough distinct projects to actually top the deck up. Scaled off
            # the constant rather than a literal, so raising the deck size does
            # not silently turn this into a test of a half-full deck.
            [{"id": f"r{i}", "project_name": f"p{i}", "mission_kind": "research",
              "momentum_score": 30}
             for i in range(shep.MISSION_DECK_TOP + 1)],
            None,
        )

    monkeypatch.setattr(shep, "_generate_deck", fake_generate)

    missions, error = shep.load_mission_deck(force=True)

    assert error is None
    assert calls == ["implementation", "research"]
    assert len(missions) == shep.MISSION_DECK_TOP
    assert missions[0]["mission_kind"] == "delivery"


def test_load_mission_deck_skips_research_when_build_deck_is_already_full(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    calls = []

    def fake_generate(repos, mode, top, min_score=None):
        calls.append(mode)
        return [
            {"id": f"b{i}", "project_name": f"p{i}"} for i in range(shep.MISSION_DECK_TOP)
        ], None

    monkeypatch.setattr(shep, "_generate_deck", fake_generate)

    shep.load_mission_deck(force=True)

    assert calls == ["implementation"]  # no wasted research sweep


def test_load_mission_deck_writes_the_cache_launch_reads(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "deck.json"
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", cache)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda repos, mode, top, min_score=None: (
            ([{"id": "m1", "project_name": "a"}], None) if mode == "implementation"
            else ([], None)
        ),
    )

    shep.load_mission_deck(force=True)

    written = json.loads(cache.read_text())
    assert [m["id"] for m in written["missions"]] == ["m1"]


def test_load_mission_deck_reports_the_build_error_when_nothing_survives(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck", lambda repos, mode, top, min_score=None: ([], "boom")
    )

    missions, error = shep.load_mission_deck(force=True)

    assert missions == []
    assert error == "boom"


def test_load_mission_deck_reports_an_uninstalled_mission_engine(
    tmp_path, monkeypatch
) -> None:
    # Covers the guard the autouse _mission_engine_installed fixture satisfies
    # for every other deck test, so bypassing it there does not leave the
    # not-installed branch untested.
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_SENSE_SCRIPT", tmp_path / "absent/sense.py")
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda *a, **k: pytest.fail("must not shell out when the engine is absent"),
    )

    missions, error = shep.load_mission_deck(force=True)

    assert missions == []
    assert error == "mission engine skills not installed"


def test_launch_refuses_when_no_deck_has_been_cached(tmp_path, monkeypatch) -> None:
    """Launch reads the deck from disk — never claim success without one."""
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "absent.json")
    monkeypatch.setattr(shep, "MISSION_LAUNCH_SCRIPT", tmp_path / "launch.py")
    (tmp_path / "launch.py").touch()

    ok, detail = shep.launch_mission_by_id("mission-x")

    assert ok is False
    assert "deck" in detail


def _stage_launch(tmp_path, monkeypatch, missions=None):
    cache = tmp_path / "deck.json"
    cache.write_text(
        json.dumps({"missions": missions if missions is not None else [
            {"id": "mission-abc", "cwd": "/repo", "default_branch": "develop"}
        ]})
    )
    script = tmp_path / "launch.py"
    script.touch()
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", cache)
    monkeypatch.setattr(shep, "MISSION_LAUNCH_SCRIPT", script)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    # module-level launched-set must not leak between tests
    monkeypatch.setattr(shep, "_MISSIONS_LAUNCHED", set())
    return cache


def test_launch_stages_an_isolated_worktree_and_single_mission_deck(
    tmp_path, monkeypatch
) -> None:
    _stage_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(
        shep, "prepare_mission_worktree", lambda m: ("/wt/mission-abc", None)
    )
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["deck"] = Path(cmd[cmd.index("--deck") + 1]).read_text()
        return SimpleNamespace(returncode=0, stdout="launched pane\n", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    ok, detail = shep.launch_mission_by_id("mission-abc")

    assert ok is True
    assert detail.startswith("launched pane")
    assert "/wt/mission-abc" in detail
    assert "mission-abc" in seen["cmd"]
    staged = json.loads(seen["deck"])
    # only the approved mission, pointed at the worktree — never the primary checkout
    assert [m["id"] for m in staged["missions"]] == ["mission-abc"]
    assert staged["missions"][0]["cwd"] == "/wt/mission-abc"


def test_launch_aborts_when_the_worktree_cannot_be_created(tmp_path, monkeypatch) -> None:
    """No isolation means no launch — never fall back to the primary checkout."""
    _stage_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(
        shep, "prepare_mission_worktree", lambda m: (None, "branch exists")
    )

    def explode(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("must not launch without isolation")

    monkeypatch.setattr(shep, "_run", explode)

    ok, detail = shep.launch_mission_by_id("mission-abc")

    assert ok is False
    assert "branch exists" in detail


def test_launch_rejects_a_mission_id_absent_from_the_deck(tmp_path, monkeypatch) -> None:
    _stage_launch(tmp_path, monkeypatch, missions=[])

    ok, detail = shep.launch_mission_by_id("mission-abc")

    assert ok is False
    assert "not in the cached deck" in detail


def test_launch_surfaces_failure_detail(tmp_path, monkeypatch) -> None:
    _stage_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/x", None))
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="herdr down"),
    )

    ok, detail = shep.launch_mission_by_id("mission-abc")

    assert ok is False
    assert "herdr down" in detail


def test_prepare_worktree_returns_the_verified_path(tmp_path, monkeypatch) -> None:
    script = tmp_path / "qa-worktree.sh"
    script.touch()
    monkeypatch.setattr(shep, "QA_WORKTREE_SCRIPT", script)
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(
            returncode=0, stdout="OK\nWORKTREE_PATH=/wt/m1\nBRANCH=qa/m1\n", stderr=""
        )

    monkeypatch.setattr(shep, "_run", fake_run)

    path, error = shep.prepare_mission_worktree(
        {"id": "m1", "cwd": "/repo", "default_branch": "develop"}
    )

    assert (path, error) == ("/wt/m1", None)
    assert seen["cmd"][-3:] == ["/repo", "m1", "develop"]


def test_prepare_worktree_reports_isolation_failure(tmp_path, monkeypatch) -> None:
    script = tmp_path / "qa-worktree.sh"
    script.touch()
    monkeypatch.setattr(shep, "QA_WORKTREE_SCRIPT", script)
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="FAIL: dirty"),
    )

    path, error = shep.prepare_mission_worktree({"id": "m1", "cwd": "/repo"})

    assert path is None
    assert "FAIL: dirty" in error


def test_prepare_worktree_rejects_output_without_a_verified_path(
    tmp_path, monkeypatch
) -> None:
    script = tmp_path / "qa-worktree.sh"
    script.touch()
    monkeypatch.setattr(shep, "QA_WORKTREE_SCRIPT", script)
    monkeypatch.setattr(
        shep, "_run", lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="OK\n", stderr="")
    )

    path, error = shep.prepare_mission_worktree({"id": "m1", "cwd": "/repo"})

    assert path is None
    assert "WORKTREE_PATH" in error


def test_launchable_repos_drops_missing_and_non_git_paths(tmp_path, monkeypatch) -> None:
    """A dead path scores fine in sense.py but can never launch — drop it early."""
    good = tmp_path / "good"
    plain = tmp_path / "plain"
    good.mkdir()
    plain.mkdir()
    listing = tmp_path / "repos.txt"
    listing.write_text(
        f"# a comment\n\n{good}\n{plain}\n{tmp_path / 'absent'}\n{good}  # trailing\n"
    )

    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(
            returncode=0 if os.fspath(good) in cmd else 1, stdout="", stderr=""
        ),
    )

    repos, dropped = shep.launchable_repos(listing)

    assert repos == [os.fspath(good)]
    assert any("plain" in d for d in dropped)
    assert any("absent" in d for d in dropped)


def test_launchable_repos_is_empty_for_an_unreadable_list(tmp_path) -> None:
    assert shep.launchable_repos(tmp_path / "absent.txt") == ([], [])


# --- Santa round-1 regressions ----------------------------------------------


def test_run_never_raises_on_timeout() -> None:
    """_run is called on the curses thread — a raise here kills the whole TUI."""
    result = shep._run(["sleep", "5"], timeout=1)

    assert result.returncode != 0
    assert "timed out" in result.stderr


def test_repoint_mission_rewrites_the_prompt_not_just_cwd() -> None:
    """launch_spec is injected verbatim as the agent's first prompt."""
    mission = {
        "id": "m1",
        "cwd": "/repo/primary",
        "launch_spec": "- Repo/dir: /repo/primary\n- Do the thing",
        "goal_condition": "work in /repo/primary until done",
        "momentum_score": 42,
    }

    staged = shep.repoint_mission(mission, "/wt/m1")

    assert "/repo/primary" not in json.dumps(staged)
    assert staged["cwd"] == "/wt/m1"
    assert "- Repo/dir: /wt/m1" in staged["launch_spec"]
    assert staged["momentum_score"] == 42  # non-strings untouched


def test_repoint_mission_tolerates_a_mission_without_cwd() -> None:
    assert shep.repoint_mission({"id": "m1"}, "/wt/m1") == {"id": "m1"}


def test_staged_deck_contains_no_reference_to_the_primary_checkout(
    tmp_path, monkeypatch
) -> None:
    primary = "/repo/primary"
    cache = tmp_path / "deck.json"
    cache.write_text(json.dumps({"missions": [{
        "id": "mission-abc",
        "cwd": primary,
        "launch_spec": f"- Repo/dir: {primary}\n- Branch off main",
    }]}))
    script = tmp_path / "launch.py"
    script.touch()
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", cache)
    monkeypatch.setattr(shep, "MISSION_LAUNCH_SCRIPT", script)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    monkeypatch.setattr(shep, "_MISSIONS_LAUNCHED", set())
    captured = {}

    def fake_run(cmd, **kw):
        deck_path = Path(cmd[cmd.index("--deck") + 1])
        captured["deck"] = deck_path.read_text()
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    shep.launch_mission_by_id("mission-abc")

    assert primary not in captured["deck"]
    assert "/wt/abc" in captured["deck"]


def test_launch_refuses_to_relaunch_an_in_flight_mission(tmp_path, monkeypatch) -> None:
    """qa-worktree.sh force-removes the track — a relaunch would delete live work."""
    _stage_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    monkeypatch.setattr(
        shep, "_run", lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="ok", stderr="")
    )

    assert shep.launch_mission_by_id("mission-abc")[0] is True

    def explode(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("relaunch must not touch the worktree")

    monkeypatch.setattr(shep, "prepare_mission_worktree", explode)
    ok, detail = shep.launch_mission_by_id("mission-abc")

    assert ok is False
    assert "already launched" in detail


def test_launch_removes_the_staging_deck_afterwards(tmp_path, monkeypatch) -> None:
    _stage_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="nope"),
    )
    shep._MISSIONS_LAUNCHED.discard("mission-abc")

    shep.launch_mission_by_id("mission-abc")

    assert list(tmp_path.glob("shep-launch-*.json")) == []


def test_implementation_mode_is_never_fed_the_wider_research_repo_list(
    tmp_path, monkeypatch
) -> None:
    """The repos file IS the guard — recommend.py has no repo allowlist."""
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    seen = []

    def fake_generate(repos, mode, top, min_score=None):
        seen.append((mode, repos, min_score))
        return [], None

    monkeypatch.setattr(shep, "_generate_deck", fake_generate)

    shep.load_mission_deck(force=True)

    build_calls = [c for c in seen if c[0] == "implementation"]
    assert build_calls, "implementation deck must be generated"
    for _mode, repos, min_score in build_calls:
        assert repos == shep.MISSION_REPOS_FILE
        assert repos != shep.MISSION_RESEARCH_REPOS_FILE
        assert min_score == shep.MISSION_MIN_SCORE
    for mode, repos, _ in seen:
        if mode == "research":
            assert repos == shep.MISSION_RESEARCH_REPOS_FILE


def test_low_value_research_scouts_are_kept_out_of_the_deck(
    tmp_path, monkeypatch
) -> None:
    """recommend.py bypasses --min-score in research mode; the floor lives here."""
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)

    def fake_generate(repos, mode, top, min_score=None):
        if mode == "implementation":
            return [], None
        return [
            {"id": "hi", "project_name": "a", "momentum_score": 30,
             "mission_kind": "research"},
            {"id": "lo", "project_name": "b", "momentum_score": 1,
             "mission_kind": "research"},
        ], None

    monkeypatch.setattr(shep, "_generate_deck", fake_generate)

    missions, _error = shep.load_mission_deck(force=True)

    assert [m["id"] for m in missions] == ["hi"]


def test_thin_deck_surfaces_the_collector_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)

    def fake_generate(repos, mode, top, min_score=None):
        if mode == "implementation":
            return [{"id": "b1", "project_name": "a", "momentum_score": 50}], None
        return [], "research sweep exploded"

    monkeypatch.setattr(shep, "_generate_deck", fake_generate)

    missions, error = shep.load_mission_deck(force=True)

    assert len(missions) == 1
    assert error == "research sweep exploded"


def test_full_deck_reports_no_error_even_if_topup_failed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda repos, mode, top, min_score=None: (
            [{"id": f"b{i}", "project_name": f"p{i}", "momentum_score": 50}
             for i in range(shep.MISSION_DECK_TOP)], None
        ),
    )

    missions, error = shep.load_mission_deck(force=True)

    assert len(missions) == shep.MISSION_DECK_TOP
    assert error is None


def test_launchable_repos_dedupes_while_preserving_order(tmp_path, monkeypatch) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    listing = tmp_path / "repos.txt"
    listing.write_text(f"{a}\n{b}\n{a}\n")
    monkeypatch.setattr(
        shep, "_run", lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="", stderr="")
    )

    assert shep.launchable_repos(listing)[0] == [os.fspath(a), os.fspath(b)]


def test_scroll_window_keeps_the_selected_mission_on_screen() -> None:
    # A 20-row terminal fits 3 complete mission rows after the tab shell and
    # footer reserves; selecting the 5th must scroll to the final window.
    top, visible = shep.mission_scroll_window(selected=4, count=5, height=20)

    assert visible == 3
    assert top == 2
    assert top <= 4 < top + visible


def test_scroll_window_does_not_scroll_when_everything_fits() -> None:
    top, visible = shep.mission_scroll_window(selected=4, count=5, height=40)

    assert top == 0
    assert visible >= 5


def test_scroll_window_survives_a_tiny_terminal() -> None:
    top, visible = shep.mission_scroll_window(selected=0, count=5, height=1)

    assert visible >= 1
    assert top == 0


def test_tiny_mission_terminal_keeps_a_headline_paint_slot() -> None:
    assert shep.mission_content_bottom(8) == shep.SHEP_TAB_Y + 3


def test_scroll_window_never_scrolls_past_the_end() -> None:
    top, visible = shep.mission_scroll_window(selected=9, count=10, height=20)

    assert top + visible <= 10
    assert top <= 9 < top + visible


# --- Santa round-2 regressions ----------------------------------------------


def test_repoint_mission_rewrites_nested_evidence_and_metadata() -> None:
    """recommend.py emits `evidence` as a list that launch.py copies into the bead."""
    mission = {
        "id": "m1",
        "cwd": "/repo/primary",
        "evidence": ["ready bead in /repo/primary", {"path": "/repo/primary/src"}],
        "meta": {"nested": {"deep": "/repo/primary/x"}},
    }

    staged = shep.repoint_mission(mission, "/wt/m1")

    assert "/repo/primary" not in json.dumps(staged)
    assert staged["evidence"][0] == "ready bead in /wt/m1"
    assert staged["meta"]["nested"]["deep"] == "/wt/m1/x"


def test_worktree_guard_is_path_based_not_branch_based(tmp_path, monkeypatch) -> None:
    """The agent switches to feat/<id>; a branch check would go blind then."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    wt = tmp_path / ".qa-worktrees" / "myrepo" / "mission-m1"
    wt.mkdir(parents=True)

    assert shep.mission_worktree_exists("/repos/myrepo", "mission-m1") is True
    assert shep.mission_worktree_exists("/repos/myrepo", "mission-absent") is False
    assert shep.mission_worktree_exists("/repos/myrepo", "") is False


def test_prepare_worktree_refuses_when_the_mission_is_already_checked_out(
    tmp_path, monkeypatch
) -> None:
    """Survives a shep restart — qa-worktree.sh would force-remove live work."""
    script = tmp_path / "qa-worktree.sh"
    script.touch()
    monkeypatch.setattr(shep, "QA_WORKTREE_SCRIPT", script)
    monkeypatch.setattr(shep, "mission_worktree_exists", lambda repo, mid: True)

    def explode(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("must not re-cut an existing worktree")

    monkeypatch.setattr(shep, "_run", explode)

    path, error = shep.prepare_mission_worktree({"id": "m1", "cwd": "/repo"})

    assert path is None
    assert "already exists" in error


def test_launch_timeout_is_not_reported_as_a_safe_to_retry_failure(
    tmp_path, monkeypatch
) -> None:
    """launch.py may have created the pane — a retry would destroy its worktree."""
    _stage_launch(tmp_path, monkeypatch)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(returncode=124, stdout="", stderr="timed out"),
    )

    ok, detail = shep.launch_mission_by_id("mission-abc")

    assert ok is False
    assert "MAY still be starting" in detail
    # recorded anyway, so the next Enter cannot re-cut the worktree
    assert "mission-abc" in shep._MISSIONS_LAUNCHED


def test_research_topup_drops_anything_not_explicitly_artifact_only(
    tmp_path, monkeypatch
) -> None:
    """Defence in depth: the wider repo list must never yield a code mission."""
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)

    def fake_generate(repos, mode, top, min_score=None):
        if mode == "implementation":
            return [], None
        return [
            {"id": "ok", "project_name": "a", "momentum_score": 40,
             "mission_kind": "research"},
            # recommend.py dropping/renaming the field must not create a
            # code-writing mission on a product repo
            {"id": "unlabelled", "project_name": "b", "momentum_score": 90},
            {"id": "delivery", "project_name": "c", "momentum_score": 90,
             "mission_kind": "delivery"},
        ], None

    monkeypatch.setattr(shep, "_generate_deck", fake_generate)

    missions, _error = shep.load_mission_deck(force=True)

    assert [m["id"] for m in missions] == ["ok"]


def test_status_message_names_repos_that_were_skipped(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_DROPPED_REPOS", {"/repos/app-repos/macdaddy"})

    message = shep.mission_status_message([{"id": "m1"}], None)

    assert "1 missions ready" in message
    assert "/repos/app-repos/macdaddy" in message


def test_status_message_prefers_the_error(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_DROPPED_REPOS", set())

    assert shep.mission_status_message([], "boom") == "boom"


def test_needs_research_missions_request_the_research_brief(
    tmp_path, monkeypatch
) -> None:
    """The spec tells the agent to read a brief — it must actually be generated."""
    cache = tmp_path / "deck.json"
    cache.write_text(json.dumps({"missions": [
        {"id": "mission-abc", "cwd": "/repo", "needs_research": True}
    ]}))
    script = tmp_path / "launch.py"
    script.touch()
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", cache)
    monkeypatch.setattr(shep, "MISSION_LAUNCH_SCRIPT", script)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "_MISSIONS_LAUNCHED", set())
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    shep.launch_mission_by_id("mission-abc")

    assert "--research" in seen["cmd"]


def test_the_code_writing_repo_list_is_not_env_overridable() -> None:
    """An override here silently defeats the only guard that exists."""
    assert shep.MISSION_REPOS_FILE.name == "delivery-repos.txt"
    assert "SHEP_MISSION_REPOS_FILE" not in Path(shep.__file__).read_text()


# --- Santa round-3 regressions ----------------------------------------------


def test_worktree_guard_survives_the_agent_switching_branches(
    tmp_path, monkeypatch
) -> None:
    """qa-worktree.sh rm -rf's by PATH, and the spec moves the agent to feat/<id>."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    script = tmp_path / "qa-worktree.sh"
    script.touch()
    monkeypatch.setattr(shep, "QA_WORKTREE_SCRIPT", script)
    wt = tmp_path / ".qa-worktrees" / "atlas-commander" / "mission-abc"
    wt.mkdir(parents=True)
    (wt / "UNCOMMITTED.txt").write_text("agent work")

    def explode(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("must not re-cut a live worktree")

    monkeypatch.setattr(shep, "_run", explode)

    path, error = shep.prepare_mission_worktree(
        {"id": "mission-abc", "cwd": "/repos/atlas-commander"}
    )

    assert path is None
    assert "already exists" in error
    assert (wt / "UNCOMMITTED.txt").exists()


def test_repoint_rewrites_the_research_artifact_path_for_harvest() -> None:
    """research_cycle.reconcile looks for <cwd.name>-research.md."""
    mission = {
        "id": "mission-bug-hunter-4e14612a",
        "cwd": "/repos/bug-hunter",
        "mission_kind": "research",
        "artifact_path": "reports/research/mission-engine/bug-hunter-research.md",
        "launch_spec": "- Write only: reports/research/mission-engine/bug-hunter-research.md",
    }
    worktree = "/wt/mission-bug-hunter-4e14612a"

    staged = shep.repoint_mission(mission, worktree)

    expected = (
        "reports/research/mission-engine/mission-bug-hunter-4e14612a-research.md"
    )
    assert staged["artifact_path"] == expected
    # the instruction the agent actually reads must match the harvested path
    assert expected in staged["launch_spec"]
    assert "bug-hunter-research.md" not in staged["launch_spec"].replace(expected, "")


def test_base_branch_prefers_develop_over_a_main_default(monkeypatch) -> None:
    """CLAUDE.md forbids cutting SDLC branches off main."""
    monkeypatch.setattr(
        shep, "_run", lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="", stderr="")
    )

    assert shep.mission_base_branch("/repo", "main") == "develop"


def test_base_branch_falls_back_when_there_is_no_develop(monkeypatch) -> None:
    monkeypatch.setattr(
        shep, "_run", lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="")
    )

    assert shep.mission_base_branch("/repo", "main") == "main"


def test_gate_research_drops_missions_the_engine_rejects(tmp_path, monkeypatch) -> None:
    script = tmp_path / "research_cycle.py"
    script.touch()
    monkeypatch.setattr(shep, "RESEARCH_CYCLE_SCRIPT", script)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(
            returncode=0, stdout=json.dumps({"missions": [{"id": "keep"}]}), stderr=""
        ),
    )

    kept = shep.gate_research([{"id": "keep"}, {"id": "already-active"}])

    assert [m["id"] for m in kept] == ["keep"]
    assert list(tmp_path.glob("shep-gate-input.json")) == []


def test_gate_research_is_fail_soft(tmp_path, monkeypatch) -> None:
    """A broken gate must not silently empty the deck."""
    script = tmp_path / "research_cycle.py"
    script.touch()
    monkeypatch.setattr(shep, "RESEARCH_CYCLE_SCRIPT", script)
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )

    missions = [{"id": "a"}, {"id": "b"}]

    assert shep.gate_research(missions) == missions


def test_gate_research_skipped_when_the_engine_gate_is_absent(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(shep, "RESEARCH_CYCLE_SCRIPT", tmp_path / "absent.py")
    missions = [{"id": "a"}]

    assert shep.gate_research(missions) == missions


def test_slow_git_probe_is_not_mislabelled_as_a_dead_repo(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "slowrepo"
    repo.mkdir()
    listing = tmp_path / "repos.txt"
    listing.write_text(str(repo))
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **kw: SimpleNamespace(returncode=124, stdout="", stderr="timed out"),
    )

    repos, dropped = shep.launchable_repos(listing)

    assert repos == []
    assert dropped == [f"{repo} (probe timed out — retry before removing)"]


def test_dropped_repos_are_recomputed_each_sweep(tmp_path, monkeypatch) -> None:
    """A repo fixed between two regenerates must stop being reported as skipped."""
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "_DROPPED_REPOS", {"stale-from-last-time"})
    monkeypatch.setattr(
        shep, "_generate_deck",
        lambda repos, mode, top, min_score=None: (
            [{"id": "b", "project_name": "p", "momentum_score": 50}], None
        ),
    )

    shep.load_mission_deck(force=True)

    assert "stale-from-last-time" not in shep._DROPPED_REPOS


def test_launch_rejects_a_mission_with_no_id(tmp_path, monkeypatch) -> None:
    _stage_launch(tmp_path, monkeypatch)

    ok, detail = shep.launch_mission_by_id("")

    assert ok is False
    assert "no id" in detail


def test_research_missions_launch_into_the_harvestable_space(
    tmp_path, monkeypatch
) -> None:
    """research_cycle.reconcile only harvests the "research" space."""
    _stage_launch(tmp_path, monkeypatch, missions=[
        {"id": "mission-abc", "cwd": "/repo", "mission_kind": "research"}
    ])
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    shep.launch_mission_by_id("mission-abc")

    assert "--space-label" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--space-label") + 1] == "research"


def test_build_missions_keep_the_default_space(tmp_path, monkeypatch) -> None:
    _stage_launch(tmp_path, monkeypatch, missions=[
        {"id": "mission-abc", "cwd": "/repo", "mission_kind": "delivery"}
    ])
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: ("/wt/abc", None))
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    shep.launch_mission_by_id("mission-abc")

    assert "--space-label" not in seen["cmd"]


# --- Shell / dead-agent panes ------------------------------------------------
#
# Every tmux row in the live fleet was reported "working" because the old
# classifier defaulted anything that was not a known agent prompt glyph to
# working: a bare login shell, a wedged zsh `quote>` continuation, and an agent
# that had already printed "Cancelled by user" all read as busy.


@pytest.mark.parametrize(
    "last_line",
    [
        "developer@Developer-Mac mb-mgmt %",
        "quote>",
        "dquote>",
        "$",
        "[07:15] Status: stopped: Cancelled by user",
    ],
)
def test_shell_and_dead_panes_are_not_working(monkeypatch, last_line) -> None:
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: f"earlier\n{last_line}\n")
    status, _cues, _ctx = shep._tmux_pane_state("%1")
    assert status == "shell"
    assert status not in shep.NUDGEABLE  # nothing there to instruct


def test_bare_glyph_without_chrome_is_not_assumed_to_be_an_agent(monkeypatch) -> None:
    """A lone `❯` is ambiguous — Claude uses it and so does starship zsh.

    This originally asserted "idle", which is the assumption that let a nudge
    reach a live shell. With no chrome to disambiguate, fail toward shell.
    """
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: "doing work\n❯")
    assert shep._tmux_pane_state("%2")[0] == "shell"


def test_shell_status_renders_distinctly() -> None:
    row = {"status": "shell"}
    assert shep.status_display(row) == "_ shell"
    assert "SHELL" in shep.status_badge(row)


# --- Open questionnaires -----------------------------------------------------
#
# An agent that stops to ask (Claude Code's AskUserQuestion or a permission
# prompt, Codex's approval prompt) draws a cursor glyph inside box chrome, so it
# read as `idle`: the question never surfaced to the operator, and the pane was
# NUDGEABLE — a drafted sentence typed into a live selector answers it at random.

_ASK_PANE = (
    "⎿  read 3 files\n"
    "╭──────────────────────────────────────────╮\n"
    "│ Which auth method should the worker use? │\n"
    "│                                          │\n"
    "│ ❯ 1. Service account (Recommended)       │\n"
    "│   2. OAuth device flow                   │\n"
    "│   3. Other                               │\n"
    "╰──────────────────────────────────────────╯\n"
)
_CODEX_APPROVAL_PANE = (
    "running: git push --force-with-lease\n"
    "Allow this command?\n"
    "› 1. Yes\n"
    "  2. No, tell Codex what to do differently\n"
)


@pytest.mark.parametrize(
    "pane", [_ASK_PANE, _CODEX_APPROVAL_PANE], ids=["claude", "codex"]
)
def test_open_questionnaire_is_not_nudgeable(monkeypatch, pane) -> None:
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane)
    status, _cues, context = shep._tmux_pane_state("%p")
    assert status == "asking"
    assert status not in shep.NUDGEABLE
    assert context.startswith("needs answer: ")


def test_questionnaire_context_carries_the_question_not_an_option() -> None:
    context = shep.pane_context_summary(_ASK_PANE)
    assert context == "needs answer: Which auth method should the worker use?"


def test_numbered_output_without_a_cursor_is_not_a_questionnaire(monkeypatch) -> None:
    """Prose lists are common in agent output; only a selector marks a choice."""
    pane = (
        "Remaining work:\n1. rebase onto develop\n2. rerun the suite\n"
        "❯ \n────────────\n  Opus 5 | med | ContextQ:--"
    )
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane)
    assert shep._tmux_pane_state("%p")[0] == "idle"


def test_herdr_questionnaire_overrides_reported_agent_status(monkeypatch) -> None:
    monkeypatch.setattr(shep, "HERDR_CTL", Path(__file__))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"panes": [{
            "pane_id": "w9:p1", "agent_status": "working", "cwd": "/repo",
        }]}),
        stderr="",
    ))
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: _ASK_PANE)
    (row,) = shep.collect_herdr()
    assert row["status"] == "asking"
    assert row["status"] not in shep.NUDGEABLE


def test_herdr_controller_stdout_error_is_preserved(monkeypatch) -> None:
    """Structured controller failures must explain the unavailable row."""
    monkeypatch.setattr(shep, "HERDR_CTL", Path(__file__))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=1,
        stdout=json.dumps({
            "error": (
                "herdr pane list failed: "
                '{"id":"cli:pane:list","error":{"code":"protocol_mismatch",'
                '"message":"client protocol 19 is newer than server protocol 16"}}'
            ),
        }),
        stderr="",
    ))

    (row,) = shep.collect_herdr()

    assert row["status"] == "error"
    assert "protocol_mismatch" in row["label"]
    assert "server protocol 16" in row["label"]
    assert "non-zero exit" not in row["label"]


def _t3_stamp(seconds_ago):
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        seconds=seconds_ago
    )
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def _t3_thread(age=60, **over):
    stamp = _t3_stamp(age)
    thread = {
        "id": "th-1",
        "title": "Finish the trading repo",
        "projectId": "p-1",
        "runtimeMode": "full-access",
        "interactionMode": "default",
        "updatedAt": stamp,
        "session": {
            "status": "ready", "activeTurnId": None, "lastError": None,
            "updatedAt": stamp,
        },
        "latestTurn": {"state": "completed", "completedAt": stamp},
    }
    thread.update(over)
    return thread


def _stub_t3(monkeypatch, threads, projects=None, status=200):
    """Wire collect_t3 to a canned shell snapshot — no binary, no server."""
    monkeypatch.setattr(shep, "T3_BIN", str(Path(__file__)))
    monkeypatch.setattr(shep, "_t3_token", lambda: "tok")
    monkeypatch.setattr(shep, "_t3_request", lambda *a, **k: (
        status, {"threads": threads, "projects": projects or []},
    ))


def _t3_row(status="idle", context="pytest failed in test_api.py"):
    return {"source": "t3", "id": "th-1", "target": "th-1", "label": "thread",
            "status": status, "cwd": "/repo", "context": context,
            "quiet_for": shep.NUDGE_QUIET_SECONDS,
            "runtime_mode": "full-access", "interaction_mode": "default"}


def test_t3_ready_thread_with_a_completed_turn_is_collected_as_idle(monkeypatch) -> None:
    _stub_t3(monkeypatch, [_t3_thread()], [{"id": "p-1", "workspaceRoot": "/repo"}])

    (row,) = shep.collect_t3()

    assert row["source"] == "t3"
    assert row["status"] == "idle"
    assert row["status"] in shep.NUDGEABLE
    assert row["target"] == "th-1"
    assert row["cwd"] == "/repo"
    assert row["context"] == "Finish the trading repo"
    assert 0 <= row["quiet_for"] < shep.STALL_AFTER_SECONDS


def test_t3_thread_quiet_past_the_stall_clock_is_reported_as_stalled(monkeypatch) -> None:
    _stub_t3(monkeypatch, [_t3_thread(age=shep.STALL_AFTER_SECONDS + 60)])

    (row,) = shep.collect_t3()

    assert row["status"] == "stalled"
    assert row["status"] in shep.NUDGEABLE


def test_t3_running_session_is_working_and_never_nudgeable(monkeypatch) -> None:
    running = _t3_thread(
        session={"status": "running", "activeTurnId": "turn-9", "lastError": None},
        latestTurn={"state": "running", "completedAt": None},
    )
    _stub_t3(monkeypatch, [running])

    (row,) = shep.collect_t3()

    assert row["status"] == "working"
    assert row["status"] not in shep.NUDGEABLE


def test_t3_background_work_outliving_a_completed_turn_stays_working(monkeypatch) -> None:
    """A settled turn is not a settled session — this is the only field that says so."""
    _stub_t3(monkeypatch, [_t3_thread(backgroundLiveness="working")])

    (row,) = shep.collect_t3()

    assert row["status"] == "working"
    assert row["status"] not in shep.NUDGEABLE


def test_t3_thread_awaiting_a_human_answer_is_not_nudgeable(monkeypatch) -> None:
    for field in ("hasPendingApprovals", "hasPendingUserInput"):
        _stub_t3(monkeypatch, [_t3_thread(**{field: True})])

        (row,) = shep.collect_t3()

        assert row["status"] == "asking", field
        assert row["status"] not in shep.NUDGEABLE, field


def test_t3_interrupted_turn_is_not_resumed_by_a_nudge(monkeypatch) -> None:
    """`interrupted` is a deliberate human stop; a nudge must not override it."""
    _stub_t3(monkeypatch, [_t3_thread(latestTurn={"state": "interrupted"})])

    (row,) = shep.collect_t3()

    assert row["status"] not in shep.NUDGEABLE


def test_t3_errored_session_is_never_nudgeable(monkeypatch) -> None:
    _stub_t3(monkeypatch, [_t3_thread(
        session={"status": "ready", "activeTurnId": None, "lastError": "boom"})])

    (row,) = shep.collect_t3()

    assert row["status"] == "error"
    assert row["status"] not in shep.NUDGEABLE


def test_t3_unrecognised_session_status_is_not_assumed_idle(monkeypatch) -> None:
    _stub_t3(monkeypatch, [_t3_thread(
        session={"status": "starting", "activeTurnId": None, "lastError": None})])

    (row,) = shep.collect_t3()

    assert row["status"] not in shep.NUDGEABLE


def test_t3_stopped_and_retired_threads_are_omitted_entirely(monkeypatch) -> None:
    _stub_t3(monkeypatch, [
        _t3_thread(id="stopped", session={"status": "stopped", "activeTurnId": None,
                                          "lastError": None}),
        _t3_thread(id="archived", archivedAt=_t3_stamp(10)),
        _t3_thread(id="deleted", deletedAt=_t3_stamp(10)),
        _t3_thread(id="sessionless", session=None),
        _t3_thread(id="live"),
    ])

    rows = shep.collect_t3()

    assert [row["id"] for row in rows] == ["live"]


def test_t3_collector_is_empty_when_the_server_is_unreachable(monkeypatch) -> None:
    """T3 being down must never read as a fleet of agents waiting to be nudged."""
    monkeypatch.setattr(shep, "T3_BIN", str(Path(__file__)))
    monkeypatch.setattr(shep, "_t3_token", lambda: "tok")
    monkeypatch.setattr(shep, "_t3_request", lambda *a, **k: (0, "connection refused"))

    assert shep.collect_t3() == []


def test_t3_collector_is_empty_when_a_token_cannot_be_minted(monkeypatch) -> None:
    monkeypatch.setattr(shep, "T3_BIN", str(Path(__file__)))
    monkeypatch.setattr(shep, "_t3_token", lambda: None)
    monkeypatch.setattr(shep, "_t3_request", lambda *a, **k: (200, {"threads": [
        _t3_thread()]}))

    assert shep.collect_t3() == []


def test_t3_collector_is_empty_when_t3_is_not_installed(monkeypatch) -> None:
    monkeypatch.setattr(shep, "T3_BIN", "/nonexistent/t3-binary")
    monkeypatch.setattr(shep, "_t3_token", lambda: pytest.fail("must not mint a token"))

    assert shep.collect_t3() == []


def test_t3_collector_returns_no_rows_for_an_unknown_payload_shape(monkeypatch) -> None:
    monkeypatch.setattr(shep, "T3_BIN", str(Path(__file__)))
    monkeypatch.setattr(shep, "_t3_token", lambda: "tok")
    monkeypatch.setattr(shep, "_t3_request", lambda *a, **k: (200, {"threads": "nope"}))

    assert shep.collect_t3() == []


def test_t3_nudge_dispatches_a_turn_start_to_the_existing_thread(monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(shep, "_t3_token", lambda: "tok")

    def _request(token, path, payload=None):
        sent.append((path, payload))
        return 200, {"sequence": 7}

    monkeypatch.setattr(shep, "_t3_request", _request)

    ok, detail = shep._deliver_nudge(_t3_row(), "Keep going.", audit=False)

    assert ok, detail
    ((path, payload),) = sent
    assert path == "/api/orchestration/dispatch"
    assert payload["type"] == "thread.turn.start"
    assert payload["threadId"] == "th-1"
    assert payload["message"] == {
        "messageId": payload["message"]["messageId"],
        "role": "user", "text": "Keep going.", "attachments": [],
    }
    assert payload["runtimeMode"] == "full-access"
    assert payload["interactionMode"] == "default"
    # No bootstrap: this continues an existing thread, it never creates one.
    assert "bootstrap" not in payload


def test_t3_nudge_fails_closed_when_a_token_cannot_be_minted(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_t3_token", lambda: None)
    monkeypatch.setattr(
        shep, "_t3_request", lambda *a, **k: pytest.fail("must not reach the API")
    )

    ok, detail = shep._deliver_nudge(_t3_row(), "Keep going.", audit=False)

    assert not ok
    assert "auth" in detail


def test_t3_nudge_reports_a_rejected_dispatch_as_failure(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_t3_token", lambda: "tok")
    monkeypatch.setattr(shep, "_t3_request", lambda *a, **k: (500, "dispatch failed"))

    ok, detail = shep._deliver_nudge(_t3_row(), "Keep going.", audit=False)

    assert not ok
    assert "500" in detail


def test_t3_pane_capture_never_falls_through_to_tmux(monkeypatch) -> None:
    """A thread id is not a pane id — capturing it would read someone else's pane."""
    calls = []
    monkeypatch.setattr(shep, "_run", lambda *a, **k: calls.append(a) or SimpleNamespace(
        returncode=0, stdout="someone else's pane", stderr=""))

    assert shep.capture_pane("t3", "th-1") == ""
    assert calls == []


def test_t3_rows_pass_through_the_same_risk_gate_as_other_sources() -> None:
    row = _t3_row()

    safe, held = shep.bulk_nudge_candidates(
        [row], {"th-1": "Run pytest test_api.py."}, {})
    assert [text for _row, text in safe] == ["Run pytest test_api.py."]
    assert held == 0

    risky, held = shep.bulk_nudge_candidates(
        [row], {"th-1": "Run the merge of MR !2 into main for test_api.py."}, {})
    assert risky == []
    assert held == 1


def test_t3_rows_join_the_fleet_alongside_the_other_collectors(monkeypatch) -> None:
    monkeypatch.setattr(shep, "collect_herdr", lambda: [])
    monkeypatch.setattr(shep, "collect_tmux", lambda claimed: [])
    monkeypatch.setattr(shep, "collect_warp", lambda: [])
    _stub_t3(monkeypatch, [_t3_thread()])

    rows = shep.collect_all()

    assert [row["source"] for row in rows] == ["t3"]


def test_t3_badge_is_named_rather_than_unknown() -> None:
    assert shep.source_badge("t3") == "T3"


def _t3_issued(token="tok-1", session_id="sess-1"):
    return SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"token": token, "sessionId": session_id}),
        stderr="",
    )


def test_t3_token_is_reused_across_separate_shep_subprocesses(monkeypatch) -> None:
    """shep_control_loop.py runs `shep.py` as several fresh subprocesses per
    pass (sweep, then a capacity plan); each starts with an empty in-process
    `_T3_TOKEN`, so only the on-disk cache can make the second subprocess
    reuse the first one's bearer instead of minting -- and orphaning -- its
    own T3 auth session.
    """
    calls = []
    monkeypatch.setattr(shep, "_run", lambda argv, **_k: calls.append(argv) or _t3_issued())

    first = shep._t3_token()
    assert first == "tok-1"
    assert calls == [[shep.T3_BIN, "auth", "session", "issue", "--ttl", "5m", "--json"]]

    # Simulate the next `shep.py` subprocess: a cold in-process cache, same
    # $HOME and therefore the same on-disk cache file.
    shep._T3_TOKEN.update(value=None, expires=0.0)

    second = shep._t3_token()
    assert second == "tok-1"
    assert len(calls) == 1, "the on-disk cache must be reused, not re-minted"


def test_t3_token_cache_expiry_forces_a_fresh_mint(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        shep, "_run", lambda argv, **_k: calls.append(argv) or _t3_issued("tok-2", "sess-2")
    )
    shep.T3_AUTH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    shep.T3_AUTH_CACHE_FILE.write_text(json.dumps(
        {"token": "tok-stale", "session_id": "sess-stale", "expires": time.time() - 1}))

    token = shep._t3_token()

    assert token == "tok-2"
    assert calls[0] == [shep.T3_BIN, "auth", "session", "issue", "--ttl", "5m", "--json"]


def test_t3_token_replacement_revokes_the_session_it_supersedes(monkeypatch) -> None:
    """T3 exposes no bulk "purge expired sessions" call (only issue/list/
    revoke-by-id, and revoke merely marks a row rather than deleting it), so
    proactively revoking the session a fresh mint replaces -- the moment it is
    replaced, rather than leaving it to idle out its own TTL -- is the one
    piece of that lifecycle shep can do through a supported command.
    """
    calls = []
    monkeypatch.setattr(
        shep, "_run", lambda argv, **_k: calls.append(argv) or _t3_issued("tok-2", "sess-2")
    )
    shep.T3_AUTH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    shep.T3_AUTH_CACHE_FILE.write_text(json.dumps(
        {"token": "tok-stale", "session_id": "sess-stale", "expires": time.time() - 1}))

    shep._t3_token()

    assert calls[-1] == [shep.T3_BIN, "auth", "session", "revoke", "sess-stale"]


def test_t3_first_ever_mint_revokes_nothing(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(shep, "_run", lambda argv, **_k: calls.append(argv) or _t3_issued())

    shep._t3_token()

    assert calls == [[shep.T3_BIN, "auth", "session", "issue", "--ttl", "5m", "--json"]]


def test_t3_token_cache_file_is_private_and_never_logs_the_bearer(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_run", lambda argv, **_k: _t3_issued())

    shep._t3_token()

    mode = shep.T3_AUTH_CACHE_FILE.stat().st_mode & 0o777
    assert mode == 0o600
    saved = json.loads(shep.T3_AUTH_CACHE_FILE.read_text())
    assert saved == {"token": "tok-1", "session_id": "sess-1", "expires": saved["expires"]}


def test_t3_token_mint_failure_never_seeds_the_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **_k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )

    assert shep._t3_token() is None
    assert not shep.T3_AUTH_CACHE_FILE.exists()


def test_t3_token_is_serialized_across_real_concurrent_os_processes(tmp_path) -> None:
    """Real cross-process contention on T3_AUTH_CACHE_FILE's fcntl lock.

    Every other cache test in this file simulates "separate shep.py
    subprocesses" by resetting `shep._T3_TOKEN` between two calls in the SAME
    process -- useful for the reuse/expiry/revoke branches, but it never
    actually contends for the file lock the way `shep_control_loop.py`'s
    concurrent sweep + capacity-plan subprocesses do. This spawns several
    real Python processes racing `_t3_token()` against one shared cache file
    and a deliberately slow fake `t3` binary, so the lock is genuinely under
    contention: only one process may be inside the mint-and-cache critical
    section at a time, and every other racer must observe its result instead
    of minting -- and orphaning -- its own T3 auth session.
    """
    root = Path(shep.__file__).resolve().parent.parent
    cache_file = tmp_path / "t3-auth-cache.json"
    calls_log = tmp_path / "calls.log"
    fake_t3 = tmp_path / "fake_t3.py"
    fake_t3.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['FAKE_T3_CALLS_LOG'], 'a', encoding='utf-8') as fh:\n"
        "    fh.write(' '.join(args) + chr(10))\n"
        "if args[:3] == ['auth', 'session', 'issue']:\n"
        "    time.sleep(float(os.environ.get('FAKE_T3_ISSUE_DELAY', '0')))\n"
        "    print(json.dumps({'token': 'tok-real', 'sessionId': 'sess-real'}))\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_t3.chmod(0o755)

    env = dict(os.environ)
    env.update({
        "SHEP_T3_AUTH_CACHE": str(cache_file),
        "T3_BIN": str(fake_t3),
        "FAKE_T3_CALLS_LOG": str(calls_log),
        # Wide enough that the other racers are provably blocked on the lock
        # (not just fast enough to never overlap) without making the test slow.
        "FAKE_T3_ISSUE_DELAY": "0.4",
        "PYTHONPATH": str(root),
    })
    worker_src = "from scripts import shep\nprint(shep._t3_token())\n"

    procs = [
        subprocess.Popen(
            [sys.executable, "-c", worker_src],
            cwd=root, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for _ in range(3)
    ]
    results = [proc.communicate(timeout=10) for proc in procs]

    for stdout, stderr in results:
        assert stdout.strip().splitlines()[-1] == "tok-real", stderr

    calls = calls_log.read_text(encoding="utf-8").splitlines()
    issue_calls = [line for line in calls if line.startswith("auth session issue")]
    assert len(issue_calls) == 1, (
        "the fcntl lock must serialize the mint so only the winning racer "
        f"issues a T3 auth session, got: {calls}"
    )

    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert saved["token"] == "tok-real"


def test_questionnaire_reaches_the_operator_as_attention() -> None:
    row = {"status": "asking"}
    assert shep.status_display(row) == "? needs answer"
    assert "NEEDS ANSWER" in shep.status_badge(row)
    assert shep.fleet_counts([row])["attention"] == 1
    assert "1" in shep.fleet_summary([row])


def test_question_options_are_parsed_in_display_order() -> None:
    assert shep.pane_question_options(_ASK_PANE) == [
        ("1", "Service account (Recommended)"),
        ("2", "OAuth device flow"),
        ("3", "Other"),
    ]


def test_answering_sends_only_the_option_key(monkeypatch) -> None:
    """The number is a hotkey — a trailing Enter submits into the next screen."""
    sent = []
    monkeypatch.setattr(shep, "_run", lambda argv, **k: sent.append(argv) or SimpleNamespace(
        returncode=0, stdout="", stderr="",
    ))
    row = {"source": "tmux", "target": "%7", "status": "asking", "label": "claude"}
    ok, _detail = shep.answer_session(row, "2", "OAuth device flow", audit=False)
    assert ok
    assert sent == [["tmux", "send-keys", "-t", "%7", "2"]]


def test_herdr_answer_does_not_submit(monkeypatch) -> None:
    sent = []
    monkeypatch.setattr(shep, "_run", lambda argv, **k: sent.append(argv) or SimpleNamespace(
        returncode=0, stdout="", stderr="",
    ))
    row = {"source": "herdr", "target": "herdr:w9:p1", "status": "asking", "label": "c"}
    assert shep.answer_session(row, "1", "Yes", audit=False)[0]
    assert "--no-submit" in sent[0]


@pytest.mark.parametrize(
    "row, choice",
    [
        ({"source": "tmux", "target": "%7", "status": "idle"}, "1"),
        ({"source": "tmux", "target": "%7", "status": "asking"}, "rm -rf /"),
    ],
    ids=["no-open-question", "not-an-option-key"],
)
def test_answer_refuses_anything_but_a_live_option_key(monkeypatch, row, choice) -> None:
    monkeypatch.setattr(shep, "_run", lambda *a, **k: pytest.fail("must not send"))
    ok, detail = shep.answer_session(row, choice, audit=False)
    assert not ok and detail


def test_answer_writes_an_audit_receipt(monkeypatch, tmp_path) -> None:
    ledger = tmp_path / "events.jsonl"
    monkeypatch.setenv("SHEP_ACTION_LOG", str(ledger))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="", stderr="",
    ))
    row = {"source": "tmux", "target": "%7", "status": "asking", "label": "claude"}
    assert shep.answer_session(row, "1", "Yes")[0]
    events = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [e["lifecycle"] for e in events] == ["intent", "answered"]
    assert all(e["action"] == "answer" for e in events)


# --- Headless sweep ----------------------------------------------------------


def _sweep_row(status="idle", quiet_for=shep.NUDGE_QUIET_SECONDS):
    # `quiet_for` is what the collectors attach from the pane's own change clock.
    # It defaults to "settled" here so each test states the one thing it is about;
    # the gate's own behaviour is covered by the pane_is_quiet tests.
    return {"source": "tmux", "id": "%9", "target": "%9", "label": "agent",
            "status": status, "cwd": "/tmp/repo", "quiet_for": quiet_for}


def _stub_draft(monkeypatch, text, context="line one"):
    monkeypatch.setattr(shep, "get_pane_context", lambda row, lines=15: context + "\n")
    monkeypatch.setattr(shep, "clean_context_lines", lambda ctx: [context])
    monkeypatch.setattr(
        shep, "llm_draft_nudge", lambda row, recent, attempt=1, **kwargs: text
    )


def _record_sends(monkeypatch, sink):
    def _send(row, text, **_kwargs):
        sink.append(text)
        return True, "ok"
    monkeypatch.setattr(shep, "send_nudge", _send)


def test_sweep_labels_autonomous_send_as_auto(monkeypatch) -> None:
    _stub_draft(monkeypatch, "Run pytest test_api.py.", "pytest failed in test_api.py")
    calls = []

    def fake_send(row, text, **kwargs):
        calls.append((row["target"], text, kwargs))
        return True, "ok"

    monkeypatch.setattr(shep, "send_nudge", fake_send)
    shep._NUDGE_STATE.clear()

    shep.sweep(send=True, rows=[_sweep_row()])

    assert calls == [
        (
            "%9",
            "Run pytest test_api.py.",
            {"mode": "auto", "engine": "operational", "path": "sweep"},
        ),
    ]


def test_sweep_dry_run_drafts_without_sending(monkeypatch) -> None:
    _stub_draft(monkeypatch, "continue with the failing test", "the failing test")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()
    results, held, _escalated = shep.sweep(send=False, rows=[_sweep_row()])
    assert [r[1] for r in results] == ["continue with the failing test"]
    assert held == []
    assert sent == []
    assert shep._nudge_state("%9")["proposed"]["context"] == "the failing test"


def test_sweep_send_holds_risky_drafts(monkeypatch) -> None:
    _stub_draft(monkeypatch, "delete from the stale sessions table")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()
    results, held, _escalated = shep.sweep(send=True, rows=[_sweep_row()])
    assert results == []
    assert sent == []
    # The held draft must be reviewable, not just counted.
    (row, text, category, reason), = held
    assert row["target"] == "%9"
    assert text == "delete from the stale sessions table"
    assert category == "destructive"
    assert reason


def test_sweep_sends_safe_continuation(monkeypatch) -> None:
    _stub_draft(monkeypatch, "continue and wrap up the migration", "the migration")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()
    results, held, _escalated = shep.sweep(send=True, rows=[_sweep_row()])
    assert sent == ["continue and wrap up the migration"]
    assert (len(results), held) == (1, [])


def test_scheduled_sweep_revalidates_before_sending_a_draft(monkeypatch) -> None:
    _stub_draft(monkeypatch, "continue with before", "before")
    snapshots = iter([[_sweep_row()], [{**_sweep_row(), "status": "working"}]])
    monkeypatch.setattr(shep, "collect_all", lambda: next(snapshots))
    monkeypatch.setattr(
        shep,
        "send_nudge",
        lambda *_args, **_kwargs: pytest.fail("stale scheduled draft was sent"),
    )

    results, held, _escalated = shep.sweep(send=True)

    assert held == []
    assert len(results) == 1
    assert results[0][2] is False
    assert "session is now working" in results[0][3]


# --- Cross-process nudge visibility ------------------------------------------
#
# The unattended sweep is a separate process that exits after each pass, so
# anything it leaves only in memory is invisible to the TUI the operator sits
# and watches. These pin the handoff between the two.

def test_a_held_draft_is_visible_to_the_operator_not_just_counted(
    monkeypatch,
) -> None:
    """The sweep's holds are what a human has to rule on, so they must surface.

    Held drafts used to live only in the loop's log file, which meant the fleet
    table showed "-" on precisely the rows waiting for a decision.
    """
    _stub_draft(monkeypatch, "delete from the stale sessions table")
    _record_sends(monkeypatch, [])
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()

    shep.sweep(send=True, rows=[_sweep_row()])

    assert shep.nudge_row_text(_sweep_row(), {}, {}, set(), set()) == (
        "HELD: delete from the stale sessions table"
    )
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_STATE.clear()


def test_nudge_events_survive_the_process_that_recorded_them(tmp_path) -> None:
    """A send in the sweep must still be on screen in a TUI started afterwards."""
    path = tmp_path / "state.json"
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "Run pytest tests/test_api.py.", "ok")
    shep.save_nudge_state({"%9"}, path=path)

    shep._NUDGE_EVENTS.clear()  # the TUI is a different process
    assert shep.nudge_row_text(_sweep_row(), {}, {}, set(), set()) == "-"

    shep.load_nudge_state(path=path)

    assert shep.nudge_row_text(_sweep_row(), {}, {}, set(), set()) == (
        "SENT: Run pytest tests/test_api.py."
    )
    assert shep.nudge_event_detail(_sweep_row()).startswith("last nudge · SENT")
    shep._NUDGE_EVENTS.clear()


def test_nudge_events_are_dropped_for_panes_that_no_longer_exist(tmp_path) -> None:
    """Same live-target filter as `sig`, so the file cannot grow without bound."""
    path = tmp_path / "state.json"
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "still here")
    shep.record_nudge_event("%dead", "sent", "pane is gone")

    shep.save_nudge_state({"%9"}, path=path)

    assert sorted(json.loads(path.read_text())["events"]) == ["%9"]
    shep._NUDGE_EVENTS.clear()


def test_state_is_never_left_half_written_for_the_other_process(tmp_path) -> None:
    """The sweep rewrites this file while the TUI reads it.

    A truncate-then-write leaves a window where the reader gets invalid JSON,
    and `load_nudge_state` treats a torn read exactly like a missing one -- it
    starts blank. That is the empty screen this file exists to prevent, and an
    intermittent one is worse than a permanent one. Also protects the fleet's
    ladder history from a crash landing mid-write.
    """
    path = tmp_path / "state.json"
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "first write")
    shep.save_nudge_state({"%9"}, path=path)

    shep.record_nudge_event("%9", "sent", "second write")
    shep.save_nudge_state({"%9"}, path=path)

    # Every observable state of the destination parses; no staging file is left
    # behind for the next reader to trip over.
    assert json.loads(path.read_text())["events"]["%9"]["text"] == "second write"
    assert list(tmp_path.glob("*.tmp")) == []
    shep._NUDGE_EVENTS.clear()


def test_an_approved_nudge_is_not_re_held_by_the_next_unattended_pass(
    monkeypatch, tmp_path
) -> None:
    """Approving from the pending queue has to resolve the item, not dispatch it.

    The TUI and the sweep are separate processes sharing one state file, and the
    TUI only ever read it. So the sweep never learned that a held draft the
    operator had approved was already sent: its dedupe history still said those
    words were unused, it redrafted them, the risk gate held them again, and the
    item the operator thought they had cleared was back in the queue minutes
    later — approving only ever dispatched, it never resolved.
    """
    path = tmp_path / "state.json"
    monkeypatch.setattr(shep, "NUDGE_STATE_FILE", path)
    monkeypatch.setattr(
        shep,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()
    text = "Run pytest tests/test_api.py -q."

    # Last night's sweep drafted this, held it for a human, and exited.
    shep.record_nudge_event("%9", "held", text, "merge needs a human")
    shep.save_nudge_state({"%9"}, path=path)
    assert shep.pending_actions([_sweep_row()])[0]["verb"] == "APPROVE"

    # The operator approves it in the TUI, which routes through the send path.
    shep._NUDGE_EVENTS.clear()
    ok, _detail = shep.send_nudge(
        {"source": "tmux", "target": "%9", "context": "pytest failed"},
        text, audit=False,
    )
    assert ok is True

    # The next pass is a fresh process: the file is everything it knows.
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()
    shep.load_nudge_state(path=path)

    assert shep._NUDGE_EVENTS["%9"]["status"] == "sent"
    assert shep.is_repeat_nudge(text, shep._nudge_state("%9")) is True
    assert shep.pending_actions([_sweep_row()]) == []
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()


def test_one_send_does_not_write_stale_state_over_the_rest_of_the_fleet(
    monkeypatch, tmp_path
) -> None:
    """Why a send persists one target instead of calling `save_nudge_state`.

    The TUI reads the ladder once at startup and then diverges from it for
    hours, so dumping its whole memory would put that startup snapshot over
    every pane the sweep has advanced since — undoing the escalation ladder for
    the rest of the fleet as the price of recording one send.
    """
    path = tmp_path / "state.json"
    monkeypatch.setattr(shep, "NUDGE_STATE_FILE", path)
    monkeypatch.setattr(
        shep,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()
    shep._nudge_state("%other")["attempt"] = 4
    shep.save_nudge_state({"%other"}, path=path)
    shep._NUDGE_STATE.clear()  # the TUI never saw that pane advance

    shep.send_nudge(
        {"source": "tmux", "target": "%9"}, "Run the tests.", audit=False,
    )

    written = json.loads(path.read_text())["nudge"]
    assert written["%other"]["attempt"] == 4
    assert written["%9"]["last_nudge"] == "Run the tests."
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()


def test_the_watched_screen_picks_up_a_later_sweep(tmp_path) -> None:
    """Loading once at startup made the fleet table a snapshot, not a feed.

    The operator watching shep would see whatever happened before they opened
    it and then nothing ever again, while the loop kept nudging behind the
    screen. This is the reload the refresh tick performs.
    """
    path = tmp_path / "state.json"
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "first pass")
    shep.save_nudge_state({"%9"}, path=path)
    shep._NUDGE_EVENTS.clear()
    shep.load_nudge_state(path=path)  # the TUI starts

    # ... and a later sweep, in its own process, sends something new.
    events_at_startup = dict(shep._NUDGE_EVENTS)
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "second pass")
    shep.save_nudge_state({"%9"}, path=path)
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_EVENTS.update(events_at_startup)

    assert "first pass" in shep.nudge_row_text(
        _sweep_row(), {}, {}, set(), set()
    )
    shep.load_nudge_state(path=path, events_only=True)  # the refresh tick
    assert "second pass" in shep.nudge_row_text(
        _sweep_row(), {}, {}, set(), set()
    )
    shep._NUDGE_EVENTS.clear()


def test_a_refresh_never_reverts_what_the_operator_just_did(tmp_path) -> None:
    """The TUI records its own sends into the same dict it reloads.

    A blind update would replace the event the operator just created with an
    older pass from the sweep -- their own action visibly undoing itself on
    screen a moment after they took it.
    """
    path = tmp_path / "state.json"
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "stale sweep pass")
    shep.save_nudge_state({"%9"}, path=path)

    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "sent", "what the operator just sent")

    shep.load_nudge_state(path=path, events_only=True)

    assert "what the operator just sent" in shep.nudge_row_text(
        _sweep_row(), {}, {}, set(), set()
    )
    shep._NUDGE_EVENTS.clear()


def test_an_events_only_reload_leaves_the_ladder_alone(tmp_path) -> None:
    """The TUI keeps its own drafting bookkeeping in the ladder dict.

    Re-merging the sweep's copy on every refresh tick would reset it mid-draft
    and put the same pane back through the drafter on a loop.
    """
    path = tmp_path / "state.json"
    shep._NUDGE_STATE.clear()
    shep._nudge_state("%9")["attempt"] = 3
    shep.save_nudge_state({"%9"}, path=path)

    shep._NUDGE_STATE.clear()
    shep._nudge_state("%9")["assessed_fingerprint"] = "mid-draft"

    shep.load_nudge_state(path=path, events_only=True)

    state = shep._nudge_state("%9")
    assert state["assessed_fingerprint"] == "mid-draft"
    assert state["attempt"] == 0
    shep._NUDGE_STATE.clear()


def test_the_detail_line_explains_the_rows_that_need_a_decision() -> None:
    """The fleet column truncates, and these two carry the long text.

    A hold carries the reason it was withheld; a handoff carries what only the
    operator can do. Selecting such a row to find out what is being asked used
    to answer nothing, because the detail line only knew about sends.
    """
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event(
        "%9", "needs human",
        detail="Only DevOps can confirm UDP port 10000 is open on the firewall.",
    )
    detail = shep.nudge_event_detail(_sweep_row())
    assert detail is not None
    assert "UDP port 10000" in detail
    assert "NEEDS HUMAN" in detail

    shep.record_nudge_event("%9", "held", "Merge MR 49.", "merges without review")
    assert "Merge MR 49." in shep.nudge_event_detail(_sweep_row())
    shep._NUDGE_EVENTS.clear()


def test_the_detail_line_stays_quiet_for_a_row_mid_flight() -> None:
    """A pane still being drafted for has nothing decided to report yet."""
    shep._NUDGE_EVENTS.clear()
    shep.record_nudge_event("%9", "drafting")
    assert shep.nudge_event_detail(_sweep_row()) is None
    shep._NUDGE_EVENTS.clear()


# --- Rate-limit recovery -----------------------------------------------------
#
# Taken from a real pane: two operator instructions in a row died on a provider
# 429, and the merge one of them asked for never happened. Nothing was wrong
# with the wording, so no drafting change could ever have recovered it.

_RATE_LIMITED_PANE = """\
› merge it in, force it through


■ exceeded retry limit, last status: 429 Too Many Requests
"""

_MOVED_ON_PANE = _RATE_LIMITED_PANE + """

› Explain this codebase
"""


def test_rate_limited_instruction_recovers_the_dropped_instruction() -> None:
    assert (
        shep.rate_limited_instruction(_RATE_LIMITED_PANE)
        == "merge it in, force it through"
    )


def test_rate_limited_instruction_takes_the_last_of_several_failures() -> None:
    pane = (
        "› first try\n\n■ exceeded retry limit, last status: 429 Too Many Requests\n"
        "\n› merge it, i approved it\n\n"
        "■ exceeded retry limit, last status: 429 Too Many Requests\n"
    )
    assert shep.rate_limited_instruction(pane) == "merge it, i approved it"


def test_rate_limited_instruction_stays_quiet_once_the_operator_moved_on() -> None:
    # A prompt after the error supersedes it. Re-sending here would run an
    # instruction the operator had already abandoned.
    assert shep.rate_limited_instruction(_MOVED_ON_PANE) is None


def test_rate_limited_instruction_ignores_a_pane_with_no_rate_limit() -> None:
    assert shep.rate_limited_instruction("› do the thing\n\nall done\n") is None


def test_rate_limited_instruction_does_not_mistake_output_for_a_prompt() -> None:
    # Diff and quoted-text lines start with `>` but nobody typed them.
    pane = (
        "› deploy the service\n\n"
        "> moved to staging\n"
        ">>> nested quote\n"
        "■ exceeded retry limit, last status: 429 Too Many Requests\n"
    )
    assert shep.rate_limited_instruction(pane) == "deploy the service"


def test_rate_limited_instruction_reads_the_claude_code_prompt_glyph() -> None:
    pane = "❯ finish the rebase\n\n■ 429 Too Many Requests\n"
    assert shep.rate_limited_instruction(pane) == "finish the rebase"


def _stub_rate_limited(monkeypatch, instruction, banner=""):
    pane = (
        f"› {instruction}\n\n"
        "■ exceeded retry limit, last status: 429 Too Many Requests\n"
        f"{banner}\n"
    )
    monkeypatch.setattr(shep, "get_pane_context", lambda row, lines=15: pane)
    monkeypatch.setattr(
        shep, "clean_context_lines",
        lambda _ctx: [instruction, "exceeded retry limit 429 Too Many Requests"],
    )

    def _never(*_args, **_kwargs):
        raise AssertionError("a rate-limit retry must not draft a new nudge")

    monkeypatch.setattr(shep, "llm_draft_nudge", _never)


def test_sweep_resends_the_instruction_a_rate_limit_dropped(monkeypatch) -> None:
    _stub_rate_limited(monkeypatch, "run the remaining migration checks")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()

    results, held, _escalated = shep.sweep(send=True, rows=[_sweep_row()])

    assert sent == ["run the remaining migration checks"]
    assert (len(results), held) == (1, [])


def test_sweep_holds_a_risky_instruction_the_rate_limit_dropped(monkeypatch) -> None:
    # The recovered text gets no privilege for having been human-typed: it goes
    # through the same gate a drafted nudge would.
    _stub_rate_limited(monkeypatch, "merge it in, force it through")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()

    results, held, _escalated = shep.sweep(send=True, rows=[_sweep_row()])

    assert (results, sent) == ([], [])
    (_row, text, category, _reason), = held
    assert text == "merge it in, force it through"
    assert category != "safe_continuation"


def test_sweep_keeps_retrying_a_rate_limit_past_the_bounded_ladder(
    monkeypatch,
) -> None:
    """A provider capacity outage keeps the pane moving with no attempt cap.

    Past `MAX_RATE_LIMIT_RETRIES` the ladder holds at its final rung instead of
    handing the pane to a human — this is the one ladder in shep that never
    exhausts, on the operator's call: they would rather it keep resending the
    dropped instruction unattended than stall on a 429 nobody's watching.
    """
    _stub_rate_limited(monkeypatch, "run the remaining migration checks")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()
    row = _sweep_row()

    attempts = shep.MAX_RATE_LIMIT_RETRIES + 2
    for _ in range(attempts):
        shep._nudge_state("%9")["next_at"] = 0.0
        shep.sweep(send=True, rows=[row])

    assert len(sent) == attempts
    assert shep._nudge_state("%9")["exhausted_reason"] is None
    assert shep._nudge_state("%9")["rate_limit_retries"] == attempts


def test_sweep_backs_off_before_retrying_a_rate_limit(monkeypatch) -> None:
    # Retrying a quota failure on the nudge ladder's 60s cadence just spends the
    # same quota again, so the wait is the rate-limit schedule, not the ladder.
    assert shep.RATE_LIMIT_BACKOFF_SECONDS[0] >= max(shep.NUDGE_BACKOFF_SECONDS)
    _stub_rate_limited(monkeypatch, "run the remaining migration checks")
    _record_sends(monkeypatch, [])
    shep._NUDGE_STATE.clear()

    shep.sweep(send=True, rows=[_sweep_row()])

    wait = shep._nudge_state("%9")["next_at"] - time.time()
    assert wait == pytest.approx(shep.RATE_LIMIT_BACKOFF_SECONDS[0], abs=5)


# The ladder above is a guess. When the banner says when the window reopens,
# the guess is strictly worse than what it says — in both directions.

def test_quota_reset_wait_reads_a_relative_banner() -> None:
    banner, wait = shep.quota_reset_wait(
        "■ 429 Too Many Requests\nYou've hit your usage limit. Try again in 2h 14m.\n"
    )
    assert banner == "Try again in 2h 14m"
    assert wait == 2 * 3600 + 14 * 60 + shep.QUOTA_RESET_GRACE_SECONDS


def test_quota_reset_wait_reads_a_clock_time_banner() -> None:
    now = time.mktime((2026, 8, 6, 13, 0, 0, 0, 0, -1))
    banner, wait = shep.quota_reset_wait(
        "5-hour limit reached ∙ resets 3pm\n", now=now
    )
    assert banner == "resets 3pm"
    assert wait == 2 * 3600 + shep.QUOTA_RESET_GRACE_SECONDS


def test_quota_reset_wait_carries_a_clock_time_over_midnight() -> None:
    now = time.mktime((2026, 8, 6, 23, 30, 0, 0, 0, -1))
    _banner, wait = shep.quota_reset_wait("resets at 01:00\n", now=now)
    assert wait == 90 * 60 + shep.QUOTA_RESET_GRACE_SECONDS


def test_quota_reset_wait_ignores_a_banner_that_states_no_time() -> None:
    assert shep.quota_reset_wait(_RATE_LIMITED_PANE) is None
    # "resets 5" without `:MM` or am/pm is indistinguishable from "resets 5
    # minutes"; reading it as five o'clock would park a live pane until tomorrow.
    assert shep.quota_reset_wait("rate limited, resets 5 minutes from now") is None


def test_sweep_waits_for_the_reset_time_the_quota_banner_states(monkeypatch) -> None:
    _stub_rate_limited(
        monkeypatch, "run the remaining migration checks",
        banner="You've hit your usage limit. Try again in 2h 14m.",
    )
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()

    results, held, _escalated = shep.sweep(send=True, rows=[_sweep_row()])

    assert (results, held, sent) == ([], [], [])
    wait = shep._nudge_state("%9")["next_at"] - time.time()
    assert wait == pytest.approx(
        2 * 3600 + 14 * 60 + shep.QUOTA_RESET_GRACE_SECONDS, abs=5
    )
    # Holding is not giving up: the retry budget is untouched, so the resend
    # still has its full ladder once the window reopens.
    assert shep._nudge_state("%9").get("rate_limit_retries", 0) == 0
    assert shep._nudge_state("%9")["exhausted_reason"] is None


def test_sweep_does_not_reread_a_reset_time_that_has_already_passed(
    monkeypatch,
) -> None:
    _stub_rate_limited(
        monkeypatch, "run the remaining migration checks",
        banner="5-hour limit reached ∙ resets 3pm",
    )
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()

    shep.sweep(send=True, rows=[_sweep_row()])
    assert sent == []

    # The window has reopened, but the pane still reads "resets 3pm" — it is a
    # static capture, not a clock. Re-parsing it here would roll the wait forward
    # a full day for a quota that is already back.
    state = shep._nudge_state("%9")
    state["next_at"] = 0.0
    state["quota_hold"]["until"] = time.time() - 1

    shep.sweep(send=True, rows=[_sweep_row()])
    assert sent == ["run the remaining migration checks"]


# `rate_limit_recovery` is the shared unit both nudge lanes call. The sweep tests
# above cover it through the sweep; these cover it directly, because the TUI's
# drafter — the lane that had no recovery at all until now — is a closure inside
# the curses loop that early-returns in fixture mode and cannot be driven here.

def _rate_limited_pane(instruction, banner=""):
    return (
        f"› {instruction}\n\n"
        "■ exceeded retry limit, last status: 429 Too Many Requests\n"
        f"{banner}\n"
    )


def test_rate_limit_recovery_leaves_an_ordinary_pane_to_the_drafter() -> None:
    """No 429 in the pane means no recovery, and no state touched either."""
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    row = _sweep_row()

    assert shep.rate_limit_recovery(row, state, "› do the thing\n\nall done\n", []) == (
        None, None,
    )
    assert state.get("rate_limit_retries", 0) == 0
    assert state.get("proposed") is None


def test_rate_limit_recovery_hands_back_the_instruction_verbatim() -> None:
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    row = _sweep_row()
    now = 1_000_000.0

    text, suppressed = shep.rate_limit_recovery(
        row, state, _rate_limited_pane("merge it in, force it through"),
        ["merge it in, force it through"], now=now,
    )

    # Recovered, not reworded: the operator's instruction was correct, it simply
    # never ran.
    assert (text, suppressed) == ("merge it in, force it through", None)
    assert state["proposed"]["text"] == "merge it in, force it through"
    assert state["proposed"]["status"] == "queued"
    # A quota-blocked pane is held, never wedged — only pane movement may set
    # `exhausted_reason`.
    assert state.get("exhausted_reason") is None


def test_rate_limit_recovery_pushes_the_cooldown_out_on_every_attempt() -> None:
    """This is what stops the TUI's 5-second redraw from spending the ladder.

    `should_nudge` reads `next_at`, so each recovery has to park the pane for the
    whole rung. Without it the interactive lane would burn all three attempts
    inside fifteen seconds of a pane sitting on screen.
    """
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    now = 1_000_000.0
    pane = _rate_limited_pane("run the migration checks")

    waits = []
    for _attempt in range(shep.MAX_RATE_LIMIT_RETRIES):
        text, _suppressed = shep.rate_limit_recovery(
            _sweep_row(), state, pane, ["run the migration checks"], now=now,
        )
        assert text == "run the migration checks"
        waits.append(state["next_at"] - now)

    assert waits == list(shep.RATE_LIMIT_BACKOFF_SECONDS)


def test_rate_limit_recovery_holds_the_final_rung_once_the_ladder_is_spent() -> None:
    """A provider capacity outage must never exhaust to a human handoff.

    Past the ladder's last rung, shep keeps resending the dropped instruction
    on a fixed cadence — it does not write `exhausted_reason` and stop, which
    would strand the session until an operator noticed and resent by hand.
    """
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    state["rate_limit_retries"] = shep.MAX_RATE_LIMIT_RETRIES

    text, suppressed = shep.rate_limit_recovery(
        _sweep_row(), state, _rate_limited_pane("deploy the service"),
        ["deploy the service"], now=1_000_000.0,
    )

    assert (text, suppressed) == ("deploy the service", None)
    assert state.get("exhausted_reason") is None
    assert state["next_at"] - 1_000_000.0 == shep.RATE_LIMIT_BACKOFF_SECONDS[-1]
    assert state["rate_limit_retries"] == shep.MAX_RATE_LIMIT_RETRIES + 1


def test_an_unpersisted_ladder_keeps_retrying_past_its_length_too() -> None:
    """The TUI's non-persisted lane gets the same unbounded retry as the sweep.

    Nothing here writes a per-session count as a verdict only a restart could
    revoke — `exhausted_reason` stays clear either way, so there is nothing
    left for a restart to strand.
    """
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    state["rate_limit_retries"] = shep.MAX_RATE_LIMIT_RETRIES
    row = _sweep_row()

    text, suppressed = shep.rate_limit_recovery(
        row, state, _rate_limited_pane("deploy the service"),
        ["deploy the service"], now=1_000_000.0, persisted=False,
    )

    assert (text, suppressed) == ("deploy the service", None)
    assert state.get("exhausted_reason") is None
    assert state["next_at"] - 1_000_000.0 == shep.RATE_LIMIT_BACKOFF_SECONDS[-1]
    assert state["rate_limit_retries"] == shep.MAX_RATE_LIMIT_RETRIES + 1
    # What ends the retries is the 429 ceasing to be the pane's last word:
    # there is then nothing to recover, and `(None, None)` hands the pane back
    # to the ordinary drafter.
    assert shep.rate_limit_recovery(
        row, state, _MOVED_ON_PANE, ["moved on"], persisted=False,
    ) == (None, None)


def test_rate_limit_recovery_waits_out_a_banner_that_states_its_own_reset() -> None:
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    now = 1_000_000.0

    text, suppressed = shep.rate_limit_recovery(
        _sweep_row(), state,
        _rate_limited_pane("finish the rebase", "Try again in 2h 14m."),
        ["finish the rebase"], now=now,
    )

    assert (text, suppressed) == (None, "quota_resets_later")
    assert state["next_at"] - now == (
        2 * 3600 + 14 * 60 + shep.QUOTA_RESET_GRACE_SECONDS
    )
    # Frozen on first sight. The pane capture is static, so re-reading the same
    # banner later would roll the deadline forward again and again.
    assert state["quota_hold"]["banner"] == "Try again in 2h 14m"
    assert state["quota_hold"]["until"] == state["next_at"]
    # Holding is not giving up: the resend keeps its full ladder for when the
    # window reopens.
    assert state.get("rate_limit_retries", 0) == 0


def test_rate_limit_recovery_ignores_a_banner_it_cannot_freeze() -> None:
    """A caller whose state does not persist must not read a stale banner.

    `run_tui` never loads or saves nudge state, so it starts every launch with
    an empty `quota_hold`. Trusting the banner there would re-parse "resets 3pm"
    at half past three as a wait until tomorrow and take a live pane out of the
    nudge loop for a day — the exact hazard the freeze exists to prevent, minus
    the freeze. Such a caller falls through to the bounded ladder instead.
    """
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    now = 1_000_000.0

    text, suppressed = shep.rate_limit_recovery(
        _sweep_row(), state,
        _rate_limited_pane("finish the rebase", "5-hour limit reached ∙ resets 3pm"),
        ["finish the rebase"], now=now, persisted=False,
    )

    assert (text, suppressed) == ("finish the rebase", None)
    assert state.get("quota_hold") is None
    assert state["next_at"] - now == shep.RATE_LIMIT_BACKOFF_SECONDS[0]


def test_should_nudge_is_false_for_the_whole_rung_after_a_recovery() -> None:
    """The bound on the TUI's 5-second redraw, asserted at the gate itself.

    The recovery ladder is only bounded because `should_nudge` reads `next_at`.
    Every other test here asserts the arithmetic; this one asserts the gate
    actually consumes it, so dropping that clause cannot stay green.
    """
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    row = _sweep_row()

    text, _suppressed = shep.rate_limit_recovery(
        row, state, _rate_limited_pane("run the migration checks"),
        ["run the migration checks"], persisted=False,
    )

    assert text == "run the migration checks"
    assert shep.should_nudge(row, state) is False


def test_rate_limit_recovery_still_holds_a_dangerous_instruction() -> None:
    """Recovered text is not pre-approved text — it faces the same risk gate."""
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    row = _sweep_row()

    text, _suppressed = shep.rate_limit_recovery(
        row, state, _RATE_LIMITED_PANE, ["merge it in, force it through"],
    )

    assert text == "merge it in, force it through"
    assert state["proposed"]["category"] == "merge"
    assert shep.nudge_hold_reason(text, row.get("context"))
    # And it cannot slip through a bulk send on the strength of having no judge
    # score, which is what a recovery lacks.
    candidates, held = shep.bulk_nudge_candidates(
        [row], {"%9": text}, {}, {}, {},
    )
    assert (candidates, held) == ([], 1)


def test_rate_limit_recovery_leaves_the_row_context_alone_when_it_has_none() -> None:
    """The TUI can hand over an empty capture; sweep never can."""
    shep._NUDGE_STATE.clear()
    row = _sweep_row()
    row["context"] = "the last thing we knew"

    text, _suppressed = shep.rate_limit_recovery(
        row, shep._nudge_state("%9"), _rate_limited_pane("deploy it"), [],
    )

    assert text == "deploy it"
    assert row["context"] == "the last thing we knew"


def test_rate_limit_recovery_does_not_disturb_the_drafting_machinery() -> None:
    """It runs ahead of the fingerprint and dedupe lanes; it must not feed them."""
    shep._NUDGE_STATE.clear()
    state = shep._nudge_state("%9")
    state["assessed_fingerprint"] = "abc123"
    state["attempt"] = 1
    state["prior_nudges"] = ["an earlier nudge"]

    shep.rate_limit_recovery(
        _sweep_row(), state, _rate_limited_pane("resume the build"),
        ["resume the build"],
    )

    assert state["assessed_fingerprint"] == "abc123"
    assert state["attempt"] == 1
    assert state["prior_nudges"] == ["an earlier nudge"]


def test_sweep_routes_its_rate_limit_recovery_through_the_shared_unit(
    monkeypatch,
) -> None:
    """The extraction is only DRY if the sweep still calls it.

    Every other rate-limit test here would stay green against a sweep that had
    quietly kept its own inline copy, or against a signature that had drifted.
    """
    _stub_rate_limited(monkeypatch, "run the remaining migration checks")
    calls = []

    def _recovery(row, state, pane_text, recent, **kwargs):
        calls.append(kwargs)
        # The real unit grounds the row in the capture it recovered from; the
        # quality gate downstream reads that, so the stub has to as well. That
        # coupling is asserted elsewhere, not here — this test would stay green
        # if the real unit stopped setting it and every recovery began to hold.
        row["context"] = "\n".join(recent[-4:])
        # The suffix is what neither an inline copy nor the real unit could
        # produce, so a sweep that reverted to its own logic fails on `sent`.
        return "run the remaining migration checks again", None

    monkeypatch.setattr(shep, "rate_limit_recovery", _recovery)
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()

    shep.sweep(send=True, rows=[_sweep_row()])

    # No kwargs: the sweep persists nudge state, so it must take the default and
    # trust the banner freeze.
    assert calls == [{}]
    assert sent == ["run the remaining migration checks again"]


def test_sweep_does_not_redraft_an_explicit_abstention_without_context_change(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr(shep, "get_pane_context", lambda *_args, **_kwargs: "waiting\n")
    monkeypatch.setattr(shep, "clean_context_lines", lambda _ctx: ["waiting"])

    def abstain(*_args, **_kwargs):
        calls.append("drafted")
        return "NO_NUDGE"

    monkeypatch.setattr(shep, "llm_draft_nudge", abstain)
    shep._NUDGE_STATE.clear()
    row = _sweep_row()

    shep.sweep(send=True, rows=[row])
    shep.sweep(send=True, rows=[row])

    assert calls == ["drafted"]
    assert shep._nudge_state(row["target"])["exhausted_reason"] == "abstained"


def test_sweep_does_not_regenerate_a_duplicate_without_context_change(
    monkeypatch,
) -> None:
    calls = []
    prior = "Run pytest on test_sessions.py and fix the failures."
    repeated = "Fix the test_sessions.py failures by running pytest."
    monkeypatch.setattr(
        shep, "get_pane_context", lambda *_args, **_kwargs: "3 failed in test_sessions.py\n"
    )
    monkeypatch.setattr(
        shep, "clean_context_lines", lambda _ctx: ["3 failed in test_sessions.py"]
    )

    def duplicate(*_args, **_kwargs):
        calls.append("drafted")
        return repeated

    monkeypatch.setattr(shep, "llm_draft_nudge", duplicate)
    shep._NUDGE_STATE.clear()
    row = _sweep_row()
    shep.remember_nudge(shep._nudge_state(row["target"]), prior)

    shep.sweep(send=True, rows=[row])
    shep.sweep(send=True, rows=[row])

    assert calls == ["drafted"]
    assert shep._nudge_state(row["target"])["exhausted_reason"] == "duplicate"


def test_sweep_requires_new_evidence_beyond_its_own_visible_nudge(monkeypatch) -> None:
    calls = []
    prior = "Run `git status` and inspect the diff for changes."
    monkeypatch.setattr(
        shep, "get_pane_context", lambda *_args, **_kwargs: prior + "\n"
    )
    monkeypatch.setattr(shep, "clean_context_lines", lambda ctx: [ctx.strip()])
    monkeypatch.setattr(
        shep,
        "llm_draft_nudge",
        lambda *_args, **_kwargs: calls.append("drafted") or "Run pytest.",
    )
    shep._NUDGE_STATE.clear()
    row = _sweep_row()
    state = shep._nudge_state(row["target"])
    shep.remember_nudge(state, prior)
    state["proposed"] = {"text": prior, "status": "sent"}

    results, held, _escalated = shep.sweep(send=True, rows=[row])

    assert calls == []
    assert results == []
    assert held == []
    assert state["exhausted_reason"] == "no_new_evidence"


def test_sweep_does_not_treat_earlier_unchanged_lines_as_new_evidence(
    monkeypatch,
) -> None:
    context = "\n".join(f"unchanged line {index}" for index in range(8))
    calls = []
    monkeypatch.setattr(shep, "get_pane_context", lambda *_args, **_kwargs: context)
    monkeypatch.setattr(
        shep,
        "llm_draft_nudge",
        lambda *_args, **_kwargs: calls.append("drafted") or "Run pytest.",
    )
    monkeypatch.setattr(shep, "send_nudge", lambda *_args, **_kwargs: (True, "ok"))
    shep._NUDGE_STATE.clear()
    row = _sweep_row()

    shep.sweep(send=True, rows=[row])
    shep._nudge_state(row["target"])["next_at"] = 0.0
    shep.sweep(send=True, rows=[row])

    assert calls == ["drafted"]
    assert shep._nudge_state(row["target"])["exhausted_reason"] == "no_new_evidence"


def test_sweep_bounds_gateway_failures_without_calling_them_abstentions(monkeypatch) -> None:
    calls = []
    now = [1000.0]
    monkeypatch.setattr(shep.time, "time", lambda: now[0])
    monkeypatch.setattr(shep, "get_pane_context", lambda *_args, **_kwargs: "pytest failed\n")
    monkeypatch.setattr(shep, "clean_context_lines", lambda _ctx: ["pytest failed"])
    monkeypatch.setattr(
        shep,
        "llm_draft_nudge",
        lambda *_args, **_kwargs: calls.append("failed") or None,
    )
    shep._NUDGE_STATE.clear()
    row = _sweep_row()

    for delay in (0, 301, 1801, 7201):
        now[0] += delay
        shep.sweep(send=True, rows=[row])

    state = shep._nudge_state(row["target"])
    assert calls == ["failed", "failed", "failed"]
    assert state["draft_failures"] == shep.MAX_DRAFT_FAILURES
    assert state["exhausted_reason"] == "draft_unavailable"


def test_sweep_retries_transport_without_redrafting_and_then_exhausts(monkeypatch) -> None:
    now = [1000.0]
    drafts = []
    sends = []
    monkeypatch.setattr(shep.time, "time", lambda: now[0])
    monkeypatch.setattr(
        shep, "get_pane_context", lambda *_args, **_kwargs: "pytest failed in test_api.py"
    )
    monkeypatch.setattr(
        shep,
        "llm_draft_nudge",
        lambda *_args, **_kwargs: drafts.append("draft") or "Run pytest test_api.py.",
    )
    monkeypatch.setattr(
        shep,
        "send_nudge",
        lambda *_args, **_kwargs: sends.append("send") or (False, "transport failed"),
    )
    shep._NUDGE_STATE.clear()
    row = _sweep_row()

    for delay in (0, 301, 1801, 7201):
        now[0] += delay
        shep.sweep(send=True, rows=[row])

    state = shep._nudge_state(row["target"])
    assert drafts == ["draft"]
    assert sends == ["send"] * shep.MAX_SEND_FAILURES
    assert state["send_failures"] == shep.MAX_SEND_FAILURES
    assert state["exhausted_reason"] == "send_failed"


def test_transport_timeout_is_delivery_unknown_and_not_auto_retried(monkeypatch) -> None:
    monkeypatch.setattr(
        shep,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=124, stdout="", stderr="timed out"
        ),
    )
    shep._NUDGE_STATE.clear()

    ok, detail = shep.send_nudge(
        {"source": "tmux", "target": "%9", "status": "idle"},
        "continue with the verification",
        audit=False,
    )

    assert not ok
    assert detail.startswith("delivery unknown:")
    assert shep._nudge_state("%9")["exhausted_reason"] == "delivery_unknown"


def test_snapshot_separates_location_happiness_status_and_nudge(monkeypatch) -> None:
    shep._NUDGE_STATE.clear()
    monkeypatch.setattr(shep, "load_nudge_state", lambda *args, **kwargs: True)
    shep._nudge_state("herdr:w1:p1").update({
        "attempt": 1,
        "proposed": {
            "text": "continue the focused verification",
            "status": "queued",
            "category": "safe_continuation",
        },
    })
    monkeypatch.setattr(shep, "_happy_daemon_sessions", lambda: [])
    payload = shep.snapshot_payload([
        {
            "source": "herdr", "target": "herdr:w1:p1",
            "label": "happy-codex", "status": "idle",
            "context": "the focused verification is next",
            "reap_ready": False,
        },
        {
            "source": "tmux", "target": "%2",
            "label": "plain", "status": "working",
            "reap_ready": False,
        },
    ])
    assert payload["counts"] == {
        "panels": 2, "in_herdr": 1, "outside_herdr": 1,
        "happy": 1, "not_happy": 1, "working": 1, "idle": 1,
        "blocked": 0, "unobserved": 0, "reap_ready": 0,
        "nudge_proposed": 1, "nudge_held": 0, "nudge_sent": 0,
        "nudge_sent_unresolved": 0,
        "nudge_needs_human": 0,
    }
    happy, plain = payload["panels"]
    assert happy["happiness"] == "happy"
    assert happy["shep_status"] == "idle"
    assert happy["nudge"]["status"] == "queued"
    assert plain["happiness"] == "not_happy"
    assert plain["shep_status"] == "working"


def test_snapshot_exposes_successful_send_as_unresolved_until_progress(monkeypatch) -> None:
    shep._NUDGE_STATE.clear()
    monkeypatch.setattr(shep, "load_nudge_state", lambda *args, **kwargs: True)
    monkeypatch.setattr(shep, "_happy_daemon_sessions", lambda: [])
    shep._nudge_state("herdr:worker").update({
        "last_sent": {
            "text": "Run pytest test_api.py.",
            "status": "sent",
            "context": "pytest failed in test_api.py",
        },
        "proposed": {
            "text": "Run pytest test_api.py.",
            "status": "sent",
            "context": "pytest failed in test_api.py",
        },
    })

    payload = shep.snapshot_payload([{
        "source": "herdr",
        "target": "herdr:worker",
        "label": "worker",
        "status": "idle",
        "context": "pytest failed in test_api.py",
    }])

    assert payload["panels"][0]["nudge"]["status"] == "sent_unresolved"
    assert payload["counts"]["nudge_sent_unresolved"] == 1


def test_snapshot_derives_held_state_for_stale_queued_proposals(monkeypatch) -> None:
    shep._NUDGE_STATE.clear()
    monkeypatch.setattr(shep, "load_nudge_state", lambda *args, **kwargs: True)
    monkeypatch.setattr(shep, "_happy_daemon_sessions", lambda: [])
    shep._nudge_state("herdr:generic").update({
        "proposed": {
            "text": "Continue the current objective and keep going.",
            "status": "queued",
            "category": "safe_continuation",
        },
    })
    shep._nudge_state("herdr:risky").update({
        "proposed": {
            "text": "Delete the stale sessions table.",
            "status": "queued",
            "category": "destructive",
        },
    })

    payload = shep.snapshot_payload([
        {
            "source": "herdr", "target": "herdr:generic", "status": "idle",
            "context": "waiting at the input prompt",
        },
        {
            "source": "herdr", "target": "herdr:risky", "status": "idle",
            "context": "waiting at the input prompt",
        },
    ])

    generic, risky = payload["panels"]
    assert generic["nudge"]["status"] == "held"
    assert "generic continuation" in generic["nudge"]["reason"]
    assert risky["nudge"]["status"] == "held"
    assert risky["nudge"]["category"] == "destructive"
    assert payload["counts"]["nudge_proposed"] == 0
    assert payload["counts"]["nudge_held"] == 2
    # Snapshot presentation is read-only; persistence is handled by sweep.
    assert shep._nudge_state("herdr:generic")["proposed"]["status"] == "queued"


def test_snapshot_uses_the_context_that_produced_a_gated_proposal(monkeypatch) -> None:
    shep._NUDGE_STATE.clear()
    monkeypatch.setattr(shep, "load_nudge_state", lambda *args, **kwargs: True)
    monkeypatch.setattr(shep, "_happy_daemon_sessions", lambda: [])
    shep._nudge_state("herdr:worker").update({
        "proposed": {
            "text": "Verify the strategy config imports after the package split.",
            "status": "queued",
            "category": "safe_continuation",
            "context": "strategy config package split completed",
        },
    })

    payload = shep.snapshot_payload([{
        "source": "herdr", "target": "herdr:worker", "status": "idle",
        "context": "Press space to switch to local mode",
    }])

    assert payload["panels"][0]["nudge"]["status"] == "queued"


def test_snapshot_marks_headless_happy_as_unobserved(monkeypatch) -> None:
    shep._NUDGE_STATE.clear()
    monkeypatch.setattr(shep, "load_nudge_state", lambda *args, **kwargs: True)
    monkeypatch.setattr(shep, "_happy_daemon_sessions", lambda: [{
        "source": "happy", "target": "happy:abc123",
        "label": "happy-abc123", "status": "unobserved",
        "shep_status": "outside_herdr", "in_herdr": False,
        "happiness": "happy", "happy_session_id": "abc123",
        "reap_ready": False,
        "nudge": None,
    }])
    payload = shep.snapshot_payload([])
    (panel,) = payload["panels"]
    assert panel["status"] == "unobserved"
    assert panel["shep_status"] == "outside_herdr"
    assert panel["nudge"]["status"] == "unobserved"
    assert panel["nudge"]["text"] is None


def test_sweep_skips_shell_panes(monkeypatch) -> None:
    _stub_draft(monkeypatch, "continue")
    shep._NUDGE_STATE.clear()
    results, held, _escalated = shep.sweep(send=False, rows=[_sweep_row(status="shell")])
    assert (results, held) == ([], [])


# Claude Code / Codex draw a status footer BELOW the input box, so the ready
# prompt is never the final line. Checking only lines[-1] reported every idle
# agent as "working", which kept idle panes out of NUDGEABLE entirely.
_IDLE_CLAUDE_PANE = (
    "  ⎿  wrote 3 files\n"
    "❯ \n"
    "────────────────────────\n"
    "  Opus 5 | med | developer | ContextQ:--\n"
    "  Eff:--\n"
    "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← 2 agents\n"
)


def test_idle_agent_below_status_footer_is_idle(monkeypatch) -> None:
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: _IDLE_CLAUDE_PANE)
    status, _cues, _ctx = shep._tmux_pane_state("%173")
    assert status == "idle"
    assert status in shep.NUDGEABLE


def test_thinking_agent_with_input_box_stays_working(monkeypatch) -> None:
    pane = _IDLE_CLAUDE_PANE.replace("  Eff:--", "  ✻ Thinking… (esc to interrupt)")
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane)
    assert shep._tmux_pane_state("%174")[0] == "working"


# --- Loop-3: mission decisions reach the learner ------------------------------
#
# sense -> recommend -> launch were wired; mission-learn was built, tested, and
# orphaned — nothing wrote its ledger, so the deck could never learn from what
# was actually taken.


def test_sense_contributions_merge_across_decks(tmp_path, monkeypatch) -> None:
    """Build and research decks run sense separately; the second must not erase
    the first's projects, or half the deck loses its attribution."""
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "MISSION_SENSE_CACHE", tmp_path / "sense.json")
    for name in ("alpha", "beta"):
        shep._cache_sense_contributions(json.dumps(
            {"projects": [{"name": name, "weighted_contributions": {"ready_backlog": 28.0}}]}
        ))
    assert sorted(shep.mission_drivers_map()) == ["alpha", "beta"]


def test_record_mission_decision_passes_drivers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "MISSION_SENSE_CACHE", tmp_path / "sense.json")
    learner = tmp_path / "learn.py"
    learner.touch()
    monkeypatch.setattr(shep, "MISSION_LEARN_SCRIPT", learner)
    shep._cache_sense_contributions(json.dumps(
        {"projects": [{"name": "alpha", "weighted_contributions": {"stale_branches": 10.0}}]}
    ))
    seen = {}

    def _fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shep, "_run", _fake_run)
    assert shep.record_mission_decision(
        "dismiss", {"id": "m1", "project_name": "alpha", "momentum_score": 52.6}
    )
    assert "--event" in seen["cmd"] and "dismiss" in seen["cmd"]
    assert json.loads(seen["cmd"][seen["cmd"].index("--drivers") + 1]) == {"stale_branches": 10.0}


def test_record_mission_decision_survives_missing_learner(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shep, "MISSION_LEARN_SCRIPT", tmp_path / "absent.py")
    assert shep.record_mission_decision("accept", {"id": "m1"}) is False


# --- Negation-aware risk classification --------------------------------------
#
# "do not merge the MR" scored identically to "merge the MR": the filter matched
# the verb and never saw the negator. Over half of one live review queue was
# nudges held for telling an agent NOT to do the risky thing. Negation now
# downgrades the matched risk to a human review (`unknown`) — but it must never
# PROMOTE a draft to `safe_continuation`, because "remember not to skip the
# merge; proceed" read the real instruction as safe by double negation.


@pytest.mark.parametrize(
    "text",
    [
        "Assign reviewers to MR !1, then stop — do not merge the MR.",
        "Don't merge the MR or alter approval rules; it stays blocked. Stop here.",
        "Never deploy this yourself. Stop and wait.",
        "Continue without a git push.",
    ],
)
def test_negated_risky_verbs_are_not_risks(text) -> None:
    # A negated risk is held for a human (`unknown`), never auto-sent.
    assert shep.classify_risk(text)[0] == "unknown"


@pytest.mark.parametrize(
    "text",
    [
        "Merge the MR once CI is green.",
        # Negation must not leak across a clause boundary into a real instruction.
        "Don't wait for approval. Rotate the key and git push.",
        "Do not stop; delete from the sessions table.",
    ],
)
def test_real_instructions_still_classify_as_risky(text) -> None:
    assert shep.classify_risk(text)[0] not in ("safe_continuation", "unknown")


def test_negation_does_not_blanket_clear_other_risks() -> None:
    """One negated risk must not excuse a second, real one in the same draft."""
    category, _reason = shep.classify_risk("Do not merge the MR — just git push it.")
    assert category == "push"


# --- Fail-closed classifier: the five confirmed auto-send bypasses -----------
#
# Each of these returned `safe_continuation` — i.e. AUTO-SENT — on the live
# sweep. The classifier is the only thing between an LLM draft and an
# unattended keystroke into a live repo, so the default is now fail-closed:
# anything not provably benign is `unknown` and waits for a human.


@pytest.mark.parametrize(
    "text",
    [
        "Run the merge of MR !2 into main once CI is green.",
        "Run the force push to origin main.",
        "Run the deletion of the stale table.",
        "Finish the rotation of the API key.",
        "Verify then do a hard reset of the branch.",
    ],
)
def test_nominalized_risky_actions_are_not_safe_continuations(text) -> None:
    """Nominalizing the action hid it from every verb-shaped risk pattern, and
    the harmless leading verb ("Run", "Finish") then UPGRADED the draft from
    `unknown` (blocked) to `safe_continuation` (auto-send)."""
    assert shep.classify_risk(text)[0] != "safe_continuation"


@pytest.mark.parametrize(
    "text",
    [
        "Continue by merging the MR.",
        "Next task: merging the MR into main.",
        "pushing the branch to origin",
    ],
)
def test_gerund_risky_actions_are_not_safe_continuations(text) -> None:
    assert shep.classify_risk(text)[0] != "safe_continuation"


def test_new_mission_tail_with_risk_never_auto_sends() -> None:
    """classify_risk scored only the text before NEW_MISSION:, but send_nudge
    transmits the whole string — this exact draft scored safe and the sweep
    would have typed the recursive delete and the table wipe into a live pane."""
    text = "Wrap up. NEW_MISSION: rm -rf the build dir and truncate the sessions table."
    assert shep.classify_risk(text)[0] != "safe_continuation"
    assert shep.nudge_hold_reason(text, text) is not None
    sql = "Wrap up. NEW_MISSION: delete from the sessions table."
    assert shep.classify_risk(sql)[0] != "safe_continuation"
    assert shep.nudge_hold_reason(sql, sql) is not None


@pytest.mark.parametrize(
    "text",
    [
        # U+00AD soft hyphen inside "merge" — invisible, but the terminal
        # renders the real word.
        "Keep going - mer\u00adge the MR.",
        # U+200B zero-width space inside "git".
        "Continue: g\u200bit push origin main",
        # U+FF50 fullwidth "p" starting "push".
        "Proceed to \uff50ush the branch.",
    ],
)
def test_unicode_and_zero_width_evasion_is_classified(text) -> None:
    assert shep.classify_risk(text)[0] != "safe_continuation"


def test_double_negation_does_not_promote_to_safe() -> None:
    """Negation may DOWNGRADE a matched risk to needs-review; it must never
    PROMOTE a draft to `safe_continuation`."""
    text = "Remember not to skip the merge of the MR; proceed."
    assert shep.classify_risk(text)[0] != "safe_continuation"


def test_safe_continuation_requires_whole_draft_benign() -> None:
    assert shep.classify_risk("Continue; then the MR merge into main.")[0] != (
        "safe_continuation"
    )


@pytest.mark.parametrize(
    "text",
    [
        "Run pytest and inspect the first failure.",
        "Continue with the next task.",
        "Fix the failing assertion in test_collect_herdr and rerun.",
        "Verify the report renders, then stop.",
    ],
)
def test_genuine_safe_continuations_still_pass(text) -> None:
    """Regression guard: provably benign continuations must keep auto-sending,
    or the human review queue drowns and the gate gets bypassed."""
    assert shep.classify_risk(text)[0] == "safe_continuation"


@pytest.mark.parametrize(
    "text",
    [
        "SAFE_TO_CLOSE: repo clean, origin/main at f66c4a5 has all work.",
        "Commit uncommitted scripts/shep.py edits.",
        "Commit the fork's changes before it's lost.",
    ],
)
def test_completion_and_local_commit_drafts_auto_send(text) -> None:
    """Real drafts the allowlist used to withhold for lacking a verb form.

    `SAFE_TO_CLOSE` is the agent's own done signal and `commit` writes only to
    the local repo, so neither names anything the risk patterns gate on. They
    were the two largest buckets in the held queue — 24 of 65 held drafts in one
    measured run — and every one of them was waiting on a human for nothing.
    """
    assert shep.classify_risk(text)[0] == "safe_continuation"


def test_a_descriptive_committed_does_not_pass_a_draft() -> None:
    """Only the imperative form is allowlisted.

    "nothing is committed yet" is a descriptive tail, not the instruction. A
    past participle in a trailing clause must not be what carries a draft past
    the gate, or the verb check stops describing what the draft asks for.
    """
    text = "Build the Shep panel for the inbox CLI, since nothing is committed yet."
    assert shep.classify_risk(text)[0] == "unknown"


def test_a_completion_signal_naming_a_risky_action_still_holds() -> None:
    """The new verbs widen the allowlist, never the risk patterns.

    A real held draft: the deploy is reported as already done, but the gate
    cannot tell a report of a deploy from a request for one, so it holds.
    """
    text = "SAFE_TO_CLOSE: sessionTitle fix rebuilt, deployed, and verified live."
    assert shep.classify_risk(text)[0] != "safe_continuation"


# --- Escalation state survives across sweeps ---------------------------------


def test_nudge_state_round_trips_and_drops_dead_targets(tmp_path) -> None:
    path = tmp_path / "state.json"
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()
    shep._SIG_STATE["%1"] = {"sig": "abc", "since": 100.0}
    shep._SIG_STATE["%dead"] = {"sig": "x", "since": 1.0}
    shep._nudge_state("%1")["attempt"] = 2
    shep._nudge_state("%dead")["attempt"] = 1
    assert shep.save_nudge_state({"%1"}, path)

    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()
    assert shep.load_nudge_state(path)
    assert shep._NUDGE_STATE["%1"]["attempt"] == 2
    assert "%dead" not in shep._NUDGE_STATE  # gone with its pane, no TTL needed
    assert shep._SIG_STATE["%1"]["sig"] == "abc"


def test_load_nudge_state_survives_a_corrupt_file(tmp_path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not json")
    assert shep.load_nudge_state(path) is False


def test_legacy_last_nudge_is_migrated_into_echo_history() -> None:
    shep._NUDGE_STATE.clear()
    shep._NUDGE_STATE["legacy"] = {
        "attempt": 1,
        "last_nudge": "Run pytest tests/test_api.py -q.",
        "next_at": 0.0,
    }

    state = shep._nudge_state("legacy")

    assert state["prior_nudges"] == ["Run pytest tests/test_api.py -q."]
    assert shep.novel_context_lines(
        ["Run pytest tests/test_api.py -q."], state
    ) == []


def test_sweep_does_not_escalate_unchanged_evidence_across_processes(
    monkeypatch, tmp_path,
) -> None:
    """Cooldown expiry alone must not manufacture a second instruction."""
    attempts = []

    def _draft(row, recent, attempt=1, **kwargs):
        attempts.append(attempt)
        return f"continue step {attempt}"

    monkeypatch.setattr(shep, "get_pane_context", lambda row, lines=15: "ctx\n")
    monkeypatch.setattr(shep, "clean_context_lines", lambda ctx: ["ctx"])
    monkeypatch.setattr(shep, "llm_draft_nudge", _draft)
    monkeypatch.setattr(shep, "NUDGE_STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(shep, "send_nudge", lambda row, text: (True, "ok"))
    row = _sweep_row()
    monkeypatch.setattr(shep, "collect_all", lambda: [row])

    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()
    shep.sweep(send=True)

    # A second sweep inside the backoff window must NOT re-nudge.
    shep._SIG_STATE.clear()          # simulate a fresh process
    shep._NUDGE_STATE.clear()
    shep.sweep(send=True)
    assert attempts == [1], "backoff must survive a restart too"

    # Past the backoff, the same evidence is still exhausted. A different
    # instruction requires new pane evidence, not merely elapsed time.
    later = time.time() + max(shep.NUDGE_BACKOFF_SECONDS) + 1
    monkeypatch.setattr(shep.time, "time", lambda: later)
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()
    shep.sweep(send=True)
    assert attempts == [1]
    assert shep._nudge_state(row["target"])["exhausted_reason"] == "no_new_evidence"


def test_herdr_shell_pane_overrides_reported_agent_status(monkeypatch) -> None:
    """herdr tracks a tab's configured agent, not whether it still has one.

    A herdr pane at a shell prompt reported `done` would land in NUDGEABLE and
    get a nudge typed into bash — how a live zsh ended up wedged at `quote>`.
    """
    monkeypatch.setattr(shep, "HERDR_CTL", Path(__file__))  # exists() must pass
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"panes": [{
            "pane_id": "w34:p1", "agent_status": "done",
            "cwd": "/repo", "agent": "claude", "workspace_id": "w34",
        }]}),
        stderr="",
    ))
    monkeypatch.setattr(
        shep, "capture_pane",
        lambda *a, **k: "developer@Developer-Mac mb-mgmt %",
    )
    (row,) = shep.collect_herdr()
    assert row["status"] == "shell"
    assert row["status"] not in shep.NUDGEABLE


def test_herdr_live_agent_status_is_preserved(monkeypatch) -> None:
    monkeypatch.setattr(shep, "HERDR_CTL", Path(__file__))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"panes": [{
            "pane_id": "w2E:p1", "agent_status": "done", "cwd": "/repo",
        }]}),
        stderr="",
    ))
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: "⎿  wrote 3 files\n❯ ")
    (row,) = shep.collect_herdr()
    assert row["status"] == "done"


def test_herdr_busy_pane_promotes_idle_status_to_working(monkeypatch) -> None:
    monkeypatch.setattr(shep, "HERDR_CTL", Path(__file__))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({"panes": [{
            "pane_id": "w2E:p2", "agent_status": "idle", "cwd": "/repo",
        }]}),
        stderr="",
    ))
    pane = _IDLE_CLAUDE_PANE.replace(
        "  Eff:--", "  ✻ Thinking… (esc to interrupt)"
    )
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane)

    (row,) = shep.collect_herdr()

    assert row["status"] == "working"


@pytest.mark.parametrize("line", ["[11:13] Status: idle", "Status: waiting"])
def test_happy_status_line_reads_as_idle(monkeypatch, line) -> None:
    """happy sessions report state on a status line instead of a prompt glyph."""
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: f"work\n{line}")
    status, _cues, _ctx = shep._tmux_pane_state("%10")
    assert status == "idle"
    assert status in shep.NUDGEABLE


def test_happy_status_idle_does_not_override_in_progress(monkeypatch) -> None:
    monkeypatch.setattr(
        shep, "capture_pane",
        lambda *a, **k: "Status: idle\n✻ Thinking… (esc to interrupt)",
    )
    assert shep._tmux_pane_state("%10")[0] == "working"


def test_stopped_status_still_reads_as_shell(monkeypatch) -> None:
    monkeypatch.setattr(
        shep, "capture_pane", lambda *a, **k: "x\n[07:15] Status: stopped: Cancelled by user")
    assert shep._tmux_pane_state("%10")[0] == "shell"


# --- Credential handling is its own risk ------------------------------------
#
# A live draft told an agent to "Rotate AI_GATEWAY_API_KEY now... don't wait on
# the DevOps approval" and scored safe_continuation, because it happened not to
# contain the words for a push. Secret handling was simply not a category.


@pytest.mark.parametrize(
    "text",
    [
        "Rotate AI_GATEWAY_API_KEY now, then wrap up.",
        "Regenerate the deploy token and continue.",
        "Update the vault secret, then finish.",
        "Revoke that API key before you proceed.",
    ],
)
def test_secret_handling_is_never_a_safe_continuation(text) -> None:
    assert shep.classify_risk(text)[0] == "credential"


def test_ordinary_continuations_are_not_credential_flagged() -> None:
    assert shep.classify_risk("Continue and fix the failing test.")[0] == "safe_continuation"
    assert shep.classify_risk("Reset the counter and keep going.")[0] == "safe_continuation"


def test_credential_lexicon_is_exposed_to_drafters() -> None:
    assert "credential" in shep.canonical_nudge_phrases()


def test_input_box_placeholder_is_not_reported_as_activity() -> None:
    """An EMPTY agent input box renders a placeholder suggestion.

    Surfacing it made a mission actively building in its worktree read as if it
    were sitting on a welcome screen.
    """
    pane = (
        "  - scripts/allocate-ports.sh emits a deterministic port block.\n"
        "• Working (4s • esc to interrupt)\n"
        "› Find and fix a bug in @filename\n"
    )
    lines = shep.clean_context_lines(pane)
    assert not any(line.strip().startswith("›") for line in lines)
    assert any("allocate-ports" in line for line in lines)


# --- A prompt glyph alone does not mean an agent -----------------------------
#
# `❯` is Claude's prompt AND the common starship/pure zsh prompt. Believing the
# glyph made a bare shell nudgeable — the failure that wedged a live zsh on an
# unterminated quote. An agent draws chrome around its input box; a shell does not.


@pytest.mark.parametrize(
    "name, pane",
    [
        ("starship", "some output\n~/repo on main\n❯ "),
        ("pure", "build ok\n❯ "),
        ("oh-my-zsh", "build finished\n➜  mb-mgmt git:(main) "),
        ("plain", "done\ndeveloper@host mb-mgmt % "),
    ],
)
def test_bare_shell_prompts_are_never_nudgeable(monkeypatch, name, pane) -> None:
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane)
    status, _cues, _ctx = shep._tmux_pane_state("%p")
    assert status == "shell", name
    assert status not in shep.NUDGEABLE


def test_agent_prompt_with_chrome_is_still_idle(monkeypatch) -> None:
    pane = "⎿  wrote 3 files\n❯ \n────────────\n  Opus 5 | med | ContextQ:--\n  Eff:--"
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane)
    status, _cues, _ctx = shep._tmux_pane_state("%p")
    assert status == "idle"
    assert status in shep.NUDGEABLE


def test_happy_status_line_needs_no_chrome(monkeypatch) -> None:
    """happy reports state textually and draws no box — it must still read idle."""
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: "work\n[11:17] Status: idle")
    assert shep._tmux_pane_state("%p")[0] == "idle"


# --- ClickUp telemetry -------------------------------------------------------


def _tel_row():
    return {"source": "herdr", "id": "w34:pH", "target": "herdr:w34:pH",
            "label": "codex", "status": "done",
            "cwd": "/workspaces/qa/commander/mission-commander-2aae0b36"}


def test_telemetry_message_identifies_the_session_and_what_it_was_doing() -> None:
    msg = shep.telemetry_message(
        "nudged", _tel_row(), detail="wrap up and commit",
        activity="Worked for 54m · MR !66 green", attempt=2, category="safe_continuation")
    assert msg.startswith("🧞 NUDGED · codex · mission-commander-2aae0b36 · herdr:w34:pH")
    assert "was: Worked for 54m · MR !66 green" in msg
    assert (
        f"(attempt 2/{shep.MAX_NUDGE_ATTEMPTS}, safe_continuation): wrap up and commit"
    ) in msg


def test_telemetry_is_inert_without_a_channel(monkeypatch) -> None:
    """An unconfigured channel must never block a nudge or a reap."""
    monkeypatch.setattr(shep, "CLICKUP_TELEMETRY_CHANNEL", "")
    posted, reason = shep.post_telemetry("nudged", _tel_row(), detail="x")
    assert posted is False and "no telemetry channel" in reason


def test_telemetry_failure_never_breaks_a_reap(monkeypatch) -> None:
    monkeypatch.setattr(shep, "CLICKUP_TELEMETRY_CHANNEL", "chan-1")
    monkeypatch.setattr(shep, "_clickup_token", lambda: "tok")
    monkeypatch.setattr(shep.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="ok", stderr=""))
    ok, _detail = shep.reap_session(_tel_row())
    assert ok is True


def test_reap_announces_the_reason_captured_before_closing(monkeypatch) -> None:
    sent = {}
    monkeypatch.setattr(shep, "post_telemetry",
                        lambda action, row, **kw: sent.update({"a": action, **kw}))
    monkeypatch.setattr(shep, "_run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout="ok", stderr=""))
    row = _tel_row() | {"reap_reason": "SAFE_TO_CLOSE: MR !66 green", "context": "Worked 54m"}
    shep.reap_session(row)
    assert sent["a"] == "reaped"
    assert sent["detail"] == "SAFE_TO_CLOSE: MR !66 green"
    assert sent["activity"] == "Worked 54m"


# --- NEW_MISSION briefs are deferred work, not current instructions ----------


def test_new_mission_brief_is_excluded_from_risk_scoring() -> None:
    """A live draft whose instruction was "don't merge, wrap up" was held as a
    push, purely because its NEW_MISSION brief mentioned deploy jobs. The brief
    still does not decide the risk CATEGORY — but because send_nudge types the
    whole draft, a risky brief blocks auto-send, so this draft now waits for a
    human as `unknown` instead of auto-firing as `safe_continuation`."""
    text = ("Don't merge the MR yourself or touch approval rules — it stays blocked on a "
            "second human. Wrap up now and end your reply with exactly "
            "'SAFE_TO_CLOSE: <why>' plus 'NEW_MISSION: after !570 is approved and merged, "
            "verify deploy jobs and repost corrected output'.")
    assert shep.classify_risk(text)[0] != "safe_continuation"


def test_real_risk_before_the_brief_is_still_caught() -> None:
    text = ("Rotate the API key and git push it now. "
            "NEW_MISSION: tidy the docs afterwards.")
    assert shep.classify_risk(text)[0] == "credential"


def test_push_outside_the_brief_still_classifies_push() -> None:
    text = "Commit the fix and git push. NEW_MISSION: nothing risky here."
    assert shep.classify_risk(text)[0] == "push"


# --- Context-aware nudging ---------------------------------------------------
#
# The escalation ladder existed in the prompt but the drafter was never told
# what it had already sent, so attempts 2 and 3 re-derived the same words from
# the same pane excerpt. Exact-equality dedup then let any rewording through.


def test_repeat_nudge_catches_a_reworded_duplicate() -> None:
    """The bug: dedup compared bytes, so the same instruction in different
    words counted as a fresh nudge and got sent again."""
    state = {"prior_nudges": ["Fix the failing auth test and commit the result."]}
    assert shep.is_repeat_nudge("Commit the result after fixing the failing auth test.", state)


def test_repeat_nudge_allows_a_materially_different_instruction() -> None:
    state = {"prior_nudges": ["Fix the failing auth test and commit the result."]}
    assert not shep.is_repeat_nudge("What command are you stuck on right now?", state)


def test_repeat_nudge_checks_the_whole_history_not_just_the_last() -> None:
    """Escalation cycling between two phrasings would otherwise loop forever."""
    state = {
        "prior_nudges": ["Fix the failing auth test and commit.", "Name the exact blocker."],
        "last_nudge": "Name the exact blocker.",
    }
    assert shep.is_repeat_nudge("Fix that failing auth test, then commit.", state)


def test_a_reworded_close_request_is_the_same_ask() -> None:
    """The bug: every close ask carries a reason written fresh from the pane,
    so two asks scored 0.22 similarity and both went out. One pane was asked
    six times; only 5 of 66 asks all day were ever answered."""
    first = ("Finish by replying SAFE_TO_CLOSE: ae-kimi-gw compiles, 18/18 tests "
             "pass, no secrets found, worktree clean.")
    second = ("Finish by replying SAFE_TO_CLOSE: MR !658 merged to main, vendor "
              "colors verified present, CI green.")
    assert shep.nudge_similarity(second, first) < shep.NUDGE_REPEAT_RATIO
    state = {"prior_nudges": [first], "close_requested": True}
    assert shep.is_repeat_nudge(second, state)


def test_the_first_close_request_is_not_suppressed() -> None:
    """Recorded on send, not on draft — an unsent ask must not swallow the real one."""
    state = {"prior_nudges": [], "close_requested": False}
    assert not shep.is_repeat_nudge(
        "Finish by replying SAFE_TO_CLOSE: nothing is left hanging.", state
    )


def test_close_request_dedupe_leaves_ordinary_instructions_alone() -> None:
    state = {"prior_nudges": ["Run the failing auth test again."], "close_requested": True}
    assert not shep.is_repeat_nudge("Push the branch and open the MR.", state)


def test_an_agent_reply_does_not_re_arm_the_close_request(monkeypatch) -> None:
    """The reply moves the pane, which resets the ladder. If the flag reset with
    it, answering the ask is what earned you a second one."""
    target = "herdr:w1:p1"
    ask = "Finish by replying SAFE_TO_CLOSE: MR !388 merged, install.sh green."
    monkeypatch.setattr(shep, "record_outcome", lambda *a, **k: None)
    shep._SIG_STATE[target] = {"sig": shep.pane_signature("> working"), "since": 100.0}
    state = shep._nudge_state(target)
    shep.remember_nudge(state, ask)
    state.update({"attempt": 2, "close_requested": True})

    shep.update_stall(target, "> I merged MR !388 and verified install.sh.", "idle")

    after = shep._nudge_state(target)
    assert after["attempt"] == 0, "the ladder should still reset on real movement"
    assert after["close_requested"] is True
    assert shep.is_repeat_nudge(
        "Finish by replying SAFE_TO_CLOSE: everything is verified and pushed.", after
    )
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_sent_nudge_echo_does_not_reset_cooldown_or_dedupe_history() -> None:
    target = "herdr:w1:p1"
    pane = "[CodexAppServer] Turn timed out"
    nudge = "Run the interrupted turn again, then verify the result."
    shep._SIG_STATE[target] = {"sig": shep.pane_signature(pane), "since": 100.0}
    state = shep._nudge_state(target)
    state.update({
        "attempt": 1,
        "last_nudge": nudge,
        "prior_nudges": [nudge],
        "next_at": 999.0,
        "proposed": {"text": nudge, "status": "sent"},
    })

    assert shep.update_stall(target, f"{pane}\n{nudge}", "idle") == "idle"
    assert shep._NUDGE_STATE[target] is state
    assert state["attempt"] == 1
    assert state["next_at"] == 999.0
    assert shep.is_repeat_nudge(nudge, state)

    assert shep.update_stall(target, f"{pane}\n{nudge}\n{nudge}", "idle") == "idle"
    assert shep._NUDGE_STATE[target] is state
    assert state["attempt"] == 1
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_real_progress_still_resets_nudge_ladder_after_echo() -> None:
    target = "herdr:w1:p1"
    nudge = "Run the interrupted turn again, then verify the result."
    shep._SIG_STATE[target] = {"sig": "tests failed", "since": 100.0}
    shep._nudge_state(target).update({
        "attempt": 1,
        "prior_nudges": [nudge],
        "proposed": {"text": nudge, "status": "sent"},
    })

    shep.update_stall(target, f"tests passed\n{nudge}", "idle")
    state = shep._nudge_state(target)
    # The stall clock and cooldown clear, but the escalation count does not:
    # this pane moved while our nudge was still unresolved, so the movement is
    # something we prompted rather than evidence it no longer needs us. Letting
    # it refill the budget here is what made MAX_NUDGE_ATTEMPTS unreachable.
    assert state["attempt"] == 1
    assert state["next_at"] == 0.0
    assert state["prior_nudges"] == [nudge]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_real_progress_keeps_only_new_evidence_for_the_next_decision() -> None:
    target = "herdr:w1:p1"
    baseline = "pytest failed"
    nudge = "Run pytest tests/test_api.py -q."
    shep._SIG_STATE[target] = {
        "sig": shep.pane_signature(baseline),
        "since": 100.0,
    }
    shep._nudge_state(target).update({
        "attempt": 1,
        "prior_nudges": [nudge],
        "proposed": {
            "text": nudge,
            "status": "sent",
            "context": baseline,
        },
    })

    moved = f"{baseline}\n{nudge}\npytest: 2 failed in test_sessions.py"
    shep.update_stall(target, moved, "idle")

    assert shep.novel_context_lines([moved], shep._nudge_state(target)) == [
        "pytest: 2 failed in test_sessions.py"
    ]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_word_wrapped_echo_of_our_own_nudge_is_not_progress(monkeypatch) -> None:
    """Herdr wraps a long nudge at the pane width, sometimes mid-word."""
    events = []
    target = "herdr:w1:p1"
    nudge = "Run: commit the vendor color fix (26/26 tests passing) and push to main."
    pane = "> building the dashboard\n  tests: 26 passed\n\n> "
    shep._SIG_STATE[target] = {"sig": shep.pane_signature(pane), "since": 100.0}
    shep._nudge_state(target).update({
        "attempt": 1,
        "prior_nudges": [nudge],
        "last_sent": {"text": nudge, "status": "sent"},
    })
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )

    wrapped = f"{nudge[:40]}\n{nudge[40:]}"
    assert shep.update_stall(target, f"{pane}{wrapped}", "idle") == "idle"

    assert events == []
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_one_sent_nudge_is_credited_with_progress_only_once(monkeypatch) -> None:
    """A burst of work is one outcome for one nudge, not one per poll."""
    events = []
    target = "herdr:w1:p1"
    shep._SIG_STATE[target] = {"sig": "pytest failed", "since": 100.0}
    shep._nudge_state(target).update({
        "attempt": 1,
        "prior_nudges": ["Fix the failing test."],
        "last_sent": {"text": "Fix the failing test.", "status": "sent"},
    })
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )

    for frame in ("pytest running", "pytest passed", "pushed to main", "done"):
        shep.update_stall(target, frame, "idle")

    assert events == [("progress", {"target": target, "outcome": "advanced"})]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


# --- Escalation to a human -------------------------------------------------
#
# Real telemetry motivating these: across the first four days of autonomous
# sends, one target absorbed 35 nudges and never resolved, and of the 34
# targets nudged three or more times only 3 ever resolved. 11 of 12 total
# resolutions arrived within two nudges. MAX_NUDGE_ATTEMPTS existed the whole
# time; it simply could not bind, because each nudge moved the pane and the
# movement reset the count.


def _nudged_pane(target, attempt, nudge="Fix the failing test."):
    """A pane holding one unresolved sent nudge at the given attempt count."""
    shep._SIG_STATE[target] = {"sig": "pytest failed", "since": 100.0}
    shep._nudge_state(target).update({
        "attempt": attempt,
        "prior_nudges": [nudge],
        "last_sent": {"text": nudge, "status": "sent"},
    })


def test_movement_we_caused_does_not_refill_the_escalation_budget() -> None:
    """The pane moved because we typed at it, so the ladder must not reset."""
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=2)

    shep.update_stall(target, "pytest running", "idle")

    assert shep._nudge_state(target)["attempt"] == 2
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_progress_the_agent_made_alone_does_refill_the_budget() -> None:
    """A pane that moved on its own is not stuck and gets a fresh ladder."""
    target = "herdr:w1:p1"
    shep._SIG_STATE[target] = {"sig": "pytest failed", "since": 100.0}
    shep._nudge_state(target).update({"attempt": 2, "last_sent": None})

    shep.update_stall(target, "pytest passed", "idle")

    assert shep._nudge_state(target)["attempt"] == 0
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_a_pane_already_credited_for_a_nudge_is_not_charged_twice() -> None:
    """The ladder is held for the whole span the nudge stays unresolved.

    Crediting progress once but releasing the ladder on the next frame would
    leave the cap just as unbindable: a chatty pane emits a frame a second.
    """
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=1)

    shep.update_stall(target, "pytest running", "idle")
    shep.update_stall(target, "pytest passed", "idle")
    shep.update_stall(target, "still going", "idle")

    assert shep._nudge_state(target)["attempt"] == 1
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_the_last_allowed_nudge_hands_the_pane_to_a_human(monkeypatch) -> None:
    events = []
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    monkeypatch.setattr(
        shep, "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )

    shep.update_stall(target, "pytest running", "idle")

    assert shep._nudge_state(target)["exhausted_reason"] == "needs_human"
    assert ("terminal", {"target": target, "outcome": "human_handoff"}) in events
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_a_pane_handed_to_a_human_is_not_nudged_again() -> None:
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    shep.update_stall(target, "pytest running", "idle")

    row = {"target": target, "status": "idle"}
    assert shep.should_nudge(row, shep._nudge_state(target)) is False
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


# An `idle` status is herdr's claim, not an observation. Measured against the
# live fleet over one 5s window — the median draft round-trip — 7 of 11 panes
# herdr called idle or done had moved by the time a draft came back, and 6 of
# those had printed genuinely new output rather than a ticking spinner. Those
# drafts were paid for in full and discarded on arrival, which is what the
# "session context changed" invalidations were.

def test_a_pane_still_producing_output_is_not_worth_a_model_call() -> None:
    row = {"target": "%1", "status": "idle", "quiet_for": 0}
    assert shep.pane_is_quiet(row) is False
    assert shep.should_nudge(row, shep._nudge_state("%1")) is False
    shep._NUDGE_STATE.clear()


def test_a_pane_that_has_settled_is_nudgeable() -> None:
    row = {"target": "%1", "status": "idle",
           "quiet_for": shep.NUDGE_QUIET_SECONDS}
    assert shep.pane_is_quiet(row) is True
    assert shep.should_nudge(row, shep._nudge_state("%1")) is True
    shep._NUDGE_STATE.clear()


def test_a_pane_seen_only_once_is_not_yet_evidence_of_quiet() -> None:
    # No clock at all means this pane has not been observed twice. Absence of
    # evidence is not quiet; the next poll settles it.
    assert shep.pane_is_quiet({"target": "never-seen", "status": "idle"}) is False


def test_the_quiet_clock_keeps_running_for_a_pane_that_is_not_working() -> None:
    # It used to be reset on every poll of a non-working pane, which pinned
    # `stalled_seconds` at ~0 for every idle pane: the drafter was told
    # "stalled for 0s" and the gate had no quiet to wait for.
    target = "herdr:w1:p1"
    shep._SIG_STATE.clear()
    now = time.time()
    shep.update_stall(target, "waiting at prompt", "idle")
    shep._SIG_STATE[target]["since"] = now - 600
    shep.update_stall(target, "waiting at prompt", "idle")

    assert shep.stalled_seconds(target, now) == 600
    shep._SIG_STATE.clear()


def test_real_output_still_resets_the_quiet_clock() -> None:
    target = "herdr:w1:p1"
    shep._SIG_STATE.clear()
    now = time.time()
    shep.update_stall(target, "waiting at prompt", "idle")
    shep._SIG_STATE[target]["since"] = now - 600
    shep.update_stall(target, "waiting at prompt\nnow running pytest", "idle")

    assert shep.stalled_seconds(target, now) == 0
    shep._SIG_STATE.clear()


def test_a_ticking_spinner_does_not_reset_the_quiet_clock() -> None:
    # pane_signature is blind to cosmetic churn, so an elapsed counter alone
    # must not read as the agent doing something.
    target = "herdr:w1:p1"
    shep._SIG_STATE.clear()
    now = time.time()
    shep.update_stall(target, "✻ Ionizing… (4m 16s)", "idle")
    shep._SIG_STATE[target]["since"] = now - 600
    shep.update_stall(target, "✢ Ionizing… (4m 21s)", "idle")

    assert shep.stalled_seconds(target, now) == 600
    shep._SIG_STATE.clear()


def test_one_nudge_short_of_the_cap_is_still_nudgeable() -> None:
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS - 1)
    shep.update_stall(target, "pytest running", "idle")

    state = shep._nudge_state(target)
    assert state.get("exhausted_reason") is None
    assert shep.should_nudge(
        {"target": target, "status": "idle", "quiet_for": shep.NUDGE_QUIET_SECONDS},
        state,
    ) is True
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_the_snapshot_says_which_panes_need_a_human() -> None:
    """Withholding drafts silently looks identical to a healthy quiet pane."""
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    shep.update_stall(target, "pytest running", "idle")

    row = _sweep_row()
    row["target"] = target
    payload = shep.snapshot_payload([row])
    nudge = payload["panels"][0]["nudge"]

    assert nudge["status"] == "needs_human"
    assert "nudging cannot fix it" in nudge["reason"]
    assert payload["counts"]["nudge_needs_human"] == 1
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_the_handoff_is_announced_once_not_every_pass(monkeypatch) -> None:
    """The unattended loop has nobody watching the TUI to read the status off."""
    posts = []
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    shep.update_stall(target, "pytest running", "idle")
    monkeypatch.setattr(
        shep, "post_telemetry",
        lambda event, row, **fields: posts.append((event, fields.get("detail"))),
    )
    monkeypatch.setattr(
        shep, "llm_draft_nudge",
        lambda *a, **k: pytest.fail("an escalated pane must not be drafted for"),
    )
    row = _sweep_row()
    row["target"] = target

    shep.sweep(send=True, rows=[row])
    shep.sweep(send=True, rows=[row])

    assert [event for event, _ in posts] == ["handoff"]
    assert "needs a human" in posts[0][1]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_sweep_does_not_draft_for_a_pane_handed_to_a_human(monkeypatch) -> None:
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    shep.update_stall(target, "pytest running", "idle")
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(
        shep, "llm_draft_nudge",
        lambda *a, **k: pytest.fail("an escalated pane must not be drafted for"),
    )
    row = _sweep_row()
    row["target"] = target

    results, held, _escalated = shep.sweep(send=True, rows=[row])

    assert results == [] and held == []
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_an_escalated_pane_is_reported_on_every_pass_not_just_the_first(
    monkeypatch,
) -> None:
    """Announcing is a one-shot event; needing a human is a standing condition.

    Tying the report to the announcement would have printed the pane once and
    then gone quiet, which is the same silence this whole change exists to end.
    """
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    shep.update_stall(target, "pytest running", "idle")
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    row = _sweep_row()
    row["target"] = target

    first = shep.sweep(send=True, rows=[row])[2]
    second = shep.sweep(send=True, rows=[row])[2]

    assert [r for r, _ in first] == [row]
    assert [r for r, _ in second] == [row]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def _guard_handoff_row(target="herdr:wZ:pA"):
    row = _sweep_row()
    row.update(source="herdr", id=target, target=target, label="rakazo")
    return row


def test_destroyed_owned_pane_is_not_escalated_again(monkeypatch) -> None:
    """A pane gone from this host's Herdr fleet has nothing waiting behind it."""
    target = "herdr:wZ:pA"
    row = _guard_handoff_row(target)
    shep._nudge_state(target).update({"exhausted_reason": "needs_human"})
    monkeypatch.setattr(shep, "_live_panes_or_none", lambda: {"w5M:p1"})
    monkeypatch.setattr(shep.escalation_guard, "ladder_targets", lambda: {target})
    monkeypatch.setattr(shep, "notify_operator", lambda *a, **k: None)

    _results, _held, escalated = shep.sweep(send=False, rows=[row])

    assert escalated == []
    shep._NUDGE_STATE.clear()


def test_live_owned_pane_still_escalates(monkeypatch) -> None:
    target = "herdr:wZ:pA"
    row = _guard_handoff_row(target)
    shep._nudge_state(target).update({"exhausted_reason": "needs_human"})
    monkeypatch.setattr(shep, "_live_panes_or_none", lambda: {"wZ:pA"})
    monkeypatch.setattr(shep, "notify_operator", lambda *a, **k: None)

    _results, _held, escalated = shep.sweep(send=False, rows=[row])

    assert [r.get("target") for r, _reason in escalated] == [target]
    shep._NUDGE_STATE.clear()


def test_unavailable_herdr_fails_open_to_escalation(monkeypatch) -> None:
    target = "herdr:wZ:pA"
    row = _guard_handoff_row(target)
    shep._nudge_state(target).update({"exhausted_reason": "needs_human"})
    monkeypatch.setattr(shep, "_live_panes_or_none", lambda: None)
    monkeypatch.setattr(shep, "notify_operator", lambda *a, **k: None)

    _results, _held, escalated = shep.sweep(send=False, rows=[row])

    assert [r.get("target") for r, _reason in escalated] == [target]
    shep._NUDGE_STATE.clear()


def test_the_sweep_report_says_a_pane_needs_a_human() -> None:
    """A skipped escalation used to read exactly like a skipped abstention.

    Both left the pane out of `results` and `held`, so the only line the
    unattended loop writes down said "0 ready to send, 0 held" while a session
    sat stranded. The operator could not tell the two apart from the log.
    """
    row = _sweep_row()

    report = shep.render_sweep([], [], send=True, escalated=[(row, "waiting on you")])

    assert "NEEDS-HUMAN" in report
    assert row["label"] in report
    assert "waiting on you" in report
    assert report.splitlines()[-1].endswith("1 needs a human --")


def test_the_sweep_report_counts_several_stranded_panes_in_the_plural() -> None:
    report = shep.render_sweep(
        [], [], send=True,
        escalated=[(_sweep_row(), "why"), (_sweep_row(), "why")],
    )

    assert report.splitlines()[-1].endswith("2 need a human --")


def test_the_sweep_report_is_unchanged_when_nothing_needs_a_human() -> None:
    assert shep.render_sweep([], [], send=True).splitlines()[-1] == (
        "-- 0 sent, 0 held for review --"
    )


def test_a_drafter_saying_only_you_can_unblock_this_hands_the_pane_over(
    monkeypatch,
) -> None:
    """The ladder measures failure by repetition and cannot see this.

    A pane waiting on a credential absorbs all three nudges and looks exactly
    like a slow one. The drafter is the only part of shep that reads the pane
    and can say the blocker is not addressable by typing.
    """
    _stub_draft(monkeypatch, "NEEDS_HUMAN: reconnect Twingate, it is your account")
    sent: list[str] = []
    _record_sends(monkeypatch, sent)
    shep._NUDGE_STATE.clear()

    results, held, escalated = shep.sweep(send=True, rows=[_sweep_row()])

    assert (results, held, sent) == ([], [], [])
    assert [reason for _, reason in escalated] == [
        "reconnect Twingate, it is your account",
    ]
    assert shep._nudge_state("%9")["exhausted_reason"] == "needs_human"
    shep._NUDGE_STATE.clear()


def test_a_needs_human_reply_is_never_typed_into_the_pane() -> None:
    """It is prose about the operator, and every gate below judges instructions.

    Without its own rejection it reads as an ordinary draft and gets typed into
    the very pane it was written about.
    """
    assert shep.operational_candidate_or_fallback(
        "NEEDS_HUMAN: reconnect Twingate", _sweep_row(), ["line one"],
    ) is None


def test_the_agents_own_close_reply_is_never_typed_back_at_it() -> None:
    """Shep asked for SAFE_TO_CLOSE, the agent answered, shep resent the answer.

    The read-side guard (`_without_sent_echo`) already stops the close detector
    reaping a pane on shep's own typing, but nothing stopped the draft going out
    in the first place: two live panes were each sent their own completion
    report back, twice over. The engine prompt forbids opening with the token
    and the model did it anyway, which is why this is a gate and not guidance.
    """
    for reply in (
        "SAFE_TO_CLOSE: MR !699 merged to main, CI green, guard verified.",
        "  safe_to_close: nothing left hanging",
    ):
        assert shep.operational_candidate_or_fallback(
            reply, _sweep_row(), ["line one"],
        ) is None


def test_an_instruction_that_merely_mentions_the_close_token_still_sends() -> None:
    """Only an opening token is the agent's reply; asking for one is our job."""
    ask = "Reply on a new line starting with SAFE_TO_CLOSE: then why nothing is left."
    assert shep.operational_candidate_or_fallback(
        ask, _sweep_row(), ["line one"],
    ) == ask


def test_an_abstention_is_not_a_handoff() -> None:
    """Abstention is the drafter's ordinary resting state, not a blocker.

    In the first week of telemetry one healthy pane abstained 138 times while
    still producing 84 usable nudges. Treating that as needing a human would
    have escalated most of the deck.
    """
    assert shep.needs_human_request("NO_NUDGE") is None
    assert shep.needs_human_request("Run pytest test_api.py.") is None


def _latched(target, reason="needs_human"):
    state = shep._nudge_state(target)
    state["exhausted_reason"] = reason
    state["attempt"] = shep.MAX_NUDGE_ATTEMPTS
    state["needs_human_reason"] = "supply the API key"
    state["handoff_announced"] = True
    state["assessed_fingerprint"] = "abc123"
    return state


def test_release_puts_a_stranded_pane_back_in_the_engine() -> None:
    """The operator cleared the blocker by hand, so the pane will never move.

    `update_stall` is the only other way out of the ladder and it needs new pane
    bytes. A pane whose blocker was fixed outside the terminal has none to give,
    so without this it stays latched forever.
    """
    shep._NUDGE_STATE.clear()
    _latched("%9")

    assert shep.release_targets(["%9"]) == ["%9"]

    state = shep._nudge_state("%9")
    assert state["exhausted_reason"] is None
    assert state["attempt"] == 0
    assert state.get("needs_human_reason") is None
    assert state.get("handoff_announced") is None
    # Dropped on purpose: the pane has produced nothing since, so carrying the
    # fingerprint over would re-suppress it as `no_new_evidence` next pass and
    # make the release a no-op.
    assert state["assessed_fingerprint"] is None
    assert shep.should_nudge(_sweep_row(), state)
    shep._NUDGE_STATE.clear()


def test_release_keeps_the_dedupe_history_it_reopens() -> None:
    """A reopened pane must not be re-sent the nudge it already ignored."""
    shep._NUDGE_STATE.clear()
    state = _latched("%9")
    state["prior_nudges"] = ["run the tests"]
    state["close_requested"] = True

    shep.release_targets(["*"])

    reopened = shep._nudge_state("%9")
    assert reopened["prior_nudges"] == ["run the tests"]
    assert reopened["close_requested"] is True
    shep._NUDGE_STATE.clear()


def test_release_leaves_unmatched_and_unlatched_panes_alone() -> None:
    """A glob that reopens the whole fleet by accident is worse than no flag."""
    shep._NUDGE_STATE.clear()
    _latched("%9")
    _latched("%7", reason="abstained")
    healthy = shep._nudge_state("%1")

    assert shep.release_targets(["%9"]) == ["%9"]

    assert shep._nudge_state("%7")["exhausted_reason"] == "abstained"
    assert shep._nudge_state("%1") is healthy
    shep._NUDGE_STATE.clear()


def test_real_progress_after_a_sent_nudge_records_an_attributable_outcome(
    monkeypatch,
) -> None:
    events = []
    target = "herdr:w1:p1"
    shep._SIG_STATE[target] = {"sig": "pytest failed", "since": 100.0}
    shep._nudge_state(target).update({
        "attempt": 1,
        "prior_nudges": ["Fix the failing test."],
        "proposed": {"text": "Fix the failing test.", "status": "sent"},
    })
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )

    shep.update_stall(target, "pytest passed", "idle")

    assert events == [("progress", {"target": target, "outcome": "advanced"})]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_unchanged_poll_cannot_erase_later_progress_attribution(monkeypatch) -> None:
    events = []
    target = "%worker"
    baseline = "pytest failed"
    nudge = "Run pytest tests/test_api.py -q."
    shep._SIG_STATE[target] = {
        "sig": shep.pane_signature(baseline),
        "since": 100.0,
    }
    state = shep._nudge_state(target)
    shep.remember_nudge(state, nudge)
    state.update({
        "last_sent": {"text": nudge, "status": "sent", "context": baseline},
        "proposed": {"text": nudge, "status": "sent", "context": baseline},
        "assessed_fingerprint": shep.nudge_evidence_fingerprint(baseline, state),
        "next_at": 0.0,
    })
    monkeypatch.setattr(shep, "get_pane_context", lambda *_args, **_kwargs: baseline)
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )

    row = _sweep_row()
    row["target"] = target
    shep.sweep(send=True, rows=[row])
    shep.update_stall(target, "pytest passed", "idle")

    assert ("progress", {"target": target, "outcome": "advanced"}) in events
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_successful_manual_nudge_is_attributable_without_a_queued_proposal(
    monkeypatch,
) -> None:
    target = "%manual"
    monkeypatch.setattr(
        shep,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    shep._NUDGE_STATE.clear()

    ok, _detail = shep.send_nudge(
        {"source": "tmux", "target": target, "context": "pytest failed"},
        "Run pytest tests/test_api.py -q.",
        audit=False,
    )

    assert ok is True
    assert shep._nudge_state(target)["proposed"] == {
        "text": "Run pytest tests/test_api.py -q.",
        "status": "sent",
        "context": "pytest failed",
        "sent_at": shep._nudge_state(target)["proposed"]["sent_at"],
    }


def test_automatic_continuation_records_a_sent_outcome(monkeypatch, tmp_path) -> None:
    """The control pass reaches a pane without passing through any of the
    interactive approval branches, and the `sent` outcome was recorded only in
    those branches — so the automatic continuations, two thirds of one measured
    day's deliveries, never reached the outcome log at all."""
    events = []
    row = {"source": "herdr", "target": "herdr:w1:p1", "label": "worker",
           "status": "idle", "cwd": "/repo"}
    monkeypatch.setattr(shep, "collect_all", lambda: [row])
    monkeypatch.setattr(
        shep,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout="accepted", stderr=""
        ),
    )
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )
    shep._NUDGE_STATE.clear()

    shep.run_control_pass(SimpleNamespace(
        action_log=str(tmp_path / "ledger.jsonl"),
        control_state=str(tmp_path / "state.json"),
        control_lock=str(tmp_path / "control.lock"),
        auto_nudge=True, auto_reap=False, dry_run=False, max_actions=1,
    ))

    assert events == [(
        "sent",
        {"target": "herdr:w1:p1", "engine": None, "ok": True, "path": "control",
         "risk_category": "safe_continuation"},
    )]
    shep._NUDGE_STATE.clear()


def test_one_delivery_records_exactly_one_sent_outcome(monkeypatch) -> None:
    """A route that still recorded its own `sent` after the recording moved into
    send_nudge would count every one of its deliveries twice, which reads as a
    doubled send count rather than as a bug."""
    events = []
    _stub_draft(monkeypatch, "Run pytest test_api.py.", "pytest failed in test_api.py")
    monkeypatch.setattr(
        shep,
        "_run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )
    shep._NUDGE_STATE.clear()

    shep.sweep(send=True, rows=[_sweep_row()])

    sends = [fields for event, fields in events if event == "sent"]
    assert len(sends) == 1
    assert sends[0]["path"] == "sweep" and sends[0]["engine"] == "operational"
    shep._NUDGE_STATE.clear()


def test_a_failed_delivery_is_recorded_once_and_marked_unsuccessful(
    monkeypatch,
) -> None:
    """`sent` with ok=False is what makes send_success_rate a rate — drop the
    failures and its numerator and denominator become the same number. A
    read-only source never reaches a transport, and that is still a delivery
    attempt the report has to see."""
    events = []
    monkeypatch.setattr(
        shep,
        "record_outcome",
        lambda event, **fields: events.append((event, fields)),
    )
    shep._NUDGE_STATE.clear()

    ok, _detail = shep.send_nudge(
        {"source": "claude", "target": "claude:1"}, "Run pytest -q.", audit=False,
    )

    assert ok is False
    assert [(event, fields["ok"]) for event, fields in events] == [("sent", False)]
    shep._NUDGE_STATE.clear()


def test_remember_nudge_keeps_history_bounded() -> None:
    state = {"prior_nudges": []}
    for i in range(6):
        shep.remember_nudge(state, f"message {i}")
    assert len(state["prior_nudges"]) == shep.NUDGE_HISTORY_DEPTH
    assert state["prior_nudges"][-1] == "message 5"
    assert state["last_nudge"] == "message 5"


def test_prior_nudges_reach_the_drafting_prompt(monkeypatch) -> None:
    """Regression for the actual defect: without this the model re-drafted
    blind and produced the same message every attempt."""
    captured = {}

    def fake_run(argv, **kwargs):
        captured["prompt"] = argv[-1]
        return SimpleNamespace(stdout="do the other thing", returncode=0)

    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(shep.subprocess, "run", fake_run)
    shep.llm_draft_nudge(
        {"label": "worker", "status": "idle"},
        ["some pane output"],
        attempt=2,
        prior=["Fix the failing auth test."],
    )
    assert "Fix the failing auth test." in captured["prompt"]
    assert '"actions_already_tried"' in captured["prompt"]


def test_operational_drafter_abstains_from_verbose_output(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(
        shep.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="Continue " + "with the current work " * 12,
            returncode=0,
        ),
    )

    assert shep.llm_draft_nudge(
        {"label": "worker", "status": "idle"}, ["pytest failed"]
    ) is None


def test_operational_drafter_rejects_stdout_from_failed_gateway(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(
        shep.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="Run pytest tests/test_api.py -q.",
            stderr="gateway unavailable",
            returncode=1,
        ),
    )

    assert shep.llm_draft_nudge(
        {"label": "worker", "status": "idle"}, ["pytest failed"]
    ) is None


def test_stall_duration_reaches_the_prompt(monkeypatch) -> None:
    captured = {}

    def fake_run(argv, **kwargs):
        captured["prompt"] = argv[-1]
        return SimpleNamespace(stdout="ok", returncode=0)

    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(shep.subprocess, "run", fake_run)
    shep.llm_draft_nudge(
        {"label": "worker", "status": "stalled"}, ["output"], stalled_for=900
    )
    assert "15 minutes" in captured["prompt"]


def test_no_stall_context_when_pane_is_moving(monkeypatch) -> None:
    """A pane that just moved must not be described as stuck."""
    captured = {}

    def fake_run(argv, **kwargs):
        captured["prompt"] = argv[-1]
        return SimpleNamespace(stdout="ok", returncode=0)

    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(shep.subprocess, "run", fake_run)
    shep.llm_draft_nudge(
        {"label": "worker", "status": "idle"}, ["output"], stalled_for=5
    )
    assert "not changed in" not in captured["prompt"]


def test_first_nudge_has_no_history_preamble(monkeypatch) -> None:
    captured = {}

    def fake_run(argv, **kwargs):
        captured["prompt"] = argv[-1]
        return SimpleNamespace(stdout="ok", returncode=0)

    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)
    monkeypatch.setattr(shep.subprocess, "run", fake_run)
    shep.llm_draft_nudge({"label": "w", "status": "idle"}, ["out"], prior=[])
    assert "ALREADY sent" not in captured["prompt"]


def test_nudge_state_rehydrates_without_prior_nudges() -> None:
    """State persisted before this change has no prior_nudges key."""
    shep._NUDGE_STATE.clear()
    shep._NUDGE_STATE["legacy"] = {"attempt": 1, "last_nudge": "x", "next_at": 0.0}
    state = shep._nudge_state("legacy")
    assert state["prior_nudges"] == ["x"]
    assert shep.is_repeat_nudge("x", state)
    shep._NUDGE_STATE.clear()


def test_escalation_ladder_is_not_suppressed_as_duplicate() -> None:
    """Over-suppression guard. Tightening repeat detection must not silence the
    genuine ladder — firmer wording and a diagnostic ask are new instructions,
    not rewordings, and suppressing them would leave a wedged pane un-nudged."""
    state = {"prior_nudges": []}
    for msg in (
        "Fix the failing auth test, then commit and end with SAFE_TO_CLOSE.",
        "You have not responded. Finish the auth fix now or name the exact blocker.",
        "What command are you on, and what was the last error you saw?",
    ):
        assert not shep.is_repeat_nudge(msg, state), msg
        shep.remember_nudge(state, msg)
    # A genuinely new direction still gets through once history is full.
    assert not shep.is_repeat_nudge("Run pytest -x and paste the first failure.", state)


# --- Tab view loops ---------------------------------------------------------
#
# run_beads_view/run_missions_view were the two entirely untested surfaces: the
# code under them was covered, but nothing drove the loops, so a stale column
# header, a key that stopped routing, or a launch fired without confirmation
# would all have shipped green.


class _ViewScreen:
    """Minimal curses stand-in that drives a view loop off a scripted keys list."""

    def __init__(self, keys, height=24, width=100) -> None:
        self.keys = list(keys)
        self.height = height
        self.width = width
        self.painted = []
        self.timeouts = []

    def getmaxyx(self):
        return self.height, self.width

    def erase(self) -> None:
        self.painted.append("--erase--")

    def timeout(self, milliseconds: int) -> None:
        self.timeouts.append(milliseconds)

    def addstr(self, _y, _x, text, *_attrs) -> None:
        self.painted.append(text)

    def refresh(self) -> None:
        pass

    def getch(self) -> int:
        if not self.keys:
            raise AssertionError("view loop asked for more keys than the test scripted")
        return self.keys.pop(0)

    def screen_text(self) -> str:
        return "\n".join(self.painted)


def _frame(screen):
    """Text painted for the last completed frame, so assertions ignore redraws."""
    return screen.screen_text().split("--erase--")[-1]


# --- run_beads_view ---------------------------------------------------------

_BEAD_ROWS = [
    {"repo": "alpha", "id": "alpha-1", "title": "First", "status": "open",
     "priority": 0, "repo_path": "/repos/alpha"},
    {"repo": "beta", "id": "beta-9", "title": "Second", "status": "in_progress",
     "priority": 2, "repo_path": "/repos/beta"},
]


def test_beads_view_renders_the_repo_of_every_row(monkeypatch) -> None:
    """A fleet-wide list is ambiguous unless each row says where it came from."""
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    screen = _ViewScreen([ord("q")])

    beads, target = shep.run_beads_view(screen, ascii_only=False)

    assert (beads, target) == (_BEAD_ROWS, "agents")
    painted = screen.screen_text()
    assert "alpha · alpha-1 · open · P0 · c:? u:? · First" in painted
    assert "beta · beta-9 · in_progress · P2 · c:? u:? · Second" in painted


def test_beads_view_column_header_matches_the_rows(monkeypatch) -> None:
    """The header drifted behind the row format once already."""
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=False)

    header = next(line for line in screen.painted if "STATUS" in line and "TITLE" in line)
    assert header.strip().split(" · ") == ["REPO", "ID", "STATUS", "PRIORITY", "TITLE"]


def test_beads_view_surfaces_a_loader_error_instead_of_a_blank_pane(monkeypatch) -> None:
    monkeypatch.setattr(
        shep, "load_beads", lambda: ([], "bug-hunter: no beads database found")
    )
    screen = _ViewScreen([ord("q")])

    beads, _target = shep.run_beads_view(screen, ascii_only=True)

    assert beads == []
    assert "bug-hunter: no beads database found" in screen.screen_text()


@pytest.mark.parametrize(
    ("key", "expected"),
    [(ord("q"), "agents"), (27, "agents"), (ord("1"), "agents"), (ord("3"), "missions")],
)
def test_beads_view_routes_every_exit_key(monkeypatch, key, expected) -> None:
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))

    _beads, target = shep.run_beads_view(_ViewScreen([key]), ascii_only=True)

    assert target == expected


@pytest.mark.parametrize("key, expected", [(ord("1"), "agents"), (ord("3"), "missions"), (ord("4"), "logs")])
def test_beads_view_keeps_tab_navigation_live_during_slow_triage(
    monkeypatch, key, expected
) -> None:
    """A slow provider must not strand the operator inside the BEADS tab."""
    started = threading.Event()
    release = threading.Event()

    def slow_strip(_beads, force=False):
        started.set()
        release.wait(2)
        return [], {}, "stubbed"

    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    monkeypatch.setattr(shep, "bead_strip", slow_strip)
    screen = _ViewScreen([key])

    started_at = time.monotonic()
    _beads, target = shep.run_beads_view(screen, ascii_only=True)
    elapsed = time.monotonic() - started_at
    release.set()

    assert target == expected
    assert elapsed < 0.5
    assert started.wait(0.5)


def test_beads_view_keeps_cached_rows_visible_while_triage_runs(monkeypatch) -> None:
    """A cached collection remains useful while the fresh verdict is pending."""
    started = threading.Event()
    release = threading.Event()
    shep._remember_loaded_beads(_BEAD_ROWS, None)

    def slow_strip(_beads, force=False):
        started.set()
        release.wait(2)
        return [], {}, "stubbed"

    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    monkeypatch.setattr(shep, "bead_strip", slow_strip)
    screen = _ViewScreen([-1, ord("3")])

    _beads, target = shep.run_beads_view(screen, ascii_only=True)
    release.set()

    assert target == "missions"
    assert "alpha | alpha-1 | open | P0 | c:? u:? | First" in screen.screen_text()
    assert started.wait(0.5)


def test_beads_view_contains_triage_failure_and_stays_navigable(monkeypatch) -> None:
    """A provider exception becomes a visible state, never a dead curses UI."""
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))

    def broken_strip(_beads, force=False):
        raise RuntimeError("triage gateway unavailable")

    monkeypatch.setattr(shep, "bead_strip", broken_strip)
    screen = _ViewScreen([-1, ord("q")])

    beads, target = shep.run_beads_view(screen, ascii_only=True)

    assert target == "agents"
    assert beads == _BEAD_ROWS
    assert "refresh failed: triage gateway unavailable" in screen.screen_text()


def test_logs_view_keeps_tab_navigation_live_during_slow_ledger_read(monkeypatch) -> None:
    """A large or unavailable ledger must not trap the operator in LOGS."""
    started = threading.Event()
    release = threading.Event()

    def slow_log():
        started.set()
        release.wait(2)
        return [], None

    monkeypatch.setattr(shep, "load_action_log", slow_log)
    screen = _ViewScreen([ord("2")])

    started_at = time.monotonic()
    _entries, target = shep.run_logs_view(screen, ascii_only=True)
    elapsed = time.monotonic() - started_at
    release.set()

    assert target == "beads"
    assert elapsed < 0.5
    assert started.wait(0.5)


def test_beads_view_selection_never_leaves_the_list(monkeypatch) -> None:
    """j past the end / k past the top used to be the classic index crash."""
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    keys = [ord("j")] * 4 + [ord("k")] * 6 + [ord("q")]

    _beads, target = shep.run_beads_view(_ViewScreen(keys), ascii_only=True)

    assert target == "agents"


def test_beads_view_refresh_rereads_every_repo(monkeypatch) -> None:
    calls = []

    def reload_beads():
        calls.append(1)
        return _BEAD_ROWS[: len(calls)], None

    monkeypatch.setattr(shep, "load_beads", reload_beads)
    monkeypatch.setattr(shep, "bead_strip", lambda beads, force=False: ([], {}, "stubbed"))

    beads, _target = shep.run_beads_view(
        _ViewScreen([ord("r"), -1, ord("q")]), ascii_only=True
    )

    assert calls
    assert beads in (_BEAD_ROWS[:1], _BEAD_ROWS[:2])


def test_beads_view_stays_put_on_its_own_tab_key(monkeypatch) -> None:
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))

    _beads, target = shep.run_beads_view(
        _ViewScreen([ord("2"), ord("q")]), ascii_only=True
    )

    assert target == "agents"


def test_beads_view_handles_an_empty_workspace_without_crashing(monkeypatch) -> None:
    monkeypatch.setattr(shep, "load_beads", lambda: ([], None))

    beads, target = shep.run_beads_view(
        _ViewScreen([ord("j"), ord("k"), ord("q")]), ascii_only=True
    )

    assert (beads, target) == ([], "agents")


# --- run_missions_view ------------------------------------------------------

_DECK = [
    {"id": "mission-a", "project_name": "alpha", "short_goal": "Ship it",
     "momentum_score": 53, "mission_kind": "delivery", "next_step": "do the thing"},
    {"id": "mission-b", "project_name": "beta", "short_goal": "Scout it",
     "momentum_score": 9, "mission_kind": "research"},
]


@pytest.fixture
def _deck(monkeypatch):
    monkeypatch.setattr(
        shep, "load_mission_deck", lambda force=False, allow_generate=True: (list(_DECK), None)
    )
    monkeypatch.setattr(shep, "record_mission_decision", lambda *_a: True)


def test_missions_view_labels_build_and_research_rows(_deck) -> None:
    """The BUILD/RESEARCH label is the only on-screen warning that code gets written."""
    screen = _ViewScreen([ord("q")])

    missions, target = shep.run_missions_view(screen, ascii_only=True)

    assert (len(missions), target) == (2, "agents")
    painted = screen.screen_text()
    assert "1. [ 53] BUILD alpha — Ship it" in painted
    assert "2. [  9] RESEARCH beta — Scout it" in painted


def test_missions_view_never_launches_without_an_explicit_capital_y(
    _deck, monkeypatch
) -> None:
    """Any key but Y must cancel — this confirm guards a code-writing agent."""
    launched = []
    monkeypatch.setattr(
        shep, "launch_mission_by_id", lambda mid: launched.append(mid) or (True, "ok")
    )
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("y"))
    screen = _ViewScreen([10, ord("q")])

    shep.run_missions_view(screen, ascii_only=True)

    assert launched == []
    assert "launch cancelled" in screen.screen_text()


def test_missions_view_launches_the_selected_mission_on_capital_y(
    _deck, monkeypatch
) -> None:
    launched = []
    monkeypatch.setattr(
        shep,
        "launch_mission_by_id",
        lambda mid: (launched.append(mid), (True, "started"))[1],
    )
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("Y"))
    screen = _ViewScreen([ord("j"), 10, ord("q")])

    missions, _target = shep.run_missions_view(screen, ascii_only=True)

    assert launched == ["mission-b"]
    # Stays in the deck — dropping it hid the fact that it was running.
    assert [m["id"] for m in missions] == ["mission-a", "mission-b"]
    assert "launched: started" in screen.screen_text()


def _running(monkeypatch, *ids):
    monkeypatch.setattr(shep, "mission_is_running", lambda m: m.get("id") in ids)


def test_missions_view_marks_a_running_mission(_deck, monkeypatch) -> None:
    """A launched mission used to vanish, then reappear unmarked — it looked
    like a backlog that never progressed."""
    _running(monkeypatch, "mission-b")
    screen = _ViewScreen([ord("q")])

    shep.run_missions_view(screen, ascii_only=True)

    rows = [line for line in screen.painted if line[:2] in ("1.", "2.")]
    assert rows == [
        "1. [ 53] BUILD alpha — Ship it",
        "2. [  9] RUNNING RESEARCH beta — Scout it",
    ]


def test_missions_view_refuses_to_relaunch_a_running_mission(_deck, monkeypatch) -> None:
    """Relaunching force-removes the worktree the live agent is working in."""
    _running(monkeypatch, "mission-a")
    monkeypatch.setattr(
        shep, "launch_mission_by_id", lambda _m: pytest.fail("must not relaunch")
    )
    monkeypatch.setattr(
        shep, "blocking_getch", lambda _s: pytest.fail("must not even prompt")
    )
    screen = _ViewScreen([10, ord("q")])

    shep.run_missions_view(screen, ascii_only=True)

    assert "already running — reap it first to relaunch" in screen.screen_text()


def test_missions_view_running_state_survives_a_deck_regenerate(_deck, monkeypatch) -> None:
    """The marker reads the worktree on disk, not an in-memory flag, so a
    restart or a second shep instance still shows what is in flight."""
    _running(monkeypatch, "mission-a")

    screen = _ViewScreen([ord("r"), ord("q")])
    shep.run_missions_view(screen, ascii_only=True)

    assert "1. [ 53] RUNNING BUILD alpha — Ship it" in screen.screen_text()


def test_missions_view_warns_that_a_build_mission_writes_code(_deck, monkeypatch) -> None:
    prompts = []
    monkeypatch.setattr(
        shep, "blocking_getch", lambda screen: prompts.append(_frame(screen)) or ord("n")
    )
    screen = _ViewScreen([10, ord("q")])

    shep.run_missions_view(screen, ascii_only=True)

    assert "WRITES CODE on its own branch" in prompts[0]


def test_missions_view_calls_a_research_scout_artifact_only(_deck, monkeypatch) -> None:
    prompts = []
    monkeypatch.setattr(
        shep, "blocking_getch", lambda screen: prompts.append(_frame(screen)) or ord("n")
    )
    screen = _ViewScreen([ord("j"), 10, ord("q")])

    shep.run_missions_view(screen, ascii_only=True)

    assert "artifact-only research" in prompts[0]
    assert "WRITES CODE" not in prompts[0]


def test_missions_view_keeps_a_failed_launch_in_the_deck(_deck, monkeypatch) -> None:
    """Dropping it would hide the failure and lose the retry."""
    monkeypatch.setattr(
        shep, "launch_mission_by_id", lambda _mid: (False, "worktree setup failed")
    )
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("Y"))
    screen = _ViewScreen([10, ord("q")])

    missions, _target = shep.run_missions_view(screen, ascii_only=True)

    assert [m["id"] for m in missions] == ["mission-a", "mission-b"]
    assert "launch failed: worktree setup failed" in screen.screen_text()


def test_missions_view_dismiss_records_the_training_signal(_deck, monkeypatch) -> None:
    recorded = []
    monkeypatch.setattr(
        shep,
        "record_mission_decision",
        lambda event, mission: (recorded.append((event, mission["id"])), True)[1],
    )
    screen = _ViewScreen([ord("d"), ord("q")])

    missions, _target = shep.run_missions_view(screen, ascii_only=True)

    assert recorded == [("dismiss", "mission-a")]
    assert [m["id"] for m in missions] == ["mission-b"]


def test_missions_view_says_so_when_the_learner_cannot_record(_deck, monkeypatch) -> None:
    monkeypatch.setattr(shep, "record_mission_decision", lambda *_a: False)
    screen = _ViewScreen([ord("d"), ord("q")])

    shep.run_missions_view(screen, ascii_only=True)

    assert "learner unavailable" in screen.screen_text()


def test_missions_view_regen_forces_a_fresh_deck(_deck, monkeypatch) -> None:
    forced = []

    def reload_deck(force=False, allow_generate=True):
        forced.append(force)
        return list(_DECK), None

    monkeypatch.setattr(shep, "load_mission_deck", reload_deck)

    shep.run_missions_view(_ViewScreen([ord("r"), ord("q")]), ascii_only=True)

    assert forced == [False, True]


@pytest.mark.parametrize(
    ("key", "expected"),
    [(ord("q"), "agents"), (27, "agents"), (ord("1"), "agents"), (ord("2"), "beads")],
)
def test_missions_view_routes_every_exit_key(_deck, key, expected) -> None:
    _missions, target = shep.run_missions_view(_ViewScreen([key]), ascii_only=True)

    assert target == expected


def test_missions_view_keeps_tab_navigation_live_during_slow_generation(monkeypatch) -> None:
    """A cold sense/recommend run must not trap the operator in MISSIONS."""
    started = threading.Event()
    release = threading.Event()

    def slow_deck(force=False, allow_generate=True):
        started.set()
        release.wait(2)
        return list(_DECK), None

    monkeypatch.setattr(shep, "load_mission_deck", slow_deck)
    screen = _ViewScreen([ord("2")])

    started_at = time.monotonic()
    _missions, target = shep.run_missions_view(screen, ascii_only=True)
    elapsed = time.monotonic() - started_at
    release.set()

    assert target == "beads"
    assert elapsed < 0.5
    assert started.wait(0.5)


def test_missions_view_ignores_launch_and_dismiss_on_an_empty_deck(monkeypatch) -> None:
    """Both handlers index missions[selected]; an empty deck must not reach them."""
    monkeypatch.setattr(
        shep, "load_mission_deck", lambda force=False, allow_generate=True: ([], "no missions found")
    )
    monkeypatch.setattr(
        shep, "launch_mission_by_id",
        lambda _mid: pytest.fail("must not launch from an empty deck"),
    )
    screen = _ViewScreen([10, ord("l"), ord("d"), ord("q")])

    missions, target = shep.run_missions_view(screen, ascii_only=True)

    assert (missions, target) == ([], "agents")


def test_beads_view_says_it_is_scanning_before_the_slow_load(monkeypatch) -> None:
    """A cold fleet scan blocks ~1s; an unpainted screen reads as a hang."""
    painted_before = []

    def slow_load():
        painted_before.extend(screen.painted)
        return _BEAD_ROWS, None

    monkeypatch.setattr(shep, "load_beads", slow_load)
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert any("scanning repos for open beads" in line for line in painted_before)


def test_beads_view_says_it_is_rescanning_on_refresh(monkeypatch) -> None:
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    screen = _ViewScreen([ord("r"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "refresh" in screen.screen_text()


def test_beads_refresh_rescans_for_newly_created_repos(monkeypatch) -> None:
    """Without busting the TTL cache, a repo that just gained a .beads/ stays
    invisible for 5 minutes even after you press r."""
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    shep._BEADS_REPO_CACHE.update(at=time.time(), repos=["/repos/alpha"])

    shep.run_beads_view(_ViewScreen([ord("r"), ord("q")]), ascii_only=True)

    assert shep._BEADS_REPO_CACHE["at"] == 0.0


def test_beads_status_line_reports_the_repo_spread(monkeypatch) -> None:
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "2 open beads across 2 repos" in screen.screen_text()


# --- the mission strip on the BEADS tab -------------------------------------


def _strip(monkeypatch, missions=(), prune=None, note="triage: claude"):
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    monkeypatch.setattr(
        shep, "bead_strip",
        lambda _beads, force=False: (list(missions), dict(prune or {}), note),
    )
    monkeypatch.setattr(shep, "mission_is_running", lambda _mission: False)


_STRIP_MISSION = {
    "id": "alpha-1", "bead_id": "alpha-1", "cwd": "/repos/alpha",
    "project_name": "alpha", "momentum_score": 85,
    "short_goal": "Close alpha-1: First", "rationale": "unblocks two beads",
}


def test_beads_view_paints_the_strip_above_the_backlog(monkeypatch) -> None:
    """The ask: open BEADS and the work worth firing off is already on screen."""
    _strip(monkeypatch, [_STRIP_MISSION])
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    frame = _frame(screen)
    assert frame.index("MISSIONS FROM BEADS") < frame.index("REPO | ID | STATUS")
    assert "Close alpha-1: First" in frame
    assert "unblocks two beads" in frame
    assert "triage: claude" in frame


def test_beads_view_marks_the_beads_the_model_says_to_prune(monkeypatch) -> None:
    """Naming what to close unworked is half of what the triage is for."""
    _strip(monkeypatch, [], {"beta-9": "superseded by alpha-1"})
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    tagged = [line for line in _frame(screen).splitlines() if "PRUNE:" in line]
    assert len(tagged) == 1
    assert "beta-9" in tagged[0] and "superseded by alpha-1" in tagged[0]


def test_beads_view_lists_the_prunable_beads_first(monkeypatch) -> None:
    """beta-9 sorts second by priority; the triage verdict pulls it to the top."""
    _strip(monkeypatch, [], {"beta-9": "superseded"})
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    frame = _frame(screen)
    assert frame.index("beta-9") < frame.index("alpha-1")


def test_beads_view_launches_the_selected_strip_mission(monkeypatch) -> None:
    """Enter has to reach the real launcher, not just move a cursor."""
    launched = []
    _strip(monkeypatch, [_STRIP_MISSION])
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda mission_id, mission=None, **_kw: (
        launched.append((mission_id, mission is not None)) or (True, "started")
    ))
    monkeypatch.setattr(shep, "record_mission_decision", lambda *_a: True)
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("Y"))
    screen = _ViewScreen([10, ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert launched == [("alpha-1", True)]  # passed inline, no deck-cache round trip
    assert "launched: started" in _frame(screen)


def test_beads_view_launch_needs_an_explicit_confirmation(monkeypatch) -> None:
    """These missions write code on their own branch; Enter alone is not consent."""
    _strip(monkeypatch, [_STRIP_MISSION])
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda *_a, **_kw: pytest.fail("launched without a Y"))
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("n"))
    screen = _ViewScreen([10, ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "launch cancelled" in _frame(screen)


def test_beads_view_refuses_to_relaunch_a_running_mission(monkeypatch) -> None:
    _strip(monkeypatch, [_STRIP_MISSION])
    monkeypatch.setattr(shep, "mission_is_running", lambda _mission: True)
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda *_a, **_kw: pytest.fail("relaunched a live worktree"))
    screen = _ViewScreen([10, ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "already running" in _frame(screen)


def test_beads_view_tab_moves_selection_between_the_two_lists(monkeypatch) -> None:
    """Two lists, one cursor each — j must drive whichever one has focus."""
    _strip(monkeypatch, [_STRIP_MISSION])
    screen = _ViewScreen([ord("j"), ord("\t"), ord("j"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    # Focus started on the strip, so the first j could not move the backlog
    # cursor; after tab the second j selects the backlog's second row.
    frames = screen.screen_text().split("--erase--")
    assert "beta-9" in frames[-1]


def test_beads_view_enter_does_nothing_while_the_backlog_has_focus(monkeypatch) -> None:
    """The backlog is a read-only list; Enter there must not launch anything."""
    _strip(monkeypatch, [_STRIP_MISSION])
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda *_a, **_kw: pytest.fail("launched from the backlog"))
    screen = _ViewScreen([ord("\t"), 10, ord("q")])

    shep.run_beads_view(screen, ascii_only=True)


def test_beads_view_closes_a_pruned_bead_on_x(monkeypatch) -> None:
    """The keystroke has to reach bd, not just drop the row from the screen."""
    closed = []
    _strip(monkeypatch, [], {"beta-9": "superseded by alpha-1"})
    monkeypatch.setattr(shep, "close_bead", lambda bead, reason: (
        closed.append((bead["id"], reason)) or (True, f"closed {bead['id']}")
    ))
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("x"))
    # tab to the backlog, j onto beta-9 (prune sorts it first, so j is not
    # needed), x to close.
    screen = _ViewScreen([ord("\t"), ord("x"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert closed == [("beta-9", "superseded by alpha-1")]
    frame = _frame(screen)
    assert "closed beta-9" in frame
    # Match the backlog ROW, not any mention of the id: the status line now
    # carries a "scanned Ns ago" suffix, so a bare "beta-9 |" substring also
    # matches the success message and the check silently passes nothing.
    assert not [line for line in frame.splitlines() if line.startswith("beta |")]


def test_beads_view_close_needs_the_repeat_key(monkeypatch) -> None:
    """Closing a bead unworked is a write to a shared tracker, and this TUI
    confirms a destructive action by repeating its own key."""
    _strip(monkeypatch, [], {"beta-9": "stale"})
    monkeypatch.setattr(shep, "close_bead", lambda *_a: pytest.fail("closed without the repeat"))
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("n"))
    screen = _ViewScreen([ord("\t"), ord("x"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "close cancelled" in _frame(screen)


def test_beads_view_close_rejects_a_y_confirmation(monkeypatch) -> None:
    """[Y] is the launch convention; a destructive close must not accept it,
    or the two keys quietly mean different things in the same view."""
    _strip(monkeypatch, [], {"beta-9": "stale"})
    monkeypatch.setattr(shep, "close_bead", lambda *_a: pytest.fail("Y closed a bead"))
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("Y"))
    screen = _ViewScreen([ord("\t"), ord("x"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "close cancelled" in _frame(screen)


def test_beads_view_close_prompt_names_the_repeat_key(monkeypatch) -> None:
    """The prompt has to teach the convention, matching the reap key's wording."""
    _strip(monkeypatch, [], {"beta-9": "stale"})
    monkeypatch.setattr(shep, "close_bead", lambda *_a: (True, "closed"))
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("x"))
    screen = _ViewScreen([ord("\t"), ord("x"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "Press [x] again to confirm" in screen.screen_text()


def test_beads_view_refuses_to_close_a_bead_the_triage_did_not_flag(monkeypatch) -> None:
    """Closing work nobody judged prunable is the one mistake this key could
    make that the operator would not notice until the work went missing."""
    _strip(monkeypatch, [], {})
    monkeypatch.setattr(shep, "close_bead", lambda *_a: pytest.fail("closed an unflagged bead"))
    screen = _ViewScreen([ord("\t"), ord("x"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "only beads the triage flagged" in _frame(screen)


def test_beads_view_x_does_nothing_while_the_strip_has_focus(monkeypatch) -> None:
    """Focus is on the strip at entry; x there must not close the backlog's row."""
    _strip(monkeypatch, [_STRIP_MISSION], {"beta-9": "stale"})
    monkeypatch.setattr(shep, "close_bead", lambda *_a: pytest.fail("closed from the strip"))

    shep.run_beads_view(_ViewScreen([ord("x"), ord("q")]), ascii_only=True)


def test_beads_view_keeps_the_bead_listed_when_the_close_fails(monkeypatch) -> None:
    """Dropping a row the tracker still has open would hide real work."""
    _strip(monkeypatch, [], {"beta-9": "stale"})
    monkeypatch.setattr(shep, "close_bead", lambda *_a: (False, "bd not installed"))
    monkeypatch.setattr(shep, "blocking_getch", lambda _screen: ord("x"))
    screen = _ViewScreen([ord("\t"), ord("x"), ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    frame = _frame(screen)
    assert "close failed: bd not installed" in frame
    assert "beta-9" in frame


def test_beads_view_footer_advertises_the_close_key(monkeypatch) -> None:
    _strip(monkeypatch, [], {})
    screen = _ViewScreen([ord("q")])

    shep.run_beads_view(screen, ascii_only=True)

    assert "[x] close pruned" in _frame(screen)


def test_beads_view_refresh_reasks_the_model(monkeypatch) -> None:
    """[r] means the operator judged the cached verdict stale."""
    forced = []
    monkeypatch.setattr(shep, "load_beads", lambda: (_BEAD_ROWS, None))
    monkeypatch.setattr(shep, "bead_strip", lambda _beads, force=False: (
        forced.append(force) or ([], {}, "triage: claude")
    ))
    monkeypatch.setattr(shep, "mission_is_running", lambda _mission: False)

    shep.run_beads_view(_ViewScreen([ord("r"), ord("q")]), ascii_only=True)

    assert forced == [False, True]


def test_a_stranded_pane_puts_one_banner_on_screen(monkeypatch) -> None:
    """The report repeats every pass; the banner must not.

    A stranded pane has to keep appearing in the log or it goes silent again,
    but a banner on that cadence is a notification every five minutes until the
    operator learns to dismiss all of them unread.
    """
    banners = []
    target = "herdr:w1:p1"
    _nudged_pane(target, attempt=shep.MAX_NUDGE_ATTEMPTS)
    shep.update_stall(target, "pytest running", "idle")
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(
        shep, "notify_operator", lambda sub, msg: banners.append((sub, msg)),
    )
    row = _sweep_row()
    row["target"] = target

    shep.sweep(send=True, rows=[row])
    shep.sweep(send=True, rows=[row])

    assert banners == [
        (
            f"{row['label']} needs you",
            f"{shep.MAX_NUDGE_ATTEMPTS} nudges did not move this on",
        ),
    ]
    shep._SIG_STATE.clear()
    shep._NUDGE_STATE.clear()


def test_a_model_written_reason_cannot_break_out_of_the_banner_script() -> None:
    """The reason reaches osascript as source, so a bare quote would be code."""
    quoted = shep._applescript_string('say "hi"; do shell script "rm -rf /"')

    assert quoted.startswith('"') and quoted.endswith('"')
    # Every inner quote stays escaped, so the string never closes early and the
    # payload can only ever be read as text.
    assert quoted.count('"') - quoted.count('\\"') == 2


def test_the_banner_survives_a_machine_with_no_notifier(monkeypatch) -> None:
    """Losing a banner is bad; losing the sweep behind it is worse."""
    def _missing(*a, **k):
        raise FileNotFoundError("osascript")

    monkeypatch.delenv("SHEP_NO_NOTIFY", raising=False)
    monkeypatch.setattr(shep.subprocess, "run", _missing)

    shep.notify_operator("pane needs you", "reconnect Twingate")


def _stranded(label="ai-gateway"):
    # Every real pane carries the agent name in `label`, so a fixture that puts
    # the repo there is the reason the first digest shipped saying "claude,
    # claude, claude". Name these the way live rows are named.
    row = _sweep_row()
    row["label"] = "claude"
    row["cwd"] = f"/Users/developer/repos/{label}"
    return [(row, "3 nudges did not move this on")]


def test_the_digest_names_every_pane_still_waiting_on_you(tmp_path) -> None:
    """The per-pane banner fires once ever, so a dismissed one is gone for good.

    This is the standing counterpart: it re-raises the whole stranded set,
    including panes escalated days ago, so forgetting costs a day not a pane.
    """
    stamp = tmp_path / "stamp.txt"
    at_nine = datetime.datetime(2026, 8, 7, 9, 0)

    line = shep.send_daily_digest(_stranded(), now=at_nine, path=stamp)

    assert "2 still" not in line
    assert "1 still waiting on you" in line and "ai-gateway" in line
    # Not the agent name. Keyed on `label` every entry reads "claude" and the
    # digest names nothing the operator can act on.
    assert "claude" not in line
    assert stamp.read_text() == "2026-08-07"


def test_the_digest_is_sent_once_a_day_and_again_the_next(tmp_path) -> None:
    stamp = tmp_path / "stamp.txt"
    day_one = datetime.datetime(2026, 8, 7, 9, 0)
    shep.send_daily_digest(_stranded(), now=day_one, path=stamp)

    assert shep.digest_due(now=day_one.replace(hour=14), path=stamp) is False
    assert shep.digest_due(
        now=day_one + datetime.timedelta(days=1), path=stamp,
    ) is True


def test_the_digest_waits_for_a_waking_hour(tmp_path) -> None:
    """Keyed on the date alone it lands at whatever minute past midnight the
    first pass runs — a notification nobody is awake for, which then blocks the
    one they would have read."""
    assert shep.digest_due(
        now=datetime.datetime(2026, 8, 7, 3, 0), path=tmp_path / "absent.txt",
    ) is False


def test_an_unblocked_deck_gets_no_daily_banner(tmp_path) -> None:
    """A "0 waiting" banner every morning is the fastest way to teach the
    operator that shep's notifications are noise."""
    stamp = tmp_path / "stamp.txt"

    assert shep.send_daily_digest([], now=datetime.datetime(2026, 8, 7, 9, 0),
                                  path=stamp) is None
    assert not stamp.exists()


def test_a_dry_run_cannot_consume_the_days_digest(monkeypatch, tmp_path) -> None:
    """Otherwise a manual `--sweep` check leaves the unattended pass mute."""
    monkeypatch.setattr(shep, "DIGEST_STAMP_FILE", tmp_path / "stamp.txt")
    monkeypatch.setattr(shep, "digest_due", lambda *a, **k: True)
    sent = []
    monkeypatch.setattr(shep, "send_daily_digest", lambda *a, **k: sent.append(a))
    _stub_draft(monkeypatch, "NO_NUDGE")
    shep._NUDGE_STATE.clear()

    shep.sweep(send=False, rows=[_sweep_row()])

    assert sent == []
    shep._NUDGE_STATE.clear()


# --- ClickUp escalations ------------------------------------------------------
#
# The 2026-09-07 Forge-outage postmortem: NEEDS-HUMAN handoffs existed only as
# an osascript banner and a log line nobody opened, so ~268 report lines across
# a 22h tunnel outage produced zero owner-visible pings. These pin that the
# escalation channel fires, stays rare, and can never take the sweep down.


def test_an_escalation_post_reaches_the_configured_channel(monkeypatch) -> None:
    monkeypatch.setattr(shep, "CLICKUP_ESCALATION_CHANNEL", "dm-1")
    monkeypatch.setattr(shep, "_clickup_token", lambda: "tok")
    sent = {}

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=None):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data.decode())
        sent["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(shep.urllib.request, "urlopen", fake_urlopen)

    posted, reason = shep.post_escalation("🚨 check the forge")

    assert posted is True and reason == "200"
    assert sent["url"].endswith("/chat/channels/dm-1/messages")
    assert sent["body"] == {"content": "🚨 check the forge"}
    assert sent["timeout"] == 15


def test_an_escalation_without_a_channel_is_inert() -> None:
    """An unconfigured channel must never block a sweep, same as telemetry."""
    posted, reason = shep.post_escalation("x")
    assert posted is False and "no escalation channel" in reason


def test_a_dead_network_never_breaks_the_escalation_path(monkeypatch) -> None:
    monkeypatch.setattr(shep, "CLICKUP_ESCALATION_CHANNEL", "dm-1")
    monkeypatch.setattr(shep, "_clickup_token", lambda: "tok")
    monkeypatch.setattr(shep.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    posted, reason = shep.post_escalation("x")
    assert posted is False and reason == "OSError"


def test_an_escalation_retries_once_on_a_rate_limit(monkeypatch) -> None:
    """The escalation is the one message that must land; a shared-token 429 is
    the most likely way it wouldn't. One bounded retry, nothing more."""
    monkeypatch.setattr(shep, "CLICKUP_ESCALATION_CHANNEL", "dm-1")
    monkeypatch.setattr(shep, "_clickup_token", lambda: "tok")
    sleeps = []
    monkeypatch.setattr(shep.time, "sleep", lambda s: sleeps.append(s))
    statuses = [429, 201]

    class _Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def throttled_urlopen(request, timeout=None):
        if statuses.pop(0) == 429:
            raise shep.urllib.error.HTTPError(
                request.full_url, 429, "Rate limit reached", None, None,
            )
        return _Response()

    monkeypatch.setattr(shep.urllib.request, "urlopen", throttled_urlopen)

    posted, reason = shep.post_escalation("x")

    assert posted is True and reason == "201"
    assert sleeps == [5.0]


def test_a_non_rate_limit_http_failure_does_not_retry(monkeypatch) -> None:
    monkeypatch.setattr(shep, "CLICKUP_ESCALATION_CHANNEL", "dm-1")
    monkeypatch.setattr(shep, "_clickup_token", lambda: "tok")
    sleeps = []
    monkeypatch.setattr(shep.time, "sleep", lambda s: sleeps.append(s))
    calls = []

    def forbidden_urlopen(request, timeout=None):
        calls.append(1)
        raise shep.urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", None, None,
        )

    monkeypatch.setattr(shep.urllib.request, "urlopen", forbidden_urlopen)

    posted, reason = shep.post_escalation("x")

    assert posted is False and reason == "HTTP403"
    assert sleeps == [] and len(calls) == 1


def test_the_handoff_is_posted_to_clickup_once_not_every_pass(monkeypatch) -> None:
    """The DM rides the same one-shot gate as the banner: once per pane."""
    posted = []
    monkeypatch.setattr(
        shep, "post_escalation",
        lambda message: posted.append(message) or (True, "200"),
    )
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(
        shep, "llm_draft_nudge",
        lambda *a, **k: pytest.fail("an escalated pane must not be drafted for"),
    )
    target = "herdr:w1:p1"
    shep._nudge_state(target).update({
        "exhausted_reason": "needs_human",
        "needs_human_reason": "approve the customer refund email",
    })
    row = _sweep_row()
    row["target"] = target

    shep.sweep(send=True, rows=[row])
    shep.sweep(send=True, rows=[row])

    assert len(posted) == 1
    assert "NEEDS-HUMAN" in posted[0]
    assert "approve the customer refund email" in posted[0]
    shep._NUDGE_STATE.clear()


def test_the_digest_is_posted_to_clickup_with_each_reason(
    monkeypatch, tmp_path,
) -> None:
    """The banner is one line; the DM carries the why, or it names nothing."""
    posted = []
    monkeypatch.setattr(
        shep, "post_escalation",
        lambda message: posted.append(message) or (True, "200"),
    )
    stamp = tmp_path / "stamp.txt"

    shep.send_daily_digest(
        _stranded(), now=datetime.datetime(2026, 8, 7, 9, 0), path=stamp,
    )

    assert len(posted) == 1
    assert "ai-gateway" in posted[0]
    assert "3 nudges did not move this on" in posted[0]


def test_a_digest_that_cannot_post_still_banners_and_stamps(
    monkeypatch, tmp_path,
) -> None:
    monkeypatch.setattr(shep, "post_escalation", lambda message: (False, "OSError"))
    monkeypatch.setattr(shep, "notify_operator", lambda *a, **k: None)
    stamp = tmp_path / "stamp.txt"

    line = shep.send_daily_digest(
        _stranded(), now=datetime.datetime(2026, 8, 7, 9, 0), path=stamp,
    )

    assert line is not None and stamp.exists()


# --- Infra-blocked panes: retry on recovery -----------------------------------
#
# "Reconnect Twingate…" parks a pane on a network, not on the operator's
# judgment. When that network heals, the pane must re-enter the ladder without
# a human running --release.


def test_a_handoff_reason_that_names_infra_is_recognised() -> None:
    assert shep.infra_blocker(
        "Reconnect Twingate to restore Forge access; "
        "pushes are blocked by 404 responses."
    )
    assert shep.infra_blocker(
        "reconnect the VPN so the Forge becomes reachable and the MRs can open"
    )
    assert not shep.infra_blocker("3 nudges did not move this on")
    assert not shep.infra_blocker("approve the customer refund email")
    assert not shep.infra_blocker("")


def test_infra_recovery_releases_the_stranded_pane_back_into_the_engine(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shep, "infra_probe_healthy", lambda: True)
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    drafted = []
    monkeypatch.setattr(
        shep, "get_pane_context",
        lambda row, lines=15: "pytest failed in test_api.py\n",
    )
    monkeypatch.setattr(
        shep, "clean_context_lines", lambda ctx: ["pytest failed in test_api.py"],
    )
    monkeypatch.setattr(
        shep, "llm_draft_nudge",
        lambda row, recent, attempt=1, **kwargs: (
            drafted.append(row.get("target")), "Run pytest test_api.py.",
        )[1],
    )
    target = "herdr:w1:p1"
    shep._nudge_state(target).update({
        "exhausted_reason": "needs_human",
        "needs_human_reason": "Reconnect Twingate to restore Forge access; "
        "pushes are blocked by 404 responses.",
        "handoff_announced": True,
        "attempt": shep.MAX_NUDGE_ATTEMPTS,
        "assessed_fingerprint": "stale-by-outage",
    })
    row = _sweep_row()
    row["target"] = target

    results, _held, escalated = shep.sweep(send=False, rows=[row])

    # No longer the operator's problem, and drafted for on this same pass.
    assert escalated == []
    assert drafted == [target]
    assert [r for r, _text, _ok, _detail in results] == [row]
    state = shep._nudge_state(target)
    assert state["exhausted_reason"] is None
    assert state["attempt"] == 1
    # The stale-by-outage fingerprint is gone; what sits here now is the one
    # this pass just assessed — evidence the pane was actually re-drafted, not
    # merely un-parked.
    assert state["assessed_fingerprint"] not in (None, "stale-by-outage")
    shep._NUDGE_STATE.clear()


def test_infra_still_down_leaves_the_pane_waiting_on_the_operator(
    monkeypatch,
) -> None:
    monkeypatch.setattr(shep, "infra_probe_healthy", lambda: False)
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(shep, "post_escalation", lambda message: (True, "200"))
    monkeypatch.setattr(
        shep, "llm_draft_nudge",
        lambda *a, **k: pytest.fail("an escalated pane must not be drafted for"),
    )
    target = "herdr:w1:p1"
    shep._nudge_state(target).update({
        "exhausted_reason": "needs_human",
        "needs_human_reason": "Reconnect Twingate to restore Forge access",
        "handoff_announced": True,
    })
    row = _sweep_row()
    row["target"] = target

    results, held, escalated = shep.sweep(send=True, rows=[row])

    assert [r for r, _ in escalated] == [row]
    assert results == [] and held == []
    shep._NUDGE_STATE.clear()


def test_a_healthy_probe_never_releases_a_non_infra_handoff(monkeypatch) -> None:
    monkeypatch.setattr(shep, "infra_probe_healthy", lambda: True)
    monkeypatch.setattr(shep, "post_telemetry", lambda *a, **k: None)
    monkeypatch.setattr(shep, "post_escalation", lambda message: (True, "200"))
    monkeypatch.setattr(
        shep, "llm_draft_nudge",
        lambda *a, **k: pytest.fail("an escalated pane must not be drafted for"),
    )
    target = "herdr:w1:p1"
    shep._nudge_state(target).update({
        "exhausted_reason": "needs_human",
        "needs_human_reason": "approve the customer refund email",
        "handoff_announced": True,
    })
    row = _sweep_row()
    row["target"] = target

    _results, _held, escalated = shep.sweep(send=True, rows=[row])

    assert [r for r, _ in escalated] == [row]
    shep._NUDGE_STATE.clear()


def test_the_infra_probe_is_cached_for_one_sweep(monkeypatch) -> None:
    """One connect per sweep, not one per pane: a dead tunnel fails slowly."""
    monkeypatch.setattr(shep, "_INFRA_PROBE_CACHE", {"at": 0.0, "ok": False})
    monkeypatch.setattr(shep, "INFRA_PROBE_TTL", 150.0)
    calls = []

    class _Sock:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def flaky_create_connection(address, timeout=None):
        calls.append(address)
        if len(calls) == 1:
            raise OSError("refused")
        return _Sock()

    monkeypatch.setattr(shep.socket, "create_connection", flaky_create_connection)

    assert shep.infra_probe_healthy(now=100.0) is False
    assert shep.infra_probe_healthy(now=200.0) is False  # cached, no re-probe
    assert len(calls) == 1
    assert shep.infra_probe_healthy(now=400.0) is True  # past the TTL
    assert len(calls) == 2


# --- Pending-actions queue ---------------------------------------------------
#
# The shortlist of everything shep needs a person for. The fleet table already
# carries all three kinds; these pin that the queue picks the right rows, keeps
# a stable order under the cursor, and maps clicks to the row the operator
# aimed at rather than the one next to it.

def _pending_row(target, cwd="/w/repo", **extra):
    row = {"source": "tmux", "id": target, "target": target, "label": "agent",
           "status": "idle", "cwd": cwd, "quiet_for": shep.NUDGE_QUIET_SECONDS}
    row.update(extra)
    return row


def _clear_pending():
    shep._NUDGE_STATE.clear()
    shep._NUDGE_EVENTS.clear()


def test_the_queue_puts_decisions_before_errands() -> None:
    """Ordered by what answering costs, not by fleet position.

    An APPROVE is a yes/no settled from this screen, a GO sends the operator
    somewhere else, and a CLOSE cannot be taken back.
    """
    _clear_pending()
    rows = [
        _pending_row("%1", reap_ready=True, reap_reason="declared itself done"),
        _pending_row("%2"),
        _pending_row("%3"),
    ]
    shep._nudge_state("%2")["exhausted_reason"] = "needs_human"
    shep._nudge_state("%2")["needs_human_reason"] = "open UDP 10000"
    shep.record_nudge_event("%3", "held", "merge MR !716", "merges without review")

    assert [i["verb"] for i in shep.pending_actions(rows)] == [
        "APPROVE", "GO", "CLOSE",
    ]
    _clear_pending()


def test_the_queue_keeps_fleet_order_inside_a_kind() -> None:
    """A list that reshuffles every tick is one Enter cannot be trusted on."""
    _clear_pending()
    rows = [_pending_row("%1"), _pending_row("%2"), _pending_row("%3")]
    for target in ("%3", "%1", "%2"):
        shep.record_nudge_event(target, "held", f"draft for {target}", "held")

    assert [i["target"] for i in shep.pending_actions(rows)] == ["%1", "%2", "%3"]
    _clear_pending()


def test_a_finished_pane_is_not_also_asked_about_its_draft() -> None:
    """One row, one slot -- otherwise the operator rules on the same pane twice."""
    _clear_pending()
    shep.record_nudge_event("%1", "held", "keep going", "held")
    rows = [_pending_row("%1", reap_ready=True, reap_reason="done")]

    items = shep.pending_actions(rows)

    assert [i["verb"] for i in items] == ["CLOSE"]
    _clear_pending()


def test_an_empty_queue_costs_no_screen() -> None:
    """No box at all, rather than a '0 waiting' header.

    That header would spend a line of fleet table on every screen to report the
    one state the operator wants, which is nothing to do.
    """
    assert shep.pending_panel_lines([], 80) == []


def test_the_queue_shows_the_cursor_once_it_outgrows_the_panel() -> None:
    """Otherwise Enter acts on an item scrolled off the panel."""
    _clear_pending()
    rows = [_pending_row(f"%{n}") for n in range(12)]
    for n in range(12):
        shep.record_nudge_event(f"%{n}", "held", f"draft {n}", "held")
    items = shep.pending_actions(rows)

    lines = shep.pending_panel_lines(items, 80, selected=11, focused=True)

    assert "draft 11" in "\n".join(lines)
    assert shep.pending_panel_start(12, 11) == 12 - shep.PENDING_PANEL_ROWS
    assert shep.pending_panel_start(12, 0) == 0
    assert shep.pending_panel_start(3, 0) == 0
    _clear_pending()


def test_clicking_the_queue_title_selects_nothing() -> None:
    """It is a heading; treating it as item one arms an unaimed action."""
    assert shep.pending_panel_row_at_y(
        shep.SHEP_TAB_Y + 1, panel_height=4, total=3, selected=0,
    ) is None


def test_clicking_a_queue_line_lands_on_that_item() -> None:
    for offset in range(3):
        assert shep.pending_panel_row_at_y(
            shep.SHEP_TAB_Y + 2 + offset, panel_height=4, total=3, selected=0,
        ) == offset
    # Below the last drawn line is the fleet table, not the queue.
    assert shep.pending_panel_row_at_y(
        shep.SHEP_TAB_Y + 5, panel_height=4, total=3, selected=0,
    ) is None


def test_a_fleet_click_accounts_for_the_queue_above_it() -> None:
    """Left at the old constant every click landed one row off per queue line."""
    press = curses.BUTTON1_CLICKED
    without = shep.mouse_selected_row(5, press, 0, 10, 10)
    with_panel = shep.mouse_selected_row(
        5 + 4, press, 0, 10, 10, header_rows=shep.SHEP_TAB_Y + 2 + 4,
    )
    assert without == with_panel == 0


def test_the_queue_cursor_marks_its_fleet_row_with_a_visible_bar() -> None:
    """The followed row used to be indistinguishable from the column header.

    `A_BOLD | A_UNDERLINE` is exactly what the table's own header is drawn
    with, one line above the first fleet row, so clicking a queue item looked
    like it had selected nothing at all -- the cursor moved, it just rendered
    as a second header. Both cursors now carry the bar; the underline is what
    says the queue is the list holding the keys.
    """
    assert shep.fleet_row_attr(False, False) == curses.A_NORMAL
    assert shep.fleet_row_attr(False, True) == curses.A_NORMAL
    assert shep.fleet_row_attr(True, False) == curses.A_REVERSE
    queue_driving = shep.fleet_row_attr(True, True)
    assert queue_driving & curses.A_REVERSE
    assert queue_driving != shep.fleet_row_attr(True, False)
    # The attribute pair the header is painted with, which this must not be.
    assert queue_driving != curses.A_BOLD | curses.A_UNDERLINE


def test_unsupported_mouse_capability_is_diagnosed(monkeypatch) -> None:
    def unreadable():
        raise curses.error("getmouse() returned ERR")

    monkeypatch.setattr(curses, "getmouse", unreadable)

    event = shep.read_mouse_event()

    assert event.kind == "unsupported"
    assert event.detail == "mouse unavailable: getmouse() returned ERR"


def test_the_wheel_scrolls_up_on_button_four(monkeypatch) -> None:
    monkeypatch.setattr(
        curses, "getmouse",
        lambda: (0, 11, 7, 0, curses.BUTTON4_PRESSED),
    )

    event = shep.read_mouse_event()

    assert (event.kind, event.x, event.y) == ("wheel_up", 11, 7)


def test_the_wheel_scrolls_down_on_button_five(monkeypatch) -> None:
    button_five = 1 << 27
    monkeypatch.setattr(shep, "WHEEL_DOWN_MASK", button_five)
    monkeypatch.setattr(
        curses,
        "getmouse",
        lambda: (0, 12, 8, 0, button_five),
    )

    event = shep.read_mouse_event()

    assert (event.kind, event.x, event.y) == ("wheel_down", 12, 8)


def test_an_ordinary_click_is_not_read_as_a_wheel_turn(monkeypatch) -> None:
    """Otherwise every click would also scroll the list it landed in."""
    monkeypatch.setattr(
        curses, "getmouse",
        lambda: (0, 4, 9, 0, curses.BUTTON1_PRESSED),
    )

    event = shep.read_mouse_event()

    assert (event.kind, event.x, event.y) == ("click", 4, 9)
    assert event.button_state & curses.BUTTON1_PRESSED


def test_a_wheel_notch_stays_inside_the_list() -> None:
    """Both ends, and an empty list, which has no row 0 to land on."""
    assert shep.scrolled(0, -1, 5) == 0
    assert shep.scrolled(4, 1, 5) == 4
    assert shep.scrolled(2, 1, 5) == 3
    assert shep.scrolled(2, -1, 5) == 1
    assert shep.scrolled(0, 1, 0) == 0


_RESELECT_ROWS = [
    {"target": "%1", "label": "alpha"},
    {"target": "%2", "label": "bravo"},
    {"target": "%3", "label": "charlie"},
]


def test_a_refresh_follows_the_session_not_the_slot() -> None:
    """A pane appearing ahead of the cursor renumbered everything after it.

    Carrying the position through meant the cursor -- and the context column
    driven off it -- silently moved onto a different session every refresh.
    """
    grew = [{"target": "%0", "label": "zero"}] + _RESELECT_ROWS

    assert shep.reselect(grew, "%3", previous_index=2) == 3
    assert grew[3]["label"] == "charlie"


def test_a_refresh_follows_a_session_that_moved_backwards() -> None:
    """herdr rows sort ahead of tmux, so a claimed pane jumps the list."""
    shrunk = [row for row in _RESELECT_ROWS if row["target"] != "%1"]

    assert shep.reselect(shrunk, "%3", previous_index=2) == 1


def test_a_refresh_clamps_only_when_the_selected_pane_is_gone() -> None:
    """Identity cannot survive the session itself exiting; the slot is all
    that is left, and it still has to be inside the new fleet."""
    without_charlie = _RESELECT_ROWS[:2]

    assert shep.reselect(without_charlie, "%3", previous_index=2) == 1
    assert shep.reselect([], "%3", previous_index=2) == 0


def test_a_refresh_keeps_the_cursor_still_when_nothing_moved() -> None:
    assert shep.reselect(_RESELECT_ROWS, "%2", previous_index=1) == 1


def test_a_session_with_no_target_is_followed_by_its_id() -> None:
    """`target or id` is the key every other consumer reads a row by."""
    rows = [{"id": "happy-1", "label": "daemon"}, {"target": "%2"}]

    assert shep.reselect(rows, "happy-1", previous_index=1) == 0


def test_agents_table_never_starves_the_context_panel() -> None:
    """A busy machine used to grow the table until the panel had no pane text."""
    for height in (18, 24, 40, 60):
        for fleet in (1, 4, 40):
            table_h = shep.agents_table_height(fleet, height)

            assert table_h >= min(2, fleet) or table_h == 2
            assert table_h <= max(2, fleet)
            # Space left below the table for the panel's own detail lines
            # (recap, plan, candidate comparison) AND real pane output.
            assert height - 9 - table_h >= min(shep.MIN_CTX_LINES, (height - 9) // 2)


def test_split_layout_hands_the_whole_body_to_the_fleet_table() -> None:
    """Beside the table, the context no longer competes with it for rows."""
    for height in (24, 40, 60):
        body = height - 9
        stacked = shep.agents_table_height(40, height)
        split = shep.agents_table_height(40, height, split=True)

        assert split > stacked  # the halving exists only to protect a panel below
        assert split <= body    # ...but the footers are still off limits


def test_bracketed_pane_output_is_not_a_status_placeholder() -> None:
    """Sniffing for a leading bracket ate real build output."""
    real = [
        "[INFO] building auth module\n[INFO] 12 files changed",
        "[12:04:31] step 3/9\n[12:04:32] step 4/9",
        "[WARN] retrying once\n[ERROR] connection reset",
        "[pytest] 421 passed",
    ]
    for capture in real:
        assert not shep.is_context_placeholder(capture), capture

    for placeholder in shep.CONTEXT_PLACEHOLDERS:
        assert shep.is_context_placeholder(placeholder)


def test_bracketed_pane_output_still_wraps_line_by_line() -> None:
    """The placeholder branch collapses a whole capture onto one line."""
    capture = "\n".join(f"[INFO] step {i} of 9" for i in range(9))

    segments = shep.context_preview_segments(capture)

    assert len(segments) == 9
    assert [seg[0][0] for seg in segments][0] == "[INFO] step 0 of 9"


def test_a_real_placeholder_is_drawn_as_the_one_line_it_is() -> None:
    segments = shep.context_preview_segments(shep.CONTEXT_LOADING)

    assert segments == [[(shep.CONTEXT_LOADING, curses.A_NORMAL)]]


def test_agents_split_keeps_both_columns_wide_enough_to_read() -> None:
    for width in (120, 150, 199, 240):
        for index in range(len(shep.AGENTS_SPLIT_RATIOS)):
            geometry = shep.agents_split(width, index)

            assert geometry is not None, (width, index)
            left, right_x, right = geometry
            assert right_x == left + 3          # gutter, divider, gutter
            assert left + 3 + right == width    # no column runs off the edge
            assert left >= shep.AGENTS_SPLIT_MIN_LEFT
            assert right >= shep.AGENTS_SPLIT_MIN_RIGHT


def test_a_narrow_terminal_stacks_rather_than_splitting_into_two_unreadable_columns() -> None:
    assert shep.agents_split(shep.AGENTS_SPLIT_MIN_WIDTH - 1, 0) is None
    assert shep.agents_split(80, 1) is None
    assert shep.agents_split(240, None) is None  # operator walked it back under


def test_the_chosen_split_never_costs_the_fleet_its_wide_columns() -> None:
    """Prefer wide fleet columns, while using a compact split when needed."""
    for width in range(120, 260):
        index = shep.auto_split_index(width)
        if index is None:
            continue
        left, _right_x, _right = shep.agents_split(width, index)

        layout_keys = {key for key, _label, _width in shep.table_layout(left)}
        if "repo" in layout_keys:
            assert layout_keys >= {
                "source", "agent", "status", "session", "activity", "repo",
            }, width
        else:
            assert index == 0, width


def test_auto_split_stacks_when_the_fleet_cannot_keep_its_columns() -> None:
    """Use a readable split even when the wide fleet columns do not fit."""
    assert shep.auto_split_index(87) is None
    assert shep.auto_split_index(120) == 0
    assert shep.auto_split_index(139) == 0   # widest left is 104, under the 110 branch
    assert shep.auto_split_index(159) == 0      # context gets the larger side
    assert shep.auto_split_index(199) == 2      # wide fleet columns still fit


def test_footer_advertises_closing_with_enter_and_moving_the_divider() -> None:
    assert "[enter/x] close" in shep.command_footer(160)
    assert "[[/]] split" in shep.command_footer(200)


def test_session_view_windows_the_pane_and_scrolls_back() -> None:
    pane = "\n".join(f"line{i}" for i in range(10)) + "\n\n\n"

    tail = shep.session_view_lines(pane, 3)
    scrolled = shep.session_view_lines(pane, 3, offset=2)

    assert [seg[0][0] for seg in tail] == ["line7", "line8", "line9"]
    assert [seg[0][0] for seg in scrolled] == ["line5", "line6", "line7"]
    assert shep.session_view_lines("", 3)[0][0][0].startswith("[no output")
    # The blank tail is trimmed before the cap, or [k] would scroll into
    # padding the view never renders.
    assert shep.max_session_scroll(pane, 3) == 7


def test_attach_command_matches_the_runtime_holding_the_session() -> None:
    """[o] must never guess a target — a wrong one types at the wrong agent."""
    tmux = {"source": "tmux", "target": "fleet:0.1"}

    assert shep.attach_command(tmux) == ["tmux", "attach", "-t", "fleet:0.1"]
    # attach refuses to nest, so from inside tmux it has to be switch-client —
    # unpinned, because the only tty a process inside a pane can name is the
    # pane's own pty and tmux rejects that as a client.
    assert shep.attach_command(tmux, inside_tmux=True) == [
        "tmux", "switch-client", "-t", "fleet:0.1",
    ]

    herdr = {"source": "herdr", "target": "herdr:w3H:pX"}
    assert shep.attach_command(herdr, tab_id="w3H:tW")[1:] == [
        "tab", "focus", "w3H:tW",
    ]
    assert shep.attach_command(herdr) is None            # tab unresolved
    assert shep.attach_command({"source": "tmux"}) is None
    assert shep.attach_command({"source": "zellij", "target": "z"}) is None


def test_interactive_session_keys_use_the_owning_transport(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)

    ok, _detail = shep.send_session_key(
        {"source": "herdr", "target": "herdr:w3H:pX"}, ord("x"),
    )
    assert ok is True
    assert calls[-1] == [shep.HERDR_BIN, "pane", "send-text", "w3H:pX", "x"]

    ok, _detail = shep.send_session_key(
        {"source": "tmux", "target": "%7"}, curses.KEY_UP,
    )
    assert ok is True
    assert calls[-1] == ["tmux", "send-keys", "-t", "%7", "Up"]

    ok, detail = shep.send_session_key(
        {"source": "t3", "target": "thread-1"}, ord("x"),
    )
    assert ok is False
    assert "do not expose terminal keys" in detail


def test_herdr_interactive_text_preserves_wispr_payload_verbatim(monkeypatch) -> None:
    payload = "Please  review ‘this’, ✅.\nKeep  both lines!"
    screen = FakeScreen(
        keys=bracketed_paste(payload) + ["\x1b", curses.KEY_LEFT],
    )
    calls = []
    _stub_curses(monkeypatch, screen)
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")
    monkeypatch.setattr(
        shep,
        "_run",
        lambda argv, **_kwargs: calls.append(argv)
        or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    shep.run_session_view(
        screen,
        fleet_row("herdr:w3H:pX", "alpha"),
        False,
        interactive=True,
    )

    assert calls == [
        [shep.HERDR_BIN, "pane", "send-text", "w3H:pX", payload],
    ]


def test_tmux_interactive_text_uses_literal_transport(monkeypatch) -> None:
    payload = "Keep  punctuation, Unicode ✅, and\nnewlines."
    screen = FakeScreen(
        keys=bracketed_paste(payload) + ["\x1b", curses.KEY_LEFT],
    )
    calls = []
    _stub_curses(monkeypatch, screen)
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")
    monkeypatch.setattr(
        shep,
        "_run",
        lambda argv, **_kwargs: calls.append(argv)
        or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    shep.run_session_view(
        screen,
        fleet_row("%7", "alpha", source="tmux"),
        False,
        interactive=True,
    )

    assert calls == [["tmux", "send-keys", "-t", "%7", "-l", payload]]


def test_herdr_interactive_special_keys_remain_logical(monkeypatch) -> None:
    screen = FakeScreen(
        keys=["x", "\n", curses.KEY_UP, "\x01", "\x1b", curses.KEY_LEFT],
    )
    calls = []
    _stub_curses(monkeypatch, screen)
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output\n")
    monkeypatch.setattr(
        shep,
        "_run",
        lambda argv, **_kwargs: calls.append(argv)
        or SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    shep.run_session_view(
        screen,
        fleet_row("herdr:w3H:pX", "alpha"),
        False,
        interactive=True,
    )

    assert calls == [
        [shep.HERDR_BIN, "pane", "send-text", "w3H:pX", "x"],
        [shep.HERDR_BIN, "pane", "send-keys", "w3H:pX", "enter"],
        [shep.HERDR_BIN, "pane", "send-keys", "w3H:pX", "up"],
        [shep.HERDR_BIN, "pane", "send-keys", "w3H:pX", "ctrl-a"],
    ]


def test_session_key_tokens_reserve_escape_for_leaving_interactive_mode() -> None:
    assert shep.session_key_token(ord("x")) == "x"
    assert shep.session_key_token(10) == "enter"
    assert shep.session_key_token(curses.KEY_UP) == "up"
    assert shep.session_key_token(27) is None


def test_herdr_tab_id_reads_the_tab_and_survives_junk(monkeypatch) -> None:
    payload = json.dumps({"result": {"pane": {"tab_id": "w3H:tW"}}})
    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **_k: SimpleNamespace(returncode=0, stdout=payload, stderr=""),
    )
    assert shep.herdr_tab_id("herdr:w3H:pX") == "w3H:tW"
    # herdr's JSON arrives unvalidated; a non-string target used to raise
    # AttributeError straight through the view and kill the TUI.
    assert shep.herdr_tab_id(1234) == "w3H:tW"

    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **_k: SimpleNamespace(returncode=0, stdout="not json", stderr=""),
    )
    assert shep.herdr_tab_id("herdr:w3H:pX") == ""

    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **_k: SimpleNamespace(returncode=1, stdout="", stderr="gone"),
    )
    assert shep.herdr_tab_id("herdr:w3H:pX") == ""
    assert shep.herdr_tab_id("") == ""


def test_attaching_to_a_herdr_pane_never_suspends_curses(monkeypatch) -> None:
    """Focusing a herdr tab is an API call, not a tty handover.

    Calling endwin() for it would blank Shep's own pane for a command that
    returns instantly and leaves this view visible behind the focused tab.
    """
    monkeypatch.setattr(shep, "herdr_tab_id", lambda _target: "w3H:tW")
    shep._FOCUSED.clear()  # the focus cooldown is process-global
    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **_k: SimpleNamespace(returncode=0, stdout="{}", stderr=""),
    )
    monkeypatch.setattr(
        curses, "endwin", lambda: pytest.fail("herdr attach must not end curses"),
    )

    message = shep.attach_to_session(
        object(), {"source": "herdr", "target": "herdr:w3H:pX"},
    )

    assert "focused in herdr" in message


def _tmux_attach_probe(monkeypatch, returncode=0, raises=None, inside_tmux=False):
    """Drive the tmux branch, recording the curses calls and the argv it ran."""
    calls = []
    argv = []
    if inside_tmux:
        monkeypatch.setenv("TMUX", "/tmp/tmux-501/default,1,0")
        # Inert against the shipping code, which never calls ttyname — and that
        # is the point. Without it, a re-added `-c os.ttyname(0)` wire emits no
        # `-c` under pytest (stdin is not a tty, ttyname raises, the client
        # falls back to ""), so the guard below would pass against the very
        # regression it exists to catch. The mock is not supplying the answer
        # under test; it is letting the failure mode reach the assertion.
        monkeypatch.setattr(os, "ttyname", lambda _fd: "/dev/ttys034")
    else:
        monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.setattr(curses, "flushinp", lambda: calls.append("flush"))
    monkeypatch.setattr(curses, "def_prog_mode", lambda: calls.append("save"))
    monkeypatch.setattr(curses, "endwin", lambda: calls.append("endwin"))
    monkeypatch.setattr(curses, "reset_prog_mode", lambda: calls.append("restore"))
    monkeypatch.setattr(
        termios, "tcflush", lambda _fd, _queue: calls.append("tcflush"),
    )

    def fake_run(cmd, *_a, **_k):
        argv.append(cmd)
        calls.append("run")
        if raises:
            raise raises
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(subprocess, "run", fake_run)
    stdscr = SimpleNamespace(
        redrawwin=lambda: calls.append("redraw"),
        refresh=lambda: calls.append("refresh"),
    )
    message = shep.attach_to_session(stdscr, {"source": "tmux", "target": "%7"})
    return message, calls, argv


def test_switch_client_is_never_pinned_to_a_client(monkeypatch) -> None:
    """`-c` cannot work from inside a pane, and does not need to.

    The only tty a process in a pane can name is the PANE's pty, and tmux
    rejects it — verified on a throwaway socket: `switch-client -c <pane_tty>`
    returns "can't find client", rc=1. Pinning it made [o] fail every time Shep
    ran inside tmux, which is how Shep normally runs. Bare switch-client moves
    the most recently active client, and pressing [o] is what makes a client
    the most recently active one.
    """
    _message, _calls, argv = _tmux_attach_probe(monkeypatch, inside_tmux=True)

    assert argv == [["tmux", "switch-client", "-t", "%7"]]
    assert not any("-c" in cmd for cmd in argv)


def test_a_failed_tmux_attach_does_not_report_success(monkeypatch) -> None:
    """tmux prints "can't find pane" to a screen this repaints over instantly.

    The pane can die between the mirror's last capture and the keypress, so a
    non-zero rc is the operator's ONLY evidence the handover never happened.
    """
    message, _calls, _argv = _tmux_attach_probe(monkeypatch, returncode=1)

    assert message == "attach failed (tmux rc=1)"


def test_a_successful_tmux_attach_reports_coming_back(monkeypatch) -> None:
    message, calls, argv = _tmux_attach_probe(monkeypatch, returncode=0)

    assert message == "back from attach"
    assert argv == [["tmux", "attach", "-t", "%7"]]
    # Flushed on both sides of the handover, and the second flush has to be the
    # LAST thing before the exec — a held key keeps emitting across endwin, so a
    # flush that runs any earlier leaves a wider window for repeats to reach the
    # live agent. Only the bracketing is pinned, not flush-vs-save order, which
    # cannot matter: def_prog_mode only saves tty state.
    assert calls.index("flush") < calls.index("endwin")
    assert calls.index("endwin") < calls.index("tcflush") < calls.index("run")
    assert calls[-4:] == ["flush", "restore", "redraw", "refresh"]


def test_attach_restores_curses_even_when_tmux_is_missing(monkeypatch) -> None:
    """A failed handover must land back in the TUI, not on a dead terminal."""
    message, calls, _argv = _tmux_attach_probe(
        monkeypatch, raises=FileNotFoundError("no tmux"),
    )

    assert message.startswith("attach failed")
    assert calls[-3:] == ["restore", "redraw", "refresh"]


def test_a_held_key_cannot_storm_herdr_with_focus_calls(monkeypatch) -> None:
    """Six held repeats measured seven _run calls at timeout=8 on the curses
    thread — up to 56s of frozen TUI, and twelve calls (96s) when the pane is
    dead, which is exactly what a held [o] finds. Both guards therefore sit
    ahead of the tab lookup, which is itself one of those calls.
    """
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if "pane" in argv:  # herdr_tab_id — deliberately NOT mocked away
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"result": {"pane": {"tab_id": "w3H:tW"}}}),
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(shep, "_run", fake_run)
    row = {"source": "herdr", "target": "herdr:w3H:pX"}
    shep._FOCUSED.clear()

    results = [shep.attach_to_session(object(), row) for _ in range(6)]

    assert "focused in herdr" in results[0]
    assert all(r == "already focused — release [o]" for r in results[1:])
    assert len(calls) == 2, "one pane get + one tab focus, not one pair per press"

    # A dead pane is the expensive case — two calls a press — so the cooldown
    # arms on ATTEMPT. Arming only on success left that path unguarded, at the
    # cost of a one-second wait before a deliberate retry.
    calls.clear()
    shep._FOCUSED.clear()
    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **_k: calls.append(argv) or SimpleNamespace(
            returncode=1, stdout="", stderr="no such pane",
        ),
    )

    failures = [shep.attach_to_session(object(), row) for _ in range(6)]

    assert failures[0].startswith("herdr did not report a tab")
    assert all(f == "already focused — release [o]" for f in failures[1:])
    assert len(calls) == 1, "a failing pane get must not repeat either"


def test_unattachable_sources_say_so_instead_of_failing_silently() -> None:
    assert "cannot be attached" in shep.attach_to_session(
        object(), {"source": "zellij", "target": "z"},
    )
    # _error_row builds real-source rows with no target, and they are
    # selectable — blaming the transport there would be flatly untrue.
    assert shep.attach_to_session(object(), {"source": "tmux"}) == (
        "this row has no live pane to attach to"
    )


def test_the_attach_key_rearms_the_poll_and_shows_what_happened(monkeypatch) -> None:
    """Nothing drove this loop before, so a key that stopped routing shipped green."""
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output")
    monkeypatch.setattr(
        shep, "attach_to_session", lambda _s, _r: "attach failed (tmux rc=1)",
    )
    screen = _ViewScreen([ord("o"), ord("q")], width=80)

    shep.run_session_view(
        screen, {"source": "tmux", "target": "%7", "label": "w"},
        ascii_only=True, interactive=False,
    )

    assert screen.timeouts == [shep.KEY_POLL_MS, shep.KEY_POLL_MS]
    # At 80 columns the base footer alone fills the row, so the notice only
    # survives by being painted first.
    assert "attach failed (tmux rc=1)" in _frame(screen)


def test_the_attach_notice_clears_on_the_next_deliberate_key(monkeypatch) -> None:
    """A notice that paints first must not squat on the legend forever.

    It sits ahead of the keys now, so a stale one clips "[r] refresh  [q] back"
    off the row for the rest of the visit — which was free to ignore while the
    notice was being truncated into invisibility, and is not any more.
    """
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output")
    monkeypatch.setattr(shep, "attach_to_session", lambda _s, _r: "back from attach")
    screen = _ViewScreen([ord("o"), ord("j"), ord("q")], width=80)

    shep.run_session_view(
        screen, {"source": "tmux", "target": "%7", "label": "w"},
        ascii_only=True, interactive=False,
    )

    frame = _frame(screen)
    assert "back from attach" not in frame
    assert "[r] refresh" in frame


def test_an_idle_poll_tick_does_not_wipe_the_attach_notice(monkeypatch) -> None:
    """The clear sits ahead of the key branches, so it needs the -1 guard.

    getch returns -1 every KEY_POLL_MS when nobody is typing. Without the
    guard the notice would be cleared within a tenth of a second of being set
    and the operator would never read it.
    """
    monkeypatch.setattr(shep, "capture_pane", lambda *_a, **_k: "agent output")
    monkeypatch.setattr(shep, "attach_to_session", lambda _s, _r: "back from attach")
    screen = _ViewScreen([ord("o"), -1, -1, ord("q")], width=80)

    shep.run_session_view(
        screen, {"source": "tmux", "target": "%7", "label": "w"},
        ascii_only=True, interactive=False,
    )

    assert "back from attach" in _frame(screen)


def test_pane_greys_render_in_the_terminals_own_foreground(monkeypatch) -> None:
    """Grey-on-white was unreadable; black/white/grey now use the default fg."""
    monkeypatch.setattr(shep, "_COLORS_READY", True)

    assert shep._rgb_to_basic8(128, 128, 128) is None   # grey
    assert shep._rgb_to_basic8(10, 10, 10) is None      # near-black
    assert shep._xterm256_to_basic8(240) is None        # greyscale ramp
    assert shep._xterm256_to_basic8(15) is None         # bright white
    assert shep._rgb_to_basic8(220, 40, 40) == 1        # real colour still colours
    assert shep._pair(None) == 0

    dim_grey = shep.ansi_segments("\x1b[2;37mplanning the next step\x1b[0m")
    assert dim_grey[0][1] & curses.A_DIM == 0
    assert dim_grey[0][1] & curses.A_COLOR == 0


def test_beads_badge_refreshes_without_opening_the_tab(monkeypatch, tmp_path) -> None:
    """The count was blank on AGENTS until you had visited BEADS at least once."""
    repo = tmp_path / "repo"
    (repo / ".beads").mkdir(parents=True)
    export = repo / ".beads" / "issues.jsonl"
    export.write_text(
        '{"id": "a-1", "status": "open", "priority": 1, "title": "one",'
        ' "updated_at": "2026-01-01"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(shep, "discover_beads_repos", lambda: [str(repo)])
    shep._BEADS_EXPORT_MTIME["at"] = None

    shep.refresh_beads_badge()

    assert shep._TAB_BADGES["beads"]["count"] == 1
    assert shep.tab_badge_text("beads")  # count AND age are now renderable

    # An unchanged export must not be re-parsed on every five-second poll.
    loads = []
    monkeypatch.setattr(shep, "load_beads", lambda *a, **k: loads.append(1) or ([], None))
    shep.refresh_beads_badge()
    assert loads == []

    shep._BEADS_EXPORT_MTIME["at"] = None


def test_beads_status_line_reports_a_live_scan_age() -> None:
    """Baked into the message it would freeze at 0s and read as always fresh."""
    shep.set_tab_badge("beads", 12, now=1000.0)

    fresh = shep.beads_status_line("12 open beads across 3 repos", now=1000.0)
    later = shep.beads_status_line("12 open beads across 3 repos", now=1180.0)
    ascii_line = shep.beads_status_line("12 open beads", ascii_only=True, now=1180.0)

    assert fresh.endswith("scanned 0s ago")
    assert later.endswith("scanned 3m ago")
    assert ascii_line.isascii()

    shep._TAB_BADGES.pop("beads", None)


# --- Sent tally in the header -----------------------------------------------

def _write_events(directory, *events):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    path = directory / f"events-{stamp}.jsonl"
    path.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8",
    )
    return path


def test_the_header_counts_what_the_sweep_sent_not_what_this_process_sent(
    tmp_path, monkeypatch,
) -> None:
    """The process that sends almost every nudge is not the one drawing this.

    The unattended sweep runs every five minutes and exits, so an in-memory
    counter in the TUI would report the handful the operator's own session
    sent and none of the engine's -- the opposite of the question.
    """
    shep._SENT_TALLY.update({"key": None, "count": 0})
    events = tmp_path / "outcomes"
    _write_events(
        events,
        {"ts": 1.0, "event": "sent", "target_id": "a"},
        {"ts": 2.0, "event": "drafted", "target_id": "b"},
        {"ts": 3.0, "event": "sent", "target_id": "c"},
        {"ts": 4.0, "event": "suppressed", "reason": "duplicate"},
    )
    monkeypatch.setattr(shep, "_outcomes_events_dir", lambda: events)

    assert shep.nudges_sent_today() == 2
    shep._SENT_TALLY.update({"key": None, "count": 0})


def test_no_log_yet_today_is_zero_not_an_error(tmp_path, monkeypatch) -> None:
    """A header has nowhere to put an exception."""
    shep._SENT_TALLY.update({"key": None, "count": 0})
    monkeypatch.setattr(shep, "_outcomes_events_dir", lambda: tmp_path / "nope")

    assert shep.nudges_sent_today() == 0
    shep._SENT_TALLY.update({"key": None, "count": 0})


def test_the_tally_rereads_only_when_the_log_changes(tmp_path, monkeypatch) -> None:
    """The header redraws every few seconds against a log that is hundreds of KB.

    Re-parsing per frame would spend more time reading telemetry than drawing
    the fleet, so the cache is keyed on the file's identity, not a clock.
    """
    shep._SENT_TALLY.update({"key": None, "count": 0})
    events = tmp_path / "outcomes"
    _write_events(events, {"ts": 1.0, "event": "sent", "target_id": "a"})
    monkeypatch.setattr(shep, "_outcomes_events_dir", lambda: events)
    assert shep.nudges_sent_today() == 1

    reads = []
    real_open = Path.open

    def counting_open(self, *args, **kwargs):
        reads.append(self)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    shep.nudges_sent_today()
    shep.nudges_sent_today()
    assert reads == []  # unchanged file, no re-parse

    monkeypatch.undo()
    monkeypatch.setattr(shep, "_outcomes_events_dir", lambda: events)
    _write_events(
        events,
        {"ts": 1.0, "event": "sent", "target_id": "a"},
        {"ts": 2.0, "event": "sent", "target_id": "b"},
    )
    assert shep.nudges_sent_today() == 2  # grew, so it re-read
    shep._SENT_TALLY.update({"key": None, "count": 0})


def test_the_header_shows_the_tally(tmp_path, monkeypatch) -> None:
    """A quiet fleet and a broken engine look identical without this number."""
    shep._SENT_TALLY.update({"key": None, "count": 0})
    events = tmp_path / "outcomes"
    _write_events(events, *[{"ts": float(i), "event": "sent"} for i in range(7)])
    monkeypatch.setattr(shep, "_outcomes_events_dir", lambda: events)

    _top, middle, _bottom = shep.commander_header([{"status": "idle"}], 100)

    assert "SENT 7 today" in middle
    shep._SENT_TALLY.update({"key": None, "count": 0})


def test_the_live_nudge_ledger_is_never_reachable_from_a_test(tmp_path) -> None:
    """The isolation fixture is silent, load-bearing, and easy to weaken.

    snapshot_payload() opens with load_nudge_state(), which merges the real
    ~/.mission-engine ladder into the process globals. Tests fabricate panes
    under live-looking ids, so without the redirect the operator's own fleet
    decides the result: the suite passes in a clean CI container and fails only
    on the machine that owns the fleet, in whichever test happens to share an
    id, only while that pane is open. Nothing was asserting the guard was on —
    so assert it here, where a broken conftest fails immediately and by name
    instead of surfacing later as a phantom in an unrelated test.
    """
    assert shep.NUDGE_STATE_FILE == tmp_path / "nudge-state.json"
    assert not shep._NUDGE_STATE
    assert not shep._SIG_STATE
    assert not shep._NUDGE_EVENTS
    assert not shep._TAB_BADGES
def test_abstention_reason_survives_the_engine_naming_its_rule() -> None:
    """The engine now says WHY it declined, and five call sites compared the
    reply against the bare string. Any one of them missed would have treated
    `NO_NUDGE: still_working` as an ordinary draft and typed it into a pane."""
    assert shep.abstention_reason("NO_NUDGE") == "unspecified"
    assert shep.abstention_reason("NO_NUDGE: still_working") == "still_working"
    assert shep.abstention_reason("NO_NUDGE - close_pending") == "close_pending"
    assert shep.abstention_reason("Run pytest test_api.py.") is None
    assert shep.is_abstention("NO_NUDGE: nothing_useful")
    assert not shep.is_abstention("Fix the KeyError on shep.py:412, then rerun.")


def test_a_reasoned_abstention_never_becomes_a_nudge() -> None:
    """The failure mode the single matcher exists to prevent."""
    for reply in ("NO_NUDGE", "NO_NUDGE: still_working", "NO_NUDGE: no_visible_work"):
        assert shep.operational_candidate_or_fallback(reply, {}, ["ctx"]) is None
        assert shep.validate_intent_candidate(reply) is None
        assert shep.nudge_content_quality_reason(reply, "ctx") == "no candidate"


def test_cap_per_project_preserves_rank_and_leaves_room() -> None:
    missions = [{"project_name": "busy", "id": f"b{i}"} for i in range(5)]
    missions += [{"project_name": "quiet", "id": "q0"}]

    capped = shep.cap_per_project(missions, per_project=2)

    assert [m["id"] for m in capped] == ["b0", "b1", "q0"]


def test_dismissing_a_mission_survives_regeneration(tmp_path, monkeypatch) -> None:
    """`[d]` used to only filter the in-memory list and write a ledger nothing
    read back, so pressing [r] returned every dismissed mission."""
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "MISSION_DISMISSED_FILE", tmp_path / "dismissed.json")

    assert shep.dismiss_mission({"id": "bug-hunter-1"})

    assert shep.drop_dismissed(
        [{"id": "bug-hunter-1"}, {"id": "other-1"}]
    ) == [{"id": "other-1"}]


def test_a_dismissal_expires_so_the_deck_cannot_starve(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "MISSION_DISMISSED_FILE", tmp_path / "dismissed.json")
    stale = time.time() - shep.MISSION_DISMISS_TTL - 1

    shep.dismiss_mission({"id": "old"}, now=stale)

    assert shep.drop_dismissed([{"id": "old"}]) == [{"id": "old"}]


def test_regen_message_distinguishes_a_no_op_from_a_dead_key() -> None:
    """"R doesn't regen" was really "R regenerates and I cannot tell"."""
    same = [{"id": "a"}, {"id": "b"}]

    unchanged = shep.mission_regen_message(["a", "b"], same, None)
    changed = shep.mission_regen_message(["a"], same, None)

    assert "same 2 missions" in unchanged
    assert "1 new" in changed


def test_finished_work_outlives_the_pane_that_declared_it() -> None:
    """reap_ready is re-derived from pane text every collection, so a finished
    session left the review queue the moment its line scrolled away."""
    shep._DONE_PILE.clear()
    row = {"target": "t1", "label": "builder", "cwd": "/tmp/repo", "reap_ready": True}

    shep.record_done(row, "tests green, MR open")
    # The pane is gone entirely on the next pass.
    queue = shep.pending_actions([])

    assert [item["target"] for item in queue] == ["t1"]
    assert queue[0]["summary"] == "tests green, MR open"
    assert queue[0]["gone"] is True
    assert queue[0]["index"] is None
    shep._DONE_PILE.clear()


def test_a_live_finished_session_is_not_listed_twice() -> None:
    shep._DONE_PILE.clear()
    row = {
        "target": "t1", "label": "builder", "cwd": "/tmp/repo",
        "reap_ready": True, "reap_reason": "declared done",
    }
    shep.record_done(row, "declared done")

    queue = shep.pending_actions([row])

    assert len(queue) == 1
    assert queue[0].get("gone") is not True
    shep._DONE_PILE.clear()


def test_reaping_clears_the_finished_record() -> None:
    """A review queue that never empties stops being read."""
    shep._DONE_PILE.clear()
    shep.record_done({"target": "t1", "label": "b", "cwd": "/tmp/r"}, "done")

    assert shep.clear_done("t1")
    assert shep.pending_actions([]) == []
    shep._DONE_PILE.clear()


def test_the_done_pile_expires_rather_than_growing_forever() -> None:
    shep._DONE_PILE.clear()
    stale = time.time() - shep.DONE_PILE_TTL - 1
    shep.record_done({"target": "old", "label": "b", "cwd": "/tmp/r"}, "done", now=stale)

    assert shep.done_pile() == []
    shep._DONE_PILE.clear()


# --- Verdict parsing hardening (MR !44 review findings) ----------------------

ABSTENTION_SPELLINGS = (
    "NO_NUDGE",
    "NO_NUDGE: still_working",
    "`NO_NUDGE: still_working`",
    '"NO_NUDGE: x"',
    "**NO_NUDGE**: x",
    "__NO_NUDGE__: x",
    "_NO_NUDGE_",
    "*NO_NUDGE*",
    "no_nudge: x",
    "No_Nudge: still working, let the tests run",
    "NO-NUDGE: x",
    "NO NUDGE - x",
    "NO_NUDGE still working",
    "  ```NO_NUDGE: x",
)

# Sentences that merely open with the token's letters. Swallowing one costs a
# real instruction; the reverse costs a live pane.
NOT_ABSTENTIONS = (
    "Run pytest test_api.py.",
    "NO_NUDGES are needed here",
    "NO_NUDGE_STILL is a var",
    "NO_NUDGEs remain",
    "Run pytest; NO_NUDGE otherwise",
    "Fix the KeyError on shep.py:412, then rerun.",
    "Nudge the worker to continue.",
)


@pytest.mark.parametrize("reply", ABSTENTION_SPELLINGS)
def test_every_abstention_spelling_is_caught_before_it_reaches_a_pane(reply) -> None:
    """The first matcher was case-sensitive and accepted no decoration, while
    the prompt it reads back presents the verdict inside backticks -- so the
    likeliest reply the guidance produces fell through and would have been
    typed at a live agent as an instruction."""
    assert shep.is_abstention(reply)
    assert shep.operational_candidate_or_fallback(reply, {}, ["running tests"]) is None
    assert shep.validate_intent_candidate(reply) is None
    assert shep.nudge_content_quality_reason(reply, "running tests") == "no candidate"


@pytest.mark.parametrize("reply", NOT_ABSTENTIONS)
def test_a_real_instruction_is_never_swallowed_as_an_abstention(reply) -> None:
    assert shep.abstention_reason(reply) is None


def test_the_handoff_verdict_accepts_the_same_spellings() -> None:
    """Same matcher, so the two cannot drift apart again."""
    assert shep.needs_human_request("NEEDS_HUMAN: rotate the key") == "rotate the key"
    assert shep.needs_human_request("`NEEDS_HUMAN: x`") == "x"
    assert shep.needs_human_request("needs_human: x") == "x"
    assert shep.needs_human_request("NEEDS-HUMAN") == "blocked on something only you can do"
    assert shep.needs_human_request("NEEDS_HUMANS are great") is None
    assert shep.needs_human_request("Run pytest.") is None


def test_an_unbounded_abstention_reason_cannot_flood_telemetry() -> None:
    """DOTALL captures the whole reply; record_done clamps at 160 and this did
    not, so a chatty model wrote thousands of characters into the shared state
    file and the outcome log."""
    assert len(shep.abstention_reason("NO_NUDGE: " + "word " * 400)) == 160


def test_a_cleared_finished_record_does_not_come_back_on_the_next_tick(
    tmp_path, monkeypatch
) -> None:
    """clear_done popped only the in-memory dict while load_nudge_state merges
    the file back every refresh, so a reviewed row reappeared within seconds and
    the queue could never empty -- the exact failure the pile exists to avoid."""
    state = tmp_path / "nudge-state.json"
    monkeypatch.setattr(shep, "NUDGE_STATE_FILE", state)
    shep._DONE_PILE.clear()
    shep.record_done({"target": "t1", "label": "b", "cwd": "/tmp/r"}, "done")
    shep.save_nudge_state({"t1"}, state)

    assert shep.clear_done("t1")
    shep.load_nudge_state(state, events_only=True)

    assert shep.done_pile() == []
    shep._DONE_PILE.clear()


def test_a_session_that_resumed_work_is_not_reported_as_gone() -> None:
    """`gone` meant "not currently reap-ready", not "pane is absent", so a
    session that declared itself done and kept working was listed as exited."""
    shep._DONE_PILE.clear()
    shep.record_done({"target": "p1", "label": "b", "cwd": "/tmp/r"}, "done")
    working = {
        "target": "p1", "label": "b", "cwd": "/tmp/r",
        "status": "working", "reap_ready": False,
    }

    assert shep.pending_actions([working]) == []
    # Absent pane still surfaces, which is the feature.
    assert [i["target"] for i in shep.pending_actions([])] == ["p1"]
    shep._DONE_PILE.clear()


def test_a_malformed_done_record_cannot_crash_the_render_loop() -> None:
    shep._DONE_PILE.clear()
    shep._DONE_PILE["x"] = {"at": time.time()}          # no target/label/reason

    assert shep.pending_actions([]) == []
    shep._DONE_PILE.clear()


def test_a_corrupt_done_section_is_read_as_best_effort(tmp_path) -> None:
    """load_nudge_state promises False on anything unreadable; a list here
    raised AttributeError straight through that contract."""
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"done": [1, 2]}))

    assert shep.load_nudge_state(path) is True   # other sections still load
    assert shep.done_pile() == []


def test_dismissing_a_repos_share_frees_the_slot_instead_of_deleting_it(
    monkeypatch, tmp_path
) -> None:
    """The cap ran before the filter, so dismissing a repo's three capped beads
    returned the same three next pass and removed them again -- the source went
    silent for the whole window while the rest of the backlog sat unoffered."""
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "MISSION_DISMISSED_FILE", tmp_path / "dismissed.json")
    root = _beads_tree(
        tmp_path,
        busy=[_issue(f"b-{i:02d}", priority=0) for i in range(10)],
    )
    _delivery(monkeypatch, tmp_path, root / "group" / "busy")

    first = [m["bead_id"] for m in shep.bead_missions(shep.MISSION_DECK_TOP)[0]]
    for bead_id in first:
        shep.dismiss_mission({"id": bead_id})
    second = [m["bead_id"] for m in shep.bead_missions(shep.MISSION_DECK_TOP)[0]]

    assert len(first) == shep.MISSION_DECK_PER_PROJECT
    assert len(second) == shep.MISSION_DECK_PER_PROJECT
    assert not set(first) & set(second)


def test_the_deck_cache_is_filtered_by_dismissals(tmp_path, monkeypatch) -> None:
    """Only [r] applied the filter, so leaving the tab and returning inside the
    30-minute TTL served the dismissed mission straight back off disk."""
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(shep, "MISSION_DECK_CACHE", tmp_path / "deck.json")
    monkeypatch.setattr(shep, "MISSION_DISMISSED_FILE", tmp_path / "dismissed.json")
    (tmp_path / "deck.json").write_text(json.dumps(
        {"missions": [{"id": "keep"}, {"id": "drop"}]}
    ))

    shep.dismiss_mission({"id": "drop"})
    missions, _error = shep.load_mission_deck(force=False, allow_generate=False)

    assert [m["id"] for m in missions] == ["keep"]


# --- Draft failure attribution and decoration --------------------------------

def _draft_row():
    return {"target": "t1", "label": "worker", "status": "idle"}


def _stub_gateway(monkeypatch, result=None, raises=None):
    monkeypatch.setattr(shep, "_nudge_cli_available", lambda: True)

    def fake_run(*_a, **_kw):
        if raises is not None:
            raise raises
        return result

    monkeypatch.setattr(shep.subprocess, "run", fake_run)


def test_a_draft_timeout_is_not_reported_as_a_dead_gateway(monkeypatch) -> None:
    """Every failure answered None and the caller logged one flat
    "gateway_unavailable", so a timeout on our own clock, a 429, a bad exit code
    and a crash were the same log entry -- and ~170 a day could not be acted on.
    Measured, the gateway answers this prompt in ~4s."""
    failures = []
    _stub_gateway(monkeypatch, raises=shep.subprocess.TimeoutExpired("cmd", 30))

    assert shep.llm_draft_nudge(_draft_row(), ["ctx"], failures=failures) is None
    assert failures == ["draft_timeout"]


def test_a_nonzero_exit_names_its_code(monkeypatch) -> None:
    failures = []
    _stub_gateway(monkeypatch, result=SimpleNamespace(stdout="", returncode=7))

    assert shep.llm_draft_nudge(_draft_row(), ["ctx"], failures=failures) is None
    assert failures == ["draft_exit:7"]


def test_an_unexpected_error_is_attributed_and_never_raises(monkeypatch) -> None:
    """This runs on the curses thread; attribution must not cost the
    never-raise contract."""
    failures = []
    _stub_gateway(monkeypatch, raises=OSError("boom"))

    assert shep.llm_draft_nudge(_draft_row(), ["ctx"], failures=failures) is None
    assert failures == ["draft_error:OSError"]


def test_a_backticked_draft_is_not_typed_at_the_agent_with_its_markdown(
    monkeypatch,
) -> None:
    """Measured live: the model returned "`Fix the 2 failing tests in
    test_api.py, then rerun pytest.`" -- which classified safe_continuation,
    held for nothing, and would have been delivered backticks and all."""
    decorated = "`Fix the 2 failing tests in test_api.py, then rerun pytest.`"
    _stub_gateway(monkeypatch, result=SimpleNamespace(stdout=decorated, returncode=0))

    draft = shep.llm_draft_nudge(_draft_row(), ["ctx"])

    assert draft == "Fix the 2 failing tests in test_api.py, then rerun pytest."
    assert shep.classify_risk(draft)[0] == "safe_continuation"


def test_the_draft_timeout_leaves_room_for_a_concurrent_sweep() -> None:
    """A ten-way concurrent burst was measured at up to 8.9s against the old
    15s ceiling -- six seconds of headroom for a whole-fleet sweep."""
    assert shep.NUDGE_DRAFT_TIMEOUT_SECONDS >= 30
def test_regen_message_reports_a_shrinking_deck_instead_of_calling_it_unchanged(
) -> None:
    """"Unchanged" was decided by the absence of NEW ids, so a regeneration
    that gained nothing was called unchanged however much it lost. The 3 -> 0
    case printed "same 0 missions (backlog unchanged)" over an empty screen and
    advised dismissing one of the nothing shown -- the exact no-op-versus-
    failure confusion this function exists to remove."""
    deck = [{"id": "a"}, {"id": "b"}]

    unchanged = shep.mission_regen_message(["a", "b"], deck, None)
    shrank = shep.mission_regen_message(["a", "b", "c"], deck, None)
    emptied = shep.mission_regen_message(["a", "b", "c"], [], None)
    swapped = shep.mission_regen_message(["x", "y"], deck, None)

    assert "same 2 missions" in unchanged
    assert "1 gone" in shrank and "unchanged" not in shrank
    assert "3 gone" in emptied and "unchanged" not in emptied
    # A same-length deck of different missions is not "unchanged" either.
    assert "2 gone" in swapped and "2 new" in swapped


def test_regen_message_counts_an_id_less_deck_consistently() -> None:
    """`before` filtered falsy ids and the current side did not, so a deck
    carrying id-less missions counted them new every pass and could never
    report itself unchanged."""
    assert "new" not in shep.mission_regen_message(
        ["a"], [{"id": None}, {"id": None}], None
    )


def test_regen_message_says_nothing_about_change_on_a_first_run() -> None:
    """No prior deck means nothing to compare; claiming a delta would invent
    one."""
    message = shep.mission_regen_message([], [{"id": "a"}, {"id": "b"}], None)

    assert message == shep.mission_status_message([{"id": "a"}, {"id": "b"}], None)
# --- Done pile and deck polish -----------------------------------------------

def test_a_recycled_pane_id_does_not_inherit_the_previous_sessions_record(
) -> None:
    """herdr reuses pane ids and the pile is keyed on the pane, so with a
    14-day TTL Monday's finished mission handed back its label, reason and age
    for Wednesday's mission on the same id -- and Wednesday's own completion was
    never recorded, because the slot was taken."""
    shep._DONE_PILE.clear()
    monday = {"target": "%12", "label": "mission-a", "cwd": "/tmp/repo-a"}
    wednesday = {"target": "%12", "label": "mission-b", "cwd": "/tmp/repo-b"}

    shep.record_done(monday, "finished A")
    later = shep.record_done(wednesday, "finished B")

    assert later["label"] == "mission-b"
    assert later["reason"] == "finished B"
    shep._DONE_PILE.clear()


def test_the_same_session_redeclaring_does_not_reset_its_age() -> None:
    """A pane re-renders SAFE_TO_CLOSE on every collection; letting each one
    overwrite would keep resetting the age of work that finished hours ago."""
    shep._DONE_PILE.clear()
    row = {"target": "%12", "label": "mission-a", "cwd": "/tmp/repo-a"}
    first = shep.record_done(row, "finished A", now=1000.0)

    again = shep.record_done(row, "finished A again", now=9999.0)

    assert again["at"] == first["at"] == 1000.0
    assert again["reason"] == "finished A"
    shep._DONE_PILE.clear()


def test_session_identity_survives_a_reload() -> None:
    """Identity round-trips through JSON, which has no tuples -- a tuple would
    read back as a list, never compare equal, and make every reloaded pane look
    like a new session."""
    shep._DONE_PILE.clear()
    row = {"target": "%12", "label": "mission-a", "cwd": "/tmp/repo-a"}
    shep.record_done(row, "done")

    reloaded = shep.prune_done_pile(json.loads(json.dumps(shep._DONE_PILE)))
    shep._DONE_PILE.clear()
    shep._DONE_PILE.update(reloaded)
    before = dict(shep._DONE_PILE["%12"])
    shep.record_done(row, "done again")

    assert shep._DONE_PILE["%12"] == before
    shep._DONE_PILE.clear()


def test_the_done_pile_is_bounded_so_the_queue_stays_readable() -> None:
    """At the observed rate (66 finished in three days) a 14-day TTL is ~300
    CLOSE rows, and a queue nobody can finish reading is one they skip."""
    pile = {
        f"t{i}": {
            "target": f"t{i}", "label": "l", "reason": "r", "repo": "x",
            "identity": ["l", "x"], "at": 1000.0 + i,
        }
        for i in range(shep.DONE_PILE_MAX + 25)
    }

    kept = shep.prune_done_pile(pile, now=1000.0)

    assert len(kept) == shep.DONE_PILE_MAX
    # Oldest dropped first: newest finished work is likeliest to still matter.
    assert f"t{shep.DONE_PILE_MAX + 24}" in kept
    assert "t0" not in kept


def test_a_recalled_record_reads_differently_from_a_live_reap_ready_pane(
) -> None:
    """Both rendered CLOSE, so the operator could not tell finished-and-gone
    from finished-and-still-here -- and only one has anything left to close."""
    shep._DONE_PILE.clear()
    shep.record_done({"target": "p1", "label": "b", "cwd": "/tmp/r"}, "done")

    lines = shep.pending_panel_lines(shep.pending_actions([]), 80)

    assert any("REVIEWED" in line for line in lines)
    assert not any("CLOSE" in line for line in lines)
    shep._DONE_PILE.clear()


def test_the_beads_strip_is_not_capped_by_the_decks_variety_rule(
    monkeypatch, tmp_path
) -> None:
    """The strip is the top of one backlog, not a varied deck. A 3-per-project
    cap made its own BEAD_STRIP_TOP=5 unreachable on a single-repo fleet."""
    root = _beads_tree(
        tmp_path, solo=[_issue(f"s-{i}", priority=0) for i in range(8)],
    )
    _delivery(monkeypatch, tmp_path, root / "group" / "solo")

    strip, _err = shep.bead_missions(
        shep.BEAD_STRIP_TOP, per_project=shep.BEAD_STRIP_TOP,
    )
    deck, _err2 = shep.bead_missions(shep.MISSION_DECK_TOP)

    assert len(strip) == shep.BEAD_STRIP_TOP
    assert len(deck) == shep.MISSION_DECK_PER_PROJECT


# --- Opaque execution gate ---------------------------------------------------

OPAQUE_DRAFTS = (
    "Run make ship and fix what it reports.",
    "Run scripts/rollout.sh and verify the smoke test.",
    "Run npm publish --dry-run and fix what it reports.",
    "Run ./deploy.sh now.",
    "Rerun just release and check output.",
    "Run yarn deploy:prod.",
    "Run scripts/deploy.py and report.",
    "Run bin/release.sh",
    "Run make and fix what it reports.",
)

# Everything the gate must leave alone. A gate that fires on ordinary drafts is
# one the operator learns to click through, which is its own safety failure.
TRANSPARENT_DRAFTS = (
    "Run the failing CI job on MR 137 and fix what it reports.",
    "Rerun pytest test_api.py and fix the first failure.",
    "Run npm test and fix the first failure.",
    "Run make test and fix what it reports.",
    "Run tox -e lint and fix what it reports.",
    "Fix the KeyError on shep.py:412, then rerun.",
    "Continue with the focused tests.",
    "Commit uncommitted scripts/shep.py edits.",
    "Verify the MR description matches the diff.",
    "Make sure nothing is left hanging.",
)


@pytest.mark.parametrize("text", OPAQUE_DRAFTS)
def test_an_opaque_target_never_auto_sends(text) -> None:
    """classify_risk is lexical over a fixed vocabulary, so `make ship` and
    `scripts/rollout.sh` read as ordinary safe continuations -- there is no
    "ship" token to match and there cannot be, because the dangerous part lives
    in a Makefile the classifier never sees. Measured: all three of `make ship`,
    `scripts/rollout.sh` and `npm publish` classified safe_continuation and
    would have been typed into a live pane unattended."""
    assert shep.classify_risk(text)[0] != "safe_continuation"
    assert shep.nudge_hold_reason(text, text) is not None


@pytest.mark.parametrize("text", TRANSPARENT_DRAFTS)
def test_the_gate_does_not_hold_an_ordinary_draft(text) -> None:
    assert shep.opaque_execution_reason(text) is None


def test_naming_a_file_is_not_running_it() -> None:
    """An earlier draft of this gate matched any path under scripts/ or bin/,
    which held "Commit uncommitted scripts/shep.py edits." -- naming a source
    file is not executing it."""
    assert shep.opaque_execution_reason("Commit uncommitted scripts/shep.py edits.") is None
    assert shep.opaque_execution_reason("Run scripts/deploy.py and report.") is not None


def test_make_sure_is_not_read_as_a_make_target() -> None:
    """The runner rule requires an explicit run verb. Without it "Make sure the
    tests pass" reads as the target `sure` and every such draft is held."""
    assert shep.opaque_execution_reason("Make sure the tests pass.") is None


def test_an_opaque_target_in_a_mission_brief_still_blocks_auto_send() -> None:
    """The brief is excluded from choosing the category but is delivered
    verbatim, so it cannot carry an unreviewable command out on an auto-send."""
    draft = "Continue with the focused tests.\n\nNEW_MISSION: run make ship"

    assert shep.classify_risk(draft)[0] != "safe_continuation"


def test_a_healthy_repo_never_depends_on_a_git_probe(tmp_path, monkeypatch) -> None:
    """The probe carried a 5s timeout and these paths sit under a Syncthing
    tree that can be cold, so a healthy repo was intermittently reported the
    same way a deleted one is -- silently shrinking the deck with no way to tell
    the two apart. A checkout with .git present must not shell out at all."""
    repo = tmp_path / "healthy"
    (repo / ".git").mkdir(parents=True)
    listing = tmp_path / "repos.txt"
    listing.write_text(str(repo))
    monkeypatch.setattr(
        shep, "_run",
        lambda *_a, **_k: pytest.fail("a checkout with .git must not be probed"),
    )

    repos, dropped = shep.launchable_repos(listing)

    assert repos == [str(repo)]
    assert dropped == []


def test_a_linked_worktree_is_launchable(tmp_path, monkeypatch) -> None:
    """A linked worktree carries .git as a FILE holding `gitdir: <path>`."""
    gitdir = tmp_path / "parent" / ".git" / "worktrees" / "linked"
    gitdir.mkdir(parents=True)
    repo = tmp_path / "linked"
    repo.mkdir()
    (repo / ".git").write_text(f"gitdir: {gitdir}\n")
    listing = tmp_path / "repos.txt"
    listing.write_text(str(repo))
    monkeypatch.setattr(
        shep, "_run",
        lambda *_a, **_k: pytest.fail("a resolvable worktree must not be probed"),
    )

    repos, dropped = shep.launchable_repos(listing)

    assert repos == [str(repo)]
    assert dropped == []


def test_a_dangling_worktree_pointer_is_not_launchable(tmp_path, monkeypatch) -> None:
    """The gitfile can outlive its parent repo. Trusting the file's existence
    alone would accept a worktree the old git probe correctly rejected --
    trading a real check away to remove a flake."""
    repo = tmp_path / "orphan"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: /nowhere/.git/worktrees/orphan\n")
    listing = tmp_path / "repos.txt"
    listing.write_text(str(repo))
    monkeypatch.setattr(
        shep, "_run",
        lambda *_a, **_k: SimpleNamespace(returncode=128, stdout="", stderr=""),
    )

    repos, dropped = shep.launchable_repos(listing)

    assert repos == []
    assert dropped == [f"{repo} (not a git repo)"]


def test_a_dropped_repo_says_why_it_was_dropped(tmp_path, monkeypatch) -> None:
    """"Missing", "not a repo" and "too slow to answer" need different actions
    from the operator, and all three read identically before."""
    missing = tmp_path / "gone"
    plain = tmp_path / "notarepo"
    plain.mkdir()
    listing = tmp_path / "repos.txt"
    listing.write_text(f"{missing}\n{plain}\n")
    monkeypatch.setattr(
        shep, "_run",
        lambda *_a, **_k: SimpleNamespace(returncode=128, stdout="", stderr=""),
    )

    repos, dropped = shep.launchable_repos(listing)

    assert repos == []
    assert dropped == [f"{missing} (no such directory)", f"{plain} (not a git repo)"]


# --- MISSIONS reap + recalled-row context ------------------------------------

def test_a_mission_is_matched_to_its_session_by_worktree(tmp_path) -> None:
    """Matched on the path mission_is_running already decides RUNNING from, so
    the deck and the reap agree by construction rather than by a naming
    convention that would drift."""
    worktree = shep.mission_worktree_path("/repos/bug-hunter", "bh-1")
    mission = {"cwd": "/repos/bug-hunter", "id": "bh-1"}

    exact = shep.mission_session(mission, [{"label": "hit", "cwd": str(worktree)}])
    nested = shep.mission_session(mission, [{"label": "hit", "cwd": str(worktree / "src")}])
    miss = shep.mission_session(mission, [{"label": "no", "cwd": str(tmp_path)}])

    assert exact["label"] == "hit"
    assert nested["label"] == "hit"
    assert miss is None


def test_the_missions_deck_cannot_close_a_session() -> None:
    """It closed live sessions: it acts on a fleet snapshot it never refreshes,
    and its RUNNING badge reads the worktree directory, so a successful close
    can never clear it and the operator presses [x] again."""
    source = inspect.getsource(shep.run_missions_view)

    assert "reap_session(" not in source
    assert "[x] reap" not in source


def test_mission_session_ignores_rows_without_a_cwd() -> None:
    mission = {"cwd": "/repos/bug-hunter", "id": "bh-1"}

    assert shep.mission_session(mission, [{"label": "x"}, {"label": "y", "cwd": ""}]) is None
    assert shep.mission_session(mission, None) is None


def test_a_recalled_row_describes_itself_not_the_selected_session() -> None:
    """follow_pending leaves the fleet cursor put for a recalled row -- there is
    no live row to move to -- so the context panel kept describing whatever was
    selected before. Arrowing onto a recalled row showed another session's live
    output under the recalled one's name."""
    item = {
        "target": "%9", "summary": "tests green, MR open", "repo": "shep",
        "gone": True, "index": None, "row": {"label": "builder-9"},
    }

    lines = shep.recalled_context_lines(item)
    body = "\n".join(lines)

    assert "builder-9" in body
    assert "pane has since closed" in body
    assert "tests green, MR open" in body
    assert "Nothing to preview" in body


def test_a_recalled_row_without_a_label_still_names_something() -> None:
    lines = shep.recalled_context_lines({"target": "%9", "gone": True})

    assert "%9" in "\n".join(lines)
    assert "declared itself done" in "\n".join(lines)


# --- The queue must contain the decisions it advertises ----------------------

def test_a_draft_the_tui_holds_reaches_the_pending_queue() -> None:
    """Only sweep() ever recorded a "held" event, and the queue keys on it. A
    draft the TUI held rendered HELD: in the fleet table (computed live from
    planned_cache) while never appearing in the queue built to collect exactly
    those decisions."""
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_STATE.clear()
    shep._DONE_PILE.clear()
    row = {"target": "t1", "label": "w1", "cwd": "/tmp/a", "status": "idle"}

    reason = shep.record_draft_verdict(
        "t1", "Run make ship and fix it.", "make ship output here"
    )
    queue = shep.pending_actions([row])

    assert reason is not None
    assert [(i["verb"], i["target"]) for i in queue] == [("APPROVE", "t1")]
    shep._NUDGE_EVENTS.clear()


def test_a_clean_draft_does_not_ask_for_a_decision() -> None:
    """The queue is for things that stop shep, not for everything it drafts."""
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_STATE.clear()
    shep._DONE_PILE.clear()
    row = {"target": "t1", "label": "w1", "cwd": "/tmp/a", "status": "idle"}

    shep.record_draft_verdict(
        "t1", "Rerun pytest test_api.py and fix the first failure.",
        "pytest test_api.py failed",
    )

    assert shep.pending_actions([row]) == []
    shep._NUDGE_EVENTS.clear()


def test_finished_work_is_not_counted_as_waiting_on_you() -> None:
    """Observed live: a panel headed "24 waiting on you" where all twenty-four
    were completed sessions and nothing was actually blocked. A queue that
    overstates its own urgency teaches the operator to stop reading it."""
    shep._NUDGE_EVENTS.clear()
    shep._DONE_PILE.clear()
    for i in range(24):
        shep.record_done({"target": f"old{i}", "label": f"w{i}", "cwd": "/tmp/x"}, "done")

    title = shep.pending_panel_lines(shep.pending_actions([]), 78)[0]

    assert "nothing waiting" in title
    assert "24 finished" in title
    assert "24 waiting on you" not in title
    shep._DONE_PILE.clear()


def test_the_title_counts_both_kinds_when_both_are_present() -> None:
    shep._NUDGE_EVENTS.clear()
    shep._NUDGE_STATE.clear()
    shep._DONE_PILE.clear()
    row = {"target": "t1", "label": "w1", "cwd": "/tmp/a", "status": "idle"}
    for i in range(3):
        shep.record_done({"target": f"old{i}", "label": f"w{i}", "cwd": "/tmp/x"}, "done")
    shep.record_draft_verdict("t1", "Run make ship and fix it.", "make ship output")

    title = shep.pending_panel_lines(shep.pending_actions([row]), 78)[0]

    assert "1 waiting on you" in title
    assert "3 finished" in title
    shep._DONE_PILE.clear()
    shep._NUDGE_EVENTS.clear()


# --- Drafter evidence window and self-pane guard (2026-09-10) -----------------


def test_fable_status_bar_is_noise_for_the_drafter() -> None:
    pane = (
        "※ recap: branch pushed, no MR yet. Next: open the merge request.\n"
        "Fable 5.1 | atlas-commander | █░░░░░░░░░ 12% | ContextQ:--\n"
        "Eff:--\n"
    )
    assert shep.clean_context_lines(pane) == [
        "※ recap: branch pushed, no MR yet. Next: open the merge request."
    ]


def test_drafter_sees_more_than_the_recap_footer() -> None:
    lines = [f"line {i}" for i in range(20)]
    prompt = shep.render_nudge_engine_prompt(
        {"target": "herdr:w1:p1", "context": "line 19"}, lines, engine_text="policy"
    )
    payload = json.loads(prompt.split("```json\n")[1].split("\n```")[0])
    assert payload["target_recent_work"] == lines[-shep.NUDGE_EVIDENCE_LINES:]
    assert shep.NUDGE_EVIDENCE_LINES > 4


def test_close_request_is_not_held_for_missing_anchor() -> None:
    context = "※ recap: all three are done and verified. No next action pending."
    text = "Reply on a new line starting with SAFE_TO_CLOSE: then why nothing is left hanging."
    assert shep.nudge_content_quality_reason(text, context) is None
    assert shep.nudge_hold_reason(text, context) is None
    assert shep.nudge_content_quality_reason(
        "Fix the assertion in test_reap.py and rerun it.", context
    ) == "candidate is not grounded in current pane context"


def test_shep_tui_pane_is_never_a_nudge_target() -> None:
    footer = (
        "queue 0 safe / 0 held / 0 drafting · drafted 0 / sent 0\n"
        "[j/k] select  [→] live  [n] nudge  [r] refresh  [q] quit  |  [click] select  [i] intent  [N] fleet\n"
    )
    assert shep.is_shell_pane(footer)
    assert not shep.is_shell_pane("※ recap: tests green. Next: open the MR.\n")


def test_sweep_drafts_panes_concurrently(monkeypatch) -> None:
    import threading as _threading

    monkeypatch.setattr(shep, "get_pane_context", lambda row, lines=15: "tests failing\n")
    monkeypatch.setattr(shep, "clean_context_lines", lambda ctx: ["tests failing"])
    in_flight = {"now": 0, "peak": 0}
    lock = _threading.Lock()

    def _slow_draft(row, recent, attempt=1, **_kwargs):
        with lock:
            in_flight["now"] += 1
            in_flight["peak"] = max(in_flight["peak"], in_flight["now"])
        time.sleep(0.2)
        with lock:
            in_flight["now"] -= 1
        return f"Fix the failing tests in {row['id']} and rerun them."

    monkeypatch.setattr(shep, "llm_draft_nudge", _slow_draft)
    shep._NUDGE_STATE.clear()
    rows = [dict(_sweep_row(), id=f"%{i}", target=f"%{i}") for i in range(4)]
    started = time.monotonic()
    results, held, _escalated = shep.sweep(send=False, rows=rows)
    elapsed = time.monotonic() - started
    assert in_flight["peak"] > 1
    assert elapsed < 0.6  # four 0.2s drafts one at a time would be 0.8s
    assert [row["id"] for row, _text, _ok, _detail in results] == ["%0", "%1", "%2", "%3"]
