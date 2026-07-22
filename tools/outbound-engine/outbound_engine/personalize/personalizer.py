"""
Personalization stage: turns an EnrichedProspect into a Draft (subject + body).

Every draft produced here is `pending_review` — nothing this module produces is
ever sent anywhere by itself. It only ever writes a row the review_queue then
shows a human (per SECURITY.md's own bar: "Skills sending outbound
communications... require explicit per-send approval").

Provider is pluggable via the `LLMClient` protocol:
  - `MockLLMClient` (default): deterministic template fill, zero network calls,
    zero API keys needed. This is what tests use and what runs out of the box.
  - `ClaudeCliClient` / `GeminiCliClient` (opt-in, `OUTBOUND_LLM_PROVIDER=claude`
    or `gemini`): shells out to the member's own already-authenticated local CLI
    session, same pattern as `automations/ai-news-feed` in this repo — no API
    key required for Claude Code subscription auth, no network credential ever
    stored by this tool. This still only *generates draft text*; it is not an
    outbound send.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional, Protocol

from ..models import Draft, EnrichedProspect

PROMPT_TEMPLATE = """You are drafting a short, personalized cold outreach email for a marketing \
agency. Use the voice examples below as a STYLE reference only — never copy their content or \
specific claims verbatim, and never invent facts about the prospect beyond what's given.

AGENCY VOICE EXAMPLES (for tone/style only):
{voice_examples}

PROSPECT:
- Company: {company_name}
- Contact: {contact_name} ({contact_role})
- Why they surfaced: {signal_reason}

Write:
1. A short subject line (under 60 chars, no clickbait, no ALL CAPS).
2. A 3-5 sentence email body: reference the specific reason they surfaced, offer one clear \
   next step (a short call), no generic filler, no fake urgency, no fabricated stats.

Return exactly two lines, no extra commentary:
SUBJECT: <subject>
BODY: <body>
"""


class LLMClient(Protocol):
    def generate(self, prompt: str) -> Optional[str]:
        """Return the raw model response, or None if the provider is unavailable
        (personalize() falls back to the mock templater in that case)."""
        ...


class MockLLMClient:
    """Deterministic, dependency-free templater. Always available; this is the
    default provider and what every test uses."""

    def generate(self, prompt: str) -> Optional[str]:
        return None  # signals "not a real generator" -> personalize() uses its own template


class ClaudeCliClient:
    """Shells out to the local `claude` CLI (Claude Code subscription auth,
    same pattern as automations/ai-news-feed/ai_news_feed.py). No API key
    required; no credentials are read, stored, or sent by this tool."""

    def __init__(self, model: str = "claude-sonnet-4-6", timeout_s: int = 60):
        self.model = model
        self.timeout_s = timeout_s

    def generate(self, prompt: str) -> Optional[str]:
        if not shutil.which("claude"):
            return None
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--model", self.model],
                capture_output=True, text=True, timeout=self.timeout_s,
            )
            return result.stdout.strip() or None
        except Exception:
            return None


class GeminiCliClient:
    """Shells out to the local `gemini` CLI, mirroring the same repo pattern."""

    def __init__(self, model: str = "gemini-2.5-flash", timeout_s: int = 60):
        self.model = model
        self.timeout_s = timeout_s

    def generate(self, prompt: str) -> Optional[str]:
        if not shutil.which("gemini"):
            return None
        try:
            result = subprocess.run(
                ["gemini", "-p", prompt, "-m", self.model],
                capture_output=True, text=True, timeout=self.timeout_s,
            )
            return result.stdout.strip() or None
        except Exception:
            return None


def build_client(provider: str) -> LLMClient:
    return {
        "claude": ClaudeCliClient(),
        "gemini": GeminiCliClient(),
    }.get(provider, MockLLMClient())


def _parse_subject_body(raw: str, fallback_company: str) -> tuple[str, str]:
    subject, body = "", ""
    for line in raw.splitlines():
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
        elif line.upper().startswith("BODY:"):
            body = line.split(":", 1)[1].strip()
    if not subject:
        subject = f"quick one about {fallback_company}"
    if not body:
        body = raw.strip()
    return subject, body


def _mock_draft(prospect: EnrichedProspect) -> Draft:
    """The zero-dependency fallback: a clean, honest template fill. This is what
    ships by default and what every test exercises."""
    signal = prospect.signal
    contact_first = (signal.contact_name or "there").split(" ")[0]
    subject = f"quick one about {signal.company_name}'s {signal.page_path or 'site'}"
    body = (
        f"Hey {contact_first},\n\n"
        f"Noticed {signal.company_name} recently checked out our "
        f"{signal.page_path or 'site'} ({prospect.signal_reason}) — figured I'd reach out "
        f"directly instead of waiting for a form-fill.\n\n"
        f"If it's useful, happy to do a quick 15-minute call and show what we'd actually do "
        f"for a business like yours, no deck required. Worth a look?\n\n"
        f"— [Your name]"
    )
    return Draft(
        prospect_id=prospect.prospect_id or 0,
        subject=subject,
        body=body,
        voice_notes="mock template (no LLM configured / OUTBOUND_LLM_PROVIDER=mock)",
    )


def personalize(prospect: EnrichedProspect, voice_examples: str = "", client: Optional[LLMClient] = None) -> Draft:
    """(EnrichedProspect, voice_examples) -> Draft. Falls back to the mock
    template if no client is given, the client is a MockLLMClient, or the real
    client returns None (CLI unavailable / call failed) — personalization
    NEVER raises just because a provider is missing."""
    client = client or MockLLMClient()
    signal = prospect.signal

    prompt = PROMPT_TEMPLATE.format(
        voice_examples=voice_examples.strip() or "(no voice examples supplied — use a plain, direct, professional tone)",
        company_name=signal.company_name,
        contact_name=signal.contact_name or "there",
        contact_role=signal.contact_role or "unknown role",
        signal_reason=prospect.signal_reason,
    )

    raw = client.generate(prompt)
    if raw is None:
        return _mock_draft(prospect)

    subject, body = _parse_subject_body(raw, signal.company_name)
    return Draft(
        prospect_id=prospect.prospect_id or 0,
        subject=subject,
        body=body,
        voice_notes=f"generated via {type(client).__name__}",
    )
