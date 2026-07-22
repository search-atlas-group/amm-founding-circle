import yaml

from outbound_engine.icp_wizard import build_icp_dict, write_icp


def test_build_icp_dict_from_answers():
    answers = {
        "business_name": "Test Agency",
        "what_we_sell": "SEO for local service businesses",
        "industries": "roofing, dental, legal",
        "min_employees": "5",
        "max_employees": "200",
        "geography": "United States",
        "trigger_signals": "visited pricing page, returned visitor",
        "exclude": "competitor agencies, current clients",
        "match_threshold": "75",
        "maybe_threshold": "45",
        "cost_comparison": "Replaces ~$700/mo Apollo spend",
    }
    icp = build_icp_dict(answers)
    assert icp["business"]["name"] == "Test Agency"
    assert icp["target"]["industries"] == ["roofing", "dental", "legal"]
    assert icp["target"]["company_size"] == {"min_employees": 5, "max_employees": 200}
    assert icp["scoring"]["match_threshold"] == 75.0
    assert icp["cost_comparison"] == "Replaces ~$700/mo Apollo spend"


def test_build_icp_dict_uses_sane_defaults_when_answers_missing():
    icp = build_icp_dict({"business_name": "Bare Agency"})
    assert icp["target"]["company_size"]["min_employees"] == 1
    assert icp["target"]["company_size"]["max_employees"] == 500
    assert icp["scoring"]["match_threshold"] == 70.0
    assert "cost_comparison" not in icp  # omitted entirely when blank, not written as ""


def test_write_icp_roundtrips_through_yaml(tmp_path):
    icp = build_icp_dict({"business_name": "Test Agency", "industries": "roofing"})
    path = write_icp(icp, tmp_path / "icp.yaml")
    assert path.exists()
    reloaded = yaml.safe_load(path.read_text())
    assert reloaded["business"]["name"] == "Test Agency"
    assert reloaded["target"]["industries"] == ["roofing"]
