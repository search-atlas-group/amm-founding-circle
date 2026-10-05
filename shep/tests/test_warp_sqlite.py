from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tools.warp_sqlite import (
    SCHEMA_VERSION,
    WarpConfig,
    WarpProcess,
    open_warp_database,
    observe_warp,
    schema_fingerprint,
)


NOW = 1_787_788_800.0


def _write_sidecar(
    path: Path, records: list[dict], *, captured_at_s: float = NOW
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "shep-warp-sidecar/v1",
                "captured_at_s": captured_at_s,
                "sessions": records,
            }
        ),
        encoding="utf-8",
    )


def _create_warp_db(path: Path, *, user_version: int = 0) -> bytes:
    pane_id = bytes.fromhex("00112233445566778899aabbccddeeff")
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE terminal_panes (
            id INTEGER PRIMARY KEY NOT NULL,
            uuid BLOB NOT NULL UNIQUE,
            cwd TEXT,
            is_active BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE TABLE blocks (
            id INTEGER PRIMARY KEY,
            pane_leaf_uuid BLOB NOT NULL,
            stylized_command BLOB NOT NULL,
            stylized_output BLOB NOT NULL,
            pwd TEXT,
            exit_code INTEGER NOT NULL,
            did_execute BOOLEAN NOT NULL,
            completed_ts DATETIME,
            start_ts DATETIME
        );
        """
    )
    connection.execute(f"PRAGMA user_version = {int(user_version)}")
    connection.execute(
        "INSERT INTO terminal_panes (uuid, cwd) VALUES (?, ?)",
        (pane_id, "/tmp/warp-repo"),
    )
    connection.execute(
        """
        INSERT INTO blocks (
            pane_leaf_uuid, stylized_command, stylized_output, pwd,
            exit_code, did_execute, completed_ts, start_ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pane_id,
            b"printf 'token=secret-value\\n'",
            b"\x1b[31mhello\x1b[0m\x00\nBearer abc.def.ghi\n",
            "/tmp/warp-repo",
            0,
            True,
            "2026-08-27T00:00:00+00:00",
            "2026-08-27T00:00:00+00:00",
        ),
    )
    connection.commit()
    connection.close()
    return pane_id


def _config(db: Path, sidecar: Path, **overrides: object) -> WarpConfig:
    expected_fingerprint = overrides.pop("expected_schema_fingerprint", None)
    values = {
        "enabled": True,
        "db_path": db,
        "sidecar_path": sidecar,
        "expected_schema_fingerprint": (
            schema_fingerprint(db)
            if expected_fingerprint is None
            else expected_fingerprint
        ),
        "expected_user_version": 0,
        "now_s": NOW,
    }
    values.update(overrides)
    return WarpConfig(**values)


def test_default_config_never_opens_warp_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("default observation opened Warp SQLite")

    monkeypatch.setattr(sqlite3, "connect", fail_if_opened)

    result = observe_warp([WarpProcess(pid=41)])

    assert result[0].status == "unobserved"
    assert result[0].reason == "adapter_disabled"


def test_fresh_unambiguous_sidecar_promotes_live_process_to_identified(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar, [{"pid": 41, "session_uuid": "00112233-4455-6677-8899-aabbccddeeff"}]
    )

    result = observe_warp(
        [WarpProcess(pid=41, cwd="/tmp/warp-repo")],
        WarpConfig(sidecar_path=sidecar, now_s=NOW),
    )

    assert result[0].status == "identified"
    assert result[0].session_uuid == "00112233445566778899aabbccddeeff"
    assert result[0].read_only is True


def test_sidecar_pid_reuse_and_duplicate_identity_degrade_to_unobserved(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar,
        [
            {
                "pid": 41,
                "session_uuid": "00112233-4455-6677-8899-aabbccddeeff",
                "started_at_s": 10,
            },
            {
                "pid": 41,
                "session_uuid": "ffeeddcc-bbaa-9988-7766-554433221100",
                "started_at_s": 10,
            },
        ],
    )

    result = observe_warp(
        [WarpProcess(pid=41, started_at_s=10)],
        WarpConfig(sidecar_path=sidecar, now_s=NOW),
    )

    assert result[0].status == "unobserved"
    assert result[0].reason == "ambiguous_sidecar_identity"


def test_stale_sidecar_identity_degrades_to_unobserved(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar, [{"pid": 41, "session_uuid": "0011223344556677"}], captured_at_s=0
    )

    result = observe_warp(
        [WarpProcess(pid=41)], WarpConfig(sidecar_path=sidecar, now_s=NOW, max_age_s=60)
    )

    assert result[0].status == "unobserved"
    assert result[0].reason == "stale_sidecar"


def test_sidecar_cwd_mismatch_cannot_promote_a_reused_pid(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar,
        [
            {
                "pid": 41,
                "session_uuid": "0011223344556677",
                "cwd": "/old/worktree",
            }
        ],
    )

    result = observe_warp(
        [WarpProcess(pid=41, cwd="/new/worktree")],
        WarpConfig(sidecar_path=sidecar, now_s=NOW),
    )

    assert result[0].status == "unobserved"
    assert result[0].reason == "sidecar_cwd_mismatch"


