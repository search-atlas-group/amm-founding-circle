"""voice_check.py — voice-profile pass/fail layer.

Offline heuristic pass (banned-phrase hits + a stdlib-only reading-level
estimate) needs zero installs. An optional LLM pass can add tone-drift
rewrites when the member has an API key configured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from content_qa.voice_profile import VoiceProfile

_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")
_WORD_RE = re.compile(r"[A-Za-z']+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)


@dataclass
class BannedPhraseHit:
    phrase: str
    snippet: str


@dataclass
class VoiceResult:
    passed: bool
    banned_phrase_hits: list[BannedPhraseHit] = field(default_factory=list)
    reading_level_estimate: str = ""
    reading_level_note: str = ""
    notes: list[str] = field(default_factory=list)
    llm_rewrites: list[dict] = field(default_factory=list)  # {"line": ..., "rewrite": ...}

    @property
    def severity(self) -> str:
        """'none' | 'minor' | 'major' — feeds verdict.py's blocking logic."""
        if not self.banned_phrase_hits and not self.notes:
            return "none"
        if len(self.banned_phrase_hits) >= 3:
            return "major"
        return "minor"


def _count_syllables(word: str) -> int:
    """Crude but stdlib-only syllable estimate — count vowel groups, with the
    standard silent-e adjustment. Good enough for a directional grade-level
    estimate; not a claim of precision."""
    word = word.lower()
    groups = _VOWEL_GROUP_RE.findall(word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def estimate_reading_grade(text: str) -> float:
    """Flesch-Kincaid-style grade estimate, computed from stdlib regex only
    (no external `textstat`/`nltk` dependency). Directional, not exact."""
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    words = _WORD_RE.findall(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = syllables / len(words)
    grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59
    return round(max(grade, 0.0), 1)


def _reading_level_target_range(reading_level: str) -> tuple[int, int] | None:
    """Parse "Grade 8-10" / "grade 6" style profile text into a numeric
    range. Returns None if the profile text doesn't parse — callers should
    then skip the numeric comparison rather than guess."""
    match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", reading_level)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)", reading_level)
    if match:
        grade = int(match.group(1))
        return grade, grade
    return None


def check_voice(text: str, profile: VoiceProfile) -> VoiceResult:
    """Offline voice check: banned-phrase hits + reading-level fit against
    the profile. Pure function, no network, no LLM."""
    result = VoiceResult(passed=True)

    for phrase in profile.banned_phrases:
        for match in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            lo, hi = max(0, match.start() - 25), min(len(text), match.end() + 25)
            result.banned_phrase_hits.append(
                BannedPhraseHit(phrase=phrase, snippet=text[lo:hi].strip())
            )

    grade = estimate_reading_grade(text)
    result.reading_level_estimate = f"~grade {grade}"
    target = _reading_level_target_range(profile.reading_level) if profile.reading_level else None
    if target:
        lo, hi = target
        if grade < lo - 2 or grade > hi + 2:
            result.reading_level_note = (
                f"Draft reads at ~grade {grade}; profile targets grade {lo}-{hi}."
            )
            result.notes.append(result.reading_level_note)

    if result.banned_phrase_hits or result.reading_level_note:
        result.passed = False

    return result
