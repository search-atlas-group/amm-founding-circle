#!/usr/bin/env python3
"""Read-only watch on the official PHP security advisories feed.

Fetches https://github.com/php/php-src/security/advisories (the canonical
list the PHP project publishes) and reports which advisories are new since
the last run. State is one local JSON file. It never touches a server, a
site, or a PHP install: it only reads a public page and writes its own
state file.

Usage:
  python3 advisory_watch.py                 # check, print new advisories
  python3 advisory_watch.py --dry-run       # fetch and report, write nothing
  python3 advisory_watch.py --state PATH    # keep state somewhere else
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

FEED = "https://github.com/php/php-src/security/advisories"
DEFAULT_STATE = ".php-advisory-state.json"
GHSA_RE = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}")
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")
TIMEOUT_SECONDS = 20


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "php-advisory-watch"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8", "replace"), resp.status


def parse(html):
    """One entry per GHSA id, with any CVE ids mentioned near it."""
    seen = {}
    for match in GHSA_RE.finditer(html):
        ghsa = match.group(0)
        if ghsa in seen:
            continue
        window = html[match.start():match.start() + 400]
        seen[ghsa] = sorted(set(CVE_RE.findall(window)))
    return seen


def load_state(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
        return set(data.get("seen", []))
    except (OSError, json.JSONDecodeError):
        return set()


def save_state(path, seen):
    payload = {
        "feed": FEED,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "seen": sorted(seen),
    }
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description="Watch the official PHP advisory feed.")
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--dry-run", action="store_true",
                    help="report only, do not write the state file")
    args = ap.parse_args()

    try:
        html, status = fetch(FEED)
    except Exception as exc:  # network, DNS, TLS: report UNKNOWN, never "all clear"
        print(f"UNKNOWN: could not read {FEED}: {exc}")
        return 2
    if status != 200:
        print(f"UNKNOWN: {FEED} answered HTTP {status}")
        return 2

    current = parse(html)
    if not current:
        print("UNKNOWN: feed answered but no advisories parsed. Page layout may have changed.")
        return 2

    known = load_state(args.state)
    first_run = not known
    new = sorted(set(current) - known)

    if first_run:
        print(f"Baseline: {len(current)} advisories on record. Nothing flagged as new.")
    elif not new:
        print(f"No new advisories. {len(current)} on record.")
    else:
        print(f"{len(new)} new PHP security advisory(ies):")
        for ghsa in new:
            cves = ", ".join(current[ghsa]) or "no CVE listed"
            print(f"  {ghsa}  ({cves})")
        print(f"Details: {FEED}")

    if not args.dry_run:
        save_state(args.state, set(current))
    return 1 if new and not first_run else 0


if __name__ == "__main__":
    sys.exit(main())
