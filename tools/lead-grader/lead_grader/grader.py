"""The grading engine: rubric + lead artifact -> a Grade.

One LLM call per lead. Parsing is deliberately defensive — LLMs sometimes
wrap JSON in prose or a code fence, or emit a grade label that doesn't
exactly match one of the four buckets. This module never guesses a grade
it can't parse cleanly: an unparseable response fails closed to "Weak"
with a reason that says so, so a human reviews it rather than the lead
silently vanishing or getting rubber-stamped Hot.
"""
from __future__ import annotations

import json
import re
from typing import Protocol

from .schema import VALID_GRADES, Grade, Lead, normalize_grade_label

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

_NEEDS_REVIEW_REASON = "Could not confidently classify this lead — needs human review."

SYSTEM_PROMPT = """You are grading inbound leads for a marketing agency's client, \
against the client's own scoring rubric. You will be given the rubric and one lead \
artifact (a call transcript). Respond with ONLY a JSON object, no prose, no code \
fence, in exactly this shape:

{"grade": "Hot" | "Qualified" | "Weak" | "Junk", "reason": "<one sentence, plain English>", \
"quote": "<the single most telling quote from the transcript, or empty string if none>"}

Grade strictly against the rubric provided. If the transcript gives too little \
signal to be sure, choose "Weak" rather than guessing Hot or Junk."""


class LLMClientProtocol(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 800) -> str: ...


def build_user_prompt(rubric_text: str, lead: Lead) -> str:
    transcript = lead.transcript.strip() or "(no transcript available for this call)"
    return (
        f"CLIENT RUBRIC:\n{rubric_text.strip()}\n\n"
        f"LEAD ARTIFACT (source: {lead.source}, caller: {lead.caller or 'unknown'}, "
        f"duration: {lead.duration_seconds or 'unknown'}s):\n{transcript}"
    )


def grade_lead(lead: Lead, rubric_text: str, llm_client: LLMClientProtocol) -> Grade:
    """Grade one lead. Never raises on a bad/odd LLM response — falls back
    to a safe "Weak / needs human review" Grade instead."""
    if not lead.has_transcript():
        return Grade(
            lead_id=lead.id,
            client=lead.client,
            grade="Weak",
            reason="No transcript was available for this call — graded conservatively.",
            model=getattr(llm_client, "model", ""),
        )

    prompt = build_user_prompt(rubric_text, lead)
    raw_response = llm_client.complete(SYSTEM_PROMPT, prompt)
    return _parse_response(raw_response, lead, model=getattr(llm_client, "model", ""))


def _parse_response(raw_response: str, lead: Lead, model: str) -> Grade:
    parsed = _extract_json(raw_response)
    if parsed is None:
        return _needs_review_grade(lead, model, raw_response)

    grade_label = normalize_grade_label(parsed.get("grade"))
    if grade_label is None or grade_label not in VALID_GRADES:
        return _needs_review_grade(lead, model, raw_response)

    reason = str(parsed.get("reason") or "").strip() or _NEEDS_REVIEW_REASON
    # keep it a genuine one-liner even if the model rambles
    reason = reason.splitlines()[0][:280]
    quote = str(parsed.get("quote") or "").strip()

    return Grade(
        lead_id=lead.id,
        client=lead.client,
        grade=grade_label,
        reason=reason,
        quote=quote,
        model=model,
    )


def _needs_review_grade(lead: Lead, model: str, raw_response: str) -> Grade:
    return Grade(
        lead_id=lead.id,
        client=lead.client,
        grade="Weak",
        reason=_NEEDS_REVIEW_REASON,
        quote=raw_response.strip()[:200],
        model=model,
    )


def _extract_json(raw_response: str) -> dict | None:
    if not raw_response or not raw_response.strip():
        return None
    text = raw_response.strip()
    # strip a markdown code fence if the model added one anyway
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None
