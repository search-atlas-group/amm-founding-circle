import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("version_check.py")


def run(tmp_path, inventory, advisory):
    inv = tmp_path / "inventory.json"
    adv = tmp_path / "advisory.json"
    inv.write_text(json.dumps(inventory))
    adv.write_text(json.dumps(advisory))
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--inventory", str(inv), "--advisory", str(adv)],
        capture_output=True, text=True,
    )


def test_in_range_and_out_of_range(tmp_path):
    result = run(tmp_path, {
        "components": [
            {"name": "php", "version": "8.2.4"},
            {"name": "wordpress", "version": "6.4.1"},
        ],
    }, {
        "id": "ADV-1",
        "affected": [
            {"name": "php", "range": ">=8.2.0,<8.2.10"},
            {"name": "wordpress", "range": "<6.4.0"},
        ],
    })
    report = json.loads(result.stdout)
    assert result.returncode == 0
    assert report["rows"][0]["status"] == "in-range"
    assert report["rows"][1]["status"] == "out-of-range"


def test_missing_component_is_not_safe(tmp_path):
    result = run(tmp_path, {"components": []}, {
        "id": "ADV-2",
        "affected": [{"name": "php", "range": "<8.3.0"}],
    })
    report = json.loads(result.stdout)
    assert report["rows"][0]["status"] == "not-present"
    assert "safe" not in result.stdout.lower()


def test_unreadable_version_is_unknown(tmp_path):
    result = run(tmp_path, {"components": [{"name": "php", "version": "UNKNOWN"}]}, {
        "id": "ADV-3",
        "affected": [{"name": "php", "range": "<8.3.0"}],
    })
    assert result.returncode == 2
    assert json.loads(result.stdout)["rows"][0]["status"] == "UNKNOWN"


def test_bad_input_exits_2(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--inventory", str(tmp_path / "missing.json"), "--advisory", str(tmp_path / "missing.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert result.stdout.startswith("UNKNOWN")
