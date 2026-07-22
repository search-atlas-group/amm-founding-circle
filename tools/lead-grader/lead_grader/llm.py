"""A minimal, provider-agnostic LLM client for the grader and rubric wizard.

Members bring their own key (`ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY`
in `.env`) — this module has no repo-side model spend and no SearchAtlas
gateway dependency (that mandate governs SearchAtlas's own internal apps,
not a member's own agency tool run with their own credentials).

Uses plain HTTP (`requests`) instead of a provider SDK so both providers
share one thin client and tests can inject a fake `session.post` with no
network access and no SDK installed.
"""
from __future__ import annotations

import os
from typing import Any, Optional


class LLMConfigError(RuntimeError):
    """Raised when no usable provider/key is configured."""


class LLMClient:
    """Chat-completion client for Anthropic or OpenRouter, selected by
    whichever API key is present in the environment (Anthropic preferred)."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        session: Any = None,
    ):
        self.provider = provider or _detect_provider()
        self.api_key = api_key or _key_for(self.provider)
        if not self.api_key:
            raise LLMConfigError(
                "No LLM key found. Set ANTHROPIC_API_KEY or OPENROUTER_API_KEY in .env "
                "(see .env.example)."
            )
        self.model = model or _default_model(self.provider)
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        """Return the raw text response for one system+user turn."""
        if self.provider == "anthropic":
            return self._complete_anthropic(system, user, max_tokens)
        return self._complete_openrouter(system, user, max_tokens)

    # -- providers --------------------------------------------------------

    def _complete_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        resp = self.session.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        blocks = payload.get("content", [])
        return "".join(b.get("text", "") for b in blocks if isinstance(b, dict))

    def _complete_openrouter(self, system: str, user: str, max_tokens: int) -> str:
        resp = self.session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        choices = payload.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")


def _detect_provider() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    return "anthropic"  # default; will raise LLMConfigError with no key present


def _key_for(provider: str) -> Optional[str]:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    return os.environ.get("OPENROUTER_API_KEY")


def _default_model(provider: str) -> str:
    if provider == "anthropic":
        return os.environ.get("LEAD_GRADER_MODEL", "claude-sonnet-4-6")
    return os.environ.get("LEAD_GRADER_MODEL", "anthropic/claude-sonnet-4-6")
