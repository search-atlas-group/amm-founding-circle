#!/usr/bin/env python3
"""Stand up Hermes for a Founding Circle member, idempotently.

    python3 onboarding/hermes_setup.py            # install, wire skills, lay down Nova
    python3 onboarding/hermes_setup.py --repair   # same, but never open a window
    python3 onboarding/hermes_setup.py --check    # report only, change nothing

What it guarantees:

- The Founding Circle ``skills/`` directory is on Hermes' skill path, so the
  skills show up in Hermes without a second copy that can drift.
- Nova, the guide, is written to ``SOUL.md`` when the member has no soul, or
  when the soul there is still a copy of ours. A soul they wrote is never touched.
- The model and the key are theirs. This script does not run ``hermes setup``
  and does not invent a provider.

Failure is a message, not an exception that stops the ladder audit.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SKILLS = REPO / "skills"
NOVA = HERE / "nova" / "SOUL.md"
MARKER = "amm-founding-circle-nova"

HERMES_INSTALL = "https://hermes-agent.nousresearch.com/install.sh"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


def config_path() -> Path:
    return hermes_home() / "config.yaml"


def soul_path() -> Path:
    return hermes_home() / "SOUL.md"


def log(msg: str) -> None:
    print(f"  hermes: {msg}")


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)


def hermes_bin() -> str | None:
    found = shutil.which("hermes")
    if found:
        return found
    candidate = hermes_home() / "hermes-agent" / ".hermes" / "bin" / "hermes"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def install_hermes() -> bool:
    """Install the CLI when it is missing. A failure is reported, not raised."""
    if hermes_bin():
        log("already installed")
        return True
    log("not installed — running the Hermes installer (this can take a few minutes)")
    curl = shutil.which("curl")
    bash = shutil.which("bash")
    if not curl or not bash:
        log("curl or bash is missing, so Hermes was not installed. Install it from https://hermes-agent.nousresearch.com and run this again.")
        return False
    proc = subprocess.run(
        [bash, "-c", f'curl -fsSL "{HERMES_INSTALL}" | bash'],
        text=True,
        timeout=900,
        check=False,
    )
    if proc.returncode != 0 or not hermes_bin():
        log("the Hermes installer did not finish. The ladder audit still runs. Try again later, or install Hermes by hand.")
        return False
    log("installed")
    return True


def _parse_scalar(text: str):
    body = text.split("#", 1)[0].strip()
    if len(body) >= 2 and body[0] == body[-1] and body[0] in ("'", '"'):
        body = body[1:-1]
    return body


def _load_external_dirs(text: str) -> list[str] | None:
    """The skills.external_dirs list, or None when the config is not ours to edit.

    None means external_dirs is present but not a list we can safely edit.
    An empty list means the key is absent and may be created. A file with no
    skills section at all also returns an empty list.
    """
    lines = text.splitlines()
    skills_at = None
    skills_indent = None
    for index, line in enumerate(lines):
        if line.startswith("skills:"):
            skills_at = index
            skills_indent = len(line) - len(line.lstrip(" "))
            break
    if skills_at is None:
        return []
    end = len(lines)
    for index in range(skills_at + 1, len(lines)):
        stripped = lines[index].lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(lines[index]) - len(stripped)
        if indent <= skills_indent:
            end = index
            break
    key_at = None
    key_indent = None
    for index in range(skills_at + 1, end):
        stripped = lines[index].lstrip(" ")
        if stripped.startswith("external_dirs:"):
            key_at = index
            key_indent = len(lines[index]) - len(stripped)
            break
    if key_at is None:
        return []
    inline = lines[key_at].split(":", 1)[1].split("#", 1)[0].strip()
    if inline.startswith("[") and inline.endswith("]"):
        inner = inline[1:-1].strip()
        return [_parse_scalar(part) for part in inner.split(",") if part.strip()] if inner else []
    if inline:
        return None
    found: list[str] = []
    for index in range(key_at + 1, end):
        stripped = lines[index].lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(lines[index]) - len(stripped)
        if indent <= key_indent:
            break
        if not stripped.startswith("- "):
            return None
        found.append(_parse_scalar(stripped[2:]))
    return found


def _append_external_dir(text: str, target: str) -> str:
    """Add one path. Creates skills.external_dirs when the file has neither."""
    lines = text.splitlines()
    skills_at = next((i for i, line in enumerate(lines) if line.startswith("skills:")), None)
    if skills_at is None:
        addition = ["skills:", "  external_dirs:", f"    - {target}"]
        base = lines + ([""] if lines and lines[-1] != "" else [])
        return "\n".join(base + addition) + "\n"
    end = len(lines)
    for index in range(skills_at + 1, len(lines)):
        stripped = lines[index].lstrip(" ")
        if stripped and not stripped.startswith("#"):
            if len(lines[index]) - len(stripped) == 0:
                end = index
                break
    key_at = next(
        (i for i in range(skills_at + 1, end) if lines[i].lstrip(" ").startswith("external_dirs:")),
        None,
    )
    if key_at is None:
        lines.insert(end, "  external_dirs:")
        lines.insert(end + 1, f"    - {target}")
        return "\n".join(lines) + "\n"
    key_indent = len(lines[key_at]) - len(lines[key_at].lstrip(" "))
    last = key_at
    for index in range(key_at + 1, len(lines)):
        stripped = lines[index].lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        if len(lines[index]) - len(stripped) <= key_indent:
            break
        last = index
    lines.insert(last + 1, f"{' ' * (key_indent + 2)}- {target}")
    return "\n".join(lines) + "\n"


def wire_skills() -> str:
    """Point Hermes at the repo's skills. Returns 'added', 'present', or 'skipped'.

    Edits only the external_dirs list, so comments and secrets elsewhere in
    config.yaml survive. A shape we do not understand is left untouched.
    """
    if not SKILLS.is_dir():
        log(f"no skills directory at {SKILLS} — nothing to wire")
        return "skipped"
    target = str(SKILLS)
    path = config_path()
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    dirs = _load_external_dirs(text)
    if dirs is None:
        log("skills.external_dirs is not a simple list — leaving config.yaml untouched")
        return "skipped"
    resolved = {str(Path(os.path.expanduser(entry)).resolve()) for entry in dirs}
    if str(SKILLS.resolve()) in resolved:
        log("Founding Circle skills already on the Hermes skill path")
        return "present"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_append_external_dir(text, target), encoding="utf-8")
    log(f"Founding Circle skills added to Hermes ({target})")
    return "added"


def write_nova() -> str:
    """Lay Nova down only when the soul is missing or still ours. Returns what happened."""
    if not NOVA.is_file():
        log("Nova's soul file is missing from this repo — skipping")
        return "skipped"
    nova = NOVA.read_text(encoding="utf-8")
    dest = soul_path()
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(nova, encoding="utf-8")
        _mark()
        log("Nova is now the guide in ~/.hermes/SOUL.md")
        return "written"
    current = dest.read_text(encoding="utf-8")
    if current == nova:
        log("Nova is already the guide")
        return "present"
    if _is_ours():
        dest.write_text(nova, encoding="utf-8")
        log("Nova updated (their soul was still the one we shipped)")
        return "updated"
    log("a soul is already there and it is theirs — Nova was not written over it")
    return "kept"


def _mark() -> None:
    marker = hermes_home() / ".amm-nova"
    marker.write_text(f"{MARKER}\n", encoding="utf-8")


def _is_ours() -> bool:
    marker = hermes_home() / ".amm-nova"
    if not marker.is_file():
        return False
    return marker.read_text(encoding="utf-8").strip() == MARKER


def open_hermes() -> None:
    """Open the desktop app once. Never from the two-hour repair."""
    binary = hermes_bin()
    if not binary:
        return
    if os.environ.get("CI") or os.environ.get("AMM_NO_OPEN") or os.environ.get("AMM_UNATTENDED"):
        log("not opening Hermes (unattended)")
        return
    log("opening Hermes")
    if sys.platform == "darwin":
        subprocess.Popen([binary, "desktop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
        subprocess.Popen([binary, "desktop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        log("open it yourself with: hermes desktop")


def check() -> int:
    binary = hermes_bin()
    log(f"command: {binary or 'not found'}")
    wired = False
    if config_path().is_file():
        dirs = _load_external_dirs(config_path().read_text(encoding="utf-8"))
        if dirs is None:
            log("Founding Circle skills on the Hermes path: config.yaml was not readable as a list")
            dirs = []
        resolved = {str(Path(os.path.expanduser(entry)).resolve()) for entry in dirs}
        wired = SKILLS.is_dir() and str(SKILLS.resolve()) in resolved
    log(f"Founding Circle skills on the Hermes path: {'yes' if wired else 'no'}")
    dest = soul_path()
    if not dest.is_file():
        log("soul: none")
    elif NOVA.is_file() and dest.read_text(encoding="utf-8") == NOVA.read_text(encoding="utf-8"):
        log("soul: Nova")
    elif _is_ours():
        log("soul: Nova, and a newer one is in the repo")
    else:
        log("soul: theirs (will not be replaced)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true", help="install and wire, but never open a window")
    parser.add_argument("--check", action="store_true", help="report only")
    args = parser.parse_args(argv)

    if args.check:
        return check()

    print("Hermes for the Founding Circle")
    installed = install_hermes()
    if not installed and not hermes_home().is_dir():
        hermes_home().mkdir(parents=True, exist_ok=True)
    try:
        wired = wire_skills()
    except Exception as exc:  # a config problem must not kill onboarding
        log(f"could not wire skills ({exc}). Left config.yaml as it was.")
        wired = "skipped"
    write_nova()
    if not args.repair and installed:
        open_hermes()
    if not installed:
        log("Hermes itself still needs installing. Everything else is in place for when it arrives.")
    elif wired == "skipped":
        log("Hermes is installed, but the Founding Circle skills are not on its path yet. config.yaml was left as it was.")
    else:
        log('the Founding Circle skills are on the Hermes skill path. Ask Nova: "what can I automate?"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
