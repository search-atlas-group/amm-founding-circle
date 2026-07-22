"""Fast, no-subprocess tests for the dashboard's own logic: the tab config
table, artifact resolution (fixed path + newest-of-glob), and shell
rendering. Deliberately does NOT spawn any of the six tools' real
subprocesses -- that's proven live in README's manual verification steps
(also exercised end-to-end when this tool shipped, see CHANGELOG), not in
a fast unit-test run.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard.shell import render_shell  # noqa: E402
from dashboard.tools_config import TOOL_TABS, ToolTab, read_artifact  # noqa: E402


class ToolTabsTests(unittest.TestCase):
    def test_all_six_tools_present(self):
        slugs = {t.slug for t in TOOL_TABS}
        self.assertEqual(
            slugs,
            {
                "connection-sentinel",
                "bug-hunter",
                "content-qa",
                "lead-grader",
                "penny-dashboard",
                "outbound-engine",
            },
        )

    def test_every_tab_has_at_least_one_run_step(self):
        for tab in TOOL_TABS:
            self.assertTrue(tab.run_steps, f"{tab.slug} has no run_steps")
            for step in tab.run_steps:
                self.assertEqual(step[0], "python3")

    def test_penny_dashboard_has_owner_and_client_safe_sub_tabs(self):
        penny = next(t for t in TOOL_TABS if t.slug == "penny-dashboard")
        labels = [label for label, _ in penny.sub_tabs]
        self.assertEqual(labels, ["Owner view (internal)", "Client-safe view"])

    def test_tool_dirs_exist_on_disk(self):
        for tab in TOOL_TABS:
            self.assertTrue(tab.tool_dir.is_dir(), f"{tab.tool_dir} missing")


class ReadArtifactTests(unittest.TestCase):
    def test_fixed_path_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp)
            (tool_dir / "status.html").write_text("<html>fixed</html>")
            tab = ToolTab(
                slug="x", label="X", tool_dir=tool_dir,
                run_steps=[["python3", "-c", "pass"]], artifact="status.html",
            )
            found = read_artifact(tab)
            self.assertIsNotNone(found)
            html, rel_path = found
            self.assertEqual(html, "<html>fixed</html>")
            self.assertEqual(rel_path, "status.html")

    def test_fixed_path_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tab = ToolTab(
                slug="x", label="X", tool_dir=Path(tmp),
                run_steps=[["python3", "-c", "pass"]], artifact="nope.html",
            )
            self.assertIsNone(read_artifact(tab))

    def test_glob_picks_newest_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp)
            reports = tool_dir / "reports"
            reports.mkdir()
            older = reports / "report-1.html"
            newer = reports / "report-2.html"
            older.write_text("older")
            time.sleep(0.01)
            newer.write_text("newer")
            tab = ToolTab(
                slug="x", label="X", tool_dir=tool_dir,
                run_steps=[["python3", "-c", "pass"]], artifact="reports/report-*.html",
            )
            found = read_artifact(tab)
            self.assertIsNotNone(found)
            html, rel_path = found
            self.assertEqual(html, "newer")
            self.assertEqual(rel_path, "reports/report-2.html")

    def test_glob_no_matches_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tab = ToolTab(
                slug="x", label="X", tool_dir=Path(tmp),
                run_steps=[["python3", "-c", "pass"]], artifact="reports/*.html",
            )
            self.assertIsNone(read_artifact(tab))

    def test_sub_pattern_overrides_default_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_dir = Path(tmp)
            (tool_dir / "owner.html").write_text("owner")
            (tool_dir / "client.html").write_text("client")
            tab = ToolTab(
                slug="x", label="X", tool_dir=tool_dir,
                run_steps=[["python3", "-c", "pass"]], artifact="owner.html",
            )
            html, rel_path = read_artifact(tab, sub_pattern="client.html")
            self.assertEqual(html, "client")
            self.assertEqual(rel_path, "client.html")


class ShellRenderTests(unittest.TestCase):
    def test_renders_all_tab_labels(self):
        html = render_shell(TOOL_TABS)
        for tab in TOOL_TABS:
            self.assertIn(tab.label, html)
            self.assertIn(f'data-slug="{tab.slug}"', html)

    def test_valid_document_shape(self):
        html = render_shell(TOOL_TABS)
        self.assertTrue(html.strip().startswith("<!doctype html>"))
        self.assertTrue(html.strip().endswith("</html>"))

    def test_penny_dashboard_pane_has_sub_toggle_buttons(self):
        html = render_shell(TOOL_TABS)
        self.assertIn("Owner view (internal)", html)
        self.assertIn("Client-safe view", html)
        self.assertIn("fc-sub-btn", html)

    def test_escapes_html_in_labels(self):
        fake = [ToolTab(slug="x", label="<script>alert(1)</script>", tool_dir=Path("."),
                         run_steps=[["python3", "-c", "pass"]], artifact="a.html")]
        html = render_shell(fake)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
