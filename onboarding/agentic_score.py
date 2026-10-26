#!/usr/bin/env python3
"""Print a member's local Agentic Ladder status and score.

This command reads local presence signals only. It never uploads, reads file
contents, or prints machine paths. Use --ask to record answers for capabilities
that a filesystem scan cannot establish.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ladder_probe  # noqa: E402
from objectives import RUNG_NAMES  # noqa: E402


def public_status(assessment: dict) -> dict:
    """Return the stable, path-free member-facing status contract."""
    next_rung = assessment["next_rung"]
    current_rung = assessment["current_rung"]
    actions = assessment["next_actions"]
    return {
        "system_score": assessment["system_score"],
        "tier_progress": assessment["tier_progress"],
        "current_rung": current_rung,
        "current_rung_name": RUNG_NAMES[current_rung],
        "reach": assessment["reach"],
        "floor": assessment["floor"],
        "next_rung": next_rung,
        "next_rung_name": RUNG_NAMES[next_rung],
        "next_actions": [item["goal"] for item in actions],
        "gaps": assessment["gaps"],
        "unconfirmed": assessment["unconfirmed"],
        "unanswered": assessment["unanswered"],
    }


def assess_local(ask: bool = False) -> tuple[dict, dict]:
    answers = ladder_probe.load_answers()
    result = ladder_probe.evaluate(answers)
    if ask:
        answers = ladder_probe.ask_questions(result, answers)
        result = ladder_probe.evaluate(answers)
    return result, ladder_probe.assess(result)


def run(ask: bool = False) -> dict:
    _result, assessment = assess_local(ask)
    return public_status(assessment)


def update_payload(member: str, result: dict, assessment: dict) -> dict:
    """Build only the score/status slice accepted by the authenticated endpoint."""
    import importlib
    share = importlib.import_module("share")
    full = share.build_payload(member, result, assessment)
    payload = {key: full[key] for key in ("schema_version", "member", "captured_at", "ladder", "objectives")}
    leaks = share.assert_clean(payload)
    if leaks:
        raise ValueError("local score contained data that cannot be sent")
    return payload


def _portal_module():
    import importlib
    return importlib.import_module("portal")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show your local Agentic Ladder status. By default nothing is uploaded; --update-portal opts in."
    )
    parser.add_argument(
        "--ask", action="store_true",
        help="answer questions the local scan cannot verify",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the path-free status as JSON",
    )
    parser.add_argument(
        "--update-portal", action="store_true",
        help="opt in to update your authenticated portal/dashboard record",
    )
    args = parser.parse_args(argv)
    portal_result = None
    if args.update_portal:
        portal = _portal_module()
        code, conn = portal.preflight()
        if conn is None:
            print("Portal update not sent. Connect this computer first with --connect.", file=sys.stderr)
            return code
        result, assessment = assess_local(args.ask)
        try:
            payload = update_payload(conn["slug"], result, assessment)
            portal_result = portal.update_score(payload)
        except ValueError as err:
            print(f"REFUSING to update the portal: {err}", file=sys.stderr)
            return 1
        except portal.PortalError as err:
            token = (portal.load() or {}).get("token")
            print(portal.redact(str(err), token), file=sys.stderr)
            return 1
        status = public_status(assessment)
    else:
        status = run(args.ask)
    if args.json:
        if portal_result is not None:
            status = {**status, "portal_update": portal_result}
        print(json.dumps(status, indent=2, sort_keys=True))
        return 0

    print(f"Agentic score: {status['system_score']}/100")
    print("  " + "  ".join(
        f"{tier} {percent}%" for tier, percent in status["tier_progress"].items()
    ))
    print(
        f"Operating at rung {status['current_rung']} — "
        f"{status['current_rung_name']}"
    )
    print(f"  reach {status['reach'] or '-'}   floor {status['floor'] or '-'}")
    label = "Next" if not status["gaps"] else "Fix first"
    print(
        f"{label}: rung {status['next_rung']} — "
        f"{status['next_rung_name']}"
    )
    for action in status["next_actions"]:
        print(f"  - {action}")
    if status["unanswered"]:
        print(f"{len(status['unanswered'])} unanswered question(s); rerun with --ask.")
    if portal_result is not None:
        summary = portal_result.get("summary", {})
        print(f"Updated your portal/dashboard record: score {summary.get('score')}, "
              f"reach {summary.get('reach')}, floor {summary.get('floor')}.")
    else:
        print("Local presence checks only; nothing was uploaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
