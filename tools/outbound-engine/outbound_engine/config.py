"""Environment + ICP config loading. Zero network calls — pure parse/validate,
so it's fully unit-testable against tmp files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised for missing/malformed config."""


def load_env(env_path: str | Path | None = None) -> None:
    """Load a local .env into os.environ, if present. Uses python-dotenv when
    installed (never `source`); silently no-ops if the file is absent — this
    tool works with zero .env at all in --dry-run mode."""
    path = Path(env_path) if env_path else Path.cwd() / ".env"
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=path, override=False)
    except ImportError:
        # Minimal fallback parser — KEY=VALUE lines, '#' comments, no export/quote handling.
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_icp(icp_path: str | Path) -> dict[str, Any]:
    """Load and lightly validate an ICP definition yaml (see config/icp.example.yaml)."""
    path = Path(icp_path)
    if not path.exists():
        raise ConfigError(
            f"ICP file not found: {path}. Run `python3 run.py wizard` to build one, "
            f"or copy config/icp.example.yaml to config/icp.yaml and edit it."
        )
    with path.open() as f:
        raw = yaml.safe_load(f) or {}

    for section in ("target", "scoring"):
        if section not in raw:
            raise ConfigError(f"icp.yaml is missing the '{section}:' section")

    scoring = raw["scoring"]
    for key in ("match_threshold", "maybe_threshold"):
        if key not in scoring:
            raise ConfigError(f"icp.yaml scoring: is missing '{key}'")

    return raw


def load_voice_examples(path: str | Path) -> str:
    """Read the raw voice-examples markdown (used as personalization style reference,
    never copied verbatim). Returns '' if the file doesn't exist yet — personalization
    just falls back to a neutral, professional default voice."""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text()


class Settings:
    """Resolved runtime settings — env vars with safe, documented defaults.

    NOTE ON LIVE MODE: `smartlead_live_mode` and `visual_visitor_live_mode` are read
    from the environment but this build's load/signal adapters DELIBERATELY ignore
    a `true` value and refuse with a clear error (see load/smartlead.py and
    signals/visual_visitor.py). Flipping them here does nothing until a future,
    JD-approved build wires the real API calls. Do not "fix" that refusal without
    that approval — see README "Live mode" section.
    """

    def __init__(self, db_path: str | Path = "outbound_engine.db"):
        self.db_path = str(db_path)
        self.smartlead_api_key = os.environ.get("SMARTLEAD_API_KEY", "")
        self.smartlead_live_mode = os.environ.get("SMARTLEAD_LIVE_MODE", "false").lower() == "true"
        self.visual_visitor_api_key = os.environ.get("VISUAL_VISITOR_API_KEY", "")
        self.visual_visitor_live_mode = os.environ.get("VISUAL_VISITOR_LIVE_MODE", "false").lower() == "true"
        self.llm_provider = os.environ.get("OUTBOUND_LLM_PROVIDER", "mock")  # mock | claude | gemini
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
