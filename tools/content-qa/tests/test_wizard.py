import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.wizard import build_wizard_prompt


class TestBuildWizardPrompt(unittest.TestCase):
    def test_includes_client_name(self):
        prompt = build_wizard_prompt("Acme", ["Sample post text here."])
        self.assertIn("Acme", prompt)

    def test_includes_all_sample_texts(self):
        prompt = build_wizard_prompt("Acme", ["First sample.", "Second sample."])
        self.assertIn("First sample.", prompt)
        self.assertIn("Second sample.", prompt)

    def test_includes_expected_output_shape_headers(self):
        prompt = build_wizard_prompt("Acme", ["Sample."])
        for heading in ["Tone words", "Banned phrases", "Reading level", "Sounds like us"]:
            self.assertIn(heading, prompt)

    def test_raises_on_empty_samples(self):
        with self.assertRaises(ValueError):
            build_wizard_prompt("Acme", [])

    def test_numbers_multiple_samples(self):
        prompt = build_wizard_prompt("Acme", ["a", "b", "c"])
        self.assertIn("SAMPLE 1", prompt)
        self.assertIn("SAMPLE 2", prompt)
        self.assertIn("SAMPLE 3", prompt)


if __name__ == "__main__":
    unittest.main()
