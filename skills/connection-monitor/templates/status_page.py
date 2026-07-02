#!/usr/bin/env python3
"""status_page.py — render the tiny local connection-status page.

One self-contained HTML file, light-mode, no external dependencies. Green rows
are alive, amber rows need attention (stalled / needs-input), red rows are down,
grey rows are unknown. The connection_check.py checker calls render() each run;
you can also run this by hand to re-draw the page from a saved state file.

Usage (standalone, optional):
  python3 status_page.py --state ~/.connection-monitor/<hash>.json --out ./status.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from pathlib import Path

STATE_COLOR = {
    "ALL_OK": "#137333",
    "OK": "#137333",
    "DOWN": "#a50e0e",
    "NEEDS_INPUT": "#b06000",
    "STALLED": "#b06000",
    "UNKNOWN": "#5f6368",
}
STATE_LABEL = {
    "ALL_OK": "All connections healthy",
    "OK": "Healthy",
    "DOWN": "Down — needs you",
    "NEEDS_INPUT": "Waiting on you",
    "STALLED": "Stalled",
    "UNKNOWN": "Unknown — re-checking",
}


def render(out_path: Path, rows: list[dict], overall: str) -> Path:
    """Write the status page. `rows` = [{name, state, evidence}, ...]."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    banner = STATE_COLOR.get(overall, "#5f6368")
    overall_label = STATE_LABEL.get(overall, overall)

    if rows:
        body = "".join(
            "<tr>"
            f"<td class='name'>{html.escape(str(r.get('name', '')))}</td>"
            f"<td><span class='dot' style='background:{STATE_COLOR.get(r.get('state', 'UNKNOWN'), '#5f6368')}'></span>"
            f"{html.escape(str(r.get('state', 'UNKNOWN')))}</td>"
            f"<td class='ev'>{html.escape(str(r.get('evidence', '')))}</td>"
            "</tr>"
            for r in rows
        )
    else:
        body = "<tr><td colspan='3'>No connections configured yet — add some to checks.json.</td></tr>"

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Connection status — {html.escape(overall)}</title>
<style>
  body {{ font:16px/1.55 -apple-system, Segoe UI, Roboto, sans-serif; color:#202124;
          background:#fff; max-width:760px; margin:2rem auto; padding:0 1.2rem; }}
  h1 {{ font-size:1.4rem; margin-bottom:.2rem; }}
  .status {{ display:inline-block; padding:.2rem .7rem; border-radius:999px;
             color:#fff; background:{banner}; font-weight:600; font-size:.85rem; }}
  .meta {{ color:#5f6368; font-size:.9rem; margin:.4rem 0 1.4rem; }}
  table {{ border-collapse:collapse; width:100%; }}
  th,td {{ text-align:left; padding:.5rem .6rem; border-bottom:1px solid #e6e6e6; font-size:.92rem; }}
  th {{ color:#5f6368; font-weight:600; }}
  .name {{ font-weight:600; }}
  .ev {{ color:#5f6368; }}
  .dot {{ display:inline-block; width:.6rem; height:.6rem; border-radius:50%; margin-right:.45rem; vertical-align:middle; }}
  .foot {{ color:#9aa0a6; font-size:.82rem; margin-top:1.6rem; }}
</style></head><body>
<h1>Connection status</h1>
<div><span class="status">{html.escape(overall_label)}</span></div>
<div class="meta">Last check {stamp} · this page re-checks itself every 60s</div>
<table>
  <tr><th>Connection</th><th>State</th><th>What the watch saw</th></tr>
  {body}
</table>
<p class="foot">Green = alive · Amber = stalled / waiting on you · Red = down · Grey = unknown (re-checking).
Silence is not success — this page proves what's actually alive.</p>
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render the connection-status page from a saved state file.")
    p.add_argument("--state", required=True, help="Path to a connection-monitor state JSON file.")
    p.add_argument("--out", default="./status.html", help="Where to write the page.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    state_path = Path(args.state).expanduser()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: could not read state {state_path}: {exc}", file=sys.stderr)
        return 2
    states = data.get("states", {})
    rows = [{"name": name, "state": st, "evidence": ""} for name, st in states.items()]
    overall = data.get("overall", "UNKNOWN")
    out = render(Path(args.out).expanduser(), rows, overall)
    print(f"[status-page] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
