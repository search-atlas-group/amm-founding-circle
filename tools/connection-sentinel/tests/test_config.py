import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import ConfigError, load_connections  # noqa: E402


class LoadConnectionsTests(unittest.TestCase):
    def _write(self, text):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        f.write(textwrap.dedent(text))
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_loads_minimal_valid_config(self):
        path = self._write("""
            connections:
              - name: "Test API"
                type: http
                url: "https://example.invalid/health"
        """)
        cfg = load_connections(path, env={})
        self.assertEqual(len(cfg.connections), 1)
        self.assertEqual(cfg.connections[0].name, "Test API")
        self.assertEqual(cfg.connections[0].timeout, 8)

    def test_env_var_interpolation_in_headers(self):
        path = self._write("""
            connections:
              - name: "SA MCP"
                type: http
                url: "https://example.invalid"
                headers:
                  Authorization: "Bearer ${MY_TOKEN}"
        """)
        cfg = load_connections(path, env={"MY_TOKEN": "abc123"})
        self.assertEqual(cfg.connections[0].headers["Authorization"], "Bearer abc123")

    def test_env_var_interpolation_in_url(self):
        path = self._write("""
            connections:
              - name: "Ads"
                type: http
                url: "https://x.invalid/customers/${CUSTOMER_ID}"
        """)
        cfg = load_connections(path, env={"CUSTOMER_ID": "999"})
        self.assertIn("999", cfg.connections[0].url)

    def test_missing_env_var_raises_clear_error(self):
        path = self._write("""
            connections:
              - name: "SA MCP"
                type: http
                url: "https://x.invalid"
                headers:
                  Authorization: "Bearer ${MISSING_VAR}"
        """)
        with self.assertRaises(ConfigError) as ctx:
            load_connections(path, env={})
        self.assertIn("MISSING_VAR", str(ctx.exception))

    def test_no_connections_raises(self):
        path = self._write("connections: []\n")
        with self.assertRaises(ConfigError):
            load_connections(path, env={})

    def test_duplicate_names_rejected(self):
        path = self._write("""
            connections:
              - name: "Dup"
                type: http
                url: "https://a.invalid"
              - name: "Dup"
                type: http
                url: "https://b.invalid"
        """)
        with self.assertRaises(ConfigError):
            load_connections(path, env={})

    def test_unknown_type_rejected(self):
        path = self._write("""
            connections:
              - name: "Weird"
                type: telepathy
        """)
        with self.assertRaises(ConfigError):
            load_connections(path, env={})

    def test_missing_required_field_rejected(self):
        path = self._write("""
            connections:
              - name: "No URL"
                type: http
        """)
        with self.assertRaises(ConfigError):
            load_connections(path, env={})

    def test_command_type_requires_command_field(self):
        path = self._write("""
            connections:
              - name: "No command"
                type: command
        """)
        with self.assertRaises(ConfigError):
            load_connections(path, env={})

    def test_notify_defaults(self):
        path = self._write("""
            connections:
              - name: "A"
                type: command
                command: "true"
        """)
        cfg = load_connections(path, env={})
        self.assertFalse(cfg.notify.email_enabled)
        self.assertTrue(cfg.notify.macos_enabled)
        self.assertFalse(cfg.notify.daily_heartbeat)

    def test_notify_block_is_honored(self):
        path = self._write("""
            notify:
              email:
                enabled: true
                to: "me@example.com"
              macos:
                enabled: false
              daily_heartbeat: true
            connections:
              - name: "A"
                type: command
                command: "true"
        """)
        cfg = load_connections(path, env={})
        self.assertTrue(cfg.notify.email_enabled)
        self.assertEqual(cfg.notify.email_to, "me@example.com")
        self.assertFalse(cfg.notify.macos_enabled)
        self.assertTrue(cfg.notify.daily_heartbeat)


if __name__ == "__main__":
    unittest.main()
