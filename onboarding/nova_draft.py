#!/usr/bin/env python3
"""A draft for JD about where this member struggles, held until they approve it.

    python3 onboarding/nova_draft.py

Nova writes one short note from what he can already see: the first thing in the
way, and the one pattern in how they work. He writes it to a file on this
machine and nowhere else. Nothing is sent. The member reads it, and they send
it if they want to.

The note names no client, no path, and no file. It says what is hard, not who
the member's customers are.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "amm-founding-circle"
DRAFT = CACHE / "nova-draft-for-jd.md"

import importlib.util


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clean(text: str) -> str:
    """Drop anything path-like. A struggle note should survive being read by someone else."""
    text = re.sub(r"/[\w./\-]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compose() -> str:
    insight = _load("nova_insight")
    practice = _load("nova_practice")
    report = insight.build()
    observed = practice.build()

    lines = [
        f"# For JD — {dt.date.today().isoformat()}",
        "",
        "Written by Nova on this machine. Nothing has been sent. "
        "If this is fair, send it to JD. If it is not, delete it.",
        "",
    ]
    blockers = [b for b in report["blockers"] if b.get("severity") != "note"]
    if blockers:
        first = blockers[0]
        lines.append(f"In the way: {_clean(first['for_member'])}")
        lines.append("")
    observations = [_clean(note) for note in observed["observations"] if _clean(note)]
    if observations:
        lines.append(f"How they work: {observations[0]}")
        lines.append("")
    if not blockers and not observations:
        lines.append("Nothing to flag. The setup is clear and there is no pattern yet.")
        lines.append("")
    lines.append("They can say what is wrong with this before it goes anywhere.")
    return "\n".join(lines)


def main() -> int:
    text = compose()
    CACHE.mkdir(parents=True, exist_ok=True)
    DRAFT.write_text(text + "\n", encoding="utf-8")
    print(f"Draft written to {DRAFT.name}. It has not been sent.")
    print("Show it to the member. They send it to JD, or they delete it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
