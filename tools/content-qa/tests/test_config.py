import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_qa.config import client_profile_path, load_env, resolve_llm_settings


class TestLoadEnvFallbackParser(unittest.TestCase):
    """Exercises the built-in fallback path (as if python-dotenv weren't
    installed) since that's the zero-install guarantee this tool makes."""

    def setUp(self):
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_loads_simple_key_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("ANTHROPIC_API_KEY=sk-test-123\n")
            os.environ.pop("ANTHROPIC_API_KEY", None)
            load_env(env_path)
            self.assertEqual(os.environ.get("ANTHROPIC_API_KEY"), "sk-test-123")

    def test_ignores_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("# a comment\n\nOPENROUTER_API_KEY=abc\n")
            os.environ.pop("OPENROUTER_API_KEY", None)
            load_env(env_path)
            self.assertEqual(os.environ.get("OPENROUTER_API_KEY"), "abc")

    def test_strips_surrounding_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text('LLM_MODEL="claude-sonnet-4-5"\n')
            os.environ.pop("LLM_MODEL", None)
            load_env(env_path)
            self.assertEqual(os.environ.get("LLM_MODEL"), "claude-sonnet-4-5")

    def test_missing_file_is_a_silent_noop(self):
        load_env("/tmp/definitely-does-not-exist-content-qa.env")  # must not raise

    def test_never_overrides_real_env_var(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("ANTHROPIC_API_KEY=from-file\n")
            os.environ["ANTHROPIC_API_KEY"] = "from-real-shell"
            load_env(env_path)
            self.assertEqual(os.environ.get("ANTHROPIC_API_KEY"), "from-real-shell")


class TestResolveLLMSettings(unittest.TestCase):
    def setUp(self):
        self._saved = dict(os.environ)
        for key in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "LLM_PROVIDER", "LLM_MODEL"):
            os.environ.pop(key, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_no_keys_returns_none_provider(self):
        settings = resolve_llm_settings()
        self.assertIsNone(settings.provider)
        self.assertIsNone(settings.api_key)

    def test_anthropic_key_alone_selects_anthropic(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant"
        settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "anthropic")
        self.assertEqual(settings.api_key, "sk-ant")

    def test_openrouter_key_alone_selects_openrouter(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or"
        settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "openrouter")

    def test_both_keys_anthropic_wins_by_default(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant"
        os.environ["OPENROUTER_API_KEY"] = "sk-or"
        settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "anthropic")

    def test_explicit_provider_override_honored(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant"
        os.environ["OPENROUTER_API_KEY"] = "sk-or"
        os.environ["LLM_PROVIDER"] = "openrouter"
        settings = resolve_llm_settings()
        self.assertEqual(settings.provider, "openrouter")


class TestClientProfilePath(unittest.TestCase):
    def test_builds_expected_path(self):
        path = client_profile_path("acme", "clients")
        self.assertEqual(path, Path("clients") / "acme" / "voice-profile.md")


if __name__ == "__main__":
    unittest.main()
