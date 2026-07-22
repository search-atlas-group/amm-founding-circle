#!/usr/bin/env python3
"""Bug Hunter — one command to sweep your whole client roster.

    python3 run.py                      # uses clients.yaml in this folder
    python3 run.py --config other.yaml
    python3 run.py --max-pages 20       # override per-site page cap (faster smoke test)
    python3 run.py --json               # also print a JSON summary (for piping)

See README.md for the clients.yaml schema and .env.example for credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bug_hunter.config import ConfigError, load_clients_file, load_env_file  # noqa: E402
from bug_hunter.delivery import maybe_deliver  # noqa: E402
from bug_hunter.report import active_findings, build_run_summary_line, render_html, render_terminal  # noqa: E402
from bug_hunter.sweep import run_sweep  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sweep every client site + Google Ads account for real errors.")
    parser.add_argument("--config", default="clients.yaml", help="Path to clients.yaml (default: clients.yaml)")
    parser.add_argument("--env", default=".env", help="Path to .env credentials file (default: .env)")
    parser.add_argument("--max-pages", type=int, default=None, help="Override max pages crawled per site (all clients)")
    parser.add_argument("--out", default=None, help="HTML report output path (default: reports/bug-hunter-<date>.html)")
    parser.add_argument("--json", action="store_true", help="Also print a JSON findings summary to stdout")
    parser.add_argument("--no-deliver", action="store_true", help="Skip Slack/email delivery even if configured")
    args = parser.parse_args(argv)

    load_env_file(args.env)

    try:
        clients = load_clients_file(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    print(f"Sweeping {len(clients)} client(s)... (this can take a few minutes for larger sites)")
    result = run_sweep(clients, max_pages_override=args.max_pages)

    print()
    print(render_terminal(result))

    out_path = Path(args.out) if args.out else Path("reports") / f"bug-hunter-{datetime.now():%Y%m%d-%H%M%S}.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_report = render_html(result)
    out_path.write_text(html_report, encoding="utf-8")
    print(f"\nHTML report written to: {out_path}")

    if not args.no_deliver:
        notes = maybe_deliver(build_run_summary_line(result), str(out_path), html_report)
        for note in notes:
            print(note)

    if args.json:
        summary = {
            "summary_line": build_run_summary_line(result),
            "clients_swept": result.clients_swept,
            "sites_swept": result.sites_swept,
            "pages_crawled": result.pages_crawled,
            "campaigns_checked": result.campaigns_checked,
            "skipped_checks": result.skipped_checks,
            "active_findings": [
                {
                    "client": f.client,
                    "category": f.category,
                    "severity": f.severity.value,
                    "title": f.title,
                    "detail": f.detail,
                    "location": f.location,
                    "suggested_fix": f.suggested_fix,
                    "key": f.key,
                }
                for f in active_findings(result)
            ],
        }
        print(json.dumps(summary, indent=2))

    critical_found = any(f.severity.value == "critical" for f in active_findings(result))
    return 2 if critical_found else 0


if __name__ == "__main__":
    raise SystemExit(main())
