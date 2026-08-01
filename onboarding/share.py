#!/usr/bin/env python3
"""Optionally share your ladder result with the program. Nothing is automatic.

This writes a small file you can look at and then send. It does not upload
anything, and it never runs on its own -- you have to ask for it.

**What goes in it:** the ten rung statuses, the name of each check and whether
it passed, and how many of this repo's skills you have installed.

**What never goes in it:** file paths, repo names, client names, directory
listings, credentials, or anything read out of a file. The local readout shows
you paths because it is yours; the shared payload strips them, because the
program only needs to know *whether* a thing is in place, never where it lives
or who it belongs to.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import ladder_probe as probe_mod

HERE = Path(__file__).resolve().parent
SHARE_DIR = HERE / "share"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Evidence is replaced with one of these. Never the raw filesystem string.
SAFE_EVIDENCE = {
    "met": "capability present",
    "unmet": "capability not found",
    "ask": "not answered",
}


def build_payload(member: str, result: dict, verdict: dict) -> dict:
    """Assemble the redacted payload. Presence facts only, no paths or names."""
    rungs = {}
    for rung, items in result["rungs"].items():
        score = verdict["scores"][rung]
        # The internal store uses solid/partial/gap/unknown and requires
        # evidence for anything that is not unknown.
        mapped = {"solid": "solid", "partial": "partial", "gap": "gap",
                  "unconfirmed": "partial", "unknown": "unknown"}[score["status"]]
        have = [i["goal"] for i in items if i["status"] == "met"]
        missing = [i["goal"] for i in items if i["status"] == "unmet"]
        if mapped == "unknown":
            evidence = None
        else:
            evidence = (f"machine scan {date.today().isoformat()} "
                        f"({score['earned']:.0f}% of rung objectives): ") + "; ".join(
                filter(None, [
                    ("has — " + ", ".join(have)) if have else "",
                    ("missing — " + ", ".join(missing)) if missing else "",
                ])
            )
        rungs[str(rung)] = {"status": mapped, "evidence": evidence,
                            "score_pct": score["earned"]}

    return {
        "schema_version": 1,
        "source": "amm-founding-circle onboarding scan",
        "member": member,
        "captured_at": date.today().isoformat(),
        "ladder": {
            "rungs": rungs,
            "scan_reach": verdict["reach"],
            "scan_floor": verdict["floor"],
            "foundation_integrity_pct": verdict["foundation_integrity_pct"],
            "system_score": verdict["system_score"],
        },
        "objectives": [
            {"rung": rung, "id": i["id"], "status": i["status"],
             "evidence": SAFE_EVIDENCE[i["status"]], "weight": i["weight"]}
            for rung, items in result["rungs"].items() for i in items
        ],
        "skills": {
            "installed": result["skills"]["installed_total"],
            "available": result["skills"]["available_total"],
        },
        "unanswered": verdict["unanswered"],
    }


def assert_clean(payload: dict) -> list[str]:
    """Fail loudly if anything path-like slipped into the payload.

    A privacy promise that is only a comment is not a promise. This walks the
    finished payload and refuses to ship a value that looks like a filesystem
    path, a home directory, or a URL.
    """
    problems: list[str] = []
    suspicious = re.compile(r"(/Users/|/home/|~/|[A-Za-z]:\\\\|https?://|\.mcp\.json|\.git\b)")

    def walk(node, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{trail}[{i}]")
        elif isinstance(node, str) and suspicious.search(node):
            problems.append(f"{trail}: {node!r}")

    walk(payload, "payload")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("member", nargs="?", help="your slug, e.g. jane-smith")
    parser.add_argument("--print", dest="show", action="store_true", help="print it, write nothing")
    parser.add_argument("--out-dir", default=str(SHARE_DIR))
    args = parser.parse_args(argv)

    member = args.member or "unnamed-member"
    if args.member and not SLUG_RE.match(member):
        print(f"slug should be lower-case-with-dashes, got {member!r}")
        return 64

    result = probe_mod.probe(probe_mod.load_answers())
    verdict = probe_mod.assess(result)
    payload = build_payload(member, result, verdict)

    leaks = assert_clean(payload)
    if leaks:
        print("REFUSING to write — something path-like got into the payload:")
        for leak in leaks:
            print(f"  {leak}")
        print("This is a bug. Please report it rather than sending the file by hand.")
        return 1

    text = json.dumps(payload, indent=2)
    if args.show:
        print(text)
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{member}.json"
    path.write_text(text + "\n", encoding="utf-8")

    print(f"Written: {path}")
    print("\nOpen it and read it before you send it — it is a small file, on purpose.")
    print("It contains your ten rung statuses and which checks passed. No paths,")
    print("no client names, no file contents. Send it to JD in the cohort channel")
    print("when you're happy with it. Nothing was uploaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
