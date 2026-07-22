"""llm_client.py — thin, dependency-free client for the two LLM providers
the AMM cohort actually uses (per config.py's resolve_llm_settings): the
member's own Anthropic key, or their own OpenRouter key. No SDK — plain
`urllib.request` so the tool needs zero pip installs even with LLM layers on.

Every call is a single request/response completion. No streaming, no tool
use, no state — the check layers only need "give me structured judgment
text back."
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"


class LLMError(RuntimeError):
    """Raised on a failed LLM call. Callers must catch this and degrade to
    the offline-only result for that layer — never crash the whole QA run
    over one flaky network call."""


@dataclass
class LLMClient:
    provider: str  # "anthropic" | "openrouter"
    api_key: str
    model: str | None = None
    timeout: float = 45.0

    def __post_init__(self) -> None:
        if self.provider not in ("anthropic", "openrouter"):
            raise ValueError(f"Unknown LLM provider: {self.provider!r}")
        if not self.model:
            self.model = (
                _DEFAULT_ANTHROPIC_MODEL if self.provider == "anthropic" else _DEFAULT_OPENROUTER_MODEL
            )

    def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        """One-shot completion. Returns the raw text response. Raises
        LLMError on any failure — never returns an empty string silently
        (which callers might mistake for "no issues found")."""
        if self.provider == "anthropic":
            return self._complete_anthropic(system, user, max_tokens)
        return self._complete_openrouter(system, user, max_tokens)

    def _post_json(self, url: str, headers: dict, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise LLMError(f"{self.provider} API returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"{self.provider} API call failed: {exc}") from exc

    def _complete_anthropic(self, system: str, user: str, max_tokens: int) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = self._post_json(_ANTHROPIC_URL, headers, payload)
        try:
            return "".join(block.get("text", "") for block in data["content"])
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Anthropic response shape: {data!r}") from exc

    def _complete_openrouter(self, system: str, user: str, max_tokens: int) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = self._post_json(_OPENROUTER_URL, headers, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected OpenRouter response shape: {data!r}") from exc


def client_from_settings(settings) -> LLMClient | None:
    """settings: content_qa.config.LLMSettings. Returns None (never a fake
    client) when no key is configured — callers must branch on this."""
    if not settings.provider or not settings.api_key:
        return None
    return LLMClient(provider=settings.provider, api_key=settings.api_key, model=settings.model)
