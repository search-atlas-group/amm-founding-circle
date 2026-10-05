"""Read-only capacity planning for the canonical Shep loop.

This module owns the observation-to-plan boundary. It may inspect Shep's
mission queue, AFK suitability, Herdr, the gateway cockpit, and the local
workstation gate. It never approves, reserves, launches, or mutates a mission.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


INPUT_SCHEMA = "mission-scheduler-input/v1"
PLAN_SCHEMA = "mission-scheduler-plan/v1"
CYCLE_SCHEMA = "mission-scheduler-cycle/v1"

DEFAULT_POLICY = {
    "refill_below": 2,
    "target_active": 4,
    "max_active": 6,
}
TIER_RANK = {"cheap": 0, "standard": 1, "frontier": 2}
LANE_TIERS = {
    "kimi-gw": "cheap",
    "codex-gw": "standard",
    "claude-gw": "frontier",
    "agy-gw": "standard",
}
ACTIVE_STATUSES = {
    "active",
    "in_progress",
    "queued",
    "running",
    "starting",
    "working",
    "dispatching",
    "review",
    "approved",
}
TERMINAL_STATUSES = {"blocked", "cancelled", "completed", "done", "failed", "paused"}
HEALTHY_VALUES = {"available", "healthy", "ok", "ready", "up"}
ACTIVE_MISSION_STATUSES = {"queued", "approved", "dispatching", "running", "review"}
STATUS_MAP = {
    "active": "running",
    "busy": "running",
    "in_progress": "running",
    "working": "running",
    "starting": "starting",
    "queued": "queued",
    "dispatching": "starting",
    "approved": "queued",
    "review": "running",
    "idle": "idle",
    "blocked": "blocked",
    "done": "done",
    "completed": "completed",
    "failed": "failed",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _tier(value: Any, default: str = "standard") -> str:
    aliases = {
        "basic": "cheap",
        "economy": "cheap",
        "high": "frontier",
        "medium": "standard",
        "normal": "standard",
    }
    candidate = aliases.get(str(value or default).lower().strip(), str(value or default).lower().strip())
    return candidate if candidate in TIER_RANK else default


def _required_tier(mission: dict[str, Any]) -> str:
    required = mission.get("required_tier")
    if required:
        return _tier(required)
    complexity = str(mission.get("complexity") or "standard").lower()
    complexity = {
        "low": "cheap",
        "routine": "cheap",
        "medium": "standard",
        "high": "frontier",
    }.get(complexity, complexity)
    if complexity not in TIER_RANK:
        complexity = "standard"
    if mission.get("needs_research"):
        complexity = max(complexity, "standard", key=TIER_RANK.get)
    return complexity


def _complexity(value: Any) -> str:
    candidate = str(value or "standard").lower().strip()
    return {
        "low": "routine",
        "cheap": "routine",
        "routine": "routine",
        "medium": "standard",
        "standard": "standard",
        "normal": "standard",
        "high": "frontier",
        "frontier": "frontier",
    }.get(candidate, "standard")


def _active_session(session: dict[str, Any]) -> bool:
    if session.get("active") is True:
        return True
    return str(session.get("status") or "").lower().strip() in ACTIVE_STATUSES


def _mission_id(mission: dict[str, Any]) -> str:
    return str(mission.get("mission_id") or mission.get("id") or "unknown")


def _excluded_reason(mission: dict[str, Any]) -> str | None:
    status = str(mission.get("status", mission.get("state", "ready"))).lower()
    if status in TERMINAL_STATUSES:
        return f"mission_status_{status}"
    if mission.get("human_gate"):
        return "human_gate_required"
    if mission.get("afk_safe") is not True:
        return "not_safe_for_unattended_run"
    if mission.get("sensitive"):
        return "sensitive_mission"
    return None


def _normalize_pool(pool: dict[str, Any], default_slots: int = 1) -> dict[str, Any]:
    max_in_flight = pool.get("max_in_flight")
    in_flight = _int(pool.get("in_flight"))
    if "available_slots" in pool:
        slots = max(0, _int(pool["available_slots"]))
    elif max_in_flight is not None:
        slots = max(0, _int(max_in_flight) - in_flight)
    else:
        slots = max(0, default_slots)
    health = str(
        pool.get("health") or pool.get("status") or pool.get("capacity") or "unknown"
    ).lower()
    if pool.get("capacity") in {False, "none", "unavailable", "full"}:
        slots = 0
    return {
        "model_id": str(pool.get("model_id") or pool.get("model") or "unknown"),
        "lane": str(pool.get("lane") or pool.get("runtime") or "unknown"),
        "tier": _tier(pool.get("tier")),
        "health": health,
        "available_slots": slots,
        "target_share": _number(pool.get("target_share"), 0.0),
        "recent_share": pool.get("recent_share"),
        "recent_assignments": _int(pool.get("recent_assignments")),
    }


def _pool_is_eligible(pool: dict[str, Any], mission: dict[str, Any]) -> bool:
    allowed_tiers = mission.get("allowed_tiers")
    if isinstance(allowed_tiers, str):
        allowed_tiers = [allowed_tiers]
    return (
        pool["health"] in HEALTHY_VALUES
        and pool["available_slots"] > 0
        and TIER_RANK[pool["tier"]] >= TIER_RANK[_required_tier(mission)]
        and (not allowed_tiers or pool["tier"] in {_tier(item) for item in allowed_tiers})
        and pool["lane"] not in set(mission.get("forbidden_lanes", []))
    )


def _mission_value(mission: dict[str, Any]) -> float:
    return _number(mission.get("value", mission.get("momentum_score")))


def build_plan(
    missions: list[dict[str, Any]],
    model_pools: list[dict[str, Any]],
    active_sessions: list[dict[str, Any]],
    resources: dict[str, Any] | None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic proposal from one immutable observation."""
    settings = {**DEFAULT_POLICY, **(policy or {})}
    active = [session for session in active_sessions if _active_session(session)]
    active_count = len(active)
    admission_allowed = bool(resources and resources.get("allowed", resources.get("allow")))
    admission_reasons = [] if admission_allowed else list(
        (resources or {}).get("reasons") or ["workstation_capacity_unknown"]
    )
    pools = [_normalize_pool(pool) for pool in model_pools]
    model_active = Counter(
        str(session.get("model_id") or session.get("model") or "unknown")
        for session in active
    )
    total_recent = sum(pool["recent_assignments"] for pool in pools)
    default_target = 1 / len(pools) if pools else 0.0
    for pool in pools:
        if not pool["target_share"]:
            pool["target_share"] = default_target
        if pool["recent_share"] is None:
            pool["recent_share"] = (
                pool["recent_assignments"] / total_recent
                if total_recent
                else model_active[pool["model_id"]] / active_count
                if active_count
                else 0.0
            )
        pool["_base_recent_share"] = _number(pool["recent_share"])
        pool["_planned_assignments"] = 0
        pool["fairness_deficit"] = round(
            pool["target_share"] - pool["_base_recent_share"], 4
        )
        pool["remaining_slots"] = pool["available_slots"]

    dispatchable, excluded = [], []
    for mission in missions:
        reason = _excluded_reason(mission)
        if reason:
            excluded.append({"mission_id": _mission_id(mission), "reason": reason})
        else:
            dispatchable.append(mission)
    dispatchable.sort(key=lambda item: (-_mission_value(item), _mission_id(item)))

    refill_below = _int(settings["refill_below"])
    target_active = _int(settings["target_active"])
    max_active = _int(settings["max_active"])
    needs_refill = active_count < refill_below
    requested = max(0, target_active - active_count) if needs_refill else 0
    requested = min(requested, max(0, max_active - active_count))

    assignments: list[dict[str, Any]] = []
    waiting: list[dict[str, str]] = []
    for mission in dispatchable:
        if not needs_refill:
            waiting.append({"mission_id": _mission_id(mission), "reason": "refill_not_needed"})
            continue
        if not admission_allowed:
            waiting.append({"mission_id": _mission_id(mission), "reason": "workstation_gate"})
            continue
        if len(assignments) >= requested:
            waiting.append({"mission_id": _mission_id(mission), "reason": "target_reached"})
            continue
        eligible = [pool for pool in pools if _pool_is_eligible(pool, mission)]
        if not eligible:
            waiting.append({"mission_id": _mission_id(mission), "reason": "no_eligible_model_capacity"})
            continue
        required_rank = TIER_RANK[_required_tier(mission)]
        chosen = max(
            eligible,
            key=lambda pool: (
                pool["fairness_deficit"],
                -abs(TIER_RANK[pool["tier"]] - required_rank),
                pool["remaining_slots"],
                pool["model_id"],
            ),
        )
        chosen["remaining_slots"] -= 1
        chosen["_planned_assignments"] += 1
        planned_total = len(assignments) + 1
        base_total = sum(pool["_base_recent_share"] for pool in pools)
        fairness_total = base_total + planned_total
        for pool in pools:
            observed_share = (
                (pool["_base_recent_share"] + pool["_planned_assignments"]) / fairness_total
                if fairness_total
                else 0.0
            )
            pool["fairness_deficit"] = round(pool["target_share"] - observed_share, 4)
        assignments.append({
            "mission_id": _mission_id(mission),
            "goal": mission.get("goal") or mission.get("short_goal"),
            "model_id": chosen["model_id"],
            "lane": chosen["lane"],
            "required_tier": _required_tier(mission),
            "reason": "best_fit_with_fairness_deficit",
        })

    return {
        "schema": PLAN_SCHEMA,
        "mode": "read-only",
        "observed_at": settings.get("observed_at"),
        "admission": {"allowed": admission_allowed, "reasons": admission_reasons},
        "policy": {
            "refill_below": refill_below,
            "target_active": target_active,
            "max_active": max_active,
            "needs_refill": needs_refill,
        },
        "summary": {
            "active": active_count,
            "requested": requested,
            "planned": len(assignments),
            "waiting": len(waiting),
            "excluded": len(excluded),
        },
        "capacity": {"model_pools": [
            {key: value for key, value in pool.items() if not key.startswith("_")}
            for pool in pools
        ]},
        "assignments": assignments,
        "waiting": waiting,
        "excluded": excluded,
    }


