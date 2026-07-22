"""Notification senders -- email + macOS notification (v1 scope; Slack/SMS
is an explicit later phase, not built here).

Message building is kept separate from the actual send so it's testable
without touching smtplib / subprocess: `format_subject` is pure; the two
`send_*` functions are thin I/O wrappers that never raise -- a broken
notifier must not crash the sweep, it just falls back to a console print.
"""
from __future__ import annotations

import os
import platform
import smtplib
import subprocess
from email.message import EmailMessage

_SUBJECT_ICON = {"down": "\U0001f534", "recovered": "✅", "heartbeat": "\U0001f7e2"}
_SUBJECT_LABEL = {"down": "connection down", "recovered": "back up", "heartbeat": "all green"}


def format_subject(alert) -> str:
    icon = _SUBJECT_ICON.get(alert.kind, "⚠️")
    label = _SUBJECT_LABEL.get(alert.kind, "update")
    return f"{icon} Connection Sentinel -- {alert.name} {label}"


def send_email(alert, to_addr: str) -> bool:
    """SMTP creds come from the environment (SENTINEL_SMTP_*), never from
    connections.yaml. Returns False (never raises) if unconfigured or if the
    send fails -- notify_all() falls back to a console print in that case."""
    host = os.environ.get("SENTINEL_SMTP_HOST")
    port = int(os.environ.get("SENTINEL_SMTP_PORT", "587") or "587")
    user = os.environ.get("SENTINEL_SMTP_USER")
    password = os.environ.get("SENTINEL_SMTP_PASS")
    from_addr = os.environ.get("SENTINEL_SMTP_FROM") or user or ""
    if not (host and user and password and to_addr):
        return False
    msg = EmailMessage()
    msg["Subject"] = format_subject(alert)
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(alert.message)
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[warn] email notify failed: {e}")
        return False


def send_macos_notification(alert) -> bool:
    if platform.system() != "Darwin":
        return False
    title = format_subject(alert).replace('"', "'")
    body = alert.message.replace('"', "'")
    script = f'display notification "{body}" with title "{title}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=5, capture_output=True)
        return True
    except Exception as e:
        print(f"[warn] macOS notify failed: {e}")
        return False


def notify_all(alert, notify_cfg) -> None:
    """Fan out to every enabled channel. If every channel is off or fails,
    the alert still surfaces to the console -- it must never vanish."""
    sent = False
    if getattr(notify_cfg, "email_enabled", False) and getattr(notify_cfg, "email_to", ""):
        sent = send_email(alert, notify_cfg.email_to) or sent
    if getattr(notify_cfg, "macos_enabled", False):
        sent = send_macos_notification(alert) or sent
    if not sent:
        print(f"[ALERT] {alert.message}")
