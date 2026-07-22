"""HTML rendering for the Penny Dashboard — owner view + client-safe view.

Self-contained, single-file HTML: inline CSS, no JS framework, no external
assets, no third-party templating dependency (stdlib string formatting
only). Matches this repo's dependency-light bar and the sibling
`client-dashboard` skill's shape: opens by double-click, works emailed as
an attachment, can't call home.

Design: shares the repo-wide Founding Circle theme (`theme.py`, vendored
into this tool so it stays runnable standalone) — same KPI-strip /
pill / hairline-card language as every other founding-circle tool.

STRUCTURAL ABSENCE, unchanged: `render_client_safe_view` only ever
receives a `ClientSafeView` (from `visibility.build_client_safe_view`),
whose type has no margin/cost/other-client attribute at all. Re-skinning
this file only ever touches markup/CSS — it must never grow a code path
that reads margin/cost data into the client-safe function.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .theme import esc, kpi_strip, page, pill, table


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def render_owner_view(rows: list, period: str, threshold_pct: float, trends: dict) -> str:
    """The private, internal margin table — billed/cost/margin per client,
    loss-making clients sorted to the top. NEVER share this file with a
    client; it contains internal cost/margin data by design."""
    sorted_rows = sorted(rows, key=lambda r: r.margin_pct)
    below_threshold = sum(1 for r in sorted_rows if r.margin_pct <= threshold_pct)
    total_billed = sum(r.billed_usd for r in sorted_rows)
    total_margin = sum(r.margin_usd for r in sorted_rows)
    avg_margin_pct = (total_margin / total_billed * 100) if total_billed else 0.0

    kpis = kpi_strip(
        [
            {"label": "Clients", "value": str(len(sorted_rows))},
            {"label": "Total billed", "value": f"${total_billed:,.0f}"},
            {"label": "Avg margin", "value": f"{avg_margin_pct:.1f}%", "trend": "good" if avg_margin_pct >= threshold_pct else "bad"},
            {
                "label": f"Below {threshold_pct:.0f}%",
                "value": str(below_threshold),
                "trend": "bad" if below_threshold else "good",
            },
        ]
    )

    body_rows = []
    for r in sorted_rows:
        trend = trends.get(r.client_id)
        trend_str = "—" if trend is None else f"{trend:+.1f} pts"
        low = r.margin_pct <= threshold_pct
        row_class = " class='fc-row-flag'" if low else ""
        badge = pill(f"below {threshold_pct:.0f}%", "bad") if low else pill("healthy", "good")
        body_rows.append(
            f"<tr{row_class}>"
            f"<td>{esc(r.client_id)}</td>"
            f"<td class='num'>${r.billed_usd:,.0f}</td>"
            f"<td class='num'>${r.cost_usd:,.0f}</td>"
            f"<td class='num'>${r.margin_usd:,.0f}</td>"
            f"<td class='num'>{r.margin_pct:.1f}%</td>"
            f"<td class='num'>{trend_str}</td>"
            f"<td>{badge}</td>"
            "</tr>"
        )
    table_html = table(
        ["Client", "Billed", "Cost", "Margin $", "Margin %", "Trend", "Status"],
        "".join(body_rows),
        empty_text="No clients configured yet.",
    )

    body = (
        '<div class="fc-card"><h2>Client margin — '
        f'<span class="fc-count">period {esc(period)}</span></h2>'
        f"{table_html}"
        '<p class="fc-note" style="margin-top:12px">Loss-making / low-margin clients are sorted '
        "to the top and highlighted. This file contains internal cost and margin data — it is "
        "never safe to send to a client.</p></div>"
    )

    return page(
        title="Penny Dashboard — Owner View",
        subtitle=f"Period: {period} · Generated {_now_stamp()} · INTERNAL ONLY, never share this file",
        kpis_html=kpis,
        body_html=body,
        footer_note="Penny Dashboard (owner view) · AMM Founding Circle",
        doc_title=f"Penny Dashboard — Owner View — {period}",
    )


def render_client_safe_view(view) -> str:
    """A single client's client-safe page.

    Structurally cannot contain margin, cost, tool names, or any other
    client's data — the only way to reach this function is through
    `visibility.build_client_safe_view`, whose return type has no
    attribute for those fields at all.
    """
    cards = []

    if view.ad_spend_usd is not None:
        cards.append(
            '<div class="fc-card"><h2>Ad spend this period</h2>'
            f'<div class="fc-kpi-value" style="font-size:32px">${view.ad_spend_usd:,.0f}</div></div>'
        )

    if view.deliverables:
        items = "".join(f"<li>{esc(d)}</li>" for d in view.deliverables)
        cards.append(
            '<div class="fc-card"><h2>What we shipped this period</h2>'
            f'<ul style="margin:8px 0 0;padding-left:20px">{items}</ul></div>'
        )

    if view.results_note:
        cards.append(f'<div class="fc-card"><h2>Results</h2><p>{esc(view.results_note)}</p></div>')

    body = "".join(cards) or '<p class="fc-empty">Nothing to show for this period yet.</p>'

    return page(
        title=view.client_name,
        subtitle=f"Data through {view.period}",
        body_html=body,
        footer_note="Prepared by your agency · AMM Founding Circle",
        doc_title=f"{view.client_name} — {view.period}",
    )