def test_opt_in_db_requires_query_only_and_rejects_writes(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db)
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid": pane_id.hex()}])

    result = observe_warp([WarpProcess(pid=41)], _config(db, sidecar))

    assert result[0].status == "transcript-ro"
    assert result[0].read_only is True
    assert "Bearer <redacted>" in result[0].transcript
    assert "hello" in result[0].transcript
    assert "printf" in result[0].transcript
    with open_warp_database(db) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE should_not_exist (id INTEGER)")


def test_schema_fingerprint_and_version_gate_fail_closed(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db, user_version=9)
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid": pane_id.hex()}])

    wrong_fingerprint = _config(
        db,
        sidecar,
        expected_schema_fingerprint="sha256:wrong",
        expected_user_version=9,
    )
    wrong_version = _config(db, sidecar, expected_user_version=0)

    assert (
        observe_warp([WarpProcess(pid=41)], wrong_fingerprint)[0].reason
        == "schema_fingerprint_mismatch"
    )
    assert (
        observe_warp([WarpProcess(pid=41)], wrong_version)[0].reason
        == "unsupported_schema_version"
    )


def test_reads_are_bounded_and_transcript_is_sanitized_and_truncated(
    tmp_path: Path,
) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db)
    connection = sqlite3.connect(db)
    for index in range(20):
        connection.execute(
            "INSERT INTO blocks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                index + 2,
                pane_id,
                b"echo x",
                b"x" * 100,
                "/tmp",
                0,
                True,
                "2026-08-27T00:00:00+00:00",
                None,
            ),
        )
    connection.commit()
    connection.close()
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid": pane_id.hex()}])

    result = observe_warp(
        [WarpProcess(pid=41)],
        _config(db, sidecar, max_rows=3, max_transcript_chars=27),
    )

    assert result[0].status == "transcript-ro"
    assert len(result[0].transcript) <= 27
    assert result[0].transcript_truncated is True
    assert "\\x1b" not in result[0].transcript


def test_opaque_non_utf8_blob_id_is_joined_without_decoding(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    _create_warp_db(db)
    connection = sqlite3.connect(db)
    connection.execute("UPDATE terminal_panes SET uuid = ?", (b"\xff\x00opaque-id",))
    connection.execute("UPDATE blocks SET pane_leaf_uuid = ?", (b"\xff\x00opaque-id",))
    connection.commit()
    connection.close()
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid_hex": "ff006f70617175652d6964"}])

    result = observe_warp([WarpProcess(pid=41)], _config(db, sidecar))

    assert result[0].status == "transcript-ro"
    assert result[0].session_uuid == "ff006f70617175652d6964"


def test_sidecar_identity_must_be_corroborated_by_the_database(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    _create_warp_db(db)
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid": "ffeeddccbbaa9988"}])

    result = observe_warp([WarpProcess(pid=41)], _config(db, sidecar))

    assert result[0].status == "unobserved"
    assert result[0].reason == "missing_database_identity"


@pytest.mark.parametrize("kind", ["missing", "corrupt", "locked"])
def test_missing_corrupt_or_locked_database_degrades_safely(
    tmp_path: Path, kind: str
) -> None:
    db = tmp_path / "warp.sqlite"
    expected_fingerprint = "sha256:fixture"
    if kind == "corrupt":
        db.write_bytes(b"not a sqlite database")
    elif kind == "locked":
        _create_warp_db(db)
        expected_fingerprint = schema_fingerprint(db)
        lock = sqlite3.connect(db)
        lock.execute("BEGIN EXCLUSIVE")
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar, [{"pid": 41, "session_uuid": "00112233445566778899aabbccddeeff"}]
    )

    try:
        result = observe_warp(
            [WarpProcess(pid=41)],
            _config(db, sidecar, expected_schema_fingerprint=expected_fingerprint),
        )
    finally:
        if kind == "locked":
            lock.rollback()
            lock.close()

    assert result[0].status == "unobserved"
    assert result[0].reason in {
        "database_missing",
        "database_unreadable",
        "database_locked",
    }


def test_stale_db_identity_cannot_be_promoted(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db)
    connection = sqlite3.connect(db)
    connection.execute(
        "UPDATE blocks SET completed_ts = ?", ("2020-01-01T00:00:00+00:00",)
    )
    connection.commit()
    connection.close()
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid": pane_id.hex()}])

    result = observe_warp([WarpProcess(pid=41)], _config(db, sidecar, max_age_s=60))

    assert result[0].status == "unobserved"
    assert result[0].reason == "stale_transcript"


def test_duplicate_live_process_rows_are_ambiguous(tmp_path: Path) -> None:
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar, [{"pid": 41, "session_uuid": "00112233445566778899aabbccddeeff"}]
    )

    result = observe_warp(
        [WarpProcess(pid=41), WarpProcess(pid=41)],
        WarpConfig(sidecar_path=sidecar, now_s=NOW),
    )

    assert [row.status for row in result] == ["unobserved", "unobserved"]
    assert {row.reason for row in result} == {"ambiguous_live_process"}


