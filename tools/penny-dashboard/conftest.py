"""Make `penny_dashboard` importable from tests/ without installing it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
