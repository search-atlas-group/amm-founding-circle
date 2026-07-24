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

    def test_client_name_is_escaped(self):
        data = _make_report_data(client_name="<script>alert(1)</script>")
        html = render_html_report(data)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_draft_source_is_escaped(self):
        data = _make_report_data(draft_source="<img src=x onerror=alert(1)>")
        html = render_html_report(data)
        self.assertNotIn("<img src=x onerror=alert(1)>", html)

    def test_verdict_reason_is_escaped(self):
        data = _make_report_data(
            verdict=VerdictResult(ShipVerdict.HOLD, "<script>alert(2)</script>")
        )
        html = render_html_report(data)
        self.assertNotIn("<script>alert(2)</script>", html)

    def test_grammar_issue_fields_are_escaped(self):
        data = _make_report_data(
            grammar_issues=[
                Issue(
                    severity="minor",
                    problem="<script>alert(3)</script>",
                    fix="<b>fix</b>",
                    snippet="<i>snippet</i>",
                    auto_fixable=True,
                )
            ]
        )
        html = render_html_report(data)
        self.assertNotIn("<script>alert(3)</script>", html)
        self.assertNotIn("<b>fix</b>", html)
        self.assertNotIn("<i>snippet</i>", html)

    def test_fact_claim_and_reason_are_escaped(self):
        data = _make_report_data(
            fact_results=[
                FactResult(
                    claim=Claim(text="<script>alert(4)</script>", claim_type="date", years=[]),
                    verdict=FactVerdict.CONTRADICTED,
                    reason="<script>alert(5)</script>",
                )
            ]
        )
        html = render_html_report(data)
        self.assertNotIn("<script>alert(4)</script>", html)
        self.assertNotIn("<script>alert(5)</script>", html)

    def test_voice_note_and_banned_phrase_are_escaped(self):
        data = _make_report_data(
            voice_result=VoiceResult(
                passed=False,
                banned_phrase_hits=[
                    BannedPhraseHit(phrase="<script>alert(6)</script>", snippet="<script>alert(7)</script>")
                ],
                reading_level_estimate="~grade 7.0",
                reading_level_note="<script>alert(8)</script>",
            )
        )
        html = render_html_report(data)
        self.assertNotIn("<script>alert(6)</script>", html)
        self.assertNotIn("<script>alert(7)</script>", html)
        self.assertNotIn("<script>alert(8)</script>", html)

    def test_degraded_note_is_escaped(self):
        data = _make_report_data(degraded_notes=["<script>alert(9)</script>"])
        html = render_html_report(data)
        self.assertNotIn("<script>alert(9)</script>", html)


if __name__ == "__main__":
    unittest.main()
