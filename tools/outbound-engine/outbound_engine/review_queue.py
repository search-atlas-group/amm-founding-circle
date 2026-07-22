"""
The review queue — the human control point the spec calls out as important:
"personalized drafts land in a 'approve/edit/skip' list before entering a
sequence — the member controls what actually gets sent under their name."

This module is deliberately split into pure, testable functions (`list_pending`,
`apply_decision`) and a thin interactive CLI loop (`run_interactive`) so the
approve/edit/skip logic can be exercised in tests without a terminal attached.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .db import Store


@dataclass
class QueueItem:
    draft_id: int
    prospect_id: int
    company_name: str
    contact_name: str
    icp_score: float
    icp_verdict: str
    signal_reason: str
    subject: str
    body: str


def list_pending(store: Store) -> list[QueueItem]:
    """Every draft still `pending_review`, joined with its prospect for display."""
    rows = store.conn.execute(
        """SELECT d.id AS draft_id, d.prospect_id, d.subject, d.body,
                  p.company_name, p.contact_name, p.icp_score, p.icp_verdict, p.signal_reason
           FROM drafts d JOIN prospects p ON p.id = d.prospect_id
           WHERE d.status = 'pending_review'
           ORDER BY p.icp_score DESC, d.id"""
    ).fetchall()
    return [
        QueueItem(
            draft_id=r["draft_id"], prospect_id=r["prospect_id"],
            company_name=r["company_name"], contact_name=r["contact_name"] or "(no named contact)",
            icp_score=r["icp_score"] or 0.0, icp_verdict=r["icp_verdict"] or "unscored",
            signal_reason=r["signal_reason"] or "", subject=r["subject"], body=r["body"],
        )
        for r in rows
    ]


def apply_decision(store: Store, draft_id: int, decision: str,
                    edited_subject: str | None = None, edited_body: str | None = None) -> None:
    """decision: 'approve' | 'edit' | 'skip' | 'reject'.
    'edit' requires at least one of edited_subject/edited_body."""
    if decision == "edit" and edited_subject is None and edited_body is None:
        raise ValueError("decision 'edit' requires edited_subject and/or edited_body")
    store.review_draft(draft_id, decision, edited_body=edited_body, edited_subject=edited_subject)


def run_interactive(store: Store) -> dict[str, int]:
    """Terminal loop: show each pending draft, take approve/edit/skip/reject/quit.
    Returns a summary count dict — used by run.py to print a final tally."""
    tally = {"approved": 0, "edited": 0, "skipped": 0, "rejected": 0}
    pending = list_pending(store)
    if not pending:
        print("Review queue is empty — nothing pending review.")
        return tally

    print(f"{len(pending)} draft(s) pending review.\n")
    for item in pending:
        print("=" * 72)
        print(f"{item.company_name}  —  {item.contact_name}  "
              f"[{item.icp_verdict} / {item.icp_score:.0f}]")
        print(f"Why: {item.signal_reason}")
        print("-" * 72)
        print(f"Subject: {item.subject}\n")
        print(item.body)
        print("=" * 72)
        choice = input("[a]pprove / [e]dit / [s]kip / [r]eject / [q]uit? ").strip().lower()

        if choice == "q":
            break
        if choice == "a":
            apply_decision(store, item.draft_id, "approve")
            tally["approved"] += 1
        elif choice == "e":
            new_subject = input(f"New subject [{item.subject}]: ").strip() or item.subject
            print("New body (end with a single '.' on its own line):")
            lines: list[str] = []
            while True:
                line = input()
                if line.strip() == ".":
                    break
                lines.append(line)
            new_body = "\n".join(lines) if lines else item.body
            apply_decision(store, item.draft_id, "edit", edited_subject=new_subject, edited_body=new_body)
            tally["edited"] += 1
        elif choice == "s":
            apply_decision(store, item.draft_id, "skip")
            tally["skipped"] += 1
        elif choice == "r":
            apply_decision(store, item.draft_id, "reject")
            tally["rejected"] += 1
        else:
            print("Not a recognized choice — treating as skip.")
            apply_decision(store, item.draft_id, "skip")
            tally["skipped"] += 1

    return tally
