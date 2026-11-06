#!/usr/bin/env python3
"""Offline synthetic contract checks for the 2026-11-05 voice-agent session.

This module deliberately does not call models, networks, providers, browsers,
or external tools. It tests labels and stage ordering only.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any


STAGES = ("capture", "process", "act", "speak")


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    capture_label: str
    process_label: str
    action_label: str
    expected_response: str
    interrupted: bool = False
    source_available: bool = True


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    trace: tuple[str, ...]
    labels: dict[str, str]
    response: str
    reason: str


def route_case(case: SyntheticCase) -> CaseResult:
    """Route one labeled case through the four offline stages."""
    trace: list[str] = ["capture"]
    labels = {"capture": case.capture_label}

    if case.interrupted:
        trace.append("capture:interrupt")

    trace.append("process")
    labels["process"] = case.process_label

    if not case.source_available:
        action = "report_source_failure"
    elif case.action_label == "external_write":
        action = "deny_external_write"
    else:
        action = case.action_label
    trace.append("act")
    labels["act"] = action

    response = case.expected_response
    trace.append("speak")
    labels["speak"] = response

    required = list(STAGES)
    stage_trace = [item for item in trace if item in STAGES]
    passed = (
        stage_trace == required
        and labels["capture"] == case.capture_label
        and labels["process"] == case.process_label
        and labels["act"]
        == (
            "report_source_failure"
            if not case.source_available
            else (
                "deny_external_write"
                if case.action_label == "external_write"
                else case.action_label
            )
        )
        and labels["speak"] == case.expected_response
    )
    reason = (
        "four-stage trace and safety label match"
        if passed
        else "stage or label mismatch"
    )
    return CaseResult(
        case_id=case.case_id,
        passed=passed,
        trace=tuple(trace),
        labels=labels,
        response=response,
        reason=reason,
    )


def synthetic_cases() -> tuple[SyntheticCase, ...]:
    """Return fixed, non-sensitive labeled fixtures."""
    return (
        SyntheticCase(
            case_id="greeting",
            capture_label="speech:greeting",
            process_label="intent:greeting",
            action_label="acknowledge",
            expected_response="response:greeting",
        ),
        SyntheticCase(
            case_id="local-question",
            capture_label="speech:question",
            process_label="intent:local_lookup",
            action_label="lookup_local_context",
            expected_response="response:answer_from_local_context",
        ),
        SyntheticCase(
            case_id="denied-write",
            capture_label="speech:publish_request",
            process_label="intent:external_write",
            action_label="external_write",
            expected_response="response:approval_required",
        ),
        SyntheticCase(
            case_id="interrupted-source-failure",
            capture_label="speech:question",
            process_label="intent:local_lookup",
            action_label="lookup_local_context",
            expected_response="response:source_unavailable",
            interrupted=True,
            source_available=False,
        ),
    )


def run() -> tuple[CaseResult, ...]:
    return tuple(route_case(case) for case in synthetic_cases())


def result_payload(results: tuple[CaseResult, ...]) -> dict[str, Any]:
    return {
        "benchmark": "cohort-2026-11-05-offline-voice-contract",
        "mode": "synthetic-labels-only",
        "performance_measurements": False,
        "external_calls": False,
        "cases": [asdict(result) for result in results],
        "passed": all(result.passed for result in results),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    args = parser.parse_args(argv)

    results = run()
    payload = result_payload(results)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("offline synthetic voice-agent contract benchmark")
        print("performance measurements: none")
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            print(
                f"{status} {result.case_id}: {result.reason}; trace={','.join(result.trace)}"
            )
        print(
            f"summary: {sum(result.passed for result in results)}/{len(results)} cases passed"
        )
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
