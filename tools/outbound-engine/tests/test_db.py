from outbound_engine.models import VisitorSignal


def _signal(external_id="vv-1"):
    return VisitorSignal(
        source="visual_visitor", external_id=external_id, company_name="Acme Co",
        company_domain="acme.com",
    )


def test_upsert_signal_is_idempotent_on_source_and_external_id(store):
    id1, created1 = store.upsert_signal(_signal())
    id2, created2 = store.upsert_signal(_signal())
    assert id1 == id2
    assert created1 is True
    assert created2 is False
    assert len(store.list_prospects()) == 1


def test_track_run_records_success(store):
    with store.track_run("signals") as counters:
        counters["count_in"] = 3
        counters["count_out"] = 2
    row = store.conn.execute("SELECT * FROM runs WHERE stage = 'signals'").fetchone()
    assert row["status"] == "ok"
    assert row["count_in"] == 3
    assert row["count_out"] == 2
    assert row["finished_at"] is not None


def test_track_run_records_error_status_and_reraises(store):
    import pytest

    with pytest.raises(RuntimeError):
        with store.track_run("enrich"):
            raise RuntimeError("boom")

    row = store.conn.execute("SELECT * FROM runs WHERE stage = 'enrich'").fetchone()
    assert row["status"] == "error"


def test_events_are_logged_on_prospect_add(store):
    store.upsert_signal(_signal())
    events = store.event_counts_since("2000-01-01T00:00:00")
    assert events.get("prospect_added") == 1
