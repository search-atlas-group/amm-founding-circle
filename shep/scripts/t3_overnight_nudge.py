#!/usr/bin/env python3
"""Conservative overnight nudger for idle T3 Code sessions.

Polls the local T3 server, finds sessions that are genuinely parked (session
ready, no active turn, last turn completed, quiet for >20 min) and sends one
short continuation turn. Everything else is skipped and logged.

Validated API path (T3 0.0.33, contracts in
vendor-apps/agent-control-planes/t3/packages/contracts/src/):
  1. `t3 auth session issue --ttl 5m --token-only` -> bearer, scopes include
     `orchestration:operate` (AuthStandardClientScopes, auth.ts:98).
  2. GET  /api/orchestration/shell             -> {projects, threads[...]}
     This is the list endpoint. `/api/orchestration/snapshot` also carries
     session state, but only `shell` exposes `backgroundLiveness`,
     `hasPendingApprovals` and `hasPendingUserInput` (OrchestrationThreadShell,
     orchestration.ts:434-483) - the three signals that say "not actually
     parked" even when the latest turn reads completed.
  3. POST /api/orchestration/dispatch          -> ClientOrchestrationCommand,
     type "thread.turn.start" (orchestration.ts:832) targets an EXISTING thread.

The WS route (ws://HOST/ws?wsTicket=...) carries the same command, but the HTTP
dispatch handler (apps/server/src/orchestration/http.ts:91) accepts the full
command union and feeds the same engine, so HTTP is used: one request, no
socket lifecycle to get wrong.

Fail-closed everywhere: any error, unknown state, or shape we do not recognise
is a skip, never a send, and never an exception that escapes the loop.

Usage:
  t3_overnight_nudge.py --dry-run --once     # decide + log, send nothing
  t3_overnight_nudge.py --once               # one live pass
  t3_overnight_nudge.py                      # loop until killed
  t3_overnight_nudge.py --self-check         # offline assertions, no network
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE_URL = os.environ.get("T3_BASE_URL", "http://127.0.0.1:3773")
T3_BIN = os.environ.get("T3_BIN") or shutil.which("t3") or "/opt/homebrew/bin/t3"
OUTCOMES_DIR = Path(
    os.environ.get("T3_NUDGE_OUTCOMES_DIR", "~/.mission-engine/t3-nudge-outcomes")
).expanduser()

POLL_SECONDS = 300
IDLE_SECONDS = 20 * 60
# A session quiet for longer than this is abandoned, not stalled. Waking a
# week-old thread unattended at 3am is the failure this ceiling prevents.
MAX_IDLE_SECONDS = 24 * 60 * 60
# Parity with Shep's nudge-attempt cap: after this the target is left for a human.
MAX_NUDGE_ATTEMPTS = 6
# Our own re-nudge floor, independent of observed idle time. If a dispatch lands
# but the thread's timestamps do not move, this is what stops a 5-minute retry
# storm from burning the whole attempt budget in half an hour.
COOLDOWN_SECONDS = 20 * 60
# Parity with Shep's MAX_NUDGE_CHARS.
MAX_NUDGE_CHARS = 160

NUDGE_TEXT = (
    "Keep driving your mission to completion. Verify with a real command "
    "before claiming done, then continue to the next step."
)

HTTP_TIMEOUT = 20

# Only these are nudgeable. Anything else -> skip. Both are allowlists.
READY_SESSION_STATUS = "ready"
COMPLETED_TURN_STATE = "completed"


# --------------------------------------------------------------------------
# logging
# --------------------------------------------------------------------------


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(when: dt.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def log_event(event: dict) -> None:
    """Append one JSONL line. Logging must never break the loop."""
    try:
        OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y-%m-%d")
        path = OUTCOMES_DIR / f"events-{stamp}.jsonl"
        event = {"ts": _iso(_now()), **event}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 - telemetry is never fatal
        print(f"[warn] could not write outcome log: {exc}", file=sys.stderr)


def load_attempts() -> dict[str, int]:
    """Rehydrate today's per-thread nudge count so the cap survives a restart.

    Without this the attempt cap resets on every relaunch, which makes it a
    decoration rather than a bound.
    """
    counts: dict[str, int] = {}
    try:
        stamp = dt.datetime.now().strftime("%Y-%m-%d")
        path = OUTCOMES_DIR / f"events-{stamp}.jsonl"
        if not path.exists():
            return counts
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:  # noqa: BLE001 - a torn line must not poison the cap
                continue
            if row.get("action") == "nudged" and row.get("thread_id"):
                counts[row["thread_id"]] = counts.get(row["thread_id"], 0) + 1
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] could not rehydrate attempts: {exc}", file=sys.stderr)
    return counts


# --------------------------------------------------------------------------
# T3 API
# --------------------------------------------------------------------------


def issue_token() -> str | None:
    """Short-lived bearer via the T3 CLI. Never logged or printed."""
    try:
        proc = subprocess.run(
            [T3_BIN, "auth", "session", "issue", "--ttl", "5m", "--token-only"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        log_event({"action": "pass_skipped", "reason": "token_exec_failed", "error": str(exc)})
        return None
    if proc.returncode != 0:
        log_event({"action": "pass_skipped", "reason": "token_issue_failed",
                   "returncode": proc.returncode})
        return None
    token = proc.stdout.strip()
    if not token:
        log_event({"action": "pass_skipped", "reason": "token_empty"})
        return None
    return token


def _request(token: str, path: str, payload: dict | None = None) -> tuple[int, object]:
    """Return (status, parsed-body). Never raises."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:  # noqa: BLE001 - SPA fallback returns HTML
                return resp.status, raw[:200]
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001
            pass
        return exc.code, body
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def fetch_threads(token: str) -> list[dict] | None:
    status, body = _request(token, "/api/orchestration/shell")
    if status != 200 or not isinstance(body, dict):
        log_event({"action": "pass_skipped", "reason": "snapshot_failed", "status": status})
        return None
    threads = body.get("threads")
    if not isinstance(threads, list):
        log_event({"action": "pass_skipped", "reason": "snapshot_shape_unknown"})
        return None
    return threads


