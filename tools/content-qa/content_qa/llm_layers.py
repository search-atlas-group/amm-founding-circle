"""llm_layers.py — optional LLM enrichment for the grammar/voice/facts
layers. Each function takes the existing offline result and merges in
LLM-derived findings. Every call degrades gracefully: on any LLMError
(network down, bad key, rate limit) it returns the offline result
UNCHANGED plus a note — it never crashes the run and never invents a
result silently.
"""

from __future__ import annotations

import json
import re

from content_qa.fact_check import Claim, FactResult
from content_qa.fact_check import Verdict as FactVerdict
from content_qa.grammar import Issue
from content_qa.llm_client import LLMClient, LLMError
from content_qa.voice_check import VoiceResult
from content_qa.voice_profile import VoiceProfile

_JSON_BLOCK_RE = re.compile(r"\[.*\]|\{.*\}", re.DOTALL)


def _extract_json(raw: str):
    """LLMs sometimes wrap JSON in prose or a code fence — pull the first
    JSON array/object out defensively rather than requiring exact output."""
    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        raise ValueError(f"No JSON found in LLM response: {raw[:200]!r}")
    return json.loads(match.group(0))


_GRAMMAR_SYSTEM = (
    "You are a meticulous copy editor. Find grammar, spelling, and mechanics "
    "issues an automated regex pass would miss (subject-verb agreement, "
    "misplaced modifiers, comma splices, wrong word choice). Do NOT flag "
    "stylistic/voice preferences — that's a separate check. Return ONLY a "
    "JSON array, each item: {\"severity\": \"minor\"|\"major\", \"problem\": "
    "str, \"fix\": str, \"snippet\": str}. Return [] if nothing found."
)


def llm_grammar_pass(text: str, llm_client: LLMClient, existing: list[Issue]) -> tuple[list[Issue], str]:
    """Returns (merged_issues, note). note is "" on success, or a
    plain-English degradation note on failure."""
    try:
        raw = llm_client.complete(system=_GRAMMAR_SYSTEM, user=text, max_tokens=1500)
        items = _extract_json(raw)
    except (LLMError, ValueError) as exc:
        return existing, f"LLM grammar pass skipped: {exc}"

    merged = list(existing)
    for item in items:
        merged.append(
            Issue(
                severity=item.get("severity", "minor"),
                problem=item.get("problem", ""),
                fix=item.get("fix", ""),
                snippet=item.get("snippet", ""),
                auto_fixable=False,  # LLM-found issues are always human-reviewed
            )
        )
    return merged, ""


_VOICE_SYSTEM = (
    "You compare a draft against a client's voice profile. Point out specific "
    "lines that drift from the profile's tone/reading-level/formatting rules "
    "and 'doesn't sound like us' examples, with a rewrite for each. Return "
    "ONLY a JSON array, each item: {\"line\": str, \"rewrite\": str, "
    "\"why\": str}. Return [] if the draft matches the voice well."
)


def llm_voice_pass(text: str, profile: VoiceProfile, llm_client: LLMClient, existing: VoiceResult) -> str:
    """Mutates `existing.llm_rewrites` in place and returns a degradation
    note ("" on success)."""
    profile_summary = (
        f"Tone words: {', '.join(profile.tone_words) or 'n/a'}\n"
        f"Reading level: {profile.reading_level or 'n/a'}\n"
        f"Formatting rules: {'; '.join(profile.formatting_rules) or 'n/a'}\n"
        f"Sounds like us: {'; '.join(profile.sounds_like_us) or 'n/a'}\n"
        f"Doesn't sound like us: {'; '.join(profile.doesnt_sound_like_us) or 'n/a'}"
    )
    user = f"VOICE PROFILE:\n{profile_summary}\n\nDRAFT:\n{text}"
    try:
        raw = llm_client.complete(system=_VOICE_SYSTEM, user=user, max_tokens=1500)
        items = _extract_json(raw)
    except (LLMError, ValueError) as exc:
        return f"LLM voice pass skipped: {exc}"

    existing.llm_rewrites = [
        {
            "line": item.get("line", ""),
            "rewrite": item.get("rewrite", ""),
            "why": item.get("why", ""),
        }
        for item in items
    ]
    if existing.llm_rewrites:
        existing.passed = False
    return ""


_FACT_SYSTEM = (
    "You judge whether a factual claim is supported by the provided "
    "evidence text (fetched from the client's own site). Be conservative: "
    "only VERIFIED if the evidence clearly supports it, only CONTRADICTED "
    "if the evidence clearly conflicts with it, otherwise UNVERIFIABLE. "
    "Never use outside knowledge — judge only from the evidence given. "
    "Return ONLY JSON: {\"verdict\": \"verified\"|\"unverifiable\"|"
    "\"contradicted\", \"reason\": str}."
)


def llm_fact_pass(claim: Claim, evidence_text: str, llm_client: LLMClient) -> FactResult:
    """One claim, one LLM judgment call. On failure, returns UNVERIFIABLE
    with the failure reason — never silently upgrades a claim to VERIFIED."""
    user = f"CLAIM:\n{claim.text}\n\nEVIDENCE:\n{evidence_text[:4000] or '(no evidence fetched)'}"
    try:
        raw = llm_client.complete(system=_FACT_SYSTEM, user=user, max_tokens=300)
        data = _extract_json(raw)
        verdict = FactVerdict(data.get("verdict", "unverifiable"))
        reason = data.get("reason", "")
    except (LLMError, ValueError, KeyError) as exc:
        return FactResult(claim=claim, verdict=FactVerdict.UNVERIFIABLE, reason=f"LLM check failed: {exc}")
    return FactResult(claim=claim, verdict=verdict, source="client site (LLM-judged)", reason=reason)
