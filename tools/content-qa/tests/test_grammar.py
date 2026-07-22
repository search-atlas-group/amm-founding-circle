import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.grammar import apply_mechanical_fixes, check_mechanics


class TestGrammarHeuristics(unittest.TestCase):
    def test_detects_double_space(self):
        issues = check_mechanics("This  has a double space.")
        problems = [i.problem for i in issues]
        self.assertTrue(any("Double space" in p for p in problems))

    def test_detects_repeated_word(self):
        issues = check_mechanics("We serve the the whole region.")
        self.assertTrue(any("Repeated word" in i.problem for i in issues))

    def test_detects_common_typo(self):
        issues = check_mechanics("We recieved great feedback.")
        self.assertTrue(any("recieved" in i.problem.lower() for i in issues))
        typo_issue = next(i for i in issues if "recieved" in i.problem.lower())
        self.assertIn("receive", typo_issue.fix.lower())

    def test_detects_multiple_exclamation_points(self):
        issues = check_mechanics("Call us today!!!")
        self.assertTrue(any("exclamation" in i.problem.lower() for i in issues))

    def test_detects_trailing_whitespace(self):
        issues = check_mechanics("Line one.   \nLine two.")
        self.assertTrue(any("trailing" in i.problem.lower() for i in issues))

    def test_clean_text_has_no_issues(self):
        issues = check_mechanics("This is a perfectly clean sentence.")
        self.assertEqual(issues, [])

    def test_all_flagged_issues_are_auto_fixable_in_v1(self):
        # v1's offline heuristics only ever raise auto-fixable, minor issues —
        # "major" is reserved for the optional LLM pass. Locking this in so a
        # future heuristic addition has to make a deliberate severity choice.
        issues = check_mechanics("teh  cat cat runs!!!  ")
        self.assertTrue(issues)
        for issue in issues:
            self.assertEqual(issue.severity, "minor")
            self.assertTrue(issue.auto_fixable)


class TestApplyMechanicalFixes(unittest.TestCase):
    def test_fixes_double_space(self):
        text = "This  has  spaces."
        issues = check_mechanics(text)
        fixed = apply_mechanical_fixes(text, issues)
        self.assertNotIn("  ", fixed)

    def test_fixes_repeated_word(self):
        text = "We serve the the region."
        issues = check_mechanics(text)
        fixed = apply_mechanical_fixes(text, issues)
        self.assertEqual(fixed, "We serve the region.")

    def test_fixes_common_typo(self):
        text = "We recieved your message."
        issues = check_mechanics(text)
        fixed = apply_mechanical_fixes(text, issues)
        self.assertIn("received", fixed)
        self.assertNotIn("recieved", fixed)

    def test_fixes_trailing_whitespace(self):
        text = "Line one.   \nLine two.  "
        issues = check_mechanics(text)
        fixed = apply_mechanical_fixes(text, issues)
        for line in fixed.splitlines():
            self.assertEqual(line, line.rstrip())

    def test_never_touches_non_auto_fixable_issues(self):
        # Simulate an LLM-sourced (non-auto-fixable) issue mixed with a real one.
        from content_qa.grammar import Issue

        text = "This  sentence has a subtle grammar problem."
        offline_issues = check_mechanics(text)
        llm_issue = Issue(
            severity="major",
            problem="Subject-verb disagreement",
            fix="Rewrite the clause.",
            snippet="",
            auto_fixable=False,
        )
        fixed = apply_mechanical_fixes(text, offline_issues + [llm_issue])
        self.assertNotIn("  ", fixed)  # the real double-space fix still applied

    def test_idempotent_on_already_fixed_text(self):
        text = "This has clean spacing already."
        issues = check_mechanics(text)
        fixed_once = apply_mechanical_fixes(text, issues)
        fixed_twice = apply_mechanical_fixes(fixed_once, check_mechanics(fixed_once))
        self.assertEqual(fixed_once, fixed_twice)


if __name__ == "__main__":
    unittest.main()
