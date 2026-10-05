#!/usr/bin/env python3
"""Deterministic no-live-state Herdr controller used only by baseline probes."""

import json
import sys


def main() -> int:
    args = sys.argv[1:]
    if args == ["session", "list"]:
        print(json.dumps({"panes": []}, sort_keys=True))
        return 0
    print("sandbox transport refuses mutation", file=sys.stderr)
    return 77


if __name__ == "__main__":
    raise SystemExit(main())
