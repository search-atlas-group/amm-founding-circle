from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.shep_events import EventLogError, append_event, read_events, validate_event_log
from scripts.shep_missions import queue_mission
from scripts.shep_phase1 import (
    adapt_mission_to_loop,
    doctor,
    record_review,
    review_status,
    set_mission_source,
    validate_coherence,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures/phase1/draft-not-run-pass-hold"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_run(
    root: Path,
    *,
    mission_id: str = "mission-1",
    state_status: str = "active",
    verification: str = "passed",
    verdict: str = "PASS WITH APPROVAL HOLD",
    source_sha: str = "a" * 40,
    owner: str = "reviewer",
    bottleneck: str = "approval",
    author: str = "agent-1",
    reviewer: str = "human-2",
) -> None:
    root.mkdir(parents=True)
    contract = root / "contract.md"
    contract.write_text("# Contract\n\nShip the bounded change.\n", encoding="utf-8")
    metadata = {
        "mission_id": mission_id,
        "status": state_status,
        "verification": verification,
        "source_sha": source_sha,
        "owner": owner,
        "bottleneck": bottleneck,
        "author": author,
        "reviewer": reviewer,
    }
    state = {
        "run_id": mission_id,
        "status": state_status,
        "current_owner_role": owner,
        "current_bottleneck": bottleneck,
        "source_sha": source_sha,
        "contract_digest": _digest(contract),
        "verification": {"last_status": verification},
    }
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "progress.md").write_text(
        "<!-- shep-phase1: " + json.dumps(metadata, sort_keys=True) + " -->\n",
        encoding="utf-8",
    )
    evaluator = dict(metadata)
    evaluator["verdict"] = verdict
    (root / "evaluator.md").write_text(
        "<!-- shep-phase1: " + json.dumps(evaluator, sort_keys=True) + " -->\n",
        encoding="utf-8",
    )


def _mission(mission_id: str = "mission-1", status: str = "review") -> dict:
    return {
        "id": mission_id,
        "goal": "Ship the bounded change",
        "mode": "fleet",
        "status": status,
        "source_sha": "a" * 40,
        "review": {
            "source_sha": "a" * 40,
            "verdict": "PASS WITH APPROVAL HOLD",
            "reviewer": "human-2",
            "author": "agent-1",
        },
    }


def _events(path: Path, mission_id: str = "mission-1") -> None:
    source_sha = "a" * 40
    for event_type, actor in (
        ("created", "shep"),
        ("approved", "human-1"),
        ("dispatch_started", "shep"),
        ("worker_completed", "agent-1"),
        ("reviewed", "human-2"),
    ):
        append_event(
            path,
            mission_id=mission_id,
            event_type=event_type,
            actor=actor,
            source_sha=source_sha,
            now="2026-08-06T12:00:00Z",
        )


def test_coherence_rejects_draft_not_run_vs_evaluator_pass_hold(tmp_path: Path) -> None:
    run_dir = tmp_path / "mission-1"
    shutil.copytree(FIXTURE_ROOT, run_dir)
    result = validate_coherence(run_dir, mission=_mission())

    assert result["ok"] is False
    assert any("evaluator verdict" in error for error in result["errors"])
    assert any("not_run" in error for error in result["errors"])


def test_coherence_accepts_matching_loop_shep_review_and_events(tmp_path: Path) -> None:
    run_dir = tmp_path / "mission-1"
    _write_run(run_dir)
    events_path = tmp_path / "events.jsonl"
    _events(events_path)

    result = validate_coherence(
        run_dir,
        mission=_mission(),
        event_path=events_path,
    )

    assert result["ok"] is True
    assert result["facts"]["source_sha"] == "a" * 40


def test_event_log_is_ordered_and_detects_a_gap(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    _events(path)

    assert [event["seq"] for event in read_events(path)] == [1, 2, 3, 4, 5]
    assert validate_event_log(path)["ok"] is True

    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2], lines[3], lines[4]]) + "\n")
    result = validate_event_log(path)
    assert result["ok"] is False
    assert any("sequence gap" in error for error in result["errors"])


