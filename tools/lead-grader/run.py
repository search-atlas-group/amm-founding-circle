#!/usr/bin/env python3
"""Lead Grader — single entrypoint.

    python3 run.py --client acme                # import + grade + digest, all defaults
    python3 run.py --client acme wizard          # build the rubric first (do this once, per client)
    python3 run.py --client acme import --days 7
    python3 run.py --client acme grade
    python3 run.py --client acme digest --send

See README.md for setup.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lead_grader.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
