import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
TOOL_ROOT = HERE.parent
sys.path.insert(0, str(TOOL_ROOT))

from outbound_engine.db import Store  # noqa: E402


@pytest.fixture
def sample_icp() -> dict:
    return {
        "business": {"name": "Test Agency", "what_we_sell": "SEO for local service businesses"},
        "target": {
            "industries": ["roofing", "dental", "legal"],
            "company_size": {"min_employees": 5, "max_employees": 200},
            "geography": ["United States"],
            "trigger_signals": ["visited pricing page"],
            "exclude": ["competitor agencies", "current clients"],
        },
        "scoring": {
            "match_threshold": 70,
            "maybe_threshold": 40,
            "weights": {
                "industry_match": 35,
                "size_match": 20,
                "geography_match": 15,
                "trigger_signal_strength": 30,
            },
        },
        "cost_comparison": "Replaces ~$700/mo Apollo + Hunter.io spend",
    }


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()
