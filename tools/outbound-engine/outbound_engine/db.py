"""SQLite state for the outbound-engine pipeline.

Everything the pipeline does lands here first, so:
  - the review queue survives a restart (per spec: "State in a local SQLite file
    so the pipeline is resumable and the review queue survives restarts"),
  - every stage is idempotent (re-running `signals` never double-adds the same
    Visual Visitor hit, keyed on (source, external_id)),
  - the weekly report is just a set of queries over `events`.

No ORM — this is small and stable enough that plain sqlite3 + explicit SQL is
easier to audit than a dependency.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .models import Draft, EnrichedProspect, LoadResult, VisitorSignal

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    company_name TEXT NOT NULL,
    company_domain TEXT NOT NULL,
    page_path TEXT,
    visit_count INTEGER DEFAULT 1,
    referrer_type TEXT DEFAULT 'unknown',
    last_seen_at TEXT,
    contact_name TEXT,
    contact_role TEXT,
    contact_email TEXT,
    icp_score REAL,
    icp_verdict TEXT,
    signal_reason TEXT,
    needs_manual_contact_lookup INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    voice_notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending_review',
    reviewed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_loads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    draft_id INTEGER NOT NULL REFERENCES drafts(id),
    mode TEXT NOT NULL,
    campaign_name TEXT,
    payload_json TEXT NOT NULL,
    loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    prospect_id INTEGER,
    ts TEXT NOT NULL,
    meta_json TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT,
    count_in INTEGER DEFAULT 0,
    count_out INTEGER DEFAULT 0,
    notes TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Thin wrapper around one sqlite3 connection to the pipeline's state DB."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def log_event(self, event_type: str, prospect_id: Optional[int] = None, meta: Optional[dict] = None) -> None:
        self.conn.execute(
            "INSERT INTO events (event_type, prospect_id, ts, meta_json) VALUES (?, ?, ?, ?)",
            (event_type, prospect_id, _now(), json.dumps(meta or {})),
        )
        self.conn.commit()

    @contextmanager
    def track_run(self, stage: str) -> Iterator[dict]:
        """Context manager that records a `runs` row (start/finish, in/out counts,
        ok/error) around a pipeline stage — this is the resumability + heartbeat
        primitive: a stalled/failed stage is visible in the DB, not just stdout."""
        counters = {"count_in": 0, "count_out": 0}
        cur = self.conn.execute(
            "INSERT INTO runs (stage, started_at, status) VALUES (?, ?, 'running')",
            (stage, _now()),
        )
        run_id = cur.lastrowid
        self.conn.commit()
        status = "ok"
        try:
            yield counters
        except Exception:
            status = "error"
            raise
        finally:
            self.conn.execute(
                "UPDATE runs SET finished_at = ?, status = ?, count_in = ?, count_out = ? WHERE id = ?",
                (_now(), status, counters["count_in"], counters["count_out"], run_id),
            )
            self.conn.commit()

    # ---- prospects ----

    def upsert_signal(self, signal: VisitorSignal) -> tuple[int, bool]:
        """Insert a raw signal as a 'new' prospect. Returns (prospect_id, created).
        Idempotent on (source, external_id) — re-running `signals` never double-adds."""
        existing = self.conn.execute(
            "SELECT id FROM prospects WHERE source = ? AND external_id = ?",
            (signal.source, signal.external_id),
        ).fetchone()
        if existing:
            return existing["id"], False

        now = _now()
        cur = self.conn.execute(
            """INSERT INTO prospects
               (source, external_id, company_name, company_domain, page_path, visit_count,
                referrer_type, last_seen_at, contact_name, contact_role, contact_email,
                status, raw_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)""",
            (
                signal.source, signal.external_id, signal.company_name, signal.company_domain,
                signal.page_path, signal.visit_count, signal.referrer_type, signal.last_seen_at,
                signal.contact_name, signal.contact_role, signal.contact_email,
                json.dumps(signal.raw), now, now,
            ),
        )
        self.conn.commit()
        prospect_id = cur.lastrowid
        self.log_event("prospect_added", prospect_id, {"source": signal.source})
        return prospect_id, True

    def record_enrichment(self, prospect_id: int, enriched: EnrichedProspect) -> None:
        self.conn.execute(
            """UPDATE prospects SET icp_score = ?, icp_verdict = ?, signal_reason = ?,
               needs_manual_contact_lookup = ?, status = 'enriched', updated_at = ?
               WHERE id = ?""",
            (
                enriched.icp_score, enriched.icp_verdict, enriched.signal_reason,
                int(enriched.needs_manual_contact_lookup), _now(), prospect_id,
            ),
        )
        self.conn.commit()
        self.log_event("enriched", prospect_id, {
            "icp_score": enriched.icp_score, "icp_verdict": enriched.icp_verdict,
        })

    def get_prospect(self, prospect_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()

    def list_prospects(self, status: Optional[str] = None) -> list[sqlite3.Row]:
        if status:
            return self.conn.execute(
                "SELECT * FROM prospects WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
        return self.conn.execute("SELECT * FROM prospects ORDER BY id").fetchall()

    # ---- drafts ----

    def add_draft(self, draft: Draft) -> int:
        cur = self.conn.execute(
            """INSERT INTO drafts (prospect_id, subject, body, voice_notes, status, created_at)
               VALUES (?, ?, ?, ?, 'pending_review', ?)""",
            (draft.prospect_id, draft.subject, draft.body, draft.voice_notes, _now()),
        )
        self.conn.execute(
            "UPDATE prospects SET status = 'drafted', updated_at = ? WHERE id = ?",
            (_now(), draft.prospect_id),
        )
        self.conn.commit()
        draft_id = cur.lastrowid
        self.log_event("drafted", draft.prospect_id, {"draft_id": draft_id})
        return draft_id

    def get_draft(self, draft_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()

    def list_drafts(self, status: Optional[str] = "pending_review") -> list[sqlite3.Row]:
        if status:
            return self.conn.execute(
                "SELECT * FROM drafts WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
        return self.conn.execute("SELECT * FROM drafts ORDER BY id").fetchall()

    def review_draft(self, draft_id: int, decision: str, edited_body: Optional[str] = None,
                      edited_subject: Optional[str] = None) -> None:
        """decision: 'approve' | 'edit' | 'skip' | 'reject'."""
        valid = {"approve", "edit", "skip", "reject"}
        if decision not in valid:
            raise ValueError(f"decision must be one of {valid}, got {decision!r}")

        draft = self.get_draft(draft_id)
        if draft is None:
            raise ValueError(f"no draft with id {draft_id}")

        new_status = {"approve": "approved", "edit": "approved", "skip": "skipped", "reject": "rejected"}[decision]
        subject = edited_subject if edited_subject is not None else draft["subject"]
        body = edited_body if edited_body is not None else draft["body"]

        self.conn.execute(
            "UPDATE drafts SET status = ?, subject = ?, body = ?, reviewed_at = ? WHERE id = ?",
            (new_status, subject, body, _now(), draft_id),
        )
        prospect_status = "approved" if new_status == "approved" else new_status
        self.conn.execute(
            "UPDATE prospects SET status = ?, updated_at = ? WHERE id = ?",
            (prospect_status, _now(), draft["prospect_id"]),
        )
        self.conn.commit()
        event_name = {
            "approve": "draft_approved", "edit": "draft_edited",
            "skip": "draft_skipped", "reject": "draft_rejected",
        }[decision]
        self.log_event(event_name, draft["prospect_id"], {"draft_id": draft_id})

    # ---- campaign loads ----

    def record_load(self, result: LoadResult) -> int:
        cur = self.conn.execute(
            """INSERT INTO campaign_loads (prospect_id, draft_id, mode, campaign_name, payload_json, loaded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (result.prospect_id, result.draft_id, result.mode, result.campaign_name,
             json.dumps(result.payload), _now()),
        )
        self.conn.execute(
            "UPDATE prospects SET status = 'loaded', updated_at = ? WHERE id = ?",
            (_now(), result.prospect_id),
        )
        self.conn.commit()
        load_id = cur.lastrowid
        self.log_event("loaded", result.prospect_id, {"mode": result.mode, "campaign_name": result.campaign_name})
        return load_id

    # ---- reporting ----

    def event_counts_since(self, since_iso: str) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT event_type, COUNT(*) AS n FROM events WHERE ts >= ? GROUP BY event_type",
            (since_iso,),
        ).fetchall()
        return {r["event_type"]: r["n"] for r in rows}

    def prospects_by_status_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM prospects GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def recent_loads(self, since_iso: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM campaign_loads WHERE loaded_at >= ? ORDER BY loaded_at DESC",
            (since_iso,),
        ).fetchall()
