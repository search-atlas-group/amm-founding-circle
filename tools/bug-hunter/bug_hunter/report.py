"""Terminal + HTML report rendering, plus the one-line run summary.

Visual language matches the repo's shared `templates/report-template.html`
design tokens (light card UI, no neon) so this fits the same report family
called out in the master spec ("shares the report/HTML template family").
"""

from __future__ import annotations

import html as _html
from datetime import datetime, timezone

from .models import Finding, RunResult, Severity
from .theme import kpi_strip, page, pill, table

SEVERITY_ORDER = (Severity.CRITICAL, Severity.DEGRADING, Severity.COSMETIC, Severity.INFO)


def active_findings(result: RunResult) -> list[Finding]:
    """Non-suppressed findings, worst-first, grouped stably by client."""
    findings = [f for f in result.findings if not f.suppressed]
    return sorted(findings, key=lambda f: (-f.severity.rank, f.client, f.category, f.title))


def suppressed_findings(result: RunResult) -> list[Finding]:
    return [f for f in result.findings if f.suppressed]


def severity_counts(findings: list[Finding]) -> dict[Severity, int]:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] += 1
    return counts


def build_run_summary_line(result: RunResult) -> str:
    """Matches the spec's exact example shape:

    "Swept 9 sites, 14 campaigns — 2 critical issues found and flagged, 5 minor."
    """
    counts = severity_counts(active_findings(result))
    critical = counts[Severity.CRITICAL]
    minor = counts[Severity.DEGRADING] + counts[Severity.COSMETIC]

    parts = [f"Swept {result.sites_swept} site(s)"]
    if result.campaigns_checked:
        parts.append(f"{result.campaigns_checked} campaign(s)")
    summary = ", ".join(parts)

    if critical == 0 and minor == 0:
        return f"{summary} across {result.clients_swept} client(s) — nothing found. Clean sweep."
    return (
        f"{summary} across {result.clients_swept} client(s) — "
        f"{critical} critical issue(s) found and flagged, {minor} minor."
    )


def render_terminal(result: RunResult) -> str:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("BUG HUNTER — sweep report")
    lines.append("=" * 60)
    lines.append(build_run_summary_line(result))
    if result.skipped_checks:
        lines.append("")
        lines.append("Skipped checks (not configured):")
        for note in result.skipped_checks:
            lines.append(f"  - {note}")

    active = active_findings(result)
    if not active:
        lines.append("")
        lines.append("No active findings. \U0001f7e2")
    else:
        by_client: dict[str, list[Finding]] = {}
        for f in active:
            by_client.setdefault(f.client, []).append(f)

        for client_name, client_findings in by_client.items():
            lines.append("")
            lines.append(f"--- {client_name} " + "-" * max(0, 50 - len(client_name)))
            for f in client_findings:
                lines.append(f"{f.severity.icon} [{f.category}] {f.title}")
                lines.append(f"    where: {f.location}")
                lines.append(f"    what:  {f.detail}")
                if f.suggested_fix:
                    lines.append(f"    fix:   {f.suggested_fix}")
                lines.append(f"    key:   {f.key}  (paste into known_exceptions to silence)")

    suppressed = suppressed_findings(result)
    if suppressed:
        lines.append("")
        lines.append(f"({len(suppressed)} finding(s) suppressed via known_exceptions — still checked, not re-flagged)")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


_SEV_PILL_KIND = {
    Severity.CRITICAL: "bad",
    Severity.DEGRADING: "warn",
    Severity.COSMETIC: "neutral",
    Severity.INFO: "neutral",
}


def _e(s: str) -> str:
    return _html.escape(str(s), quote=True)


def render_html(result: RunResult, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    summary_line = build_run_summary_line(result)
    active = active_findings(result)
    counts = severity_counts(active)
    suppressed = suppressed_findings(result)

    kpis = kpi_strip(
        [
            {"label": "Clients swept", "value": str(result.clients_swept)},
            {"label": "Sites swept", "value": str(result.sites_swept)},
            {
                "label": "Critical",
                "value": str(counts[Severity.CRITICAL]),
                "trend": "bad" if counts[Severity.CRITICAL] else "good",
            },
            {
                "label": "Degrading",
                "value": str(counts[Severity.DEGRADING]),
                "trend": "warn" if counts[Severity.DEGRADING] else "good",
            },
            {"label": "Cosmetic", "value": str(counts[Severity.COSMETIC])},
        ]
    )

    sections = []

    if result.skipped_checks:
        items = "".join(f"<li>{_e(s)}</li>" for s in result.skipped_checks)
        sections.append(f'<div class="fc-card"><h2>Skipped checks</h2><ul>{items}</ul></div>')

    if not active:
        sections.append(
            '<div class="fc-card"><div class="fc-callout good">'
            "No active findings across any client. Clean sweep.</div></div>"
        )
    else:
        by_client: dict[str, list[Finding]] = {}
        for f in active:
            by_client.setdefault(f.client, []).append(f)

        for client_name, client_findings in by_client.items():
            rows = []
            for f in client_findings:
                fix_html = f"<br><em>Fix: {_e(f.suggested_fix)}</em>" if f.suggested_fix else ""
                sev_pill = pill(f"{f.severity.icon} {f.severity.value.upper()}", _SEV_PILL_KIND[f.severity])
                rows.append(
                    "<tr>"
                    f"<td>{sev_pill}</td>"
                    f"<td>{_e(f.category)}</td>"
                    f"<td>{_e(f.title)}</td>"
                    f"<td>{_e(f.location)}</td>"
                    f"<td>{_e(f.detail)}{fix_html}</td>"
                    f"<td class='mono'>{_e(f.key)}</td>"
                    "</tr>"
                )
            table_html = table(
                ["Severity", "Category", "Title", "Where", "What / Fix", "Key"],
                "".join(rows),
            )
            sections.append(
                f'<div class="fc-card"><h2>{_e(client_name)} '
                f'<span class="fc-count">{len(client_findings)} finding(s)</span></h2>{table_html}</div>'
            )

    if suppressed:
        sections.append(
            '<div class="fc-card"><h2>Suppressed (known exceptions)</h2>'
            f'<p class="fc-note">{len(suppressed)} finding(s) matched a known_exceptions entry — '
            "still checked every run, just not re-flagged.</p></div>"
        )

    return page(
        title="Bug Hunter — Sweep Report",
        subtitle=summary_line,
        kpis_html=kpis,
        body_html="\n".join(sections),
        footer_note=f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')} · Bug Hunter · AMM Founding Circle",
        doc_title="Bug Hunter — Sweep Report",
    )
