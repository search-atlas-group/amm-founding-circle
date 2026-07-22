import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.voice_profile import (
    VoiceProfile,
    parse_voice_profile,
    render_voice_profile,
    load_voice_profile,
)

SAMPLE = """# Voice Profile: Acme Home Services

## Tone words
direct, no-nonsense, friendly

## Banned phrases
- "synergy"
- "leverage our solutions"

## Reading level
Grade 6-8 (plain language)

## Formatting rules
- Use the Oxford comma
- No em-dashes in headlines

## Sounds like us
- "We show up on time and fix it right."

## Doesn't sound like us
- "We leverage synergistic solutions."
"""


class TestVoiceProfileParsing(unittest.TestCase):
    def test_parses_client_name_from_h1(self):
        profile = parse_voice_profile(SAMPLE)
        self.assertEqual(profile.client_name, "Acme Home Services")

    def test_parses_tone_words_comma_line(self):
        profile = parse_voice_profile(SAMPLE)
        self.assertEqual(profile.tone_words, ["direct", "no-nonsense", "friendly"])

    def test_parses_banned_phrases_bullets_and_strips_quotes(self):
        profile = parse_voice_profile(SAMPLE)
        self.assertEqual(profile.banned_phrases, ["synergy", "leverage our solutions"])

    def test_parses_reading_level_as_free_text(self):
        profile = parse_voice_profile(SAMPLE)
        self.assertEqual(profile.reading_level, "Grade 6-8 (plain language)")

    def test_parses_formatting_rules(self):
        profile = parse_voice_profile(SAMPLE)
        self.assertEqual(
            profile.formatting_rules,
            ["Use the Oxford comma", "No em-dashes in headlines"],
        )

    def test_parses_sounds_like_and_doesnt_sound_like(self):
        profile = parse_voice_profile(SAMPLE)
        self.assertEqual(profile.sounds_like_us, ["We show up on time and fix it right."])
        self.assertEqual(profile.doesnt_sound_like_us, ["We leverage synergistic solutions."])

    def test_empty_profile_is_empty(self):
        self.assertTrue(VoiceProfile().is_empty())

    def test_parsed_profile_is_not_empty(self):
        self.assertFalse(parse_voice_profile(SAMPLE).is_empty())

    def test_unknown_sections_are_ignored_not_fatal(self):
        text = SAMPLE + "\n## Some Future Section\n- unhandled item\n"
        profile = parse_voice_profile(text)
        self.assertEqual(profile.client_name, "Acme Home Services")  # still parses fine

    def test_missing_sections_stay_empty_not_raise(self):
        profile = parse_voice_profile("# Voice Profile: Bare Client\n")
        self.assertEqual(profile.client_name, "Bare Client")
        self.assertEqual(profile.banned_phrases, [])
        self.assertTrue(profile.is_empty())

    def test_load_voice_profile_missing_file_raises_helpful_error(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load_voice_profile("/tmp/definitely-not-a-real-profile-xyz.md")
        self.assertIn("wizard", str(ctx.exception).lower())


class TestVoiceProfileRoundTrip(unittest.TestCase):
    def test_render_then_reparse_preserves_core_fields(self):
        original = parse_voice_profile(SAMPLE)
        rendered = render_voice_profile(original)
        reparsed = parse_voice_profile(rendered)
        self.assertEqual(reparsed.client_name, original.client_name)
        self.assertEqual(reparsed.tone_words, original.tone_words)
        self.assertEqual(reparsed.banned_phrases, original.banned_phrases)
        self.assertEqual(reparsed.reading_level, original.reading_level)


if __name__ == "__main__":
    unittest.main()
