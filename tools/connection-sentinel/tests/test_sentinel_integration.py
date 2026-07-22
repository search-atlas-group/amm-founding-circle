import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sentinel import check_once  # noqa: E402


class CheckOnceIntegrationTests(unittest.TestCase):
    """End-to-end: config -> probe -> state -> status page, using only the
    `command` probe type so no network call or real credential is needed."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.dir, "connections.yaml")
        self.state_path = os.path.join(self.dir, "state.json")
        self.status_path = os.path.join(self.dir, "status.html")

    def _write_config(self, command):
        with open(self.config_path, "w") as f:
            f.write(textwrap.dedent(f"""
                notify:
                  macos:
                    enabled: false
                connections:
                  - name: "Local Check"
                    type: command
                    command: "{command}"
            """))

    def test_full_sweep_writes_status_page_and_returns_health(self):
        self._write_config("true")
        healthy = check_once(self.config_path, self.state_path, self.status_path)
        self.assertTrue(healthy)
        self.assertTrue(os.path.exists(self.status_path))
        with open(self.status_path) as f:
            page = f.read()
        self.assertIn("Local Check", page)
        self.assertIn("Healthy", page)

    def test_first_sweep_never_alerts_only_second_does_on_a_drop(self):
        self._write_config("true")
        check_once(self.config_path, self.state_path, self.status_path)  # baseline, silent

        self._write_config("false")
        healthy = check_once(self.config_path, self.state_path, self.status_path)
        self.assertFalse(healthy)
        with open(self.status_path) as f:
            page = f.read()
        self.assertIn("Down", page)

    def test_state_file_is_created_and_reused(self):
        self._write_config("true")
        self.assertFalse(os.path.exists(self.state_path))
        check_once(self.config_path, self.state_path, self.status_path)
        self.assertTrue(os.path.exists(self.state_path))


if __name__ == "__main__":
    unittest.main()
