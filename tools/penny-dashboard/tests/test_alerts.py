from penny_dashboard.alerts import (
    build_alert_lines,
    find_low_margin_clients,
    format_alert_line,
)
from penny_dashboard.margin import MarkupRule, compute_client_financials


def _financials(client_id: str, margin_pct_target: float):
    """Build a ClientFinancials whose margin_pct lands at the target, via
    a simple retainer-only, zero-cost scenario (billed==margin so
    margin_pct == 100 - shortfall works out cleanly)."""
    # billed=100, cost = 100 - margin_pct_target -> margin_pct = margin_pct_target
    return compute_client_financials(
        client_id=client_id,
        period="2026-07",
        retainer_usd=100.0,
        ad_spend_usd=0.0,
        markup_rule=MarkupRule(type="none"),
        tool_cost_usd=100.0 - margin_pct_target,
    )


class TestFindLowMarginClients:
    def test_filters_at_and_below_threshold(self):
        rows = [_financials("a", 10.0), _financials("b", 20.0), _financials("c", 30.0)]
        low = find_low_margin_clients(rows, threshold_pct=20.0)
        ids = {r.client_id for r in low}
        assert ids == {"a", "b"}  # 20.0 is at the threshold -> included

    def test_empty_when_all_healthy(self):
        rows = [_financials("a", 50.0)]
        assert find_low_margin_clients(rows, threshold_pct=20.0) == []


class TestFormatAlertLine:
    def test_plain_english_line(self):
        line = format_alert_line("Acme Roofing", 12.5, 20.0)
        assert "Acme Roofing" in line
        assert "12.5%" in line
        assert "20%" in line


class TestBuildAlertLines:
    def test_uses_client_names_when_provided(self):
        rows = [_financials("acme", 10.0)]
        lines = build_alert_lines(rows, threshold_pct=20.0, client_names={"acme": "Acme Roofing"})
        assert len(lines) == 1
        assert "Acme Roofing" in lines[0]

    def test_falls_back_to_client_id_without_names(self):
        rows = [_financials("acme", 10.0)]
        lines = build_alert_lines(rows, threshold_pct=20.0)
        assert "acme" in lines[0]

    def test_no_lines_when_nothing_below_threshold(self):
        rows = [_financials("acme", 90.0)]
        assert build_alert_lines(rows, threshold_pct=20.0) == []
