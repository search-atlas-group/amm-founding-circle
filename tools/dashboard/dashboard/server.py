"""Founding Circle Dashboard — a small stdlib-only local server.

Zero pip installs (matches the repo's dependency-light bar): plain
`http.server` + `subprocess`. Serves one shell page with a tab per tool;
each tab's pane is an `<iframe srcdoc="...">` holding that tool's own,
already-complete HTML report — so embedding six independently-generated
documents never collides on duplicate <html>/<head>/<style> tags.

Routes:
  GET  /                          the tab shell
  GET  /api/tab/<slug>            read the tool's current artifact (no re-run)
  POST /api/run/<slug>            re-run the tool's own report command, then
                                   read the fresh artifact back
"""

from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .shell import render_shell
from .tools_config import TOOL_BY_SLUG, TOOL_TABS, read_artifact


def _run_tool(slug: str) -> dict:
    tab = TOOL_BY_SLUG.get(slug)
    if tab is None:
        return {"ok": False, "error": f"Unknown tool: {slug}"}

    log_lines: list[str] = []
    before = read_artifact(tab)
    before_mtime = None
    if before is not None:
        try:
            before_mtime = (tab.tool_dir / before[1]).stat().st_mtime
        except OSError:
            before_mtime = None

    for step in tab.run_steps:
        try:
            result = subprocess.run(
                step,
                cwd=tab.tool_dir,
                capture_output=True,
                text=True,
                timeout=tab.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"'{' '.join(step)}' timed out after {tab.timeout_s}s",
                "log": "\n".join(log_lines),
            }
        except OSError as exc:
            return {
                "ok": False,
                "error": f"Could not launch '{' '.join(step)}': {exc}",
                "log": "\n".join(log_lines),
            }
        log_lines.append(f"$ {' '.join(step)} (exit {result.returncode})\n{result.stdout}{result.stderr}")
        # A non-zero exit is NOT necessarily a run failure for these tools: both
        # Bug Hunter and Connection Sentinel deliberately use the exit code to
        # signal findings (e.g. "critical issue found" / "a connection is down"),
        # per their own run.py/sentinel.py docstrings -- that is the tool doing
        # its job, not the dashboard's refresh breaking. So we don't abort the
        # step chain here; whether the run actually produced something is
        # decided below by whether a fresh artifact exists, not by the exit code.

    found = read_artifact(tab)
    if found is None:
        return {
            "ok": False,
            "error": "The command ran but no report file was found yet at the expected path.",
            "log": "\n".join(log_lines),
        }
    html, artifact_path = found
    after_mtime = None
    try:
        after_mtime = (tab.tool_dir / artifact_path).stat().st_mtime
    except OSError:
        pass
    fresh = before_mtime is None or after_mtime is None or after_mtime > before_mtime
    return {
        "ok": True,
        "html": html,
        "artifact_path": artifact_path,
        "log": "\n".join(log_lines),
        "fresh": fresh,
    }


def _read_tab(slug: str, sub_index: int | None) -> dict:
    tab = TOOL_BY_SLUG.get(slug)
    if tab is None:
        return {"ok": False, "error": f"Unknown tool: {slug}"}
    sub_pattern = None
    if sub_index is not None and tab.sub_tabs:
        try:
            sub_pattern = tab.sub_tabs[sub_index][1]
        except IndexError:
            sub_pattern = tab.sub_tabs[0][1]
    found = read_artifact(tab, sub_pattern)
    if found is None:
        return {
            "ok": False,
            "error": "No report generated yet — click Refresh to run this tool for the first time.",
        }
    html, artifact_path = found
    return {"ok": True, "html": html, "artifact_path": artifact_path}


class Handler(BaseHTTPRequestHandler):
    server_version = "FoundingCircleDashboard/1.0"

    def log_message(self, fmt, *args):  # quieter default logging
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status: int = 200) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 (stdlib method name)
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_shell(TOOL_TABS))
            return
        if parsed.path.startswith("/api/tab/"):
            slug = parsed.path.removeprefix("/api/tab/")
            qs = parse_qs(parsed.query)
            sub = qs.get("sub", [None])[0]
            sub_index = int(sub) if sub is not None else None
            self._send_json(_read_tab(slug, sub_index))
            return
        self._send_html("<h1>Not found</h1>", status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/run/"):
            slug = parsed.path.removeprefix("/api/run/")
            self._send_json(_run_tool(slug))
            return
        self._send_json({"ok": False, "error": "Unknown route"}, status=404)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Founding Circle Dashboard running at http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
