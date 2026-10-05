from __future__ import annotations

from pathlib import Path


OPENAPI = Path(__file__).parents[1] / "docs/shep-v1-openapi.yaml"


def test_openapi_declares_every_v1_mission_boundary() -> None:
    text = OPENAPI.read_text(encoding="utf-8")
    for path in (
        "/v1/health:",
        "/v1/missions:",
        "/v1/missions/{mission_id}:",
        "/v1/missions/{mission_id}/receipts:",
        "/v1/missions/{mission_id}/actions/approve:",
        "/v1/missions/{mission_id}/actions/dispatch:",
        "/v1/missions/{mission_id}/actions/cancel:",
        "/v1/missions/{mission_id}/events:",
    ):
        assert f"  {path}" in text
    assert "scheme: bearer" in text
    assert "IfMatch:" in text
    assert "IdempotencyKey:" in text
    assert "additionalProperties: false" in text


def test_openapi_preserves_fail_closed_and_revision_contract() -> None:
    text = OPENAPI.read_text(encoding="utf-8")
    assert "ETag:" in text
    assert "'409':" in text
    assert "expected_revision" in text
    assert "blocked" in text
    assert "additionalProperties: false" in text
