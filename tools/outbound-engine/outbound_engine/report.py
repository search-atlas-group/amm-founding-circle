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

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Outbound Engine — Weekly Report</title>
<style>
  :root {{
    --bg: #f7f8fb; --card: #ffffff; --ink: #17202a; --muted: #5d6b7a;
    --line: #d9e0e8; --accent: #2563eb; --good: #0f766e; --warn: #b45309;
  }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px 64px; }}
  header, section {{ background: var(--card); border:1px solid var(--line);
    border-radius: 8px; padding: 24px; margin-bottom: 18px; }}
  h1,h2,h3 {{ line-height:1.2; margin:0 0 12px; }}
  h1 {{ font-size: 30px; }} h2 {{ font-size: 20px; }}
  p {{ margin: 0 0 12px; }}
  .lede {{ color: var(--muted); font-size: 16px; }}
  .callout {{ border-left: 4px solid var(--accent); background:#eef4ff;
    padding: 14px 16px; border-radius: 6px; }}
  .warn-callout {{ border-left: 4px solid var(--warn); background:#fef3e2;
    padding: 14px 16px; border-radius: 6px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background: var(--card); }}
  th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align:left; vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 700; }}
  .stat-row {{ display:flex; gap:16px; flex-wrap:wrap; }}
  .stat {{ flex: 1 1 140px; background:#f2f5fa; border:1px solid var(--line); border-radius:8px;
    padding: 14px; }}
  .stat .n {{ font-size: 26px; font-weight: 700; }}
  .stat .label {{ color: var(--muted); font-size: 13px; }}
  footer {{ color: var(--muted); font-size: 13px; text-align:center; padding-top: 8px; }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Outbound Engine — Weekly Pipeline Report</h1>
    <p class="lede">{period_line}</p>
  </header>

  <section>
    <h2>This week</h2>
    <div class="stat-row">
      <div class="stat"><div class="n">{prospects_added}</div><div class="label">Prospects surfaced</div></div>
      <div class="stat"><div class="n">{drafted}</div><div class="label">Drafts written</div></div>
      <div class="stat"><div class="n">{approved}</div><div class="label">Approved by you</div></div>
      <div class="stat"><div class="n">{skipped}</div><div class="label">Skipped</div></div>
      <div class="stat"><div class="n">{rejected}</div><div class="label">Rejected</div></div>
      <div class="stat"><div class="n">{loaded}</div><div class="label">Loaded to Smartlead (dry-run)</div></div>
    </div>
  </section>

  <section>
    <h2>Sending status</h2>
    <div class="warn-callout">
      <strong>Dry-run build.</strong> This report is from the pre-live version of the
      Outbound Engine — nothing has actually been sent to Smartlead yet. Opens, replies,
      and calls booked will read real once live sending is approved and wired.
    </div>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Emails sent</td><td>n/a — dry-run build, no live sending yet</td></tr>
      <tr><td>Opens</td><td>n/a — dry-run build, no live sending yet</td></tr>
      <tr><td>Replies</td><td>n/a — dry-run build, no live sending yet</td></tr>
      <tr><td>Calls booked</td><td>n/a — dry-run build, no live sending yet</td></tr>
    </table>
  </section>

  <section>
    <h2>Cost comparison</h2>
    <p class="callout">{cost_line}</p>
  </section>

  <section>
    <h2>Pipeline status (all-time, current DB)</h2>
    <table>
      <tr><th>Status</th><th>Count</th></tr>
      {status_rows}
    </table>
  </section>

  <section>
    <h2>Recent dry-run loads (would-send previews)</h2>
    <table>
      <tr><th>When</th><th>Company</th><th>Campaign</th><th>Subject</th></tr>
      {load_rows}
    </table>
  </section>

  <footer>Generated {generated_at} · outbound-engine (dry-run build) · amm-founding-circle</footer>
</main>
</body>
</html>
"""


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

    status_rows = "".join(
        f"<tr><td>{html.escape(status)}</td><td>{count}</td></tr>"
        for status, count in sorted(status_counts.items())
    ) or "<tr><td colspan='2'>No prospects yet.</td></tr>"

    load_rows = "".join(
        f"<tr><td>{html.escape(row['loaded_at'])}</td>"
        f"<td>{html.escape(_company_for_load(store, row['prospect_id']))}</td>"
        f"<td>{html.escape(row['campaign_name'] or '')}</td>"
        f"<td>{html.escape(_subject_for_draft(store, row['draft_id']))}</td></tr>"
        for row in loads
    ) or "<tr><td colspan='4'>No loads in this period.</td></tr>"

    cost_line = cost_comparison_note or (
        "No cost-comparison figure configured yet — set `cost_comparison` in "
        "config/icp.yaml to show what this replaced in tool spend."
    )

    rendered = _TEMPLATE.format(
        period_line=html.escape(period_line),
        prospects_added=events.get("prospect_added", 0),
        drafted=events.get("drafted", 0),
        approved=events.get("draft_approved", 0) + events.get("draft_edited", 0),
        skipped=events.get("draft_skipped", 0),
        rejected=events.get("draft_rejected", 0),
        loaded=events.get("loaded", 0),
        status_rows=status_rows,
        load_rows=load_rows,
        cost_line=html.escape(cost_line),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
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
