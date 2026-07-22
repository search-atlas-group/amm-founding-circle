"""Tracking-tag presence checks: GA4, GTM, Meta pixel.

Spec: "missing tracking tags (GA4/GTM/pixel presence check on key pages)".
Pure regex-detection functions first (unit-tested against inline HTML
strings — no fixture files, no network), then a thin `check_tracking_page()`
that does the one HTTP GET.
"""

from __future__ import annotations

import re

from .models import ClientConfig, Finding, Severity

# GA4: gtag.js loader OR the inline gtag('config', 'G-XXXXXXXXXX') call.
_GA4_LOADER_RE = re.compile(r"googletagmanager\.com/gtag/js\?id=(G-[A-Z0-9]+)", re.IGNORECASE)
_GA4_CONFIG_RE = re.compile(r"gtag\(\s*['\"]config['\"]\s*,\s*['\"](G-[A-Z0-9]+)['\"]", re.IGNORECASE)

# GTM: container loader script OR the noscript iframe fallback.
_GTM_RE = re.compile(r"googletagmanager\.com/(?:gtm\.js|ns\.html)\?id=(GTM-[A-Z0-9]+)", re.IGNORECASE)

# Meta (Facebook) pixel: connect.facebook.net loader + fbq('init', 'PIXEL_ID').
_META_PIXEL_LOADER_RE = re.compile(r"connect\.facebook\.net", re.IGNORECASE)
_META_PIXEL_ID_RE = re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d+)['\"]", re.IGNORECASE)


def find_ga4_ids(html: str) -> set[str]:
    return set(_GA4_LOADER_RE.findall(html)) | set(_GA4_CONFIG_RE.findall(html))


def find_gtm_ids(html: str) -> set[str]:
    return set(_GTM_RE.findall(html))


def find_meta_pixel_ids(html: str) -> set[str]:
    if not _META_PIXEL_LOADER_RE.search(html):
        return set()
    return set(_META_PIXEL_ID_RE.findall(html))


def check_tracking_html(client: ClientConfig, page_url: str, html: str) -> list[Finding]:
    """Pure: given one page's HTML, return the tracking findings for it.

    Rule: if the client config names an *expected* ID for a tag type, we
    verify that specific ID is present (a generic "some GA4 tag exists" pass
    would hide the classic bug of a dev/staging property leaking to prod).
    If no expected ID is configured, we only report if the tag category is
    entirely absent — that's still useful signal with zero setup.
    """
    findings: list[Finding] = []

    ga4_ids = find_ga4_ids(html)
    if client.ga4_measurement_id:
        if client.ga4_measurement_id not in ga4_ids:
            found_note = f" Found instead: {', '.join(sorted(ga4_ids))}." if ga4_ids else " No GA4 tag found at all."
            findings.append(
                Finding(
                    client=client.name,
                    category="tracking",
                    severity=Severity.DEGRADING,
                    title="Expected GA4 measurement ID not found",
                    detail=f"Expected {client.ga4_measurement_id}.{found_note}",
                    location=page_url,
                    suggested_fix="Confirm the correct GA4 property is installed (check for a wrong/staging ID).",
                )
            )
    elif not ga4_ids:
        findings.append(
            Finding(
                client=client.name,
                category="tracking",
                severity=Severity.DEGRADING,
                title="No GA4 tag detected",
                detail="No gtag.js loader or gtag('config', ...) call found on this page.",
                location=page_url,
                suggested_fix="Install GA4 if this client is meant to be tracked, or set ga4_measurement_id in clients.yaml to silence if intentional.",
            )
        )

    gtm_ids = find_gtm_ids(html)
    if client.gtm_container_id:
        if client.gtm_container_id not in gtm_ids:
            found_note = f" Found instead: {', '.join(sorted(gtm_ids))}." if gtm_ids else " No GTM container found at all."
            findings.append(
                Finding(
                    client=client.name,
                    category="tracking",
                    severity=Severity.DEGRADING,
                    title="Expected GTM container not found",
                    detail=f"Expected {client.gtm_container_id}.{found_note}",
                    location=page_url,
                    suggested_fix="Confirm the correct GTM container is installed.",
                )
            )
    elif not gtm_ids:
        findings.append(
            Finding(
                client=client.name,
                category="tracking",
                severity=Severity.COSMETIC,
                title="No GTM container detected",
                detail="No googletagmanager.com/gtm.js loader found on this page.",
                location=page_url,
                suggested_fix="Optional — only relevant if this client is meant to run tags through GTM.",
            )
        )

    pixel_ids = find_meta_pixel_ids(html)
    if client.meta_pixel_id:
        if client.meta_pixel_id not in pixel_ids:
            found_note = f" Found instead: {', '.join(sorted(pixel_ids))}." if pixel_ids else " No Meta pixel found at all."
            findings.append(
                Finding(
                    client=client.name,
                    category="tracking",
                    severity=Severity.DEGRADING,
                    title="Expected Meta pixel not found",
                    detail=f"Expected pixel {client.meta_pixel_id}.{found_note}",
                    location=page_url,
                    suggested_fix="Confirm the correct Meta pixel is installed (common cause: a client swapped ad accounts and the old pixel was never updated).",
                )
            )
    elif not pixel_ids:
        findings.append(
            Finding(
                client=client.name,
                category="tracking",
                severity=Severity.COSMETIC,
                title="No Meta pixel detected",
                detail="No connect.facebook.net pixel loader found on this page.",
                location=page_url,
                suggested_fix="Optional — only relevant if this client runs Meta ads.",
            )
        )

    return findings


def check_tracking(client: ClientConfig, site_url: str, http_get) -> list[Finding]:
    """I/O wrapper: fetch each configured `tracking_check_paths` page and run
    `check_tracking_html` on it. `http_get` has the same shape as in crawler.py.
    """
    from urllib.parse import urljoin

    findings: list[Finding] = []
    for path in client.tracking_check_paths:
        page_url = urljoin(site_url, path)
        try:
            resp = http_get(page_url)
        except Exception as exc:
            findings.append(
                Finding(
                    client=client.name,
                    category="tracking",
                    severity=Severity.CRITICAL,
                    title="Could not check tracking (page unreachable)",
                    detail=f"Request failed: {exc}",
                    location=page_url,
                    suggested_fix="Fix site reachability first — tracking can't be verified on a page that doesn't load.",
                )
            )
            continue
        if resp.status_code != 200:
            continue  # site-crawl already reports this page's status
        findings.extend(check_tracking_html(client, page_url, getattr(resp, "text", "") or ""))
    return findings
