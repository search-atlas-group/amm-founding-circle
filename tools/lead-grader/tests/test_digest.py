"""Digest tests — sort order, summary line, HTML shape, delivery
dispatch. All offline (fake Slack/SMTP clients, no real network)."""
from __future__ import annotations

from datetime import datetime, timezone

from lead_grader.digest import build_digest, deliver, send_email, send_slack, write_html
from lead_grader.schema import Grade, Lead


def _pair(id_, grade, caller="Jamie", reason="reason", quote="", occurred_at=None):
    lead = Lead(
        id=id_,
        client="acme",
        source="callrail",
        occurred_at=occurred_at or datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        caller=caller,
        duration_seconds=120,
    )
    return lead, Grade(lead_id=id_, client="acme", grade=grade, reason=reason, quote=quote)


def test_build_digest_sorts_hot_first_then_junk_last():
    pairs = [
        _pair("L1", "Junk"),
        _pair("L2", "Hot"),
        _pair("L3", "Weak"),
        _pair("L4", "Qualified"),
    ]
    digest = build_digest(pairs, "Acme Roofing", datetime(2026, 7, 20, tzinfo=timezone.utc))
    ids_in_order = [line for line in digest.text.splitlines() if line.startswith(("🔥", "✅", "⚠️", "🗑️"))]
    assert ids_in_order[0].startswith("🔥")
    assert ids_in_order[-1].startswith("🗑️")


def test_build_digest_counts_and_summary_line():
    pairs = [_pair("L1", "Hot"), _pair("L2", "Hot"), _pair("L3", "Junk")]
    digest = build_digest(pairs, "Acme Roofing", datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert digest.counts == {"Hot": 2, "Qualified": 0, "Weak": 0, "Junk": 1}
    assert "Graded 3 leads for Acme Roofing on 2026-07-20" in digest.text
    assert "2 hot" in digest.text
    assert "1 junk" in digest.text


def test_build_digest_handles_zero_leads():
    digest = build_digest([], "Acme Roofing", datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert "No graded leads" in digest.text
    assert "nothing to grade today" in digest.text.lower()
    assert "Nothing to grade today" in digest.html


def test_html_output_is_well_formed_and_escapes_content():
    pairs = [_pair("L1", "Hot", reason="<script>alert(1)</script>", quote="he said <b>now</b>")]
    digest = build_digest(pairs, "Acme & Co", datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert "<!doctype html>" in digest.html
    assert "<script>alert(1)</script>" not in digest.html
    assert "&lt;script&gt;" in digest.html
    assert "Acme &amp; Co" in digest.html


def test_write_html_creates_file(tmp_path):
    digest = build_digest([_pair("L1", "Hot")], "Acme", datetime(2026, 7, 20, tzinfo=timezone.utc))
    path = write_html(digest, output_dir=tmp_path)
    assert path.exists()
    assert path.name == "digest-Acme-2026-07-20.html"
    assert "Acme" in path.read_text()


class _FakeSlackResp:
    def raise_for_status(self):
        return None


class _FakeSlackSession:
    def __init__(self):
        self.posted = None

    def post(self, url, json=None):
        self.posted = {"url": url, "json": json}
        return _FakeSlackResp()


def test_send_slack_posts_text():
    session = _FakeSlackSession()
    send_slack("https://hooks.slack.com/services/x", "hello digest", session=session)
    assert session.posted["json"]["text"] == "hello digest"


class _FakeSMTP:
    def __init__(self):
        self.sent = []

    def send_message(self, msg):
        self.sent.append(msg)


def test_send_email_uses_injected_client():
    smtp = _FakeSMTP()
    send_email(
        smtp_host="x", smtp_port=587, username="me@x.com", password="pw",
        to_addr="owner@example.com", subject="subj", html_body="<p>hi</p>",
        text_body="hi", smtp_client=smtp,
    )
    assert len(smtp.sent) == 1
    assert smtp.sent[0]["To"] == "owner@example.com"


def test_deliver_reports_no_channel_configured(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    digest = build_digest([_pair("L1", "Hot")], "Acme", datetime(2026, 7, 20, tzinfo=timezone.utc))
    messages = []
    delivered = deliver(digest, client_config={}, print_func=messages.append)
    assert delivered == []
    assert any("No delivery channel" in m for m in messages)


def test_deliver_uses_client_config_slack_webhook(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    digest = build_digest([_pair("L1", "Hot")], "Acme", datetime(2026, 7, 20, tzinfo=timezone.utc))

    called = {}

    def _fake_send_slack(webhook_url, text, session=None):
        called["webhook_url"] = webhook_url

    import lead_grader.digest as digest_mod

    monkeypatch.setattr(digest_mod, "send_slack", _fake_send_slack)
    delivered = deliver(
        digest,
        client_config={"digest": {"slack_webhook": "https://hooks.slack.com/services/abc"}},
        print_func=lambda *_: None,
    )
    assert delivered == ["slack"]
    assert called["webhook_url"] == "https://hooks.slack.com/services/abc"
