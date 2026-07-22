"""Config loading for the Penny Dashboard.

All config is plain YAML the non-technical owner edits by hand (or has
their agent edit for them). Real config files (without ".example" in the
name) are gitignored — they hold client cost/billing data that must never
land in the public repo, per this repo's own CONTRIBUTING.md rule
("Member/customer names, emails, or private status" — never commit).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from .margin import MarkupRule

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"

REQUIRED_CONFIG_FILES = ["clients.yaml", "billing.yaml", "tools-costs.yaml", "visibility.yaml"]


class ConfigError(Exception):
    pass


def scaffold_config(config_dir: Path = CONFIG_DIR) -> list[str]:
    """Copy every <name>.example.yaml to <name>.yaml if it doesn't exist yet.

    Returns the list of files created (empty if everything already existed).
    Never overwrites a file a member has already started filling in.
    """
    created = []
    for name in REQUIRED_CONFIG_FILES:
        target = config_dir / name
        stem = name.rsplit(".", 1)[0]
        example = config_dir / f"{stem}.example.yaml"
        if not target.exists() and example.exists():
            shutil.copy(example, target)
            created.append(str(target))
    return created


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(
            f"missing config file: {path}. Run `python3 run.py init` to scaffold it "
            "from the .example version, then fill in your real data."
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class ClientConfig:
    client_id: str
    name: str
    google_ads_customer_id: str | None
    manual_spend_csv: str | None
    hours_csv: str | None
    retainer_usd: float
    markup_rule: MarkupRule
    hourly_rate_usd: float


def load_clients(config_dir: Path = CONFIG_DIR) -> list[ClientConfig]:
    """Merge clients.yaml (roster) with billing.yaml (what they pay) into
    one ClientConfig per client, keyed by `id`."""
    clients_raw = _load_yaml(config_dir / "clients.yaml").get("clients", [])
    billing_raw = _load_yaml(config_dir / "billing.yaml").get("clients", [])
    billing_by_id = {c["id"]: c for c in billing_raw}

    clients = []
    for c in clients_raw:
        cid = c["id"]
        billing = billing_by_id.get(cid, {})
        markup = billing.get("ad_spend_markup", {}) or {}
        clients.append(
            ClientConfig(
                client_id=cid,
                name=c.get("name", cid),
                google_ads_customer_id=c.get("google_ads_customer_id") or None,
                manual_spend_csv=c.get("manual_spend_csv") or None,
                hours_csv=c.get("hours_csv") or None,
                retainer_usd=float(billing.get("retainer_usd", 0.0)),
                markup_rule=MarkupRule(
                    type=markup.get("type", "none"),
                    value=float(markup.get("value", 0.0)),
                ),
                hourly_rate_usd=float(billing.get("hourly_rate_usd", 0.0)),
            )
        )
    return clients


def load_tool_costs(config_dir: Path = CONFIG_DIR) -> tuple[list[dict], dict]:
    raw = _load_yaml(config_dir / "tools-costs.yaml")
    return raw.get("monthly_fixed_costs", []), raw.get("per_client_overrides", {})


def load_visibility(config_dir: Path = CONFIG_DIR) -> dict:
    raw = _load_yaml(config_dir / "visibility.yaml")
    return raw.get("clients", {})
