"""Shared test fixtures for lead-grader.

Ensures the package under test (``lead_grader/``) is importable regardless
of which directory pytest is invoked from, without requiring an install
step (`pip install -e .`) that a non-technical member wouldn't run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402


@pytest.fixture()
def sample_calls_raw() -> list[dict]:
    """The raw CallRail-shaped payload used across adapter/store/grader tests."""
    path = ROOT / "examples" / "sample_calls.json"
    return json.loads(path.read_text())["calls"]
