"""The normalized lead/grade schema every adapter and grader speaks.

Every input source (CallRail today; LSA / form-fills / the outbound
pipeline later — see adapters/) gets mapped into one ``Lead`` shape so the
grading engine, the store, and the digest never need to know which source
a lead came from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# The four grades every lead artifact is judged into. Order matters — it's
# also the digest sort order (Hot first, Junk last).
VALID_GRADES: tuple[str, ...] = ("Hot", "Qualified", "Weak", "Junk")

GRADE_EMOJI: dict[str, str] = {
    "Hot": "🔥",
    "Qualified": "✅",
    "Weak": "⚠️",
    "Junk": "🗑️",
}

_UNKNOWN_EMOJI = "❓"

# Lowercased grade -> canonical form, for tolerant parsing of LLM output
# ("hot", " HOT ", "Hot" all mean the same thing).
_NORMALIZE_MAP: dict[str, str] = {g.lower(): g for g in VALID_GRADES}


def emoji_for(grade: str) -> str:
    """Return the emoji for a grade; a safe fallback for anything unrecognized."""
    return GRADE_EMOJI.get(grade, _UNKNOWN_EMOJI)


def is_valid_grade(grade: Any) -> bool:
    """Exact-form membership check — does NOT normalize case/whitespace."""
    return grade in VALID_GRADES


def normalize_grade_label(raw: Any) -> Optional[str]:
    """Best-effort recovery of a grade label from LLM output.

    Tolerates case and surrounding whitespace ("hot", " HOT ") but returns
    None (never a guess) for anything that isn't one of the four grades —
    callers must fail closed on None, not assume a grade.
    """
    if not isinstance(raw, str):
        return None
    return _NORMALIZE_MAP.get(raw.strip().lower())


@dataclass
class Lead:
    """One normalized inbound lead artifact (a call, a form fill, ...)."""

    id: str
    """Stable id from the source system — used to dedupe on re-import."""
    client: str
    """Client slug (matches a clients/<slug>/ folder)."""
    source: str
    """Which adapter produced this — "callrail", "lsa", "form", "outbound"."""
    occurred_at: datetime

    caller: Optional[str] = None
    """Phone number or caller name, whichever the source gives us."""
    duration_seconds: Optional[int] = None
    transcript: str = ""
    recording_url: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)
    """The untouched source payload, kept for audit / re-processing."""

    def has_transcript(self) -> bool:
        return bool(self.transcript and self.transcript.strip())


@dataclass
class Grade:
    """The verdict on one Lead."""

    lead_id: str
    client: str
    grade: str
    """One of VALID_GRADES."""
    reason: str
    """One-line, plain-English reason."""
    quote: str = ""
    """The key quote from the transcript that justifies the grade, if any."""
    graded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    model: str = ""
    """Which LLM/provider produced this grade, for audit."""

    def emoji(self) -> str:
        return emoji_for(self.grade)
