"""Google Ads read-only checks: disapproved ads, paused campaigns, broken final URLs.

v1 scope is explicitly find-and-report ONLY — nothing here ever writes to
Google Ads. Per the spec's honest correction from Bryan Fikes' own feedback:
Google Ads is NOT fully autonomous yet, so this stays read-only in v1 with
auto-fix deliberately out of scope for a later phase.

Classification logic (pure, unit-tested) is separated from the live SDK
wrapper (`GoogleAdsChecker`) so the rules can be verified without a Google
Ads developer token or network access. The live wrapper is a thin, mostly
untested seam by design — see tests/test_google_ads.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .models import ClientConfig, Finding, Severity


class GoogleAdsNotConfigured(RuntimeError):
    """Raised when Google Ads credentials are absent — a normal, expected
    state for any member who hasn't set this up. Callers should catch this
    and record a skipped-check note, not treat it as an error."""


REQUIRED_ENV_VARS = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)


def is_configured() -> bool:
    return all(os.environ.get(v) for v in REQUIRED_ENV_VARS)


# --- Pure row shapes -------------------------------------------------------
# Plain dicts so tests never need the google-ads SDK installed.
# ad row:       {"ad_id", "ad_name", "approval_status", "status", "final_urls",
#                "campaign_name", "ad_group_name"}
# campaign row: {"campaign_name", "campaign_status"}


def classify_ad_approval(client: str, row: dict) -> Finding | None:
    if row.get("approval_status") == "DISAPPROVED":
        location = f"{row.get('campaign_name', '?')} / {row.get('ad_group_name', '?')} / ad {row.get('ad_id', '?')}"
        return Finding(
            client=client,
            category="google-ads",
            severity=Severity.CRITICAL,
            title="Disapproved ad",
            detail=row.get("ad_name") or "(unnamed ad)",
            location=location,
            suggested_fix="Open the ad in Google Ads, read the specific policy violation, and edit/resubmit.",
        )
    return None


def classify_campaign_status(client: str, row: dict) -> Finding | None:
    """A PAUSED campaign isn't automatically wrong — pausing is a normal,
    intentional lever. We flag it as a drift *signal*, not a verdict, and it's
    exactly the kind of thing a member silences via known_exceptions once
    they confirm it's deliberate."""
    status = row.get("campaign_status")
    if status == "PAUSED":
        return Finding(
            client=client,
            category="google-ads",
            severity=Severity.DEGRADING,
            title="Campaign is paused",
            detail="Campaign status is PAUSED. If this is intentional (seasonal, budget hold), add it to known_exceptions to silence.",
            location=row.get("campaign_name", "?"),
            suggested_fix="Confirm this is intentional; resume if it should be live.",
        )
    return None


def classify_final_url_status(client: str, row: dict, url: str, status_code: int) -> Finding | None:
    if status_code == 404 or 500 <= status_code < 600:
        location = f"{row.get('campaign_name', '?')} / {row.get('ad_group_name', '?')} / ad {row.get('ad_id', '?')}"
        return Finding(
            client=client,
            category="google-ads",
            severity=Severity.CRITICAL,
            title="Ad final URL is broken",
            detail=f"Final URL {url} returned {status_code}. This ad is spending money on a broken landing page.",
            location=location,
            suggested_fix="Pause the ad or fix the landing page URL immediately — this is active spend hitting a dead page.",
        )
    return None


def check_ads_and_campaigns(
    client: ClientConfig,
    ad_rows: list[dict],
    campaign_rows: list[dict],
    final_url_status_of,
) -> list[Finding]:
    """Pure orchestration over already-fetched rows.

    `final_url_status_of(url) -> int` is an injectable HTTP-status lookup so
    tests can fake it; production wires it to a real HEAD/GET.
    """
    findings: list[Finding] = []

    for row in ad_rows:
        f = classify_ad_approval(client.name, row)
        if f:
            findings.append(f)
        if row.get("status") == "ENABLED":
            for url in row.get("final_urls") or []:
                try:
                    status_code = final_url_status_of(url)
                except Exception:
                    continue
                f = classify_final_url_status(client.name, row, url, status_code)
                if f:
                    findings.append(f)

    for row in campaign_rows:
        f = classify_campaign_status(client.name, row)
        if f:
            findings.append(f)

    return findings


# --- Live SDK wrapper -------------------------------------------------------

_ADS_QUERY = """
SELECT
  ad_group_ad.ad.id,
  ad_group_ad.ad.name,
  ad_group_ad.ad.final_urls,
  ad_group_ad.status,
  ad_group_ad.policy_summary.approval_status,
  ad_group.name,
  campaign.name
FROM ad_group_ad
WHERE ad_group_ad.status != 'REMOVED'
"""

_CAMPAIGNS_QUERY = """
SELECT campaign.name, campaign.status
FROM campaign
WHERE campaign.status != 'REMOVED'
"""


@dataclass
class GoogleAdsChecker:
    """Thin live wrapper around the official `google-ads` client library.

    Intentionally NOT unit-tested against a real API — that would require a
    live developer token. The rows it produces feed straight into the pure
    `check_ads_and_campaigns()` above, which IS fully tested.
    """

    login_customer_id: str | None = None

    def _client(self):
        try:
            from google.ads.googleads.client import GoogleAdsClient  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised via is_configured() gate
            raise GoogleAdsNotConfigured(
                "google-ads package not installed. Run: pip install google-ads"
            ) from exc

        if not is_configured():
            missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
            raise GoogleAdsNotConfigured(
                f"Missing Google Ads credentials in .env: {', '.join(missing)}"
            )

        config = {
            "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
            "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            "use_proto_plus": True,
        }
        login_customer_id = self.login_customer_id or os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
        if login_customer_id:
            config["login_customer_id"] = login_customer_id
        return GoogleAdsClient.load_from_dict(config)

    def fetch_ad_rows(self, customer_id: str) -> list[dict]:
        client = self._client()
        service = client.get_service("GoogleAdsService")
        rows: list[dict] = []
        response = service.search(customer_id=customer_id, query=_ADS_QUERY)
        for r in response:
            rows.append(
                {
                    "ad_id": r.ad_group_ad.ad.id,
                    "ad_name": r.ad_group_ad.ad.name,
                    "final_urls": list(r.ad_group_ad.ad.final_urls),
                    "status": r.ad_group_ad.status.name,
                    "approval_status": r.ad_group_ad.policy_summary.approval_status.name,
                    "ad_group_name": r.ad_group.name,
                    "campaign_name": r.campaign.name,
                }
            )
        return rows

    def fetch_campaign_rows(self, customer_id: str) -> list[dict]:
        client = self._client()
        service = client.get_service("GoogleAdsService")
        rows: list[dict] = []
        response = service.search(customer_id=customer_id, query=_CAMPAIGNS_QUERY)
        for r in response:
            rows.append(
                {
                    "campaign_name": r.campaign.name,
                    "campaign_status": r.campaign.status.name,
                }
            )
        return rows
