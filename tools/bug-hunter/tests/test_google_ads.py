from bug_hunter.models import ClientConfig
from bug_hunter.google_ads import (
    check_ads_and_campaigns,
    classify_ad_approval,
    classify_campaign_status,
    classify_final_url_status,
)


def test_classify_ad_approval_disapproved_is_critical():
    row = {
        "ad_id": "111",
        "ad_name": "Spring Sale",
        "approval_status": "DISAPPROVED",
        "campaign_name": "Spring Campaign",
        "ad_group_name": "Ad Group 1",
    }
    f = classify_ad_approval("Acme", row)
    assert f is not None
    assert f.severity.value == "critical"
    assert "Spring Campaign" in f.location


def test_classify_ad_approval_approved_returns_none():
    row = {"approval_status": "APPROVED"}
    assert classify_ad_approval("Acme", row) is None


def test_classify_campaign_status_paused_is_degrading():
    f = classify_campaign_status("Acme", {"campaign_name": "Q3 Promo", "campaign_status": "PAUSED"})
    assert f is not None
    assert f.severity.value == "degrading"
    assert f.location == "Q3 Promo"


def test_classify_campaign_status_enabled_returns_none():
    assert classify_campaign_status("Acme", {"campaign_name": "X", "campaign_status": "ENABLED"}) is None


def test_classify_final_url_status_broken_is_critical():
    row = {"ad_id": "1", "campaign_name": "C", "ad_group_name": "AG"}
    f = classify_final_url_status("Acme", row, "https://acme.com/landing", 404)
    assert f is not None
    assert f.severity.value == "critical"
    assert "spending money" in f.detail


def test_classify_final_url_status_ok_returns_none():
    row = {"ad_id": "1", "campaign_name": "C", "ad_group_name": "AG"}
    assert classify_final_url_status("Acme", row, "https://acme.com/landing", 200) is None


def test_check_ads_and_campaigns_end_to_end():
    client = ClientConfig(name="Acme", sites=["https://acme.com"])
    ad_rows = [
        {
            "ad_id": "1",
            "ad_name": "Ad A",
            "approval_status": "DISAPPROVED",
            "status": "ENABLED",
            "final_urls": ["https://acme.com/a"],
            "campaign_name": "Campaign A",
            "ad_group_name": "AG A",
        },
        {
            "ad_id": "2",
            "ad_name": "Ad B",
            "approval_status": "APPROVED",
            "status": "ENABLED",
            "final_urls": ["https://acme.com/broken"],
            "campaign_name": "Campaign B",
            "ad_group_name": "AG B",
        },
        {
            "ad_id": "3",
            "ad_name": "Ad C (paused, shouldn't be checked)",
            "approval_status": "APPROVED",
            "status": "PAUSED",
            "final_urls": ["https://acme.com/also-broken-but-paused"],
            "campaign_name": "Campaign C",
            "ad_group_name": "AG C",
        },
    ]
    campaign_rows = [
        {"campaign_name": "Campaign A", "campaign_status": "ENABLED"},
        {"campaign_name": "Campaign D", "campaign_status": "PAUSED"},
    ]

    def fake_status(url: str) -> int:
        return 404 if "broken" in url else 200

    findings = check_ads_and_campaigns(client, ad_rows, campaign_rows, fake_status)
    titles = [f.title for f in findings]

    assert "Disapproved ad" in titles
    assert titles.count("Ad final URL is broken") == 1  # only the ENABLED broken ad, not the paused one
    assert "Campaign is paused" in titles
    paused_findings = [f for f in findings if f.title == "Campaign is paused"]
    assert paused_findings[0].location == "Campaign D"
