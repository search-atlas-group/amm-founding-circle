#!/usr/bin/env python3
"""How this member actually works, read from their own machine. Nothing leaves.

    python3 onboarding/nova_practice.py

Counts and shapes only. It reads Hermes' session table for which models ran
and which tools got called, and the names of the harness, skill, and cron
directories. It does not read message text, so a client's name typed into a
chat cannot end up in the report. Pain is inferred from end reasons and from
repeated tool calls, never from a sentence.

The cohort file (onboarding/nova/cohort.md) is the only place a person's name
may come from. Nova may suggest one of those names against a counted weakness.
He may not invent one.
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
COHORT = HERE / "nova" / "cohort.md"
HOME = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))

# A tool name that means they are driving several models, not calling one.
ORCHESTRATION = {"delegate_task", "terminal", "cronjob", "execute_code"}
# Tools where repetition usually means they are fighting the machine.
FRICTION = {"terminal", "search_files", "read_file", "patch"}


def _dirs(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith("."))


def _cohort() -> list[dict]:
    """Lines of 'Name — strength'. Anything else is ignored."""
    if not COHORT.is_file():
        return []
    found = []
    for line in COHORT.read_text(encoding="utf-8").splitlines():
        body = line.strip()
        if not body.startswith("- "):
            continue
        body = body[2:].strip()
        if "—" not in body:
            continue
        name, _, strength = body.partition("—")
        name, strength = name.strip(), strength.strip()
        if name and strength:
            found.append({"name": name, "strength": strength})
    return found


def _sessions() -> dict:
    """Aggregates from Hermes' session table. Read only, and no message text."""
    db = HOME / "state.db"
    empty = {"sessions": 0, "models": [], "tools": [], "end_reasons": [], "sources": []}
    if not db.is_file():
        return empty
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0.5)
        conn.execute("PRAGMA query_only = ON")
    except sqlite3.Error:
        return empty
    try:
        models = conn.execute(
            "SELECT model, COUNT(*) FROM sessions WHERE model IS NOT NULL AND model != '' GROUP BY model ORDER BY 2 DESC LIMIT 8"
        ).fetchall()
        reasons = conn.execute(
            "SELECT COALESCE(end_reason, 'still_open'), COUNT(*) FROM sessions GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
        sources = conn.execute(
            "SELECT source, COUNT(*) FROM sessions GROUP BY 1 ORDER BY 2 DESC LIMIT 6"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        tools: list[tuple] = []
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "messages" in tables:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
            if "tool_name" in cols:
                tools = conn.execute(
                    "SELECT tool_name, COUNT(*) FROM messages WHERE tool_name IS NOT NULL AND tool_name != '' GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
                ).fetchall()
    except sqlite3.Error:
        return empty
    finally:
        conn.close()
    return {
        "sessions": total,
        "models": [{"name": name, "sessions": count} for name, count in models],
        "tools": [{"name": name, "calls": count} for name, count in tools],
        "end_reasons": [{"reason": reason, "sessions": count} for reason, count in reasons],
        "sources": [{"source": source, "sessions": count} for source, count in sources],
    }


def _friction(practice: dict) -> list[str]:
    """Plain observations a person can check. Each one cites the count it came from."""
    notes = []
    sessions = practice["sessions"]
    if sessions == 0:
        return ["No Hermes sessions yet, so there is nothing to say about how they work."]
    models = practice["models"]
    if len(models) >= 3:
        top = ", ".join(m["name"] for m in models[:3])
        notes.append(f"They run {len(models)} models. The ones used most are {top}.")
    elif models:
        notes.append("Almost all of their sessions use one model: " + models[0]["name"] + f" ({models[0]['sessions']} sessions).")
    tools = {t["name"]: t["calls"] for t in practice["tools"]}
    if tools:
        busiest = max(tools, key=tools.get)
        notes.append(f"The tool they call most is {busiest}, {tools[busiest]} times.")
        if ORCHESTRATION & set(tools):
            used = ", ".join(sorted(ORCHESTRATION & set(tools)))
            notes.append(f"They orchestrate rather than only chat: {used} shows up in their sessions.")
        repeats = {name: calls for name, calls in tools.items() if name in FRICTION and calls >= 15}
        if repeats:
            name, calls = max(repeats.items(), key=lambda item: item[1])
            notes.append(f"{name} was called {calls} times. That much repetition usually means something is hard to find or hard to land.")
    reasons = {r["reason"]: r["sessions"] for r in practice["end_reasons"]}
    cut = reasons.get("max_iterations", 0) + reasons.get("error", 0) + reasons.get("interrupted", 0)
    if sessions and cut / sessions >= 0.3:
        notes.append(f"{cut} of {sessions} sessions ended early or on an error. That is a pain point, not a preference.")
    return notes


def build() -> dict:
    sessions = _sessions()
    practice = {
        "hermes_home_present": HOME.is_dir(),
        "sessions": sessions["sessions"],
        "models": sessions["models"],
        "tools": sessions["tools"],
        "end_reasons": sessions["end_reasons"],
        "sources": sessions["sources"],
        "architecture": {
            "skill_dirs": _dirs(HOME / "skills"),
            "cron_jobs": len(list((HOME / "cron").glob("*.json"))) if (HOME / "cron").is_dir() else 0,
            "profiles": _dirs(HOME / "profiles"),
            "harness_dirs": _dirs(Path(os.environ.get("AMM_FOUNDING_CIRCLE_DIR") or HERE.parent) / "harnesses"),
        },
    }
    return {
        "practice": practice,
        "observations": _friction(practice),
        "cohort": _cohort(),
    }


def render(report: dict) -> str:
    lines = ["How they work — counts only, no session text"]
    practice = report["practice"]
    arch = practice["architecture"]
    lines.append(f"sessions: {practice['sessions']}")
    if practice["models"]:
        lines.append("models: " + ", ".join(f"{m['name']} ({m['sessions']})" for m in practice["models"]))
    if practice["tools"]:
        lines.append("tools: " + ", ".join(f"{t['name']} ({t['calls']})" for t in practice["tools"]))
    lines.append(
        f"shape: {len(arch['skill_dirs'])} skill groups, {arch['cron_jobs']} scheduled jobs, {len(arch['profiles'])} profiles, {len(arch['harness_dirs'])} harnesses in the repo"
    )
    lines.append("observed:")
    lines.extend(f"  - {note}" for note in report["observations"])
    if report["cohort"]:
        lines.append("people the program says are strong at something:")
        lines.extend(f"  - {p['name']} — {p['strength']}" for p in report["cohort"])
    else:
        lines.append("no cohort strengths are filled in, so Nova will not name a person.")
    return "\n".join(lines)


def main() -> int:
    print(render(build()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
