import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from status_page import render  # noqa: E402


class RenderTests(unittest.TestCase):
    def test_healthy_connection_renders_ok_row(self):
        page = render({"connections": {"A": {"healthy": True, "detail": "HTTP 200", "checked_at": "now"}}})
        self.assertIn("class='ok'", page)
        self.assertIn("Healthy", page)
        self.assertIn("HTTP 200", page)

    def test_down_connection_renders_down_row(self):
        page = render({"connections": {"A": {"healthy": False, "detail": "HTTP 401", "checked_at": "now"}}})
        self.assertIn("class='down'", page)
        self.assertIn("Down", page)

    def test_empty_state_renders_placeholder(self):
        page = render({"connections": {}})
        self.assertIn("No connections configured yet.", page)

    def test_none_state_does_not_crash(self):
        page = render({})
        self.assertIn("No connections configured yet.", page)

    def test_html_escapes_connection_name(self):
        page = render({"connections": {"<script>alert(1)</script>": {"healthy": True}}})
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_rows_are_sorted_by_name(self):
        page = render({
            "connections": {
                "Zeta": {"healthy": True},
                "Alpha": {"healthy": True},
            }
        })
        self.assertLess(page.index("Alpha"), page.index("Zeta"))


if __name__ == "__main__":
    unittest.main()
