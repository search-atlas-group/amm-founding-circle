"""Shared design system for every Founding Circle tool report.

One CSS token set + a handful of layout helpers, adapted from this repo's
own `skills/html-reports/atlas` archetype (the "leadership BI dashboard"
shape: hairline cards, tabular numerals, letterspaced uppercase labels,
KPI strip, status pills). Reusing that in-repo, already-vetted system
instead of inventing a seventh look is the point: six tools sharing one
visual language is what actually reads as "one product" to a client,
and Atlas already matches JD's standing house style — light mode, one
muted accent, no gradients, no neon.

Every tool's own render module imports `THEME_CSS` + the helpers below
and swaps its ad hoc inline `<style>` block for this shared one. Business
logic (findings, verdicts, grades, margins) never moves — only the
markup/CSS layer does.
"""

from __future__ import annotations

import html as _html

THEME_CSS = """
:root {
  --fc-bg:            #f4f6f9;
  --fc-surface:       #ffffff;
  --fc-surface-alt:   #fafbfc;
  --fc-border:        #e3e6eb;
  --fc-border-strong: #d1d6de;
  --fc-rule:          #ecedf1;

  --fc-text:   #14181f;
  --fc-muted:  #525a68;
  --fc-subtle: #7a8290;

  --fc-accent:      #2453d6;
  --fc-accent-soft: #e7edfc;
  --fc-good:        #117a3d;
  --fc-good-soft:   #e4f3eb;
  --fc-warn:        #92590a;
  --fc-warn-soft:   #fbeed1;
  --fc-bad:         #b8302a;
  --fc-bad-soft:    #fbe3e1;

  --fc-radius:    8px;
  --fc-radius-sm: 4px;

  --fc-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  --fc-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body.fc {
  background: var(--fc-bg);
  color: var(--fc-text);
  font-family: var(--fc-font);
  font-size: 14.5px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
.fc-shell { max-width: 1040px; margin: 0 auto; padding: 32px 24px 56px; }
.fc-header { margin-bottom: 20px; }
.fc-header h1 { margin: 0; font-size: 23px; font-weight: 650; letter-spacing: -0.01em; }
.fc-subtitle { margin-top: 5px; color: var(--fc-muted); font-size: 13px; }

/* KPI strip */
.fc-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  background: var(--fc-surface);
  border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius);
  margin-bottom: 20px;
  overflow: hidden;
}
.fc-kpi {
  position: relative;
  padding: 15px 16px 16px;
  border-right: 1px solid var(--fc-rule);
  border-bottom: 1px solid var(--fc-rule);
  min-width: 0;
}
.fc-kpi::before {
  content: ""; position: absolute; left: 0; top: 10px; bottom: 10px;
  width: 3px; background: var(--fc-subtle); border-radius: 0 2px 2px 0;
}
.fc-kpi[data-trend="good"]::before { background: var(--fc-good); }
.fc-kpi[data-trend="bad"]::before  { background: var(--fc-bad); }
.fc-kpi[data-trend="warn"]::before { background: var(--fc-warn); }
.fc-kpi .fc-kpi-label {
  font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--fc-subtle);
}
.fc-kpi .fc-kpi-value {
  margin-top: 5px; font-size: 30px; font-weight: 650;
  font-variant-numeric: tabular-nums; letter-spacing: -0.01em; line-height: 1.1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.fc-kpi .fc-kpi-sub { margin-top: 5px; font-size: 12px; color: var(--fc-subtle); }

/* Cards / sections */
.fc-card {
  background: var(--fc-surface); border: 1px solid var(--fc-border);
  border-radius: var(--fc-radius); padding: 20px 22px; margin-bottom: 16px;
}
.fc-card h2 { margin: 0 0 12px; font-size: 16px; font-weight: 650; }
.fc-card h2 .fc-count { color: var(--fc-subtle); font-weight: 500; font-size: 13px; }
.fc-callout {
  border-left: 3px solid var(--fc-accent); background: var(--fc-accent-soft);
  padding: 12px 14px; border-radius: var(--fc-radius-sm); margin-bottom: 6px;
}
.fc-callout.good { border-left-color: var(--fc-good); background: var(--fc-good-soft); }
.fc-callout.warn { border-left-color: var(--fc-warn); background: var(--fc-warn-soft); }
.fc-callout.bad  { border-left-color: var(--fc-bad);  background: var(--fc-bad-soft); }

/* Table */
.fc-table-wrap { overflow-x: auto; }
table.fc-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.fc-table th {
  text-align: left; color: var(--fc-subtle); font-size: 10.5px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.06em;
  background: var(--fc-surface-alt); padding: 9px 10px; border-bottom: 1px solid var(--fc-border);
}
table.fc-table td {
  padding: 9px 10px; border-bottom: 1px solid var(--fc-rule); vertical-align: top;
}
table.fc-table tbody tr:last-child td { border-bottom: none; }
table.fc-table tbody tr:hover td { background: var(--fc-surface-alt); }
table.fc-table td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.fc-table td.mono { font-family: var(--fc-mono); font-size: 12px; color: var(--fc-muted); }
table.fc-table tr.fc-row-flag td { background: var(--fc-bad-soft); }
.fc-empty { color: var(--fc-subtle); text-align: center; padding: 22px 0; font-style: italic; }

/* Pills */
.fc-pill {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px;
  border-radius: 999px; font-size: 11.5px; font-weight: 650; white-space: nowrap;
}
.fc-pill.good  { background: var(--fc-good-soft);  color: var(--fc-good); }
.fc-pill.warn  { background: var(--fc-warn-soft);  color: var(--fc-warn); }
.fc-pill.bad   { background: var(--fc-bad-soft);   color: var(--fc-bad); }
.fc-pill.accent{ background: var(--fc-accent-soft); color: var(--fc-accent); }
.fc-pill.neutral{ background: var(--fc-surface-alt); color: var(--fc-muted); border: 1px solid var(--fc-border); }

.fc-note { color: var(--fc-muted); font-size: 12.5px; }
.fc-quote {
  border-left: 3px solid var(--fc-accent); padding: 6px 0 6px 12px; margin: 8px 0 0;
  color: var(--fc-text); font-style: italic;
}
.fc-footer { color: var(--fc-subtle); font-size: 12px; text-align: center; padding-top: 6px; }

@media (max-width: 640px) {
  .fc-shell { padding: 20px 14px 40px; }
  .fc-card { padding: 16px; }
  .fc-header h1 { font-size: 20px; }
  .fc-kpi .fc-kpi-value { font-size: 24px; }
}
@media print {
  body.fc { background: #fff; }
  .fc-card, .fc-kpis { box-shadow: none; }
}
"""


