#!/usr/bin/env python3
"""Validate a Founding Circle AI security register."""
import json
import sys
from pathlib import Path

REQUIRED = {"id", "name", "domain", "priority", "status", "owner", "due", "evidence"}
STATUSES = {"not_started", "in_progress", "blocked", "complete", "accepted_risk"}

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_register.py path/to/security-register.json")
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"invalid JSON: {exc}")
        return 1
    controls = data.get("controls")
    if not isinstance(controls, list):
        print("controls must be a list")
        return 1
    errors = []
    ids = set()
    for i, control in enumerate(controls, 1):
        missing = REQUIRED - control.keys()
        if missing:
            errors.append(f"control {i}: missing {sorted(missing)}")
        if control.get("id") in ids:
            errors.append(f"control {i}: duplicate id {control.get('id')}")
        ids.add(control.get("id"))
        if control.get("status") not in STATUSES:
            errors.append(f"control {i}: invalid status {control.get('status')}")
        if control.get("status") == "complete" and not control.get("evidence"):
            errors.append(f"control {i}: complete requires evidence")
    if errors:
        print("INVALID")
        print("\n".join(f"- {e}" for e in errors))
        return 1
    print(f"VALID: {len(controls)} controls; {sum(c['status']=='complete' for c in controls)} complete")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
