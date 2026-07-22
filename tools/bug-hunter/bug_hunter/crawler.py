"""Site crawl: broken links/images, 404s, and long redirect chains.

Split like every other module here: pure parsing/classification functions at
the top (fully unit-tested, no network), then a thin `crawl_site()` that does
the actual HTTP work and is exercised only via the manual smoke test in the
README (mocking a full crawl end-to-end isn't worth the complexity budget for
v1 — the value is in getting the classification rules right).
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .models import ClientConfig, Finding, Severity

DEFAULT_USER_AGENT = "AMM-BugHunter/1.0 (+read-only site sweep; https://github.com/search-atlas-group/amm-founding-circle)"
REDIRECT_CHAIN_WARN_AT = 2  # a chain of MORE than this many hops is flagged


class _LinkImgParser(HTMLParser):
    """Minimal stdlib HTML parser — no bs4 dependency required."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.images: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "a" and attr_map.get("href"):
            self.links.append(attr_map["href"])
        elif tag == "img" and attr_map.get("src"):
            self.images.append(attr_map["src"])


def extract_links_and_images(html: str, base_url: str) -> tuple[set[str], set[str]]:
    """Return (absolute link URLs, absolute image URLs) found in `html`.

    Fragment-only links (#anchor), mailto:, tel:, and javascript: hrefs are
    dropped — they are never a "broken page" finding.
    """
    parser = _LinkImgParser()
    try:
        parser.feed(html)
    except Exception:
        # Malformed HTML shouldn't crash a whole sweep — report what we got.
        pass

    def _resolve(raw: set[str] | list[str]) -> set[str]:
        out: set[str] = set()
        for href in raw:
            href = href.strip()
            if not href or href.startswith("#"):
                continue
            scheme = urlparse(href).scheme
            if scheme in ("mailto", "tel", "javascript", "data"):
                continue
            out.add(urljoin(base_url, href))
        return out

    return _resolve(parser.links), _resolve(parser.images)


def is_same_domain(url: str, root_netloc: str) -> bool:
    """Same-domain check, treating www./non-www as equivalent."""
    netloc = urlparse(url).netloc.lower()
    root = root_netloc.lower()
    return netloc == root or netloc.removeprefix("www.") == root.removeprefix("www.")


def classify_page_status(
    client: str, url: str, status_code: int, referrer: str | None = None
) -> Finding | None:
    """Turn one crawled page's HTTP status into a Finding, or None if fine."""
    location = url if referrer is None else f"{url} (linked from {referrer})"
    if status_code == 404:
        return Finding(
            client=client,
            category="site-crawl",
            severity=Severity.CRITICAL,
            title="Broken page (404)",
            detail="Page returned 404 Not Found.",
            location=location,
            suggested_fix="Fix or remove the link pointing here, or restore/redirect the page.",
        )
    if 500 <= status_code < 600:
        return Finding(
            client=client,
            category="site-crawl",
            severity=Severity.CRITICAL,
            title=f"Server error ({status_code})",
            detail=f"Page returned a {status_code} server error.",
            location=location,
            suggested_fix="Check server/application logs for this path; likely a hosting or plugin issue.",
        )
    if status_code in (401, 403):
        return Finding(
            client=client,
            category="site-crawl",
            severity=Severity.DEGRADING,
            title=f"Page blocked ({status_code})",
            detail=f"Page returned {status_code} — may be intentional (staging/private area) or a misconfiguration.",
            location=location,
            suggested_fix="Confirm this page is meant to be restricted; if not, check auth/firewall rules.",
        )
    return None


def classify_image_status(client: str, image_url: str, status_code: int, page_url: str) -> Finding | None:
    if status_code == 404 or 500 <= status_code < 600:
        return Finding(
            client=client,
            category="site-crawl",
            severity=Severity.DEGRADING,
            title="Broken image",
            detail=f"Image returned {status_code} on page {page_url}.",
            location=image_url,
            suggested_fix="Re-upload the image or fix the src path.",
        )
    return None


