#!/usr/bin/env python3
"""Connect this computer to the AMM portal, then run your ladder audit from the portal.

The audit itself makes no network call. Only these commands talk to the
network, and only when you start them:

  pair      trades the one-time code the portal shows you for a device token
  listen    waits for the "Run audit" button in the portal, runs the audit on
            this computer, streams plain progress lines and publishes the
            stripped share payload that ``share.py`` builds (the leak guard
            runs first). No file path, repo name or file content is sent.
  connect   saves a token you pasted by hand (the older route)
  publish   sends the payload once, from the terminal, after you say yes

The token is created by you in the portal ("Connect your audit" on /onboarding).
It is stored in ``~/.config/amm-portal/connection.json`` (Windows:
``%APPDATA%\\amm-portal\\connection.json``) and is never printed.

Standard library only.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
DEFAULT_FILE = HERE / "portal.default.json"
TIMEOUT = 15
LISTEN_WAIT = 25
LISTEN_TIMEOUT = 40
RUN_WAIT = 20
_ran = [False]
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
REASON_RE = re.compile(r"^[a-z0-9_]{1,40}$")

NOT_SET = ("The portal address is not set yet. Ask JD for it, then run "
           "./onboarding/onboard.sh --connect --portal <address>")
NOT_CONNECTED = ("Not connected to the portal. Create a token under 'Connect your "
                 "audit' on /onboarding in the portal, then run:\n"
                 "  ./onboarding/onboard.sh --connect --portal <address>\n"
                 "(Windows: .\\onboarding\\onboard.ps1 -Connect -Portal <address>)")


class PortalError(Exception):
    """A message that is safe to show a member. Never contains the token."""


def redact(text: str, token: str | None) -> str:
    text = str(text)
    if token:
        text = text.replace(token, "[token]")
    return re.sub(r"amm_[A-Za-z0-9_\-]{8,}", "[token]", text)


# --- config -----------------------------------------------------------------


def config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path.home() / ".config"
    return base / "amm-portal" / "connection.json"


def load() -> dict | None:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not all(data.get(k) for k in ("portal_url", "token", "slug")):
        return None
    return data


def _save(portal_url: str, token: str, slug: str) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"portal_url": portal_url, "token": token, "slug": slug}, indent=2)
    # Create with 0600 from the first byte so the token is never world-readable.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body + "\n")
    try:
        os.chmod(path, 0o600)  # best effort on Windows
    except OSError:
        pass
    return path


def disconnect() -> bool:
    path = config_path()
    if path.exists():
        path.unlink()
        return True
    return False


def default_portal_url() -> str:
    try:
        return str(json.loads(DEFAULT_FILE.read_text(encoding="utf-8")).get("portal_url") or "")
    except (OSError, ValueError):
        return ""


def resolve_portal_url(explicit: str | None = None) -> str:
    """explicit arg, then env AMM_PORTAL_URL, then saved connection, then default file."""
    saved = load()
    url = (explicit or os.environ.get("AMM_PORTAL_URL")
           or (saved or {}).get("portal_url") or default_portal_url() or "").strip()
    if not url:
        raise PortalError(NOT_SET)
    return validate_url(url)


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise PortalError("The portal address must look like https://your-portal.example")
    if parsed.scheme != "https" and host not in LOCAL_HOSTS:
        raise PortalError("The portal address must start with https:// "
                          "(plain http is only allowed for localhost).")
    return url.rstrip("/")


# --- http -------------------------------------------------------------------


def _reason(body: bytes) -> str | None:
    try:
        reason = json.loads(body.decode("utf-8")).get("reason")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
    return reason if isinstance(reason, str) and REASON_RE.match(reason) else None


def _request(method: str, url: str, token: str | None, body: dict | None = None,
             timeout: int = TIMEOUT, retry: bool = True) -> tuple[int, dict, bytes]:
    """One request, one retry on connection error only. Returns (status, json, raw)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "User-Agent": "amm-founding-circle-onboarding"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    for _attempt in range(2 if retry else 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as err:  # a real answer: never retried
            raw = err.read() or b""
            status = err.code
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            continue
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            parsed = {}
        return status, parsed if isinstance(parsed, dict) else {}, raw
    raise PortalError("Could not reach the portal. Check your internet connection and "
                      "the portal address, then try again.") from None


def _status_message(status: int, raw: bytes) -> str:
    reason = _reason(raw)
    if status == 401:
        return ("The portal did not accept your token. Create a new one under 'Connect "
                "your audit' on /onboarding, then run --connect again.")
    if status == 400:
        code = f" ({reason})" if reason else ""
        return (f"The portal could not accept this upload{code}. "
                "Run git pull to update this repo, then try again.")
    if status == 413:
        return "The upload was too large for the portal. Please tell JD."
    if status == 415:
        return "The portal rejected the upload format. Run git pull to update this repo, then try again."
    if status == 429:
        return "Too many uploads in a short time. Wait a few minutes and try again."
    if status >= 500:
        return "The portal had a problem on its side. Try again in a few minutes."
    return f"The portal answered with an unexpected status ({status})."


def connect(url: str, token: str) -> str:
    """Check the token with whoami, save the connection, return the slug."""
    url = validate_url(url)
    if not re.match(r"^amm_[A-Za-z0-9_\-]{20,}$", token or ""):
        raise PortalError("That does not look like a portal token (it starts with amm_). "
                          "Copy it again from 'Connect your audit' in the portal.")
    status, data, raw = _request("GET", f"{url}/api/scans/whoami", token)
    if status != 200:
        raise PortalError(_status_message(status, raw))
    slug = data.get("slug")
    if not isinstance(slug, str) or not slug:
        raise PortalError("The portal answered, but not with a member name. Please tell JD.")
    _save(url, token, slug)
    return slug


def publish(payload: dict) -> dict:
    """POST the payload. Returns the server JSON (adds 'http_status')."""
    conn = load()
    if not conn:
        raise PortalError(NOT_CONNECTED)
    url = validate_url(conn["portal_url"])
    status, data, raw = _request("POST", f"{url}/api/scans/upload", conn["token"], payload)
    if status in (200, 201):
        data["http_status"] = status
        return data
    raise PortalError(_status_message(status, raw))


# --- pair and listen ---------------------------------------------------------


def pair(url: str, code: str) -> str:
    """Trade a one-time portal code for a device token, save it, return the slug."""
    url = validate_url(url)
    status, data, raw = _request("POST", f"{url}/api/scans/pair", None, {"code": (code or "").strip()})
    if status == 201 and isinstance(data.get("token"), str) and isinstance(data.get("slug"), str):
        _save(url, data["token"], data["slug"])
        return data["slug"]
    reason = _reason(raw)
    if status == 401:
        raise PortalError("That code did not work. A code is single use and lasts 10 minutes. "
                          "Press 'Connect this computer' in the portal for a new one.")
    if status == 409 and reason == "device_limit":
        raise PortalError("This account already has 3 connected computers. "
                          "Disconnect one in the portal (Onboarding), then try again.")
    raise PortalError(_status_message(status, raw))


def _say(conn: dict, run_id: str, *lines: str) -> None:
    """Show a progress line here and send it to the portal. Best effort: a failed send never stops the audit."""
    for line in lines:
        print(f"  {line}")
    try:
        _request("POST", f"{conn['portal_url']}/api/scans/runs/{run_id}/log", conn["token"],
                 {"lines": list(lines)}, retry=False)
    except PortalError:
        pass


def _finish(conn: dict, run_id: str, status: str, **extra) -> None:
    try:
        _request("POST", f"{conn['portal_url']}/api/scans/runs/{run_id}/finish", conn["token"],
                 {"status": status, **extra})
    except PortalError:
        print("  Could not tell the portal how the run ended. Check the Onboarding page.")


def run_requested_audit(conn: dict, run_id: str) -> str:
    """One requested run: audit locally, leak-guard, publish, finish. Returns the end status."""
    import ladder_probe as probe_mod
    import share

    _ran[0] = True
    print(f"Run requested from the portal ({run_id}).")
    try:
        _say(conn, run_id, "Reading your agent setup on this computer. Nothing leaves it yet.")
        result = probe_mod.probe(probe_mod.load_answers())
        verdict = probe_mod.assess(result)
        _say(conn, run_id, "Scoring the ten rungs.")
        payload = share.build_payload(conn["slug"], result, verdict)
    except Exception:  # a broken probe must end the run, not the connector
        _say(conn, run_id, "The audit could not finish on this computer.")
        _finish(conn, run_id, "failed", failure="audit_failed")
        return "failed"
    if share.assert_clean(payload):
        _say(conn, run_id, "Stopped before sending: the result held something path-like. Nothing was sent.")
        _finish(conn, run_id, "failed", failure="rejected")
        return "failed"
    _say(conn, run_id, *[line.strip() for line in summarize(payload)])
    _say(conn, run_id, "Sending the stripped result to your portal (no paths, repo names or file contents).")
    try:
        out = publish(payload)
    except PortalError as err:
        _say(conn, run_id, "The portal did not accept the result.")
        print(f"  {redact(str(err), conn['token'])}")
        _finish(conn, run_id, "failed", failure="publish_failed")
        return "failed"
    scan_id = out.get("scanId")
    if not isinstance(scan_id, str):
        _finish(conn, run_id, "failed", failure="publish_failed")
        return "failed"
    _say(conn, run_id, "Already up to date, nothing new to add." if out.get("created") is False else "Published. Your portal is updating.")
    _finish(conn, run_id, "done", scanId=scan_id)
    return "done"


def listen(conn: dict, *, once: bool = False, wait: int | None = None, sleep=time.sleep) -> int:
    """Wait for runs from the portal. Returns only on Ctrl+C, a revoked token, or after one poll with once=True."""
    url = validate_url(conn["portal_url"])
    conn = {**conn, "portal_url": url}
    delay = 5
    print(f"Connected to {url} as {conn['slug']}. Waiting for 'Run audit' in the portal. Ctrl+C stops this.")
    while True:
        hold = (wait if wait is not None else 0) if once else LISTEN_WAIT
        try:
            status, data, _raw = _request("GET", f"{url}/api/scans/runs/next?wait={hold}", conn["token"],
                                          timeout=LISTEN_TIMEOUT, retry=False)
        except PortalError:
            if once:
                return 1
            sleep(delay)
            delay = min(delay * 2, 60)
            continue
        if status == 401:
            print("The portal no longer accepts this connection (it was disconnected or expired). "
                  "Press 'Connect this computer' in the portal to pair again.")
            return 1
        if status == 429:
            sleep(60)
        elif status != 200:
            if once:
                return 1
            sleep(delay)
            delay = min(delay * 2, 60)
        else:
            delay = 5
            run = data.get("run")
            run_id = run.get("id") if isinstance(run, dict) else None
            if isinstance(run_id, str) and RUN_ID_RE.match(run_id):
                run_requested_audit(conn, run_id)
        if once:
            return 0


# --- cli --------------------------------------------------------------------


def summarize(payload: dict) -> list[str]:
    ladder = payload["ladder"]
    counts = {"solid": 0, "partial": 0, "gap": 0, "unknown": 0}
    for rung in ladder["rungs"].values():
        counts[rung["status"]] = counts.get(rung["status"], 0) + 1
    return [
        f"  score:      {ladder['system_score']}",
        f"  reach:      {ladder['scan_reach']}",
        f"  floor:      {ladder['scan_floor']}",
        "  rungs:      " + ", ".join(f"{k} {v}" for k, v in counts.items()),
        f"  objectives: {len(payload['objectives'])} (status only, no file contents)",
    ]


def cmd_connect(args) -> int:
    url = resolve_portal_url(args.portal)
    token = os.environ.get("AMM_PORTAL_TOKEN") or ""
    if not token:
        if not sys.stdin.isatty():
            raise PortalError("No token given. Set AMM_PORTAL_TOKEN or run this in a terminal.")
        token = getpass.getpass("Paste your portal token (hidden): ").strip()
    slug = connect(url, token.strip())
    print(f"Connected to {url} as {slug}.")
    print("Nothing was uploaded. Run --publish when you want your results in the portal.")
    return 0


def cmd_pair(args) -> int:
    url = resolve_portal_url(args.portal)
    slug = pair(url, args.pair)
    print(f"Connected to {url} as {slug}.")
    print("Nothing was uploaded. The portal's Run audit button now works while this computer is listening.")
    return 0


def cmd_run(args) -> int:
    """Run the audit the portal asked for, once. With a code: pair first. Without: use the saved connection."""
    if args.run:
        url = resolve_portal_url(args.portal)
        slug = pair(url, args.run)
        print(f"Connected to {url} as {slug}.")
    code, conn = preflight()
    if conn is None:
        return code
    print("Looking for the audit you asked for in the portal.")
    status = listen(conn, once=True, wait=RUN_WAIT)
    if status == 0 and not _ran[0]:
        print("The portal has no audit waiting. Press Run audit on the Onboarding page, then run this again.")
    return status


def cmd_listen(args) -> int:
    code, conn = preflight()
    if conn is None:
        return code
    try:
        return listen(conn, once=args.once)
    except KeyboardInterrupt:
        print("\nStopped listening.")
        return 0


def cmd_disconnect(_args) -> int:
    if disconnect():
        print(f"Disconnected. Removed {config_path()}")
        print("You can also revoke the token in the portal.")
    else:
        print("Not connected, nothing to remove.")
    return 0


def preflight() -> tuple[int, dict | None]:
    """Check the connection and portal address before any audit or network call."""
    conn = load()
    if not conn:
        try:
            resolve_portal_url()
        except PortalError as err:
            print(err)
        else:
            print(NOT_CONNECTED)
        return 2, None
    try:
        validate_url(conn["portal_url"])
    except PortalError as err:
        print(err)
        return 2, None
    return 0, conn


def cmd_publish(args) -> int:
    code, conn = preflight()
    if conn is None:
        return code
    import ladder_probe as probe_mod
    import share

    result = probe_mod.probe(probe_mod.load_answers())
    verdict = probe_mod.assess(result)
    payload = share.build_payload(conn["slug"], result, verdict)
    leaks = share.assert_clean(payload)
    if leaks:
        print("REFUSING to publish: something path-like got into the payload:")
        for leak in leaks:
            print(f"  {leak}")
        print("This is a bug. Nothing was sent. Please report it.")
        return 1

    print(f"This will be sent to {conn['portal_url']} as {conn['slug']}:")
    print("\n".join(summarize(payload)))
    print("No file paths, repo names, client names or file contents are included.")
    if not args.yes:
        if not sys.stdin.isatty():
            print("Not sent: add --yes to publish without a prompt.")
            return 2
        if input("Send this now? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Not sent.")
            return 0
    out = publish(payload)
    if out.get("created") is False:
        print("The portal already has this exact result, nothing new was added.")
    else:
        s = out.get("summary") or {}
        c = s.get("counts") or {}
        print(f"Published. score {s.get('score')}, reach {s.get('reach')}, floor {s.get('floor')}; "
              f"solid {c.get('solid')}, partial {c.get('partial')}, gap {c.get('gap')}, "
              f"unknown {c.get('unknown')}.")
    nxt = out.get("next") if isinstance(out.get("next"), str) and str(out.get("next")).startswith("/") else "/onboarding"
    print(f"Open: {conn['portal_url'].rstrip('/')}{nxt}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--connect", action="store_true")
    group.add_argument("--disconnect", action="store_true")
    group.add_argument("--publish", action="store_true")
    group.add_argument("--pair", metavar="CODE", help="trade the one-time code from the portal for a device token")
    group.add_argument("--listen", action="store_true", help="wait for the portal's Run audit button")
    group.add_argument("--run", nargs="?", const="", metavar="CODE",
                       help="run the audit the portal asked for, once (with CODE, connect first)")
    group.add_argument("--preflight", action="store_true",
                       help="check the connection only; no audit, no network")
    parser.add_argument("--portal", help="portal address, e.g. https://portal.example")
    parser.add_argument("--yes", action="store_true", help="skip the y/N prompt")
    parser.add_argument("--once", action="store_true", help="with --listen: check once and exit")
    args = parser.parse_args(argv)
    try:
        if args.run is not None:
            return cmd_run(args)
        if args.pair:
            return cmd_pair(args)
        if args.listen:
            return cmd_listen(args)
        if args.connect:
            return cmd_connect(args)
        if args.disconnect:
            return cmd_disconnect(args)
        if args.preflight:
            return preflight()[0]
        return cmd_publish(args)
    except PortalError as err:
        tok = (load() or {}).get("token") or os.environ.get("AMM_PORTAL_TOKEN")
        print(redact(str(err), tok), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
