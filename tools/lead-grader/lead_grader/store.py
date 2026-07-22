"""SQLite persistence for leads + grades — dedupe on re-import, the
digest's source data, and the raw material for the weekly trend view.

One local file per install (default ``leads.db``, gitignored). No server,
no login — matches the rest of the six-script family's "static/local
file, not a hosted service" security posture.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schema import Grade, Lead

_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    client TEXT NOT NULL,
    source TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    caller TEXT,
    duration_seconds INTEGER,
    transcript TEXT,
    recording_url TEXT,
    raw_json TEXT,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grades (
    lead_id TEXT PRIMARY KEY REFERENCES leads(id),
    client TEXT NOT NULL,
    grade TEXT NOT NULL,
    reason TEXT NOT NULL,
    quote TEXT,
    graded_at TEXT NOT NULL,
    model TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_client_occurred ON leads(client, occurred_at);
CREATE INDEX IF NOT EXISTS idx_grades_client_graded ON grades(client, graded_at);
"""


def connect(db_path: str | Path = "leads.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def upsert_lead(conn: sqlite3.Connection, lead: Lead) -> bool:
    """Insert a lead if it isn't already stored. Returns True if this was a
    new insert, False if the lead (by id) was already present — this is
    the dedupe guard for re-running import on an overlapping date range."""
    existing = conn.execute("SELECT 1 FROM leads WHERE id = ?", (lead.id,)).fetchone()
    if existing:
        return False
    conn.execute(
        """INSERT INTO leads
           (id, client, source, occurred_at, caller, duration_seconds,
            transcript, recording_url, raw_json, imported_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            lead.id,
            lead.client,
            lead.source,
            lead.occurred_at.isoformat(),
            lead.caller,
            lead.duration_seconds,
            lead.transcript,
            lead.recording_url,
            json.dumps(lead.raw, default=str),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return True


def save_grade(conn: sqlite3.Connection, grade: Grade) -> None:
    """Insert or overwrite the grade for a lead (re-grading replaces it)."""
    conn.execute(
        """INSERT INTO grades (lead_id, client, grade, reason, quote, graded_at, model)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(lead_id) DO UPDATE SET
               grade=excluded.grade, reason=excluded.reason, quote=excluded.quote,
               graded_at=excluded.graded_at, model=excluded.model""",
        (
            grade.lead_id,
            grade.client,
            grade.grade,
            grade.reason,
            grade.quote,
            grade.graded_at.isoformat(),
            grade.model,
        ),
    )
    conn.commit()


def _row_to_lead(row: sqlite3.Row) -> Lead:
    return Lead(
        id=row["id"],
        client=row["client"],
        source=row["source"],
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        caller=row["caller"],
        duration_seconds=row["duration_seconds"],
        transcript=row["transcript"] or "",
        recording_url=row["recording_url"],
        raw=json.loads(row["raw_json"]) if row["raw_json"] else {},
    )


def _row_to_grade(row: sqlite3.Row) -> Grade:
    return Grade(
        lead_id=row["lead_id"],
        client=row["client"],
        grade=row["grade"],
        reason=row["reason"],
        quote=row["quote"] or "",
        graded_at=datetime.fromisoformat(row["graded_at"]),
        model=row["model"] or "",
    )


def ungraded_leads(conn: sqlite3.Connection, client: str) -> list[Lead]:
    """Leads imported for a client that don't yet have a grade."""
    rows = conn.execute(
        """SELECT l.* FROM leads l
           LEFT JOIN grades g ON g.lead_id = l.id
           WHERE l.client = ? AND g.lead_id IS NULL
           ORDER BY l.occurred_at""",
        (client,),
    ).fetchall()
    return [_row_to_lead(r) for r in rows]


def leads_with_grades_for_date(
    conn: sqlite3.Connection, client: str, date: datetime
) -> list[tuple[Lead, Grade]]:
    """Every (Lead, Grade) pair for one client on one calendar date (UTC)."""
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)
    rows = conn.execute(
        """SELECT l.*, g.grade as g_grade, g.reason as g_reason, g.quote as g_quote,
                  g.graded_at as g_graded_at, g.model as g_model
           FROM leads l
           JOIN grades g ON g.lead_id = l.id
           WHERE l.client = ? AND l.occurred_at BETWEEN ? AND ?
           ORDER BY l.occurred_at""",
        (client, day_start.isoformat(), day_end.isoformat()),
    ).fetchall()

    results = []
    for row in rows:
        lead = _row_to_lead(row)
        grade = Grade(
            lead_id=row["id"],
            client=row["client"],
            grade=row["g_grade"],
            reason=row["g_reason"],
            quote=row["g_quote"] or "",
            graded_at=datetime.fromisoformat(row["g_graded_at"]),
            model=row["g_model"] or "",
        )
        results.append((lead, grade))
    return results


def trend(conn: sqlite3.Connection, client: str, days: int = 7) -> dict:
    """Grade counts per day for the last N days — the weekly lead-quality
    trend view (e.g. "LSA junk rate up to 40% this week")."""
    rows = conn.execute(
        """SELECT date(l.occurred_at) as day, g.grade as grade, COUNT(*) as n
           FROM leads l JOIN grades g ON g.lead_id = l.id
           WHERE l.client = ? AND date(l.occurred_at) >= date('now', ?)
           GROUP BY day, grade
           ORDER BY day""",
        (client, f"-{days} days"),
    ).fetchall()

    by_day: dict[str, dict[str, int]] = {}
    for row in rows:
        by_day.setdefault(row["day"], {}).setdefault(row["grade"], 0)
        by_day[row["day"]][row["grade"]] += row["n"]
    return by_day


def all_leads(conn: sqlite3.Connection, client: Optional[str] = None) -> list[Lead]:
    if client:
        rows = conn.execute("SELECT * FROM leads WHERE client = ? ORDER BY occurred_at", (client,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM leads ORDER BY occurred_at").fetchall()
    return [_row_to_lead(r) for r in rows]