def classify_redirect_chain(client: str, original_url: str, chain: list[str]) -> Finding | None:
    """`chain` = the full sequence of URLs visited, original first, final last.

    A chain of length 1 is "no redirect" — nothing to report.
    """
    hops = max(0, len(chain) - 1)
    if hops > REDIRECT_CHAIN_WARN_AT:
        return Finding(
            client=client,
            category="site-crawl",
            severity=Severity.DEGRADING,
            title=f"Long redirect chain ({hops} hops)",
            detail=" → ".join(chain),
            location=original_url,
            suggested_fix="Collapse to a single redirect straight to the final URL — each hop costs load time and SEO signal.",
        )
    return None


@dataclass
class CrawlOutcome:
    findings: list[Finding]
    pages_crawled: int


def crawl_site(
    client: ClientConfig,
    site_url: str,
    http_get,
    max_pages: int | None = None,
    delay_seconds: float = 0.3,
) -> CrawlOutcome:
    """Breadth-first same-domain crawl starting at `site_url`.

    `http_get(url)` must return an object with `.status_code`, `.text`,
    `.headers` (dict-like), and `.history` (list of prior-hop URL strings,
    empty if no redirect) — this is exactly httpx.Response's shape, so
    production code passes `httpx.Client(...).get` directly and tests pass a
    tiny fake.
    """
    import time

    findings: list[Finding] = []
    root_netloc = urlparse(site_url).netloc
    cap = max_pages if max_pages is not None else client.max_pages_per_site

    queue: list[tuple[str, str | None]] = [(site_url, None)]
    visited: set[str] = set()
    checked_images: set[str] = set()
    pages_crawled = 0

    while queue and pages_crawled < cap:
        url, referrer = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = http_get(url)
        except Exception as exc:  # network error itself is a finding
            findings.append(
                Finding(
                    client=client.name,
                    category="site-crawl",
                    severity=Severity.CRITICAL,
                    title="Page unreachable",
                    detail=f"Request failed: {exc}",
                    location=url if referrer is None else f"{url} (linked from {referrer})",
                    suggested_fix="Confirm the site is up and DNS resolves; re-run once confirmed reachable.",
                )
            )
            continue

        pages_crawled += 1
        history = list(getattr(resp, "history", []) or [])
        if history:
            chain_finding = classify_redirect_chain(client.name, url, [*history, url])
            if chain_finding:
                findings.append(chain_finding)

        status_finding = classify_page_status(client.name, url, resp.status_code, referrer)
        if status_finding:
            findings.append(status_finding)
            time.sleep(delay_seconds)
            continue  # don't parse links out of a broken page

        content_type = ""
        try:
            content_type = (resp.headers.get("content-type") or "").lower()
        except AttributeError:
            pass
        if content_type and "html" not in content_type:
            time.sleep(delay_seconds)
            continue

        links, images = extract_links_and_images(getattr(resp, "text", "") or "", url)

        for img_url in images:
            if img_url in checked_images:
                continue
            checked_images.add(img_url)
            try:
                img_resp = http_get(img_url)
            except Exception:
                continue
            img_finding = classify_image_status(client.name, img_url, img_resp.status_code, url)
            if img_finding:
                findings.append(img_finding)

        for link in links:
            if is_same_domain(link, root_netloc) and link not in visited:
                queue.append((link, url))
            elif not is_same_domain(link, root_netloc):
                # External link — checked but only flagged as degrading, and
                # only once (not crawled further).
                if link in visited:
                    continue
                visited.add(link)
                try:
                    ext_resp = http_get(link)
                except Exception:
                    continue
                if ext_resp.status_code == 404 or 500 <= ext_resp.status_code < 600:
                    findings.append(
                        Finding(
                            client=client.name,
                            category="site-crawl",
                            severity=Severity.DEGRADING,
                            title="Broken external link",
                            detail=f"Outbound link returned {ext_resp.status_code}.",
                            location=f"{link} (linked from {url})",
                            suggested_fix="Update or remove the outbound link.",
                        )
                    )

        time.sleep(delay_seconds)

    return CrawlOutcome(findings=findings, pages_crawled=pages_crawled)
