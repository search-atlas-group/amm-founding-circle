"""Ground-truth probes for Connection Sentinel.

Every probe runs a real, live check against the connection it's watching —
never a self-report. Pure classification logic (``classify_http_status``) is
kept separate from the I/O so it can be unit tested without a network call.

Three probe types:
  http       - any REST/HTTP endpoint. A 401/403 is flagged as an auth
               failure specifically (as opposed to a generic error), so the
               alert can say "your token expired" instead of just "broken."
  mcp_http   - same live-request check as http, but names the MCP-specific
               fix on a 401/403 -- this is the Rick Janson case: an MCP
               server whose login silently expired mid-run.
  command    - the escape hatch. Any read-only shell command; exit 0 =
               healthy, anything else = down. Covers CLIs with their own
               auth-check subcommand, local process checks, anything not
               covered by http/mcp_http.
"""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

OK = "ok"
AUTH_FAILED = "auth_failed"
UNREACHABLE = "unreachable"
ERROR = "error"

AUTH_FIX_HINTS = {
    "http": (
        "Token/API key looks expired or revoked -- generate a fresh one "
        "and update your .env."
    ),
    "mcp_http": (
        "MCP login expired -- reconnect this MCP server (re-run its "
        "auth/login step) and re-authorize."
    ),
}

GENERIC_COMMAND_FIX_HINT = (
    "The command reported a non-zero exit -- check what it depends on "
    "(login, network, or the service it's probing)."
)


@dataclass
class ProbeResult:
    name: str
    kind: str  # "ok" | "auth_failed" | "unreachable" | "error"
    detail: str
    fix_hint: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def healthy(self) -> bool:
        return self.kind == OK


def classify_http_status(status_code: int) -> tuple[str, str]:
    """Pure classification, no I/O. 401/403 -> auth failure specifically;
    2xx/3xx -> healthy (a redirect isn't a break); anything else -> error."""
    if status_code in (401, 403):
        return AUTH_FAILED, f"HTTP {status_code}"
    if 200 <= status_code < 400:
        return OK, f"HTTP {status_code}"
    return ERROR, f"HTTP {status_code}"


def probe_http(conn) -> ProbeResult:
    """GET/POST a URL and classify the real response. Never trusts anything
    the endpoint merely claims -- only the status code / connection outcome."""
    body = getattr(conn, "body", None)
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        conn.url, data=data, headers=conn.headers or {}, method=conn.method or "GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=conn.timeout or 8) as resp:
            kind, detail = classify_http_status(resp.status)
    except urllib.error.HTTPError as e:
        kind, detail = classify_http_status(e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        kind, detail = UNREACHABLE, f"Connection error: {e}"
    fix_hint = AUTH_FIX_HINTS["http"] if kind == AUTH_FAILED else ""
    return ProbeResult(name=conn.name, kind=kind, detail=detail, fix_hint=fix_hint)


def probe_mcp_http(conn) -> ProbeResult:
    """Same live classification as probe_http, but with the MCP-specific fix
    hint on an auth failure -- the Rick Janson case: detected the same way
    any real auth failure is (a live 401), just named for what it is."""
    result = probe_http(conn)
    if result.kind == AUTH_FAILED:
        result.fix_hint = AUTH_FIX_HINTS["mcp_http"]
    return result


def probe_command(conn) -> ProbeResult:
    """Run a read-only shell command. Exit 0 = healthy, non-zero = down."""
    timeout = conn.timeout or 15
    try:
        proc = subprocess.run(
            conn.command, shell=True, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(conn.name, UNREACHABLE, f"Command timed out after {timeout}s")
    if proc.returncode == 0:
        return ProbeResult(conn.name, OK, "exit 0")
    tail_lines = (proc.stderr or proc.stdout or "").strip().splitlines()
    tail = tail_lines[-1] if tail_lines else ""
    return ProbeResult(
        conn.name, ERROR, f"exit {proc.returncode}: {tail}",
        fix_hint=GENERIC_COMMAND_FIX_HINT,
    )


PROBES = {
    "http": probe_http,
    "mcp_http": probe_mcp_http,
    "command": probe_command,
}


def run_probe(conn) -> ProbeResult:
    """Dispatch by connection type. A single bad connection (bad URL, a
    probe that raises something unexpected) must never take down the whole
    sweep -- caught here and reported as an ERROR result instead."""
    fn = PROBES.get(conn.type)
    if fn is None:
        return ProbeResult(conn.name, ERROR, f"Unknown connection type: {conn.type!r}")
    try:
        return fn(conn)
    except Exception as e:
        return ProbeResult(conn.name, ERROR, f"Probe raised: {e}")
