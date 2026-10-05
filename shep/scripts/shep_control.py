#!/usr/bin/env python3
"""Bounded, headless Shep control pass.

The control pass is intentionally a small policy engine. Collection and the
transport callbacks are injected so a dry-run and the safety rules can be
tested without touching a real Herdr session.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Callable, Iterable

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

try:
    from shep_action_log import ActionLogError, append
except ImportError:  # pragma: no cover - package import from repository root
    from scripts.shep_action_log import ActionLogError, append


DEFAULT_STATE = Path(__file__).resolve().parent.parent / "reports/data/shep-actions/state.json"
DEFAULT_LOCK = Path(__file__).resolve().parent.parent / "reports/data/shep-actions/control.lock"
MAX_ATTEMPTS = 3
COOLDOWN_SECONDS = 60.0
DEFAULT_ACTION_CAP = 3


class ControlBusy(RuntimeError):
    """Another Shep control pass holds the singleton lock."""


def _key(row: dict) -> str:
    return str(row.get("target") or row.get("id") or "")


def _metadata(row: dict) -> dict[str, object]:
    return {
        "session": row.get("label") or row.get("id"),
        "workspace": row.get("workspace_id") or row.get("cwd"),
        "repository": row.get("repository") or row.get("cwd"),
        "pane": row.get("pane_id") or row.get("target"),
        "source": row.get("source"),
    }


def _safe_continuation(row: dict) -> str:
    # This fixed phrase is deliberately the only automatic nudge. It is in the
    # safe_continuation classifier vocabulary and cannot smuggle a new action.
    return "Continue with the next task."


def _read_state(path: Path) -> dict[str, dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(path: Path, state: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


@contextlib.contextmanager
def _singleton(path: Path):
    if fcntl is None:
        raise ControlBusy("platform has no singleton lock")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ControlBusy("control pass already running") from exc
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _current_row(collector: Callable[[], Iterable[dict]], row: dict) -> dict | None:
    key = _key(row)
    for current in collector():
        if _key(current) == key:
            return current
    return None


def _reap_safe(current: dict | None, original: dict) -> tuple[bool, str]:
    if current is None:
        return False, "session disappeared"
    if _key(current) != _key(original):
        return False, "target identity changed"
    if current.get("source") != "herdr":
        return False, "auto-reap is Herdr-only"
    if current.get("status") not in {"idle", "done"}:
        return False, f"session is now {current.get('status') or 'unknown'}"
    if not current.get("reap_ready"):
        return False, "missing explicit SAFE_TO_CLOSE evidence"
    if current.get("operator_attached"):
        return False, "operator is attached"
    if current.get("workspace_safe") is False or current.get("repo_safe") is False:
        return False, "workspace or repository safety check failed"
    return True, "explicit SAFE_TO_CLOSE revalidated"


def control_once(
    collector: Callable[[], Iterable[dict]],
    *,
    send: Callable[[dict, str], tuple[bool, str]],
    reap: Callable[[dict], tuple[bool, str]],
    ledger_path: str | os.PathLike[str] | None = None,
    state_path: str | os.PathLike[str] | None = None,
    lock_path: str | os.PathLike[str] | None = None,
    auto_nudge: bool = False,
    auto_reap: bool = False,
    dry_run: bool = False,
    max_actions: int = DEFAULT_ACTION_CAP,
    now: float | None = None,
) -> dict[str, object]:
    """Run one bounded pass; transient failures wait for the next schedule.

    # RETRY-LOOP-SAFETY: bounded by design — do not add a naive rate-limit retry handler here.
    #   concurrency: one non-blocking process lock prevents overlapping passes.
    #   attempts:    each target has at most 3 attempts, then terminal handoff.
    #   backoff:     failures skip this cycle; the next scheduled pass retries.
    #   why no retry handler: inline sleeps would hold the singleton lock and starve the scheduler.
    # The pass is also capped at max_actions and never sleeps or retries inline.
    """
    cap = max(0, min(int(max_actions), DEFAULT_ACTION_CAP))
    state_file = Path(state_path or DEFAULT_STATE).expanduser()
    singleton = Path(lock_path or DEFAULT_LOCK).expanduser()
    timestamp = time.time() if now is None else float(now)
    report: dict[str, object] = {"dry_run": dry_run, "nudged": 0, "reaped": 0, "refused": 0, "failed": 0, "audit_errors": 0, "planned": []}

    def terminal_receipt(action: str, lifecycle: str, **fields) -> None:
        try:
            append(action, lifecycle, path=ledger_path, **fields)
        except ActionLogError:
            # The intent receipt already prevented an un-audited mutation. A
            # terminal receipt can fail after transport; surface that fact and
            # finish the bounded pass so launchd does not replay the action.
            report["audit_errors"] += 1

    with _singleton(singleton):
        state = _read_state(state_file)
        rows = list(collector())
        considered = 0
        for row in rows:
            if considered >= cap:
                break
            target = _key(row)
            if not target or row.get("source") != "herdr":
                continue
            item = state.setdefault(target, {})
            if auto_nudge and row.get("status") in {"idle", "done", "stalled"} and not row.get("reap_ready"):
                if item.get("nudge_terminal") or item.get("nudge_attempts", 0) >= MAX_ATTEMPTS:
                    continue
                if timestamp < float(item.get("next_nudge_at", 0)):
                    continue
                text = _safe_continuation(row)
                considered += 1
                report["planned"].append({"action": "nudge", "target": target, "text": text})
                if dry_run:
                    continue
                try:
                    append("nudge", "intent", mode="auto", target=target, metadata=_metadata(row), policy="safe_continuation", context=row.get("context_hash") or row.get("pane_signature") or "", reason="bounded automatic continuation", text=text, path=ledger_path)
                except ActionLogError as exc:
                    report["refused"] += 1
                    item["nudge_attempts"] = item.get("nudge_attempts", 0) + 1
                    item["next_nudge_at"] = timestamp + COOLDOWN_SECONDS
                    try:
                        append("nudge", "refused", mode="auto", target=target, metadata=_metadata(row), policy="safe_continuation", context=row.get("context_hash") or row.get("pane_signature") or "", reason="audit receipt unavailable", error=str(exc), path=ledger_path)
                    except ActionLogError:
                        pass
                    continue
                ok, detail = send(row, text)
                item["nudge_attempts"] = item.get("nudge_attempts", 0) + 1
                item["next_nudge_at"] = timestamp + COOLDOWN_SECONDS
                if ok:
                    report["nudged"] += 1
                    terminal_receipt("nudge", "sent", mode="auto", target=target, metadata=_metadata(row), policy="safe_continuation", context=row.get("context_hash") or row.get("pane_signature") or "", reason="bounded automatic continuation", text=text, result=detail)
                else:
                    report["failed"] += 1
                    if item["nudge_attempts"] >= MAX_ATTEMPTS:
                        item["nudge_terminal"] = True
                    terminal_receipt("nudge", "failed", mode="auto", target=target, metadata=_metadata(row), policy="safe_continuation", context=row.get("context_hash") or row.get("pane_signature") or "", reason="transport failed", text=text, result=detail, error=detail)
                continue
            if auto_reap and row.get("reap_ready"):
                if item.get("reap_terminal"):
                    continue
                considered += 1
                current = _current_row(collector, row)
                safe, reason = _reap_safe(current, row)
                if dry_run:
                    report["planned"].append({"action": "reap", "target": target, "reason": reason})
                    continue
                try:
                    append("reap", "candidate", mode="auto", target=target, metadata=_metadata(row), policy="SAFE_TO_CLOSE", context=row.get("context_hash") or row.get("pane_signature") or "", reason="candidate observed", path=ledger_path)
                except ActionLogError:
                    report["refused"] += 1
                    continue
                if not safe:
                    report["refused"] += 1
                    try:
                        append("reap", "refused", mode="auto", target=target, metadata=_metadata(current or row), policy="SAFE_TO_CLOSE", context=(current or row).get("context_hash") or (current or row).get("pane_signature") or "", reason=reason, path=ledger_path)
                    except ActionLogError:
                        pass
                    item["reap_terminal"] = True
                    continue
                report["planned"].append({"action": "reap", "target": target, "reason": reason})
                try:
                    append("reap", "intent", mode="auto", target=target, metadata=_metadata(current or row), policy="SAFE_TO_CLOSE", context=(current or row).get("context_hash") or (current or row).get("pane_signature") or "", reason=reason, path=ledger_path)
                except ActionLogError as exc:
                    report["refused"] += 1
                    try:
                        append("reap", "refused", mode="auto", target=target, metadata=_metadata(row), policy="SAFE_TO_CLOSE", context=row.get("context_hash") or row.get("pane_signature") or "", reason="audit receipt unavailable", error=str(exc), path=ledger_path)
                    except ActionLogError:
                        pass
                    continue
                ok, detail = reap(current or row)
                item["reap_terminal"] = True
                if ok:
                    report["reaped"] += 1
                    terminal_receipt("reap", "reaped", mode="auto", target=target, metadata=_metadata(current or row), policy="SAFE_TO_CLOSE", context=(current or row).get("context_hash") or (current or row).get("pane_signature") or "", reason=reason, result=detail)
                else:
                    report["failed"] += 1
                    terminal_receipt("reap", "failed", mode="auto", target=target, metadata=_metadata(current or row), policy="SAFE_TO_CLOSE", context=(current or row).get("context_hash") or (current or row).get("pane_signature") or "", reason="close transport failed", result=detail, error=detail)
        if not dry_run:
            _write_state(state_file, state)
    return report
