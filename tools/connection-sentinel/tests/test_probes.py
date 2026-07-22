import os
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Connection  # noqa: E402
from probes import (  # noqa: E402
    AUTH_FAILED,
    ERROR,
    OK,
    UNREACHABLE,
    classify_http_status,
    probe_command,
    probe_http,
    probe_mcp_http,
    run_probe,
)


class ClassifyHttpStatusTests(unittest.TestCase):
    def test_2xx_is_ok(self):
        kind, detail = classify_http_status(200)
        self.assertEqual(kind, OK)
        self.assertIn("200", detail)

    def test_3xx_redirect_is_ok_not_a_break(self):
        kind, _ = classify_http_status(302)
        self.assertEqual(kind, OK)

    def test_401_is_auth_failed(self):
        kind, _ = classify_http_status(401)
        self.assertEqual(kind, AUTH_FAILED)

    def test_403_is_auth_failed(self):
        kind, _ = classify_http_status(403)
        self.assertEqual(kind, AUTH_FAILED)

    def test_500_is_error_not_auth(self):
        kind, _ = classify_http_status(500)
        self.assertEqual(kind, ERROR)

    def test_404_is_error(self):
        kind, _ = classify_http_status(404)
        self.assertEqual(kind, ERROR)


class FakeHTTPResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def _conn(**kw):
    defaults = dict(name="Test API", type="http", url="https://example.invalid/health")
    defaults.update(kw)
    return Connection(**defaults)


class ProbeHttpTests(unittest.TestCase):
    @patch("probes.urllib.request.urlopen")
    def test_healthy_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(200)
        result = probe_http(_conn())
        self.assertTrue(result.healthy)
        self.assertEqual(result.kind, OK)
        self.assertEqual(result.name, "Test API")

    @patch("probes.urllib.request.urlopen")
    def test_401_flags_auth_failed_with_fix_hint(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.invalid", 401, "Unauthorized", {}, None
        )
        result = probe_http(_conn())
        self.assertFalse(result.healthy)
        self.assertEqual(result.kind, AUTH_FAILED)
        self.assertTrue(result.fix_hint, "a 401 must always carry a plain-English fix hint")

    @patch("probes.urllib.request.urlopen")
    def test_connection_error_is_unreachable(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Name or service not known")
        result = probe_http(_conn())
        self.assertEqual(result.kind, UNREACHABLE)
        self.assertFalse(result.healthy)

    @patch("probes.urllib.request.urlopen")
    def test_server_error_has_no_fix_hint(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.invalid", 500, "Server Error", {}, None
        )
        result = probe_http(_conn())
        self.assertEqual(result.kind, ERROR)
        self.assertEqual(result.fix_hint, "")


class ProbeMcpHttpTests(unittest.TestCase):
    @patch("probes.urllib.request.urlopen")
    def test_401_names_mcp_specific_fix(self, mock_urlopen):
        conn = _conn(name="Search Atlas MCP", type="mcp_http", url="https://x.invalid/mcp")
        mock_urlopen.side_effect = urllib.error.HTTPError("https://x.invalid/mcp", 401, "no", {}, None)
        result = probe_mcp_http(conn)
        self.assertEqual(result.kind, AUTH_FAILED)
        self.assertIn("MCP", result.fix_hint)
        self.assertIn("reconnect", result.fix_hint.lower())

    @patch("probes.urllib.request.urlopen")
    def test_healthy_mcp_has_no_fix_hint(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(200)
        conn = _conn(name="Search Atlas MCP", type="mcp_http")
        result = probe_mcp_http(conn)
        self.assertTrue(result.healthy)
        self.assertEqual(result.fix_hint, "")


class ProbeCommandTests(unittest.TestCase):
    def test_exit_zero_is_healthy(self):
        conn = _conn(name="local check", type="command", command="true")
        result = probe_command(conn)
        self.assertTrue(result.healthy)

    def test_nonzero_exit_is_down_with_fix_hint(self):
        conn = _conn(name="local check", type="command", command="false")
        result = probe_command(conn)
        self.assertFalse(result.healthy)
        self.assertTrue(result.fix_hint)

    def test_timeout_is_unreachable(self):
        conn = _conn(name="slow check", type="command", command="sleep 5", timeout=1)
        result = probe_command(conn)
        self.assertEqual(result.kind, UNREACHABLE)

    def test_stderr_tail_surfaces_in_detail(self):
        conn = _conn(name="noisy", type="command", command="echo boom 1>&2; exit 3")
        result = probe_command(conn)
        self.assertIn("boom", result.detail)
        self.assertIn("exit 3", result.detail)


class RunProbeDispatchTests(unittest.TestCase):
    def test_unknown_type_is_error_not_crash(self):
        conn = _conn(name="mystery", type="carrier_pigeon")
        result = run_probe(conn)
        self.assertEqual(result.kind, ERROR)

    def test_probe_exception_never_crashes_the_sweep(self):
        # An unparseable URL raises inside urllib, not one of the caught
        # exception types in probe_http -- run_probe's outer guard must
        # still turn it into a reported result, never propagate.
        conn = _conn(name="broken", type="http", url="not a url at all")
        result = run_probe(conn)
        self.assertIn(result.kind, (OK, AUTH_FAILED, UNREACHABLE, ERROR))

    def test_dispatches_to_command_probe(self):
        conn = _conn(name="local", type="command", command="true")
        result = run_probe(conn)
        self.assertTrue(result.healthy)


if __name__ == "__main__":
    unittest.main()
