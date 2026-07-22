import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.fact_check import Claim, FactResult, Verdict as FactVerdict
from content_qa.grammar import Issue
from content_qa.report import build_report_data, render_html_report, render_terminal_summary
from content_qa.verdict import ShipVerdict, VerdictResult
from content_qa.voice_check import BannedPhraseHit, VoiceResult


def _make_report_data(**overrides):
    defaults = dict(
        client_name="Acme",
        draft_source="draft.md",
        grammar_issues=[
            Issue(severity="minor", problem="Double space", fix="Collapse", snippet="a  b", auto_fixable=True)
        ],
        voice_result=VoiceResult(
            passed=False,
            banned_phrase_hits=[BannedPhraseHit(phrase="synergy", snippet="uses synergy here")],
            reading_level_estimate="~grade 7.0",
        ),
        fact_results=[
            FactResult(
                claim=Claim(text="Founded in 1998.", claim_type="date", years=["1998"]),
                verdict=FactVerdict.VERIFIED,
                reason="Matches evidence.",
            )
        ],
        verdict=VerdictResult(ShipVerdict.SHIP_WITH_FIXES, "1 mechanical fix(es) available."),
        degraded_notes=["No --client-url given."],
    )
    defaults.update(overrides)
    return build_report_data(**defaults)


class TestTerminalSummary(unittest.TestCase):
    def test_includes_verdict_line(self):
        summary = render_terminal_summary(_make_report_data())
        self.assertIn("VERDICT: SHIP WITH FIXES", summary)

    def test_includes_grammar_issue(self):
        summary = render_terminal_summary(_make_report_data())
        self.assertIn("Double space", summary)

    def test_includes_banned_phrase(self):
        summary = render_terminal_summary(_make_report_data())
        self.assertIn("synergy", summary)

    def test_includes_fact_claim(self):
        summary = render_terminal_summary(_make_report_data())
        self.assertIn("Founded in 1998", summary)

    def test_includes_degraded_note(self):
        summary = render_terminal_summary(_make_report_data())
        self.assertIn("No --client-url given.", summary)


class TestHtmlReport(unittest.TestCase):
    def test_renders_without_error_and_contains_verdict(self):
        html = render_html_report(_make_report_data())
        self.assertIn("VERDICT: SHIP WITH FIXES", html)
        self.assertIn("Acme", html)

    def test_ship_verdict_uses_ship_class(self):
        data = _make_report_data(verdict=VerdictResult(ShipVerdict.SHIP, "Clean."))
        html = render_html_report(data)
        self.assertIn('class="verdict SHIP"', html)

    def test_hold_verdict_uses_hold_class(self):
        data = _make_report_data(verdict=VerdictResult(ShipVerdict.HOLD, "Contradicted fact."))
        html = render_html_report(data)
        self.assertIn('class="verdict HOLD"', html)

    def test_no_grammar_issues_shows_empty_state(self):
        data = _make_report_data(grammar_issues=[])
        html = render_html_report(data)
        self.assertIn("No mechanical issues found.", html)

    def test_no_facts_shows_empty_state(self):
        data = _make_report_data(fact_results=[])
        html = render_html_report(data)
        self.assertIn("No checkable claims extracted.", html)


if __name__ == "__main__":
    unittest.main()
