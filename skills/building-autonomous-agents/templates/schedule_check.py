#!/usr/bin/env python3
"""schedule_check.py — the cloud-cron gotcha catcher.

Cloud routines almost always schedule on UTC, not your local time zone. A job
you think of as "6am" fires at 6am UTC — which is lunchtime for a lot of the
world. This is the single most common silent failure in always-on setups: the
agent runs fine, just at the wrong hour, and nothing tells you.

Give this script the local time you WANT the job to fire. It prints:
  * the correct UTC cron line to paste into a cloud routine, and
  * the next few times it will actually fire, shown in BOTH your local time
    and UTC, so you can eyeball it against your wall clock before walking away.

Pure standard library.

    python3 schedule_check.py 06:00
    python3 schedule_check.py 06:00 --tz America/New_York
    python3 schedule_check.py 18:30 --tz Europe/London --count 5
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover - very old interpreters only
    ZoneInfo = None  # type: ignore[assignment]


def parse_hhmm(value: str) -> tuple[int, int]:
    """Parse 'HH:MM' (24-hour) into (hour, minute), validating ranges."""
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"time must look like HH:MM (24-hour), got {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        raise ValueError(f"time out of range: {value!r}")
    return hour, minute


def resolve_tz(name: str | None):
    """Return a tzinfo for the given zone name, or the system local zone."""
    if name is None:
        # System local zone, whatever the machine is set to.
        local = dt.datetime.now().astimezone().tzinfo
        return local
    if ZoneInfo is None:
        raise RuntimeError(
            "zoneinfo is unavailable on this Python; upgrade to 3.9+ "
            "or omit --tz to use the system local zone."
        )
    return ZoneInfo(name)


def next_fires(hour: int, minute: int, tz, count: int) -> list[dt.datetime]:
    """The next `count` datetimes (tz-aware, local) the job fires at HH:MM."""
    now = dt.datetime.now(tz)
    first = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if first <= now:
        first = first + dt.timedelta(days=1)
    return [first + dt.timedelta(days=i) for i in range(count)]


def utc_cron_line(local_fire: dt.datetime) -> str:
    """A daily cron line, in UTC, for the given local fire time."""
    u = local_fire.astimezone(dt.timezone.utc)
    # minute hour day-of-month month day-of-week  -> daily
    return f"{u.minute} {u.hour} * * *"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("time", help="local time you want the job to fire, HH:MM (24h)")
    parser.add_argument(
        "--tz",
        default=None,
        help="IANA zone name (e.g. America/New_York). Omit to use system local zone.",
    )
    parser.add_argument(
        "--count", type=int, default=3, help="how many upcoming fire times to show"
    )
    args = parser.parse_args(argv)

    try:
        hour, minute = parse_hhmm(args.time)
        tz = resolve_tz(args.tz)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.count < 1:
        print("error: --count must be at least 1", file=sys.stderr)
        return 2

    fires = next_fires(hour, minute, tz, args.count)
    cron = utc_cron_line(fires[0])
    tz_label = args.tz or "system local"

    print(f"You want: {args.time} local ({tz_label})")
    print()
    print("Paste THIS cron line into your cloud routine (it is in UTC):")
    print(f"    {cron}")
    print()
    print("Sanity-check — the next runs, shown local and UTC side by side:")
    for f in fires:
        u = f.astimezone(dt.timezone.utc)
        print(
            f"    {f:%a %Y-%m-%d %H:%M %Z}   ==   {u:%a %Y-%m-%d %H:%M} UTC"
        )
    print()
    print("If the LOCAL column matches the hour you actually want, you're good.")
    print("If a cloud routine shows a different 'next run', trust the tool's")
    print("display over this script and adjust — some routines interpret cron")
    print("in a fixed zone. The point is: never walk away without checking it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
