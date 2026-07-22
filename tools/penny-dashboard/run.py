#!/usr/bin/env python3
"""Penny Dashboard — per-client profitability, owner view + client-safe view.

Usage:
    python3 run.py init                 # scaffold config/ from the .example files
    python3 run.py generate             # compute this month's margins, write history,
                                         # render owner.html + one client-safe page per client
    python3 run.py generate --period 2026-06 --threshold 25
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from penny_dashboard import config as cfg  # noqa: E402
from penny_dashboard import history_db  # noqa: E402
from penny_dashboard.alerts import (  # noqa: E402
    DEFAULT_MARGIN_THRESHOLD_PCT,
    build_alert_lines,
    dispatch_alerts,
)
from penny_dashboard.google_ads_adapter import resolve_client_spend  # noqa: E402
from penny_dashboard.margin import (  # noqa: E402
    allocate_fixed_costs,
    compute_client_financials,
    margin_trend,
)
from penny_dashboard.render import render_client_safe_view, render_owner_view  # noqa: E402
from penny_dashboard.visibility import build_client_safe_view, describe_dropped_fields  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
DB_PATH = OUT_DIR / "history.db"


def cmd_init(args: argparse.Namespace) -> int:
    created = cfg.scaffold_config()
    if created:
        print("Created:")
        for c in created:
            print(f"  {c}")
        print("\nEdit these with your real client/billing/cost data, then run:")
        print("  python3 run.py generate")
    else:
        print("Config already present in config/ — nothing to scaffold.")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    period = args.period or datetime.now(timezone.utc).strftime("%Y-%m")
    threshold = args.threshold if args.threshold is not None else DEFAULT_MARGIN_THRESHOLD_PCT

    try:
        clients = cfg.load_clients()
        fixed_costs, overrides = cfg.load_tool_costs()
        visibility = cfg.load_visibility()
    except cfg.ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1

    if not clients:
        print("No clients found in config/clients.yaml — nothing to generate.", file=sys.stderr)
        return 1

    active_ids = [c.client_id for c in clients]
    tool_allocation = allocate_fixed_costs(fixed_costs, active_ids, overrides)

    conn = history_db.connect(str(DB_PATH))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "clients").mkdir(parents=True, exist_ok=True)

    financials = []
    trends: dict[str, float | None] = {}
    for c in clients:
        ad_spend = resolve_client_spend(
            google_ads_customer_id=c.google_ads_customer_id,
            manual_spend_csv=c.manual_spend_csv,
            period=period,
        )
        # Hours-based labor cost is a documented "Later phase" item (see
        # README) — hours_csv parsing isn't wired in v1, so this is always 0.
        hours = 0.0
        result = compute_client_financials(
            client_id=c.client_id,
            period=period,
            retainer_usd=c.retainer_usd,
            ad_spend_usd=ad_spend,
            markup_rule=c.markup_rule,
            tool_cost_usd=tool_allocation.get(c.client_id, 0.0),
            hours=hours,
            hourly_rate_usd=c.hourly_rate_usd,
        )
        financials.append(result)
        prev = history_db.previous_margin_pct(conn, c.client_id, period)
        trends[c.client_id] = margin_trend(result.margin_pct, prev)
        history_db.upsert_period(conn, result)

    owner_html = render_owner_view(financials, period, threshold, trends)
    owner_path = OUT_DIR / "owner.html"
    owner_path.write_text(owner_html, encoding="utf-8")
    print(f"Wrote owner view -> {owner_path}")

    client_names = {c.client_id: c.name for c in clients}
    for f in financials:
        client_vis = visibility.get(f.client_id, {})
        vfields = client_vis.get("visible_fields", [])
        dropped = describe_dropped_fields(vfields)
        if dropped:
            print(
                f"  note: {f.client_id} visibility.yaml requested unsupported field(s) "
                f"{dropped} — not shown (allowlist only).",
                file=sys.stderr,
            )
        view = build_client_safe_view(
            client_id=f.client_id,
            client_name=client_names.get(f.client_id, f.client_id),
            period=period,
            ad_spend_usd=f.ad_spend_usd,
            visible_fields=vfields,
            deliverables=client_vis.get("deliverables", []),
            results_note=client_vis.get("results_note", ""),
        )
        page = render_client_safe_view(view)
        path = OUT_DIR / "clients" / f"{f.client_id}.html"
        path.write_text(page, encoding="utf-8")
        print(f"Wrote client-safe view -> {path}")

    lines = build_alert_lines(financials, threshold, client_names)
    if lines:
        print("\nMargin alerts:")
        for line in lines:
            print(f"  - {line}")
        used = dispatch_alerts(lines)
        if used:
            print(f"Sent via: {', '.join(used)}")
        else:
            print("(No PENNY_SLACK_WEBHOOK_URL / PENNY_ALERT_EMAIL_TO configured — printed only.)")
    else:
        print(f"\nNo clients below {threshold:.0f}% margin this period.")

    conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Penny Dashboard — client cost/billing profitability")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Scaffold config/ from the .example files")
    p_init.set_defaults(func=cmd_init)

    p_gen = sub.add_parser("generate", help="Compute margins and render the dashboards")
    p_gen.add_argument("--period", help="YYYY-MM to compute (default: current month)")
    p_gen.add_argument(
        "--threshold",
        type=float,
        help=f"Margin-%% alert threshold (default: {DEFAULT_MARGIN_THRESHOLD_PCT})",
    )
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
