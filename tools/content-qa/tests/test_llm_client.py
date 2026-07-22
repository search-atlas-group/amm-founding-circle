import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.llm_client import LLMClient, LLMError, client_from_settings
from content_qa.config import LLMSettings


def _fake_response(payload: dict):
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.__exit__.return_value = False
    mock.read.return_value = json.dumps(payload).encode("utf-8")
    return mock


class TestLLMClientConstruction(unittest.TestCase):
    def test_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):
            LLMClient(provider="bogus", api_key="x")

    def test_defaults_model_per_provider(self):
        anthropic = LLMClient(provider="anthropic", api_key="x")
        openrouter = LLMClient(provider="openrouter", api_key="x")
        self.assertTrue(anthropic.model)
        self.assertTrue(openrouter.model)
        self.assertNotEqual(anthropic.model, openrouter.model)

    def test_explicit_model_is_kept(self):
        client = LLMClient(provider="anthropic", api_key="x", model="claude-custom")
        self.assertEqual(client.model, "claude-custom")


class TestClientFromSettings(unittest.TestCase):
    def test_none_when_no_provider(self):
        self.assertIsNone(client_from_settings(LLMSettings(None, None, None)))

    def test_none_when_no_key(self):
        self.assertIsNone(client_from_settings(LLMSettings("anthropic", None, None)))

    def test_builds_client_when_configured(self):
        client = client_from_settings(LLMSettings("anthropic", "sk-test", None))
        self.assertIsInstance(client, LLMClient)
        self.assertEqual(client.provider, "anthropic")


class TestAnthropicComplete(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_extracts_text_from_content_blocks(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"content": [{"type": "text", "text": "Hello "}, {"type": "text", "text": "world"}]}
        )
        client = LLMClient(provider="anthropic", api_key="sk-test")
        result = client.complete(system="sys", user="hi")
        self.assertEqual(result, "Hello world")

    @patch("urllib.request.urlopen")
    def test_raises_llm_error_on_unexpected_shape(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response({"unexpected": "shape"})
        client = LLMClient(provider="anthropic", api_key="sk-test")
        with self.assertRaises(LLMError):
            client.complete(system="sys", user="hi")


class TestOpenRouterComplete(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_extracts_text_from_choices(self, mock_urlopen):
        mock_urlopen.return_value = _fake_response(
            {"choices": [{"message": {"content": "response text"}}]}
        )
        client = LLMClient(provider="openrouter", api_key="sk-test")
        result = client.complete(system="sys", user="hi")
        self.assertEqual(result, "response text")


if __name__ == "__main__":
    unittest.main()