def test_event_log_rejects_dispatch_before_approval_and_sha_drift(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_event(path, mission_id="mission-1", event_type="created", actor="shep")

    with pytest.raises(EventLogError, match="invalid transition"):
        append_event(
            path,
            mission_id="mission-1",
            event_type="dispatch_started",
            actor="shep",
        )

    append_event(
        path,
        mission_id="mission-1",
        event_type="approved",
        actor="human-1",
        source_sha="a" * 40,
    )
    with pytest.raises(EventLogError, match="source_sha changed"):
        append_event(
            path,
            mission_id="mission-1",
            event_type="dispatch_started",
            actor="shep",
            source_sha="b" * 40,
        )


def test_review_verdict_is_invalid_for_a_changed_source_sha(tmp_path: Path) -> None:
    missions_path = tmp_path / "missions.json"
    mission = queue_mission("Ship the bounded change", path=missions_path)
    set_mission_source(missions_path, mission["id"], "a" * 40)
    record_review(
        missions_path,
        mission["id"],
        source_sha="a" * 40,
        verdict="GO",
        reviewer="human-2",
        author="agent-1",
    )

    stored = next(item for item in doctor(missions_path)["missions"] if item["id"] == mission["id"])
    assert stored["review_status"]["fresh"] is True
    assert review_status(stored, "b" * 40)["fresh"] is False
    assert review_status(stored, "b" * 40)["reason"] == "source_sha_changed"
    changed = set_mission_source(missions_path, mission["id"], "b" * 40)
    assert changed["review"]["valid"] is False


def test_adapter_maps_shep_review_to_loop_active_state(tmp_path: Path) -> None:
    run_dir = tmp_path / "mission-1"
    _write_run(run_dir)
    view = adapt_mission_to_loop(_mission(), run_dir)

    assert view["mission_id"] == "mission-1"
    assert view["loop_status"] == "active"
    assert view["shep_status"] == "review"
    assert view["contract_dir"] == str(run_dir)


def test_adapter_does_not_map_cancelled_to_loop_complete(tmp_path: Path) -> None:
    run_dir = tmp_path / "mission-1"
    _write_run(run_dir)
    view = adapt_mission_to_loop({**_mission(), "status": "cancelled"}, run_dir)

    assert view["loop_status"] == "blocked"


def test_doctor_reports_blocked_stale_divergent_and_approval_held(tmp_path: Path) -> None:
    missions_path = tmp_path / "missions.json"
    stale = queue_mission("Stale review", path=missions_path)
    set_mission_source(missions_path, stale["id"], "a" * 40)
    record_review(
        missions_path,
        stale["id"],
        source_sha="a" * 40,
        verdict="GO",
        reviewer="human-2",
        author="agent-1",
    )
    set_mission_source(missions_path, stale["id"], "b" * 40)
    blocked = queue_mission("Blocked mission", path=missions_path)
    blocked["status"] = "blocked"
    state = json.loads(missions_path.read_text(encoding="utf-8"))
    state["missions"][1] = blocked
    missions_path.write_text(json.dumps(state), encoding="utf-8")

    runs_root = tmp_path / "runs"
    divergent_run = runs_root / "mission-divergent"
    _write_run(
        divergent_run,
        mission_id="mission-divergent",
        state_status="draft",
        verification="not_run",
        owner="planner",
        bottleneck="unknown",
    )
    divergent = queue_mission("Divergent mission", path=missions_path)
    state = json.loads(missions_path.read_text(encoding="utf-8"))
    state["missions"][2] = {
        **divergent,
        "id": "mission-divergent",
        "status": "review",
        "source_sha": "a" * 40,
        "review": _mission()["review"],
    }
    missions_path.write_text(json.dumps(state), encoding="utf-8")

    report = doctor(missions_path, runs_root=runs_root)

    assert report["ok"] is False
    assert report["counts"]["stale"] == 1
    assert report["counts"]["blocked"] == 1
    assert report["counts"]["divergent"] == 2
    assert report["counts"]["approval_held"] == 1
