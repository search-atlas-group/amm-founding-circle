"""Append-only lifecycle events for Shep Phase 1.

The event log is deliberately boring: one JSON object per line, a global
sequence, and a per-mission sequence.  A damaged or edited log fails closed.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import uuid
from pathlib import Path


EVENT_SCHEMA = "shep-events/v1"
EVENT_TYPES = {
    "created",
    "approved",
    "dispatch_started",
    "worker_completed",
    "reviewed",
    "landed",
    "blocked",
    "failed",
    "cancelled",
}
REQUIRES_SOURCE_SHA = {"worker_completed", "reviewed", "landed"}
ALLOWED_NEXT = {
    None: {"created"},
    "created": {"approved", "blocked", "cancelled", "failed"},
    "approved": {"dispatch_started", "blocked", "cancelled", "failed"},
    "dispatch_started": {"worker_completed", "blocked", "cancelled", "failed"},
    "worker_completed": {"reviewed", "blocked", "failed"},
    "reviewed": {"landed", "blocked", "failed"},
    "landed": set(),
    "blocked": set(),
    "failed": set(),
    "cancelled": set(),
}


class EventLogError(RuntimeError):
    """Raised when the append-only log cannot be safely read or extended."""


def _timestamp(value: str | None) -> str:
    if value is not None:
        return value
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _payload_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _event_digest(event: dict) -> str:
    body = {key: value for key, value in event.items() if key != "event_digest"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@contextlib.contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    lock = path.with_name(f"{path.name}.lock")
    handle = open(lock, "a+", encoding="utf-8")
    try:
        os.chmod(lock, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _read_unlocked(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EventLogError(f"event log is unreadable: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise EventLogError(f"event log has a blank line at {line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EventLogError(
                f"event log has invalid JSON at line {line_number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise EventLogError(f"event log line {line_number} is not an object")
        events.append(value)
    return events


def read_events(path: str | os.PathLike[str]) -> list[dict]:
    destination = Path(path).expanduser()
    with _locked(destination):
        return _read_unlocked(destination)


def append_event(
    path: str | os.PathLike[str],
    *,
    mission_id: str,
    event_type: str,
    actor: str,
    source_sha: str | None = None,
    payload: object | None = None,
    event_id: str | None = None,
    now: str | None = None,
) -> dict:
    if not mission_id.strip():
        raise ValueError("mission_id must be non-empty")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unsupported event type: {event_type}")
    if not actor.strip():
        raise ValueError("actor must be non-empty")
    if event_type in REQUIRES_SOURCE_SHA and not source_sha:
        raise ValueError(f"{event_type} requires source_sha")
    if source_sha and not re.fullmatch(r"[0-9a-fA-F]{7,64}", source_sha):
        raise ValueError("source_sha must be a hexadecimal commit SHA")

    destination = Path(path).expanduser()
    event_id = event_id or f"event-{uuid.uuid4().hex}"
    value = payload if payload is not None else {}
    with _locked(destination):
        events = _read_unlocked(destination)
        for existing in events:
            if existing.get("event_id") == event_id:
                candidate = {
                    "schema": EVENT_SCHEMA,
                    "event_id": event_id,
                    "mission_id": mission_id,
                    "event_type": event_type,
                    "actor": actor,
                    "source_sha": source_sha,
                    "payload": value,
                    "payload_digest": _payload_digest(value),
                }
                if all(existing.get(key) == item for key, item in candidate.items()):
                    return existing
                raise EventLogError(f"event_id replay has different content: {event_id}")
        mission_events = [item for item in events if item.get("mission_id") == mission_id]
        previous_type = mission_events[-1].get("event_type") if mission_events else None
        if event_type not in ALLOWED_NEXT.get(previous_type, set()):
            raise EventLogError(
                f"invalid transition for {mission_id}: "
                f"{previous_type or 'start'} -> {event_type}"
            )
        previous_shas = {
            item.get("source_sha")
            for item in mission_events
            if item.get("source_sha")
        }
        if previous_shas and source_sha and source_sha not in previous_shas:
            raise EventLogError(
                f"source_sha changed within mission {mission_id}: "
                f"{sorted(previous_shas)[0]} -> {source_sha}"
            )
        event = {
            "schema": EVENT_SCHEMA,
            "seq": len(events) + 1,
            "mission_seq": len(mission_events) + 1,
            "event_id": event_id,
            "mission_id": mission_id,
            "event_type": event_type,
            "actor": actor,
            "source_sha": source_sha,
            "payload": value,
            "payload_digest": _payload_digest(value),
            "created_at": _timestamp(now),
        }
        event["previous_digest"] = events[-1].get("event_digest") if events else None
        event["event_digest"] = _event_digest(event)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(destination.parent, 0o700)
        with destination.open("a", encoding="utf-8") as handle:
            os.chmod(destination, 0o600)
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return event


def validate_event_log(
    path: str | os.PathLike[str], *, mission_id: str | None = None
) -> dict:
    destination = Path(path).expanduser()
    errors: list[str] = []
    try:
        events = read_events(destination)
    except (EventLogError, OSError) as exc:
        return {"ok": False, "errors": [str(exc)], "events": []}

    seen_ids: set[str] = set()
    mission_sequences: dict[str, int] = {}
    mission_last_types: dict[str, str | None] = {}
    mission_source_shas: dict[str, str] = {}
    previous_digest: str | None = None
    for expected_seq, event in enumerate(events, start=1):
        if event.get("schema") != EVENT_SCHEMA:
            errors.append(f"event {expected_seq} has unsupported schema")
        if event.get("seq") != expected_seq:
            errors.append(
                f"event sequence gap at position {expected_seq}: got {event.get('seq')}"
            )
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id in seen_ids:
            errors.append(f"duplicate or missing event_id at sequence {expected_seq}")
        else:
            seen_ids.add(event_id)
        current_mission = event.get("mission_id")
        expected_mission_seq = mission_sequences.get(current_mission, 0) + 1
        if event.get("mission_seq") != expected_mission_seq:
            errors.append(
                f"mission sequence gap for {current_mission}: "
                f"got {event.get('mission_seq')}, expected {expected_mission_seq}"
            )
        mission_sequences[current_mission] = expected_mission_seq
        if event.get("event_type") not in EVENT_TYPES:
            errors.append(f"unsupported event type at sequence {expected_seq}")
        event_type = event.get("event_type")
        if event_type in REQUIRES_SOURCE_SHA and not event.get("source_sha"):
            errors.append(f"missing source_sha at sequence {expected_seq}")
        if event.get("source_sha") and not re.fullmatch(
            r"[0-9a-fA-F]{7,64}", event["source_sha"]
        ):
            errors.append(f"invalid source_sha at sequence {expected_seq}")
        previous_type = mission_last_types.get(current_mission)
        if event_type not in ALLOWED_NEXT.get(previous_type, set()):
            errors.append(
                f"invalid transition for {current_mission}: "
                f"{previous_type or 'start'} -> {event_type}"
            )
        mission_last_types[current_mission] = event_type
        source_sha = event.get("source_sha")
        if source_sha:
            previous_sha = mission_source_shas.get(current_mission)
            if previous_sha and previous_sha != source_sha:
                errors.append(
                    f"source_sha changed within mission {current_mission}: "
                    f"{previous_sha} -> {source_sha}"
                )
            mission_source_shas[current_mission] = source_sha
        payload = event.get("payload")
        if event.get("payload_digest") != _payload_digest(payload):
            errors.append(f"payload digest mismatch at sequence {expected_seq}")
        if event.get("previous_digest") != previous_digest:
            errors.append(f"event digest chain mismatch at sequence {expected_seq}")
        if event.get("event_digest") != _event_digest(event):
            errors.append(f"event digest mismatch at sequence {expected_seq}")
        previous_digest = event.get("event_digest")

    selected = events
    if mission_id is not None:
        selected = [event for event in events if event.get("mission_id") == mission_id]
        if not selected:
            errors.append(f"no events found for mission {mission_id}")
    return {"ok": not errors, "errors": errors, "events": selected}
