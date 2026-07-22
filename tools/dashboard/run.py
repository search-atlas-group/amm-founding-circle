#!/usr/bin/env python3
"""Founding Circle Dashboard — one tabbed local page for all six tools.

    python3 run.py                  # start on http://127.0.0.1:58822 and open it
    python3 run.py --port 58900     # use a different port
    python3 run.py --no-browser     # start the server only, don't auto-open

Each tab shows that tool's own latest report. Click "Refresh" on a tab to
re-run that tool's own command (its normal `run.py`/CLI, with its demo
config out of the box) and pull the freshly generated report back in —
no full page reload. See README.md for what each tab needs to have real
data instead of the demo config it ships with.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path
from threading import Timer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard.server import serve  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AMM Founding Circle tools dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=58822)
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab.")
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        Timer(0.6, lambda: webbrowser.open(url)).start()

    serve(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
