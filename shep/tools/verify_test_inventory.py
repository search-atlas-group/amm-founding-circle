#!/usr/bin/env python3
"""Fail when the reviewed Shep pytest node inventory drifts."""

from __future__ import annotations

from collections import Counter
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PINNED = ROOT / "tests/pinned-node-ids.txt"


def collect() -> tuple[str, ...]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            # Collection is a structural inventory check. Third-party pytest
            # plugins on a developer machine may emit deprecation/user
            # warnings during import and turn an otherwise valid inventory
            # into exit code 1/2. The real test run still owns warning policy;
            # this subprocess only needs the node IDs.
            "-W",
            "ignore",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"pytest collection failed ({result.returncode}): {result.stderr[-2000:]}"
        )
    return tuple(
        line.strip()
        for line in result.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    )


def main() -> int:
    expected = tuple(
        line.strip()
        for line in PINNED.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    )
    actual = collect()
    if actual != expected:
        expected_counts = Counter(expected)
        actual_counts = Counter(actual)
        missing = sorted((expected_counts - actual_counts).elements())
        added = sorted((actual_counts - expected_counts).elements())
        if not missing and not added:
            position = next(
                index
                for index, (wanted, observed) in enumerate(
                    zip(expected, actual), start=1
                )
                if wanted != observed
            )
            print(
                "pytest node inventory ordering drift at position "
                f"{position}: expected={expected[position - 1]!r} "
                f"actual={actual[position - 1]!r}",
                file=sys.stderr,
            )
            return 1
        drift_kind = (
            "multiset"
            if any(count > 1 for count in (*expected_counts.values(), *actual_counts.values()))
            else "set"
        )
        print(
            f"pytest node inventory {drift_kind} drift: "
            f"missing={missing!r} added={added!r}",
            file=sys.stderr,
        )
        return 1
    print(f"pytest node inventory verified: {len(actual)} nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
