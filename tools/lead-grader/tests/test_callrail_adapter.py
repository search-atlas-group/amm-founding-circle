"""CallRail adapter tests — normalization + pagination, fully offline via
a fake HTTP session (no real network, no real API key required)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lead_grader.adapters.callrail import CallRailAdapter
from lead_grader.schema import Lead


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeSession:
    """Records calls and serves canned pages, so pagination can be tested
    without a real CallRail account."""

    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def get(self, url, headers=None, params=None):
        self.requests.append({"url": url, "headers": headers, "params": dict(params or {})})
        page_num = (params or {}).get("page", 1)
        return _FakeResponse(self.pages[page_num - 1])


def test_adapter_requires_api_key_and_account_id():
    with pytest.raises(ValueError):
        CallRailAdapter(api_key="", account_id="A1")
    with pytest.raises(ValueError):
        CallRailAdapter(api_key="k", account_id="")


def test_normalize_maps_core_fields(sample_calls_raw):
    adapter = CallRailAdapter(api_key="k", account_id="A1", session=_FakeSession([{}]))
    lead = adapter.normalize(sample_calls_raw[0], client="acme")

    assert isinstance(lead, Lead)
    assert lead.id == "CAL1001"
    assert lead.client == "acme"
    assert lead.source == "callrail"
    assert lead.caller == "Jamie R."
    assert lead.duration_seconds == 214
    assert lead.recording_url.endswith("recording.mp3")
    assert "roof" in lead.transcript.lower()
    assert lead.occurred_at.tzinfo is not None
    # original payload preserved for audit
    assert lead.raw["id"] == "CAL1001"


def test_normalize_falls_back_to_phone_when_no_customer_name(sample_calls_raw):
    adapter = CallRailAdapter(api_key="k", account_id="A1", session=_FakeSession([{}]))
    lead = adapter.normalize(sample_calls_raw[1], client="acme")
    assert lead.caller == "+15555550111"


def test_normalize_returns_none_without_call_id():
    adapter = CallRailAdapter(api_key="k", account_id="A1", session=_FakeSession([{}]))
    assert adapter.normalize({"start_time": "2026-07-20T00:00:00Z"}, client="acme") is None


def test_normalize_never_raises_on_missing_or_malformed_transcription():
    adapter = CallRailAdapter(api_key="k", account_id="A1", session=_FakeSession([{}]))
    lead = adapter.normalize({"id": "X1", "start_time": "2026-07-20T00:00:00Z"}, client="acme")
    assert lead.transcript == ""

    lead2 = adapter.normalize(
        {"id": "X2", "start_time": "2026-07-20T00:00:00Z", "transcription": {"unexpected": "shape"}},
        client="acme",
    )
    assert lead2.transcript == ""


def test_normalize_bad_start_time_does_not_raise():
    adapter = CallRailAdapter(api_key="k", account_id="A1", session=_FakeSession([{}]))
    lead = adapter.normalize({"id": "X3", "start_time": "not-a-date"}, client="acme")
    assert isinstance(lead.occurred_at, datetime)


def test_fetch_paginates_and_normalizes_every_call(sample_calls_raw):
    page1 = {"page": 1, "total_pages": 2, "calls": sample_calls_raw[:2]}
    page2 = {"page": 2, "total_pages": 2, "calls": sample_calls_raw[2:]}
    session = _FakeSession([page1, page2])
    adapter = CallRailAdapter(api_key="k", account_id="A1", session=session)

    since = datetime(2026, 7, 20, tzinfo=timezone.utc)
    until = datetime(2026, 7, 21, tzinfo=timezone.utc)
    leads = adapter.fetch({"slug": "acme", "callrail_company_id": "CO900"}, since, until)

    assert len(leads) == 4
    assert {lead.id for lead in leads} == {"CAL1001", "CAL1002", "CAL1003", "CAL1004"}
    assert len(session.requests) == 2
    assert session.requests[0]["params"]["company_id"] == "CO900"
    assert session.requests[0]["params"]["start_date"] == "2026-07-20"


def test_headers_send_callrail_token_format():
    adapter = CallRailAdapter(api_key="secret-key", account_id="A1", session=_FakeSession([{}]))
    headers = adapter._headers()
    assert headers["Authorization"] == 'Token token="secret-key"'


def test_fetch_transcript_returns_empty_string_on_any_error():
    class _RaisingSession:
        def get(self, *a, **k):
            raise ConnectionError("network down")

    adapter = CallRailAdapter(api_key="k", account_id="A1", session=_RaisingSession())
    assert adapter.fetch_transcript("CAL999") == ""
