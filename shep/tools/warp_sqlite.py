"""Fail-closed, read-only observation of Warp-native terminal transcripts.

Warp does not provide Shep with a supported capture or control API.  This
module is consequently an optional observation boundary only.  A sidecar can
correlate a live process with Warp's opaque pane identifier; when no sidecar is
present, a unique active-pane cwd match may identify the same pane.  A SQLite
reader can then corroborate that identity and expose a bounded, sanitized
transcript.  There is intentionally no send, nudge, attach, or close operation
here.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import re
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import quote


SCHEMA_VERSION = 1
SIDECAR_SCHEMA = "shep-warp-sidecar/v1"
# Sidecar data is operator metadata, not a transcript. Keep the parser small
# enough that a hostile or accidentally redirected file cannot become a TUI
# memory/latency event.
MAX_SIDECAR_BYTES = 4_096
MAX_BLOCK_ROWS = 500
MAX_BLOCK_BYTES = 16_384
MAX_TRANSCRIPT_CHARS = 200_000
DEFAULT_MAX_AGE_S = 15 * 60
MAX_CLOCK_SKEW_S = 60
SQLITE_TIMEOUT_S = 0.25

_REQUIRED_COLUMNS = {
    "terminal_panes": ("uuid", "cwd"),
    "blocks": (
        "pane_leaf_uuid",
        "stylized_command",
        "stylized_output",
        "pwd",
        "exit_code",
        "did_execute",
        "completed_ts",
        "start_ts",
    ),
}
_ANSI_RE = re.compile(r"(?:\x1b\][^\x07]*(?:\x07|\x1b\\))|(?:\x1b\[[0-?]*[ -/]*[@-~])")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SECRET_RE = re.compile(
    r"(?i)(\b(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|password|secret|token)\b\s*[:=]\s*)[^\s,;]+"
)
_BEARER_RE = re.compile(r"(?i)(\bbearer\s+)[^\s,;]+")


class WarpAdapterError(RuntimeError):
    """A local Warp observation input is unsafe or outside its contract."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class WarpConfig:
    """Configuration for the optional Warp transcript adapter."""

    enabled: bool = False
    db_path: Path | str | None = None
    sidecar_path: Path | str | None = None
    expected_schema_fingerprint: str | None = None
    expected_user_version: int = 0
    max_rows: int = 50
    max_transcript_chars: int = 4_000
    max_age_s: float = DEFAULT_MAX_AGE_S
    now_s: float | None = None
    # Unique active terminal_panes.cwd may identify a pane without a sidecar.
    # Ambiguous cwds stay unresolved rather than guessing.
    allow_cwd_correlation: bool = False


@dataclass(frozen=True)
class WarpProcess:
    """The minimum process-scan row needed for sidecar correlation."""

    pid: int
    cwd: str | None = None
    tty: str | None = None
    started_at_s: float | None = None
    alive: bool = True


@dataclass(frozen=True)
class WarpObservation:
    """One read-only observation row returned by :func:`observe_warp`."""

    pid: int
    status: str
    session_uuid: str | None = None
    cwd: str | None = None
    transcript: str = ""
    transcript_truncated: bool = False
    reason: str | None = None
    read_only: bool = True
    control_allowed: bool = False
    custom_title: str | None = None
    correlation: str | None = None

    @property
    def terminal_session_uuid(self) -> str | None:
        """Compatibility name used by the process-row contract."""

        return self.session_uuid

    def as_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "status": self.status,
            "session_uuid": self.session_uuid,
            "terminal_session_uuid": self.session_uuid,
            "cwd": self.cwd,
            "transcript": self.transcript,
            "transcript_truncated": self.transcript_truncated,
            "read_only": self.read_only,
            "control_allowed": self.control_allowed,
            "reason": self.reason,
            "custom_title": self.custom_title,
            "correlation": self.correlation,
        }


@dataclass(frozen=True)
class WarpAdapterResult:
    """Compatibility envelope for callers that use ``WarpSQLiteAdapter``."""

    rows: tuple[dict[str, Any], ...]
    degraded: bool = False
    reason: str | None = None


WarpSQLiteConfig = WarpConfig


