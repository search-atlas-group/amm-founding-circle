"""HTML rendering for the Penny Dashboard — owner view + client-safe view.

Self-contained, single-file HTML: inline CSS, no JS framework, no external
assets, no third-party templating dependency (stdlib string formatting
only). Matches this repo's dependency-light bar and the sibling
`client-dashboard` skill's shape: opens by double-click, works emailed as
an attachment, can't call home.

Design intent (JD's standing house style): clean and minimal, not a
flashy SaaS demo — one muted accent color, generous whitespace, no
gradients or neon.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

_BASE_CSS = """
  :root {
    --bg: #fafafa; --panel: #ffffff; --border: #e4e4e7;
    --text: #18181b; --muted: #71717a; --accent: #2563eb;
    --danger: #b91c1c; --danger-bg: #fef2f2; --ok: #15803d;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 40px 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 15px; line-height: 1.5;
  }
  .wrap { max-width: 880px; margin: 0 auto; }
  h1 { font-size: 20px; font-weight: 600; margin: 0 0 4px; }
  .meta { color: var(--muted); font-size: 13px; margin-bottom: 28px; }
  table { width: 100%; border-collapse: collapse; background: var(--panel);
          border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 14px; }
  th { color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  tr:last-child td { border-bottom: none; }
  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .row-low { background: var(--danger-bg); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 500; }
  .badge-low { background: var(--danger-bg); color: var(--danger); }
  .badge-ok { color: var(--ok); }
  .note { margin-top: 24px; color: var(--muted); font-size: 13px; }
  ul.deliverables { margin: 8px 0 0; padding-left: 20px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 20px 24px; margin-bottom: 16px; }
  .stat { font-size: 22px; margin-top: 6px; }
"""


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _esc(value) -> str:
    return html.escape(str(value))


def render_owner_view(rows: list, period: str, threshold_pct: float, trends: dict) -> str:
    """The private, internal margin table — billed/cost/margin per client,
    loss-making clients sorted to the top. NEVER share this file with a
    client; it contains internal cost/margin data by design."""
    sorted_rows = sorted(rows, key=lambda r: r.margin_pct)
    body_rows = []
    for r in sorted_rows:
        trend = trends.get(r.client_id)
        trend_str = "—" if trend is None else f"{trend:+.1f} pts"
        low = r.margin_pct <= threshold_pct
        row_class = ' class="row-low"' if low else ""
        badge = (
            f'<span class="badge badge-low">below {threshold_pct:.0f}%</span>'
            if low
            else '<span class="badge badge-ok">healthy</span>'
        )
        body_rows.append(
            f"<tr{row_class}>"
            f"<td>{_esc(r.client_id)}</td>"
            f"<td class='num'>${r.billed_usd:,.0f}</td>"
            f"<td class='num'>${r.cost_usd:,.0f}</td>"
            f"<td class='num'>${r.margin_usd:,.0f}</td>"
            f"<td class='num'>{r.margin_pct:.1f}%</td>"
            f"<td class='num'>{trend_str}</td>"
            f"<td>{badge}</td>"
            "</tr>"
        )
    body_html = "".join(body_rows) or '<tr><td colspan="7">No clients configured yet.</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Penny Dashboard — Owner View — {_esc(period)}</title>
<style>{_BASE_CSS}</style></head>
<body><div class="wrap">
  <h1>Penny Dashboard — Owner View</h1>
  <div class="meta">Period: {_esc(period)} &middot; Generated {_now_stamp()} &middot; INTERNAL ONLY, never share this file</div>
  <table>
    <thead><tr><th>Client</th><th class='num'>Billed</th><th class='num'>Cost</th>
    <th class='num'>Margin $</th><th class='num'>Margin %</th><th class='num'>Trend</th><th>Status</th></tr></thead>
    <tbody>{body_html}</tbody>
  </table>
  <div class="note">Loss-making / low-margin clients are sorted to the top and highlighted. This file contains internal cost and margin data — it is never safe to send to a client.</div>
</div></body></html>"""


def render_client_safe_view(view) -> str:
    """A single client's client-safe page.

    Structurally cannot contain margin, cost, tool names, or any other
    client's data — the only way to reach this function is through
    `visibility.build_client_safe_view`, whose return type has no
    attribute for those fields at all.
    """
    deliverables_html = ""
    if view.deliverables:
        items = "".join(f"<li>{_esc(d)}</li>" for d in view.deliverables)
        deliverables_html = (
            f'<div class="card"><strong>What we shipped this period</strong>'
            f'<ul class="deliverables">{items}</ul></div>'
        )

    spend_html = ""
    if view.ad_spend_usd is not None:
        spend_html = (
            '<div class="card"><strong>Ad spend this period</strong>'
            f'<div class="stat">${view.ad_spend_usd:,.0f}</div></div>'
        )

    results_html = ""
    if view.results_note:
        results_html = (
            f'<div class="card"><strong>Results</strong>'
            f'<div style="margin-top:6px;">{_esc(view.results_note)}</div></div>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{_esc(view.client_name)} — {_esc(view.period)}</title>
<style>{_BASE_CSS}</style></head>
<body><div class="wrap">
  <h1>{_esc(view.client_name)}</h1>
  <div class="meta">Data through {_esc(view.period)}</div>
  {spend_html}
  {deliverables_html}
  {results_html}
</div></body></html>"""
