#!/usr/bin/env python3
"""Suppress NEEDS-HUMAN escalations whose pane no longer exists.

Why this exists
---------------
Over the 24h to 2026-09-12T01:02Z every NEEDS-HUMAN escalation delivered to the
owner (22/22) named a herdr pane that does not exist. `herdr:wY:p1` alone was
delivered 5 times. Each one costs a full human triage to reach the same answer:
"the pane is gone, there is nothing behind this".

shep decides to escalate from PERSISTED LADDER STATE (`exhausted_reason ==
"needs_human"`), and never asks herdr whether the pane is still there. A pane
destroyed mid-ladder therefore keeps paging a human about work that no longer
exists, forever, because the only documented exit from the latch is
`update_stall` observing the pane move -- and a destroyed pane cannot move.

This module is the missing predicate, isolated so it can be used three ways
without touching shep's sweep:

    from escalation_guard import should_escalate
    if should_escalate(target):        # library use, inside a sweep
        post_escalation(...)

    ./escalation_guard.py herdr:wY:p1  # exit 0 escalate / 1 suppress
    ./escalation_guard.py --audit      # measure the phantom rate

Fail-open by design
-------------------
If herdr cannot be reached we return True (escalate). A monitoring guard that
silences real pages when its own dependency is down is worse than the noise it
removes: the 2026-09-07 postmortem was about handoffs nobody saw. Unreachable
herdr is not evidence a pane is gone.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = Path.home() / ".local/share/mbot/live/runtime/mbot.sqlite"
PANE_RE = re.compile(r"herdr:(w[0-9A-Za-z]+:p[0-9A-Za-z]+)")
ESCALATION_MARKER = "NEEDS-HUMAN"
NUDGE_STATE = Path(
    os.environ.get(
        "SHEP_NUDGE_STATE",
        str(Path.home() / ".mission-engine" / "shep-nudge-state.json"),
    )
)


class HerdrUnavailable(RuntimeError):
    """herdr could not be asked. Never means 'the pane is gone'."""


def live_panes(timeout: float = 60.0) -> set[str]:
    """Pane ids herdr's own server reports right now. -> {"w5M:p1", ...}"""
    try:
        proc = subprocess.run(
            ["herdr", "pane", "list"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HerdrUnavailable(str(exc)) from exc
    if proc.returncode != 0:
        raise HerdrUnavailable(proc.stderr.strip()[:200] or "non-zero exit")
    try:
        payload = json.loads(proc.stdout)
        panes = payload["result"]["panes"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HerdrUnavailable(f"unparseable pane list: {exc}") from exc
    # An empty fleet is a real answer, but it is also what a half-started
    # server returns, and treating it as "every pane is gone" would silence
    # the entire deck at once. Refuse to draw conclusions from it.
    if not panes:
        raise HerdrUnavailable("herdr reported zero panes")
    return {p["pane_id"] for p in panes if p.get("pane_id")}


def pane_of(target: str) -> str:
    """The bare pane id inside a shep target. 'herdr:w5M:p1' -> 'w5M:p1'."""
    match = PANE_RE.search(target or "")
    return match.group(1) if match else (target or "").removeprefix("herdr:")


def ladder_targets(path: Path | None = None) -> set[str]:
    """Targets this host's own nudge ladder has ever tracked.

    This is the ownership record. shep only escalates a target it nudged six
    times, and it can only nudge a pane it tracked, so a target absent from the
    ladder was never this fleet's to escalate -- and a `herdr pane list` here
    is not evidence about it either way.
    """
    source = NUDGE_STATE if path is None else path
    try:
        state = json.loads(source.read_text())
    except (OSError, ValueError):
        return set()
    nudge = state.get("nudge")
    return set(nudge) if isinstance(nudge, dict) else set()


def is_ours(target: str, tracked: set[str] | None = None) -> bool:
    """Whether this host's ladder has ever tracked `target`.

    A target from a workspace id-space this machine does not own (another
    host's herdr server, another fleet) is unaddressable here: our pane list
    can neither confirm nor deny it.
    """
    known = ladder_targets() if tracked is None else tracked
    if not known:
        # No ladder to consult => no ownership claim either way. Treat every
        # target as ours so the pane-existence check still runs, exactly as it
        # did before ownership was considered.
        return True
    return target in known


def should_escalate(
    target: str,
    panes: set[str] | None = None,
    tracked: set[str] | None = None,
) -> bool:
    """False only when herdr positively reports OUR OWN pane is gone.

    Two distinct reasons a pane is missing from `herdr pane list`, which the
    first version of this guard conflated:

    1. It was destroyed. It was ours, we tracked it, it is gone -- nothing is
       waiting behind the page, so suppress.
    2. It was never ours. Its workspace belongs to another herdr server, so our
       pane list says nothing about it. Absence here is not evidence of
       absence there, and silencing it would be the exact failure mode the
       2026-09-07 postmortem was written about: a real handoff nobody sees.

    Only (1) is evidence. (2) fails open, like every other unknown.

    Non-herdr targets (tmux, t3, warp) are not addressable by this check and
    always escalate.
    """
    if not target or not target.startswith("herdr:"):
        return True
    if not is_ours(target, tracked):
        return True  # another fleet's pane: unaddressable, so fail open
    try:
        panes = live_panes() if panes is None else panes
    except HerdrUnavailable:
        return True  # fail open, loudly upstream
    return pane_of(target) in panes


def audit(hours: int = 24) -> int:
    """Measure the phantom rate in delivered escalations. -> exit code.

    Reports the two causes separately. A run that shows every page as FOREIGN
    is telling you this host is not the emitter and the guard cannot fix it
    from here -- which a single blended "100% suppressed" number hides.
    """
    if not DB.exists():
        print(f"no store at {DB}", file=sys.stderr)
        return 2
    try:
        panes = live_panes()
    except HerdrUnavailable as exc:
        print(f"herdr unavailable: {exc}", file=sys.stderr)
        return 2
    tracked = ladder_targets()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT content FROM inbound_messages WHERE content LIKE ?"
        " AND external_created_at_ms > (strftime('%s','now')-?)*1000",
        (f"%{ESCALATION_MARKER}%", hours * 3600),
    ).fetchall()
    seen: dict[str, list] = {}
    for (content,) in rows:
        match = PANE_RE.search(content or "")
        if not match:
            continue
        pane = match.group(1)
        if pane in seen:
            seen[pane][0] += 1
            continue
        target = f"herdr:{pane}"
        if not is_ours(target, tracked):
            verdict = "FOREIGN"
        elif pane in panes:
            verdict = "DELIVER"
        else:
            verdict = "SUPPRESS"
        seen[pane] = [1, verdict]
    total = sum(n for n, _ in seen.values())
    if not total:
        print(f"no {ESCALATION_MARKER} escalations in the last {hours}h")
        return 0
    tally = {"SUPPRESS": 0, "DELIVER": 0, "FOREIGN": 0}
    for count, verdict in seen.values():
        tally[verdict] += count
    print(f"{ESCALATION_MARKER} escalations, last {hours}h: {total}")
    print(f"  SUPPRESSED (our pane, destroyed) : {tally['SUPPRESS']}"
          f" ({100*tally['SUPPRESS']//total}%)")
    print(f"  DELIVERED  (our pane, still live): {tally['DELIVER']}")
    print(f"  FOREIGN    (not this host's fleet): {tally['FOREIGN']}"
          f" ({100*tally['FOREIGN']//total}%)")
    if tally["FOREIGN"] == total:
        print()
        print("  Every page names a pane this host never tracked. This machine")
        print("  is not the emitter; the guard cannot suppress these from here.")
    print()
    for pane, (n, verdict) in sorted(seen.items(), key=lambda kv: -kv[1][0]):
        print(f"  {pane:<12} x{n:<3} {verdict}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", help="e.g. herdr:wY:p1")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()
    if args.audit:
        return audit(args.hours)
    if not args.target:
        parser.error("give a target or --audit")
    ok = should_escalate(args.target)
    pane = pane_of(args.target)
    print(f"{'ESCALATE' if ok else 'SUPPRESS'}  {pane}")
    if not ok:
        print("  herdr does not list this pane; nothing is waiting behind it.")
    elif args.target.startswith("herdr:") and not is_ours(args.target):
        print("  this host's ladder never tracked it: another fleet's pane,")
        print("  so a local pane list is not evidence about it. Failing open.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
