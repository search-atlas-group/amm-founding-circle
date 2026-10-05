from __future__ import annotations

from scripts.shep_capacity import (
    build_plan,
    collect_cycle,
    merge_queued_sessions,
    normalize_gateway,
    normalize_missions,
    summary_payload,
)


def _score(mission, issue=None, facts=None):
    return {
        "blended": mission.get("value", 0),
        "afk_safe": mission.get("safe", True),
    }


def test_capacity_plan_refills_and_uses_a_healthy_model_pool():
    plan = build_plan(
        [{
            "mission_id": "m1",
            "goal": "Close the ready bead",
            "value": 90,
            "complexity": "routine",
            "afk_safe": True,
        }],
        [{
            "model_id": "k3",
            "lane": "kimi-gw",
            "tier": "cheap",
            "health": "available",
            "available_slots": 1,
        }],
        [],
        {"allowed": True, "reasons": []},
        {"refill_below": 2, "target_active": 1, "max_active": 2},
    )

    assert plan["summary"] == {
        "active": 0,
        "requested": 1,
        "planned": 1,
        "waiting": 0,
        "excluded": 0,
    }
    assert plan["assignments"][0]["lane"] == "kimi-gw"


def test_missions_without_afk_verdict_are_excluded():
    missions = normalize_missions(
        [{"mission": {"id": "m1", "short_goal": "Needs a human", "safe": False}}],
        _score,
    )
    assert missions[0]["complexity"] == "routine"
    plan = build_plan(
        missions,
        [{
            "model_id": "gpt-5.6-luna",
            "lane": "codex-gw",
            "tier": "standard",
            "health": "available",
            "available_slots": 1,
        }],
        [],
        {"allowed": True, "reasons": []},
        {"refill_below": 2, "target_active": 1, "max_active": 2},
    )

    assert plan["assignments"] == []
    assert plan["excluded"] == [
        {"mission_id": "m1", "reason": "not_safe_for_unattended_run"}
    ]


def test_queued_shep_missions_count_before_new_assignments():
    sessions = merge_queued_sessions(
        [],
        [{"id": "mission-queued", "status": "queued"}],
    )
    plan = build_plan(
        [{
            "mission_id": "m1",
            "goal": "A second mission",
            "value": 90,
            "complexity": "routine",
            "afk_safe": True,
        }],
        [{
            "model_id": "k3",
            "lane": "kimi-gw",
            "tier": "cheap",
            "health": "available",
            "available_slots": 1,
        }],
        sessions,
        {"allowed": True, "reasons": []},
        {"refill_below": 2, "target_active": 2, "max_active": 3},
    )

    assert plan["summary"]["active"] == 1
    assert plan["summary"]["planned"] == 1


def test_collection_uses_one_timestamp_and_fails_closed_on_source_loss():
    candidates = [
        {
            "mission": {"id": "m1", "short_goal": "Safe work", "value": 80},
            "issue": None,
            "facts": {"has_verifier": True, "worktree_ok": True},
        }
    ]

    def run_json(command, **kwargs):
        if "gw.py" in command[1]:
            return None, {"status": "unavailable", "detail": "gateway down"}
        if "herdr" in command[-2:]:
            return {"panes": []}, {"status": "ok"}
        return {"allow": True, "reasons": []}, {"status": "ok"}

    cycle = collect_cycle(
        lambda: (candidates, None),
        lambda: [],
        _score,
        run_json=run_json,
    )

    assert cycle["observed_at"] == cycle["snapshot"]["observed_at"]
    assert cycle["snapshot"]["workstation"]["allowed"] is False
    assert cycle["plan"]["assignments"] == []
    assert cycle["snapshot"]["source"]["gateway"]["status"] == "unavailable"


def test_gateway_lanes_use_explicit_tiers_and_capacity_health():
    pools = normalize_gateway({
        "lanes": [
            {
                "command": "kimi",
                "model": "k3",
                "status": "ok",
                "capacity": "ok",
            },
            {
                "command": "codex",
                "model": "gpt-5.6-luna",
                "status": "degraded",
                "capacity": "fail",
            },
        ]
    })

    assert pools[0]["tier"] == "cheap"
    assert pools[0]["available_slots"] == 1
    assert pools[1]["tier"] == "standard"
    assert pools[1]["available_slots"] == 0


def test_summary_payload_drops_unbounded_waiting_and_excluded_rows():
    cycle = {
        "schema": "mission-scheduler-cycle/v1",
        "mode": "read-only",
        "observed_at": "2026-08-07T00:00:00Z",
        "snapshot": {"source": {"gateway": {"status": "ok"}}},
        "plan": {
            "admission": {"allowed": True, "reasons": []},
            "policy": {"needs_refill": False},
            "summary": {"active": 3, "planned": 0, "waiting": 2, "excluded": 1},
            "assignments": [],
            "waiting": [{"mission_id": "m1"}, {"mission_id": "m2"}],
            "excluded": [{"mission_id": "m3"}],
        },
    }

    payload = summary_payload(cycle)

    assert payload["waiting_count"] == 2
    assert payload["excluded_count"] == 1
    assert "waiting" not in payload
    assert "excluded" not in payload