def esc(value) -> str:
    return _html.escape(str(value), quote=True)


def kpi(label: str, value: str, sub: str = "", trend: str | None = None) -> str:
    """One KPI tile. `trend`: "good" | "bad" | "warn" | None."""
    attr = f' data-trend="{trend}"' if trend else ""
    sub_html = f'<div class="fc-kpi-sub">{esc(sub)}</div>' if sub else ""
    return (
        f'<div class="fc-kpi"{attr}>'
        f'<div class="fc-kpi-label">{esc(label)}</div>'
        f'<div class="fc-kpi-value">{esc(value)}</div>'
        f"{sub_html}</div>"
    )


def kpi_strip(items: list[dict]) -> str:
    """items: [{"label":..., "value":..., "sub":..., "trend":...}, ...]"""
    if not items:
        return ""
    tiles = "".join(kpi(**item) for item in items)
    return f'<section class="fc-kpis">{tiles}</section>'


def pill(label: str, kind: str = "neutral") -> str:
    return f'<span class="fc-pill {kind}">{esc(label)}</span>'


def table(headers: list[str], rows_html: str, empty_text: str = "Nothing to show yet.") -> str:
    if not rows_html.strip():
        return f'<p class="fc-empty">{esc(empty_text)}</p>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    return (
        '<div class="fc-table-wrap"><table class="fc-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{rows_html}</tbody></table></div>"
    )


def card(title_html: str, body_html: str) -> str:
    return f'<div class="fc-card"><h2>{title_html}</h2>{body_html}</div>'


def page(
    *,
    title: str,
    subtitle: str,
    kpis_html: str = "",
    body_html: str,
    footer_note: str = "",
    doc_title: str | None = None,
) -> str:
    """Wraps a tool's report body in the shared shell. Returns a complete
    standalone HTML document (self-contained <style>, no external deps)."""
    footer = f'<div class="fc-footer">{esc(footer_note)}</div>' if footer_note else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(doc_title or title)}</title>
<style>{THEME_CSS}</style>
</head>
<body class="fc">
<main class="fc-shell">
  <header class="fc-header">
    <h1>{esc(title)}</h1>
    <p class="fc-subtitle">{esc(subtitle)}</p>
  </header>
  {kpis_html}
  {body_html}
  {footer}
</main>
</body>
</html>"""
