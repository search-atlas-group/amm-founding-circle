#!/usr/bin/env python3
"""The newest cohort session, read from the transcripts committed in the portal repo.

    python3 onboarding/nova_cohort.py

The weekly sessions and the Las Vegas days are committed as
scripts/data/recordings-pack.json in the portal repository (the knowledge hub),
not in the founding-circle repo. This reads that file and keeps the newest
weekly session's transcript locally, so Nova can learn from it.

It never makes a network call. It only reads a file already on the machine. If
the portal repo is not cloned here, it says so and stops.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "amm-founding-circle"
LAST = CACHE / "nova-cohort-last.txt"
TRANSCRIPT = CACHE / "nova-cohort-latest.txt"

PACK_RELATIVE = Path("scripts") / "data" / "recordings-pack.json"
# Where a member's machine might already have the portal repo.
CANDIDATES = [
    Path.home() / "Desktop" / "amm" / "amm-portal-ux-onboarding",
    Path.home() / "amm" / "amm-portal-ux-onboarding",
    Path.home() / "amm-mothership" / "portal",
]


def find_pack() -> Path | None:
    override = os.environ.get("AMM_PORTAL_REPO")
    roots = [Path(override)] if override else CANDIDATES
    for root in roots:
        candidate = root / PACK_RELATIVE
        if candidate.is_file():
            return candidate
    return None


def newest(pack: dict) -> dict | None:
    """The weekly session with the latest date. The Vegas days are not the weekly cohort."""
    recordings = pack.get("recordings") or []
    dated = []
    for recording in recordings:
        if recording.get("section") != "recordings" or not recording.get("transcript"):
            continue
        meta = recording.get("metadata") or {}
        date = meta.get("date") or meta.get("recordedOn") or ""
        if isinstance(date, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            dated.append((date, recording))
    if not dated:
        return None
    dated.sort(key=lambda item: item[0])
    return dated[-1][1]


def render(recording: dict) -> str:
    meta = recording.get("metadata") or {}
    date = meta.get("date") or meta.get("recordedOn") or "undated"
    lines = [f"SESSION {date}", f"TITLE {recording.get('title', '')}", ""]
    for window in recording.get("transcript") or []:
        text = re.sub(r"\s+", " ", str(window.get("text") or "")).strip()
        if not text:
            continue
        speaker = window.get("speaker")
        lines.append(f"{speaker}: {text}" if speaker else text)
    return "\n".join(lines)


def main() -> int:
    pack_path = find_pack()
    if pack_path is None:
        raise SystemExit(
            "Nova cannot see the sessions. The transcripts live in the portal repo "
            "(scripts/data/recordings-pack.json), and that repo is not on this machine."
        )
    try:
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit("The recordings pack is there but Nova could not read it.")
    recording = newest(pack)
    if recording is None:
        raise SystemExit("The recordings pack has no dated weekly session.")
    date = (recording.get("metadata") or {}).get("date") or "undated"
    CACHE.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT.write_text(render(recording) + "\n", encoding="utf-8")
    seen = LAST.read_text(encoding="utf-8").strip() if LAST.is_file() else ""
    if date == seen:
        print(f"The newest session is still {date}. Nova has already read it.")
        return 0
    LAST.write_text(date + "\n", encoding="utf-8")
    print(f"New session: {date}. Nova saved it locally and has not read it before.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
