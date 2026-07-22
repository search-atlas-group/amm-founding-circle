"""Orchestrates one full sweep: crawl every client's sites, check tracking,
check Google Ads if configured, apply known_exceptions, and hand the result
to the report layer. This is the thin I/O seam `run.py` calls into — kept
separate from run.py so a future scheduler/daemon can import it directly.
"""

from __future__ import annotations

from .config import ClientConfig
from .crawler import DEFAULT_USER_AGENT, crawl_site
from .exceptions import apply_known_exceptions
from .google_ads import GoogleAdsChecker, GoogleAdsNotConfigured, check_ads_and_campaigns, is_configured
from .models import Finding, RunResult, Severity
from .tracking import check_tracking


def _make_http_get(timeout: float = 10.0):
    import httpx

    client = httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": DEFAULT_USER_AGENT},
    )

    def _get(url: str):
        return client.get(url)

    return _get


def _final_url_status_of(http_get):
    def _check(url: str) -> int:
        return http_get(url).status_code

    return _check


def run_sweep(clients: list[ClientConfig], max_pages_override: int | None = None) -> RunResult:
    """Run the full sweep and return a RunResult with known_exceptions already
    applied per-client (a client's exception list only ever suppresses that
    client's own findings)."""
    result = RunResult()
    http_get = _make_http_get()

    google_ads_checker: GoogleAdsChecker | None = None
    if is_configured():
        google_ads_checker = GoogleAdsChecker()
    else:
        result.skipped_checks.append(
            "google-ads: not configured (set GOOGLE_ADS_* in .env to enable disapproved-ad and broken-final-URL checks)"
        )

    for client in clients:
        result.clients_swept += 1
        client_findings: list[Finding] = []

        for site in client.sites:
            result.sites_swept += 1
            outcome = crawl_site(client, site, http_get, max_pages=max_pages_override)
            client_findings.extend(outcome.findings)
            result.pages_crawled += outcome.pages_crawled
            client_findings.extend(check_tracking(client, site, http_get))

        if client.google_ads_customer_id:
            if google_ads_checker is not None:
                try:
                    ad_rows = google_ads_checker.fetch_ad_rows(client.google_ads_customer_id)
                    campaign_rows = google_ads_checker.fetch_campaign_rows(client.google_ads_customer_id)
                    result.campaigns_checked += len(campaign_rows)
                    client_findings.extend(
                        check_ads_and_campaigns(client, ad_rows, campaign_rows, _final_url_status_of(http_get))
                    )
                except GoogleAdsNotConfigured as exc:
                    result.skipped_checks.append(f"google-ads ({client.name}): {exc}")
                except Exception as exc:
                    client_findings.append(
                        Finding(
                            client=client.name,
                            category="google-ads",
                            severity=Severity.DEGRADING,
                            title="Google Ads check failed to run",
                            detail=f"{exc}",
                            location=client.google_ads_customer_id,
                            suggested_fix="Check API credentials/quota; the site + tracking checks above still ran normally.",
                        )
                    )
            # else: already noted once in skipped_checks above.

        result.findings.extend(apply_known_exceptions(client_findings, client.known_exceptions))

    return result
