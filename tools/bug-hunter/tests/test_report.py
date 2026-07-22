from bug_hunter.models import Finding, RunResult, Severity
from bug_hunter.report import active_findings, build_run_summary_line, render_html, render_terminal, suppressed_findings


def _result_with(critical=0, degrading=0, cosmetic=0, suppressed=0, **counts) -> RunResult:
    result = RunResult(clients_swept=2, sites_swept=3, campaigns_checked=5)
    i = 0
    for _ in range(critical):
        i += 1
        result.findings.append(
            Finding(client="Acme", category="site-crawl", severity=Severity.CRITICAL, title=f"c{i}", detail="d", location=f"loc{i}")
        )
    for _ in range(degrading):
        i += 1
        result.findings.append(
            Finding(client="Acme", category="tracking", severity=Severity.DEGRADING, title=f"d{i}", detail="d", location=f"loc{i}")
        )
    for _ in range(cosmetic):
        i += 1
        result.findings.append(
            Finding(client="Acme", category="tracking", severity=Severity.COSMETIC, title=f"o{i}", detail="d", location=f"loc{i}")
        )
    for _ in range(suppressed):
        i += 1
        f = Finding(client="Acme", category="site-crawl", severity=Severity.CRITICAL, title=f"s{i}", detail="d", location=f"loc{i}")
        f.suppressed = True
        result.findings.append(f)
    return result


def test_build_run_summary_line_clean_sweep():
    result = _result_with()
    line = build_run_summary_line(result)
    assert "nothing found" in line
    assert "Clean sweep" in line


def test_build_run_summary_line_matches_spec_shape():
    result = _result_with(critical=2, degrading=3, cosmetic=2)
    line = build_run_summary_line(result)
    assert "Swept 3 site(s)" in line
    assert "5 campaign(s)" in line
    assert "2 critical issue(s) found and flagged" in line
    assert "5 minor" in line  # degrading + cosmetic


def test_active_findings_excludes_suppressed():
    result = _result_with(critical=1, suppressed=2)
    active = active_findings(result)
    supp = suppressed_findings(result)
    assert len(active) == 1
    assert len(supp) == 2
    assert all(not f.suppressed for f in active)
    assert all(f.suppressed for f in supp)


def test_active_findings_sorted_worst_first():
    result = _result_with(critical=1, degrading=1, cosmetic=1)
    active = active_findings(result)
    ranks = [f.severity.rank for f in active]
    assert ranks == sorted(ranks, reverse=True)


def test_render_terminal_includes_summary_and_key_hint():
    result = _result_with(critical=1)
    output = render_terminal(result)
    assert "BUG HUNTER" in output
    assert "critical issue(s)" in output
    assert "known_exceptions" in output  # the "paste this key" hint


def test_render_terminal_notes_skipped_checks():
    result = _result_with()
    result.skipped_checks.append("google-ads: not configured")
    output = render_terminal(result)
    assert "Skipped checks" in output
    assert "google-ads: not configured" in output


def test_render_html_escapes_content_and_includes_summary():
    result = _result_with(critical=1)
    result.findings[0].detail = "<script>alert(1)</script>"
    html = render_html(result)
    assert "<script>alert(1)</script>" not in html  # must be escaped
    assert "&lt;script&gt;" in html
    assert "Bug Hunter" in html


def test_render_html_clean_sweep_shows_callout():
    html = render_html(_result_with())
    assert "Clean sweep" in html


def test_render_html_valid_document_shape():
    html = render_html(_result_with(critical=1, degrading=1))
    assert html.strip().startswith("<!doctype html>")
    assert html.strip().endswith("</html>")
