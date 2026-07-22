import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.voice_check import check_voice, estimate_reading_grade
from content_qa.voice_profile import VoiceProfile


class TestBannedPhrases(unittest.TestCase):
    def test_flags_banned_phrase_case_insensitive(self):
        profile = VoiceProfile(banned_phrases=["synergy"])
        result = check_voice("We LEVERAGE Synergy across every team.", profile)
        self.assertEqual(len(result.banned_phrase_hits), 1)
        self.assertFalse(result.passed)

    def test_no_banned_phrases_passes(self):
        profile = VoiceProfile(banned_phrases=["synergy"])
        result = check_voice("We show up on time and fix it right.", profile)
        self.assertEqual(result.banned_phrase_hits, [])
        self.assertTrue(result.passed)

    def test_counts_multiple_occurrences_of_same_phrase(self):
        profile = VoiceProfile(banned_phrases=["circle back"])
        result = check_voice("We'll circle back. Then we'll circle back again.", profile)
        self.assertEqual(len(result.banned_phrase_hits), 2)

    def test_severity_major_at_three_or_more_hits(self):
        profile = VoiceProfile(banned_phrases=["synergy", "leverage", "circle back"])
        result = check_voice("synergy, leverage, and circle back all in one line", profile)
        self.assertEqual(result.severity, "major")

    def test_severity_minor_below_threshold(self):
        profile = VoiceProfile(banned_phrases=["synergy"])
        result = check_voice("just synergy once", profile)
        self.assertEqual(result.severity, "minor")

    def test_severity_none_when_clean(self):
        profile = VoiceProfile(banned_phrases=["synergy"])
        result = check_voice("a perfectly clean sentence", profile)
        self.assertEqual(result.severity, "none")


class TestReadingLevel(unittest.TestCase):
    def test_short_simple_sentences_score_low_grade(self):
        text = "We fix it. We are fast. We are fair."
        grade = estimate_reading_grade(text)
        self.assertLess(grade, 6)

    def test_long_complex_sentence_scores_higher_grade(self):
        simple = estimate_reading_grade("We fix it fast.")
        complex_ = estimate_reading_grade(
            "The comprehensive optimization methodology we implement "
            "substantially enhances organizational operational efficiency "
            "across multidimensional stakeholder engagement frameworks."
        )
        self.assertGreater(complex_, simple)

    def test_empty_text_returns_zero(self):
        self.assertEqual(estimate_reading_grade(""), 0.0)

    def test_flags_reading_level_mismatch_against_profile(self):
        profile = VoiceProfile(reading_level="Grade 3-4")
        complex_text = (
            "The comprehensive optimization methodology we implement "
            "substantially enhances organizational operational efficiency "
            "across multidimensional stakeholder engagement frameworks "
            "for enterprise clientele seeking transformational outcomes."
        )
        result = check_voice(complex_text, profile)
        self.assertTrue(result.reading_level_note)
        self.assertFalse(result.passed)

    def test_no_mismatch_note_when_within_range(self):
        profile = VoiceProfile(reading_level="Grade 6-8")
        text = (
            "Our technicians arrive on schedule and diagnose the problem "
            "quickly. You will always understand the price before we begin "
            "any work."
        )
        result = check_voice(text, profile)
        self.assertEqual(result.reading_level_note, "")

    def test_unparsable_reading_level_is_skipped_not_fatal(self):
        profile = VoiceProfile(reading_level="somewhere between casual and formal")
        result = check_voice("Any old text here.", profile)
        self.assertEqual(result.reading_level_note, "")  # no numeric target -> skip, don't guess


if __name__ == "__main__":
    unittest.main()
