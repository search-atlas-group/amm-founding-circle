#!/usr/bin/env python3
"""Session spec-lock: the constraints JD stated survive everything.

WHY THIS EXISTS
---------------
The interaction audit (2026-09-05) found the second-biggest cost is intra-session
spec loss, and that compaction is NOT the cause: only 13 of 200 sessions compacted
at all, and inside those the post-compaction friction rate (32.6%) was *lower* than
the pre-compaction rate (34.0%). What actually happens is the agent forgets a
constraint JD stated 40 turns earlier, rebuilds without it, and JD re-states it:

  * `b521b304` — heat-map ordering fixed at t14, regressed by t122.
  * `b26ede4d` t83 — "seventh time I've asked".
  * `1544a376` — "STILL THE MAPS URL SHOULD BE OPTIONAL".
  * `d431be36` — the loop only ended at t70 when JD locked the format himself:
    "let's keep the card dashboard".

Three of the fourteen longest sessions, 49 wasted JD turns. The existing machinery
could not help: `_brain/sessions/*.md` records turn counts and byte sizes but no
state, PostCompact reloads only the `MEMORY.md` index, and the `next-session-handoff`
skill was invoked once in sixty days.

WHAT THIS DOES
--------------
One file per session, `_brain/sessions/<session_id>/spec-lock.md`, and three hooks
that keep it in front of the model:

  UserPromptSubmit  JD says something that sounds like a lock ("keep the", "don't
                    change", "from now on", "final", "that's the one", ...) → append
                    it, dated, under "## Locked by JD", and echo it straight back
                    into context so it binds on this turn too.
  PreCompact        tell the compactor, by name, what it may not drop: the lock file
                    verbatim, the current goal, open asks, what is blocked on JD,
                    artifact paths, and every correction JD made this session.
  SessionStart      on a resume or a post-compaction start, inject the file.
  PostCompact       same, immediately after the summary replaces the transcript.

The lock file is append-only and plain markdown. JD can read it, edit it, or delete
it, and nothing else depends on it existing.

CLI
---
  spec-lock.py --add "<text>"      append a lock by hand (this is what `/lock` runs)
  spec-lock.py --show              print the current session's lock file
  spec-lock.py --session <id>      target a specific session for either of those

NEVER RAISES. A hook that crashes on an odd payload costs more than the loss it
prevents, so every unexpected shape exits 0 silently.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BRAIN = Path(os.environ.get("HARNESS_BRAIN") or os.environ.get("SPEC_LOCK_BRAIN")
             or Path.home() / "Desktop" / "Agentic" / "_brain")
SESSIONS = BRAIN / "sessions"
LATEST = SESSIONS / ".latest-session"
HEADING = "## Locked by JD"
MAX_LOCK_CHARS = 300

# What a lock sounds like. Every phrase here was said by JD in a session the audit
# tracked, at the moment a loop stopped or should have. Deliberately generous: a
# false positive costs one line in a file nobody has to read; a false negative
# costs the b26ede4d loop, twenty-two turns.
LOCK_RE = re.compile(
    r"\bkeep the\b"
    r"|\bthis is the format\b"
    r"|\block\b|\blocked\b|\blocking\b"
    r"|\bdon'?t change\b|\bdo not change\b|\bstop changing\b"
    r"|\bthat'?s the one\b|\bthis is the one\b"
    r"|\bfrom now on\b"
    r"|\bfinal\b"
    r"|\buse this\b",
    re.I,
)

# Prompts that are not JD talking: slash-command envelopes, hook injections,
# pasted tool output. A lock harvested from one of those is noise in the file.
NOISE_PREFIXES = (
    "<local-command", "<command-name", "<command-message", "<system-reminder",
    "<user-prompt-submit-hook", "Caveat:",
)


def emit_context(event: str, text: str) -> None:
    """Both shapes on purpose: the top-level key is what this workspace's existing
    SessionStart/PostCompact hooks use, `hookSpecificOutput` is the documented one.
    A hook that only speaks half the protocol is a hook that silently does nothing."""
    print(json.dumps({
        "additionalContext": text,
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": text},
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


def session_id(data: dict[str, Any]) -> str:
    for key in ("session_id", "sessionId"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return re.sub(r"[^A-Za-z0-9_.-]", "_", v.strip())[:80]
    return ""


def lock_path(sid: str) -> Path:
    return SESSIONS / sid / "spec-lock.md"


def remember_latest(sid: str) -> None:
    """So `--add` (and therefore `/lock`) can find the session without being told."""
    try:
        SESSIONS.mkdir(parents=True, exist_ok=True)
        LATEST.write_text(sid + "\n")
    except OSError:
        pass


def resolve_session(explicit: str = "") -> str:
    if explicit:
        return re.sub(r"[^A-Za-z0-9_.-]", "_", explicit)[:80]
    env = os.environ.get("CLAUDE_SESSION_ID") or ""
    if env.strip():
        return re.sub(r"[^A-Za-z0-9_.-]", "_", env.strip())[:80]
    try:
        return LATEST.read_text().strip()
    except OSError:
        return ""


def read_lock(sid: str) -> str:
    try:
        return lock_path(sid).read_text()
    except OSError:
        return ""


def append_lock(sid: str, text: str, source: str = "prompt") -> bool:
    """Append one dated line. Returns False if it was already there.

    Append-only and deduplicated: `/lock <text>` and the UserPromptSubmit sniffer
    both fire on the same prompt, and the file has to stay readable by JD.
    """
    text = " ".join(str(text).split())[:MAX_LOCK_CHARS]
    if not text:
        return False
    path = lock_path(sid)
    existing = read_lock(sid)
    if text in existing:
        return False
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not existing:
            path.write_text(
                "# Spec lock — session %s\n\n"
                "Constraints JD stated in this session. Append-only. Re-read this before "
                "rebuilding any artifact named in it; a rebuild that drops one of these "
                "lines is the failure this file exists to stop.\n\n"
                "%s\n\n" % (sid, HEADING)
            )
            existing = path.read_text()
        if HEADING not in existing:
            with path.open("a") as fh:
                fh.write("\n%s\n\n" % HEADING)
        with path.open("a") as fh:
            fh.write("- **%s** (%s) — %s\n" % (stamp, source, text))
    except OSError:
        return False
    return True


# ── the three hook modes ────────────────────────────────────────────────────
def on_user_prompt(data: dict[str, Any]) -> int:
    sid = session_id(data)
    if not sid:
        return 0
    remember_latest(sid)
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return 0
    stripped = prompt.strip()
    if stripped.startswith(NOISE_PREFIXES):
        return 0
    if not LOCK_RE.search(stripped):
        return 0
    text = " ".join(stripped.split())[:MAX_LOCK_CHARS]
    added = append_lock(sid, text, source="auto")
    if not added:
        return 0
    emit_context(
        "UserPromptSubmit",
        "SPEC LOCK — recorded to _brain/sessions/%s/spec-lock.md:\n"
        "  \"%s\"\n"
        "Treat this as binding for the rest of the session. Do not rebuild any artifact "
        "it names without re-reading that file first. If you believe it is wrong, say so "
        "in one sentence — do not quietly drop it." % (sid, text),
    )
    return 0


PRECOMPACT_INSTRUCTIONS = """\
COMPACT PRESERVATION — these survive verbatim or the summary is wrong.

