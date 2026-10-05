#!/usr/bin/env python3
"""Report Shep missions whose evidence needs operator attention."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from scripts.shep_missions import _state_path
    from scripts.shep_phase1 import doctor
except ImportError:  # pragma: no cover - direct script execution
    from shep_missions import _state_path
    from shep_phase1 import doctor


def _default_path(name: str) -> Path:
    root = Path(os.environ.get("MISSION_ENGINE_DIR", str(Path.home() / ".mission-engine")))
    return root / name


def install_report() -> dict:
    """Version-integrity facts about the `shep` command vs this checkout.

    Advisory: a mismatch surfaces here rather than flipping the exit code,
    because doctor runs from wherever bin/shep resolved -- including a
    deliberate detached pin.
    """
    import shutil
    import subprocess

    repo = Path(__file__).resolve().parents[1]
    canonical = repo / "bin" / "shep"
    on_path = shutil.which("shep") or ""
    resolved = str(Path(on_path).resolve()) if on_path else ""
    branch = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        capture_output=True, text=True, timeout=15, check=False,
    ).stdout.strip()
    ok = bool(on_path) and resolved == str(canonical.resolve()) and branch in ("", "main")
    return {
        "ok": ok,
        "on_path": on_path,
        "resolves_to": resolved,
        "canonical": str(canonical.resolve()),
        "branch": branch or "detached",
    }


def render(report: dict) -> str:
    counts = report["counts"]
    lines = [
        "Shep doctor",
        f"status: {'OK' if report['ok'] else 'ATTENTION REQUIRED'}",
        "blocked={blocked} stale={stale} divergent={divergent} approval-held={approval_held}".format(**counts),
    ]
    install = report.get("install")
    if install:
        state = "ok" if install["ok"] else "MISMATCH"
        lines.append(
            f"install: {state} -- shep -> {install['resolves_to'] or 'not on PATH'}"
            f" (checkout branch: {install['branch']})"
        )
    for mission in report["missions"]:
        issues = mission.get("issues", [])
        if issues:
            lines.append(f"- {mission.get('id')}: {', '.join(issues)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--missions", type=Path, default=None)
    parser.add_argument("--runs-root", type=Path, default=None)
    parser.add_argument("--events", type=Path, default=None)
    args = parser.parse_args(argv)
    missions = args.missions or _state_path()
    runs_root = args.runs_root or Path(
        os.environ.get("SHEP_RUNS_ROOT", str(_default_path("runs")))
    )
    events = args.events or (
        Path(os.environ["SHEP_EVENTS_PATH"])
        if os.environ.get("SHEP_EVENTS_PATH")
        else _default_path("events.jsonl")
    )
    report = doctor(
        missions,
        runs_root=runs_root,
        event_path=events,
    )
    report["install"] = install_report()
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
