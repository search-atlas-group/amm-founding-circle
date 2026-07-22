"""Bounded, change-only alerting.

Rule (product spec, v1 scope): alert only on healthy->down or down->healthy
transitions -- never a stream of "still fine" pings. A connection's first
sighting establishes a silent baseline (no alert on startup). An optional
once-a-day "all green" heartbeat fires when every connection is healthy and
one hasn't gone out yet today, so silence from the watch itself is never
ambiguous.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Alert:
    name: str
    kind: str  # "down" | "recovered" | "heartbeat"
    message: str


class StateStore:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {"connections": {}, "last_heartbeat_date": None}
        with open(self.path) as f:
            return json.load(f)

    def save(self, data: dict) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def apply(self, results, daily_heartbeat: bool = False) -> list:
        """`results`: iterable of objects with .name / .healthy / .detail /
        .fix_hint (a ProbeResult, or anything shaped like one -- kept duck-
        typed so tests don't need the full probes.py machinery)."""
        data = self.load()
        conns = data.setdefault("connections", {})
        alerts = []
        now = datetime.now(timezone.utc).isoformat()

        for r in results:
            prior = conns.get(r.name)
            conns[r.name] = {
                "healthy": r.healthy,
                "detail": r.detail,
                "fix_hint": getattr(r, "fix_hint", ""),
                "checked_at": now,
                "last_change": prior["last_change"] if prior else now,
            }
            if prior is None:
                continue  # first sighting: silent baseline, never alert
            if prior["healthy"] and not r.healthy:
                conns[r.name]["last_change"] = now
                fix_hint = getattr(r, "fix_hint", "")
                message = f"{r.name} failed at {_hhmm(now)} -- {r.detail}."
                if fix_hint:
                    message += f" Likely fix: {fix_hint}"
                alerts.append(Alert(r.name, "down", message))
            elif (not prior["healthy"]) and r.healthy:
                conns[r.name]["last_change"] = now
                alerts.append(Alert(r.name, "recovered", f"{r.name} is back up as of {_hhmm(now)}."))

        if daily_heartbeat and conns and all(c["healthy"] for c in conns.values()):
            today = now[:10]
            if data.get("last_heartbeat_date") != today:
                data["last_heartbeat_date"] = today
                alerts.append(Alert(
                    "*all*", "heartbeat",
                    f"All {len(conns)} connection(s) healthy as of {_hhmm(now)}.",
                ))

        self.save(data)
        return alerts


def _hhmm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M UTC")
    except ValueError:
        return iso
