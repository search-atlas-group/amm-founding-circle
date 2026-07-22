from bug_hunter.exceptions import apply_known_exceptions, is_known_exception
from bug_hunter.models import Finding, Severity, make_finding_key


def _finding(**overrides) -> Finding:
    base = dict(
        client="Acme Co",
        category="site-crawl",
        severity=Severity.CRITICAL,
        title="Broken page (404)",
        detail="d",
        location="https://acme.com/dead",
    )
    base.update(overrides)
    return Finding(**base)


def test_make_finding_key_is_deterministic():
    k1 = make_finding_key("Acme Co", "site-crawl", "https://acme.com/x", "Broken page (404)")
    k2 = make_finding_key("Acme Co", "site-crawl", "https://acme.com/x", "Broken page (404)")
    assert k1 == k2


def test_make_finding_key_differs_on_location():
    k1 = make_finding_key("Acme Co", "site-crawl", "https://acme.com/a", "Broken page (404)")
    k2 = make_finding_key("Acme Co", "site-crawl", "https://acme.com/b", "Broken page (404)")
    assert k1 != k2


def test_make_finding_key_slugifies_client_name():
    key = make_finding_key("Acme Co!", "site-crawl", "https://acme.com/x", "Title")
    assert key.startswith("acme-co/site-crawl/")


def test_finding_ignores_severity_and_detail_in_key():
    # Two findings that describe the SAME underlying problem but with a
    # different severity/detail string should still collide on key — this is
    # what makes "paste into known_exceptions" durable across minor wording tweaks.
    f1 = _finding(severity=Severity.CRITICAL, detail="detail A")
    f2 = _finding(severity=Severity.DEGRADING, detail="detail B")
    assert f1.key == f2.key


def test_is_known_exception_exact_match():
    key = make_finding_key("Acme", "tracking", "https://acme.com/", "No GA4 tag detected")
    assert is_known_exception(key, [key])
    assert not is_known_exception(key, ["something/else/entirely"])


def test_is_known_exception_wildcard_prefix():
    key = "acme/tracking/deadbeef01"
    assert is_known_exception(key, ["acme/tracking/*"])
    assert not is_known_exception(key, ["acme/site-crawl/*"])


def test_is_known_exception_ignores_blank_entries():
    key = "acme/tracking/deadbeef01"
    assert not is_known_exception(key, ["", "   "])


def test_apply_known_exceptions_marks_suppressed_without_mutating_input():
    f = _finding()
    findings = [f]
    result = apply_known_exceptions(findings, [f.key])

    assert findings[0].suppressed is False  # original untouched
    assert result[0].suppressed is True
    assert result[0].key == f.key  # same identity, just flagged


def test_apply_known_exceptions_leaves_non_matching_findings_active():
    f = _finding()
    result = apply_known_exceptions([f], ["totally-different-key"])
    assert result[0].suppressed is False
