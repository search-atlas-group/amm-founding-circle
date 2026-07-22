"""voice_profile.py — parse and represent a per-client voice profile.

A voice profile is a plain markdown file a member builds once per client
(by hand, or via the `--build-profile` wizard in run.py). See
templates/voice-profile.example.md for the exact shape this parses.

Deliberately NOT yaml/frontmatter — this stays a zero-dependency parser so
the tool needs no `pip install` to run in offline mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(?:Voice Profile:\s*)?(.+?)\s*$", re.MULTILINE)

# Canonical section names -> the VoiceProfile field they populate.
_KNOWN_SECTIONS = {
    "tone words": "tone_words",
    "banned phrases": "banned_phrases",
    "reading level": "reading_level",
    "formatting rules": "formatting_rules",
    "sounds like us": "sounds_like_us",
    "doesn't sound like us": "doesnt_sound_like_us",
    "doesnt sound like us": "doesnt_sound_like_us",
}

# Sections whose body is a single free-text line/paragraph, not a list.
_FREE_TEXT_SECTIONS = {"reading_level"}


@dataclass
class VoiceProfile:
    client_name: str = ""
    tone_words: list[str] = field(default_factory=list)
    banned_phrases: list[str] = field(default_factory=list)
    reading_level: str = ""
    formatting_rules: list[str] = field(default_factory=list)
    sounds_like_us: list[str] = field(default_factory=list)
    doesnt_sound_like_us: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [
                self.tone_words,
                self.banned_phrases,
                self.reading_level,
                self.formatting_rules,
                self.sounds_like_us,
                self.doesnt_sound_like_us,
            ]
        )


def _parse_list_items(body: str) -> list[str]:
    """Bullet list ("- item" / "* item") or comma-separated single line."""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    bullets = [ln[1:].strip() for ln in lines if ln.startswith(("-", "*"))]
    if bullets:
        return [_strip_quotes(b) for b in bullets if b]
    # Fall back to a comma-separated single line (tone words are often this).
    if len(lines) == 1 and "," in lines[0]:
        return [_strip_quotes(part.strip()) for part in lines[0].split(",") if part.strip()]
    return [_strip_quotes(ln) for ln in lines]


def _strip_quotes(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    return text


def parse_voice_profile(text: str) -> VoiceProfile:
    """Parse a voice-profile markdown document into a VoiceProfile.

    Unknown/extra sections are ignored (forward-compatible); missing
    sections stay empty rather than raising — a partial profile is still
    usable, and the QA report will note what's missing.
    """
    profile = VoiceProfile()

    title_match = _TITLE_RE.search(text)
    if title_match:
        profile.client_name = title_match.group(1).strip()

    matches = list(_SECTION_RE.finditer(text))
    for idx, match in enumerate(matches):
        heading = match.group(1).strip().lower()
        field_name = _KNOWN_SECTIONS.get(heading)
        if not field_name:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        if field_name in _FREE_TEXT_SECTIONS:
            setattr(profile, field_name, " ".join(body.split()))
        else:
            setattr(profile, field_name, _parse_list_items(body))

    return profile


def load_voice_profile(path: Path | str) -> VoiceProfile:
    """Read + parse a voice profile from disk. Raises FileNotFoundError with
    a plain-English message if the client hasn't been set up yet — callers
    should catch this and point the user at the wizard, never fabricate a
    profile."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No voice profile found at {path}. Run the voice-profile wizard "
            f"first: python3 run.py --build-profile sample1.md sample2.md "
            f"sample3.md --client <client-slug>"
        )
    return parse_voice_profile(path.read_text(encoding="utf-8"))


def render_voice_profile(profile: VoiceProfile) -> str:
    """Render a VoiceProfile back to the canonical markdown shape (used by
    the wizard to write what it derived, and round-trippable with parse)."""
    lines = [f"# Voice Profile: {profile.client_name or 'Unnamed Client'}", ""]

    def bullet_section(title: str, items: list[str]) -> None:
        lines.append(f"## {title}")
        if items:
            for item in items:
                lines.append(f'- "{item}"' if " " in item else f"- {item}")
        lines.append("")

    lines.append("## Tone words")
    lines.append(", ".join(profile.tone_words) if profile.tone_words else "")
    lines.append("")

    bullet_section("Banned phrases", profile.banned_phrases)

    lines.append("## Reading level")
    lines.append(profile.reading_level or "")
    lines.append("")

    bullet_section("Formatting rules", profile.formatting_rules)
    bullet_section("Sounds like us", profile.sounds_like_us)
    bullet_section("Doesn't sound like us", profile.doesnt_sound_like_us)

    return "\n".join(lines).rstrip() + "\n"
