"""SQLite month-over-month margin history for the Penny Dashboard.

One row per (client, period). This is what makes the "trend vs. last
month" column on the owner view possible without re-deriving history from
scratch every run.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS margin_history (
    client_id TEXT NOT NULL,
    period TEXT NOT NULL,
    billed_usd REAL NOT NULL,
    cost_usd REAL NOT NULL,
    margin_usd REAL NOT NULL,
    margin_pct REAL NOT NULL,
    computed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (client_id, period)
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def upsert_period(conn: sqlite3.Connection, financials) -> None:
    """Insert or overwrite this client's row for this period (re-running
    `generate` for the same month is idempotent, not additive)."""
    conn.execute(
        """
        INSERT INTO margin_history (client_id, period, billed_usd, cost_usd, margin_usd, margin_pct)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(client_id, period) DO UPDATE SET
            billed_usd=excluded.billed_usd,
            cost_usd=excluded.cost_usd,
            margin_usd=excluded.margin_usd,
            margin_pct=excluded.margin_pct,
            computed_at=datetime('now')
        """,
        (
            financials.client_id,
            financials.period,
            financials.billed_usd,
            financials.cost_usd,
            financials.margin_usd,
            financials.margin_pct,
        ),
    )
    conn.commit()


def previous_margin_pct(conn: sqlite3.Connection, client_id: str, before_period: str) -> float | None:
    """The most recent margin_pct strictly before `before_period`, if any."""
    row = conn.execute(
        """
        SELECT margin_pct FROM margin_history
        WHERE client_id = ? AND period < ?
        ORDER BY period DESC LIMIT 1
        """,
        (client_id, before_period),
    ).fetchone()
    return row[0] if row else None
