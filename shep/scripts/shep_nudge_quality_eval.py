#!/usr/bin/env python3
"""Deterministic, fixture-driven quality evals for Shep nudges.

Cases use sanitized pane/conversation context and a candidate nudge.  The same
schema can hold simulated conversations or reviewed real examples; this tool
never calls a model and never writes candidate text to telemetry.  Send/hold
decisions use Shep's production risk and content gates; the quality score is
reviewer-facing diagnostic evidence, not a second delivery policy.

Example:
  python3 scripts/shep_nudge_quality_eval.py \
    --fixtures tests/fixtures/shep_nudge_quality_eval.json --strict
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts import shep as _shep
except ImportError:  # direct `python scripts/shep_nudge_quality_eval.py`
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import shep as _shep  # type: ignore[no-redef]


DEFAULT_MIN_SCORE = 70
DEFAULT_FIXTURES = (
    Path(__file__).resolve().parent.parent
    / "tests/fixtures/shep_nudge_quality_eval.json"
)
DEFAULT_TRAJECTORY_FIXTURES = (
    Path(__file__).resolve().parent.parent
    / "tests/fixtures/shep_nudge_trajectory_eval.json"
)

_ACTION_RE = re.compile(
    r"\b(?:apply|capture|check|compare|commit|finish|fix|inspect|name|open|"
    r"record|recompute|reproduce|rerun|run(?:ning)?|trace|update|verify|wrap)\b",
    re.IGNORECASE,
)
_GENERIC_RE = re.compile(
    r"\b(?:continue|resume|keep going)\b[^.!?]{0,36}\b(?:current|objective|task|work)\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"(?:https?://|\bwww\.)\S+", re.IGNORECASE)
_UI_NOISE_RE = re.compile(
    r"(?:^\s*saw\s*:|codex-gw\s*[▸>-]|claude code|happy session id|"
    r"status:\s*(?:idle|starting|working)|api/v\d+/proxy|"
    r"esc to interrupt|contextq:|tokens used)",
    re.IGNORECASE,
)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def conversation_lines(case: dict[str, Any]) -> list[str]:
    """Extract pane-like text from either simulated or reviewed real cases."""
    entries = case.get("conversation", case.get("pane_lines", [])) or []
    lines: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            lines.append(entry)
        elif isinstance(entry, dict) and entry.get("text") is not None:
            lines.append(str(entry["text"]))
    return lines


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).lower()))


def _contains_term(text: str, term: str) -> bool:
    candidate = _normalized(text)
    expected = _normalized(term)
    return bool(expected) and expected in candidate


def _candidate_score(
    candidate: str,
    context: str,
    expected: dict[str, Any],
) -> tuple[int, list[str], list[str]]:
    violations: list[str] = []
    matched: list[str] = []
    grounding_terms = [str(term) for term in expected.get("grounding_terms", [])]
    for term in grounding_terms:
        if _contains_term(candidate, term):
            matched.append(term)
    if grounding_terms and len(matched) != len(grounding_terms):
        violations.append("missing_grounding")
    for term in expected.get("context_terms", []):
        if not _contains_term(context, str(term)):
            violations.append("context_mismatch")
    for term in expected.get("grounded_terms", []):
        if not _contains_term(context, str(term)) or not _contains_term(candidate, str(term)):
            violations.append("context_mismatch")

    if not _ACTION_RE.search(candidate) or _GENERIC_RE.search(candidate):
        violations.append("non_actionable")
    if "?" in candidate:
        violations.append("question")
    if _UI_NOISE_RE.search(candidate) or _URL_RE.search(candidate) or _CONTROL_RE.search(candidate):
        violations.append("ui_noise")
    if len(candidate) > 220 or len(candidate.split()) > 40:
        violations.append("overlong")
    for term in expected.get("forbidden_terms", []):
        if _contains_term(candidate, str(term)):
            violations.append("forbidden_term")
            break

    grounding = 40 * len(matched) // len(grounding_terms) if grounding_terms else 0
    actionability = 25 if "non_actionable" not in violations else 0
    clarity = 15 if not {"question", "forbidden_term"} & set(violations) else 0
    cleanliness = 10 if "ui_noise" not in violations else 0
    brevity = 10 if "overlong" not in violations else 0
    return grounding + actionability + clarity + cleanliness + brevity, matched, violations


def evaluate_case(case: dict[str, Any], min_score: int = DEFAULT_MIN_SCORE) -> dict[str, Any]:
    """Evaluate one candidate through the observable Shep safety boundary."""
    expected = case.get("expected") or {}
    raw_candidate = case.get("candidate")
    candidate = None if raw_candidate is None else str(raw_candidate).strip()
    if _shep.is_abstention(candidate):
        actual = {
            "decision": "abstain",
            "risk": "none",
            "risk_reason": "candidate abstained",
            "production_quality_reason": "candidate abstained",
            "quality_score": 100,
            "matched_grounding": [],
            "violations": [],
        }
    elif not candidate:
        actual = {
            "decision": "abstain",
            "risk": "none",
            "risk_reason": "candidate absent",
            "production_quality_reason": "candidate absent",
            "quality_score": 100,
            "matched_grounding": [],
            "violations": [],
        }
    else:
        context_lines = conversation_lines(case)
        context = "\n".join(context_lines)
        score, matched, violations = _candidate_score(candidate, context, expected)
        risk, risk_reason = _shep.classify_risk(candidate)
        production_quality_reason = _shep.nudge_content_quality_reason(
            candidate, context_lines
        )
        if _shep.is_repeat_nudge(
            candidate,
            {"prior_nudges": list(case.get("prior_nudges") or [])},
        ):
            violations.append("semantic_repeat")
            production_quality_reason = "semantic repeat of an earlier nudge"
        decision = (
            "send"
            if risk == "safe_continuation"
            and production_quality_reason is None
            else "hold"
        )
        actual = {
            "decision": decision,
            "risk": risk,
            "risk_reason": risk_reason,
            "production_quality_reason": production_quality_reason,
            "quality_score": score,
            "matched_grounding": matched,
            "violations": violations,
        }

    expected_risk = expected.get("risk")
    expected_decision = expected.get("decision")
    passed = True
    if expected_decision is not None and actual["decision"] != expected_decision:
        passed = False
    if expected_risk is not None and actual["risk"] != expected_risk:
        passed = False
    if expected.get("decision") == "send" and "missing_grounding" in actual["violations"]:
        passed = False
    return {
        "id": str(case.get("id") or "unnamed"),
        "passed": passed,
        "candidate_present": bool(candidate and not _shep.is_abstention(candidate)),
        "context_lines": len(conversation_lines(case)),
        **actual,
    }


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSON case collection or one JSON object per line."""
    source = Path(path)
    if source.suffix == ".jsonl":
        return [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    payload = json.loads(source.read_text())
    if isinstance(payload, list):
        return payload
    return payload.get("cases", [])


def evaluate_cases(cases: list[dict[str, Any]], min_score: int = DEFAULT_MIN_SCORE) -> dict[str, Any]:
    results = [evaluate_case(case, min_score=min_score) for case in cases]
    violations = Counter(
        violation
        for result in results
        for violation in result["violations"]
    )
    scores = [result["quality_score"] for result in results if result["candidate_present"]]
    return {
        "cases": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "mean_quality_score": sum(scores) / len(scores) if scores else None,
        "decisions": dict(Counter(result["decision"] for result in results)),
        "violations": dict(violations),
        "results": results,
    }


def evaluate_trajectory_case(case: dict[str, Any]) -> dict[str, Any]:
    """Drive production ``sweep`` across repeated pane observations."""
    target = f"%trajectory-{case.get('id', 'case')}"
    observations = list(case.get("observations") or [])
    expected = dict(case.get("expected") or {})
    now = [1000.0]
    current = {"candidate": None, "context": "", "send_ok": True}
    model_calls = 0
    sends: list[str] = []
    send_contexts: list[list[str]] = []
    held = 0
    progress = 0
    prior_for_novelty = list(case.get("prior_nudges") or [])
    unsafe_sends = 0
    ungrounded_sends = 0
    repeat_sends = 0
    send_attempts = 0
    failed_sends = 0
    unsafe_candidates = 0
    call_attempts: dict[int, list[bool]] = {}

    originals = {
        "get_pane_context": _shep.get_pane_context,
        "llm_draft_nudge": _shep.llm_draft_nudge,
        "send_nudge": _shep.send_nudge,
        "post_telemetry": _shep.post_telemetry,
        "record_outcome": _shep.record_outcome,
        "time": _shep.time.time,
    }

    def draft(*_args, **_kwargs):
        nonlocal model_calls, unsafe_candidates
        model_calls += 1
        fingerprint = _shep.nudge_context_fingerprint(current["context"])
        call_attempts.setdefault(fingerprint, []).append(current["candidate"] is not None)
        candidate = current["candidate"]
        if candidate and not _shep.is_abstention(candidate):
            if _shep.classify_risk(candidate)[0] != "safe_continuation":
                unsafe_candidates += 1
        return current["candidate"]

    def send(_row, text, **_kwargs):
        nonlocal unsafe_sends, ungrounded_sends, repeat_sends
        nonlocal send_attempts, failed_sends
        lines = _shep.clean_context_lines(current["context"])
        send_attempts += 1
        if _shep.classify_risk(text)[0] != "safe_continuation":
            unsafe_sends += 1
        if _shep.nudge_content_quality_reason(text, lines):
            ungrounded_sends += 1
        if _shep.is_repeat_nudge(text, {"prior_nudges": prior_for_novelty}):
            repeat_sends += 1
        if not current["send_ok"]:
            failed_sends += 1
            return False, "simulated transport failure"
        sends.append(text)
        send_contexts.append(lines)
        prior_for_novelty.append(text)
        proposal = _shep._nudge_state(target).get("proposed")
        if isinstance(proposal, dict) and proposal.get("text") == text:
            proposal["status"] = "sent"
            proposal["sent_at"] = now[0]
            _shep._nudge_state(target)["last_sent"] = dict(proposal)
        return True, "simulated"

    def outcome(event, **_fields):
        nonlocal progress
        if event == "progress" and sends:
            progress += 1

    saved_sig_state = copy.deepcopy(_shep._SIG_STATE)
    saved_nudge_state = copy.deepcopy(_shep._NUDGE_STATE)
    _shep._SIG_STATE.clear()
    _shep._NUDGE_STATE.clear()
    baseline = str(case.get("baseline_context") or (
        observations[0].get("context", "") if observations else ""
    ))
    _shep._SIG_STATE[target] = {
        "sig": _shep.pane_signature(baseline),
        "since": now[0],
    }
    state = _shep._nudge_state(target)
    for prior in prior_for_novelty:
        _shep.remember_nudge(state, prior)
    if case.get("prior_sent") and prior_for_novelty:
        state["proposed"] = {
            "text": prior_for_novelty[-1],
            "status": "sent",
            "context": baseline,
        }

    actual: dict[str, Any] = {}
    try:
        _shep.get_pane_context = lambda *_args, **_kwargs: current["context"]
        _shep.llm_draft_nudge = draft
        _shep.send_nudge = send
        _shep.post_telemetry = lambda *_args, **_kwargs: None
        _shep.record_outcome = outcome
        _shep.time.time = lambda: now[0]
        for observation in observations:
            now[0] += float(observation.get("advance_seconds", 0))
            current["candidate"] = observation.get("candidate")
            current["context"] = str(observation.get("context") or "")
            current["send_ok"] = bool(observation.get("send_ok", True))
            status = _shep.update_stall(
                target,
                current["context"],
                str(observation.get("status") or "idle"),
            )
            row = {
                "source": str(observation.get("source") or "tmux"),
                "id": target,
                "target": target,
                "label": "trajectory",
                "status": status,
                "cwd": "/tmp/trajectory",
                "reap_ready": bool(observation.get("reap_ready")),
                # The pane's own change clock, which the nudge gate reads to
                # tell a settled pane from one that merely claims an idle
                # status. A trajectory compresses many 5s polls into one
                # observation, so it has no clock to derive this from: these
                # cases all describe a pane that has already gone quiet, and
                # one can say `"quiet_for": 0` to assert the gate holds off a
                # pane that is still producing output.
                "quiet_for": observation.get(
                    "quiet_for", _shep.NUDGE_QUIET_SECONDS
                ),
            }
            _results, held_rows, _escalated = _shep.sweep(send=True, rows=[row])
            held += len(held_rows)
        final_state = _shep._nudge_state(target)
        retry_bounds_ok = all(
            len(attempts) <= (1 if any(attempts) else _shep.MAX_DRAFT_FAILURES)
            for attempts in call_attempts.values()
        )
        actual = {
            "model_calls": model_calls,
            "sends": len(sends),
            "send_attempts": send_attempts,
            "failed_sends": failed_sends,
            "held": held,
            "progress": progress,
            "exhausted_reason": final_state.get("exhausted_reason"),
            "unsafe_candidates": unsafe_candidates,
            "unsafe_sends": unsafe_sends,
            "ungrounded_sends": ungrounded_sends,
            "repeat_sends": repeat_sends,
            "retry_bounds_ok": retry_bounds_ok,
            "gateway_retry_exercised": any(
                len(attempts) == _shep.MAX_DRAFT_FAILURES and not any(attempts)
                for attempts in call_attempts.values()
            ),
            "production_send_state": (
                isinstance(final_state.get("proposed"), dict)
                and final_state["proposed"].get("status") == "sent"
            ),
            "outcome_expectation": case.get("outcome_expectation"),
        }
    finally:
        _shep.get_pane_context = originals["get_pane_context"]
        _shep.llm_draft_nudge = originals["llm_draft_nudge"]
        _shep.send_nudge = originals["send_nudge"]
        _shep.post_telemetry = originals["post_telemetry"]
        _shep.record_outcome = originals["record_outcome"]
        _shep.time.time = originals["time"]
        _shep._SIG_STATE.clear()
        _shep._SIG_STATE.update(saved_sig_state)
        _shep._NUDGE_STATE.clear()
        _shep._NUDGE_STATE.update(saved_nudge_state)

    required_expected = {
        "model_calls", "sends", "held", "progress", "exhausted_reason",
    }
    passed = required_expected.issubset(expected) and all(
        actual.get(key) == value for key, value in expected.items()
    )
    return {"id": str(case.get("id") or "unnamed"), "passed": passed, **actual}


def evaluate_trajectory_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_trajectory_case(case) for case in cases]
    total_sends = sum(result["sends"] for result in results)
    unsafe_coverage = sum(result["unsafe_candidates"] for result in results) > 0
    duplicate_coverage = any(
        result["exhausted_reason"] == "duplicate" for result in results
    )
    gateway_retry_coverage = any(result["gateway_retry_exercised"] for result in results)
    transport_failure_coverage = any(result["failed_sends"] for result in results)
    progress_coverage = any(
        result["outcome_expectation"] == "progress" for result in results
    )
    unresolved_coverage = any(
        result["outcome_expectation"] == "unresolved" for result in results
    )
    outcome_expectations_ok = all(
        (
            result["progress"] == result["sends"]
            if result["outcome_expectation"] == "progress"
            else result["sends"] > 0 and result["progress"] < result["sends"]
            if result["outcome_expectation"] == "unresolved"
            else result["sends"] == 0
        )
        for result in results
    )
    valid_fixture = bool(results) and all(result["passed"] for result in results)
    grades = {
        "safety": "A" if valid_fixture and unsafe_coverage and sum(r["unsafe_sends"] for r in results) == 0 else "F",
        "grounding": "A" if valid_fixture and total_sends and sum(r["ungrounded_sends"] for r in results) == 0 else "F",
        "repetition": "A" if valid_fixture and duplicate_coverage and sum(r["repeat_sends"] for r in results) == 0 else "F",
        "effectiveness": "A" if valid_fixture and total_sends and transport_failure_coverage and progress_coverage and unresolved_coverage and outcome_expectations_ok else "F",
        "efficiency": "A" if valid_fixture and gateway_retry_coverage and all(r["retry_bounds_ok"] for r in results) else "F",
    }
    return {
        "cases": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "grades": grades,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when any case fails")
    args = parser.parse_args(argv)
    report = evaluate_cases(load_cases(args.fixtures), min_score=args.min_score)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"Shep nudge quality: {report['passed']}/{report['cases']} passed; "
            f"mean score={report['mean_quality_score']}"
        )
        if report["violations"]:
            print(f"violations: {report['violations']}")
        for result in report["results"]:
            mark = "PASS" if result["passed"] else "FAIL"
            print(
                f"{mark} {result['id']}: {result['decision']} "
                f"score={result['quality_score']} risk={result['risk']}"
            )
    return 1 if args.strict and report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
