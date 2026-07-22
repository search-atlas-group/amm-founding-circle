"""Command-line entry point. One copy-paste command runs the whole
pipeline for a client; subcommands give finer control.

    python3 run.py --client acme                 # import + grade + digest
    python3 run.py wizard --client acme            # build rubric.md
    python3 run.py import --client acme --days 1
    python3 run.py grade --client acme
    python3 run.py digest --client acme --send
    python3 run.py trend --client acme --days 7
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

from . import digest as digest_mod
from . import rubric as rubric_mod
from . import store as store_mod
from .adapters.callrail import CallRailAdapter
from .grader import grade_lead
from .llm import LLMClient, LLMConfigError

DEFAULT_CLIENTS_DIR = Path("clients")
DEFAULT_DB_PATH = Path("leads.db")


def load_client_config(client_slug: str, clients_dir: Path = DEFAULT_CLIENTS_DIR) -> dict:
    config_path = clients_dir / client_slug / "config.yaml"
    if not config_path.exists():
        raise SystemExit(
            f"No config for client '{client_slug}' — expected {config_path}. "
            f"Copy clients/_example/ to clients/{client_slug}/ and fill it in first."
        )
    config = yaml.safe_load(config_path.read_text()) or {}
    config["slug"] = client_slug
    return config


def cmd_wizard(args: argparse.Namespace) -> int:

    try:
        llm = LLMClient()
    except LLMConfigError as exc:
        print(f"Can't run the rubric wizard: {exc}")
        return 1

    client_config = _try_load_config(args.client, args.clients_dir)
    client_name = client_config.get("name", args.client) if client_config else args.client

    rubric_md = rubric_mod.run_wizard(client_name, llm)
    print("\n--- Draft rubric ---\n")
    print(rubric_md)
    confirm = input("\nSave this as clients/%s/rubric.md? [y/N] " % args.client).strip().lower()
    if confirm != "y":
        print("Not saved. Re-run the wizard when ready.")
        return 0
    path = rubric_mod.write_rubric(args.client, args.clients_dir, rubric_md)
    print(f"Saved: {path}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    client_config = load_client_config(args.client, args.clients_dir)
    conn = store_mod.connect(args.db)

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    until = datetime.now(timezone.utc)

    if args.from_file:
        import json

        raw_calls = json.loads(Path(args.from_file).read_text()).get("calls", [])
        adapter = CallRailAdapter.__new__(CallRailAdapter)  # normalize() only, no HTTP
        adapter.name = "callrail"
        leads = [adapter.normalize(c, client=args.client) for c in raw_calls]
        leads = [lead for lead in leads if lead is not None]
    else:
        import os

        api_key = os.environ.get("CALLRAIL_API_KEY")
        account_id = os.environ.get("CALLRAIL_ACCOUNT_ID")
        if not api_key or not account_id:
            print("Missing CALLRAIL_API_KEY / CALLRAIL_ACCOUNT_ID in .env — see .env.example.")
            return 1
        adapter = CallRailAdapter(api_key=api_key, account_id=account_id)
        leads = adapter.fetch(client_config, since, until)

    new_count = 0
    for lead in leads:
        if store_mod.upsert_lead(conn, lead):
            new_count += 1
    print(f"Imported {new_count} new lead(s) for {args.client} ({len(leads)} fetched, "
          f"{len(leads) - new_count} already on file).")
    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    client_config = load_client_config(args.client, args.clients_dir)
    client_name = client_config.get("name", args.client)
    rubric_text = rubric_mod.load_rubric(args.client, args.clients_dir)
    if not rubric_text:
        print(
            f"No rubric yet for {client_name} — run `python3 run.py wizard --client "
            f"{args.client}` first."
        )
        return 1

    try:
        llm = LLMClient()
    except LLMConfigError as exc:
        print(f"Can't grade: {exc}")
        return 1

    conn = store_mod.connect(args.db)
    pending = store_mod.ungraded_leads(conn, args.client)
    if args.limit:
        pending = pending[: args.limit]

    for lead in pending:
        grade = grade_lead(lead, rubric_text, llm)
        store_mod.save_grade(conn, grade)

    print(f"Graded {len(pending)} lead(s) for {client_name}.")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    client_config = load_client_config(args.client, args.clients_dir)
    client_name = client_config.get("name", args.client)
    conn = store_mod.connect(args.db)

    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        date = datetime.now(timezone.utc)
    pairs = store_mod.leads_with_grades_for_date(conn, args.client, date)
    result = digest_mod.build_digest(pairs, client_name, date)

    print(result.text)
    path = digest_mod.write_html(result, output_dir=args.output_dir)
    print(f"\nWrote {path}")

    if args.send:
        delivered = digest_mod.deliver(result, client_config)
        if delivered:
            print(f"Delivered to: {', '.join(delivered)}")
    return 0


def cmd_trend(args: argparse.Namespace) -> int:
    conn = store_mod.connect(args.db)
    trend = store_mod.trend(conn, args.client, days=args.days)
    if not trend:
        print(f"No graded leads in the last {args.days} day(s) for {args.client}.")
        return 0
    print(f"Lead-quality trend for {args.client}, last {args.days} day(s):\n")
    for day, counts in sorted(trend.items()):
        total = sum(counts.values())
        breakdown = ", ".join(f"{n} {g.lower()}" for g, n in counts.items())
        junk_rate = (counts.get("Junk", 0) / total * 100) if total else 0
        print(f"  {day}: {total} graded ({breakdown}) — junk rate {junk_rate:.0f}%")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """The one-command path: import + grade + digest."""
    rc = cmd_import(args)
    if rc != 0:
        return rc
    rc = cmd_grade(args)
    if rc != 0:
        return rc
    return cmd_digest(args)


def _try_load_config(client_slug: str, clients_dir: Path) -> Optional[dict]:
    try:
        return load_client_config(client_slug, clients_dir)
    except SystemExit:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lead-grader",
        description="Grade inbound leads (calls today, more sources later) against a per-client rubric.",
    )
    parser.add_argument("--client", required=True, help="Client slug (matches clients/<slug>/)")
    parser.add_argument("--clients-dir", type=Path, default=DEFAULT_CLIENTS_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    sub = parser.add_subparsers(dest="command")

    p_wizard = sub.add_parser("wizard", help="Build this client's rubric.md from labeled examples")
    p_wizard.set_defaults(func=cmd_wizard)

    p_import = sub.add_parser("import", help="Pull new leads from CallRail (or a fixture file)")
    p_import.add_argument("--days", type=int, default=1, help="How many days back to pull (default 1)")
    p_import.add_argument("--from-file", help="Use a CallRail-shaped JSON fixture instead of the live API")
    p_import.set_defaults(func=cmd_import)

    p_grade = sub.add_parser("grade", help="Grade every ungraded lead for this client")
    p_grade.add_argument("--limit", type=int, default=None)
    p_grade.set_defaults(func=cmd_grade)

    p_digest = sub.add_parser("digest", help="Build (and optionally send) the daily digest")
    p_digest.add_argument("--date", help="YYYY-MM-DD, defaults to today (UTC)")
    p_digest.add_argument("--send", action="store_true", help="Also deliver via Slack/email if configured")
    p_digest.add_argument("--output-dir", type=Path, default=Path("output"))
    p_digest.set_defaults(func=cmd_digest)

    p_trend = sub.add_parser("trend", help="Weekly lead-quality trend from stored history")
    p_trend.add_argument("--days", type=int, default=7)
    p_trend.set_defaults(func=cmd_trend)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    from dotenv import load_dotenv

    # Load THIS tool's own .env only — never `source .env` (see python-style
    # conventions), and never the bare `load_dotenv()` default, which walks
    # UP the directory tree and can silently pick up an unrelated .env from
    # a parent folder (e.g. a different project's credentials) instead of
    # this tool's own local one.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        # `python3 run.py --client acme` with no subcommand -> run everything,
        # with sane one-command defaults (last 1 day, no forced send).
        args.days = 1
        args.from_file = None
        args.limit = None
        args.date = None
        args.send = bool(_try_load_config(args.client, args.clients_dir) or {}) and _has_delivery_configured(
            args.client, args.clients_dir
        )
        args.output_dir = Path("output")
        return cmd_run(args)

    return args.func(args)


def _has_delivery_configured(client_slug: str, clients_dir: Path) -> bool:
    import os

    config = _try_load_config(client_slug, clients_dir) or {}
    digest_cfg = config.get("digest", {}) or {}
    return bool(
        digest_cfg.get("slack_webhook")
        or digest_cfg.get("email_to")
        or os.environ.get("SLACK_WEBHOOK_URL")
    )


if __name__ == "__main__":
    sys.exit(main())