def normalize_gateway(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    lanes = snapshot.get("lanes", snapshot.get("model_pools", []))
    if isinstance(lanes, dict):
        lanes = [dict(value, lane=key) for key, value in lanes.items()]
    pools = []
    for lane in lanes if isinstance(lanes, list) else []:
        row = dict(lane)
        name = str(row.get("command") or row.get("lane") or "unknown")
        name = name if name.endswith("-gw") else f"{name}-gw"
        status = str(row.get("status") or "unknown").lower()
        capacity = str(row.get("capacity") or "unknown").lower()
        row.update({
            "lane": name,
            "model_id": row.get("model_id") or row.get("model"),
            "tier": row.get("tier") or LANE_TIERS.get(name, "standard"),
            "health": "available" if status in HEALTHY_VALUES and capacity in HEALTHY_VALUES else status,
        })
        if row["health"] not in HEALTHY_VALUES and "available_slots" not in row:
            row["available_slots"] = 0
        pools.append(_normalize_pool(row))
    return pools


def normalize_sessions(data: Any, pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        rows = data.get("panes", data.get("sessions", data.get("items", [])))
    else:
        rows = data
    if not isinstance(rows, list):
        return []
    models_by_lane = {pool["lane"]: pool["model_id"] for pool in pools}
    normalized = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        text = " ".join(str(row.get(key) or "") for key in ("lane", "agent", "runtime", "label", "command")).lower()
        lane = next((f"{name}-gw" for name in ("agy", "claude", "codex", "kimi") if name in text), None)
        status = STATUS_MAP.get(str(row.get("status") or row.get("agent_status") or "unknown").lower(), "unknown")
        session_id = str(row.get("session_id") or row.get("id") or row.get("pane_id") or row.get("label") or f"herdr-{index}")
        normalized_row = {"session_id": session_id, "status": status}
        if lane:
            normalized_row["lane"] = lane
            if lane in models_by_lane:
                normalized_row["model_id"] = models_by_lane[lane]
        mission_id = row.get("mission_id")
        label = str(row.get("label") or row.get("session_label") or "")
        if mission_id:
            normalized_row["mission_id"] = str(mission_id)
        elif label.startswith("mission-"):
            normalized_row["mission_id"] = label
        normalized.append(normalized_row)
    return normalized


def merge_queued_sessions(
    sessions: list[dict[str, Any]], queued_missions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    observed_ids = {
        str(row.get("mission_id"))
        for row in sessions
        if row.get("mission_id")
    }
    merged = list(sessions)
    for mission in queued_missions:
        if not isinstance(mission, dict):
            continue
        mission_id = str(mission.get("id") or mission.get("mission_id") or "")
        status = str(mission.get("status") or "").lower()
        if not mission_id or status not in ACTIVE_MISSION_STATUSES or mission_id in observed_ids:
            continue
        merged.append({
            "session_id": f"shep-mission:{mission_id}",
            "mission_id": mission_id,
            "status": STATUS_MAP.get(status, status),
            "model_id": mission.get("model_id"),
        })
        observed_ids.add(mission_id)
    return merged


def normalize_missions(
    candidates: list[dict[str, Any]],
    score_mission: Callable[[dict[str, Any], Any, Any], dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = []
    for candidate in candidates:
        mission = dict(candidate.get("mission") or {})
        mission_id = str(mission.get("id") or mission.get("mission_id") or "").strip()
        if not mission_id:
            continue
        try:
            verdict = score_mission(
                mission,
                issue=candidate.get("issue"),
                facts=candidate.get("facts"),
            )
        except Exception as exc:  # noqa: BLE001 - fail closed for this candidate
            verdict = {"blended": 0, "afk_safe": False, "error": str(exc)}
        complexity = _complexity(
            mission.get("complexity")
            or mission.get("required_tier")
            or ("standard" if mission.get("needs_research") else "routine")
        )
        row = {
            "mission_id": mission_id,
            "goal": str(mission.get("goal") or mission.get("short_goal") or mission.get("next_step") or ""),
            "status": str(mission.get("status") or "ready").lower(),
            "value": verdict.get("blended", mission.get("momentum_score", 0)),
            "complexity": complexity,
            "needs_research": bool(mission.get("needs_research")),
            "human_gate": bool(mission.get("human_gate", False)),
            "afk_safe": bool(verdict.get("afk_safe", False)),
            "sensitive": bool(mission.get("sensitive", False)),
        }
        if mission.get("required_tier"):
            row["required_tier"] = _tier(mission["required_tier"])
        for key in ("allowed_tiers", "forbidden_lanes"):
            if isinstance(mission.get(key), list):
                row[key] = list(mission[key])
        normalized.append(row)
    return normalized


def _run_json(
    command: list[str], *, timeout: int = 30, allow_nonzero: bool = False
) -> tuple[Any | None, dict[str, Any]]:
    # RETRY-LOOP-SAFETY: bounded by design — do not add a naive retry handler here.
    #   concurrency: the Shep control loop owns one singleton lock per pass.
    #   attempts: one attempt per source per pass; the scheduled pass is the retry.
    #   backoff: no inline sleep; the next five-minute pass retries unavailable sources.
    #   why no retry handler: a source can consume the whole loop timeout while sleeping.
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, {"status": "unavailable", "detail": type(exc).__name__}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, {
            "status": "unavailable",
            "detail": f"command returned no valid JSON (exit {result.returncode})",
        }
    return value, {
        "status": "ok" if result.returncode == 0 or allow_nonzero else "unavailable",
        "exit_code": result.returncode,
    }


def _source_script(env_name: str, default: str) -> Path:
    return Path(os.environ.get(env_name, default)).expanduser()


def collect_cycle(
    candidate_source: Callable[[], tuple[list[dict[str, Any]], str | None]],
    mission_source: Callable[[], list[dict[str, Any]]],
    score_mission: Callable[[dict[str, Any], Any, Any], dict[str, Any]],
    *,
    policy: dict[str, int] | None = None,
    herdr_ctl: Path | None = None,
    run_json: Callable[..., tuple[Any | None, dict[str, Any]]] = _run_json,
) -> dict[str, Any]:
    candidates, candidate_error = candidate_source()
    try:
        queued = mission_source()
        queue_meta = {"status": "ok"}
    except (OSError, RuntimeError, ValueError) as exc:
        queued = []
        queue_meta = {"status": "unavailable", "detail": str(exc)}

    gateway_script = _source_script(
        "AI_GATEWAY_GW_SCRIPT",
        "/Users/developer/Sync/searchatlas-eng/forge-repos/org-internal/"
        "agentic-engineering/stack/gw/scripts/gw.py",
    )
    resources_script = _source_script(
        "WORKSTATION_RESOURCE_GATE",
        "/Users/developer/Sync/searchatlas-eng/forge-repos/org-internal/"
        "agentic-engineering/stack/enforcement/workstation_resource_gate.py",
    )
    herdr_script = herdr_ctl or Path(
        os.environ.get(
            "SHEP_HERDR_CTL",
            str(Path.home() / "Sync/.agent-config/skills-shared/herdr/scripts/herdr_ctl.py"),
        )
    ).expanduser()
    gateway, gateway_meta = run_json([sys.executable, str(gateway_script), "--dump-json"])
    herdr, herdr_meta = run_json([sys.executable, str(herdr_script), "session", "list"])
    resources, resources_meta = run_json(
        [sys.executable, str(resources_script)], allow_nonzero=True
    )

    pools = normalize_gateway(gateway or {})
    sessions = merge_queued_sessions(normalize_sessions(herdr, pools), queued)
    source = {
        "missions": {"status": "ok" if not candidate_error else "unavailable", "detail": candidate_error},
        "shep_queue": queue_meta,
        "gateway": gateway_meta,
        "herdr": herdr_meta,
        "workstation": resources_meta,
    }
    unavailable = [name for name, info in source.items() if info.get("status") != "ok"]
    workstation = resources if isinstance(resources, dict) else {
        "allowed": False,
        "reasons": ["workstation_snapshot_unavailable"],
    }
    if unavailable:
        workstation = dict(workstation)
        workstation["allowed"] = False
        workstation["reasons"] = list(workstation.get("reasons") or []) + [
            f"{name}_snapshot_unavailable" for name in unavailable
        ]
    timestamp = _now()
    settings = {**DEFAULT_POLICY, **(policy or {})}
    snapshot = {
        "schema": INPUT_SCHEMA,
        "observed_at": timestamp,
        "policy": settings,
        "source": source,
        "missions": normalize_missions(candidates, score_mission),
        "capacity": {"model_pools": pools},
        "active_sessions": sessions,
        "workstation": {
            "allowed": bool(workstation.get("allowed", workstation.get("allow"))),
            "reasons": [str(reason) for reason in workstation.get("reasons") or []],
            **{
                key: workstation[key]
                for key in ("free_disk_gib", "swap_used_gib", "rmux_sessions")
                if key in workstation
            },
        },
    }
    plan = build_plan(
        snapshot["missions"],
        pools,
        sessions,
        snapshot["workstation"],
        {**settings, "observed_at": timestamp},
    )
    return {
        "schema": CYCLE_SCHEMA,
        "mode": "read-only",
        "observed_at": timestamp,
        "snapshot": snapshot,
        "plan": plan,
    }


def render_text(cycle: dict[str, Any]) -> str:
    summary = cycle["plan"]["summary"]
    lines = [
        "mode=read-only "
        f"active={summary['active']} planned={summary['planned']} "
        f"waiting={summary['waiting']} excluded={summary['excluded']}",
    ]
    for assignment in cycle["plan"]["assignments"]:
        lines.append(
            f"PLAN {assignment['mission_id']} -> "
            f"{assignment['lane']}/{assignment['model_id']} ({assignment['required_tier']})"
        )
    if not cycle["plan"]["admission"]["allowed"]:
        lines.append("admission=blocked: " + "; ".join(cycle["plan"]["admission"]["reasons"]))
    return "\n".join(lines)


def summary_payload(cycle: dict[str, Any]) -> dict[str, Any]:
    """Return bounded telemetry for the recurring control-loop log."""
    plan = cycle["plan"]
    return {
        "schema": cycle["schema"],
        "mode": cycle["mode"],
        "observed_at": cycle["observed_at"],
        "source": cycle["snapshot"]["source"],
        "admission": plan["admission"],
        "policy": plan["policy"],
        "summary": plan["summary"],
        "assignments": plan["assignments"],
        "excluded_count": len(plan["excluded"]),
        "waiting_count": len(plan["waiting"]),
    }
