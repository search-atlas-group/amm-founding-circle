"""clients.yaml loading + validation.

Deliberately has zero network calls — this module is pure parse-and-validate
so it's fully unit-testable against tmp files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .models import ClientConfig


class ConfigError(ValueError):
    """Raised for a malformed or incomplete clients.yaml."""


REQUIRED_CLIENT_FIELDS = ("name",)


def _require_list_of_str(value: Any, field_name: str, client_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"client '{client_name}': '{field_name}' must be a string or list of strings")
    return list(value)


def parse_clients(raw: dict[str, Any]) -> list[ClientConfig]:
    if not isinstance(raw, dict) or "clients" not in raw:
        raise ConfigError("clients.yaml must have a top-level 'clients:' list")
    clients_raw = raw["clients"]
    if not isinstance(clients_raw, list) or not clients_raw:
        raise ConfigError("'clients:' must be a non-empty list")

    clients: list[ClientConfig] = []
    seen_names: set[str] = set()
    for i, entry in enumerate(clients_raw):
        if not isinstance(entry, dict):
            raise ConfigError(f"clients[{i}] must be a mapping (dict)")
        for field_name in REQUIRED_CLIENT_FIELDS:
            if field_name not in entry or not str(entry[field_name]).strip():
                raise ConfigError(f"clients[{i}] is missing required field '{field_name}'")

        name = str(entry["name"]).strip()
        if name in seen_names:
            raise ConfigError(f"duplicate client name: '{name}'")
        seen_names.add(name)

        sites = _require_list_of_str(entry.get("sites"), "sites", name)
        for s in sites:
            if not (s.startswith("http://") or s.startswith("https://")):
                raise ConfigError(f"client '{name}': site '{s}' must include http:// or https://")

        tracking_paths = _require_list_of_str(
            entry.get("tracking_check_paths"), "tracking_check_paths", name
        ) or ["/"]

        known_exceptions = _require_list_of_str(
            entry.get("known_exceptions"), "known_exceptions", name
        )

        max_pages = entry.get("max_pages_per_site", 60)
        if not isinstance(max_pages, int) or max_pages < 1:
            raise ConfigError(f"client '{name}': 'max_pages_per_site' must be a positive integer")

        clients.append(
            ClientConfig(
                name=name,
                sites=sites,
                google_ads_customer_id=(str(entry["google_ads_customer_id"]).strip() or None)
                if entry.get("google_ads_customer_id")
                else None,
                meta_ad_account_id=(str(entry["meta_ad_account_id"]).strip() or None)
                if entry.get("meta_ad_account_id")
                else None,
                ga4_measurement_id=entry.get("ga4_measurement_id"),
                gtm_container_id=entry.get("gtm_container_id"),
                meta_pixel_id=entry.get("meta_pixel_id"),
                tracking_check_paths=tracking_paths,
                max_pages_per_site=max_pages,
                known_exceptions=known_exceptions,
            )
        )
    return clients


def load_clients_file(path: str | Path) -> list[ClientConfig]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"clients file not found: {p}\n"
            "Copy clients.example.yaml to clients.yaml and fill in your own client list."
        )
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return parse_clients(raw or {})


# --- .env-style credential loading (no python-dotenv dependency required,
# but we use it if it's already on the path — keeps requirements.txt lean).
def load_env_file(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(p, override=False)
        return
    except ImportError:
        pass
    # Minimal fallback parser — stdlib only.
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
