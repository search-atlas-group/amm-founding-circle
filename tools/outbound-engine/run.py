#!/usr/bin/env python3
"""
Outbound Engine — CLI entrypoint.

Quick start:
    python3 run.py wizard                  # build config/icp.yaml via interview
    python3 run.py pipeline --dry-run       # signals -> enrich -> personalize
    python3 run.py review                   # approve/edit/skip drafts, interactively
    python3 run.py load --dry-run           # preview what WOULD load to Smartlead
    python3 run.py report                   # write a weekly HTML report

This build is dry-run only end to end — see README.md "Live mode" and the
module docstrings in outbound_engine/signals/visual_visitor.py and
outbound_engine/load/smartlead.py for exactly why, and what a future build
needs before flipping any of this to real credentials.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from outbound_engine import pipeline  # noqa: E402
from outbound_engine.config import Settings, load_env, load_icp, load_voice_examples  # noqa: E402
from outbound_engine.db import Store  # noqa: E402
from outbound_engine.icp_wizard import run_wizard  # noqa: E402
from outbound_engine.load.smartlead import LiveModeNotImplementedError as SmartleadLiveModeError  # noqa: E402
from outbound_engine.personalize.personalizer import build_client  # noqa: E402
from outbound_engine.report import generate_weekly_report  # noqa: E402
from outbound_engine.review_queue import run_interactive  # noqa: E402
from outbound_engine.signals.visual_visitor import (  # noqa: E402
    LiveModeNotImplementedError as VisualVisitorLiveModeError,
)
from outbound_engine.signals.visual_visitor import VisualVisitorAdapter  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Outbound Engine — dry-run prospecting pipeline")
    p.add_argument("--db", default="outbound_engine.db", help="SQLite state file (default: outbound_engine.db)")
    p.add_argument("--icp", default="config/icp.yaml", help="ICP yaml path (default: config/icp.yaml)")
    p.add_argument("--voice", default="config/voice-examples.md", help="Voice examples markdown path")
    p.add_argument("--env", default=".env", help=".env path (default: .env)")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("wizard", help="Interactively build config/icp.yaml")
    sub.add_parser("signals", help="Pull new visitor signals (mock — see signals/visual_visitor.py)")
    sub.add_parser("enrich", help="Score new prospects against the ICP")
    sub.add_parser("personalize", help="Draft outreach for enriched, non-rejected prospects")

    p_pipeline = sub.add_parser("pipeline", help="Run signals -> enrich -> personalize in one go")
    p_pipeline.add_argument("--dry-run", action="store_true", default=True,
                             help="No-op flag in this build — everything is dry-run (kept for forward compatibility)")

    sub.add_parser("review", help="Interactively approve/edit/skip/reject pending drafts")

    p_load = sub.add_parser("load", help="Load approved drafts to the campaign target (dry-run only)")
    p_load.add_argument("--dry-run", action="store_true", default=True,
                         help="This build only ever runs dry-run — flag kept for forward compatibility")
    p_load.add_argument("--live", action="store_true",
                         help="Refused on purpose in this build — see load/smartlead.py")
    p_load.add_argument("--campaign-name", default="AMM Outbound Engine (dry-run)")

    p_report = sub.add_parser("report", help="Generate the weekly HTML pipeline report")
    p_report.add_argument("--out", default="reports/weekly-report.html")
    p_report.add_argument("--days", type=int, default=7)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    load_env(args.env)
    settings = Settings(db_path=args.db)

    if args.command == "wizard":
        run_wizard(args.icp)
        return 0

    try:
        return _run_command(args, settings)
    except (VisualVisitorLiveModeError, SmartleadLiveModeError) as e:
        print(f"REFUSED: {e}")
        return 1


def _run_command(args: argparse.Namespace, settings: Settings) -> int:
    with Store(settings.db_path) as store:
        if args.command == "signals":
            adapter = VisualVisitorAdapter(
                api_key=settings.visual_visitor_api_key, live_mode=settings.visual_visitor_live_mode,
            )
            counts = pipeline.run_signals_stage(store, adapter)
            print(f"signals: fetched {counts['fetched']}, {counts['new']} new")

        elif args.command == "enrich":
            icp = load_icp(args.icp)
            counts = pipeline.run_enrich_stage(store, icp)
            print(f"enrich: scored {counts['enriched']} prospect(s)")

        elif args.command == "personalize":
            icp = load_icp(args.icp)
            voice = load_voice_examples(args.voice)
            client = build_client(settings.llm_provider)
            counts = pipeline.run_personalize_stage(store, icp, voice, client)
            print(f"personalize: drafted {counts['drafted']} outreach email(s)")

        elif args.command == "pipeline":
            icp = load_icp(args.icp)
            voice = load_voice_examples(args.voice)
            client = build_client(settings.llm_provider)
            adapter = VisualVisitorAdapter(
                api_key=settings.visual_visitor_api_key, live_mode=settings.visual_visitor_live_mode,
            )
            results = pipeline.run_dry_run_pipeline(store, icp, voice, adapter, client)
            print("Pipeline (dry-run) complete:")
            for stage, counts in results.items():
                print(f"  {stage}: {counts}")
            print("\nNext: python3 run.py review")

        elif args.command == "review":
            tally = run_interactive(store)
            print(f"\nReview complete: {tally}")

        elif args.command == "load":
            if args.live:
                print(
                    "REFUSED: --live is not implemented in this build. This tool only ships "
                    "a dry-run Smartlead adapter — see outbound_engine/load/smartlead.py for why "
                    "(build directive + Bryan Fikes' wiring not yet confirmed). Re-run without --live."
                )
                return 1
            adapter = pipeline.default_load_adapter(
                api_key=settings.smartlead_api_key, live_mode=settings.smartlead_live_mode,
            )
            counts = pipeline.run_load_stage_dry_run(store, adapter, args.campaign_name)
            print(f"load (dry-run): {counts['loaded']} approved prospect(s) — payload previewed, nothing sent")

        elif args.command == "report":
            icp = load_icp(args.icp) if Path(args.icp).exists() else {}
            cost_note = icp.get("cost_comparison")
            out = generate_weekly_report(store, args.out, cost_comparison_note=cost_note, days=args.days)
            print(f"Report written: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
