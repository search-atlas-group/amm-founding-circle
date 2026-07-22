from outbound_engine.models import EnrichedProspect, VisitorSignal
from outbound_engine.personalize.personalizer import (
    MockLLMClient,
    _mock_draft,
    _parse_subject_body,
    build_client,
    personalize,
)


def _enriched(**overrides) -> EnrichedProspect:
    signal = VisitorSignal(
        source="visual_visitor", external_id="vv-1", company_name="Ridgeline Roofing Co",
        company_domain="ridgelineroofingco.com", page_path="/pricing", visit_count=3,
        referrer_type="organic", contact_name="Dana Ruiz", contact_role="Marketing Director",
        contact_email="dana@ridgelineroofingco.com",
    )
    defaults = dict(
        signal=signal, icp_score=82.0, icp_verdict="match",
        signal_reason="industry matches ICP; visited a high-intent page (/pricing)",
        prospect_id=1,
    )
    defaults.update(overrides)
    return EnrichedProspect(**defaults)


class _FakeRealClient:
    """Stands in for ClaudeCliClient/GeminiCliClient without shelling out."""

    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        return self.response


def test_default_provider_is_mock_no_network():
    prospect = _enriched()
    draft = personalize(prospect)  # no client passed -> MockLLMClient
    assert draft.subject
    assert draft.body
    assert draft.prospect_id == 1
    assert "mock template" in draft.voice_notes


def test_mock_draft_references_signal_reason_and_company():
    prospect = _enriched()
    draft = _mock_draft(prospect)
    assert "Ridgeline Roofing Co" in draft.body
    assert prospect.signal_reason in draft.body


def test_personalize_with_real_client_parses_subject_and_body():
    fake = _FakeRealClient("SUBJECT: worth a look?\nBODY: Hi Dana, saw you checking pricing. Free 15 min?\n")
    prospect = _enriched()
    draft = personalize(prospect, voice_examples="be casual", client=fake)
    assert draft.subject == "worth a look?"
    assert "Hi Dana" in draft.body
    assert "_FakeRealClient" in draft.voice_notes
    assert "be casual" in fake.last_prompt


def test_real_client_returning_none_falls_back_to_mock():
    fake = _FakeRealClient(None)  # simulates CLI unavailable / call failed
    prospect = _enriched()
    draft = personalize(prospect, client=fake)
    assert "mock template" in draft.voice_notes


def test_parse_subject_body_handles_missing_subject():
    subject, body = _parse_subject_body("BODY: just a body, no subject line", "Acme Co")
    assert subject == "quick one about Acme Co"
    assert body == "just a body, no subject line"


def test_build_client_defaults_to_mock_for_unknown_provider():
    client = build_client("something-unrecognized")
    assert isinstance(client, MockLLMClient)


def test_never_invents_facts_not_in_prospect_record():
    # The prompt sent to a real client must only ever contain what's on the
    # EnrichedProspect / VisitorSignal — no fabricated stats get injected.
    fake = _FakeRealClient("SUBJECT: hi\nBODY: hi")
    prospect = _enriched()
    personalize(prospect, client=fake)
    assert "Ridgeline Roofing Co" in fake.last_prompt
    assert prospect.signal_reason in fake.last_prompt
