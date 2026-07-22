from bug_hunter.models import ClientConfig
from bug_hunter.tracking import (
    check_tracking_html,
    find_ga4_ids,
    find_gtm_ids,
    find_meta_pixel_ids,
)

GA4_LOADER_HTML = "<script src='https://www.googletagmanager.com/gtag/js?id=G-ABC1234567'></script>"
GA4_CONFIG_HTML = "<script>gtag('config', 'G-ABC1234567');</script>"
GTM_HTML = "<script src='https://www.googletagmanager.com/gtm.js?id=GTM-XYZ9999'></script>"
META_PIXEL_HTML = """
<script src="https://connect.facebook.net/en_US/fbevents.js"></script>
<script>fbq('init', '1234567890'); fbq('track', 'PageView');</script>
"""


def test_find_ga4_ids_from_loader():
    assert find_ga4_ids(GA4_LOADER_HTML) == {"G-ABC1234567"}


def test_find_ga4_ids_from_config_call():
    assert find_ga4_ids(GA4_CONFIG_HTML) == {"G-ABC1234567"}


def test_find_ga4_ids_absent():
    assert find_ga4_ids("<html><body>nothing here</body></html>") == set()


def test_find_gtm_ids():
    assert find_gtm_ids(GTM_HTML) == {"GTM-XYZ9999"}


def test_find_meta_pixel_ids_requires_loader_present():
    # fbq('init', ...) alone without the connect.facebook.net loader shouldn't
    # count — that pattern shows up in copy-pasted docs/snippets, not real installs.
    assert find_meta_pixel_ids("fbq('init', '999');") == set()


def test_find_meta_pixel_ids_with_loader():
    assert find_meta_pixel_ids(META_PIXEL_HTML) == {"1234567890"}


def _client(**overrides) -> ClientConfig:
    base = dict(name="Acme", sites=["https://acme.com"])
    base.update(overrides)
    return ClientConfig(**base)


def test_check_tracking_html_no_expectation_flags_absence():
    client = _client()
    findings = check_tracking_html(client, "https://acme.com/", "<html></html>")
    titles = [f.title for f in findings]
    assert "No GA4 tag detected" in titles


def test_check_tracking_html_no_expectation_passes_when_present():
    client = _client()
    findings = check_tracking_html(client, "https://acme.com/", GA4_LOADER_HTML + GTM_HTML + META_PIXEL_HTML)
    ga4_findings = [f for f in findings if "GA4" in f.title]
    assert ga4_findings == []


def test_check_tracking_html_expected_id_mismatch_flags_degrading():
    client = _client(ga4_measurement_id="G-EXPECTED99")
    findings = check_tracking_html(client, "https://acme.com/", GA4_CONFIG_HTML)  # has G-ABC1234567 instead
    ga4_findings = [f for f in findings if "GA4" in f.title]
    assert len(ga4_findings) == 1
    assert "Found instead" in ga4_findings[0].detail
    assert ga4_findings[0].severity.value == "degrading"


def test_check_tracking_html_expected_id_match_passes():
    client = _client(ga4_measurement_id="G-ABC1234567")
    findings = check_tracking_html(client, "https://acme.com/", GA4_CONFIG_HTML)
    ga4_findings = [f for f in findings if "GA4" in f.title]
    assert ga4_findings == []


def test_check_tracking_html_expected_gtm_missing_entirely():
    client = _client(gtm_container_id="GTM-EXPECTED")
    findings = check_tracking_html(client, "https://acme.com/", "<html></html>")
    gtm_findings = [f for f in findings if "GTM" in f.title]
    assert len(gtm_findings) == 1
    assert "No GTM container found at all" in gtm_findings[0].detail


def test_check_tracking_html_expected_meta_pixel_mismatch():
    client = _client(meta_pixel_id="0000000000")
    findings = check_tracking_html(client, "https://acme.com/", META_PIXEL_HTML)  # has 1234567890
    pixel_findings = [f for f in findings if "pixel" in f.title.lower()]
    assert len(pixel_findings) == 1
