#!/usr/bin/env python3
"""Export one Hermes session as a Claude Code JSONL transcript.

The harness scripts (session beads, the claims gate, the two-strike rule, the
session log) were written against Claude's transcript file. Hermes keeps the
same facts in ~/.hermes/state.db and never writes that file. This renders the
rows into the shape those scripts already parse, so the scripts run unchanged.

Read-only against the database. Writes one file under
~/.hermes/cache/transcripts/<session_id>.jsonl and prints its path.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
DB = HOME / "state.db"
OUT_DIR = HOME / "cache" / "transcripts"


def _iso(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return ""


def _loads(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _tool_input(call: dict) -> dict:
    fn = call.get("function") or {}
    args = _loads(fn.get("arguments"))
    return args if isinstance(args, dict) else {}


def render(session_id: str) -> Path | None:
    if not DB.is_file() or not session_id:
        return None
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        session = con.execute("select cwd from sessions where id=?", (session_id,)).fetchone()
        rows = con.execute(
            "select role, content, tool_calls, tool_name, tool_call_id, timestamp "
            "from messages where session_id=? and active=1 order by id",
            (session_id,),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    if not rows:
        return None

    cwd = (session["cwd"] if session else "") or ""
    lines: list[str] = []
    for row in rows:
        role = row["role"]
        stamp = _iso(row["timestamp"])
        if role == "user":
            rec = {
                "type": "user",
                "cwd": cwd,
                "timestamp": stamp,
                "entrypoint": "cli",
                "message": {"role": "user", "content": row["content"] or ""},
            }
        elif role == "assistant":
            blocks: list[dict] = []
            if row["content"]:
                blocks.append({"type": "text", "text": row["content"]})
            for call in _loads(row["tool_calls"]) or []:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                blocks.append({
                    "type": "tool_use",
                    "id": call.get("id") or call.get("call_id") or "",
                    "name": fn.get("name") or "",
                    "input": _tool_input(call),
                })
            rec = {
                "type": "assistant",
                "cwd": cwd,
                "timestamp": stamp,
                "message": {"role": "assistant", "content": blocks},
            }
        elif role == "tool":
            text = row["content"] or ""
            parsed = _loads(text)
            is_error = bool(isinstance(parsed, dict) and (
                parsed.get("success") is False or parsed.get("is_error")
                or (isinstance(parsed.get("exit_code"), int) and parsed["exit_code"] != 0)
            ))
            rec = {
                "type": "user",
                "timestamp": stamp,
                "message": {"role": "user", "content": [{
                    "type": "tool_result",
                    "tool_use_id": row["tool_call_id"] or "",
                    "is_error": is_error,
                    "content": text,
                }]},
                "toolUseResult": parsed if isinstance(parsed, dict) else {"stdout": text},
            }
        else:
            continue
        lines.append(json.dumps(rec, ensure_ascii=False))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{session_id}.jsonl"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def main() -> int:
    session_id = sys.argv[1] if len(sys.argv) > 1 else ""
    if not session_id:
        raw = sys.stdin.read()
        try:
            session_id = str(json.loads(raw).get("session_id") or "")
        except (ValueError, AttributeError):
            session_id = ""
    dest = render(session_id)
    if dest:
        print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
