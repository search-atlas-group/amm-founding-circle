#!/usr/bin/env python3
"""Append-only, privacy-bounded action receipts for Shep.

This ledger is deliberately separate from ``shep_nudge_outcomes``: outcomes
measure drafts, while this file answers the operator's audit question of what
Shep actually attempted.  It never accepts pane transcripts.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - supported platforms have fcntl
    fcntl = None


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER = REPO_ROOT / "reports/data/shep-actions/events.jsonl"
MAX_TEXT = 280
MAX_FIELD = 160
_ACTIONS = frozenset({"nudge", "reap", "answer"})
_MODES = frozenset({"auto", "manual"})
_LIFECYCLES = frozenset(
    {"candidate", "intent", "sent", "failed", "refused", "reaped", "answered"}
)
_SECRET_RE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{8,}|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+)"
)
_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class ActionLogError(RuntimeError):
    """Raised when a required audit receipt cannot be persisted."""


def ledger_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path or os.environ.get("SHEP_ACTION_LOG") or DEFAULT_LEDGER).expanduser()


def _clean(value: object, limit: int = MAX_FIELD) -> str:
    text = _ANSI_RE.sub("", "" if value is None else str(value))
    text = _SECRET_RE.sub("[REDACTED]", text)
    text = " ".join(text.replace("\x00", "").split())
    return text[:limit]


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()


def context_hash(value: object) -> str:
    """Return a stable full SHA-256 context/policy hash, never the context."""
    return _hash(value)


def _metadata(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key in ("session", "workspace", "repository", "pane", "source"):
        if key not in value or value[key] is None:
            continue
        item = _clean(value[key])
        # Paths are useful to an operator but full paths can expose unrelated
        # user data; retain only the final component for workspace/repository.
        if key in {"workspace", "repository"}:
            item = Path(item.rstrip("/")).name or item
        out[key] = item
    return out


@contextlib.contextmanager
def _locked(path: Path):
    if fcntl is None:
        raise ActionLogError("platform has no file-lock primitive")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(path, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    except OSError as exc:
        raise ActionLogError(f"could not lock action ledger: {exc}") from exc
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def append(
    action: str,
    lifecycle: str,
    *,
    mode: str = "auto",
    target: object = None,
    metadata: dict[str, object] | None = None,
    policy: object = "",
    context: object = "",
    reason: object = "",
    text: object = None,
    result: object = "",
    error: object = "",
    path: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Append one receipt, or raise ``ActionLogError`` before any action."""
    if action not in _ACTIONS:
        raise ValueError(f"invalid action: {action}")
    if lifecycle not in _LIFECYCLES:
        raise ValueError(f"invalid lifecycle: {lifecycle}")
    if mode not in _MODES:
        raise ValueError(f"invalid mode: {mode}")
    destination = ledger_path(path)
    event: dict[str, object] = {
        "event_id": uuid.uuid4().hex,
        "ts": time.time(),
        "action": action,
        "lifecycle": lifecycle,
        "mode": mode,
        "target": _clean(target),
        "metadata": _metadata(metadata),
        "policy_hash": _hash(policy),
        "context_hash": _hash(context),
        "reason": _clean(reason),
        "reason_hash": _hash(reason),
        "result": _clean(result),
    }
    if text is not None:
        event["text"] = _clean(text, MAX_TEXT)
        event["text_hash"] = _hash(text)
    if error:
        event["error"] = _clean(error)
    line = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
    lock_path = destination.with_name(destination.name + ".lock")
    try:
        with _locked(lock_path):
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(destination.parent, 0o700)
            fd = os.open(destination, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.chmod(destination, 0o600)
                written = os.write(fd, line)
                if written != len(line):
                    raise ActionLogError("short action-ledger write")
            finally:
                os.close(fd)
    except ActionLogError:
        raise
    except OSError as exc:
        raise ActionLogError(f"could not append action ledger: {exc}") from exc
    return event


def load(path: str | os.PathLike[str] | None = None) -> list[dict[str, object]]:
    destination = ledger_path(path)
    if not destination.exists():
        return []
    events: list[dict[str, object]] = []
    with destination.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and item.get("action") in _ACTIONS:
                events.append(item)
    return sorted(events, key=lambda item: float(item.get("ts", 0)))


def filter_events(
    events: list[dict[str, object]],
    *,
    since: float | None = None,
    until: float | None = None,
    action: str | None = None,
    mode: str | None = None,
    target: str | None = None,
    result: str | None = None,
) -> list[dict[str, object]]:
    return [
        item for item in events
        if (since is None or float(item.get("ts", 0)) >= since)
        and (until is None or float(item.get("ts", 0)) <= until)
        and (not action or item.get("action") == action)
        and (not mode or item.get("mode") == mode)
        and (not target or target.lower() in str(item.get("target", "")).lower())
        and (not result or result.lower() in str(item.get("result", "")).lower())
    ]
