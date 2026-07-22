"""Client-safe view filtering — the structural-absence guarantee.

The rule from the product spec: a client-safe page can ONLY ever contain
fields on the hard-coded allowlist below. This is enforced in CODE, not
just in config — even a misconfigured visibility.yaml (someone accidentally
lists "margin_pct" as visible, or copy-pastes an internal field name) can
never leak an internal number, because the renderer only ever reads from a
ClientSafeView dataclass that has no attribute for it in the first place.

"Structural absence, not hidden by CSS" — see product-descriptions doc,
Penny Dashboard section.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The ONLY fields a client-safe page may ever show. Margin, cost, tool
# names, hourly rate, retainer, and any other client's data are never on
# this list — which means they are never reachable from this module's
# output, no matter what a config file asks for.
ALLOWED_CLIENT_SAFE_FIELDS = frozenset(
    {
        "ad_spend_usd",
        "deliverables",
        "results_note",
    }
)


@dataclass
class ClientSafeView:
    """Everything (and only everything) one client is allowed to see."""

    client_id: str
    client_name: str
    period: str
    ad_spend_usd: float | None = None
    deliverables: list[str] = field(default_factory=list)
    results_note: str = ""


def build_client_safe_view(
    *,
    client_id: str,
    client_name: str,
    period: str,
    ad_spend_usd: float,
    visible_fields: list[str],
    deliverables: list[str] | None = None,
    results_note: str = "",
) -> ClientSafeView:
    """Build the client-safe view, honoring only allowlisted fields.

    `visible_fields` comes from visibility.yaml and can only NARROW what's
    shown for this client — it can never widen it beyond
    ALLOWED_CLIENT_SAFE_FIELDS. A typo or a copy-pasted internal field name
    in config is silently dropped, never rendered.
    """
    requested = set(visible_fields)
    granted = requested & ALLOWED_CLIENT_SAFE_FIELDS

    view = ClientSafeView(
        client_id=client_id,
        client_name=client_name,
        period=period,
    )
    if "ad_spend_usd" in granted:
        view.ad_spend_usd = ad_spend_usd
    if "deliverables" in granted:
        view.deliverables = list(deliverables or [])
    if "results_note" in granted:
        view.results_note = results_note
    return view


def describe_dropped_fields(visible_fields: list[str]) -> list[str]:
    """Which requested fields were dropped for not being on the allowlist.

    Useful for `run.py` to warn a member their visibility.yaml asked for
    something that will never show up, without ever printing what the
    (blocked) internal value would have been.
    """
    return sorted(set(visible_fields) - ALLOWED_CLIENT_SAFE_FIELDS)
