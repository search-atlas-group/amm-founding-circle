from outbound_engine.enrich.enrichment import enrich
from outbound_engine.models import VisitorSignal


def _signal(**overrides) -> VisitorSignal:
    defaults = dict(
        source="visual_visitor", external_id="vv-1", company_name="Ridgeline Roofing Co",
        company_domain="ridgelineroofingco.com", page_path="/pricing", visit_count=3,
        referrer_type="organic", contact_name="Dana Ruiz", contact_role="Marketing Director",
        contact_email="dana@ridgelineroofingco.com",
    )
    defaults.update(overrides)
    return VisitorSignal(**defaults)


def test_strong_match_scores_high(sample_icp):
    signal = _signal()  # roofing, pricing page, 3 visits, organic, has contact
    result = enrich(signal, sample_icp)
    assert result.icp_verdict == "match"
    assert result.icp_score >= sample_icp["scoring"]["match_threshold"]
    assert "industry matches ICP" in result.signal_reason
    assert result.needs_manual_contact_lookup is False


def test_edu_domain_is_hard_excluded(sample_icp):
    signal = _signal(company_domain="stateu.edu", company_name="State University Marketing Dept",
                      contact_name=None, contact_email=None)
    result = enrich(signal, sample_icp)
    assert result.icp_verdict == "reject"
    assert result.icp_score == 0.0
    assert ".edu" in result.signal_reason


def test_agency_name_is_excluded_as_competitor(sample_icp):
    signal = _signal(company_name="Ironclad Digital Agency", company_domain="ironcladagency.com",
                      contact_name=None, contact_email=None)
    result = enrich(signal, sample_icp)
    assert result.icp_verdict == "reject"
    assert "agency" in result.signal_reason.lower()


def test_explicit_exclude_term_matches(sample_icp):
    signal = _signal(company_name="Acme Current Clients Inc")
    result = enrich(signal, sample_icp)
    assert result.icp_verdict == "reject"
    assert "excluded" in result.signal_reason


def test_no_contact_flags_needs_manual_lookup(sample_icp):
    signal = _signal(contact_name=None, contact_email=None, contact_role=None)
    result = enrich(signal, sample_icp)
    assert result.needs_manual_contact_lookup is True


def test_weak_signal_scores_low_not_excluded(sample_icp):
    # No industry match, no page/visit/referrer signal at all
    signal = _signal(
        company_name="Generic Widgets Co", page_path=None, visit_count=1,
        referrer_type="unknown", contact_name=None, contact_email=None,
    )
    result = enrich(signal, sample_icp)
    assert result.icp_verdict in {"maybe", "reject"}
    assert result.icp_score < sample_icp["scoring"]["match_threshold"]


def test_scoring_is_deterministic(sample_icp):
    signal = _signal()
    r1 = enrich(signal, sample_icp)
    r2 = enrich(signal, sample_icp)
    assert r1.icp_score == r2.icp_score
    assert r1.icp_verdict == r2.icp_verdict
