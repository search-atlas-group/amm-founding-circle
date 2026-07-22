"""report.py — assemble the three layers + verdict into a report, and
render it two ways: a terminal summary and an HTML file. HTML rendering
uses Python's stdlib `string.Template` — no jinja2 dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from content_qa.fact_check import FactResult, Verdict as FactVerdict
from content_qa.grammar import Issue
from content_qa.theme import THEME_CSS, kpi_strip, pill
from content_qa.verdict import VerdictResult
from content_qa.voice_check import VoiceResult

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


@dataclass
class ReportData:
    client_name: str
    draft_source: str
    generated_at: str
    grammar_issues: list[Issue]
    voice_result: VoiceResult
    fact_results: list[FactResult]
    verdict: VerdictResult
    degraded_notes: list[str]


def build_report_data(
    *,
    client_name: str,
    draft_source: str,
    grammar_issues: list[Issue],
    voice_result: VoiceResult,
    fact_results: list[FactResult],
    verdict: VerdictResult,
    degraded_notes: list[str] | None = None,
) -> ReportData:
    return ReportData(
        client_name=client_name,
        draft_source=draft_source,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        grammar_issues=grammar_issues,
        voice_result=voice_result,
        fact_results=fact_results,
        verdict=verdict,
        degraded_notes=degraded_notes or [],
    )


_VERDICT_ICON = {"SHIP": "✅", "SHIP WITH FIXES": "⚠️", "HOLD": "\U0001f6d1"}
_FACT_ICON = {
    FactVerdict.VERIFIED: "✅ verified",
    FactVerdict.UNVERIFIABLE: "❓ unverifiable",
    FactVerdict.CONTRADICTED: "❌ contradicted",
}


def render_terminal_summary(data: ReportData) -> str:
    icon = _VERDICT_ICON.get(data.verdict.verdict.value, "")
    lines = [
        f"Content QA — {data.client_name}",
        f"Draft: {data.draft_source}",
        f"Generated: {data.generated_at}",
        "",
        f"{icon} VERDICT: {data.verdict.verdict.value} — {data.verdict.reason}",
        "",
        f"Grammar/mechanics: {len(data.grammar_issues)} issue(s)",
    ]
    for issue in data.grammar_issues[:10]:
        lines.append(f"  [{issue.severity}] {issue.problem} -> {issue.fix}")
    if len(data.grammar_issues) > 10:
        lines.append(f"  ...and {len(data.grammar_issues) - 10} more (see HTML report).")

    lines.append("")
    voice_status = "PASS" if data.voice_result.passed else "FAIL"
    lines.append(f"Voice: {voice_status} (reading level {data.voice_result.reading_level_estimate})")
    for hit in data.voice_result.banned_phrase_hits[:10]:
        lines.append(f'  banned phrase "{hit.phrase}" — "{hit.snippet}"')
    for note in data.voice_result.notes:
        lines.append(f"  note: {note}")

    lines.append("")
    lines.append(f"Facts: {len(data.fact_results)} checkable claim(s)")
    for fact in data.fact_results[:10]:
        lines.append(f"  {_FACT_ICON[fact.verdict]} — {fact.claim.text[:90]}")
        if fact.reason:
            lines.append(f"      {fact.reason}")

    if data.degraded_notes:
        lines.append("")
        lines.append("Notes:")
        for note in data.degraded_notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


def _row(cells: list[str]) -> str:
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def _grammar_rows(issues: list[Issue]) -> str:
    if not issues:
        return "<p class='fc-empty'>No mechanical issues found.</p>"
    rows = "\n".join(
        _row([i.severity, f"{i.problem}<br><span class='snippet'>{i.snippet}</span>", i.fix])
        for i in issues
    )
    return (
        "<div class='fc-table-wrap'><table class='fc-table'>"
        "<thead><tr><th>Severity</th><th>Issue</th><th>Suggested fix</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def _fact_rows(facts: list[FactResult]) -> str:
    if not facts:
        return "<p class='fc-empty'>No checkable claims extracted.</p>"
    rows = []
    for fact in facts:
        pill_kind = {"verified": "good", "unverifiable": "neutral", "contradicted": "bad"}[fact.verdict.value]
        rows.append(
            _row(
                [
                    pill(_FACT_ICON[fact.verdict], pill_kind),
                    fact.claim.text,
                    fact.reason or "",
                ]
            )
        )
    return (
        "<div class='fc-table-wrap'><table class='fc-table'>"
        "<thead><tr><th>Verdict</th><th>Claim</th><th>Reason / source</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _voice_block(voice: VoiceResult) -> str:
    parts = [f"<p><strong>Reading level:</strong> {voice.reading_level_estimate}</p>"]
    if voice.reading_level_note:
        parts.append(f"<p class='note'>{voice.reading_level_note}</p>")
    if voice.banned_phrase_hits:
        parts.append("<ul>")
        for hit in voice.banned_phrase_hits:
            parts.append(f"<li>banned phrase “{hit.phrase}” &mdash; “{hit.snippet}”</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>No banned phrases found.</p>")
    return "\n".join(parts)


def render_html_report(data: ReportData, template_path: Path | None = None) -> str:
    template_path = template_path or _TEMPLATE_PATH
    template = Template(template_path.read_text(encoding="utf-8"))

    verdict_class = data.verdict.verdict.value.replace(" ", "-")
    voice_status = "PASS" if data.voice_result.passed else "FAIL"

    degraded_html = ""
    if data.degraded_notes:
        items = "".join(f"<li>{n}</li>" for n in data.degraded_notes)
        degraded_html = f"<div class='fc-card'><h2>Notes</h2><ul>{items}</ul></div>"

    auto_fixable = sum(1 for i in data.grammar_issues if i.auto_fixable)
    verified = sum(1 for f in data.fact_results if f.verdict == FactVerdict.VERIFIED)
    kpis = kpi_strip(
        [
            {"label": "Verdict", "value": data.verdict.verdict.value},
            {"label": "Grammar issues", "value": str(len(data.grammar_issues)), "sub": f"{auto_fixable} auto-fixable"},
            {"label": "Voice", "value": voice_status, "trend": "good" if data.voice_result.passed else "bad"},
            {"label": "Facts checked", "value": str(len(data.fact_results)), "sub": f"{verified} verified"},
        ]
    )

    return template.substitute(
        theme_css=THEME_CSS,
        kpis=kpis,
        client_name=data.client_name,
        draft_source=data.draft_source,
        generated_at=data.generated_at,
        verdict=data.verdict.verdict.value,
        verdict_class=verdict_class,
        verdict_reason=data.verdict.reason,
        grammar_count=len(data.grammar_issues),
        grammar_table=_grammar_rows(data.grammar_issues),
        voice_status=voice_status,
        voice_block=_voice_block(data.voice_result),
        fact_count=len(data.fact_results),
        fact_table=_fact_rows(data.fact_results),
        degraded_notes=degraded_html,
    )
