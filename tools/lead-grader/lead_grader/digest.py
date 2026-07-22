"""The daily lead digest — the thing a member actually reads every
morning: graded leads sorted Hot-first, a one-line summary, delivered to
terminal + a local HTML file + (if configured) email/Slack.
"""
from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import Any, Optional

from .schema import VALID_GRADES, Grade, Lead
from .theme import kpi_strip, page, pill

_GRADE_SORT_ORDER = {g: i for i, g in enumerate(VALID_GRADES)}
_GRADE_PILL_KIND = {"Hot": "accent", "Qualified": "good", "Weak": "warn", "Junk": "bad"}
_GRADE_KPI_TREND = {"Hot": "good", "Qualified": "good", "Weak": "warn", "Junk": "bad"}

_LEAD_HTML = """<div class="lead">
  <div class="emoji">{emoji}</div>
  <div>
    <div class="grade-label">{grade_pill}</div>
    <div class="meta">{caller} &middot; {duration}</div>
    <div>{reason}</div>
    {quote_html}
  </div>
</div>
"""


@dataclass
class DigestResult:
    client: str
    date: str
    text: str
    html: str
    counts: dict[str, int]


def _sort_key(pair: tuple[Lead, Grade]) -> tuple[int, datetime]:
    _, grade = pair
    return (_GRADE_SORT_ORDER.get(grade.grade, len(VALID_GRADES)), pair[0].occurred_at)


def build_digest(
    leads_with_grades: list[tuple[Lead, Grade]], client_name: str, date: datetime
) -> DigestResult:
    date_str = date.date().isoformat()
    ordered = sorted(leads_with_grades, key=_sort_key)

    counts = {g: 0 for g in VALID_GRADES}
    for _, grade in ordered:
        if grade.grade in counts:
            counts[grade.grade] += 1

    summary = _summary_line(client_name, date_str, counts, total=len(ordered))
    text = _render_text(client_name, date_str, ordered, summary)
    html = _render_html(client_name, date_str, ordered, summary)

    return DigestResult(client=client_name, date=date_str, text=text, html=html, counts=counts)


def _summary_line(client_name: str, date_str: str, counts: dict[str, int], total: int) -> str:
    if total == 0:
        return f"No graded leads for {client_name} on {date_str}."
    parts = ", ".join(f"{counts[g]} {g.lower()}" for g in VALID_GRADES if counts[g])
    return f"Graded {total} lead{'s' if total != 1 else ''} for {client_name} on {date_str} — {parts}."


def _render_text(client_name: str, date_str: str, ordered, summary: str) -> str:
    lines = [f"Lead digest — {client_name} — {date_str}", summary, ""]
    if not ordered:
        lines.append("(nothing to grade today)")
    for lead, grade in ordered:
        lines.append(f"{grade.emoji()} {grade.grade} — {lead.caller or 'unknown caller'} — {grade.reason}")
        if grade.quote:
            lines.append(f'    "{grade.quote}"')
    return "\n".join(lines)


def _render_html(client_name: str, date_str: str, ordered, summary: str) -> str:
    counts = {g: 0 for g in VALID_GRADES}
    for _, grade in ordered:
        if grade.grade in counts:
            counts[grade.grade] += 1

    kpis = kpi_strip(
        [
            {"label": g, "value": str(counts[g]), "trend": _GRADE_KPI_TREND.get(g)}
            for g in VALID_GRADES
        ]
    )

    if not ordered:
        leads_html = "<p class='fc-empty'>Nothing to grade today.</p>"
    else:
        blocks = []
        for lead, grade in ordered:
            duration = f"{lead.duration_seconds}s" if lead.duration_seconds else "unknown length"
            quote_html = ""
            if grade.quote:
                quote_html = f'<div class="fc-quote">&ldquo;{escape(grade.quote)}&rdquo;</div>'
            blocks.append(
                _LEAD_HTML.format(
                    emoji=grade.emoji(),
                    grade_pill=pill(grade.grade, _GRADE_PILL_KIND.get(grade.grade, "neutral")),
                    caller=escape(lead.caller or "unknown caller"),
                    duration=duration,
                    reason=escape(grade.reason),
                    quote_html=quote_html,
                )
            )
        leads_html = (
            "<style>.lead{display:flex;gap:14px;align-items:flex-start;padding:14px 0;"
            "border-bottom:1px solid var(--fc-rule)}.lead:last-child{border-bottom:none}"
            ".lead .emoji{font-size:24px;line-height:1}</style>"
            f'<div class="fc-card"><h2>Today\'s leads</h2>{"".join(blocks)}</div>'
        )

    return page(
        title=f"Lead digest — {client_name}",
        subtitle=summary,
        kpis_html=kpis,
        body_html=leads_html,
        footer_note="Lead Grader · AMM Founding Circle",
        doc_title=f"Lead digest — {client_name} — {date_str}",
    )


def write_html(digest: DigestResult, output_dir: str | Path = "output") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"digest-{digest.client}-{digest.date}.html"
    path.write_text(digest.html)
    return path


def send_slack(webhook_url: str, text: str, session: Any = None) -> None:
    if session is None:
        import requests as session  # type: ignore[assignment]
    resp = session.post(webhook_url, json={"text": text})
    resp.raise_for_status()


def send_email(
    smtp_host: str,
    smtp_port: int,
    username: Optional[str],
    password: Optional[str],
    to_addr: str,
    subject: str,
    html_body: str,
    text_body: str,
    smtp_client: Any = None,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = username or "lead-grader@localhost"
    msg["To"] = to_addr
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    if smtp_client is not None:
        smtp_client.send_message(msg)
        return

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)


def deliver(digest: DigestResult, client_config: dict, print_func=print) -> list[str]:
    """Best-effort delivery to whatever's configured for this client, plus
    always writing the HTML file and printing to terminal. Returns a list
    of channels actually delivered to, for the CLI to report back."""
    delivered: list[str] = []

    slack_webhook = client_config.get("digest", {}).get("slack_webhook") or os.environ.get(
        "SLACK_WEBHOOK_URL"
    )
    if slack_webhook:
        try:
            send_slack(slack_webhook, digest.text)
            delivered.append("slack")
        except Exception as exc:  # pragma: no cover - network failure path
            print_func(f"Slack delivery failed: {exc}")

    email_to = client_config.get("digest", {}).get("email_to")
    smtp_host = os.environ.get("SMTP_HOST")
    if email_to and smtp_host:
        try:
            send_email(
                smtp_host=smtp_host,
                smtp_port=int(os.environ.get("SMTP_PORT", "587")),
                username=os.environ.get("SMTP_USERNAME"),
                password=os.environ.get("SMTP_PASSWORD"),
                to_addr=email_to,
                subject=f"Lead digest — {digest.client} — {digest.date}",
                html_body=digest.html,
                text_body=digest.text,
            )
            delivered.append("email")
        except Exception as exc:  # pragma: no cover - network failure path
            print_func(f"Email delivery failed: {exc}")

    if not delivered:
        print_func(
            "No delivery channel configured — add slack_webhook/email_to to this "
            "client's config.yaml (or SLACK_WEBHOOK_URL/SMTP_* in .env) to get the "
            "digest pushed to you instead of just written to disk."
        )
    return delivered