def test_symlink_and_relative_paths_are_rejected_without_opening_target(
    tmp_path: Path,
) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db)
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(sidecar, [{"pid": 41, "session_uuid": pane_id.hex()}])
    db_link = tmp_path / "warp-link.sqlite"
    db_link.symlink_to(db)

    expected_fingerprint = schema_fingerprint(db)
    linked = observe_warp(
        [WarpProcess(pid=41)],
        _config(db_link, sidecar, expected_schema_fingerprint=expected_fingerprint),
    )
    relative = observe_warp(
        [WarpProcess(pid=41)],
        _config(
            Path("warp.sqlite"),
            sidecar,
            expected_schema_fingerprint=expected_fingerprint,
        ),
    )

    assert linked[0].status == relative[0].status == "unobserved"
    assert linked[0].reason == "unsafe_database_path"
    assert relative[0].reason == "unsafe_database_path"


def test_sidecar_path_is_size_limited_and_symlinks_are_not_followed(
    tmp_path: Path,
) -> None:
    target = tmp_path / "real-sidecar.json"
    target.write_text("x" * 2_000_000, encoding="utf-8")
    link = tmp_path / "sidecar.json"
    link.symlink_to(target)

    result = observe_warp(
        [WarpProcess(pid=41)],
        WarpConfig(sidecar_path=link, now_s=NOW),
    )

    assert result[0].status == "unobserved"
    assert result[0].reason == "unsafe_sidecar_path"


def test_schema_version_constant_is_public_and_stable() -> None:
    assert SCHEMA_VERSION == 1



def test_unique_cwd_correlates_without_sidecar(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db)
    connection = __import__("sqlite3").connect(db)
    # Fixture schema may omit is_active; add and mark active when possible.
    cols = {row[1] for row in connection.execute("PRAGMA table_info(terminal_panes)")}
    if "is_active" not in cols:
        connection.execute(
            "ALTER TABLE terminal_panes ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
        )
    else:
        connection.execute("UPDATE terminal_panes SET is_active = 1")
    connection.commit()
    connection.close()

    result = observe_warp(
        [WarpProcess(pid=41, cwd="/tmp/warp-repo")],
        WarpConfig(
            enabled=True,
            db_path=db,
            allow_cwd_correlation=True,
            now_s=NOW,
            max_age_s=10**9,
        ),
    )

    assert result[0].status == "transcript-ro"
    assert result[0].correlation == "cwd"
    assert result[0].session_uuid == pane_id.hex()
    assert result[0].read_only is True


def test_ambiguous_cwd_does_not_guess_a_pane(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    _create_warp_db(db)
    connection = __import__("sqlite3").connect(db)
    cols = {row[1] for row in connection.execute("PRAGMA table_info(terminal_panes)")}
    if "is_active" not in cols:
        connection.execute(
            "ALTER TABLE terminal_panes ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
        )
    connection.execute(
        "INSERT INTO terminal_panes (uuid, cwd, is_active) VALUES (?, ?, 1)",
        (bytes.fromhex("ffeeddccbbaa99887766554433221100"), "/tmp/warp-repo"),
    )
    connection.commit()
    connection.close()

    result = observe_warp(
        [
            WarpProcess(pid=41, cwd="/tmp/warp-repo"),
            WarpProcess(pid=42, cwd="/tmp/warp-repo"),
        ],
        WarpConfig(
            enabled=True,
            db_path=db,
            allow_cwd_correlation=True,
            now_s=NOW,
            max_age_s=10**9,
        ),
    )

    assert all(row.status == "unobserved" for row in result)
    assert {row.reason for row in result} == {"ambiguous_cwd"}


def test_naive_block_timestamps_are_treated_as_utc(tmp_path: Path) -> None:
    db = tmp_path / "warp.sqlite"
    pane_id = _create_warp_db(db)
    connection = __import__("sqlite3").connect(db)
    # Warp stores UTC without an offset. A local parse would reject this as future.
    connection.execute(
        "UPDATE blocks SET completed_ts = ?, start_ts = ?",
        ("2026-09-28 03:38:25.728681", "2026-09-28 03:38:25.728681"),
    )
    connection.commit()
    connection.close()
    sidecar = tmp_path / "sidecar.json"
    _write_sidecar(
        sidecar,
        [{"pid": 41, "session_uuid": pane_id.hex()}],
        captured_at_s=1790568505.728681,
    )

    # Naive Warp timestamps are UTC. A local parse would mark this future.
    result = observe_warp(
        [WarpProcess(pid=41)],
        _config(db, sidecar, now_s=1790568505.728681, max_age_s=7200),
    )
    assert result[0].status == "transcript-ro"
    assert result[0].reason is None
