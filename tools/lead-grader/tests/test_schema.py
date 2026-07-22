"""Tests for the normalized Lead / Grade schema every adapter must produce."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lead_grader.schema import (
    GRADE_EMOJI,
    VALID_GRADES,
    Grade,
    Lead,
    emoji_for,
    is_valid_grade,
    normalize_grade_label,
)


def test_lead_has_sane_defaults():
    lead = Lead(
        id="CAL123",
        client="acme",
        source="callrail",
        occurred_at=datetime(2026, 7, 20, 14, 30, tzinfo=timezone.utc),
    )
    assert lead.caller is None
    assert lead.duration_seconds is None
    assert lead.transcript == ""
    assert lead.recording_url is None
    assert lead.raw == {}


def test_lead_raw_defaults_are_independent_between_instances():
    # dataclass mutable-default footgun — each Lead must get its own dict.
    lead_a = Lead(id="a", client="acme", source="callrail", occurred_at=datetime.now(timezone.utc))
    lead_b = Lead(id="b", client="acme", source="callrail", occurred_at=datetime.now(timezone.utc))
    lead_a.raw["x"] = 1
    assert lead_b.raw == {}


@pytest.mark.parametrize("grade", VALID_GRADES)
def test_grade_emoji_covers_every_valid_grade(grade):
    assert grade in GRADE_EMOJI
    assert emoji_for(grade) == GRADE_EMOJI[grade]


def test_emoji_for_unknown_grade_falls_back_safely():
    assert emoji_for("Not A Grade") == "❓"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("hot", "Hot"),
        (" HOT ", "Hot"),
        ("Qualified", "Qualified"),
        ("qualified", "Qualified"),
        ("weak", "Weak"),
        ("junk", "Junk"),
        ("JUNK", "Junk"),
    ],
)
def test_normalize_grade_label_is_case_and_whitespace_tolerant(raw, expected):
    assert normalize_grade_label(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "spam", "hottt", 42, "maybe"])
def test_normalize_grade_label_returns_none_for_anything_unrecognized(raw):
    assert normalize_grade_label(raw) is None


def test_is_valid_grade():
    assert is_valid_grade("Hot") is True
    assert is_valid_grade("hot") is False  # exact-form check, not normalizing
    assert is_valid_grade("Bogus") is False


def test_grade_construction_and_defaults():
    grade = Grade(lead_id="CAL123", client="acme", grade="Hot", reason="Ready to buy this week.")
    assert grade.quote == ""
    assert grade.model == ""
    assert grade.graded_at is not None
