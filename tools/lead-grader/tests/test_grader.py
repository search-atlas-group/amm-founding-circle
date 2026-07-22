"""Grading-engine tests — response parsing is the load-bearing logic here,
so it gets the heaviest coverage: clean JSON, prose-wrapped JSON, a code
fence, a bogus grade label, empty/garbage output, and the no-transcript
short-circuit. All fully offline via a fake LLM client."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lead_grader.grader import grade_lead
from lead_grader.schema import Lead

RUBRIC = "Hot: ready to buy within 30 days. Junk: wrong number or solicitor."


def _lead(transcript="Caller wants a quote for a full roof replacement, ready this month."):
    return Lead(
        id="L1",
        client="acme",
        source="callrail",
        occurred_at=datetime.now(timezone.utc),
        transcript=transcript,
    )


class _CannedLLM:
    model = "fake-model-v1"

    def __init__(self, response: str):
        self.response = response
        self.last_call = None

    def complete(self, system, user, max_tokens=800):
        self.last_call = {"system": system, "user": user}
        return self.response


def test_clean_json_response_parses_directly():
    llm = _CannedLLM('{"grade": "Hot", "reason": "Ready to buy this month.", "quote": "ready this month"}')
    grade = grade_lead(_lead(), RUBRIC, llm)
    assert grade.grade == "Hot"
    assert grade.reason == "Ready to buy this month."
    assert grade.quote == "ready this month"
    assert grade.model == "fake-model-v1"
    assert grade.lead_id == "L1"
    assert grade.client == "acme"


def test_prose_wrapped_json_is_recovered():
    llm = _CannedLLM(
        "Sure, here is my assessment:\n"
        '{"grade": "Qualified", "reason": "Solid lead.", "quote": ""}\n'
        "Hope that helps!"
    )
    grade = grade_lead(_lead(), RUBRIC, llm)
    assert grade.grade == "Qualified"
    assert grade.reason == "Solid lead."


def test_markdown_code_fence_is_stripped():
    llm = _CannedLLM('```json\n{"grade": "Weak", "reason": "Vague timeline.", "quote": "not sure yet"}\n```')
    grade = grade_lead(_lead(), RUBRIC, llm)
    assert grade.grade == "Weak"


def test_grade_label_is_case_insensitive():
    llm = _CannedLLM('{"grade": "hot", "reason": "x", "quote": ""}')
    grade = grade_lead(_lead(), RUBRIC, llm)
    assert grade.grade == "Hot"


@pytest.mark.parametrize(
    "bad_response",
    [
        "",
        "not json at all, sorry",
        '{"grade": "Super Hot", "reason": "x"}',  # not one of the 4 valid grades
        '{"reason": "no grade field at all"}',
        "{malformed json",
    ],
)
def test_unparseable_or_invalid_response_fails_closed_to_weak(bad_response):
    llm = _CannedLLM(bad_response)
    grade = grade_lead(_lead(), RUBRIC, llm)
    assert grade.grade == "Weak"
    assert "needs human review" in grade.reason.lower()


def test_long_reason_is_truncated_to_one_line():
    long_reason = "This is a very long rambling reason. " * 20
    llm = _CannedLLM(f'{{"grade": "Junk", "reason": "{long_reason.strip()}", "quote": ""}}')
    grade = grade_lead(_lead(), RUBRIC, llm)
    assert grade.grade == "Junk"
    assert len(grade.reason) <= 280
    assert "\n" not in grade.reason


def test_no_transcript_never_calls_llm_and_grades_conservatively():
    llm = _CannedLLM('{"grade": "Hot", "reason": "should never see this"}')
    grade = grade_lead(_lead(transcript=""), RUBRIC, llm)
    assert grade.grade == "Weak"
    assert llm.last_call is None  # confirms the LLM was never invoked
    assert "no transcript" in grade.reason.lower()


def test_prompt_includes_rubric_and_transcript():
    llm = _CannedLLM('{"grade": "Hot", "reason": "x", "quote": ""}')
    lead = _lead(transcript="unique transcript marker XYZ123")
    grade_lead(lead, RUBRIC, llm)
    assert RUBRIC in llm.last_call["user"]
    assert "XYZ123" in llm.last_call["user"]
