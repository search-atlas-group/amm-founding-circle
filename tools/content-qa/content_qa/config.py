"""config.py — env loading and client-profile path resolution.

Zero-install by design: the tool runs fully offline with no pip installs.
`load_env()` prefers `python-dotenv` (the org-standard loader — see
requirements.txt) but falls back to a tiny built-in parser if it isn't
installed, so "one copy-paste command" still works on a bare clone.

Never `source` a .env file. Never print or log a loaded value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(env_path: Path | str = ".env") -> None:
    """Load key=value pairs from env_path into os.environ (does not override
    values already set in the real environment). Silently no-ops if the file
    doesn't exist — the tool falls back to whatever's already exported.
    """
    env_path = Path(env_path)

    try:
        from dotenv import load_dotenv as _load  # type: ignore

        if env_path.exists():
            _load(dotenv_path=env_path, override=False)
        return
    except ImportError:
        pass

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class LLMSettings:
    """Resolved from the environment. `provider`/`api_key` are None when no
    key is configured — callers must treat that as "run offline-only", never
    guess or fabricate a key."""

    provider: str | None
    api_key: str | None
    model: str | None


def resolve_llm_settings() -> LLMSettings:
    """Anthropic wins if both are set (documented in .env.example); either
    alone is fine. Returns provider=None, api_key=None when neither is set —
    the caller must degrade to offline-only checks, not error out.
    """
    provider_override = os.environ.get("LLM_PROVIDER", "").strip().lower() or None
    model = os.environ.get("LLM_MODEL", "").strip() or None

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or None
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip() or None

    if provider_override == "openrouter" and openrouter_key:
        return LLMSettings("openrouter", openrouter_key, model)
    if provider_override == "anthropic" and anthropic_key:
        return LLMSettings("anthropic", anthropic_key, model)

    if anthropic_key:
        return LLMSettings("anthropic", anthropic_key, model)
    if openrouter_key:
        return LLMSettings("openrouter", openrouter_key, model)

    return LLMSettings(None, None, model)


def client_profile_path(client_slug: str, profiles_dir: Path | str = "clients") -> Path:
    """Where a client's voice-profile.md lives: <profiles_dir>/<slug>/voice-profile.md"""
    return Path(profiles_dir) / client_slug / "voice-profile.md"
