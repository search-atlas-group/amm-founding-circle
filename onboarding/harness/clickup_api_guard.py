#!/usr/bin/env python3
"""PreToolUse gate — block hand-rolled ClickUp API calls.

Why: raw curl/python calls against api.clickup.com have two documented
silent-failure modes that cost real time on 2026-07-29 —
  1. Posting a thread reply to a `/t/<id>` URL's message id (a nested reply,
     not the thread root) returns HTTP 201 but is invisible to the user.
  2. Attaching a file via a channel/chat-message entity type doesn't exist in
     the public API; only Task attachments and (unconfigured) custom fields
     do, so a raw attempt 400s or the agent falls back to a fabricated link.

The fix already exists as code: `_brain/scripts/clickup_bash_bridge.py`
(root-resolves + render-asserts replies) and the carrier-task file-share
protocol in [[reference-clickup-file-share-jd-workspace]]. This hook blocks
any Bash command that talks to api.clickup.com directly without going through
an allowlisted wrapper, so a fresh session can't repeat the mistake even if it
never reads memory first.

Contract: PreToolUse hook. Reads the tool payload on stdin; emits a
`permissionDecision: deny` envelope to block, or nothing to allow. Never
hard-fails on its own errors (fail-open on any exception). Disable with
CLICKUP_API_GUARD_DISABLE=1.
"""
from __future__ import annotations

import json
import os
import sys

ALLOWLISTED_MARKERS = (
    "clickup_bash_bridge.py",
    "clickup_file_share.py",
    "send_clickup_message.py",
    "clickup-thread-reply.py",
    "clickup_fleet.py",
    "clickup-pm-bridge.py",
)


def emit(payload: dict) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def load_hook_input() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def main() -> int:
    if os.environ.get("CLICKUP_API_GUARD_DISABLE") == "1":
        return 0

    payload = load_hook_input()
    tool = str(payload.get("tool_name") or payload.get("toolName") or "")
    if tool != "Bash":
        return 0

    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    command = str(ti.get("command") or "") if isinstance(ti, dict) else ""
    if "api.clickup.com" not in command:
        return 0

    if any(marker in command for marker in ALLOWLISTED_MARKERS):
        return 0  # going through a vetted wrapper — allow

    reason = (
        "Blocked: this Bash command talks to api.clickup.com directly instead of "
        "through a vetted wrapper. Two documented silent-failure modes: (1) thread "
        "replies posted to a /t/<id> URL's message id land in a detached thread "
        "nobody sees (HTTP 201, invisible) — use "
        "`python3 _brain/scripts/clickup_bash_bridge.py --reply <id> --channel <id> \"text\"` "
        "which root-resolves and render-asserts; (2) file attachments have no direct "
        "chat-message upload path — use the carrier-task protocol in "
        "reference-clickup-file-share-jd-workspace (Agent File Vault -> Shares list "
        "901114056639, POST /v2/task/{id}/attachment), not a fabricated link. Read the "
        "`clickup` skill's Shared Policy section before writing raw ClickUp API calls."
    )
    emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open — never block on our own bug
