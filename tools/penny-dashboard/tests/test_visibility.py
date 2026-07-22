from penny_dashboard.visibility import (
    ALLOWED_CLIENT_SAFE_FIELDS,
    build_client_safe_view,
    describe_dropped_fields,
)


class TestAllowlistIsClosed:
    """The whole security model rests on this list never accidentally
    growing to include an internal field. Lock the exact contents down
    so a future edit can't silently widen it."""

    def test_exact_allowed_fields(self):
        assert ALLOWED_CLIENT_SAFE_FIELDS == frozenset({"ad_spend_usd", "deliverables", "results_note"})

    def test_margin_and_cost_fields_never_allowed(self):
        blocked = {
            "margin_usd",
            "margin_pct",
            "cost_usd",
            "tool_cost_usd",
            "labor_cost_usd",
            "hourly_rate_usd",
            "retainer_usd",
            "billed_usd",
            "client_id",
        }
        assert blocked.isdisjoint(ALLOWED_CLIENT_SAFE_FIELDS)


class TestBuildClientSafeView:
    def test_only_requested_and_allowed_fields_are_populated(self):
        view = build_client_safe_view(
            client_id="acme",
            client_name="Acme Roofing",
            period="2026-07",
            ad_spend_usd=1000.0,
            visible_fields=["ad_spend_usd"],
            deliverables=["Shipped a landing page"],
            results_note="Great month.",
        )
        assert view.ad_spend_usd == 1000.0
        # not requested -> stays at the dataclass default, never populated
        assert view.deliverables == []
        assert view.results_note == ""

    def test_all_three_allowed_fields_together(self):
        view = build_client_safe_view(
            client_id="acme",
            client_name="Acme Roofing",
            period="2026-07",
            ad_spend_usd=500.0,
            visible_fields=["ad_spend_usd", "deliverables", "results_note"],
            deliverables=["Fixed the contact form"],
            results_note="Traffic up 8%.",
        )
        assert view.ad_spend_usd == 500.0
        assert view.deliverables == ["Fixed the contact form"]
        assert view.results_note == "Traffic up 8%."

    def test_internal_field_name_in_config_is_a_silent_no_op(self):
        """A misconfigured visibility.yaml that lists an internal field
        (e.g. copy-pasted "margin_pct") must never surface it — the
        ClientSafeView object simply has no attribute for it."""
        view = build_client_safe_view(
            client_id="acme",
            client_name="Acme Roofing",
            period="2026-07",
            ad_spend_usd=500.0,
            visible_fields=["margin_pct", "cost_usd", "ad_spend_usd"],
            deliverables=[],
            results_note="",
        )
        assert view.ad_spend_usd == 500.0  # the one legit field still works
        assert not hasattr(view, "margin_pct")
        assert not hasattr(view, "cost_usd")

    def test_no_visible_fields_gives_empty_view(self):
        view = build_client_safe_view(
            client_id="acme",
            client_name="Acme Roofing",
            period="2026-07",
            ad_spend_usd=500.0,
            visible_fields=[],
        )
        assert view.ad_spend_usd is None
        assert view.deliverables == []
        assert view.results_note == ""


class TestDescribeDroppedFields:
    def test_reports_unknown_fields_only(self):
        dropped = describe_dropped_fields(["ad_spend_usd", "margin_pct", "cost_usd"])
        assert dropped == ["cost_usd", "margin_pct"]

    def test_all_allowed_fields_reports_nothing(self):
        assert describe_dropped_fields(["ad_spend_usd", "deliverables", "results_note"]) == []
