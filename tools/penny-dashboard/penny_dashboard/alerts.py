"""Margin-drop alerting — plain-English, one line per client below threshold.

v1 delivery: stdout (always) + optional Slack webhook + optional email, both
via stdlib only (no requests dependency). See product-descriptions doc:
"A monthly margin alert: 'Client X dropped below 20% margin this month' to
email/Slack."
"""

from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText

DEFAULT_MARGIN_THRESHOLD_PCT = 20.0


def find_low_margin_clients(financials: list, threshold_pct: float = DEFAULT_MARGIN_THRESHOLD_PCT) -> list:
    """Clients whose margin_pct fell at/below the threshold this period."""
    return [f for f in financials if f.margin_pct <= threshold_pct]


def format_alert_line(client_name: str, margin_pct: float, threshold_pct: float) -> str:
    return (
        f"Client {client_name} dropped to {margin_pct:.1f}% margin this month "
        f"(below the {threshold_pct:.0f}% alert line)."
    )


def build_alert_lines(
    financials: list,
    threshold_pct: float = DEFAULT_MARGIN_THRESHOLD_PCT,
    client_names: dict | None = None,
) -> list[str]:
    client_names = client_names or {}
    low = find_low_margin_clients(financials, threshold_pct)
    return [
        format_alert_line(client_names.get(f.client_id, f.client_id), f.margin_pct, threshold_pct)
        for f in low
    ]


def send_email_alert(
    lines: list[str],
    *,
    to_addr: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_addr: str | None = None,
) -> None:
    if not lines:
        return
    body = "Penny Dashboard margin alert:\n\n" + "\n".join(f"- {line}" for line in lines)
    msg = MIMEText(body)
    msg["Subject"] = "Penny Dashboard: margin alert"
    msg["From"] = from_addr or smtp_user
    msg["To"] = to_addr
    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(msg["From"], [to_addr], msg.as_string())


def send_slack_alert(lines: list[str], *, webhook_url: str) -> None:
    if not lines:
        return
    text = "*Penny Dashboard margin alert*\n" + "\n".join(f"- {line}" for line in lines)
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - trusted, user-configured webhook
        resp.read()


def dispatch_alerts(lines: list[str]) -> list[str]:
    """Send alerts via whichever channels are configured in the environment.

    Returns the list of channels actually used, so the CLI can report what
    happened. Never raises on a missing config — an unconfigured channel is
    just skipped, not an error.
    """
    if not lines:
        return []
    used = []

    webhook = os.environ.get("PENNY_SLACK_WEBHOOK_URL")
    if webhook:
        send_slack_alert(lines, webhook_url=webhook)
        used.append("slack")

    to_addr = os.environ.get("PENNY_ALERT_EMAIL_TO")
    smtp_host = os.environ.get("PENNY_SMTP_HOST")
    if to_addr and smtp_host:
        send_email_alert(
            lines,
            to_addr=to_addr,
            smtp_host=smtp_host,
            smtp_port=int(os.environ.get("PENNY_SMTP_PORT", "587")),
            smtp_user=os.environ.get("PENNY_SMTP_USER", ""),
            smtp_password=os.environ.get("PENNY_SMTP_PASSWORD", ""),
            from_addr=os.environ.get("PENNY_SMTP_FROM"),
        )
        used.append("email")

    return used
