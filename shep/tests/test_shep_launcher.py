"""Regression tests for the bin/shep launcher's interpreter selection.

The launcher is the only part of Shep that runs before Python does, so a wrong
interpreter here fails as a bare ``TypeError`` inside shep.py that names neither
Shep nor the version. It bit the unattended path specifically: bare ``python3``
resolves to 3.11 in an interactive shell but to /usr/bin/python3 (3.9) under
launchd and login shells, so the crash only ever appeared where nobody was
watching.

These tests fabricate the interpreters rather than looking for a real 3.9 on the
machine. A skipif on "is there an old python here" passes vacuously on exactly
the hosts that lack one -- including CI, whose image ships a single modern
Python -- so the regression would be unguarded in the one place that gates
merges. Fabricating also keeps the assertions about the launcher's *ordering*,
which is the actual contract, instead of about the host's Python inventory.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


LAUNCHER = Path(__file__).resolve().parents[1] / "bin" / "shep"
CANDIDATE_NAMES = ("python3", "python3.13", "python3.12", "python3.11")


def _write_stub(directory: Path, name: str, body: str) -> Path:
    stub = directory / name
    stub.write_text(body, encoding="utf-8")
    stub.chmod(0o755)
    return stub


def _too_old(directory: Path, name: str) -> Path:
    """An interpreter that fails the >= 3.10 probe, as 3.9 does."""
    return _write_stub(directory, name, "#!/bin/sh\nexit 1\n")


def _modern(directory: Path, name: str) -> Path:
    """An interpreter that passes the probe by delegating to this very Python."""
    return _write_stub(
        directory, name, f'#!/bin/sh\nexec "{sys.executable}" "$@"\n'
    )


def _run(stub_dir: Path, *, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the launcher with the stub dir ahead of the system utilities.

    /usr/bin and /bin stay on PATH so the launcher's own shell helpers (dirname,
    readlink, git) still resolve -- the variable under test is which Python is
    reachable, not whether coreutils exist. SHEP_ALLOW_BRANCH is set because the
    branch guard runs first and would otherwise mask the behaviour under test.
    """
    env = {
        "HOME": os.environ.get("HOME", ""),
        "PATH": f"{stub_dir}:/usr/bin:/bin",
        "SHEP_ALLOW_BRANCH": "1",
    }
    env.update(env_extra or {})
    return subprocess.run(
        [str(LAUNCHER), "--help"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_launcher_skips_a_too_old_python3_and_keeps_looking(tmp_path: Path) -> None:
    """`python3` being first on PATH must not settle it if it is too old."""
    _too_old(tmp_path, "python3")
    _modern(tmp_path, "python3.11")

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "unsupported operand type" not in result.stderr
    assert "usage:" in result.stdout


def test_launcher_reports_a_clear_error_when_every_candidate_is_too_old(
    tmp_path: Path,
) -> None:
    """Name the requirement and the override; the raw TypeError told us neither."""
    for name in CANDIDATE_NAMES:
        _too_old(tmp_path, name)

    result = _run(tmp_path)

    assert result.returncode == 1
    assert "python >= 3.10" in result.stderr
    assert "SHEP_PYTHON" in result.stderr


def test_shep_python_override_beats_a_too_old_python3_on_path(tmp_path: Path) -> None:
    """An explicit pin wins, so an operator can point at a chosen build."""
    for name in CANDIDATE_NAMES:
        _too_old(tmp_path, name)
    pinned_dir = tmp_path / "pinned"
    pinned_dir.mkdir()
    pinned = _modern(pinned_dir, "python3")

    result = _run(tmp_path, env_extra={"SHEP_PYTHON": str(pinned)})

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
