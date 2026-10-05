"""Drive the real curses loop against a fake screen.

Every TUI defect found in this codebase so far was found by a human looking at
a terminal: a mouse click that killed the app, a context panel describing the
wrong session, a queue headed "24 waiting on you" containing nothing that was.
None were reachable by the existing suite, because the suite only ever calls the
pure helpers -- it never presses a key, so the ~1,400-line event loop that binds
those helpers together was untested by construction.

This is the smallest thing that closes that gap. `run_tui` already supports a
fixture mode (`initial_rows`), which disables pane collection, drafting and the
background refresh thread, so the loop can be driven deterministically. What was
missing was a screen to draw on and a way to press keys.

Deliberately not tmux: a real terminal exercises real curses but cannot run in
CI, is slow, and is flaky in exactly the way a regression net must not be. This
runs in milliseconds and asserts on the characters shep actually placed.
"""

from __future__ import annotations

import curses
import unicodedata
from typing import NamedTuple


class MouseEvent(NamedTuple):
    """One deterministic event in the shape returned by ``curses.getmouse``."""

    mouse_id: int
    x: int
    y: int
    z: int
    button_state: int


class ResizeEvent(NamedTuple):
    """A terminal resize applied immediately before ``KEY_RESIZE``."""

    height: int
    width: int


def click(x, y, button_state=None):
    """Inject a primary-button click at terminal coordinate ``(x, y)``."""
    return MouseEvent(
        0,
        x,
        y,
        0,
        curses.BUTTON1_CLICKED if button_state is None else button_state,
    )


def resize(*, height, width):
    """Resize the fake terminal and inject curses' resize notification."""
    return ResizeEvent(height, width)


def bracketed_paste(text):
    """Real ``get_wch`` events for one terminal bracketed-paste payload."""
    return list("\x1b[200~") + list(text) + list("\x1b[201~")


class FakeScreen:
    """A curses window that records what was drawn instead of drawing it."""

    def __init__(self, height=40, width=120, keys=()):
        self.height = height
        self.width = width
        # Keys are consumed in order. -1 is curses' "nothing pressed", which the
        # loop treats as an idle tick, so a test can render frames without
        # acting. Running out raises rather than looping forever: a harness that
        # hangs on a missing quit key is worse than one that fails loudly.
        self._keys = list(keys)
        self._mouse_events = []
        self._grid = self._blank()
        self._frames = []

    def _blank(self):
        return [[" "] * self.width for _ in range(self.height)]

    # --- the surface shep actually uses ---------------------------------
    def getmaxyx(self):
        return self.height, self.width

    def erase(self):
        self._grid = self._blank()

    @staticmethod
    def _char_width(char):
        if unicodedata.combining(char) or unicodedata.category(char) in {
            "Cf",
            "Me",
            "Mn",
        }:
            return 0
        return 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1

    @classmethod
    def _cell_width(cls, text):
        return sum(cls._char_width(char) for char in text)

    def addstr(self, y, x, text, attr=0):
        # Same contract as curses: out-of-bounds is an error, and shep already
        # guards for it with safe_addstr. Raising here is what proves that guard
        # is actually in front of every write.
        rendered = str(text)
        if (
            not (0 <= y < self.height)
            or x < 0
            or x >= self.width
            or x + self._cell_width(rendered) > self.width
        ):
            raise curses.error(f"addstr out of bounds at ({y}, {x})")
        row = self._grid[y]
        cell = x
        for char in rendered:
            width = self._char_width(char)
            if width == 0:
                for previous in range(cell - 1, -1, -1):
                    if row[previous]:
                        row[previous] += char
                        break
                else:
                    row[cell] += char
                continue
            row[cell] = char
            if width == 2:
                row[cell + 1] = ""
            cell += width

    def getch(self):
        if not self._keys:
            raise AssertionError(
                "harness ran out of keys — the loop never quit. "
                "End the key list with ord('q')."
            )
        event = self._keys.pop(0)
        if isinstance(event, MouseEvent):
            self._mouse_events.append(event)
            return curses.KEY_MOUSE
        if isinstance(event, ResizeEvent):
            self.height, self.width = event
            self._grid = self._blank()
            return curses.KEY_RESIZE
        return event

    def get_wch(self):
        """Return one wide-character or logical-key event, like curses does."""
        return self.getch()

    def getmouse(self):
        if not self._mouse_events:
            raise AssertionError("getmouse called without an injected mouse event")
        return self._mouse_events.pop(0)

    def nodelay(self, _flag=True):
        return None

    def timeout(self, _ms):
        return None

    def refresh(self):
        # Keep a bounded-by-test transcript of rendered frames.  Public-loop
        # tests need to prove that an action changed views (detail -> list),
        # surfaced a receipt, or rendered a temporary resize warning; the
        # final frame alone cannot distinguish those cases.
        self._frames.append(self.text())
        return None

    def redrawwin(self):
        return None

    # --- assertions ------------------------------------------------------
    def lines(self):
        """Rendered screen as a list of rstripped strings."""
        return ["".join(row).rstrip() for row in self._grid]

    def text(self):
        return "\n".join(self.lines())

    def line_containing(self, needle):
        """The first rendered line containing `needle`, or None."""
        return next((line for line in self.lines() if needle in line), None)

    def frames(self):
        """All rendered frame snapshots, oldest first."""
        return list(self._frames)

    def saw(self, needle):
        """Whether any rendered frame contained `needle`."""
        return any(needle in frame for frame in self._frames)


