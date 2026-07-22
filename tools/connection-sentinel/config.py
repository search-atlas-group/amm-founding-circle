"""Load and validate connections.yaml.

Resolves ${ENV_VAR} placeholders from the process environment. Real
credentials never live in the yaml file itself -- only ${VAR_NAME}
references, resolved from a .env the caller loads with python-dotenv
(never `source`, per this repo's python-style convention).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import yaml

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

REQUIRED_BY_TYPE = {
    "http": ["url"],
    "mcp_http": ["url"],
    "command": ["command"],
}


class ConfigError(Exception):
    """Raised for anything wrong with connections.yaml -- always with a
    plain-English, actionable message (this tool is used by non-engineers)."""


def _interpolate(value, env):
    if isinstance(value, str):
        def sub(match):
            var = match.group(1)
            if var not in env:
                raise ConfigError(
                    f"connections.yaml references ${{{var}}} but it isn't set in "
                    f"your environment/.env. Add {var}=... to your .env and try again."
                )
            return env[var]
        return _VAR_RE.sub(sub, value)
    if isinstance(value, dict):
        return {k: _interpolate(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v, env) for v in value]
    return value


@dataclass
class Connection:
    name: str
    type: str
    url: str = ""
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    body: dict | None = None
    command: str = ""
    timeout: int = 8


@dataclass
class NotifyConfig:
    email_enabled: bool = False
    email_to: str = ""
    macos_enabled: bool = True
    daily_heartbeat: bool = False


@dataclass
class SentinelConfig:
    connections: list
    notify: NotifyConfig


def load_connections(path: str, env: dict | None = None) -> SentinelConfig:
    """Read + validate connections.yaml at `path`. `env` defaults to the real
    process environment; tests pass an explicit dict so they never depend on
    (or pollute) the caller's actual environment."""
    env = os.environ if env is None else env
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    raw = _interpolate(raw, env)

    notify_raw = raw.get("notify") or {}
    email_raw = notify_raw.get("email") or {}
    macos_raw = notify_raw.get("macos") or {}
    notify = NotifyConfig(
        email_enabled=bool(email_raw.get("enabled", False)),
        email_to=email_raw.get("to", ""),
        macos_enabled=bool(macos_raw.get("enabled", True)),
        daily_heartbeat=bool(notify_raw.get("daily_heartbeat", False)),
    )

    conns_raw = raw.get("connections") or []
    if not conns_raw:
        raise ConfigError(
            "connections.yaml has no 'connections:' entries -- nothing to watch. "
            "Copy connections.example.yaml and uncomment at least one."
        )

    names_seen = set()
    connections = []
    for i, c in enumerate(conns_raw):
        name = c.get("name")
        ctype = c.get("type")
        if not name:
            raise ConfigError(f"connections[{i}] is missing 'name'.")
        if name in names_seen:
            raise ConfigError(f"Duplicate connection name: {name!r} -- names must be unique.")
        names_seen.add(name)
        if ctype not in REQUIRED_BY_TYPE:
            raise ConfigError(
                f"{name!r}: unknown type {ctype!r}. Must be one of: "
                f"{', '.join(REQUIRED_BY_TYPE)}."
            )
        for required_field in REQUIRED_BY_TYPE[ctype]:
            if not c.get(required_field):
                raise ConfigError(
                    f"{name!r} (type={ctype}) is missing required field {required_field!r}."
                )
        connections.append(Connection(
            name=name,
            type=ctype,
            url=c.get("url", ""),
            method=c.get("method", "GET"),
            headers=c.get("headers") or {},
            body=c.get("body"),
            command=c.get("command", ""),
            timeout=c.get("timeout", 8),
        ))

    return SentinelConfig(connections=connections, notify=notify)
