"""Read-only Atlas contracts consumed by Shep Phase 2.

Atlas owns the proposal and outcome stores.  Shep may verify and cache their
published read contracts, but it never writes to Atlas's source files or
outcome database.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import quote


PROPOSALS_VERSION = "atlas-fleet-proposals/v3"
PROPOSALS_MAX_AGE_S = 2 * 60 * 60
OUTCOME_SCHEMA_MAJOR = 1
OUTCOME_META_KEYS = (
    "schema_major",
    "schema_minor",
    "generated_at_s",
    "ledger_seq",
    "source_commit",
    "freshness_sla_s",
)
HANDOFF_SCHEMA = "atlas-handoff/v1"
MIRROR_SCHEMA = "shep-atlas-mirror/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AtlasContractError(RuntimeError):
    """Atlas data is missing, malformed, stale, or not safe to consume."""


class AtlasVersionError(AtlasContractError):
    """The published Atlas schema major is not understood."""


class AtlasStaleError(AtlasContractError):
    """The published Atlas data is older than its freshness contract."""


class AtlasChecksumError(AtlasContractError):
    """Published Atlas bytes do not match their checksum sidecar."""


def _now_s(value: float | None = None) -> float:
    return dt.datetime.now(dt.timezone.utc).timestamp() if value is None else float(value)


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AtlasContractError(f"Atlas contract is unreadable: {exc}") from exc


def _canonical_dir(value: object) -> Path | None:
    if not isinstance(value, str) or not value or not os.path.isabs(value):
        return None
    path = Path(value).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    return resolved if resolved.is_dir() else None


def _proposal_target(proposal: dict) -> Path | None:
    project = _canonical_dir(proposal.get("project_path"))
    cwd = _canonical_dir(proposal.get("cwd"))
    routing = proposal.get("routing")
    if project is None or cwd is None or project != cwd:
        return None
    if not isinstance(routing, dict) or routing.get("status") != "resolved":
        return None
    checks = proposal.get("acceptance_checks")
    if not isinstance(checks, list) or not checks:
        return None
    kind = proposal.get("work_kind")
    required_kind = "git_worktree_clean" if kind == "build" else "fleet_report_v1"
    for check in checks:
        if not isinstance(check, dict) or check.get("kind") != required_kind:
            continue
        check_path = check.get("path") if required_kind == "git_worktree_clean" else check.get("expected_root")
        if _canonical_dir(check_path) == cwd:
            return cwd
    return None


def _valid_proposal(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_strings = (
        "id",
        "source",
        "work_kind",
        "short_goal",
        "instruction",
        "recommendation",
        "cwd",
        "proposal_id",
        "project_name",
    )
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required_strings):
        return False
    if value.get("source") != "fleet_journey" or value.get("dispatchable") is not True:
        return False
    evidence = value.get("evidence")
    return isinstance(evidence, list) and bool(evidence) and _proposal_target(value) is not None


def _default_proposals_path() -> Path:
    explicit = os.environ.get("ATLAS_PROPOSALS_PATH")
    if explicit:
        return Path(explicit).expanduser()
    data_root = os.environ.get("GOVERNOR_DATA_DIR") or os.environ.get("ATLAS_GOVERNOR_DATA_DIR")
    if data_root:
        return Path(data_root).expanduser() / "governor/fleet-journey-proposals.json"
    return Path.home() / "Sync/searchatlas-eng/forge-repos/engineering-rnd/atlas-commander/data/governor/fleet-journey-proposals.json"


def read_atlas_proposals(
    path: str | os.PathLike[str] | None = None,
    *,
    now_s: float | None = None,
    max_age_s: float = PROPOSALS_MAX_AGE_S,
) -> dict:
    """Read v3 proposals and return a fail-closed Shep read result."""
    source = Path(path).expanduser() if path is not None else _default_proposals_path()
    if not source.is_file():
        return {
            "schema": "shep-atlas-read/v1",
            "ok": False,
            "blocked_reason": "atlas_proposals_missing",
            "proposals": [],
            "notes": ["Atlas proposal file is missing"],
        }
    try:
        value = _read_json(source)
    except AtlasContractError as exc:
        return _blocked("atlas_proposals_malformed", str(exc))
    if not isinstance(value, dict):
        return _blocked("atlas_proposals_malformed", "Atlas proposal envelope is not an object")
    if value.get("version") != PROPOSALS_VERSION:
        return _blocked("atlas_proposals_unknown_version", "Atlas proposal version is not v3")
    generated = value.get("generated_at")
    if not isinstance(generated, str):
        return _blocked("atlas_proposals_missing_timestamp", "Atlas proposal timestamp is missing")
    try:
        generated_s = dt.datetime.fromisoformat(generated.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return _blocked("atlas_proposals_invalid_timestamp", "Atlas proposal timestamp is invalid")
    age = _now_s(now_s) - generated_s
    if age > max_age_s or age < -60:
        return _blocked("atlas_proposals_stale", "Atlas proposal data is outside its freshness window")
    proposals = value.get("proposals")
    if not isinstance(proposals, list):
        return _blocked("atlas_proposals_malformed", "Atlas proposal list is missing")
    valid = [proposal for proposal in proposals if _valid_proposal(proposal)]
    dropped = len(proposals) - len(valid)
    notes = list(value.get("diagnostics") or []) if isinstance(value.get("diagnostics"), list) else []
    if dropped:
        notes.append(f"dropped {dropped} invalid Atlas proposals")
    if not valid:
        return _blocked("atlas_proposals_empty", "Atlas has no complete dispatchable proposal")
    return {
        "schema": "shep-atlas-read/v1",
        "ok": True,
        "blocked_reason": None,
        "generated_at": generated,
        "generated_at_s": generated_s,
        "proposals": valid,
        "notes": notes,
        "source_path": str(source),
    }


def _blocked(reason: str, note: str) -> dict:
    return {
        "schema": "shep-atlas-read/v1",
        "ok": False,
        "blocked_reason": reason,
        "proposals": [],
        "notes": [note],
    }


def build_atlas_handoff(
    read_result: dict,
    proposal_id: str,
    *,
    approver: str,
    approved_at: str,
) -> dict:
    """Build a digest-bound handoff from one fresh, approved v3 proposal."""
    if not read_result.get("ok"):
        raise AtlasContractError(str(read_result.get("blocked_reason") or "Atlas read is blocked"))
    if not isinstance(approver, str) or not approver.strip():
        raise ValueError("approver must be non-empty")
    proposal = next(
        (item for item in read_result.get("proposals", []) if item.get("proposal_id") == proposal_id),
        None,
    )
    if proposal is None:
        raise AtlasContractError(f"proposal is not present in the approved v3 read: {proposal_id}")
    target = _proposal_target(proposal)
    if target is None:
        raise AtlasContractError("proposal target binding is unresolved")
    try:
        dt.datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("approved_at must be an ISO-8601 timestamp") from exc
    revision = proposal.get("proposal_revision", 1)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise AtlasContractError("proposal_revision must be a positive integer")
    evidence_refs = [f"atlas://proposal/{proposal_id}"]
    analysis_ref = proposal.get("analysis_ref")
    if isinstance(analysis_ref, dict) and analysis_ref.get("schema"):
        evidence_refs.append(f"atlas://analysis/{proposal_id}")
    return {
        "schema": HANDOFF_SCHEMA,
        "proposal_id": proposal_id,
        "proposal_revision": revision,
        "proposal_digest": _canonical_digest(proposal),
        "goal": proposal["short_goal"],
        "work_kind": proposal["work_kind"],
        "dispatchable": True,
        "target_root": str(target),
        "acceptance_checks": proposal["acceptance_checks"],
        "evidence_refs": evidence_refs,
        "approver": approver.strip(),
        "approved_at": approved_at,
        "outcome_receipt_ref": None,
    }


def verify_atlas_handoff(handoff: dict, read_result: dict) -> dict:
    """Verify that a handoff still names the exact current Atlas proposal."""
    if not isinstance(handoff, dict) or handoff.get("schema") != HANDOFF_SCHEMA:
        return {"ok": False, "reason": "handoff_schema_invalid"}
    if not read_result.get("ok"):
        return {"ok": False, "reason": read_result.get("blocked_reason", "atlas_read_blocked")}
    proposal = next(
        (item for item in read_result["proposals"] if item.get("proposal_id") == handoff.get("proposal_id")),
        None,
    )
    if proposal is None:
        return {"ok": False, "reason": "proposal_missing"}
    if handoff.get("proposal_digest") != _canonical_digest(proposal):
        return {"ok": False, "reason": "proposal_changed"}
    if handoff.get("dispatchable") is not True or _proposal_target(proposal) is None:
        return {"ok": False, "reason": "proposal_not_dispatchable"}
    if handoff.get("proposal_revision", 1) != proposal.get("proposal_revision", 1):
        return {"ok": False, "reason": "proposal_revision_changed"}
    if handoff.get("target_root") != str(_proposal_target(proposal)):
        return {"ok": False, "reason": "target_changed"}
    if handoff.get("goal") != proposal.get("short_goal"):
        return {"ok": False, "reason": "goal_changed"}
    if handoff.get("work_kind") != proposal.get("work_kind"):
        return {"ok": False, "reason": "work_kind_changed"}
    if handoff.get("acceptance_checks") != proposal.get("acceptance_checks"):
        return {"ok": False, "reason": "acceptance_checks_changed"}
    return {"ok": True, "reason": None}


def _sidecar_path(snapshot: Path) -> Path:
    return Path(str(snapshot) + ".sha256.json")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(meta: dict, key: str) -> int | float:
    value = meta.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AtlasContractError(f"outcome snapshot sidecar field {key} is not numeric")
    return value


@contextlib.contextmanager
def _verified_snapshot(
    snapshot: str | os.PathLike[str], *, now_s: float | None = None, max_age_s: float | None = None
):
    """Verify and open one immutable snapshot before yielding its connection."""
    path = Path(snapshot).expanduser()
    sidecar = _sidecar_path(path)
    if not path.is_file() or not sidecar.is_file():
        raise AtlasChecksumError("Atlas outcome snapshot or checksum sidecar is missing")
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AtlasChecksumError(f"Atlas outcome snapshot sidecar is unreadable: {exc}") from exc
    if not isinstance(meta, dict) or not SHA256_RE.fullmatch(str(meta.get("sha256", ""))):
        raise AtlasChecksumError("Atlas outcome snapshot sidecar has no valid checksum")
    actual = _sha256_file(path)
    if actual != meta["sha256"]:
        raise AtlasChecksumError("Atlas outcome snapshot checksum mismatch")
    major = _number(meta, "schema_major")
    if major != OUTCOME_SCHEMA_MAJOR:
        raise AtlasVersionError(f"Atlas outcome schema major {major} is unsupported")
    for key in OUTCOME_META_KEYS:
        if key not in meta:
            raise AtlasContractError(f"Atlas outcome snapshot sidecar is missing {key}")
    _number(meta, "schema_minor")
    _number(meta, "ledger_seq")
    if not isinstance(meta.get("source_commit"), str):
        raise AtlasContractError("Atlas outcome snapshot source_commit is not a string")
    row_count_meta = _number(meta, "row_count")
    freshness = _number(meta, "freshness_sla_s")
    generated = _number(meta, "generated_at_s")
    effective_max_age = freshness if max_age_s is None else max_age_s
    if _now_s(now_s) - generated > effective_max_age:
        raise AtlasStaleError("Atlas outcome snapshot is stale")
    verified_stat = path.stat()
    uri = f"file:{quote(str(path.resolve()), safe='/:@')}?mode=ro&immutable=1"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        opened_stat = path.stat()
        if (opened_stat.st_ino, opened_stat.st_dev) != (verified_stat.st_ino, verified_stat.st_dev):
            raise AtlasChecksumError("Atlas outcome snapshot changed while opening")
        inner = dict(connection.execute("SELECT key, value FROM ledger_meta").fetchall())
        for key in OUTCOME_META_KEYS:
            if str(meta[key]) != inner.get(key):
                raise AtlasContractError(f"Atlas outcome envelope mismatch on {key}")
        pragma_major = connection.execute("PRAGMA user_version").fetchone()[0]
        if pragma_major != major:
            raise AtlasContractError("Atlas outcome PRAGMA major disagrees with sidecar")
        row_count = connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    except sqlite3.Error as exc:
        raise AtlasContractError(f"Atlas outcome snapshot cannot be opened read-only: {exc}") from exc
    except Exception:
        if connection is not None:
            connection.close()
        raise
    if row_count != row_count_meta:
        connection.close()
        raise AtlasContractError("Atlas outcome snapshot row_count disagrees with sidecar")
    try:
        yield dict(meta), connection
    finally:
        connection.close()


def verify_outcome_snapshot(
    snapshot: str | os.PathLike[str], *, now_s: float | None = None, max_age_s: float | None = None
) -> dict:
    """Verify checksum, major version, envelope agreement, and freshness."""
    with _verified_snapshot(snapshot, now_s=now_s, max_age_s=max_age_s) as (meta, _connection):
        return meta


@contextlib.contextmanager
def open_outcome_snapshot(snapshot: str | os.PathLike[str], **kwargs):
    """Yield a verified immutable SQLite connection and close it safely."""
    with _verified_snapshot(snapshot, **kwargs) as pair:
        yield pair


def build_atlas_mirror(
    proposal_read: dict,
    handoffs: list[dict],
    *,
    captured_at: str,
    outcome_snapshot_meta: dict | None = None,
) -> dict:
    """Build a Shep-owned display cache without copying Atlas write state."""
    if not proposal_read.get("ok"):
        raise AtlasContractError("cannot mirror blocked Atlas proposals")
    return {
        "schema": MIRROR_SCHEMA,
        "captured_at": captured_at,
        "proposal_source": {
            "schema": PROPOSALS_VERSION,
            "generated_at": proposal_read["generated_at"],
            "source_path": proposal_read.get("source_path"),
        },
        "proposals": proposal_read["proposals"],
        "approved_handoffs": handoffs,
        "outcome_snapshot": outcome_snapshot_meta,
    }


def write_atlas_mirror(path: str | os.PathLike[str], mirror: dict) -> None:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(mirror, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
