#!/usr/bin/env python3
"""Read-only Shep action-log viewer.

This command only reads the Shep action ledger. It has no transport imports and
no controls that can send, close, launch, or mutate a mission.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from shep_action_log import filter_events, load
except ImportError:  # pragma: no cover
    from scripts.shep_action_log import filter_events, load


def _timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _when(value: object) -> str:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return "-"


def render_table(events: list[dict[str, object]]) -> str:
    lines = ["UTC | ACTION | MODE | LIFECYCLE | TARGET | RESULT", "--- | --- | --- | --- | --- | ---"]
    for event in events:
        lines.append(" | ".join([
            _when(event.get("ts")), str(event.get("action", "-")),
            str(event.get("mode", "-")), str(event.get("lifecycle", "-")),
            str(event.get("target", "-")), str(event.get("result", "-")),
        ]))
    return "\n".join(lines)


def render_html(events: list[dict[str, object]]) -> str:
    rows = []
    for event in events:
        details = html.escape(json.dumps(event, sort_keys=True, indent=2))
        cells = [
            _when(event.get("ts")), event.get("action", "-"), event.get("mode", "-"),
            event.get("lifecycle", "-"), event.get("target", "-"), event.get("result", "-"),
        ]
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + f"<td><details><summary>details</summary><pre>{details}</pre></details></td></tr>")
    return """<!doctype html>
<meta charset="utf-8"><title>Shep Action Audit</title>
<style>body{font:14px system-ui;margin:2rem;color:#172033}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd3df;padding:.45rem;text-align:left;vertical-align:top}th{background:#eef2f7}pre{white-space:pre-wrap;max-width:50rem}</style>
<h1>Shep Action Audit</h1><p>Read-only action receipts. This page has no control actions.</p>
<table><thead><tr><th>UTC</th><th>Action</th><th>Mode</th><th>Lifecycle</th><th>Target</th><th>Result</th><th>Details</th></tr></thead><tbody>""" + "".join(rows) + "</tbody></table>\n"


def read_events(path=None, **filters):
    """Public read-only interface used by the CLI and tests."""
    return filter_events(load(path), **filters)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", help="ledger JSONL path (read-only)")
    parser.add_argument("--since", help="epoch or ISO-8601 lower bound")
    parser.add_argument("--until", help="epoch or ISO-8601 upper bound")
    parser.add_argument("--action", choices=("nudge", "reap", "answer"))
    parser.add_argument("--mode", choices=("auto", "manual"))
    parser.add_argument("--target")
    parser.add_argument("--result")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("--html-output", type=Path, help="write a static HTML report here")
    args = parser.parse_args(argv)
    events = read_events(
        args.ledger, since=_timestamp(args.since), until=_timestamp(args.until),
        action=args.action, mode=args.mode, target=args.target, result=args.result,
    )
    if args.html_output:
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(render_html(events), encoding="utf-8")
        return 0
    print(json.dumps(events, indent=2, sort_keys=True) if args.json else render_table(events))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
