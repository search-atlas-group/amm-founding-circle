"""Optional, read-only Google Ads spend pull.

The `google-ads` package is intentionally NOT a hard dependency — most
members will run Penny Dashboard on manual/CSV spend data (v1's actual
supported path per the product spec). This module only imports the Google
Ads client library when a client config asks for it, so the tool works
with zero Ads setup out of the box.

Every call in this module is READ-ONLY (a metrics-reporting query). Penny
Dashboard never writes to a Google Ads account — matches the "find and
report first, read-only by default" posture used across all six Founding
Circle products.
"""

from __future__ import annotations

import csv
from pathlib import Path


class GoogleAdsUnavailable(Exception):
    """Raised when Google Ads spend was requested but the library/creds
    aren't set up. Callers should fall back to CSV/manual spend, not abort."""


def spend_from_google_ads(customer_id: str, period: str) -> float:
    """Pull total ad spend for `customer_id` in `period` (YYYY-MM), read-only.

    Requires the `google-ads` package installed and a `google-ads.yaml` in
    the working directory (the official client library's own config
    format) with a developer token + OAuth refresh token the member
    generates themselves in their own Google Ads account. See:
    https://developers.google.com/google-ads/api/docs/client-libs/python/oauth-desktop
    """
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError as e:
        raise GoogleAdsUnavailable(
            "google-ads package not installed. Run `pip install google-ads` "
            "or set manual_spend_csv for this client instead."
        ) from e

    client = GoogleAdsClient.load_from_storage()  # reads ./google-ads.yaml
    ga_service = client.get_service("GoogleAdsService")

    year, month = period.split("-")
    query = f"""
        SELECT metrics.cost_micros
        FROM customer
        WHERE segments.month = '{year}-{month}-01'
    """
    total_micros = 0
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    for batch in response:
        for row in batch.results:
            total_micros += row.metrics.cost_micros
    return total_micros / 1_000_000


def spend_from_csv(csv_path: str, period: str) -> float:
    """Fallback: sum a `date,amount_usd` CSV for the given YYYY-MM period.

    This is the path most members will actually use in v1 — export spend
    from whichever ad platform's UI and drop it in as a CSV, no API/OAuth
    setup required. Rows outside `period` are ignored so the same file can
    hold a full year of history.
    """
    path = Path(csv_path)
    if not path.exists():
        return 0.0
    total = 0.0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = (row.get("date") or "").strip()
            if date.startswith(period):
                total += float(row.get("amount_usd", 0) or 0)
    return total


def resolve_client_spend(
    *,
    google_ads_customer_id: str | None,
    manual_spend_csv: str | None,
    period: str,
) -> float:
    """Pick whichever spend source the client config actually provides.

    Prefers the Google Ads pull when a customer_id is configured; falls
    back to the CSV when Ads isn't set up; returns 0.0 (never raises) when
    neither is set, so one client with no ad spend tracked yet never
    breaks the whole run.
    """
    if google_ads_customer_id:
        try:
            return spend_from_google_ads(google_ads_customer_id, period)
        except GoogleAdsUnavailable:
            pass  # fall through to CSV/zero rather than aborting the run
    if manual_spend_csv:
        return spend_from_csv(manual_spend_csv, period)
    return 0.0
