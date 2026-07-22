import pytest

from outbound_engine.review_queue import apply_decision, list_pending
from outbound_engine.models import Draft, EnrichedProspect, VisitorSignal


def _seed_prospect(store, external_id="vv-1", contact_name="Dana Ruiz"):
    signal = VisitorSignal(
        source="visual_visitor", external_id=external_id, company_name="Ridgeline Roofing Co",
        company_domain="ridgelineroofingco.com", contact_name=contact_name,
        contact_email="dana@ridgelineroofingco.com",
    )
    prospect_id, _ = store.upsert_signal(signal)
    enriched = EnrichedProspect(
        signal=signal, icp_score=82.0, icp_verdict="match",
        signal_reason="industry matches ICP", prospect_id=prospect_id,
    )
    store.record_enrichment(prospect_id, enriched)
    draft_id = store.add_draft(Draft(prospect_id=prospect_id, subject="quick one", body="hi there"))
    return prospect_id, draft_id


def test_list_pending_returns_seeded_draft(store):
    _seed_prospect(store)
    pending = list_pending(store)
    assert len(pending) == 1
    assert pending[0].company_name == "Ridgeline Roofing Co"
    assert pending[0].icp_verdict == "match"


def test_approve_moves_prospect_and_draft_to_approved(store):
    prospect_id, draft_id = _seed_prospect(store)
    apply_decision(store, draft_id, "approve")
    assert store.get_prospect(prospect_id)["status"] == "approved"
    assert store.get_draft(draft_id)["status"] == "approved"
    assert list_pending(store) == []


def test_skip_removes_from_pending_but_keeps_history(store):
    prospect_id, draft_id = _seed_prospect(store)
    apply_decision(store, draft_id, "skip")
    assert store.get_prospect(prospect_id)["status"] == "skipped"
    assert list_pending(store) == []


def test_reject_removes_from_pending(store):
    prospect_id, draft_id = _seed_prospect(store)
    apply_decision(store, draft_id, "reject")
    assert store.get_prospect(prospect_id)["status"] == "rejected"


def test_edit_overwrites_subject_and_body_then_approves(store):
    prospect_id, draft_id = _seed_prospect(store)
    apply_decision(store, draft_id, "edit", edited_subject="new subject", edited_body="new body text")
    draft = store.get_draft(draft_id)
    assert draft["subject"] == "new subject"
    assert draft["body"] == "new body text"
    assert draft["status"] == "approved"


def test_edit_without_edited_fields_raises(store):
    prospect_id, draft_id = _seed_prospect(store)
    with pytest.raises(ValueError):
        apply_decision(store, draft_id, "edit")


def test_pending_list_sorted_by_icp_score_desc(store):
    p1, d1 = _seed_prospect(store, external_id="vv-1")
    # second prospect scores lower
    signal2 = VisitorSignal(
        source="visual_visitor", external_id="vv-2", company_name="Low Score Co",
        company_domain="lowscore.com",
    )
    p2_id, _ = store.upsert_signal(signal2)
    store.record_enrichment(p2_id, EnrichedProspect(
        signal=signal2, icp_score=20.0, icp_verdict="reject", signal_reason="weak", prospect_id=p2_id,
    ))
    d2 = store.add_draft(Draft(prospect_id=p2_id, subject="s2", body="b2"))

    pending = list_pending(store)
    assert pending[0].icp_score >= pending[1].icp_score
