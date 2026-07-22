from outbound_engine.report import generate_weekly_report


def test_report_generates_on_empty_store(store, tmp_path):
    out = generate_weekly_report(store, tmp_path / "report.html")
    assert out.exists()
    html = out.read_text()
    assert "Outbound Engine" in html
    assert "No prospects yet." in html
    assert "Dry-run build." in html


def test_report_reflects_pipeline_activity(store, sample_icp, tmp_path):
    from outbound_engine import pipeline
    from outbound_engine.review_queue import apply_decision, list_pending
    from outbound_engine.signals.visual_visitor import VisualVisitorAdapter

    pipeline.run_dry_run_pipeline(store, sample_icp, signal_adapter=VisualVisitorAdapter())
    pending = list_pending(store)
    apply_decision(store, pending[0].draft_id, "approve")

    out = generate_weekly_report(store, tmp_path / "report.html", cost_comparison_note=sample_icp["cost_comparison"])
    html = out.read_text()
    assert "Replaces ~$700/mo Apollo" in html
    assert "n/a — dry-run build" in html


def test_report_never_shows_fabricated_send_metrics(store, tmp_path):
    # No live sending in this build -> opens/replies/booked must read n/a, never a number.
    out = generate_weekly_report(store, tmp_path / "report.html")
    html = out.read_text()
    assert html.count("n/a — dry-run build, no live sending yet") == 4
