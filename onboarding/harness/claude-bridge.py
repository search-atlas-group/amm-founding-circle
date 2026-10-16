#!/usr/bin/env python3
"""Run a Claude Code hook against a Hermes shell-hook event.

Hermes speaks one dialect and the Claude harness another:

- Hermes names the event ``hook_event_name`` and puts the prompt in
  ``extra.user_message``. Claude names it ``hook_event_name`` too, but puts the
  prompt in ``prompt`` and expects the transcript at ``transcript_path``.
- Claude answers with ``hookSpecificOutput.additionalContext`` or
  ``permissionDecision``. Hermes reads ``context`` to inject and ``decision:
  block`` (or exit code 2) to stop a tool.

This translates in both directions and then execs the real script, so the
harness files stay exactly as they are. A script that crashes or says nothing
becomes a no-op: a hook must never wedge the turn.

Usage: claude-bridge.py <script> [args...]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hermes_transcript  # noqa: E402

EVENT_NAMES = {
    "pre_llm_call": "UserPromptSubmit",
    "on_session_start": "SessionStart",
    "post_llm_call": "Stop",
    "post_tool_call": "PostToolUse",
    "pre_tool_call": "PreToolUse",
    "on_session_end": "SessionEnd",
}

# Claude tool names the harness scripts match on, and the Hermes names behind them.
TOOL_NAMES = {
    "terminal": "Bash",
    "patch": "Edit",
    "write_file": "Write",
    "read_file": "Read",
    "search_files": "Grep",
}

NEEDS_TRANSCRIPT = {"Stop", "PostToolUse", "SessionEnd"}


def _context_of(out: dict) -> str:
    specific = out.get("hookSpecificOutput")
    if isinstance(specific, dict):
        text = specific.get("additionalContext")
        if isinstance(text, str) and text.strip():
            return text
    for key in ("additionalContext", "systemMessage"):
        text = out.get(key)
        if isinstance(text, str) and text.strip():
            return text
    return ""


def _denied(out: dict) -> str:
    specific = out.get("hookSpecificOutput")
    if isinstance(specific, dict) and specific.get("permissionDecision") == "deny":
        return str(specific.get("permissionDecisionReason") or "Blocked by harness hook.")
    return ""


def _rewrite(out: dict) -> dict | None:
    specific = out.get("hookSpecificOutput")
    if isinstance(specific, dict) and isinstance(specific.get("updatedInput"), dict):
        return specific["updatedInput"]
    return None


def translate(event: str, out: dict, code: int, stderr: str) -> tuple[dict, int]:
    """Claude's answer, restated in the dialect Hermes acts on."""
    if event == "pre_tool_call":
        reason = _denied(out)
        if reason:
            return {"decision": "block", "reason": reason}, 0
        updated = _rewrite(out)
        if updated is not None:
            return {"decision": "modify", "tool_input": updated}, 0
        if code == 2:
            return {"decision": "block", "reason": (stderr or "Blocked by harness hook.")[:400]}, 2
        return {}, 0
    if event == "post_llm_call":
        # Claude's Stop hook blocks to force another turn. Hermes' pre_verify is
        # that gate; post_llm_call only observes, so a block becomes context the
        # next turn can see rather than a turn that never ends.
        reason = out.get("reason") or out.get("message") or ""
        if out.get("decision") == "block" and reason:
            return {"context": reason}, 0
        text = _context_of(out)
        return ({"context": text} if text else {}), 0
    text = _context_of(out)
    return ({"context": text} if text else {}), 0


def main() -> int:
    if len(sys.argv) < 2:
        return 0
    script, hook_args = sys.argv[1], sys.argv[2:]
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(data, dict):
        return 0

    hermes_event = str(data.get("hook_event_name") or "")
    claude_event = EVENT_NAMES.get(hermes_event, hermes_event)
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}

    def pick(*keys):
        """Hermes puts some facts at the top level and the rest under extra."""
        for source in (data, extra):
            for key in keys:
                value = source.get(key)
                if value not in (None, ""):
                    return value
        return ""

    data["hook_event_name"] = claude_event
    data["session_id"] = str(pick("session_id"))
    prompt = pick("user_message", "prompt")
    if isinstance(prompt, str) and prompt:
        data["prompt"] = prompt
    if hermes_event == "on_session_end":
        data["reason"] = "prompt_input_exit" if pick("completed") else "other"

    tool = data.get("tool_name")
    if isinstance(tool, str) and tool in TOOL_NAMES:
        data["tool_name"] = TOOL_NAMES[tool]
    tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else None
    # A real firing carries the tool arguments once, under "args", and Hermes
    # copies them to tool_input. The test command nests a second copy under
    # extra, so when the two disagree, extra.args is the one the caller set.
    if isinstance(extra.get("args"), dict):
        tool_input = extra["args"]
    if isinstance(tool_input, dict) and tool_input:
        if "file_path" not in tool_input and isinstance(tool_input.get("path"), str):
            tool_input = dict(tool_input, file_path=tool_input["path"])
        data["tool_input"] = tool_input

    result = pick("result", "tool_response")
    if result:
        data["tool_response"] = result if isinstance(result, dict) else {"content": str(result)}

    if claude_event in NEEDS_TRANSCRIPT and data.get("session_id"):
        try:
            dest = hermes_transcript.render(str(data["session_id"]))
        except Exception:
            dest = None
        if dest:
            data["transcript_path"] = str(dest)
    if hermes_event == "post_tool_call":
        data.setdefault("tool_response", {"content": ""})

    try:
        proc = subprocess.run(
            [sys.executable, script, *hook_args],
            input=json.dumps(data),
            text=True,
            capture_output=True,
            timeout=30,
        )
    except Exception:
        return 0

    out: dict = {}
    raw = proc.stdout.strip()
    if raw:
        try:
            parsed = json.loads(raw.splitlines()[-1])
            if isinstance(parsed, dict):
                out = parsed
        except ValueError:
            out = {}
    translated, code = translate(hermes_event, out, proc.returncode, proc.stderr.strip())
    if translated:
        print(json.dumps(translated))
    return code


if __name__ == "__main__":
    sys.exit(main())
