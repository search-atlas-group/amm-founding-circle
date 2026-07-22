"""LLMClient tests — provider selection + request shape, no real network."""
from __future__ import annotations

import pytest

from lead_grader.llm import LLMClient, LLMConfigError


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    def post(self, url, headers=None, json=None):
        self.last_request = {"url": url, "headers": headers, "json": json}
        return _FakeResp(self.payload)


def test_raises_clear_error_with_no_key_configured(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMConfigError):
        LLMClient()


def test_prefers_anthropic_when_both_keys_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o-key")
    session = _FakeSession({"content": [{"type": "text", "text": "hi"}]})
    client = LLMClient(session=session)
    assert client.provider == "anthropic"
    out = client.complete("sys", "user")
    assert out == "hi"
    assert "anthropic.com" in session.last_request["url"]
    assert session.last_request["headers"]["x-api-key"] == "a-key"


def test_falls_back_to_openrouter_when_only_that_key_present(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "o-key")
    session = _FakeSession({"choices": [{"message": {"content": "graded"}}]})
    client = LLMClient(session=session)
    assert client.provider == "openrouter"
    out = client.complete("sys", "user")
    assert out == "graded"
    assert "openrouter.ai" in session.last_request["url"]
    assert session.last_request["headers"]["Authorization"] == "Bearer o-key"


def test_openrouter_empty_choices_returns_empty_string(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "o-key")
    session = _FakeSession({"choices": []})
    client = LLMClient(session=session)
    assert client.complete("sys", "user") == ""


def test_explicit_provider_and_key_override_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    session = _FakeSession({"content": [{"type": "text", "text": "ok"}]})
    client = LLMClient(provider="anthropic", api_key="explicit-key", session=session)
    client.complete("sys", "user")
    assert session.last_request["headers"]["x-api-key"] == "explicit-key"
