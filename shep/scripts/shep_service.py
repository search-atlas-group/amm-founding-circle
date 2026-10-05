"""Authenticated local Shep mission service.

This is the first transport slice of the v1 API.  It deliberately exposes only
readiness, mission listing, and mission creation until the approval/dispatch
state machine is wired to durable receipts.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import hmac
import http.server
import json
import os
import secrets
import socket
import socketserver
import tempfile
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

try:
    from .shep_missions import list_missions, queue_mission
except ImportError:  # pragma: no cover - direct script execution
    from shep_missions import list_missions, queue_mission


SERVICE_SCHEMA = "shep-health/v1"
MISSION_SCHEMA = "shep-mission/v1"
ALLOWED_CREATE_FIELDS = {"goal", "mode", "base"}
VALID_STATUSES = {
    "queued",
    "approved",
    "dispatching",
    "running",
    "review",
    "landed",
    "failed",
    "cancelled",
}
MAX_BODY_BYTES = 1_048_576


def _iso_timestamp(value: object) -> str:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        timestamp = time.time()
    return (
        dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _etag(revision: int) -> str:
    return f'"{revision}"'


def _json_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mission_response(mission: dict[str, Any]) -> dict[str, Any]:
    revision = int(mission.get("revision", 1))
    return {
        "schema": MISSION_SCHEMA,
        "id": mission["id"],
        "goal": mission["goal"],
        "mode": mission["mode"],
        "base": mission["base"],
        "status": mission["status"],
        "revision": revision,
        "branch_prefix": mission["branch_prefix"],
        "created_at": _iso_timestamp(mission.get("created_at")),
        "updated_at": _iso_timestamp(mission.get("updated_at")),
        "artifacts": mission.get("artifacts", {}),
    }


def _bearer(headers: dict[str, str]) -> str | None:
    value = headers.get("authorization", "")
    scheme, separator, token = value.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        return None
    return token


class ShepService:
    """Pure request dispatcher backed by the canonical mission store."""

    def __init__(
        self,
        *,
        token: str,
        state_path: str | os.PathLike[str],
        idempotency_path: str | os.PathLike[str] | None = None,
        clock: callable = time.time,
    ) -> None:
        if not isinstance(token, str) or not token:
            raise ValueError("service token must be non-empty")
        self.token = token
        self.state_path = Path(state_path).expanduser()
        self.idempotency_path = Path(
            idempotency_path
            or self.state_path.with_name(f"{self.state_path.stem}.idempotency.json")
        ).expanduser()
        self.clock = clock
        self._mutation_lock = threading.Lock()

    def _headers(self, request_id: str, *, etag: str | None = None) -> dict[str, str]:
        result = {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Request-Id": request_id,
        }
        if etag is not None:
            result["ETag"] = etag
        return result

    def _error(
        self,
        status: int,
        code: str,
        message: str,
        request_id: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, str], dict[str, Any]]:
        return (
            status,
            self._headers(request_id),
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                    "request_id": request_id,
                }
            },
        )

    def _read_idempotency(self) -> dict[str, Any]:
        try:
            value = json.loads(self.idempotency_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_idempotency(self, value: dict[str, Any]) -> None:
        self.idempotency_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.idempotency_path.parent, 0o700)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.idempotency_path.name}.", dir=self.idempotency_path.parent
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                json.dump(value, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.idempotency_path)
            os.chmod(self.idempotency_path, 0o600)
        finally:
            if fd >= 0:
                os.close(fd)
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)

    def _create(
        self,
        body: dict[str, Any],
        request_id: str,
        idempotency_key: str | None,
    ) -> tuple[int, dict[str, str], dict[str, Any]]:
        if not idempotency_key:
            return self._error(
                400,
                "invalid_request",
                "Idempotency-Key is required",
                request_id,
            )
        unknown = sorted(set(body) - ALLOWED_CREATE_FIELDS)
        if unknown:
            return self._error(
                422,
                "validation_failed",
                "Request contains unsupported fields",
                request_id,
                details={"fields": unknown},
            )
        if not isinstance(body.get("goal"), str) or not body["goal"].strip():
            return self._error(
                422,
                "validation_failed",
                "Mission goal is required",
                request_id,
            )
        mode = body.get("mode", "fleet")
        base = body.get("base", "develop")
        if mode not in {"inline", "fleet"} or not isinstance(base, str) or not base.strip():
            return self._error(
                422,
                "validation_failed",
                "Mission mode or base is invalid",
                request_id,
            )

        with self._mutation_lock:
            digest = _json_digest(body)
            idempotency = self._read_idempotency()
            prior = idempotency.get(idempotency_key)
            if isinstance(prior, dict):
                if prior.get("digest") != digest:
                    return self._error(
                        409,
                        "idempotency_conflict",
                        "Idempotency key was already used for another request",
                        request_id,
                    )
                mission = prior.get("mission")
                if isinstance(mission, dict):
                    output = {"mission": mission}
                    return 200, self._headers(request_id, etag=_etag(int(mission["revision"]))), output

            mission = queue_mission(
                body["goal"],
                mode=mode,
                base=base,
                path=self.state_path,
                now=self.clock(),
            )
            output_mission = _mission_response(mission)
            output = {"mission": output_mission}
            idempotency[idempotency_key] = {"digest": digest, "mission": output_mission}
            self._write_idempotency(idempotency)
            response_headers = self._headers(request_id, etag=_etag(1))
            response_headers["Location"] = f"/v1/missions/{mission['id']}"
            return 201, response_headers, output

    def handle(
        self,
        method: str,
        target: str,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> tuple[int, dict[str, str], dict[str, Any]]:
        request_headers = {key.lower(): value for key, value in (headers or {}).items()}
        request_id = request_headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:16]}"
        if not hmac.compare_digest(_bearer(request_headers) or "", self.token):
            return self._error(401, "unauthorized", "Authentication is required", request_id)

        parsed = urllib.parse.urlsplit(target)
        if method == "GET" and parsed.path == "/v1/health":
            return (
                200,
                self._headers(request_id),
                {"schema": SERVICE_SCHEMA, "status": "ready", "service_version": "1"},
            )
        if method == "GET" and parsed.path == "/v1/missions":
            params = urllib.parse.parse_qs(parsed.query, strict_parsing=False)
            status = params.get("status", [None])[0]
            if status is not None and status not in VALID_STATUSES:
                return self._error(422, "validation_failed", "Mission status is invalid", request_id)
            try:
                limit = int(params.get("limit", [50])[0])
            except (TypeError, ValueError):
                limit = 0
            if not 1 <= limit <= 100:
                return self._error(422, "validation_failed", "Mission limit must be 1 through 100", request_id)
            if params.get("cursor", [None])[0] not in {None, ""}:
                return self._error(422, "validation_failed", "Cursor is not valid", request_id)
            missions = list_missions(self.state_path)
            if status is not None:
                missions = [mission for mission in missions if mission.get("status") == status]
            items = [_mission_response(mission) for mission in missions[:limit]]
            return 200, self._headers(request_id), {"items": items, "next_cursor": None}
        if method == "POST" and parsed.path == "/v1/missions":
            if len(body) > MAX_BODY_BYTES:
                return self._error(413, "invalid_request", "Request body is too large", request_id)
            try:
                value = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return self._error(400, "invalid_request", "Request body must be JSON", request_id)
            if not isinstance(value, dict):
                return self._error(400, "invalid_request", "Request body must be an object", request_id)
            return self._create(value, request_id, request_headers.get("idempotency-key"))
        return self._error(404, "not_found", "Resource was not found", request_id)


class _UnixHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    address_family = socket.AF_UNIX
    daemon_threads = True
    allow_reuse_address = False


class _Handler(http.server.BaseHTTPRequestHandler):
    server: _UnixHTTPServer

    def _service(self) -> ShepService:
        return self.server.shep_service  # type: ignore[attr-defined]

    def _run(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY_BYTES:
            body = b"x" * (MAX_BODY_BYTES + 1)
        else:
            body = self.rfile.read(length)
        request_id = self.headers.get("X-Request-Id") or f"req-{uuid.uuid4().hex[:16]}"
        try:
            status, headers, payload = self._service().handle(
                self.command,
                self.path,
                dict(self.headers.items()),
                body,
            )
        except Exception:
            status, headers, payload = self._service()._error(
                500,
                "internal_error",
                "Shep could not complete the request",
                request_id,
            )
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        self._run()

    def do_POST(self) -> None:  # noqa: N802
        self._run()

    def log_message(self, format: str, *args: object) -> None:
        return


def _runtime_dir() -> Path:
    return Path(os.environ.get("MISSION_ENGINE_DIR", str(Path.home() / ".mission-engine"))).expanduser()


def ensure_service_token(path: str | os.PathLike[str] | None = None) -> str:
    destination = Path(path).expanduser() if path else _runtime_dir() / "service.token"
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination.parent, 0o700)
    try:
        token = destination.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        token = secrets.token_urlsafe(32)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, token.encode("utf-8"))
            os.write(fd, b"\n")
        finally:
            os.close(fd)
    if not token:
        raise RuntimeError("service token is empty")
    os.chmod(destination, 0o600)
    return token


def serve(
    *,
    socket_path: str | os.PathLike[str] | None = None,
    token_path: str | os.PathLike[str] | None = None,
    state_path: str | os.PathLike[str] | None = None,
) -> None:
    runtime = _runtime_dir()
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(runtime, 0o700)
    destination = Path(socket_path).expanduser() if socket_path else runtime / "shep.sock"
    if destination.exists():
        if not destination.is_socket():
            raise RuntimeError("Shep socket path is occupied by a non-socket")
        destination.unlink()
    token = ensure_service_token(token_path)
    server = _UnixHTTPServer(str(destination), _Handler)
    os.chmod(destination, 0o600)
    server.shep_service = ShepService(
        token=token,
        state_path=state_path or runtime / "missions.json",
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        with contextlib.suppress(FileNotFoundError):
            destination.unlink()


if __name__ == "__main__":  # pragma: no cover - exercised through the service launcher
    serve()
