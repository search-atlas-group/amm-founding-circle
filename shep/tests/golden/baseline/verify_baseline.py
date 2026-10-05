#!/usr/bin/env python3
"""Verify Shep's immutable two-ancestor behavioral baseline artifacts.

Source attestation reads blobs from the recorded commits, never from checkout
files.  Consequently unrelated dirty/untracked files cannot change the result.
The verifier executes no ancestor code and consults no live Shep state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


BASELINE_ROOT = Path(__file__).resolve().parent
SELF_HASH_NAME = "BASELINE_SHA256SUMS"
SELF_HASH_SCHEMA = "shep-baseline-sha256/v1"
RECORDED_INTERPRETER = Path("/opt/homebrew/bin/python3")
RECORDED_SANITIZED_ENV = {
    "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
    "HOME": "/nonexistent",
    "PYTHONDONTWRITEBYTECODE": "1",
    "TERM": "xterm-256color",
}


class BaselineVerificationError(RuntimeError):
    """Raised when a baseline attestation or reference is invalid."""


@dataclass(frozen=True)
class Ancestor:
    name: str
    recorded_path: Path
    sha: str
    entrypoint: str


ANCESTORS = (
    Ancestor(
        name="mb_mgmt",
        recorded_path=Path(os.environ.get("SHEP_BASELINE_MBM_REPO", "/unavailable/mb-mgmt")),
        sha="ace78be9ff2b594b82d73ca59c8cbd9a5ab1c7d0",
        entrypoint="scripts/shep.py",
    ),
    Ancestor(
        name="agentic_engineering",
        recorded_path=Path(
            os.environ.get("SHEP_BASELINE_AE_REPO", "/unavailable/agentic-engineering")
        ),
        sha="073b2025e51430b8eecdf6d097fb0e30436fe86f",
        entrypoint="stack/fleetmon/fleet_monitor.py",
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_paths(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.name != SELF_HASH_NAME
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def build_self_hash_manifest(root: Path = BASELINE_ROOT) -> str:
    """Build a deterministic manifest whose header authenticates its own body."""

    root = root.resolve()
    lines = [
        f"{_sha256(path.read_bytes())}  {path.relative_to(root).as_posix()}"
        for path in _artifact_paths(root)
    ]
    body = "\n".join(lines) + ("\n" if lines else "")
    return (
        f"# schema={SELF_HASH_SCHEMA}\n"
        f"# manifest_body_sha256={_sha256(body.encode('utf-8'))}\n"
        f"{body}"
    )


def verify_self_hash_manifest(root: Path = BASELINE_ROOT) -> list[str]:
    root = root.resolve()
    path = root / SELF_HASH_NAME
    if not path.is_file():
        raise BaselineVerificationError(f"missing self-hash manifest: {path}")
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines(keepends=True)
    if len(lines) < 2 or lines[0] != f"# schema={SELF_HASH_SCHEMA}\n":
        raise BaselineVerificationError("invalid self-hash manifest schema header")
    digest_prefix = "# manifest_body_sha256="
    if not lines[1].startswith(digest_prefix):
        raise BaselineVerificationError("missing self-hash manifest body digest")
    declared_body_digest = lines[1].strip()[len(digest_prefix) :]
    body = "".join(lines[2:])
    actual_body_digest = _sha256(body.encode("utf-8"))
    if actual_body_digest != declared_body_digest:
        raise BaselineVerificationError(
            f"self-hash manifest body hash mismatch: {actual_body_digest} != {declared_body_digest}"
        )

    listed: dict[str, str] = {}
    for number, line in enumerate(body.splitlines(), start=3):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise BaselineVerificationError(f"invalid manifest line {number}") from exc
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise BaselineVerificationError(f"invalid SHA-256 on manifest line {number}")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative == SELF_HASH_NAME:
            raise BaselineVerificationError(f"unsafe manifest path on line {number}: {relative}")
        if relative in listed:
            raise BaselineVerificationError(f"duplicate manifest path: {relative}")
        listed[relative] = digest

    actual_paths = [path.relative_to(root).as_posix() for path in _artifact_paths(root)]
    if sorted(listed) != actual_paths:
        missing = sorted(set(actual_paths) - set(listed))
        extra = sorted(set(listed) - set(actual_paths))
        raise BaselineVerificationError(
            f"self-hash manifest coverage mismatch: missing={missing!r} extra={extra!r}"
        )
    for relative in actual_paths:
        actual = _sha256((root / relative).read_bytes())
        if actual != listed[relative]:
            raise BaselineVerificationError(
                f"artifact hash mismatch for {relative}: {actual} != {listed[relative]}"
            )
    return actual_paths


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise BaselineVerificationError(f"{path}:{number}: invalid environment record")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise BaselineVerificationError(f"{path}:{number}: duplicate/empty key {key!r}")
        values[key] = value
    return values


def _parse_source_hashes(path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise BaselineVerificationError(f"{path}:{number}: invalid hash line") from exc
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise BaselineVerificationError(f"{path}:{number}: unsafe source path {relative!r}")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise BaselineVerificationError(f"{path}:{number}: invalid SHA-256")
        if relative in hashes:
            raise BaselineVerificationError(f"{path}:{number}: duplicate source path")
        hashes[relative] = digest
    if not hashes:
        raise BaselineVerificationError(f"{path}: empty source hash manifest")
    return hashes


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise BaselineVerificationError(
            f"git object read failed in recorded ancestor {repo}: {stderr or result.returncode}"
        )
    return result.stdout


def _verify_probe_command(
    command: str, *, require_interpreter_available: bool = True
) -> dict[str, object]:
    words = shlex.split(command)
    if words[:2] != ["env", "-i"]:
        raise BaselineVerificationError("probe command must begin with an empty environment")
    environment: dict[str, str] = {}
    index = 2
    while index < len(words) and "=" in words[index] and not words[index].startswith("="):
        key, value = words[index].split("=", 1)
        environment[key] = value
        index += 1
    if environment != RECORDED_SANITIZED_ENV:
        raise BaselineVerificationError(
            f"sanitized probe environment mismatch: {environment!r}"
        )
    if index >= len(words) or words[index] != "python3":
        raise BaselineVerificationError("probe interpreter must be recorded as python3")
    logical_interpreter = Path(environment["PATH"].split(os.pathsep)[0]) / "python3"
    if logical_interpreter != RECORDED_INTERPRETER:
        raise BaselineVerificationError(
            f"recorded interpreter path changed: {logical_interpreter}"
        )
    if require_interpreter_available and not logical_interpreter.is_file():
        raise BaselineVerificationError(
            f"recorded interpreter is unavailable: {logical_interpreter}"
        )
    return {
        "logical_path": str(logical_interpreter),
        "realpath": (
            str(logical_interpreter.resolve())
            if logical_interpreter.is_file()
            else "<unavailable-on-current-host>"
        ),
        "sanitized_environment": environment,
        "argv": words[index + 1 :],
    }


def _verify_help(path: Path, inventory: Mapping[str, object], expected_exit: int) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("usage:") or "Options captured from the sanitized executable probe:" not in text:
        raise BaselineVerificationError(f"invalid help capture: {path}")
    for flag in inventory.get("cli_flags", []):
        if not isinstance(flag, str) or flag not in text:
            raise BaselineVerificationError(f"{path}: missing inventory CLI flag {flag!r}")
    if f"Probe exit: {expected_exit}" not in text:
        raise BaselineVerificationError(f"{path}: probe exit does not match manifest")
    if "\x1b" in text or any(ord(char) in range(0x80, 0xA0) for char in text):
        raise BaselineVerificationError(f"{path}: help contains terminal controls")


def _verify_json_and_fixture_references(root: Path) -> list[str]:
    checked: list[str] = []
    for path in sorted(root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BaselineVerificationError(f"invalid JSON artifact {path}: {exc}") from exc
        if path.parent.name in {"ae", "mbm"} and isinstance(value, dict) and "surface" in value:
            required = {"surface", "exit_code"}
            missing = required - value.keys()
            if missing:
                raise BaselineVerificationError(
                    f"fixture {path} lacks executable probe fields: {sorted(missing)!r}"
                )
            if not ({"stderr", "stderr_class"} & value.keys()):
                raise BaselineVerificationError(f"fixture {path} lacks stderr semantics")
            if not ({"stdout", "stdout_json", "observation", "flags"} & value.keys()):
                raise BaselineVerificationError(f"fixture {path} lacks output semantics")
        checked.append(path.relative_to(root).as_posix())
    _verify_golden_map(root / "golden", checked)
    return checked


def _verify_golden_map(golden_root: Path, checked_json: list[str]) -> None:
    map_path = golden_root / "MAP.md"
    if not map_path.is_file():
        raise BaselineVerificationError("missing golden fixture destination map")
    referenced: set[str] = set()
    for line in map_path.read_text(encoding="utf-8").splitlines():
        cells = line.split("|")
        if len(cells) < 3:
            continue
        for pattern in re.findall(r"`([^`]+)`", cells[1]):
            matches = [
                path
                for path in golden_root.glob(pattern)
                if path.is_file() and path.suffix == ".json"
            ]
            if not matches:
                raise BaselineVerificationError(
                    f"golden map reference matched no fixtures: {pattern}"
                )
            referenced.update(path.relative_to(golden_root).as_posix() for path in matches)
    fixtures = {
        Path(relative).relative_to("golden").as_posix()
        for relative in checked_json
        if relative.startswith("golden/")
    }
    if not referenced or not referenced.issubset(fixtures):
        raise BaselineVerificationError(
            f"golden map has invalid fixture references: {sorted(referenced - fixtures)!r}"
        )


def verify_ancestor(
    root: Path, ancestor: Ancestor, *, attest_objects: bool = True
) -> dict[str, object]:
    directory = root / ancestor.name
    metadata = _parse_env(directory / "manifest.env")
    inventory_path = directory / metadata.get("summary_json", "")
    hashes_path = directory / metadata.get("source_hashes", "")
    help_path = directory / metadata.get("stdout", "")
    for reference in (inventory_path, hashes_path, help_path):
        if not reference.is_file() or directory not in reference.resolve().parents:
            raise BaselineVerificationError(f"invalid ancestor artifact reference: {reference}")
    if metadata.get("git_head") != ancestor.sha:
        raise BaselineVerificationError(f"{ancestor.name}: recorded SHA mismatch")
    if metadata.get("exit_code") != "0" or metadata.get("stderr") != "empty":
        raise BaselineVerificationError(f"{ancestor.name}: help probe exit/stderr metadata changed")

    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BaselineVerificationError(f"invalid inventory JSON: {inventory_path}") from exc
    if inventory.get("git_head") != ancestor.sha or inventory.get("entrypoint") != ancestor.entrypoint:
        raise BaselineVerificationError(f"{ancestor.name}: inventory provenance mismatch")
    if inventory.get("probe", {}).get("exit_code") != int(metadata["exit_code"]):
        raise BaselineVerificationError(f"{ancestor.name}: inventory probe exit mismatch")
    _verify_help(help_path, inventory, int(metadata["exit_code"]))

    hashes = _parse_source_hashes(hashes_path)
    if ancestor.entrypoint not in hashes:
        raise BaselineVerificationError(f"{ancestor.name}: entrypoint is absent from source hashes")
    if attest_objects:
        _git(ancestor.recorded_path, "cat-file", "-e", f"{ancestor.sha}^{{commit}}")
        for relative, expected in hashes.items():
            blob = _git(ancestor.recorded_path, "show", f"{ancestor.sha}:{relative}")
            actual = _sha256(blob)
            if actual != expected:
                raise BaselineVerificationError(
                    f"{ancestor.name}: commit-object hash mismatch for {relative}: {actual} != {expected}"
                )

    interpreter = _verify_probe_command(
        metadata["command"], require_interpreter_available=attest_objects
    )
    expected_argv = [ancestor.entrypoint, "--help"]
    if interpreter["argv"] != expected_argv:
        raise BaselineVerificationError(
            f"{ancestor.name}: probe argv mismatch: {interpreter['argv']!r}"
        )
    return {
        "recorded_path": str(ancestor.recorded_path),
        "recorded_sha": ancestor.sha,
        "content_attestation": (
            "git-commit-object" if attest_objects else "sealed-source-hash-manifest"
        ),
        "source_objects_verified": len(hashes) if attest_objects else 0,
        "source_hashes_declared": len(hashes),
        "interpreter": interpreter,
    }


def verify(root: Path = BASELINE_ROOT, *, portable: bool = False) -> dict[str, object]:
    root = root.resolve()
    top_metadata = _parse_env(root / "manifest.env")
    expected_heads = {
        "mb_mgmt_git_head": ANCESTORS[0].sha,
        "agentic_engineering_git_head": ANCESTORS[1].sha,
    }
    for key, expected in expected_heads.items():
        if top_metadata.get(key) != expected:
            raise BaselineVerificationError(f"top-level provenance mismatch for {key}")
    if top_metadata.get("live_state_observed") != "false" or top_metadata.get(
        "mutations_performed"
    ) != "false":
        raise BaselineVerificationError("baseline safety metadata does not attest a read-only capture")
    for reference_key in ("normalizer", "inventory"):
        raw_reference = top_metadata.get(reference_key)
        if not raw_reference:
            raise BaselineVerificationError(f"missing top-level reference: {reference_key}")
        reference = (root / raw_reference).resolve()
        if not reference.is_file():
            raise BaselineVerificationError(f"broken top-level reference: {raw_reference}")

    json_artifacts = _verify_json_and_fixture_references(root)
    ancestors = {
        item.name: verify_ancestor(root, item, attest_objects=not portable)
        for item in ANCESTORS
    }
    artifacts = verify_self_hash_manifest(root)
    return {
        "schema": "shep-baseline-verification/v1",
        "baseline_root": str(root),
        "ancestors": ancestors,
        "json_artifacts_verified": json_artifacts,
        "self_hashed_artifacts_verified": len(artifacts),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=BASELINE_ROOT)
    parser.add_argument(
        "--portable",
        action="store_true",
        help="verify sealed artifacts without requiring the two ancestor checkouts",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = verify(args.root, portable=args.portable)
    except BaselineVerificationError as exc:
        print(f"baseline verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
