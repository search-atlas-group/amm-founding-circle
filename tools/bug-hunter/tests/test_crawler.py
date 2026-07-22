from bug_hunter.crawler import (
    classify_image_status,
    classify_page_status,
    classify_redirect_chain,
    extract_links_and_images,
    is_same_domain,
)
from bug_hunter.models import Severity


def test_extract_links_and_images_resolves_relative_urls():
    html = """
    <html><body>
      <a href="/about">About</a>
      <a href="https://external.com/page">External</a>
      <a href="#top">Anchor only</a>
      <a href="mailto:hi@acme.com">Email</a>
      <img src="/logo.png">
      <img src="https://cdn.acme.com/hero.jpg">
    </body></html>
    """
    links, images = extract_links_and_images(html, "https://acme.com/")

    assert "https://acme.com/about" in links
    assert "https://external.com/page" in links
    assert not any("top" in link for link in links)  # anchor dropped
    assert not any(link.startswith("mailto:") for link in links)
    assert "https://acme.com/logo.png" in images
    assert "https://cdn.acme.com/hero.jpg" in images


def test_extract_links_and_images_survives_malformed_html():
    # Deliberately broken markup shouldn't crash the parser.
    html = "<html><body><a href='/ok'>ok<img src='/x.png'"
    links, images = extract_links_and_images(html, "https://acme.com/")
    assert "https://acme.com/ok" in links


def test_is_same_domain_treats_www_as_equivalent():
    assert is_same_domain("https://www.acme.com/page", "acme.com")
    assert is_same_domain("https://acme.com/page", "www.acme.com")
    assert not is_same_domain("https://other.com/page", "acme.com")


def test_classify_page_status_404_is_critical():
    f = classify_page_status("Acme", "https://acme.com/dead", 404)
    assert f is not None
    assert f.severity == Severity.CRITICAL
    assert "404" in f.title


def test_classify_page_status_500_is_critical():
    f = classify_page_status("Acme", "https://acme.com/oops", 502)
    assert f is not None
    assert f.severity == Severity.CRITICAL


def test_classify_page_status_401_is_degrading_not_critical():
    f = classify_page_status("Acme", "https://acme.com/staging", 401)
    assert f is not None
    assert f.severity == Severity.DEGRADING


def test_classify_page_status_200_is_none():
    assert classify_page_status("Acme", "https://acme.com/", 200) is None


def test_classify_page_status_includes_referrer_in_location():
    f = classify_page_status("Acme", "https://acme.com/dead", 404, referrer="https://acme.com/")
    assert "linked from https://acme.com/" in f.location


def test_classify_image_status_only_flags_broken_images():
    assert classify_image_status("Acme", "https://acme.com/x.png", 200, "https://acme.com/") is None
    f = classify_image_status("Acme", "https://acme.com/x.png", 404, "https://acme.com/")
    assert f is not None
    assert f.severity == Severity.DEGRADING


def test_classify_redirect_chain_short_chain_is_fine():
    assert classify_redirect_chain("Acme", "https://acme.com/a", ["https://acme.com/a", "https://acme.com/b"]) is None


def test_classify_redirect_chain_long_chain_flags():
    chain = [
        "https://acme.com/a",
        "https://acme.com/b",
        "https://acme.com/c",
        "https://acme.com/d",
    ]
    f = classify_redirect_chain("Acme", chain[0], chain)
    assert f is not None
    assert f.severity == Severity.DEGRADING
    assert "3 hops" in f.title