def _safe_regular_path(value: Path | str, *, kind: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or "\x00" in str(path):
        raise WarpAdapterError(f"unsafe_{kind}_path")
    try:
        if not path.exists():
            raise WarpAdapterError(f"{kind}_missing")
        if (
            path.is_symlink()
            or not path.is_file()
            or not stat.S_ISREG(path.stat().st_mode)
        ):
            raise WarpAdapterError(f"unsafe_{kind}_path")
        if path.resolve(strict=True) != path:
            raise WarpAdapterError(f"unsafe_{kind}_path")
    except OSError as exc:
        raise WarpAdapterError(f"unsafe_{kind}_path") from exc
    return path


@contextlib.contextmanager
def open_warp_database(path: Path | str) -> Iterator[sqlite3.Connection]:
    """Open a Warp database in SQLite URI read-only plus ``query_only`` mode."""

    safe_path = _safe_regular_path(path, kind="database")
    uri = f"file:{quote(safe_path.as_posix(), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=SQLITE_TIMEOUT_S)
    try:
        connection.execute("PRAGMA query_only = 1")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise WarpAdapterError("query_only_not_enabled")
        yield connection
    finally:
        connection.close()


def _schema_description(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    description: list[dict[str, Any]] = []
    for table, required in _REQUIRED_COLUMNS.items():
        columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        if not columns:
            raise WarpAdapterError("required_schema_missing")
        actual = {str(row[1]): row for row in columns}
        if any(column not in actual for column in required):
            raise WarpAdapterError("required_schema_missing")
        description.append(
            {
                "table": table,
                "columns": [
                    [str(row[1]), str(row[2]), int(row[3]), int(row[5])]
                    for row in columns
                ],
            }
        )
    return description


def _fingerprint_connection(connection: sqlite3.Connection) -> str:
    value = {
        "schema_version": SCHEMA_VERSION,
        "tables": _schema_description(connection),
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def schema_fingerprint(path: Path | str) -> str:
    """Return the fingerprint used by the opt-in schema gate."""

    with open_warp_database(path) as connection:
        return _fingerprint_connection(connection)


def _unobserved(process: WarpProcess, reason: str) -> WarpObservation:
    return WarpObservation(pid=process.pid, status="unobserved", reason=reason)


def _coerce_process(value: WarpProcess | dict[str, Any]) -> WarpProcess | None:
    if isinstance(value, WarpProcess):
        return value
    if not isinstance(value, dict):
        return None
    pid = value.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        return None
    started = value.get("started_at_s")
    if started is not None and not isinstance(started, (int, float)):
        started = None
    return WarpProcess(
        pid=pid,
        cwd=value.get("cwd") if isinstance(value.get("cwd"), str) else None,
        tty=value.get("tty") if isinstance(value.get("tty"), str) else None,
        started_at_s=float(started) if started is not None else None,
        alive=value.get("alive", True) is not False,
    )


def _opaque_id(value: object) -> bytes:
    if not isinstance(value, str):
        raise WarpAdapterError("malformed_sidecar")
    compact = value.replace("-", "").strip().lower()
    if (
        not compact
        or len(compact) > 256
        or len(compact) % 2
        or not re.fullmatch(r"[0-9a-f]+", compact)
    ):
        raise WarpAdapterError("malformed_sidecar")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise WarpAdapterError("malformed_sidecar") from exc


def _read_sidecar(
    path_value: Path | str | None, *, now_s: float, max_age_s: float
) -> tuple[dict[int, tuple[bytes, float | None, str | None, str | None]], str | None]:
    if path_value is None:
        return {}, None
    try:
        path = _safe_regular_path(path_value, kind="sidecar")
        if path.stat().st_size > MAX_SIDECAR_BYTES:
            return {}, "sidecar_too_large"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except WarpAdapterError as exc:
        return {}, exc.reason
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return {}, "sidecar_unreadable"

    if not isinstance(payload, dict) or payload.get("schema") != SIDECAR_SCHEMA:
        return {}, "unsupported_sidecar_schema"
    captured = payload.get("captured_at_s")
    sessions = payload.get("sessions")
    if (
        not isinstance(captured, (int, float))
        or isinstance(captured, bool)
        or not isinstance(sessions, list)
    ):
        return {}, "malformed_sidecar"
    age = now_s - float(captured)
    if age > max_age_s or age < -MAX_CLOCK_SKEW_S:
        return {}, "stale_sidecar"

    identities: dict[int, tuple[bytes, float | None, str | None, str | None]] = {}
    for entry in sessions:
        if not isinstance(entry, dict):
            return {}, "malformed_sidecar"
        pid = entry.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return {}, "malformed_sidecar"
        raw_id = entry.get(
            "session_uuid_hex",
            entry.get("session_uuid", entry.get("terminal_session_uuid")),
        )
        try:
            opaque_id = _opaque_id(raw_id)
        except WarpAdapterError as exc:
            return {}, exc.reason
        started = entry.get("started_at_s")
        if started is not None and (
            not isinstance(started, (int, float)) or isinstance(started, bool)
        ):
            return {}, "malformed_sidecar"
        cwd = entry.get("cwd")
        tty = entry.get("tty")
        if cwd is not None and not isinstance(cwd, str):
            return {}, "malformed_sidecar"
        if tty is not None and not isinstance(tty, str):
            return {}, "malformed_sidecar"
        if pid in identities:
            return {}, "ambiguous_sidecar_identity"
        identities[pid] = (
            opaque_id,
            float(started) if started is not None else None,
            cwd,
            tty,
        )
    return identities, None


def _timestamp_s(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
    except ValueError:
        return None
    # Warp writes naive UTC timestamps (no offset). Treating them as local
    # makes recent blocks look like they are in the future.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.timestamp()


def _safe_text(value: object) -> str:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    elif isinstance(value, str):
        text = value
    else:
        return ""
    text = _ANSI_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    text = _BEARER_RE.sub(r"\1<redacted>", text)
    return _SECRET_RE.sub(r"\1<redacted>", text)


def _read_transcript(
    connection: sqlite3.Connection,
    pane_id: bytes,
    config: WarpConfig,
    *,
    now_s: float,
) -> tuple[str, bool, str | None, str | None]:
    pane_rows = connection.execute(
        "SELECT uuid, cwd FROM terminal_panes WHERE uuid = ? LIMIT 2", (pane_id,)
    ).fetchall()
    if len(pane_rows) != 1:
        reason = (
            "missing_database_identity"
            if not pane_rows
            else "ambiguous_database_identity"
        )
        return "", False, None, reason
    stored_id, cwd = pane_rows[0]
    if (
        not isinstance(stored_id, (bytes, bytearray, memoryview))
        or bytes(stored_id) != pane_id
    ):
        return "", False, None, "opaque_id_mismatch"

    max_rows = min(max(int(config.max_rows), 1), MAX_BLOCK_ROWS)
    block_rows = connection.execute(
        """
        SELECT substr(stylized_command, 1, ?),
               substr(stylized_output, 1, ?),
               completed_ts,
               start_ts
        FROM blocks
        WHERE pane_leaf_uuid = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (MAX_BLOCK_BYTES, MAX_BLOCK_BYTES, pane_id, max_rows),
    ).fetchall()
    if not block_rows:
        return "", False, None, "transcript_missing"
    latest = next(
        (
            timestamp
            for row in block_rows
            for timestamp in (_timestamp_s(row[2]), _timestamp_s(row[3]))
            if timestamp is not None
        ),
        None,
    )
    if latest is None:
        return "", False, None, "transcript_timestamp_missing"
    age = now_s - latest
    if age > float(config.max_age_s):
        return "", False, None, "stale_transcript"
    if age < -MAX_CLOCK_SKEW_S:
        return "", False, None, "future_transcript"

    chunks: list[str] = []
    for row in reversed(block_rows):
        command = _safe_text(row[0]).strip()
        output = _safe_text(row[1]).strip("\n")
        if command:
            chunks.append(command)
        if output:
            chunks.append(output)
    transcript = "\n".join(chunks)
    limit = min(max(int(config.max_transcript_chars), 1), MAX_TRANSCRIPT_CHARS)
    truncated = len(transcript) > limit
    return transcript[:limit], truncated, str(cwd) if cwd is not None else None, None


def _active_pane_cwd_index(
    connection: sqlite3.Connection,
) -> dict[str, list[tuple[bytes, str | None]]]:
    """Map cwd -> [(pane_uuid, custom_title), ...] for active terminal panes."""

    pane_columns = {
        str(row[1]) for row in connection.execute('PRAGMA table_info("terminal_panes")')
    }
    active_filter = "is_active = 1 AND " if "is_active" in pane_columns else ""
    try:
        tp_active = (
            "tp.is_active = 1 AND " if "is_active" in pane_columns else ""
        )
        rows = connection.execute(
            f"""
            SELECT tp.uuid, tp.cwd, t.custom_title
            FROM terminal_panes tp
            LEFT JOIN pane_nodes pn ON pn.id = tp.id
            LEFT JOIN tabs t ON t.id = pn.tab_id
            WHERE {tp_active}tp.cwd IS NOT NULL AND tp.cwd != ''
            """
        ).fetchall()
    except sqlite3.Error:
        rows = connection.execute(
            f"""
            SELECT uuid, cwd, NULL
            FROM terminal_panes
            WHERE {active_filter}cwd IS NOT NULL AND cwd != ''
            """
        ).fetchall()

    index: dict[str, list[tuple[bytes, str | None]]] = {}
    for raw_id, cwd, title in rows:
        if not isinstance(raw_id, (bytes, bytearray, memoryview)):
            continue
        if not isinstance(cwd, str) or not cwd:
            continue
        custom = title.strip() if isinstance(title, str) and title.strip() else None
        index.setdefault(cwd, []).append((bytes(raw_id), custom))
    return index


def _lookup_custom_title(
    connection: sqlite3.Connection, pane_id: bytes
) -> str | None:
    try:
        row = connection.execute(
            """
            SELECT t.custom_title
            FROM terminal_panes tp
            LEFT JOIN pane_nodes pn ON pn.id = tp.id
            LEFT JOIN tabs t ON t.id = pn.tab_id
            WHERE tp.uuid = ?
            LIMIT 1
            """,
            (pane_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if row and isinstance(row[0], str) and row[0].strip():
        return row[0].strip()
    return None


def _apply_cwd_correlation(
    base: list[WarpObservation],
    processes: list[WarpProcess],
    connection: sqlite3.Connection,
) -> list[WarpObservation]:
    """Promote unobserved rows whose cwd uniquely matches one active pane."""

    by_pid = {process.pid: process for process in processes}
    cwd_counts: dict[str, int] = {}
    for process in processes:
        if process.cwd:
            cwd_counts[process.cwd] = cwd_counts.get(process.cwd, 0) + 1
    panes_by_cwd = _active_pane_cwd_index(connection)

    enriched: list[WarpObservation] = []
    for row in base:
        if row.status == "identified" and row.session_uuid:
            enriched.append(
                row
                if row.correlation
                else WarpObservation(
                    pid=row.pid,
                    status=row.status,
                    session_uuid=row.session_uuid,
                    cwd=row.cwd,
                    transcript=row.transcript,
                    transcript_truncated=row.transcript_truncated,
                    reason=row.reason,
                    custom_title=row.custom_title,
                    correlation="sidecar",
                )
            )
            continue
        process = by_pid.get(row.pid)
        if process is None or not process.cwd:
            enriched.append(row)
            continue
        if cwd_counts.get(process.cwd, 0) != 1:
            enriched.append(
                _unobserved(process, "ambiguous_cwd")
                if cwd_counts.get(process.cwd, 0) > 1
                else row
            )
            continue
        matches = panes_by_cwd.get(process.cwd, [])
        if not matches:
            enriched.append(row)
            continue
        if len(matches) != 1:
            enriched.append(_unobserved(process, "ambiguous_cwd"))
            continue
        pane_id, custom_title = matches[0]
        enriched.append(
            WarpObservation(
                pid=process.pid,
                status="identified",
                session_uuid=pane_id.hex(),
                cwd=process.cwd,
                custom_title=custom_title,
                correlation="cwd",
            )
        )
    return enriched


def _database_reason(exc: BaseException) -> str:
    message = str(exc).lower()
    if "locked" in message or "busy" in message:
        return "database_locked"
    if isinstance(exc, WarpAdapterError):
        return exc.reason
    return "database_unreadable"


def observe_warp(
    processes: Sequence[WarpProcess | dict[str, Any]], config: WarpConfig | None = None
) -> tuple[WarpObservation, ...]:
    """Observe live Warp processes, degrading every unsafe case safely."""

    config = config or WarpConfig()
    now_s = (
        float(config.now_s)
        if config.now_s is not None
        else dt.datetime.now(dt.timezone.utc).timestamp()
    )
    live = [_coerce_process(value) for value in processes]
    valid = [process for process in live if process is not None]
    duplicate_pids = {
        process.pid
        for process in valid
        if sum(item.pid == process.pid for item in valid) > 1
    }
    identities, sidecar_reason = _read_sidecar(
        config.sidecar_path, now_s=now_s, max_age_s=float(config.max_age_s)
    )

    base: list[WarpObservation] = []
    for process in valid:
        if process.pid <= 0:
            base.append(_unobserved(process, "invalid_process"))
        elif process.pid in duplicate_pids:
            base.append(_unobserved(process, "ambiguous_live_process"))
        elif not process.alive:
            base.append(_unobserved(process, "process_not_live"))
        elif sidecar_reason:
            base.append(_unobserved(process, sidecar_reason))
        elif process.pid not in identities:
            base.append(_unobserved(process, "no_sidecar_identity"))
        else:
            opaque_id, started_at_s, sidecar_cwd, sidecar_tty = identities[process.pid]
            if (
                started_at_s is not None
                and process.started_at_s is not None
                and abs(started_at_s - process.started_at_s) > 1
            ):
                base.append(_unobserved(process, "sidecar_pid_reuse"))
            elif sidecar_cwd and process.cwd and sidecar_cwd != process.cwd:
                base.append(_unobserved(process, "sidecar_cwd_mismatch"))
            elif sidecar_tty and process.tty and sidecar_tty != process.tty:
                base.append(_unobserved(process, "sidecar_tty_mismatch"))
            else:
                base.append(
                    WarpObservation(
                        pid=process.pid,
                        status="identified",
                        session_uuid=opaque_id.hex(),
                        cwd=process.cwd,
                        correlation="sidecar",
                    )
                )

    if not config.enabled:
        if config.sidecar_path is None and not config.allow_cwd_correlation:
            return tuple(_unobserved(process, "adapter_disabled") for process in valid)
        return tuple(base)

    if config.db_path is None:
        return tuple(
            row
            if row.status != "identified"
            else _unobserved(WarpProcess(row.pid), "database_path_missing")
            for row in base
        )
    if (
        config.expected_schema_fingerprint is None
        and not config.allow_cwd_correlation
    ):
        return tuple(
            row
            if row.status != "identified"
            else _unobserved(WarpProcess(row.pid), "schema_fingerprint_required")
            for row in base
        )

    try:
        with open_warp_database(config.db_path) as connection:
            actual_version = int(
                connection.execute("PRAGMA user_version").fetchone()[0]
            )
            if actual_version != int(config.expected_user_version):
                raise WarpAdapterError("unsupported_schema_version")
            _schema_description(connection)
            if config.expected_schema_fingerprint is not None and (
                _fingerprint_connection(connection)
                != config.expected_schema_fingerprint
            ):
                raise WarpAdapterError("schema_fingerprint_mismatch")

            working = base
            if config.allow_cwd_correlation:
                working = _apply_cwd_correlation(working, valid, connection)

            enriched: list[WarpObservation] = []
            for row in working:
                if row.status != "identified" or row.session_uuid is None:
                    enriched.append(row)
                    continue
                pane_id = bytes.fromhex(row.session_uuid)
                custom_title = row.custom_title or _lookup_custom_title(
                    connection, pane_id
                )
                transcript, truncated, cwd, reason = _read_transcript(
                    connection,
                    pane_id,
                    config,
                    now_s=now_s,
                )
                correlation = row.correlation or "sidecar"
                if reason:
                    enriched.append(
                        WarpObservation(
                            pid=row.pid,
                            status="unobserved",
                            session_uuid=row.session_uuid,
                            cwd=row.cwd,
                            custom_title=custom_title,
                            correlation=correlation,
                            reason=reason,
                        )
                    )
                else:
                    enriched.append(
                        WarpObservation(
                            pid=row.pid,
                            status="transcript-ro",
                            session_uuid=row.session_uuid,
                            cwd=cwd or row.cwd,
                            transcript=transcript,
                            transcript_truncated=truncated,
                            custom_title=custom_title,
                            correlation=correlation,
                        )
                    )
            return tuple(enriched)
    except (OSError, sqlite3.Error, WarpAdapterError) as exc:
        reason = _database_reason(exc)
        return tuple(
            row
            if row.status != "identified"
            else _unobserved(WarpProcess(row.pid), reason)
            for row in base
        )


class WarpSQLiteAdapter:
    """Compatibility wrapper around :func:`observe_warp`; observation only."""

    def __init__(self, config: WarpConfig | None = None) -> None:
        self.config = config or WarpConfig()

    def observe(
        self,
        processes: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        now: float | None = None,
    ) -> WarpAdapterResult:
        values = {
            **self.config.__dict__,
            **({"now_s": now} if now is not None else {}),
        }
        rows = observe_warp(processes, WarpConfig(**values))
        return WarpAdapterResult(
            rows=tuple(row.as_dict() for row in rows),
            degraded=any(row.status == "unobserved" for row in rows),
            reason=next((row.reason for row in rows if row.reason), None),
        )