1. THE SPEC LOCK, word for word. Do not paraphrase, merge or shorten these lines:
{lock}
2. THE CURRENT GOAL in one sentence: what JD asked for, in his words, not a
   restatement of what has been done about it.
3. OPEN ASKS — everything JD asked for that has not shipped yet, each with the
   artifact path it lands in.
4. BLOCKED ON JD — the list of things waiting on him, each with the exact command,
   click or decision he owes. Keep this separate from what is ours to do.
5. ARTIFACT PATHS — every file, URL, ticket, channel and session id touched this
   session. Paths verbatim; a paraphrased path is a lost path.
6. EVERY CORRECTION JD MADE this session, in his words. A correction that gets
   summarised away comes back as the same correction, and that is the single
   largest cost measured in the interaction audit.

Drop tool output, retries, and reasoning about work already finished. Never drop
anything in 1-6.
"""


def on_pre_compact(data: dict[str, Any]) -> int:
    sid = session_id(data)
    body = read_lock(sid) if sid else ""
    if body.strip():
        lock_block = "\n".join("   " + ln for ln in body.strip().splitlines())
    else:
        lock_block = "   (no spec-lock file for this session — nothing recorded yet)"
    emit_context("PreCompact", PRECOMPACT_INSTRUCTIONS.format(lock=lock_block))
    return 0


def _inject(event: str, sid: str) -> int:
    body = read_lock(sid) if sid else ""
    if not body.strip():
        return 0
    emit_context(
        event,
        "SPEC LOCK for this session (_brain/sessions/%s/spec-lock.md) — JD stated these "
        "and they still bind. Re-read before rebuilding anything they name.\n\n%s"
        % (sid, body.strip()),
    )
    return 0


def on_session_start(data: dict[str, Any]) -> int:
    sid = session_id(data)
    if sid:
        remember_latest(sid)
    source = (data.get("source") or data.get("matcher") or "").lower()
    # A fresh startup has no session to restore; resume and compact do.
    if source and source not in ("resume", "compact", "clear"):
        return 0
    return _inject("SessionStart", sid)


def on_post_compact(data: dict[str, Any]) -> int:
    sid = session_id(data)
    if sid:
        remember_latest(sid)
    return _inject("PostCompact", sid)


HANDLERS = {
    "UserPromptSubmit": on_user_prompt,
    "PreCompact": on_pre_compact,
    "SessionStart": on_session_start,
    "PostCompact": on_post_compact,
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--add", default=None)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--session", default="")
    ap.add_argument("--runtime", default=None)   # tolerated, unused
    args, _unknown = ap.parse_known_args(argv)

    if args.add is not None:
        sid = resolve_session(args.session)
        if not sid:
            sys.stderr.write(
                "spec-lock: no session id. Pass --session <id>, or let a prompt go "
                "through the UserPromptSubmit hook first.\n")
            return 1
        added = append_lock(sid, args.add, source="/lock")
        print("%s _brain/sessions/%s/spec-lock.md" % (
            "locked ->" if added else "already locked in", sid))
        return 0

    if args.show:
        sid = resolve_session(args.session)
        body = read_lock(sid) if sid else ""
        sys.stdout.write(body or "(no spec-lock for session %r)\n" % sid)
        return 0

    data = payload_in()
    event = data.get("hook_event_name") or data.get("hookEventName") or ""
    handler = HANDLERS.get(event)
    if handler is None:
        return 0
    return handler(data)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001 — never wedge a session
        sys.stderr.write("spec-lock: internal error, continuing: %s\n" % exc)
        sys.exit(0)
