from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.shep_atlas import (
    AtlasChecksumError,
    AtlasStaleError,
    AtlasVersionError,
    build_atlas_handoff,
    build_atlas_mirror,
    open_outcome_snapshot,
    read_atlas_proposals,
    verify_atlas_handoff,
    verify_outcome_snapshot,
    write_atlas_mirror,
)


NOW = 1_786_017_600.0


def _proposal(root: Path, **overrides: object) -> dict:
    value = {
        "id": "fj-abc123",
        "source": "fleet_journey",
        "work_kind": "review",
        "short_goal": "Review the bounded change",
        "instruction": "Review the bounded change and write the report.",
        "recommendation": "Review the bounded change — report",
        "cwd": str(root),
        "project_path": str(root),
        "proposal_id": "fj-abc123",
        "project_name": "example",
        "routing": {"status": "resolved", "reason": "test"},
        "dispatchable": True,
        "acceptance_checks": [
            {"kind": "fleet_report_v1", "path": str(root / "report.json"), "expected_root": str(root)}
        ],
        "evidence": ["loop2 evidence session:s1"],
        "analysis_ref": {"schema": "atlas-loop2-evidence/v1"},
    }
    value.update(overrides)
    return value


def _write_proposals(path: Path, root: Path, *, generated_at: str = "2026-08-06T12:00:00+00:00", proposals=None) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "atlas-fleet-proposals/v3",
                "generated_at": generated_at,
                "proposals": [_proposal(root)] if proposals is None else proposals,
                "diagnostics": [],
            }
        ),
        encoding="utf-8",
    )


def _write_snapshot(path: Path, *, generated_at_s: float = NOW, schema_major: int = 1) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE ledger_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("CREATE TABLE outcomes (rec_id TEXT)")
    connection.execute("INSERT INTO outcomes VALUES ('rec-1')")
    connection.execute("PRAGMA user_version = 1")
    meta = {
        "schema_major": schema_major,
        "schema_minor": 0,
        "generated_at_s": generated_at_s,
        "ledger_seq": 4,
        "source_commit": "abc1234",
        "freshness_sla_s": 86400,
        "row_count": 1,
    }
    for key in ("schema_major", "schema_minor", "generated_at_s", "ledger_seq", "source_commit", "freshness_sla_s"):
        connection.execute("INSERT INTO ledger_meta VALUES (?, ?)", (key, str(meta[key])))
    connection.commit()
    connection.close()
    meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256.json").write_text(json.dumps(meta), encoding="utf-8")


def test_missing_or_stale_proposals_block_instead_of_looking_empty(tmp_path: Path) -> None:
    missing = read_atlas_proposals(tmp_path / "missing.json", now_s=NOW)
    assert missing["ok"] is False
    assert missing["blocked_reason"] == "atlas_proposals_missing"

    path = tmp_path / "proposals.json"
    _write_proposals(path, tmp_path, generated_at="2026-08-06T08:00:00+00:00")
    stale = read_atlas_proposals(path, now_s=NOW, max_age_s=60)
    assert stale["ok"] is False
    assert stale["blocked_reason"] == "atlas_proposals_stale"


def test_malformed_proposals_block_instead_of_raising(tmp_path: Path) -> None:
    path = tmp_path / "fleet-journey-proposals.json"
    path.write_text("not-json", encoding="utf-8")

    result = read_atlas_proposals(path, now_s=NOW)

    assert result["ok"] is False
    assert result["blocked_reason"] == "atlas_proposals_malformed"


def test_v3_reader_keeps_complete_proposals_and_drops_invalid_entries(tmp_path: Path) -> None:
    path = tmp_path / "proposals.json"
    _write_proposals(path, tmp_path, proposals=[_proposal(tmp_path), {"proposal_id": "bad"}])

    result = read_atlas_proposals(path, now_s=NOW)

    assert result["ok"] is True
    assert [item["proposal_id"] for item in result["proposals"]] == ["fj-abc123"]
    assert "dropped 1" in result["notes"][-1]


def test_handoff_is_bound_to_the_current_proposal_digest_and_target(tmp_path: Path) -> None:
    path = tmp_path / "proposals.json"
    _write_proposals(path, tmp_path)
    read = read_atlas_proposals(path, now_s=NOW)
    handoff = build_atlas_handoff(
        read,
        "fj-abc123",
        approver="human-1",
        approved_at="2026-08-06T12:01:00Z",
    )

    assert handoff["schema"] == "atlas-handoff/v1"
    assert verify_atlas_handoff(handoff, read)["ok"] is True

    changed = dict(read["proposals"][0])
    changed["instruction"] = "A different instruction"
    changed_read = dict(read, proposals=[changed])
    assert verify_atlas_handoff(handoff, changed_read)["reason"] == "proposal_changed"
    changed_handoff = dict(handoff, acceptance_checks=[])
    assert verify_atlas_handoff(changed_handoff, read)["reason"] == "acceptance_checks_changed"


def test_outcome_snapshot_verifies_checksum_schema_freshness_and_read_only(tmp_path: Path) -> None:
    snapshot = tmp_path / "outcomes.db"
    _write_snapshot(snapshot)

    meta = verify_outcome_snapshot(snapshot, now_s=NOW + 60)
    assert meta["schema_major"] == 1
    with open_outcome_snapshot(snapshot, now_s=NOW + 60) as (_meta, connection):
        assert connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO outcomes VALUES ('no-write')")

    data = bytearray(snapshot.read_bytes())
    data[-1] ^= 1
    snapshot.write_bytes(data)
    with pytest.raises(AtlasChecksumError):
        verify_outcome_snapshot(snapshot, now_s=NOW + 60)


def test_outcome_snapshot_rejects_unknown_major_and_stale_data(tmp_path: Path) -> None:
    snapshot = tmp_path / "outcomes.db"
    _write_snapshot(snapshot, generated_at_s=NOW - 1000)
    with pytest.raises(AtlasStaleError):
        verify_outcome_snapshot(snapshot, now_s=NOW, max_age_s=60)

    snapshot = tmp_path / "future.db"
    _write_snapshot(snapshot, schema_major=2)
    with pytest.raises(AtlasVersionError):
        verify_outcome_snapshot(snapshot, now_s=NOW)


def test_atlas_mirror_is_a_private_shep_cache(tmp_path: Path) -> None:
    path = tmp_path / "proposals.json"
    _write_proposals(path, tmp_path)
    read = read_atlas_proposals(path, now_s=NOW)
    mirror = build_atlas_mirror(
        read,
        [{"schema": "atlas-handoff/v1", "proposal_id": "fj-abc123"}],
        captured_at="2026-08-06T12:02:00Z",
    )
    destination = tmp_path / "mirror.json"
    write_atlas_mirror(destination, mirror)

    assert json.loads(destination.read_text(encoding="utf-8"))["schema"] == "shep-atlas-mirror/v1"
    assert destination.stat().st_mode & 0o777 == 0o600
