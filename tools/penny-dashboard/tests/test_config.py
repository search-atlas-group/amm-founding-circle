import textwrap
from pathlib import Path

import pytest

from penny_dashboard import config as cfg


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


@pytest.fixture
def config_dir(tmp_path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    return d


class TestScaffoldConfig:
    def test_copies_example_files_when_missing(self, config_dir):
        for name in cfg.REQUIRED_CONFIG_FILES:
            stem = name.rsplit(".", 1)[0]
            _write(config_dir / f"{stem}.example.yaml", "clients: []\n")

        created = cfg.scaffold_config(config_dir)

        assert len(created) == len(cfg.REQUIRED_CONFIG_FILES)
        for name in cfg.REQUIRED_CONFIG_FILES:
            assert (config_dir / name).exists()

    def test_never_overwrites_an_existing_file(self, config_dir):
        stem = "clients"
        _write(config_dir / f"{stem}.example.yaml", "clients: [{id: example}]\n")
        _write(config_dir / "clients.yaml", "clients: [{id: real-client}]\n")

        created = cfg.scaffold_config(config_dir)

        assert str(config_dir / "clients.yaml") not in created
        assert "real-client" in (config_dir / "clients.yaml").read_text()


class TestLoadClients:
    def test_missing_file_raises_config_error(self, config_dir):
        with pytest.raises(cfg.ConfigError):
            cfg.load_clients(config_dir)

    def test_merges_roster_and_billing(self, config_dir):
        _write(
            config_dir / "clients.yaml",
            """
            clients:
              - id: acme
                name: "Acme Roofing"
                google_ads_customer_id: null
                manual_spend_csv: "data/spend/acme.csv"
            """,
        )
        _write(
            config_dir / "billing.yaml",
            """
            clients:
              - id: acme
                retainer_usd: 2000
                hourly_rate_usd: 75
                ad_spend_markup:
                  type: percent
                  value: 10
            """,
        )

        clients = cfg.load_clients(config_dir)

        assert len(clients) == 1
        c = clients[0]
        assert c.client_id == "acme"
        assert c.name == "Acme Roofing"
        assert c.retainer_usd == 2000.0
        assert c.markup_rule.type == "percent"
        assert c.markup_rule.value == 10.0
        assert c.manual_spend_csv == "data/spend/acme.csv"

    def test_client_with_no_billing_entry_defaults_to_zero(self, config_dir):
        _write(config_dir / "clients.yaml", "clients: [{id: orphan, name: 'Orphan Co'}]\n")
        _write(config_dir / "billing.yaml", "clients: []\n")

        clients = cfg.load_clients(config_dir)

        assert clients[0].retainer_usd == 0.0
        assert clients[0].markup_rule.type == "none"


class TestLoadToolCosts:
    def test_returns_costs_and_overrides(self, config_dir):
        _write(
            config_dir / "tools-costs.yaml",
            """
            monthly_fixed_costs:
              - name: seat
                amount_usd: 300
                allocation: even
            per_client_overrides:
              acme:
                extra_costs_usd: 50
            """,
        )
        costs, overrides = cfg.load_tool_costs(config_dir)
        assert costs == [{"name": "seat", "amount_usd": 300, "allocation": "even"}]
        assert overrides == {"acme": {"extra_costs_usd": 50}}


class TestLoadVisibility:
    def test_returns_per_client_visibility(self, config_dir):
        _write(
            config_dir / "visibility.yaml",
            """
            clients:
              acme:
                visible_fields: [ad_spend_usd]
            """,
        )
        vis = cfg.load_visibility(config_dir)
        assert vis == {"acme": {"visible_fields": ["ad_spend_usd"]}}
