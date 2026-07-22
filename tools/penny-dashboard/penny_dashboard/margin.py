"""Core margin math for the Penny Dashboard.

Pure functions, no I/O — kept separate from config/rendering/adapters so
this is trivially unit-testable and the math is never duplicated elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarkupRule:
    """How a client's ad-spend markup is billed on top of raw ad spend."""

    type: str = "none"  # "none" | "flat" | "percent"
    value: float = 0.0  # flat: USD amount; percent: 0-100


@dataclass
class ClientFinancials:
    """One client's computed period financials — the single source of
    truth both the owner view and the alerts/history layers read from."""

    client_id: str
    period: str  # "YYYY-MM"
    retainer_usd: float
    ad_spend_usd: float
    ad_spend_markup_usd: float
    tool_cost_usd: float
    hours: float
    hourly_rate_usd: float
    labor_cost_usd: float
    billed_usd: float
    cost_usd: float
    margin_usd: float
    margin_pct: float


def compute_ad_spend_markup(ad_spend_usd: float, rule: MarkupRule) -> float:
    """What the client is billed ON TOP of raw ad spend, per the markup rule."""
    if ad_spend_usd < 0:
        raise ValueError("ad_spend_usd cannot be negative")
    if rule.type == "none":
        return 0.0
    if rule.type == "flat":
        return max(0.0, rule.value)
    if rule.type == "percent":
        return ad_spend_usd * (rule.value / 100.0)
    raise ValueError(f"unknown markup rule type: {rule.type!r}")


def compute_client_financials(
    *,
    client_id: str,
    period: str,
    retainer_usd: float,
    ad_spend_usd: float,
    markup_rule: MarkupRule,
    tool_cost_usd: float,
    hours: float = 0.0,
    hourly_rate_usd: float = 0.0,
) -> ClientFinancials:
    """Compute billed / cost / margin for one client in one period.

    billed = retainer + (ad spend passed through to the client) + markup
    cost   = ad spend (what you actually paid the platform) + allocated
             tool cost + labor cost (hours * hourly rate, if tracked)
    margin = billed - cost
    """
    for name, val in (
        ("retainer_usd", retainer_usd),
        ("ad_spend_usd", ad_spend_usd),
        ("tool_cost_usd", tool_cost_usd),
        ("hours", hours),
        ("hourly_rate_usd", hourly_rate_usd),
    ):
        if val < 0:
            raise ValueError(f"{name} must be non-negative, got {val!r}")

    markup_usd = compute_ad_spend_markup(ad_spend_usd, markup_rule)
    labor_cost_usd = hours * hourly_rate_usd

    billed_usd = retainer_usd + ad_spend_usd + markup_usd
    cost_usd = ad_spend_usd + tool_cost_usd + labor_cost_usd
    margin_usd = billed_usd - cost_usd
    margin_pct = (margin_usd / billed_usd * 100.0) if billed_usd > 0 else 0.0

    return ClientFinancials(
        client_id=client_id,
        period=period,
        retainer_usd=retainer_usd,
        ad_spend_usd=ad_spend_usd,
        ad_spend_markup_usd=markup_usd,
        tool_cost_usd=tool_cost_usd,
        hours=hours,
        hourly_rate_usd=hourly_rate_usd,
        labor_cost_usd=labor_cost_usd,
        billed_usd=billed_usd,
        cost_usd=cost_usd,
        margin_usd=margin_usd,
        margin_pct=round(margin_pct, 2),
    )


def allocate_fixed_costs(
    fixed_costs: list[dict],
    active_client_ids: list[str],
    per_client_overrides: dict | None = None,
) -> dict[str, float]:
    """Split monthly fixed tool costs across active clients.

    Costs with allocation "even" are split equally across every active
    client. Per-client overrides add a flat extra amount on top (e.g. a
    tool seat dedicated to one client).
    """
    per_client_overrides = per_client_overrides or {}
    n = len(active_client_ids)
    allocation: dict[str, float] = {cid: 0.0 for cid in active_client_ids}

    if n == 0:
        return allocation

    for cost in fixed_costs:
        amount = float(cost.get("amount_usd", 0.0))
        method = cost.get("allocation", "even")
        if method == "even":
            share = amount / n
            for cid in active_client_ids:
                allocation[cid] += share
        else:
            raise ValueError(f"unknown allocation method: {method!r}")

    for cid, override in per_client_overrides.items():
        if cid in allocation:
            allocation[cid] += float(override.get("extra_costs_usd", 0.0))

    return allocation


def margin_trend(current_pct: float, previous_pct: float | None) -> float | None:
    """Percentage-point delta vs. the previous period, or None with no history."""
    if previous_pct is None:
        return None
    return round(current_pct - previous_pct, 2)
