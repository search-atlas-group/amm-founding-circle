#!/usr/bin/env python3
"""PostToolUse: two failures on one target, then hand it back to JD.

WHY THIS EXISTS
---------------
Every tooling loop in the interaction audit (2026-09-05) ended one of three ways,
and "the agent succeeded on attempt five" was never one of them:

  * `13ce35fc` — 24 wasted JD turns on Zoom headless auth: MCP rejected, permission
    blocks, missing scopes, manual app creation. It ended at t73 when JD dropped the
    requirement: "forgetting about the headless authentication... I just need the
    fucking recordings".
  * `003606ac` — five failed browser/MFA attempts, a stall at t45-52, and three OTP
    codes that expired unused. It ended at t65: "ok open it for me". JD did it in his
    own Chrome in under a minute.
  * `904c34bc` — 1,197 minutes, seven JD turns, abandoned outright: "nevermind".

The agent's third, fourth and fifth attempts have no measured success rate above
zero, and each one costs JD a turn of watching. The cheap move is available the
whole time and never taken: say what failed and hand him the one click.

WHAT THIS DOES
--------------
Counts consecutive failures per TARGET within the current turn — the same file, the
same command shape, the same host, the same tool and argument. On the second one it
injects a stop-and-hand-back instruction naming the target.

The transcript is the source of truth, not an accumulated counter: the hook re-reads
the tool calls since JD's last message on every invocation. That means the count is
right even if PostToolUse does not fire on some failure shapes, and it resets on a
new user turn and on a success by construction rather than by bookkeeping.

A third form of failure is counted too, because it is the `b521b304` shape rather
than an error: the SAME edit applied to the same file three or more times. Nothing
errored; the model is just going in a circle.

CONTRACT
--------
additionalContext on stdout, exit 0. Never blocks a tool, never raises, never
repeats the same warning twice for the same target and count.

ESCAPE HATCH
------------
`TWO_STRIKE=off` in the environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

STATE_TTL_SECONDS = 6 * 60 * 60
STRIKE_LIMIT = 2          # warn on the SECOND failure, not the fifth
SAME_EDIT_LIMIT = 3       # the same edit re-applied this many times is a loop

# Failure signatures. Deliberately narrow: a `grep -i error` result that prints the
# word "error" is not a failed tool call, and a gate that miscounts those turns
# itself into the noise it exists to stop.
ERROR_TEXT_RE = re.compile(
    r"^\s*(?:error|exception|traceback|fatal|usage:)\b"
    r"|permission (?:for this action was )?denied"
    r"|denied by the .*classifier"
    r"|requested permissions?"
    r"|operation not permitted"
    r"|command not found"
    r"|no such file or directory"
    r"|exit (?:code|status):? [1-9]"
    r"|\b(?:401|403|404|429|500|502|503)\b .*(?:unauthor|forbidden|not found|limit|error)"
    r"|authentication failed|invalid[_ ]grant|token (?:expired|invalid)"
    r"|timed out|timeout (?:exceeded|after)"
    r"|is not a valid|could not (?:connect|resolve|authenticate)",
    re.I,
)

URL_RE = re.compile(r"https?://([A-Za-z0-9._-]+)")
# A bare word is a subcommand (`git push`); a path, flag or glob is an argument.
SUBCOMMAND_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
# `cd /some/path &&` in front of the real command is bookkeeping, not the target.
CD_PREFIX_RE = re.compile(r"^\s*cd\s+[^\s;&|]+\s*(?:&&|;)\s*")


def emit_context(text: str) -> None:
    print(json.dumps({
        "additionalContext": text,
        "hookSpecificOutput": {"hookEventName": "PostToolUse",
                               "additionalContext": text},
    }, separators=(",", ":")))


def payload_in() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


# ── state (dedupe only; the transcript holds the truth) ─────────────────────
def state_file(session: str) -> Path:
    root = Path(os.environ.get("TWO_STRIKE_STATE_DIR")
                or (Path(tempfile.gettempdir()) / "two-strike"))
    root.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "unknown")[:80]
    return root / ("%s.json" % safe)


def load_state(session: str) -> dict[str, Any]:
    try:
        s = json.loads(state_file(session).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(s, dict) or time.time() - float(s.get("ts") or 0) > STATE_TTL_SECONDS:
        return {}
    return s


def save_state(session: str, state: dict[str, Any]) -> None:
    state["ts"] = time.time()
    try:
        state_file(session).write_text(json.dumps(state, separators=(",", ":")) + "\n")
    except OSError:
        pass


# ── target identity ─────────────────────────────────────────────────────────
def target_of(tool: str, inp: dict[str, Any]) -> str:
    """What is being attempted, at the grain a human would name it."""
    if not isinstance(inp, dict):
        inp = {}
    low = tool.lower()

    if low in ("edit", "write", "multiedit", "notebookedit"):
        return "file %s" % (inp.get("file_path") or inp.get("path") or "?")

    if low == "bash":
        cmd = " ".join(str(inp.get("command") or "").split())
        host = URL_RE.search(cmd)
        stripped = CD_PREFIX_RE.sub("", cmd)
        head = re.split(r"[|;&]", stripped)[0].strip()
        parts = head.split()
        if not parts:
            return "bash (empty)"
        binary = parts[0].split("/")[-1]
        shape = binary
        # Only a real subcommand widens the shape (`git push`, `bd list`). A path or
        # a flag does not: `ls -a ~/.claude/` and `cd X && ls ~/.claude/settings.json`
        # are the same attempt, and the audit measured 52 of 57 blocked commands being
        # retried in exactly that rephrased form.
        if len(parts) > 1 and SUBCOMMAND_RE.match(parts[1]):
            shape = "%s %s" % (binary, parts[1])
        if host:
            return "%s -> %s" % (shape, host.group(1))
        return "`%s`" % shape

    if low.startswith("mcp__"):
        first = ""
        for k in ("url", "channel_id", "task_id", "id", "query", "path", "name"):
            if inp.get(k):
                first = "%s=%s" % (k, str(inp[k])[:40])
                break
        return "%s %s".strip() % (tool, first)

    first_arg = ""
    for k, v in (inp.items() if isinstance(inp, dict) else []):
        if isinstance(v, (str, int, float)):
            first_arg = "%s=%s" % (k, str(v)[:40])
            break
    return ("%s %s" % (tool, first_arg)).strip()


def edit_fingerprint(tool: str, inp: dict[str, Any]) -> str | None:
    """Identity of an edit's *content*, to catch the same change re-applied."""
    if tool.lower() not in ("edit", "multiedit", "write", "notebookedit"):
        return None
    if not isinstance(inp, dict):
        return None
    blob = json.dumps(
        {k: inp.get(k) for k in ("file_path", "old_string", "new_string", "content", "edits")},
        sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ── failure detection ───────────────────────────────────────────────────────
def result_text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return " ".join(result_text(x) for x in obj)
    if isinstance(obj, dict):
        parts = []
        for k in ("content", "text", "stdout", "stderr", "error", "message", "result"):
            v = obj.get(k)
            if v:
                parts.append(result_text(v))
        return " ".join(parts)
    return ""


def is_failure(is_error_flag: bool, text: str, extra: dict[str, Any] | None = None) -> bool:
    if is_error_flag:
        return True
    extra = extra or {}
    if extra.get("interrupted"):
        return True
    for key in ("exit_code", "exitCode", "returncode", "code"):
        v = extra.get(key)
        if isinstance(v, int) and v != 0:
            return True
    head = " ".join(text.split())[:600]
    return bool(head and ERROR_TEXT_RE.search(head))


# ── the turn ────────────────────────────────────────────────────────────────
def read_records(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def _blocks(rec: dict[str, Any]) -> list[Any]:
    msg = rec.get("message")
    c = msg.get("content") if isinstance(msg, dict) else rec.get("content")
    if isinstance(c, list):
        return c
    if isinstance(c, str):
        return [{"type": "text", "text": c}]
    return []


def is_human_turn(rec: dict[str, Any]) -> bool:
    if rec.get("type") not in ("user", "human") or rec.get("isMeta"):
        return False
    msg = rec.get("message")
    content = msg.get("content") if isinstance(msg, dict) else rec.get("content")
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        text = " ".join(str(b.get("text", "")) for b in content
                        if isinstance(b, dict) and b.get("type") == "text")
    elif isinstance(content, str):
        text = content
    else:
        return False
    if not text.strip():
        return False
    if text.lstrip().startswith(("<local-command", "<command-name", "<system-reminder",
                                "Caveat:", "<user-prompt-submit-hook")):
        return False
    return True


def attempts_this_turn(records: list[dict[str, Any]]) -> list[tuple[str, str | None, bool]]:
    """[(target, edit_fingerprint, failed)] in order, since JD last spoke."""
    start = 0
    for i in range(len(records) - 1, -1, -1):
        if is_human_turn(records[i]):
            start = i + 1
            break

    uses: dict[str, tuple[str, dict[str, Any]]] = {}
    order: list[str] = []
    out: list[tuple[str, str | None, bool]] = []

    for rec in records[start:]:
        if rec.get("type") == "assistant":
            for b in _blocks(rec):
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    uses[str(b.get("id"))] = (str(b.get("name") or ""), b.get("input") or {})
                    order.append(str(b.get("id")))
        elif rec.get("type") in ("user", "human"):
            for b in _blocks(rec):
                if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                    continue
                uid = str(b.get("tool_use_id"))
                name, inp = uses.get(uid, ("", {}))
                if not name:
                    continue
                text = result_text(b.get("content"))
                extra = rec.get("toolUseResult") if isinstance(rec.get("toolUseResult"), dict) else {}
                if not text:
                    text = result_text(extra)
                out.append((target_of(name, inp),
                            edit_fingerprint(name, inp),
                            is_failure(bool(b.get("is_error")), text, extra)))
    return out


def consecutive_failures(attempts: list[tuple[str, str | None, bool]], target: str) -> int:
    """Trailing failures on this target. A success on it zeroes the count."""
    count = 0
    for tgt, _fp, failed in attempts:
        if tgt != target:
            continue
        count = count + 1 if failed else 0
    return count


def repeated_edit_count(attempts: list[tuple[str, str | None, bool]], fp: str | None) -> int:
    if not fp:
        return 0
    return sum(1 for _t, f, _ in attempts if f == fp)


# ── the message ─────────────────────────────────────────────────────────────
def handback(target: str, strikes: int, looping: bool) -> str:
    lead = ("The same edit has now been applied to %s %d times with nothing changing."
            % (target, strikes) if looping else
            "%d failed attempts on %s." % (strikes, target))
    return (
        "%s Stop.\n\n"
        "Report, in this order:\n"
        "  1. What you tried — the attempts, one line each, with the exact error.\n"
        "  2. What that means — the actual blocker, not a restatement of the error.\n"
        "  3. Hand the next step to JD: the exact command he runs or the exact click he\n"
        "     makes, ready to paste. If there is a cheaper route that drops the blocked\n"
        "     requirement entirely, name it and what it costs.\n\n"
        "Do not attempt a third time unless he says so. Every measured loop of this shape\n"
        "ended with JD dropping the requirement or doing it himself in under a minute "
        "(13ce35fc, 003606ac, 904c34bc) — never with the next attempt working."
        % lead
    )


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    if os.environ.get("TWO_STRIKE", "").lower() in ("off", "0", "false", "no"):
        return 0

    data = payload_in()
    event = data.get("hook_event_name") or data.get("hookEventName") or "PostToolUse"
    if event != "PostToolUse":
        return 0

    tool = str(data.get("tool_name") or "")
    if not tool:
        return 0
    inp = data.get("tool_input") or {}
    target = target_of(tool, inp)
    fp = edit_fingerprint(tool, inp)
    session = str(data.get("session_id") or data.get("sessionId") or "unknown")

    tpath = data.get("transcript_path") or data.get("transcriptPath")
    attempts = attempts_this_turn(read_records(Path(str(tpath)).expanduser())) if tpath else []

    # The call that just happened may not be in the transcript yet; judge it from
    # the payload and append it, so the second strike fires on the second failure
    # rather than the third.
    resp = data.get("tool_response")
    extra = resp if isinstance(resp, dict) else {}
    just_failed = is_failure(
        bool(extra.get("is_error") or extra.get("isError") or data.get("is_error")),
        result_text(resp), extra)
    if not attempts or attempts[-1][0] != target or attempts[-1][2] != just_failed:
        attempts = attempts + [(target, fp, just_failed)]

    strikes = consecutive_failures(attempts, target)
    looping = False
    if strikes < STRIKE_LIMIT:
        repeats = repeated_edit_count(attempts, fp)
        if repeats >= SAME_EDIT_LIMIT:
            strikes, looping = repeats, True

    if strikes < STRIKE_LIMIT:
        return 0

    state = load_state(session)
    warned = state.get("warned") or {}
    key = "%s|%s" % ("loop" if looping else "fail", target)
    if int(warned.get(key, 0)) >= strikes:
        return 0                      # already said it for this count; do not nag
    warned[key] = strikes
    save_state(session, {"warned": warned})

    emit_context(handback(target, strikes, looping))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — never wedge a session
        sys.stderr.write("two-strike: internal error, continuing: %s\n" % exc)
        sys.exit(0)
