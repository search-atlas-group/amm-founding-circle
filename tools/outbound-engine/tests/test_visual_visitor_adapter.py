import json

import pytest

from outbound_engine.signals.visual_visitor import LiveModeNotImplementedError, VisualVisitorAdapter


def _write_fixture(tmp_path, entries):
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(entries))
    return path


def test_mock_adapter_returns_fixture_signals(tmp_path):
    entries = [
        {"external_id": "vv-1", "company_name": "Acme Co", "company_domain": "acme.com"},
    ]
    path = _write_fixture(tmp_path, entries)
    adapter = VisualVisitorAdapter(fixture_path=path)
    signals = adapter.fetch_signals()
    assert len(signals) == 1
    assert signals[0].source == "visual_visitor"
    assert signals[0].external_id == "vv-1"
    assert signals[0].company_name == "Acme Co"


def test_default_fixture_loads_without_error():
    adapter = VisualVisitorAdapter()
    signals = adapter.fetch_signals()
    assert len(signals) >= 1
    assert all(s.source == "visual_visitor" for s in signals)


def test_live_mode_refuses_regardless_of_api_key():
    adapter = VisualVisitorAdapter(api_key="fake-key-present", live_mode=True)
    with pytest.raises(LiveModeNotImplementedError):
        adapter.fetch_signals()


def test_contact_fields_are_optional(tmp_path):
    entries = [{"external_id": "vv-2", "company_name": "No Contact Co", "company_domain": "nocontact.com"}]
    path = _write_fixture(tmp_path, entries)
    adapter = VisualVisitorAdapter(fixture_path=path)
    signals = adapter.fetch_signals()
    assert signals[0].contact_name is None
    assert signals[0].contact_email is None
