from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

from scripts.shep_service import ShepService, _Handler, _UnixHTTPServer


TOKEN = "test-service-token"


def service(tmp_path: Path) -> ShepService:
    return ShepService(
        token=TOKEN,
        state_path=tmp_path / "missions.json",
        clock=lambda: 1_786_017_600.0,
    )


def headers(**extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}", **extra}


def test_service_requires_bearer_auth_for_health(tmp_path: Path) -> None:
    status, _, body = service(tmp_path).handle("GET", "/v1/health")

    assert status == 401
    assert body["error"]["code"] == "unauthorized"


def test_service_creates_and_lists_missions_with_revision_etag_and_request_id(tmp_path: Path) -> None:
    shep = service(tmp_path)
    status, response_headers, body = shep.handle(
        "POST",
        "/v1/missions",
        headers(**{"Idempotency-Key": "create-1", "X-Request-Id": "req-fixed"}),
        json.dumps({"goal": "Ship the socket", "mode": "fleet", "base": "develop"}).encode(),
    )

    assert status == 201
    assert response_headers["X-Request-Id"] == "req-fixed"
    assert response_headers["ETag"] == '"1"'
    assert body["mission"]["schema"] == "shep-mission/v1"
    assert body["mission"]["revision"] == 1

    list_status, _, listed = shep.handle("GET", "/v1/missions?status=queued", headers())
    assert list_status == 200
    assert listed["items"][0]["id"] == body["mission"]["id"]


def test_service_idempotency_is_durable_and_conflicts_on_changed_body(tmp_path: Path) -> None:
    shep = service(tmp_path)
    request = json.dumps({"goal": "Ship the socket"}).encode()
    first = shep.handle("POST", "/v1/missions", headers(**{"Idempotency-Key": "same"}), request)
    replay = shep.handle("POST", "/v1/missions", headers(**{"Idempotency-Key": "same"}), request)
    conflict = shep.handle(
        "POST",
        "/v1/missions",
        headers(**{"Idempotency-Key": "same"}),
        json.dumps({"goal": "Different mission"}).encode(),
    )

    assert first[0] == 201
    assert replay[0] == 200
    assert replay[2] == first[2]
    assert conflict[0] == 409
    assert conflict[2]["error"]["code"] == "idempotency_conflict"
    assert (tmp_path / "missions.idempotency.json").stat().st_mode & 0o777 == 0o600


def test_service_rejects_unknown_fields_and_invalid_limits(tmp_path: Path) -> None:
    shep = service(tmp_path)
    unknown = shep.handle(
        "POST",
        "/v1/missions",
        headers(**{"Idempotency-Key": "unknown"}),
        json.dumps({"goal": "Ship it", "dispatch": True}).encode(),
    )
    limit = shep.handle("GET", "/v1/missions?limit=101", headers())

    assert unknown[0] == 422
    assert limit[0] == 422


def test_unix_socket_serves_authenticated_http(tmp_path: Path) -> None:
    socket_path = Path("/tmp/shep-test.sock")
    socket_path.unlink(missing_ok=True)
    server = _UnixHTTPServer(str(socket_path), _Handler)
    server.shep_service = service(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
            client.sendall(
                b"GET /v1/health HTTP/1.1\r\n"
                b"Host: shep.local\r\n"
                b"Authorization: Bearer test-service-token\r\n"
                b"Connection: close\r\n\r\n"
            )
            response = b""
            while chunk := client.recv(4096):
                response += chunk
    finally:
        server.shutdown()
        server.server_close()
        socket_path.unlink(missing_ok=True)

    assert b"200 OK" in response
    assert b'"status": "ready"' in response
