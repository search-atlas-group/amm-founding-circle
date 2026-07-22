import pytest

from penny_dashboard.margin import (
    MarkupRule,
    allocate_fixed_costs,
    compute_ad_spend_markup,
    compute_client_financials,
    margin_trend,
)


class TestComputeAdSpendMarkup:
    def test_none_markup_is_zero(self):
        assert compute_ad_spend_markup(1000.0, MarkupRule(type="none")) == 0.0

    def test_flat_markup(self):
        assert compute_ad_spend_markup(1000.0, MarkupRule(type="flat", value=150.0)) == 150.0

    def test_flat_markup_never_negative(self):
        assert compute_ad_spend_markup(1000.0, MarkupRule(type="flat", value=-50.0)) == 0.0

    def test_percent_markup(self):
        assert compute_ad_spend_markup(1000.0, MarkupRule(type="percent", value=10.0)) == 100.0

    def test_percent_markup_zero_spend(self):
        assert compute_ad_spend_markup(0.0, MarkupRule(type="percent", value=10.0)) == 0.0

    def test_negative_spend_rejected(self):
        with pytest.raises(ValueError):
            compute_ad_spend_markup(-10.0, MarkupRule(type="none"))

    def test_unknown_rule_type_rejected(self):
        with pytest.raises(ValueError):
            compute_ad_spend_markup(100.0, MarkupRule(type="bogus"))


class TestComputeClientFinancials:
    def test_percent_markup_end_to_end(self):
        result = compute_client_financials(
            client_id="acme",
            period="2026-07",
            retainer_usd=2000.0,
            ad_spend_usd=1000.0,
            markup_rule=MarkupRule(type="percent", value=10.0),
            tool_cost_usd=150.0,
        )
        # billed = 2000 + 1000 + 100 = 3100
        # cost   = 1000 + 150 + 0    = 1150
        # margin = 1950 -> 1950/3100 = 62.90%
        assert result.billed_usd == 3100.0
        assert result.cost_usd == 1150.0
        assert result.margin_usd == 1950.0
        assert result.margin_pct == pytest.approx(62.9, abs=0.01)

    def test_flat_markup_and_labor_cost(self):
        result = compute_client_financials(
            client_id="bolt-hvac",
            period="2026-07",
            retainer_usd=1500.0,
            ad_spend_usd=500.0,
            markup_rule=MarkupRule(type="flat", value=150.0),
            tool_cost_usd=50.0,
            hours=4.0,
            hourly_rate_usd=75.0,
        )
        # billed = 1500 + 500 + 150 = 2150
        # cost   = 500 + 50 + (4*75=300) = 850
        assert result.billed_usd == 2150.0
        assert result.labor_cost_usd == 300.0
        assert result.cost_usd == 850.0
        assert result.margin_usd == 1300.0

    def test_zero_billed_gives_zero_pct_not_a_crash(self):
        result = compute_client_financials(
            client_id="freebie",
            period="2026-07",
            retainer_usd=0.0,
            ad_spend_usd=0.0,
            markup_rule=MarkupRule(type="none"),
            tool_cost_usd=0.0,
        )
        assert result.billed_usd == 0.0
        assert result.margin_pct == 0.0

    @pytest.mark.parametrize(
        "field,value",
        [
            ("retainer_usd", -1.0),
            ("ad_spend_usd", -1.0),
            ("tool_cost_usd", -1.0),
            ("hours", -1.0),
            ("hourly_rate_usd", -1.0),
        ],
    )
    def test_negative_inputs_rejected(self, field, value):
        kwargs = dict(
            client_id="x",
            period="2026-07",
            retainer_usd=100.0,
            ad_spend_usd=100.0,
            markup_rule=MarkupRule(type="none"),
            tool_cost_usd=10.0,
            hours=0.0,
            hourly_rate_usd=0.0,
        )
        kwargs[field] = value
        with pytest.raises(ValueError):
            compute_client_financials(**kwargs)


class TestAllocateFixedCosts:
    def test_even_split_across_clients(self):
        costs = [{"name": "seat", "amount_usd": 300.0, "allocation": "even"}]
        result = allocate_fixed_costs(costs, ["a", "b", "c"])
        assert result == {"a": 100.0, "b": 100.0, "c": 100.0}

    def test_multiple_costs_sum(self):
        costs = [
            {"name": "seat", "amount_usd": 300.0, "allocation": "even"},
            {"name": "tracker", "amount_usd": 100.0, "allocation": "even"},
        ]
        result = allocate_fixed_costs(costs, ["a", "b"])
        assert result == {"a": 200.0, "b": 200.0}

    def test_per_client_override_adds_on_top(self):
        costs = [{"name": "seat", "amount_usd": 200.0, "allocation": "even"}]
        result = allocate_fixed_costs(
            costs, ["a", "b"], per_client_overrides={"a": {"extra_costs_usd": 50.0}}
        )
        assert result["a"] == 150.0
        assert result["b"] == 100.0

    def test_no_active_clients_returns_empty(self):
        assert allocate_fixed_costs([{"amount_usd": 100.0}], []) == {}

    def test_unknown_allocation_method_rejected(self):
        with pytest.raises(ValueError):
            allocate_fixed_costs([{"amount_usd": 100.0, "allocation": "weighted"}], ["a"])

    def test_override_for_inactive_client_is_ignored(self):
        costs = [{"amount_usd": 100.0, "allocation": "even"}]
        result = allocate_fixed_costs(costs, ["a"], per_client_overrides={"ghost": {"extra_costs_usd": 999}})
        assert result == {"a": 100.0}


class TestMarginTrend:
    def test_no_history_returns_none(self):
        assert margin_trend(50.0, None) is None

    def test_improvement_is_positive(self):
        assert margin_trend(55.0, 50.0) == 5.0

    def test_decline_is_negative(self):
        assert margin_trend(45.0, 50.0) == -5.0
