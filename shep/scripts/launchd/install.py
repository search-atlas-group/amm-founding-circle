#!/usr/bin/env python3
"""Render and load the Shep control LaunchAgent for this checkout.

The committed template is deliberately inert (no schedule, ``RunAtLoad`` and
``KeepAlive`` false). Enabling automation is an install-time act: this script
resolves the placeholders against a real checkout, adds the schedule and log
paths, and hands the result to launchd.
"""

from __future__ import annotations

import argparse
import plistlib
import subprocess
import sys
from pathlib import Path


LABEL = "com.searchatlas.shep-control"
TEMPLATE = Path(__file__).resolve().parent / f"{LABEL}.plist.in"
TARGET = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = Path.home() / ".mission-engine"
# launchd starts agents with a bare PATH; codex-gw, herdr, and git all live here.
# /usr/sbin is not optional: sysctl lives there and nothing else on this PATH
# provides it, so omitting it makes the probe fail rather than report.
PATH = (
    f"{Path.home()}/.local/bin:/opt/homebrew/bin:/usr/local/bin:"
    "/usr/bin:/bin:/usr/sbin:/sbin"
)


def _launchctl(*args: str) -> int:
    return subprocess.run(["launchctl", *args], check=False).returncode


def _domain() -> str:
    return f"gui/{Path.home().stat().st_uid}"


def render(shep_root: Path, interval: int, nudge_cmd: str | None = None) -> dict:
    config = plistlib.loads(
        TEMPLATE.read_text(encoding="utf-8")
        .replace("@PYTHON@", sys.executable)
        .replace("@SHEP_ROOT@", str(shep_root))
        .encode("utf-8")
    )
    config["WorkingDirectory"] = str(shep_root)
    config["EnvironmentVariables"]["HOME"] = str(Path.home())
    config["EnvironmentVariables"]["PATH"] = PATH
    if nudge_cmd:
        config["EnvironmentVariables"]["SHEP_NUDGE_CMD"] = nudge_cmd
    config["StartInterval"] = interval
    config["ProcessType"] = "Background"
    config["StandardOutPath"] = str(LOG_DIR / "shep-control.stdout.log")
    config["StandardErrorPath"] = str(LOG_DIR / "shep-control.stderr.log")
    return config


def install(shep_root: Path, interval: int, nudge_cmd: str | None = None) -> None:
    loop = shep_root / "scripts/shep_control_loop.py"
    if not loop.is_file():
        raise SystemExit(f"not a Shep checkout: {loop} is missing")

    LOG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("wb") as stream:
        plistlib.dump(render(shep_root, interval, nudge_cmd), stream)

    _launchctl("bootout", f"{_domain()}/{LABEL}")
    # A previous `launchctl disable` persists across installs and makes
    # bootstrap fail with a bare I/O error, so clear it before loading.
    _launchctl("enable", f"{_domain()}/{LABEL}")
    if _launchctl("bootstrap", _domain(), str(TARGET)):
        raise SystemExit(f"launchctl could not load {TARGET}")
    print(f"loaded {LABEL} -> {loop} every {interval}s")


def uninstall() -> None:
    _launchctl("bootout", f"{_domain()}/{LABEL}")
    TARGET.unlink(missing_ok=True)
    print(f"removed {LABEL}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shep-root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="checkout the agent should run (default: this one)")
    parser.add_argument("--interval", type=int, default=300,
                        help="seconds between control passes (default: 300)")
    parser.add_argument("--nudge-cmd",
                        help="override the draft gateway, e.g. 'claude-gw -p' when the "
                             "Codex pool is out of capacity")
    parser.add_argument("--uninstall", action="store_true", help="unload and delete the agent")
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
        return 0
    install(args.shep_root.expanduser().resolve(), args.interval, args.nudge_cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
