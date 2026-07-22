import pytest

from bug_hunter.config import ConfigError, parse_clients


def test_parse_clients_minimal_valid():
    raw = {"clients": [{"name": "Acme", "sites": ["https://acme.com"]}]}
    clients = parse_clients(raw)
    assert len(clients) == 1
    assert clients[0].name == "Acme"
    assert clients[0].sites == ["https://acme.com"]
    assert clients[0].tracking_check_paths == ["/"]  # default applied
    assert clients[0].max_pages_per_site == 60  # default applied


def test_parse_clients_missing_top_level_key_raises():
    with pytest.raises(ConfigError):
        parse_clients({"not_clients": []})


def test_parse_clients_empty_list_raises():
    with pytest.raises(ConfigError):
        parse_clients({"clients": []})


def test_parse_clients_missing_name_raises():
    with pytest.raises(ConfigError, match="name"):
        parse_clients({"clients": [{"sites": ["https://acme.com"]}]})


def test_parse_clients_duplicate_name_raises():
    raw = {
        "clients": [
            {"name": "Acme", "sites": ["https://acme.com"]},
            {"name": "Acme", "sites": ["https://other.com"]},
        ]
    }
    with pytest.raises(ConfigError, match="duplicate"):
        parse_clients(raw)


def test_parse_clients_site_without_scheme_raises():
    raw = {"clients": [{"name": "Acme", "sites": ["acme.com"]}]}
    with pytest.raises(ConfigError, match="http"):
        parse_clients(raw)


def test_parse_clients_single_site_as_string_is_normalized_to_list():
    raw = {"clients": [{"name": "Acme", "sites": "https://acme.com"}]}
    clients = parse_clients(raw)
    assert clients[0].sites == ["https://acme.com"]


def test_parse_clients_known_exceptions_and_optional_fields():
    raw = {
        "clients": [
            {
                "name": "Acme",
                "sites": ["https://acme.com"],
                "google_ads_customer_id": "123-456-7890",
                "ga4_measurement_id": "G-ABC123",
                "known_exceptions": ["acme/tracking/*"],
                "max_pages_per_site": 10,
            }
        ]
    }
    clients = parse_clients(raw)
    c = clients[0]
    assert c.google_ads_customer_id == "123-456-7890"
    assert c.ga4_measurement_id == "G-ABC123"
    assert c.known_exceptions == ["acme/tracking/*"]
    assert c.max_pages_per_site == 10


def test_parse_clients_invalid_max_pages_raises():
    raw = {"clients": [{"name": "Acme", "sites": ["https://acme.com"], "max_pages_per_site": 0}]}
    with pytest.raises(ConfigError, match="max_pages_per_site"):
        parse_clients(raw)


def test_load_clients_file_missing_file_raises(tmp_path):
    from bug_hunter.config import load_clients_file

    with pytest.raises(ConfigError, match="not found"):
        load_clients_file(tmp_path / "does-not-exist.yaml")


def test_load_clients_file_reads_yaml(tmp_path):
    from bug_hunter.config import load_clients_file

    p = tmp_path / "clients.yaml"
    p.write_text(
        """
clients:
  - name: Acme
    sites:
      - https://acme.com
""".strip()
    )
    clients = load_clients_file(p)
    assert clients[0].name == "Acme"


def test_load_env_file_sets_environ_without_overriding_existing(tmp_path, monkeypatch):
    from bug_hunter.config import load_env_file

    monkeypatch.delenv("BUGHUNTER_TEST_VAR", raising=False)
    monkeypatch.setenv("BUGHUNTER_TEST_PRESET", "already-set")

    p = tmp_path / ".env"
    p.write_text('BUGHUNTER_TEST_VAR=hello\nBUGHUNTER_TEST_PRESET=should-not-override\n# a comment\n\n')

    load_env_file(p)

    import os

    assert os.environ["BUGHUNTER_TEST_VAR"] == "hello"
    assert os.environ["BUGHUNTER_TEST_PRESET"] == "already-set"
