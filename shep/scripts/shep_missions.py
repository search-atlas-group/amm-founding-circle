"""Canonical Shep mission queue.

This module is the small, process-safe boundary used by Commander and Shep's
interactive view.  It owns mission identity, durable queue state, and the
Orca-inspired dispatch metadata; it does not launch agents or create
worktrees.  Launch remains an explicit Shep operation.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path


VALID_MODES = {"inline", "fleet"}
SCHEMA = "shep-missions/v1"


def _state_path(path: str | os.PathLike[str] | None = None) -> Path:
    if path:
        return Path(path).expanduser()
    root = Path(os.environ.get("MISSION_ENGINE_DIR", str(Path.home() / ".mission-engine"))).expanduser()
    return Path(os.environ.get("SHEP_MISSIONS_PATH", str(root / "missions.json"))).expanduser()


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (result[:48].rstrip("-") or "mission")


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema": SCHEMA, "missions": []}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Shep mission store is unreadable: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or not isinstance(value.get("missions"), list):
        raise RuntimeError("Shep mission store has an unsupported schema")
    return value


def _atomic_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@contextlib.contextmanager
def _locked(path: Path):
    lock = path.with_name(f"{path.name}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(lock.parent, 0o700)
    handle = open(lock, "a+", encoding="utf-8")
    try:
        os.chmod(lock, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def create_mission(goal: str, *, mode: str = "fleet", base: str = "develop", now: float | None = None) -> dict:
    """Return a validated queued mission without touching the filesystem."""
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("mission goal must be a non-empty string")
    if mode not in VALID_MODES:
        raise ValueError("mission mode must be inline or fleet")
    if not isinstance(base, str) or not base.strip():
        raise ValueError("mission base must be a non-empty string")
    timestamp = time.time() if now is None else float(now)
    slug = _slug(goal)
    mission_id = f"mission-{uuid.uuid4().hex[:16]}-{slug}"
    return {
        "id": mission_id,
        "goal": goal.strip(),
        "mode": mode,
        "status": "queued",
        "base": base.strip(),
        "branch_prefix": f"swarmlet/{slug}",
        "artifacts": {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def queue_mission(goal: str, *, mode: str = "fleet", base: str = "develop", path=None, now=None) -> dict:
    """Durably queue one mission and return the stored record."""
    destination = _state_path(path)
    mission = create_mission(goal, mode=mode, base=base, now=now)
    with _locked(destination):
        state = _read(destination)
        state["missions"].append(mission)
        _atomic_write(destination, state)
    return mission


def list_missions(path=None) -> list[dict]:
    """Read queued and historical missions in creation order."""
    destination = _state_path(path)
    with _locked(destination):
        return list(_read(destination)["missions"])
