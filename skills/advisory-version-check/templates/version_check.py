#!/usr/bin/env python3
"""Compare one local stack inventory against one advisory's affected ranges.

Read-only. It never contacts a site, never fetches an advisory, and never
writes a fix. A missing version or an unparseable range is UNKNOWN, not safe.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def parse_version(value):
    if not value or not isinstance(value, str):
        return None
    match = re.search(r"\d+(?:\.\d+){0,3}", value.strip())
    if not match:
        return None
    parts = [int(part) for part in match.group(0).split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def compare_version(left, right):
    size = max(len(left), len(right))
    a = left + (0,) * (size - len(left))
    b = right + (0,) * (size - len(right))
    return (a > b) - (a < b)


def matches_range(version, spec):
    """Return True, False, or None when the spec cannot be read.

    Supported shapes, comma-separated: >=X, >X, <=X, <X, ==X, X.
    A bare number means an exact match on the numbers given.
    """
    parsed = parse_version(version)
    clauses = [part.strip() for part in spec.split(",") if part.strip()]
    if parsed is None or not clauses:
        return None
    for clause in clauses:
        match = re.match(r"^(>=|<=|>|<|==)?\s*(\d+(?:\.\d+){0,3})$", clause)
        if not match:
            return None
        op, raw = match.group(1) or "==", match.group(2)
        bound = parse_version(raw)
        order = compare_version(parsed, bound)
        if op == ">=" and order < 0:
            return False
        if op == ">" and order <= 0:
            return False
        if op == "<=" and order > 0:
            return False
        if op == "<" and order >= 0:
            return False
        if op == "==" and parsed[:len(bound)] != bound:
            return False
    return True


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def check(inventory, advisory):
    components = inventory.get("components") or []
    by_name = {}
    for component in components:
        name = (component.get("name") or "").lower()
        if name:
            by_name.setdefault(name, component)

    rows = []
    for affected in advisory.get("affected") or []:
        name = (affected.get("name") or "").strip()
        spec = (affected.get("range") or "").strip()
        found = by_name.get(name.lower())
        if not name or not spec:
            rows.append({"name": name or "UNKNOWN", "status": "UNKNOWN", "reason": "advisory row is incomplete"})
            continue
        if found is None:
            rows.append({"name": name, "status": "not-present", "reason": "not in the local inventory"})
            continue
        version = found.get("version") or "UNKNOWN"
        result = matches_range(version, spec)
        if result is None:
            rows.append({
                "name": name,
                "version": version,
                "range": spec,
                "status": "UNKNOWN",
                "reason": "version or range could not be read",
            })
        else:
            rows.append({
                "name": name,
                "version": version,
                "range": spec,
                "status": "in-range" if result else "out-of-range",
                "reason": "compared against the stated range only",
            })
    return {
        "advisory": advisory.get("id") or "UNKNOWN",
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--advisory", required=True)
    args = parser.parse_args()
    inventory = load_json(args.inventory)
    advisory = load_json(args.advisory)
    if inventory is None or advisory is None:
        print("UNKNOWN: inventory or advisory file could not be read")
        return 2
    report = check(inventory, advisory)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if any(row["status"] == "UNKNOWN" for row in report["rows"]):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
