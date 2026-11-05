"""Offline fixture CLI checks; these do not exercise voice or authentication."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).with_name("pilot_tool.py")


class PilotToolTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    def test_alpha_lookup_labels_synthetic_source(self):
        result = self.invoke("--session", "pilot-alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source_mode"], "SYNTHETIC_FIXTURE_NOT_LIVE")
        self.assertEqual(payload["session"]["session_id"], "pilot-alpha")
        self.assertEqual(payload["session"]["status"], "active")

    def test_unknown_function_is_denied(self):
        result = self.invoke("--session", "pilot-alpha", "--function", "run_command")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "DENIED_FUNCTION")

    def test_cross_session_is_denied(self):
        result = self.invoke("--session", "pilot-beta")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "DENIED_SESSION")
        self.assertNotIn("paused", result.stdout)

    def test_beta_with_explicit_test_context(self):
        result = self.invoke(
            "--session", "pilot-beta", "--authorized-session", "pilot-beta"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["session"]["status"], "paused")

    def test_missing_authorized_record_is_not_found(self):
        result = self.invoke(
            "--session", "pilot-missing", "--authorized-session", "pilot-missing"
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "NOT_FOUND")

    def test_extra_arguments_are_denied(self):
        result = self.invoke(
            "--arguments-json", '{"session_id":"pilot-alpha","command":"restart"}'
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "INVALID_ARGUMENTS")

    def test_invalid_argument_shapes_are_denied(self):
        for text in (
            "null",
            "[]",
            "{}",
            '{"session_id":true}',
            '{"session_id":{}}',
            "not json",
        ):
            with self.subTest(text=text):
                result = self.invoke("--arguments-json", text)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    json.loads(result.stdout)["error"], "INVALID_ARGUMENTS"
                )

    def test_shell_and_path_input_are_never_executed(self):
        for value in ("$(whoami)", "../pilot-alpha", "x" * 65):
            with self.subTest(value=value):
                result = self.invoke("--session", value)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    json.loads(result.stdout)["error"], "INVALID_ARGUMENTS"
                )

    def test_no_argument_is_usage_error(self):
        self.assertEqual(self.invoke().returncode, 2)


if __name__ == "__main__":
    unittest.main()
