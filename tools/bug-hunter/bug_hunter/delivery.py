"""Optional delivery: Slack webhook and/or plain SMTP email.

Both are opt-in via env vars — a member who sets neither just gets the
terminal + HTML file, which is the v1 default. Mirrors the
automations/ai-news-feed SLACK_WEBHOOK_URL convention already used in this
repo, so the pattern is familiar across tools.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def deliver_slack(webhook_url: str, summary_line: str, report_path: str) -> None:
    import httpx

    text = f":mag: *Bug Hunter sweep complete*\n{summary_line}\nFull report: {report_path}"
    resp = httpx.post(webhook_url, json={"text": text}, timeout=10)
    resp.raise_for_status()


def deliver_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_addr: str,
    summary_line: str,
    html_report: str,
) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"Bug Hunter sweep: {summary_line}"
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.set_content(summary_line + "\n\n(Your email client may not render the HTML report below — the .html file is also saved locally.)")
    msg.add_alternative(html_report, subtype="html")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def maybe_deliver(summary_line: str, report_path: str, html_report: str) -> list[str]:
    """Reads delivery config from env; returns a list of human-readable
    delivery outcome notes for the terminal output. Never raises — a failed
    delivery must not hide the report that was already written to disk."""
    notes: list[str] = []

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        try:
            deliver_slack(webhook, summary_line, report_path)
            notes.append("Slack: sent.")
        except Exception as exc:
            notes.append(f"Slack: FAILED to send ({exc}).")

    smtp_host = os.environ.get("SMTP_HOST")
    to_addr = os.environ.get("REPORT_EMAIL_TO")
    if smtp_host and to_addr:
        try:
            deliver_email(
                smtp_host=smtp_host,
                smtp_port=int(os.environ.get("SMTP_PORT", "587")),
                smtp_user=os.environ["SMTP_USER"],
                smtp_password=os.environ["SMTP_PASSWORD"],
                to_addr=to_addr,
                summary_line=summary_line,
                html_report=html_report,
            )
            notes.append(f"Email: sent to {to_addr}.")
        except Exception as exc:
            notes.append(f"Email: FAILED to send ({exc}).")

    return notes
