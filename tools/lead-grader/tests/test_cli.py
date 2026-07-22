"""CLI integration tests — exercise the real subcommands end to end
against a tmp clients dir + a tmp SQLite file + the fixture CallRail file,
with the LLM client swapped for a fake (no network, no real key needed)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lead_grader import cli


@pytest.fixture()
def clients_dir(tmp_path):
    d = tmp_path / "clients" / "acme"
    d.mkdir(parents=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump({"name": "Acme Roofing", "callrail_company_id": "CO900"})
    )
    (d / "rubric.md").write_text(
        "# Acme Roofing Rubric\n\nHot: ready to buy within 30 days.\nJunk: wrong number or solicitor."
    )
    return tmp_path / "clients"


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "leads.db"


def test_load_client_config_missing_client_exits(tmp_path):
    with pytest.raises(SystemExit):
        cli.load_client_config("nope", tmp_path / "clients")


def test_load_client_config_reads_yaml_and_stamps_slug(clients_dir):
    config = cli.load_client_config("acme", clients_dir)
    assert config["name"] == "Acme Roofing"
    assert config["slug"] == "acme"


def test_import_from_fixture_file_dedupes_on_rerun(clients_dir, db_path, tmp_path):
    sample_path = Path(__file__).resolve().parent.parent / "examples" / "sample_calls.json"
    args = cli.build_parser().parse_args(
        [
            "--client", "acme",
            "--clients-dir", str(clients_dir),
            "--db", str(db_path),
            "import",
            "--from-file", str(sample_path),
        ]
    )
    assert cli.cmd_import(args) == 0
    from lead_grader import store as store_mod

    conn = store_mod.connect(db_path)
    assert len(store_mod.all_leads(conn, "acme")) == 4

    # re-import the same file -> dedupe, no growth
    assert cli.cmd_import(args) == 0
    assert len(store_mod.all_leads(conn, "acme")) == 4


class _FakeLLM:
    model = "fake-model"

    def complete(self, system, user, max_tokens=800):
        if "roof" in user.lower() and "replacement" in user.lower():
            return '{"grade": "Hot", "reason": "Ready to buy this month.", "quote": "roof leak"}'
        if "pizza" in user.lower() or "wrong number" in user.lower():
            return '{"grade": "Junk", "reason": "Wrong number.", "quote": ""}'
        if "subcontract" in user.lower():
            return '{"grade": "Junk", "reason": "Vendor pitch, not a customer.", "quote": ""}'
        return '{"grade": "Weak", "reason": "Curious but no timeline.", "quote": ""}'


def _import(clients_dir, db_path):
    sample_path = Path(__file__).resolve().parent.parent / "examples" / "sample_calls.json"
    args = cli.build_parser().parse_args(
        [
            "--client", "acme",
            "--clients-dir", str(clients_dir),
            "--db", str(db_path),
            "import",
            "--from-file", str(sample_path),
        ]
    )
    cli.cmd_import(args)


def test_grade_command_grades_every_pending_lead(monkeypatch, clients_dir, db_path):
    monkeypatch.setattr(cli, "LLMClient", lambda: _FakeLLM())
    _import(clients_dir, db_path)

    args = cli.build_parser().parse_args(
        ["--client", "acme", "--clients-dir", str(clients_dir), "--db", str(db_path), "grade"]
    )
    assert cli.cmd_grade(args) == 0

    from lead_grader import store as store_mod

    conn = store_mod.connect(db_path)
    assert store_mod.ungraded_leads(conn, "acme") == []
    leads = store_mod.all_leads(conn, "acme")
    graded = {lead.id: lead for lead in leads}
    assert "CAL1001" in graded


def test_grade_command_fails_gracefully_with_no_rubric(monkeypatch, tmp_path, db_path):
    clients_dir = tmp_path / "clients" / "acme"
    clients_dir.mkdir(parents=True)
    (clients_dir / "config.yaml").write_text(yaml.safe_dump({"name": "Acme"}))
    monkeypatch.setattr(cli, "LLMClient", lambda: _FakeLLM())

    args = cli.build_parser().parse_args(
        ["--client", "acme", "--clients-dir", str(tmp_path / "clients"), "--db", str(db_path), "grade"]
    )
    assert cli.cmd_grade(args) == 1


def test_digest_command_writes_html_and_prints_summary(monkeypatch, clients_dir, db_path, tmp_path, capsys):
    monkeypatch.setattr(cli, "LLMClient", lambda: _FakeLLM())
    _import(clients_dir, db_path)

    grade_args = cli.build_parser().parse_args(
        ["--client", "acme", "--clients-dir", str(clients_dir), "--db", str(db_path), "grade"]
    )
    cli.cmd_grade(grade_args)

    out_dir = tmp_path / "output"
    digest_args = cli.build_parser().parse_args(
        [
            "--client", "acme",
            "--clients-dir", str(clients_dir),
            "--db", str(db_path),
            "digest",
            "--date", "2026-07-20",
            "--output-dir", str(out_dir),
        ]
    )
    assert cli.cmd_digest(digest_args) == 0
    captured = capsys.readouterr()
    assert "Graded 4 leads for Acme Roofing" in captured.out
    assert (out_dir / "digest-Acme Roofing-2026-07-20.html").exists()


def test_trend_command_reports_no_data_gracefully(db_path, capsys):
    args = cli.build_parser().parse_args(["--client", "acme", "--db", str(db_path), "trend"])
    assert cli.cmd_trend(args) == 0
    assert "No graded leads" in capsys.readouterr().out
