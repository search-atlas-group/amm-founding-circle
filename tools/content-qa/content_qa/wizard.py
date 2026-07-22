"""wizard.py — voice-profile-builder wizard.

Given 3-5 sample published posts, asks the LLM to derive tone words, banned
phrases, reading level, formatting rules, and "sounds like us / doesn't
sound like us" examples, then writes the profile file. Requires an LLM
client — there is no offline substitute for "read these and describe the
voice," so this function errors clearly (never fabricates a profile) if no
API key is configured.
"""

from __future__ import annotations

from content_qa.llm_client import LLMClient, LLMError
from content_qa.voice_profile import VoiceProfile, parse_voice_profile

_SYSTEM_PROMPT = (
    "You are a precise brand-voice analyst for a marketing agency. You read "
    "sample published posts and derive a reusable voice profile that a "
    "content-QA tool will use to check FUTURE drafts against. Be concrete "
    "and specific — vague adjectives ('friendly', 'professional') are "
    "useless without examples. Output ONLY the markdown profile in the exact "
    "shape requested, nothing else."
)

_PROFILE_SHAPE = """# Voice Profile: {client_name}

## Tone words
word1, word2, word3

## Banned phrases
- "phrase one"
- "phrase two"

## Reading level
Grade N-M (one-line description)

## Formatting rules
- rule one
- rule two

## Sounds like us
- "a real sentence pulled or closely modeled from the samples"

## Doesn't sound like us
- "an invented sentence in the OPPOSITE style — generic, jargon-y, or off-tone"
"""


def build_wizard_prompt(client_name: str, sample_texts: list[str]) -> str:
    """Pure function (no network) so the prompt construction itself is
    unit-testable without hitting the LLM."""
    if not sample_texts:
        raise ValueError("build_wizard_prompt requires at least one sample text.")

    samples_block = "\n\n".join(
        f"--- SAMPLE {i + 1} ---\n{text.strip()}" for i, text in enumerate(sample_texts)
    )

    return (
        f"Client: {client_name}\n\n"
        f"Here are {len(sample_texts)} sample published posts from this client. "
        f"Derive their voice profile and output it in EXACTLY this markdown shape "
        f"(fill in real content, don't leave placeholders):\n\n{_PROFILE_SHAPE}\n\n"
        f"SAMPLE POSTS:\n\n{samples_block}"
    )


def build_voice_profile(client_name: str, sample_texts: list[str], llm_client: LLMClient) -> VoiceProfile:
    """Runs the wizard and returns a parsed VoiceProfile. Raises LLMError on
    any API failure — callers should surface that plainly, never fall back
    to a fabricated profile."""
    prompt = build_wizard_prompt(client_name, sample_texts)
    raw_markdown = llm_client.complete(system=_SYSTEM_PROMPT, user=prompt, max_tokens=1200)
    profile = parse_voice_profile(raw_markdown)
    if profile.is_empty():
        raise LLMError(
            "The LLM response didn't parse into a usable voice profile. "
            "Try again, or build the profile by hand from templates/voice-profile.example.md."
        )
    if not profile.client_name:
        profile.client_name = client_name
    return profile
