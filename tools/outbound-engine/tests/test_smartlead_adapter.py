import pytest

from outbound_engine.load.smartlead import LiveModeNotImplementedError, SmartleadAdapter
from outbound_engine.models import Draft, EnrichedProspect, VisitorSignal


def _prospect() -> EnrichedProspect:
    signal = VisitorSignal(
        source="visual_visitor", external_id="vv-1", company_name="Ridgeline Roofing Co",
        company_domain="ridgelineroofingco.com", contact_name="Dana Ruiz",
        contact_email="dana@ridgelineroofingco.com",
    )
    return EnrichedProspect(
        signal=signal, icp_score=82.0, icp_verdict="match",
        signal_reason="industry matches ICP", prospect_id=7,
    )


def _draft() -> Draft:
    return Draft(prospect_id=7, subject="quick one", body="hi there", draft_id=3)


def test_dry_run_load_never_makes_network_call():
    adapter = SmartleadAdapter(api_key="fake-key-not-used", live_mode=False)
    result = adapter.load(_prospect(), _draft(), campaign_name="Test Campaign")
    assert result.mode == "dry_run"
    assert result.campaign_name == "Test Campaign"
    assert "NOT called" in result.would_call


def test_dry_run_payload_shape_matches_smartlead_contract():
    adapter = SmartleadAdapter()
    result = adapter.load(_prospect(), _draft(), campaign_name="Test Campaign")
    lead = result.payload["lead"]
    assert lead["email"] == "dana@ridgelineroofingco.com"
    assert lead["first_name"] == "Dana"
    assert lead["last_name"] == "Ruiz"
    assert lead["custom_fields"]["icp_score"] == 82.0
    assert result.payload["sequence"]["subject"] == "quick one"


def test_live_mode_true_refuses_hard():
    adapter = SmartleadAdapter(api_key="fake-key", live_mode=True)
    with pytest.raises(LiveModeNotImplementedError):
        adapter.load(_prospect(), _draft(), campaign_name="Test Campaign")


def test_smartlead_adapter_module_has_no_http_import():
    import inspect

    from outbound_engine.load import smartlead

    source = inspect.getsource(smartlead)
    for forbidden in ("import requests", "import httpx", "import urllib.request", "import http.client"):
        assert forbidden not in source, f"unexpected network import found: {forbidden}"
