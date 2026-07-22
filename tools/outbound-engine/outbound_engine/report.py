"""
Weekly pipeline report — the spec's "weekly pipeline report: prospects added,
emails sent, opens/replies, calls booked, and the cost-comparison line."

NOTE ON "opens/replies/calls booked": those numbers only exist once real
Smartlead sending is live (this build never sends). In dry-run mode this
report honestly shows 0 / "n/a — dry-run build, no live sending yet" for those
fields rather than fabricating numbers, and clearly labels every dry-run load
as a "would-send" preview, not a sent count. Once a future build wires real
Smartlead reporting, replace the zeroed fields below with a real pull from
Smartlead's campaign-stats endpoint — the report's HTML shape doesn't need to
change, just where these numbers come from.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .db import Store
from .theme import kpi_strip, page, pill, table

def generate_weekly_report(store: Store, output_path: str | Path,
                            cost_comparison_note: Optional[str] = None,
                            days: int = 7) -> Path:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    events = store.event_counts_since(since)
    status_counts = store.prospects_by_status_counts()
    loads = store.recent_loads(since)

    period_line = (
        f"Covers the last {days} days, through "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."
    )

    prospects_added = events.get("prospect_added", 0)
    drafted = events.get("drafted", 0)
    approved = events.get("draft_approved", 0) + events.get("draft_edited", 0)
    skipped = events.get("draft_skipped", 0)
    rejected = events.get("draft_rejected", 0)
    loaded = events.get("loaded", 0)

    kpis = kpi_strip(
        [
            {"label": "Prospects surfaced", "value": str(prospects_added)},
            {"label": "Drafts written", "value": str(drafted)},
            {"label": "Approved by you", "value": str(approved), "trend": "good" if approved else None},
            {"label": "Skipped", "value": str(skipped)},
            {"label": "Rejected", "value": str(rejected), "trend": "bad" if rejected else None},
            {"label": "Loaded (dry-run)", "value": str(loaded)},
        ]
    )

    status_table = table(
        ["Status", "Count"],
        "".join(
            f"<tr><td>{html.escape(status)}</td><td class='num'>{count}</td></tr>"
            for status, count in sorted(status_counts.items())
        ),
        empty_text="No prospects yet.",
    )

    load_table = table(
        ["When", "Company", "Campaign", "Subject"],
        "".join(
            "<tr>"
            f"<td class='mono'>{html.escape(row['loaded_at'])}</td>"
            f"<td>{html.escape(_company_for_load(store, row['prospect_id']))}</td>"
            f"<td>{html.escape(row['campaign_name'] or '')}</td>"
            f"<td>{html.escape(_subject_for_draft(store, row['draft_id']))}</td>"
            "</tr>"
            for row in loads
        ),
        empty_text="No loads in this period.",
    )

    cost_line = cost_comparison_note or (
        "No cost-comparison figure configured yet — set `cost_comparison` in "
        "config/icp.yaml to show what this replaced in tool spend."
    )

    sending_metric_rows = "".join(
        f"<tr><td>{metric}</td><td>{pill('n/a — dry-run build, no live sending yet', 'neutral')}</td></tr>"
        for metric in ("Emails sent", "Opens", "Replies", "Calls booked")
    )
    # The literal delivered-metric text must appear exactly 4 times, unescaped
    # by any pill/markup wrapping — never fabricate a number for a stage this
    # dry-run build has not actually wired to live sending.
    sending_table = (
        "<div class='fc-table-wrap'><table class='fc-table'>"
        "<thead><tr><th>Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{sending_metric_rows}</tbody></table></div>"
    )

    body = "".join(
        [
            f'<div class="fc-card"><h2>Sending status</h2>'
            '<div class="fc-callout warn"><strong>Dry-run build.</strong> This report is from the '
            "pre-live version of the Outbound Engine — nothing has actually been sent to Smartlead yet. "
            "Opens, replies, and calls booked will read real once live sending is approved and wired.</div>"
            f"{sending_table}</div>",
            f'<div class="fc-card"><h2>Cost comparison</h2>'
            f'<div class="fc-callout">{html.escape(cost_line)}</div></div>',
            f'<div class="fc-card"><h2>Pipeline status <span class="fc-count">all-time, current DB</span></h2>{status_table}</div>',
            f'<div class="fc-card"><h2>Recent dry-run loads <span class="fc-count">would-send previews</span></h2>{load_table}</div>',
        ]
    )

    rendered = page(
        title="Outbound Engine — Weekly Pipeline Report",
        subtitle=period_line,
        kpis_html=kpis,
        body_html=body,
        footer_note=(
            f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
            "outbound-engine (dry-run build) · amm-founding-circle"
        ),
        doc_title="Outbound Engine — Weekly Report",
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered)
    return out


def _company_for_load(store: Store, prospect_id: int) -> str:
    row = store.get_prospect(prospect_id)
    return row["company_name"] if row else "(unknown)"


def _subject_for_draft(store: Store, draft_id: int) -> str:
    row = store.get_draft(draft_id)
    return row["subject"] if row else "(unknown)"
