#!/usr/bin/env python3
"""check_brief.py — a tiny, read-only sanity check for a finished morning brief.

It does NOT read your mail, tasks, or any account. It only reads a brief file you
already produced and checks two things a trustworthy brief must have:

  1. A STATUS line is present and well-formed.
  2. The correlate-first work actually happened — i.e. the STATUS line reports
     how many items were closed as already-handled and how many are waiting on
     someone else, and lists which sources it reached vs skipped.

Why this exists: a brief with no STATUS line, or one where "closed_as_already_
handled" and "waiting_on_others" are always absent, is a brief that skipped the
one step that makes it worth trusting (Correlate before you Judge). This flags
that at a glance.

Usage:
    python3 check_brief.py path/to/morning-brief.md

Exit code 0 = the brief looks honest. Exit code 1 = something's missing (details
printed). Pure standard library. Reads one file. Writes nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# The fields we expect the STATUS line to carry. Keep in sync with
# templates/brief-format.md.
REQUIRED_STATUS_FIELDS = (
    "do-now",
    "schedule",
    "handoff",
    "fyi",
    "closed_as_already_handled",
    "waiting_on_others",
    "reached",
    "skipped",
)

VALID_RUN_STATES = ("DELIVERED", "DEGRADED", "FAILED")


def find_status_line(text: str) -> str | None:
    """Return the STATUS line from a brief, or None if it's missing."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("STATUS:"):
            return stripped
    return None


def check_brief(path: Path) -> list[str]:
    """Return a list of problems found in the brief. Empty list = all good."""
    problems: list[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as err:
        return [f"could not read {path}: {err}"]

    if not text.strip():
        return [f"{path} is empty"]

    status = find_status_line(text)
    if status is None:
        problems.append(
            "no STATUS line found — a brief must end with a STATUS line so you "
            "can trust it at a glance (see templates/brief-format.md)."
        )
        # Without a STATUS line there is nothing further to check.
        return problems

    # The run state (DELIVERED / DEGRADED / FAILED) should be present.
    if not any(state in status.upper() for state in VALID_RUN_STATES):
        problems.append(
            "STATUS line has no run state — expected one of "
            f"{', '.join(VALID_RUN_STATES)}."
        )

    # Each required field must appear as "field:<value>".
    for field in REQUIRED_STATUS_FIELDS:
        if not re.search(rf"\b{re.escape(field)}\s*:", status):
            problems.append(
                f"STATUS line is missing '{field}:' — this field is what proves "
                "the correlate-first step and the source sweep actually ran."
            )

    # The two correlate-first counts should be real numbers, and it's a yellow
    # flag (not fatal) if BOTH are zero every single day — that usually means the
    # agent isn't correlating, just listing.
    closed = _extract_int(status, "closed_as_already_handled")
    waiting = _extract_int(status, "waiting_on_others")
    if closed == 0 and waiting == 0:
        problems.append(
            "note: both closed_as_already_handled and waiting_on_others are 0. "
            "That can be a real quiet day — but if it's 0/0 every day, the agent "
            "is probably NOT correlating across sources (it's listing signals, "
            "not judging who has the ball). Review the correlate-first step."
        )

    return problems


def _extract_int(status: str, field: str) -> int | None:
    """Pull the integer value of 'field:<n>' from the STATUS line, if present."""
    match = re.search(rf"\b{re.escape(field)}\s*:\s*(\d+)", status)
    if match is None:
        return None
    return int(match.group(1))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        print("error: pass exactly one path to a brief file.", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2

    problems = check_brief(path)
    if not problems:
        print(f"OK — {path} has an honest, well-formed STATUS line.")
        return 0

    print(f"Found {len(problems)} thing(s) to look at in {path}:")
    for i, problem in enumerate(problems, start=1):
        print(f"  {i}. {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
