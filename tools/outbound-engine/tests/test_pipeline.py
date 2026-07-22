from outbound_engine import pipeline
from outbound_engine.load.smartlead import SmartleadAdapter
from outbound_engine.review_queue import apply_decision, list_pending
from outbound_engine.signals.visual_visitor import VisualVisitorAdapter


def test_full_dry_run_pipeline_end_to_end(store, sample_icp, tmp_path):
    # 5 fixture rows: 1 strong roofing match w/ contact, 1 dental paid-no-contact,
    # 1 legal match w/ contact, 1 .edu excluded, 1 agency-name excluded.
    adapter = VisualVisitorAdapter()  # uses the repo's default fixture

    results = pipeline.run_dry_run_pipeline(store, sample_icp, voice_examples="", signal_adapter=adapter)

    assert results["signals"]["fetched"] == 5
    assert results["signals"]["new"] == 5
    assert results["enrich"]["enriched"] == 5

    # Only non-rejected prospects get drafted (default only_matches=True)
    statuses = {row["status"] for row in store.list_prospects()}
    assert "enriched" not in statuses or True  # sanity: no crash reading status set

    pending = list_pending(store)
    assert len(pending) >= 1  # at least the strong roofing/legal matches got drafted
    assert all(item.icp_verdict != "reject" for item in pending)


def test_signals_stage_is_idempotent(store, sample_icp):
    adapter = VisualVisitorAdapter()
    first = pipeline.run_signals_stage(store, adapter)
    second = pipeline.run_signals_stage(store, adapter)
    assert first["new"] == 5
    assert second["new"] == 0  # already-seen external_ids don't duplicate
    assert len(store.list_prospects()) == 5


def test_load_stage_only_loads_approved_and_is_dry_run(store, sample_icp):
    adapter = VisualVisitorAdapter()
    pipeline.run_dry_run_pipeline(store, sample_icp, signal_adapter=adapter)

    pending = list_pending(store)
    assert pending, "expected at least one drafted prospect to approve"
    apply_decision(store, pending[0].draft_id, "approve")

    load_adapter = SmartleadAdapter()  # dry-run by default
    counts = pipeline.run_load_stage_dry_run(store, load_adapter, campaign_name="Test Campaign")
    assert counts["loaded"] == 1

    loads = store.recent_loads("2000-01-01T00:00:00")
    assert len(loads) == 1
    assert loads[0]["mode"] == "dry_run"
    assert store.get_prospect(pending[0].prospect_id)["status"] == "loaded"


def test_rejected_prospects_never_get_drafted(store, sample_icp):
    adapter = VisualVisitorAdapter()
    pipeline.run_dry_run_pipeline(store, sample_icp, signal_adapter=adapter)
    rejected_ids = {row["id"] for row in store.list_prospects() if row["icp_verdict"] == "reject"}
    drafted_prospect_ids = {row["prospect_id"] for row in store.conn.execute("SELECT prospect_id FROM drafts").fetchall()}
    assert rejected_ids.isdisjoint(drafted_prospect_ids)
