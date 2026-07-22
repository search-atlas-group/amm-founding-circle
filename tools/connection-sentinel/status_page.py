"""Renders the tiny local status board -- one glance, green/red per
connection. Self-contained HTML, no build step, no server.

Design: shares the repo-wide Founding Circle theme (`theme.py`, vendored
into this tool so it stays runnable standalone) -- KPI strip up top
(healthy / down / total), one status-pill table below.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from theme import kpi_strip, page, pill

# Kept for back-compat with anything reading connections.state.json/tests
# that checks the raw row status class -- the semantic OK/DOWN class stays
# on the <tr> even though the visible pill now carries the styling.
_ROW_CLASS = {True: "ok", False: "down"}


def render(state: dict) -> str:
    conns = (state or {}).get("connections", {}) or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    names = sorted(conns)
    healthy_count = sum(1 for n in names if bool((conns[n] or {}).get("healthy")))
    down_count = len(names) - healthy_count

    rows = []
    for name in names:
        c = conns[name] or {}
        healthy = bool(c.get("healthy"))
        row_class = _ROW_CLASS[healthy]
        status_pill = pill("Healthy", "good") if healthy else pill("Down", "bad")
        rows.append(
            f"<tr class='{row_class}'>"
            f"<td>{html.escape(name)}</td>"
            f"<td>{status_pill}</td>"
            f"<td>{html.escape(str(c.get('detail', '')))}</td>"
            f"<td class='mono'>{html.escape(str(c.get('checked_at', '')))}</td>"
            f"</tr>"
        )

    kpis = kpi_strip(
        [
            {"label": "Healthy", "value": str(healthy_count), "trend": "good" if healthy_count else None},
            {"label": "Down", "value": str(down_count), "trend": "bad" if down_count else "good"},
            {"label": "Total watched", "value": str(len(names))},
        ]
    )

    if rows:
        table_html = (
            "<div class='fc-table-wrap'><table class='fc-table'>"
            "<thead><tr><th>Connection</th><th>Status</th><th>Detail</th><th>Last checked</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
    else:
        table_html = "<p class='fc-empty'>No connections configured yet.</p>"

    body = (
        '<style>table.fc-table tr.down td{background:var(--fc-bad-soft)}</style>'
        f'<div class="fc-card"><h2>Watched connections</h2>{table_html}</div>'
    )

    return page(
        title="Connection Sentinel",
        subtitle=f"Generated {now} — refreshes every check cycle.",
        kpis_html=kpis,
        body_html=body,
        footer_note="Connection Sentinel · AMM Founding Circle",
    )


def write(path: str, state: dict) -> None:
    with open(path, "w") as f:
        f.write(render(state))
