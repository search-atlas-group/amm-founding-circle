"""Terminal + HTML report rendering, plus the one-line run summary.

Visual language matches the repo's shared `templates/report-template.html`
design tokens (light card UI, no neon) so this fits the same report family
called out in the master spec ("shares the report/HTML template family").
"""

from __future__ import annotations

import html as _html
from datetime import datetime, timezone

from .models import Finding, RunResult, Severity

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


_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bug Hunter — Sweep Report</title>
  <style>
    :root {{
      --bg: #f7f8fb; --card: #ffffff; --ink: #17202a; --muted: #5d6b7a;
      --line: #d9e0e8; --accent: #2563eb; --good: #0f766e; --warn: #b45309;
      --critical: #b91c1c; --degrading: #b45309; --cosmetic: #64748b;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--ink);
      font: 15px/1.55 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px 64px; }}
    header, section {{ background: var(--card); border: 1px solid var(--line);
      border-radius: 8px; padding: 24px; margin-bottom: 18px; }}
    h1, h2, h3 {{ line-height: 1.2; margin: 0 0 12px; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 20px; }}
    h3 {{ font-size: 16px; margin-top: 20px; }}
    p {{ margin: 0 0 12px; }}
    .lede {{ color: var(--muted); font-size: 17px; }}
    .callout {{ border-left: 4px solid var(--accent); background: #eef4ff;
      padding: 14px 16px; border-radius: 6px; }}
    .callout.clean {{ border-left-color: var(--good); background: #ecfdf5; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background: var(--card); }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 700; font-size: 13px; text-transform: uppercase; }}
    td.key {{ font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: var(--muted); }}
    .sev-critical {{ color: var(--critical); font-weight: 700; }}
    .sev-degrading {{ color: var(--degrading); font-weight: 700; }}
    .sev-cosmetic {{ color: var(--cosmetic); }}
    .muted {{ color: var(--muted); font-size: 13px; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
    @media (max-width: 640px) {{ main {{ padding: 20px 12px 40px; }} header, section {{ padding: 18px; }} h1 {{ font-size: 26px; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Bug Hunter — Sweep Report</h1>
      <p class="lede">{summary_line}</p>
      <p class="muted">Generated {generated_at}</p>
    </header>
    {skipped_section}
    {clients_html}
    {suppressed_section}
  </main>
</body>
</html>
"""

_CLIENT_SECTION_TEMPLATE = """<section>
      <h2>{client_name}</h2>
      <table>
        <thead><tr><th>Severity</th><th>Category</th><th>Title</th><th>Where</th><th>What / Fix</th><th>Key</th></tr></thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </section>"""

_ROW_TEMPLATE = """<tr>
            <td class="sev-{sev_class}">{sev_icon} {sev_label}</td>
            <td>{category}</td>
            <td>{title}</td>
            <td>{location}</td>
            <td>{detail}{fix_html}</td>
            <td class="key">{key}</td>
          </tr>"""


def _e(s: str) -> str:
    return _html.escape(str(s), quote=True)


def render_html(result: RunResult, generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now(timezone.utc)
    summary_line = build_run_summary_line(result)

    skipped_section = ""
    if result.skipped_checks:
        items = "".join(f"<li>{_e(s)}</li>" for s in result.skipped_checks)
        skipped_section = f'<section><h2>Skipped checks</h2><ul>{items}</ul></section>'

    active = active_findings(result)
    if not active:
        clients_html = '<section><div class="callout clean">No active findings across any client. Clean sweep.</div></section>'
    else:
        by_client: dict[str, list[Finding]] = {}
        for f in active:
            by_client.setdefault(f.client, []).append(f)

        sections = []
        for client_name, client_findings in by_client.items():
            rows = []
            for f in client_findings:
                fix_html = f"<br><em>Fix: {_e(f.suggested_fix)}</em>" if f.suggested_fix else ""
                rows.append(
                    _ROW_TEMPLATE.format(
                        sev_class=f.severity.value,
                        sev_icon=f.severity.icon,
                        sev_label=f.severity.value.upper(),
                        category=_e(f.category),
                        title=_e(f.title),
                        location=_e(f.location),
                        detail=_e(f.detail),
                        fix_html=fix_html,
                        key=_e(f.key),
                    )
                )
            sections.append(
                _CLIENT_SECTION_TEMPLATE.format(client_name=_e(client_name), rows="\n          ".join(rows))
            )
        clients_html = "\n    ".join(sections)

    suppressed = suppressed_findings(result)
    suppressed_section = ""
    if suppressed:
        suppressed_section = (
            f'<section><h2>Suppressed (known exceptions)</h2>'
            f'<p class="muted">{len(suppressed)} finding(s) matched a known_exceptions entry — '
            f"still checked every run, just not re-flagged.</p></section>"
        )

    return _HTML_TEMPLATE.format(
        summary_line=_e(summary_line),
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M UTC"),
        skipped_section=skipped_section,
        clients_html=clients_html,
        suppressed_section=suppressed_section,
    )
