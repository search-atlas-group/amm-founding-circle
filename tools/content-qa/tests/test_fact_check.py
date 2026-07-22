import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.fact_check import (
    Claim,
    Verdict,
    check_facts,
    extract_claims,
    strip_html,
    verdict_from_evidence,
)


class TestExtractClaims(unittest.TestCase):
    def test_extracts_sentence_with_a_year(self):
        claims = extract_claims("We've been serving customers since 1998.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].claim_type, "date")
        self.assertIn("1998", claims[0].years)

    def test_extracts_sentence_with_a_number(self):
        claims = extract_claims("We serve over 500 households a month.")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].claim_type, "numeric")

    def test_extracts_sentence_with_trigger_phrase_no_number(self):
        claims = extract_claims("We are the only certified provider in the region.")
        self.assertEqual(len(claims), 1)

    def test_skips_plain_opinion_sentence(self):
        claims = extract_claims("We think customer service really matters a lot.")
        self.assertEqual(claims, [])

    def test_multiple_sentences_only_checkable_ones_extracted(self):
        text = (
            "We love what we do. Founded in 1998, we've grown steadily. "
            "Everyone here is genuinely nice."
        )
        claims = extract_claims(text)
        self.assertEqual(len(claims), 1)
        self.assertIn("1998", claims[0].text)


class TestStripHtml(unittest.TestCase):
    def test_strips_tags(self):
        self.assertEqual(strip_html("<p>Hello <b>world</b></p>"), "Hello world")

    def test_drops_script_and_style_blocks(self):
        html = "<html><style>.a{}</style><body>Text<script>alert(1)</script></body></html>"
        result = strip_html(html)
        self.assertNotIn("alert", result)
        self.assertIn("Text", result)

    def test_unescapes_entities(self):
        self.assertEqual(strip_html("Tom &amp; Jerry"), "Tom & Jerry")

    def test_collapses_whitespace(self):
        self.assertEqual(strip_html("<p>a</p>\n\n<p>b</p>"), "a b")


class TestVerdictFromEvidence(unittest.TestCase):
    def test_no_evidence_is_unverifiable(self):
        claim = Claim(text="Founded in 1998.", claim_type="date", years=["1998"])
        result = verdict_from_evidence(claim, "")
        self.assertEqual(result.verdict, Verdict.UNVERIFIABLE)

    def test_matching_year_in_evidence_is_verified(self):
        claim = Claim(text="Founded in 1998.", claim_type="date", years=["1998"])
        result = verdict_from_evidence(claim, "Acme was founded in 1998 by two brothers.")
        self.assertEqual(result.verdict, Verdict.VERIFIED)

    def test_different_year_same_topic_is_contradicted(self):
        claim = Claim(text="Founded in 1998.", claim_type="date", years=["1998"])
        evidence = "Acme Home Services was founded by the Smith family in 2005."
        result = verdict_from_evidence(claim, evidence)
        self.assertEqual(result.verdict, Verdict.CONTRADICTED)

    def test_unrelated_evidence_is_unverifiable_not_contradicted(self):
        claim = Claim(text="Founded in 1998.", claim_type="date", years=["1998"])
        evidence = "Our team offers weekend appointments and free estimates."
        result = verdict_from_evidence(claim, evidence)
        self.assertEqual(result.verdict, Verdict.UNVERIFIABLE)

    def test_matching_number_in_evidence_is_verified(self):
        claim = Claim(text="We serve over 500 households.", claim_type="numeric", numbers=["500"])
        result = verdict_from_evidence(claim, "We currently serve over 500 households monthly.")
        self.assertEqual(result.verdict, Verdict.VERIFIED)

    def test_descriptive_claim_verified_on_strong_overlap(self):
        claim = Claim(
            text="Our technicians are certified and licensed.",
            claim_type="descriptive",
        )
        evidence = "Every technician on our team is certified and fully licensed by the state."
        result = verdict_from_evidence(claim, evidence)
        self.assertEqual(result.verdict, Verdict.VERIFIED)

    def test_descriptive_claim_unverifiable_on_weak_overlap(self):
        claim = Claim(
            text="Our technicians are certified and licensed.",
            claim_type="descriptive",
        )
        evidence = "We love pizza and long walks on the beach."
        result = verdict_from_evidence(claim, evidence)
        self.assertEqual(result.verdict, Verdict.UNVERIFIABLE)

    def test_absence_alone_never_produces_contradicted_for_descriptive(self):
        # A descriptive claim with zero matching evidence must degrade to
        # unverifiable, never a false "contradicted" — silence isn't a lie.
        claim = Claim(text="We are family owned and operated.", claim_type="descriptive")
        result = verdict_from_evidence(claim, "Completely unrelated evidence text here.")
        self.assertEqual(result.verdict, Verdict.UNVERIFIABLE)


class TestCheckFacts(unittest.TestCase):
    def test_runs_extraction_and_verification_together(self):
        text = "Founded in 1998, we've served this town for decades."
        results = check_facts(text, "Acme was founded in 1998.")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].verdict, Verdict.VERIFIED)

    def test_no_claims_returns_empty_list(self):
        results = check_facts("We really care about our customers.", "some evidence")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
