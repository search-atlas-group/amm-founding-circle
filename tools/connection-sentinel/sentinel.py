#!/usr/bin/env python3
"""Connection Sentinel -- a ground-truth watch over the connections your
automations depend on. See README.md for the 3-step setup.

Usage:
  python3 sentinel.py --config connections.yaml --once
  python3 sentinel.py --config connections.yaml --interval 900   # loop every 15 min
"""
from __future__ import annotations

import argparse
import os
import sys
import time

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from config import ConfigError, load_connections  # noqa: E402
from notify import notify_all  # noqa: E402
from probes import run_probe  # noqa: E402
from state import StateStore  # noqa: E402
from status_page import write as write_status_page  # noqa: E402


def check_once(config_path: str, state_path: str, status_path: str) -> bool:
    """Runs one full sweep: probe every connection, apply the change-only
    state machine, notify on anything that changed, refresh the status page.
    Returns True if every connection is currently healthy."""
    cfg = load_connections(config_path)
    results = [run_probe(c) for c in cfg.connections]

    store = StateStore(state_path)
    alerts = store.apply(results, daily_heartbeat=cfg.notify.daily_heartbeat)
    for alert in alerts:
        notify_all(alert, cfg.notify)
        print(f"[{alert.kind}] {alert.message}")

    write_status_page(status_path, store.load())

    for r in results:
        label = "OK" if r.healthy else "DOWN"
        print(f"{r.name:<28} {label:<5} | {r.detail}")

    return all(r.healthy for r in results)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Connection Sentinel -- ground-truth connection watch."
    )
    parser.add_argument("--config", default="connections.yaml", help="Path to connections.yaml")
    parser.add_argument(
        "--state", default=None,
        help="Path to the state JSON file (default: <config>.state.json alongside the config)",
    )
    parser.add_argument("--status-page", default="status.html", help="Where to write the HTML status board")
    parser.add_argument(
        "--interval", type=int, default=0,
        help="Seconds between checks. 0 (default) = run one sweep and exit.",
    )
    parser.add_argument("--once", action="store_true", help="Alias for --interval 0 (explicit, for scripts)")
    parser.add_argument("--env-file", default=".env", help="Path to a .env file to load (python-dotenv)")
    args = parser.parse_args()

    if load_dotenv and os.path.exists(args.env_file):
        load_dotenv(args.env_file)

    state_path = args.state or (os.path.splitext(args.config)[0] + ".state.json")
    interval = 0 if args.once else args.interval

    try:
        if interval <= 0:
            healthy = check_once(args.config, state_path, args.status_page)
            return 0 if healthy else 1

        print(f"Connection Sentinel watching every {interval}s. Ctrl-C to stop.")
        while True:
            try:
                check_once(args.config, state_path, args.status_page)
            except ConfigError as e:
                print(f"[config error] {e}", file=sys.stderr)
            except Exception as e:
                # one bad cycle must never kill the watch -- log and keep going
                print(f"[error] sweep failed: {e}", file=sys.stderr)
            time.sleep(interval)
    except ConfigError as e:
        print(f"[config error] {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
