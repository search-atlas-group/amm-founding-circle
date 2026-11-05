"""Offline fixture policy rehearsal. Not a voice server or authentication service."""

import argparse
import json
from pathlib import Path
import re

FIXTURE = Path(__file__).resolve().parents[1] / "templates" / "sessions.fixture.json"
FUNCTION = "get_pilot_session_status"
SESSION_PATTERN = re.compile(r"pilot-[a-z0-9-]{1,58}\Z")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--session", help="Synthetic test session ID")
    selection.add_argument(
        "--arguments-json", help="Untrusted function arguments for rehearsal"
    )
    parser.add_argument("--function", default=FUNCTION)
    parser.add_argument(
        "--authorized-session",
        default="pilot-alpha",
        help="Operator-supplied TEST context only; not authentication",
    )
    args = parser.parse_args()
    error = None
    payload = None
    if args.function != FUNCTION:
        error = "DENIED_FUNCTION"
    else:
        try:
            arguments = (
                json.loads(args.arguments_json)
                if args.arguments_json is not None
                else {"session_id": args.session}
            )
        except (json.JSONDecodeError, RecursionError):
            arguments = None
        if (
            not isinstance(arguments, dict)
            or set(arguments) != {"session_id"}
            or not isinstance(arguments["session_id"], str)
            or len(arguments["session_id"]) > 64
            or not SESSION_PATTERN.fullmatch(arguments["session_id"])
        ):
            error = "INVALID_ARGUMENTS"
        elif arguments["session_id"] != args.authorized_session:
            error = "DENIED_SESSION"
        else:
            try:
                data = json.loads(FIXTURE.read_text(encoding="utf-8"))
                record = data["sessions"].get(arguments["session_id"])
                if record is None:
                    error = "NOT_FOUND"
                else:
                    fields = ("session_id", "status", "summary", "blocker", "freshness")
                    payload = {
                        "ok": True,
                        "source_mode": "SYNTHETIC_FIXTURE_NOT_LIVE",
                        "session": {field: record[field] for field in fields},
                    }
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                RecursionError,
            ):
                error = "FIXTURE_UNAVAILABLE"
    if error:
        payload = {
            "ok": False,
            "error": error,
            "source_mode": "SYNTHETIC_FIXTURE_NOT_LIVE",
        }
    print(json.dumps(payload, sort_keys=True))
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
