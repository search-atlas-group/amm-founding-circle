import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.fact_check import Claim, FactResult, Verdict as FactVerdict
from content_qa.grammar import Issue
from content_qa.verdict import ShipVerdict, compute_verdict
from content_qa.voice_check import BannedPhraseHit, VoiceResult


def _fact(verdict, text="some claim"):
    return FactResult(claim=Claim(text=text, claim_type="descriptive"), verdict=verdict)


class TestComputeVerdict(unittest.TestCase):
    def test_clean_draft_ships(self):
        result = compute_verdict([], VoiceResult(passed=True), [])
        self.assertEqual(result.verdict, ShipVerdict.SHIP)

    def test_contradicted_fact_always_holds(self):
        result = compute_verdict([], VoiceResult(passed=True), [_fact(FactVerdict.CONTRADICTED)])
        self.assertEqual(result.verdict, ShipVerdict.HOLD)
        self.assertIn("contradicted", result.reason.lower())

    def test_contradicted_fact_holds_even_with_everything_else_clean(self):
        # The whole point of the tool: one contradicted fact overrides
        # otherwise-perfect grammar and voice.
        result = compute_verdict(
            [], VoiceResult(passed=True), [_fact(FactVerdict.VERIFIED), _fact(FactVerdict.CONTRADICTED)]
        )
        self.assertEqual(result.verdict, ShipVerdict.HOLD)

    def test_major_voice_fail_holds(self):
        voice = VoiceResult(
            passed=False,
            banned_phrase_hits=[BannedPhraseHit("a", "x"), BannedPhraseHit("b", "y"), BannedPhraseHit("c", "z")],
        )
        result = compute_verdict([], voice, [])
        self.assertEqual(result.verdict, ShipVerdict.HOLD)

    def test_major_grammar_issue_holds(self):
        issue = Issue(severity="major", problem="Broken clause", fix="Rewrite", snippet="")
        result = compute_verdict([issue], VoiceResult(passed=True), [])
        self.assertEqual(result.verdict, ShipVerdict.HOLD)

    def test_auto_fixable_grammar_only_is_ship_with_fixes(self):
        issue = Issue(
            severity="minor", problem="Double space", fix="Collapse", snippet="", auto_fixable=True
        )
        result = compute_verdict([issue], VoiceResult(passed=True), [])
        self.assertEqual(result.verdict, ShipVerdict.SHIP_WITH_FIXES)

    def test_minor_voice_drift_is_ship_with_fixes(self):
        voice = VoiceResult(passed=False, banned_phrase_hits=[BannedPhraseHit("synergy", "x")])
        result = compute_verdict([], voice, [])
        self.assertEqual(result.verdict, ShipVerdict.SHIP_WITH_FIXES)

    def test_two_or_more_unverifiable_is_ship_with_fixes(self):
        result = compute_verdict(
            [], VoiceResult(passed=True), [_fact(FactVerdict.UNVERIFIABLE), _fact(FactVerdict.UNVERIFIABLE)]
        )
        self.assertEqual(result.verdict, ShipVerdict.SHIP_WITH_FIXES)

    def test_single_unverifiable_alone_still_ships(self):
        result = compute_verdict([], VoiceResult(passed=True), [_fact(FactVerdict.UNVERIFIABLE)])
        self.assertEqual(result.verdict, ShipVerdict.SHIP)

    def test_verified_facts_alone_still_ship(self):
        result = compute_verdict(
            [], VoiceResult(passed=True), [_fact(FactVerdict.VERIFIED), _fact(FactVerdict.VERIFIED)]
        )
        self.assertEqual(result.verdict, ShipVerdict.SHIP)

    def test_priority_contradicted_beats_major_voice(self):
        voice = VoiceResult(
            passed=False,
            banned_phrase_hits=[BannedPhraseHit("a", "x"), BannedPhraseHit("b", "y"), BannedPhraseHit("c", "z")],
        )
        result = compute_verdict([], voice, [_fact(FactVerdict.CONTRADICTED)])
        self.assertEqual(result.verdict, ShipVerdict.HOLD)
        self.assertIn("contradicted", result.reason.lower())


if __name__ == "__main__":
    unittest.main()
