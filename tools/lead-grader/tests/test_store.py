"""Store tests — in-memory SQLite (":memory:"), so nothing touches disk."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lead_grader import store
from lead_grader.schema import Grade, Lead


@pytest.fixture()
def conn():
    c = store.connect(":memory:")
    yield c
    c.close()


def _lead(id_="L1", client="acme", occurred_at=None, transcript="hello"):
    return Lead(
        id=id_,
        client=client,
        source="callrail",
        occurred_at=occurred_at or datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        transcript=transcript,
        raw={"id": id_},
    )


def test_upsert_lead_new_then_duplicate(conn):
    lead = _lead()
    assert store.upsert_lead(conn, lead) is True
    assert store.upsert_lead(conn, lead) is False  # dedupe on re-import
    assert len(store.all_leads(conn, "acme")) == 1


def test_ungraded_leads_excludes_graded_ones(conn):
    store.upsert_lead(conn, _lead("L1"))
    store.upsert_lead(conn, _lead("L2"))
    assert {lead.id for lead in store.ungraded_leads(conn, "acme")} == {"L1", "L2"}

    store.save_grade(conn, Grade(lead_id="L1", client="acme", grade="Hot", reason="ready now"))
    assert [lead.id for lead in store.ungraded_leads(conn, "acme")] == ["L2"]


def test_save_grade_upserts_on_regrade(conn):
    store.upsert_lead(conn, _lead("L1"))
    store.save_grade(conn, Grade(lead_id="L1", client="acme", grade="Weak", reason="unsure"))
    store.save_grade(conn, Grade(lead_id="L1", client="acme", grade="Hot", reason="actually great"))

    results = store.leads_with_grades_for_date(conn, "acme", datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert len(results) == 1
    _, grade = results[0]
    assert grade.grade == "Hot"
    assert grade.reason == "actually great"


def test_leads_with_grades_for_date_scopes_to_day_and_client(conn):
    d20 = datetime(2026, 7, 20, 9, tzinfo=timezone.utc)
    d21 = datetime(2026, 7, 21, 9, tzinfo=timezone.utc)
    store.upsert_lead(conn, _lead("L1", client="acme", occurred_at=d20))
    store.upsert_lead(conn, _lead("L2", client="acme", occurred_at=d21))
    store.upsert_lead(conn, _lead("L3", client="other", occurred_at=d20))
    for lid in ("L1", "L2", "L3"):
        client = "acme" if lid != "L3" else "other"
        store.save_grade(conn, Grade(lead_id=lid, client=client, grade="Hot", reason="x"))

    results = store.leads_with_grades_for_date(conn, "acme", datetime(2026, 7, 20, tzinfo=timezone.utc))
    assert [lead.id for lead, _ in results] == ["L1"]


def test_trend_aggregates_by_day_and_grade(conn):
    day = datetime.now(timezone.utc)
    store.upsert_lead(conn, _lead("L1", occurred_at=day))
    store.upsert_lead(conn, _lead("L2", occurred_at=day))
    store.save_grade(conn, Grade(lead_id="L1", client="acme", grade="Hot", reason="x"))
    store.save_grade(conn, Grade(lead_id="L2", client="acme", grade="Junk", reason="x"))

    result = store.trend(conn, "acme", days=7)
    today_key = day.date().isoformat()
    assert result[today_key]["Hot"] == 1
    assert result[today_key]["Junk"] == 1


def test_raw_payload_roundtrips_through_json(conn):
    lead = _lead("L1")
    lead.raw = {"id": "L1", "nested": {"a": 1}}
    store.upsert_lead(conn, lead)
    stored = store.all_leads(conn, "acme")[0]
    assert stored.raw == {"id": "L1", "nested": {"a": 1}}
