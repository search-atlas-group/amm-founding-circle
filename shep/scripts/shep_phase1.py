"""Shep v1 Phase 1 safety gates.

This module is intentionally read/write-light.  Loop 1 remains the owner of
the contract files; Shep reads them, records exact-SHA review state, and fails
closed when the evidence does not agree.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    from scripts.shep_events import validate_event_log
    from scripts.shep_missions import _atomic_write, _locked, _read
except ImportError:  # pragma: no cover - direct script execution
    from shep_events import validate_event_log
    from shep_missions import _atomic_write, _locked, _read


PASS_VERDICTS = {"go", "pass", "passed", "pass_with_approval_hold"}
APPROVAL_HOLD_VERDICTS = {"pass_with_approval_hold", "approval_hold"}
SHEP_TO_LOOP_STATUS = {
    "queued": "draft",
    "approved": "active",
    "dispatching": "active",
    "running": "active",
    "review": "active",
    "landed": "complete",
    "failed": "blocked",
    "cancelled": "blocked",
    "blocked": "blocked",
}
MARKER_RE = re.compile(r"<!--\s*shep-phase1:\s*(\{.*?\})\s*-->", re.DOTALL)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _marker(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = MARKER_RE.search(text)
    if match:
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} has an invalid Phase 1 marker: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path.name} Phase 1 marker must be an object")
        return value
    return _prose_facts(path.name, text)


def _prose_facts(name: str, text: str) -> dict:
    """Read the old evaluator prose well enough to reject known drift."""
    facts: dict[str, object] = {}
    lowered = text.lower()
    if name == "evaluator.md":
        if "pass with approval hold" in lowered:
            facts["verdict"] = "pass_with_approval_hold"
        else:
            match = re.search(r"verdict\s*:\s*([^\n]+)", lowered)
            if match:
                facts["verdict"] = match.group(1).strip()
    if "not_run" in lowered:
        facts["verification"] = "not_run"
    if "pass" in lowered and "verification" in lowered:
        facts.setdefault("verification", "passed")
    return facts


def _normalize(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def review_status(mission: dict, current_source_sha: str | None = None) -> dict:
    review = mission.get("review")
    if not isinstance(review, dict):
        return {"fresh": False, "valid": False, "reason": "review_missing"}
    expected = current_source_sha or mission.get("source_sha")
    reviewed = review.get("source_sha")
    if not expected:
        return {"fresh": False, "valid": False, "reason": "source_sha_missing"}
    if reviewed != expected:
        return {
            "fresh": False,
            "valid": False,
            "reason": "source_sha_changed",
            "review_source_sha": reviewed,
            "current_source_sha": expected,
        }
    verdict = _normalize(review.get("verdict"))
    valid = bool(review.get("valid", True)) and verdict in PASS_VERDICTS
    return {
        "fresh": True,
        "valid": valid,
        "reason": "fresh" if valid else "verdict_not_pass",
        "review_source_sha": reviewed,
        "current_source_sha": expected,
    }


def set_mission_source(path: str | Path, mission_id: str, source_sha: str) -> dict:
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", source_sha):
        raise ValueError("source_sha must be a hexadecimal commit SHA")
    destination = Path(path).expanduser()
    with _locked(destination):
        state = _read(destination)
        mission = next((item for item in state["missions"] if item.get("id") == mission_id), None)
        if mission is None:
            raise KeyError(f"unknown mission: {mission_id}")
        review = mission.get("review")
        if isinstance(review, dict) and review.get("source_sha") != source_sha.lower():
            review["valid"] = False
            review["invalidated_at"] = time.time()
        mission["source_sha"] = source_sha.lower()
        mission["updated_at"] = time.time()
        mission["revision"] = int(mission.get("revision", 0)) + 1
        _atomic_write(destination, state)
        return dict(mission)


def record_review(
    path: str | Path,
    mission_id: str,
    *,
    source_sha: str,
    verdict: str,
    reviewer: str,
    author: str,
    now: float | None = None,
) -> dict:
    if reviewer.strip().lower() == author.strip().lower():
        raise ValueError("reviewer must be different from author")
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", source_sha):
        raise ValueError("source_sha must be a hexadecimal commit SHA")
    destination = Path(path).expanduser()
    with _locked(destination):
        state = _read(destination)
        mission = next((item for item in state["missions"] if item.get("id") == mission_id), None)
        if mission is None:
            raise KeyError(f"unknown mission: {mission_id}")
        current_source = mission.get("source_sha")
        if not current_source:
            raise ValueError("review requires a current mission source_sha")
        if current_source and current_source.lower() != source_sha.lower():
            raise ValueError("review source_sha must match the mission current source_sha")
        mission["review"] = {
            "source_sha": source_sha.lower(),
            "verdict": verdict.strip(),
            "reviewer": reviewer.strip(),
            "author": author.strip(),
            "valid": True,
            "recorded_at": time.time() if now is None else float(now),
        }
        mission["status"] = "review"
        mission["updated_at"] = time.time() if now is None else float(now)
        mission["revision"] = int(mission.get("revision", 0)) + 1
        _atomic_write(destination, state)
        return dict(mission)


def adapt_mission_to_loop(mission: dict, run_dir: str | Path) -> dict:
    directory = Path(run_dir).expanduser().resolve()
    state_path = directory / "state.json"
    state = _read_json(state_path)
    mission_id = mission.get("id")
    if state.get("run_id") != mission_id:
        raise ValueError(
            f"Loop 1 run_id {state.get('run_id')!r} does not match mission {mission_id!r}"
        )
    shep_status = str(mission.get("status", ""))
    loop_status = SHEP_TO_LOOP_STATUS.get(shep_status)
    if loop_status is None:
        raise ValueError(f"unsupported Shep mission status: {shep_status}")
    return {
        "schema": "shep-loop-adapter/v1",
        "mission_id": mission_id,
        "run_id": state["run_id"],
        "shep_status": shep_status,
        "loop_status": loop_status,
        "source_sha": mission.get("source_sha") or state.get("source_sha"),
        "contract_dir": str(directory),
    }


def check_loop_contract(run_dir: str | Path) -> dict:
    directory = Path(run_dir).expanduser().resolve()
    validator = Path(__file__).resolve().parents[2] / "loop-contract" / "agent_loop.py"
    result = subprocess.run(
        [sys.executable, str(validator), "check", str(directory), "--quiet"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def validate_coherence(
    run_dir: str | Path,
    *,
    mission: dict | None = None,
    event_path: str | Path | None = None,
) -> dict:
    directory = Path(run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    facts: dict[str, object] = {}
    state_path = directory / "state.json"
    contract_path = directory / "contract.md"
    progress_path = directory / "progress.md"
    evaluator_path = directory / "evaluator.md"
    required = (state_path, contract_path, progress_path, evaluator_path)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        return {"ok": False, "errors": ["missing required files: " + ", ".join(missing)], "warnings": [], "facts": {}}
    try:
        state = _read_json(state_path)
        progress = _marker(progress_path)
        evaluator = _marker(evaluator_path)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "facts": {}}

    run_id = state.get("run_id")
    source_sha = state.get("source_sha")
    verification = state.get("verification")
    if not isinstance(verification, dict):
        errors.append("state.json verification must be an object")
        verification = {}
    state_verification = _normalize(verification.get("last_status"))
    state_status = _normalize(state.get("status"))
    facts.update({"mission_id": run_id, "source_sha": source_sha, "status": state_status})
    if not isinstance(run_id, str) or not run_id:
        errors.append("state.json run_id is missing")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{7,64}", source_sha):
        errors.append("state.json source_sha must be a lowercase hexadecimal commit SHA")
    expected_digest = _sha256(contract_path)
    if state.get("contract_digest") != expected_digest:
        errors.append("contract digest does not match state.json contract_digest")

    for source_name, metadata in (("progress.md", progress), ("evaluator.md", evaluator)):
        if metadata.get("mission_id") and metadata.get("mission_id") != run_id:
            errors.append(f"{source_name} mission_id disagrees with state.json run_id")
        state_values = {
            "status": state_status,
            "verification": state_verification,
            "source_sha": source_sha,
            "owner": state.get("current_owner_role"),
            "bottleneck": state.get("current_bottleneck"),
        }
        for key in ("status", "verification", "source_sha", "owner", "bottleneck"):
            if metadata.get(key) and state_values[key] != metadata.get(key):
                errors.append(
                    f"{source_name} {key} disagrees with state.json: "
                    f"{state_values[key]} vs {metadata.get(key)}"
                )
    verdict = _normalize(evaluator.get("verdict"))
    if verdict in PASS_VERDICTS and state_verification in {"", "not_run", "pending", "failed"}:
        errors.append(f"evaluator verdict {verdict} conflicts with verification {state_verification or 'missing'}")
    if verdict in APPROVAL_HOLD_VERDICTS and state_status in {"draft", "queued"}:
        errors.append(f"evaluator verdict {verdict} conflicts with Loop status {state_status}")
    author = evaluator.get("author") or state.get("author")
    reviewer = evaluator.get("reviewer") or state.get("reviewer")
    if author and reviewer and str(author).strip().lower() == str(reviewer).strip().lower():
        errors.append("evaluator reviewer must be different from generator author")
    if mission is not None:
        if mission.get("id") != run_id:
            errors.append("Shep mission id disagrees with Loop 1 run_id")
        mission_source = mission.get("source_sha")
        if mission_source and mission_source != source_sha:
            errors.append("Shep mission source_sha disagrees with state.json source_sha")
        review = mission.get("review")
        if isinstance(review, dict) and review.get("source_sha") != source_sha:
            errors.append("review verdict is stale for the current source_sha")
        if isinstance(review, dict):
            review_author = str(review.get("author", "")).strip()
            review_reviewer = str(review.get("reviewer", "")).strip()
            if not review_author or not review_reviewer:
                errors.append("review verdict must name both author and reviewer")
            elif review_author.lower() == review_reviewer.lower():
                errors.append("review reviewer must be different from author")
        shep_status = str(mission.get("status", ""))
        expected_loop_status = SHEP_TO_LOOP_STATUS.get(shep_status)
        if expected_loop_status and expected_loop_status != state_status:
            errors.append(f"Shep status {shep_status} disagrees with Loop status {state_status}")
        customer_facing = bool(mission.get("customer_facing"))
        if customer_facing and mission.get("outcome_claim") and not mission.get("measurement_ref"):
            errors.append("customer-facing outcome claim has no Atlas measurement reference")
        if shep_status in {"review", "landed"}:
            if verdict not in PASS_VERDICTS:
                errors.append("review or landed mission has no passing evaluator verdict")
            if not author or not reviewer:
                errors.append("review or landed mission has no independent evaluator identity")

    if event_path is None:
        errors.append("event log path is required for coherence validation")
    else:
        event_report = validate_event_log(event_path, mission_id=run_id)
        errors.extend(event_report["errors"])
        events = event_report["events"]
        approval_index = next((index for index, event in enumerate(events) if event.get("event_type") == "approved"), None)
        dispatch_index = next((index for index, event in enumerate(events) if event.get("event_type") == "dispatch_started"), None)
        if dispatch_index is not None and approval_index is None:
            errors.append("dispatch_started event has no human approval event")
        elif approval_index is not None and dispatch_index is not None and approval_index > dispatch_index:
            errors.append("human approval happened after dispatch")
        if source_sha:
            for event in events:
                if event.get("event_type") in {"worker_completed", "reviewed", "landed"} and event.get("source_sha") != source_sha:
                    errors.append(f"event {event.get('event_type')} has a stale source_sha")
        facts["event_count"] = len(events)
    return {"ok": not errors, "errors": errors, "warnings": warnings, "facts": facts}


def doctor(
    missions_path: str | Path,
    *,
    runs_root: str | Path | None = None,
    event_path: str | Path | None = None,
) -> dict:
    destination = Path(missions_path).expanduser()
    state = _read(destination)
    missions: list[dict] = []
    counts = {"blocked": 0, "stale": 0, "divergent": 0, "approval_held": 0}
    for original in state["missions"]:
        item = dict(original)
        review = review_status(item)
        item["review_status"] = review
        if original.get("status") == "blocked":
            counts["blocked"] += 1
            item.setdefault("issues", []).append("blocked")
        if review["reason"] == "source_sha_changed":
            counts["stale"] += 1
            item.setdefault("issues", []).append("stale_review")
        verdict = _normalize((original.get("review") or {}).get("verdict"))
        if verdict in APPROVAL_HOLD_VERDICTS:
            counts["approval_held"] += 1
            item.setdefault("issues", []).append("approval_held")
        if runs_root is not None:
            run_dir = Path(runs_root).expanduser() / str(original.get("id"))
            if run_dir.is_dir():
                coherence = validate_coherence(
                    run_dir,
                    mission=original,
                    event_path=event_path,
                )
                item["coherence"] = coherence
                if not coherence["ok"]:
                    counts["divergent"] += 1
                    item.setdefault("issues", []).append("divergent")
            elif original.get("status") in {"dispatching", "running", "review", "landed"}:
                counts["divergent"] += 1
                item.setdefault("issues", []).append("loop_run_missing")
        missions.append(item)
    return {
        "schema": "shep-doctor/v1",
        "ok": not any(counts.values()),
        "counts": counts,
        "missions": missions,
    }