def _stub_curses(monkeypatch, screen=None):
    """Neutralise the module-level curses calls the loop makes on entry."""
    for name in (
        "curs_set",
        "start_color",
        "use_default_colors",
        "init_pair",
        "def_prog_mode",
        "reset_prog_mode",
        "endwin",
        "flushinp",
        "mouseinterval",
    ):
        monkeypatch.setattr(curses, name, lambda *_a, **_k: None, raising=False)
    monkeypatch.setattr(curses, "has_colors", lambda: False, raising=False)
    monkeypatch.setattr(curses, "color_pair", lambda n: 0, raising=False)
    monkeypatch.setattr(
        curses,
        "mousemask",
        lambda mask, *_a: (mask, 0),
        raising=False,
    )
    if screen is not None:
        fallback_getmouse = curses.getmouse

        def getmouse():
            if screen._mouse_events:
                return screen.getmouse()
            return fallback_getmouse()

        monkeypatch.setattr(curses, "getmouse", getmouse, raising=False)


def drive(monkeypatch, rows, keys, height=40, width=120, theme="classic"):
    """Run the real loop over `rows`, pressing `keys`. -> FakeScreen

    `rows` puts run_tui in fixture mode, which is what makes this deterministic:
    no pane collection, no drafting, no background refresh thread.
    """
    from scripts import shep

    screen = FakeScreen(height=height, width=width, keys=list(keys))
    _stub_curses(monkeypatch, screen)
    shep.run_tui(screen, theme, rows)
    return screen


def fleet_row(target, label="worker", **over):
    """One live pane, shaped the way collect_all would hand it over."""
    row = {
        "source": "herdr",
        "id": target,
        "target": target,
        "label": label,
        "status": "idle",
        "cwd": "/tmp/repo",
        "context": "pytest failed in test_api.py",
        "preview": "pytest failed in test_api.py",
        "quiet_for": 120,
    }
    row.update(over)
    return row


def _screen(monkeypatch, keys, height, width):
    screen = FakeScreen(height=height, width=width, keys=list(keys))
    _stub_curses(monkeypatch, screen)
    return screen


def drive_missions(
    monkeypatch,
    missions,
    keys,
    rows=None,
    height=40,
    width=120,
    error=None,
):
    """Run the MISSIONS sub-loop over a fixed deck. -> (FakeScreen, result)

    The deck loader shells out to mission-sense/recommend and can take minutes,
    so it is stubbed rather than called: this exercises the view's keys and
    rendering, which is the part no test could reach before.
    """
    from scripts import shep

    screen = _screen(monkeypatch, keys, height, width)
    monkeypatch.setattr(
        shep,
        "load_mission_deck",
        lambda **_k: (list(missions), error),
    )
    monkeypatch.setattr(shep, "mission_is_running", lambda _m: False)
    return screen, shep.run_missions_view(screen, False, rows or [])


def drive_logs(monkeypatch, entries, keys, height=40, width=120, error=None):
    """Run the LOGS sub-loop over a fixed ledger. -> (FakeScreen, result)"""
    from scripts import shep

    screen = _screen(monkeypatch, keys, height, width)
    monkeypatch.setattr(shep, "load_action_log", lambda: (list(entries), error))
    return screen, shep.run_logs_view(screen, False)


def drive_beads(
    monkeypatch,
    beads,
    missions=(),
    keys=(),
    height=40,
    width=120,
):
    """Run the BEADS sub-loop over a fixed backlog. -> (FakeScreen, result)

    Both the fleet bead scan and the triage model call are stubbed: one walks
    the disk, the other is a billed request, and neither is what these assert.
    """
    from scripts import shep

    screen = _screen(monkeypatch, keys, height, width)
    monkeypatch.setattr(shep, "load_beads", lambda: (list(beads), None))
    monkeypatch.setattr(
        shep,
        "bead_strip",
        lambda _b, force=False: (list(missions), {}, "stubbed"),
    )
    return screen, shep.run_beads_view(screen, False)


def mission(mission_id, project="repo", goal="do the thing", **over):
    """One deck entry, shaped the way recommend.py hands it over."""
    row = {
        "id": mission_id,
        "project_name": project,
        "short_goal": goal,
        "momentum_score": 50,
        "cwd": "/tmp/repo",
        "next_step": "start step 1",
        "rationale": "momentum stalled",
    }
    row.update(over)
    return row