def send_nudge(token: str, thread: dict) -> tuple[bool, str]:
    """Dispatch one user turn to an existing thread."""
    command = {
        "type": "thread.turn.start",
        "commandId": str(uuid.uuid4()),
        "threadId": thread["id"],
        "message": {
            "messageId": str(uuid.uuid4()),
            "role": "user",
            "text": NUDGE_TEXT,
            "attachments": [],
        },
        # Both are required on the client command; mirror the thread's own
        # settings so a nudge never silently changes how the session runs.
        "runtimeMode": thread.get("runtimeMode") or "full-access",
        "interactionMode": thread.get("interactionMode") or "default",
        "createdAt": _iso(_now()),
    }
    status, body = _request(token, "/api/orchestration/dispatch", command)
    if status == 200:
        return True, "ok"
    return False, f"status={status} body={str(body)[:200]}"


# --------------------------------------------------------------------------
# decision
# --------------------------------------------------------------------------


def _parse(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def last_activity(thread: dict) -> dt.datetime | None:
    """Most recent timestamp anywhere on the thread.

    Deliberately the MAX: if any field says the thread moved recently, that is
    enough to leave it alone.
    """
    session = thread.get("session") or {}
    turn = thread.get("latestTurn") or {}
    stamps = [
        _parse(thread.get("updatedAt")),
        _parse(session.get("updatedAt") if isinstance(session, dict) else None),
        _parse(turn.get("completedAt") if isinstance(turn, dict) else None),
        _parse(turn.get("startedAt") if isinstance(turn, dict) else None),
        _parse(turn.get("requestedAt") if isinstance(turn, dict) else None),
    ]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def classify(thread: dict, now: dt.datetime, attempts: int, last_nudge: dt.datetime | None,
             idle_seconds: int = IDLE_SECONDS,
             max_idle_seconds: int = MAX_IDLE_SECONDS,
             max_attempts: int = MAX_NUDGE_ATTEMPTS,
             cooldown_seconds: int = COOLDOWN_SECONDS) -> tuple[bool, str, float | None]:
    """Return (should_nudge, reason, idle_minutes). Pure; no I/O."""
    if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
        return False, "thread_shape_unknown", None
    if thread.get("deletedAt"):
        return False, "deleted", None
    if thread.get("archivedAt"):
        return False, "archived", None

    session = thread.get("session")
    if not isinstance(session, dict):
        return False, "no_session", None
    status = session.get("status")
    if status != READY_SESSION_STATUS:
        # "running" means the agent is working; "stopped" means no live process.
        return False, f"session_status:{status}", None
    if session.get("activeTurnId"):
        return False, "active_turn", None
    if session.get("lastError"):
        return False, "session_error", None

    turn = thread.get("latestTurn")
    if not isinstance(turn, dict):
        return False, "no_turn", None
    state = turn.get("state")
    if state != COMPLETED_TURN_STATE:
        # "interrupted" is a deliberate human stop - do not override it.
        return False, f"turn_state:{state}", None

    # A settled turn does not mean a settled session: background work outlives
    # the turn that started it, and this is the only field that says so.
    if thread.get("backgroundLiveness"):
        return False, f"background_{thread['backgroundLiveness']}", None
    # Both of these are waiting on a specific answer. A generic continuation is
    # the wrong reply and would push a real question further up the transcript.
    if thread.get("hasPendingApprovals"):
        return False, "pending_approval", None
    if thread.get("hasPendingUserInput"):
        return False, "pending_user_input", None

    snoozed = _parse(thread.get("snoozedUntil"))
    if snoozed and snoozed > now:
        return False, "snoozed", None

    seen = last_activity(thread)
    if seen is None:
        return False, "no_timestamp", None
    idle = (now - seen).total_seconds()
    idle_min = idle / 60
    if idle < 0:
        return False, "clock_skew", idle_min
    if idle < idle_seconds:
        return False, "not_idle", idle_min
    if idle > max_idle_seconds:
        return False, "idle_beyond_ceiling", idle_min

    if attempts >= max_attempts:
        return False, "max_attempts", idle_min
    if last_nudge and (now - last_nudge).total_seconds() < cooldown_seconds:
        return False, "cooldown", idle_min

    return True, "idle_stalled", idle_min


# --------------------------------------------------------------------------
# loop
# --------------------------------------------------------------------------


def run_pass(dry_run: bool, attempts: dict[str, int], last_nudge: dict[str, dt.datetime]) -> None:
    """One full pass. Never raises."""
    token = issue_token()
    if token is None:
        return
    threads = fetch_threads(token)
    if threads is None:
        return

    now = _now()
    nudged = skipped = 0
    for thread in threads:
        try:
            thread_id = thread.get("id") if isinstance(thread, dict) else None
            ok, reason, idle_min = classify(
                thread, now, attempts.get(thread_id or "", 0), last_nudge.get(thread_id or "")
            )
            base = {
                "thread_id": thread_id,
                "title": (thread.get("title") if isinstance(thread, dict) else None),
                "reason": reason,
                "idle_min": round(idle_min, 1) if idle_min is not None else None,
                "attempts": attempts.get(thread_id or "", 0),
            }
            if not ok:
                skipped += 1
                # Quiet the two states that describe most of the fleet forever.
                if reason not in ("session_status:stopped", "deleted", "archived"):
                    log_event({"action": "skipped", **base})
                continue
            if dry_run:
                log_event({"action": "would_nudge", "dry_run": True, **base})
                nudged += 1
                continue
            sent, detail = send_nudge(token, thread)
            if sent:
                attempts[thread_id] = attempts.get(thread_id, 0) + 1
                last_nudge[thread_id] = now
                nudged += 1
                log_event({"action": "nudged", "text": NUDGE_TEXT,
                           **{**base, "attempts": attempts[thread_id]}})
            else:
                # A failed send is NOT an attempt, but the cooldown still
                # applies so a broken thread cannot be retried every pass.
                last_nudge[thread_id] = now
                log_event({"action": "send_failed", "detail": detail, **base})
        except Exception as exc:  # noqa: BLE001 - one bad thread never kills the pass
            log_event({"action": "skipped", "reason": "classify_exception", "error": str(exc)})
            skipped += 1

    log_event({"action": "pass_complete", "threads": len(threads),
               "nudged": nudged, "skipped": skipped, "dry_run": dry_run})
    print(f"[{_iso(now)}] pass: {len(threads)} threads, "
          f"{'would nudge' if dry_run else 'nudged'} {nudged}, skipped {skipped}")


def self_check() -> int:
    """Offline assertions on the decision logic. No network, no T3 required."""
    now = dt.datetime(2026, 8, 21, 6, 0, tzinfo=dt.timezone.utc)

    def thread(**over):
        base = {
            "id": "t-1",
            "title": "x",
            "runtimeMode": "full-access",
            "interactionMode": "default",
            "updatedAt": _iso(now - dt.timedelta(minutes=45)),
            "session": {"status": "ready", "activeTurnId": None, "lastError": None,
                        "updatedAt": _iso(now - dt.timedelta(minutes=45))},
            "latestTurn": {"state": "completed",
                           "completedAt": _iso(now - dt.timedelta(minutes=45))},
        }
        base.update(over)
        return base

    ok, reason, _ = classify(thread(), now, 0, None)
    assert ok and reason == "idle_stalled", (ok, reason)

    # streaming / working is never nudged
    for status in ("running", "stopped", None, "weird"):
        sess = {"status": status, "activeTurnId": None, "lastError": None}
        ok, reason, _ = classify(thread(session=sess), now, 0, None)
        assert not ok, f"nudged a {status} session"

    # an active turn blocks even when the session says ready
    ok, _, _ = classify(
        thread(session={"status": "ready", "activeTurnId": "t", "lastError": None}), now, 0, None)
    assert not ok

    # errored session
    ok, _, _ = classify(
        thread(session={"status": "ready", "activeTurnId": None, "lastError": "boom"}),
        now, 0, None)
    assert not ok

    # non-completed turn states, including a human interrupt
    for state in ("running", "interrupted", None, "queued"):
        ok, _, _ = classify(thread(latestTurn={"state": state}), now, 0, None)
        assert not ok, f"nudged turn state {state}"

    # background work outliving a completed turn
    for live in ("working", "monitoring"):
        ok, reason, _ = classify(thread(backgroundLiveness=live), now, 0, None)
        assert not ok and reason == f"background_{live}", reason

    # waiting on a human answer -> a generic continuation is the wrong reply
    ok, reason, _ = classify(thread(hasPendingApprovals=True), now, 0, None)
    assert not ok and reason == "pending_approval", reason
    ok, reason, _ = classify(thread(hasPendingUserInput=True), now, 0, None)
    assert not ok and reason == "pending_user_input", reason

    # fresh activity
    fresh = _iso(now - dt.timedelta(minutes=5))
    ok, reason, _ = classify(
        thread(updatedAt=fresh,
               session={"status": "ready", "activeTurnId": None, "lastError": None,
                        "updatedAt": fresh},
               latestTurn={"state": "completed", "completedAt": fresh}), now, 0, None)
    assert not ok and reason == "not_idle", reason

    # the MAX rule: one stale field must not outvote one fresh field
    ok, reason, _ = classify(
        thread(session={"status": "ready", "activeTurnId": None, "lastError": None,
                        "updatedAt": _iso(now - dt.timedelta(minutes=2))}),
        now, 0, None)
    assert not ok and reason == "not_idle", reason

    # abandoned threads are left alone
    old = _iso(now - dt.timedelta(days=6))
    ok, reason, _ = classify(
        thread(updatedAt=old,
               session={"status": "ready", "activeTurnId": None, "lastError": None,
                        "updatedAt": old},
               latestTurn={"state": "completed", "completedAt": old}), now, 0, None)
    assert not ok and reason == "idle_beyond_ceiling", reason

    # caps
    ok, reason, _ = classify(thread(), now, MAX_NUDGE_ATTEMPTS, None)
    assert not ok and reason == "max_attempts", reason
    ok, reason, _ = classify(thread(), now, 1, now - dt.timedelta(minutes=3))
    assert not ok and reason == "cooldown", reason
    ok, _, _ = classify(thread(), now, 1, now - dt.timedelta(minutes=40))
    assert ok

    # snooze, archive, delete, junk
    ok, _, _ = classify(thread(snoozedUntil=_iso(now + dt.timedelta(hours=2))), now, 0, None)
    assert not ok
    ok, _, _ = classify(thread(archivedAt=_iso(now)), now, 0, None)
    assert not ok
    ok, _, _ = classify(thread(deletedAt=_iso(now)), now, 0, None)
    assert not ok
    for junk in ({}, {"id": 5}, {"id": "t", "session": "nope"},
                 {"id": "t", "session": {"status": "ready"}, "latestTurn": "nope"}):
        ok, _, _ = classify(junk, now, 0, None)
        assert not ok
    ok, reason, _ = classify(
        thread(updatedAt="not-a-date",
               session={"status": "ready", "activeTurnId": None, "lastError": None},
               latestTurn={"state": "completed"}), now, 0, None)
    assert not ok and reason == "no_timestamp", reason

    assert len(NUDGE_TEXT) <= MAX_NUDGE_CHARS, len(NUDGE_TEXT)
    print(f"self-check OK  (nudge text {len(NUDGE_TEXT)} chars, cap {MAX_NUDGE_CHARS})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="decide and log, send nothing")
    parser.add_argument("--once", action="store_true", help="single pass, then exit")
    parser.add_argument("--interval", type=int, default=POLL_SECONDS,
                        help=f"seconds between passes (default {POLL_SECONDS})")
    parser.add_argument("--self-check", action="store_true",
                        help="offline assertions on the decision logic")
    args = parser.parse_args()

    if args.self_check:
        return self_check()

    attempts = load_attempts()
    last_nudge: dict[str, dt.datetime] = {}
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"t3-overnight-nudge {mode} base={BASE_URL} idle>{IDLE_SECONDS // 60}m "
          f"cap={MAX_NUDGE_ATTEMPTS} log={OUTCOMES_DIR}")
    log_event({"action": "started", "dry_run": args.dry_run, "once": args.once,
               "interval": args.interval, "rehydrated_threads": len(attempts)})

    while True:
        try:
            run_pass(args.dry_run, attempts, last_nudge)
        except Exception as exc:  # noqa: BLE001 - the loop outlives any pass
            log_event({"action": "pass_skipped", "reason": "unhandled", "error": str(exc)})
        if args.once:
            return 0
        try:
            time.sleep(max(30, args.interval))
        except KeyboardInterrupt:
            log_event({"action": "stopped"})
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
