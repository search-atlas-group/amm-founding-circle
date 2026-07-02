#!/usr/bin/env python3
"""agent_loop.py — a runnable scaffold of the five-step agent loop.

The doctrine in SKILL.md, made concrete. Every autonomous agent is the same
loop on a trigger:

    Sense  ->  Correlate  ->  Judge  ->  Act  ->  Report

This file is a fill-in-the-blanks skeleton. It runs as-is (with harmless demo
data) so you can see the shape, then you replace the four marked functions with
your own job. The trust ladder (observe / propose / act) is built in as a mode
flag so you literally cannot let a brand-new agent take action before you've
watched it — see EarnedMode below.

Pure standard library. No dependencies. Copy this into your own project.

    python3 agent_loop.py                 # observe mode (read-only, the default)
    python3 agent_loop.py --mode propose  # drafts actions, does not execute
    python3 agent_loop.py --mode act      # executes low-risk actions (earn this)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


# ---------------------------------------------------------------------------
# The trust ladder, as code. You start at OBSERVE and earn your way up.
# ---------------------------------------------------------------------------
class EarnedMode(str, Enum):
    OBSERVE = "observe"   # read-only: sense, correlate, judge, report. No action.
    PROPOSE = "propose"   # also drafts the action and leaves it for a human.
    ACT = "act"           # also executes low-risk actions on its own.


@dataclass
class Signal:
    """One raw thing pulled during Sense — an email, a task, an event."""
    source: str
    subject: str
    topic: str          # what it's ABOUT (used to correlate across sources)
    last_from_me: bool  # was the most recent message in this signal from me?
    body: str = ""


@dataclass
class Situation:
    """A cluster of related signals about one topic — the unit you judge."""
    topic: str
    signals: list[Signal] = field(default_factory=list)

    @property
    def who_has_the_ball(self) -> str:
        """Net state across the WHOLE cluster, not any single signal.

        If the most recent activity anywhere in the cluster was from me, the
        ball is with THEM (waiting on them / closed). Otherwise it's mine.
        This is the 'judge by who has the ball' rule from the doctrine.
        """
        # Later signals in the list are treated as more recent; a real
        # implementation would sort by timestamp. If any of the freshest
        # signals came from me, I've handed it back.
        if self.signals and self.signals[-1].last_from_me:
            return "them"
        return "me"


# ---------------------------------------------------------------------------
# STEP 1 — SENSE.  <<< REPLACE THIS with a pull from your real sources. >>>
# ---------------------------------------------------------------------------
def sense() -> list[Signal]:
    """Pull raw signals from the sources that feed the job.

    Swap this out for real calls to your inbox / task list / calendar / CRM.
    The demo data below deliberately includes the tricky case the doctrine
    warns about: the SAME topic ('acme onboarding') shows up under two
    different subject lines, and the most recent one was answered by me.
    """
    return [
        Signal("email", "Re: kickoff for Acme", "acme onboarding",
               last_from_me=False, body="When can we start?"),
        Signal("email", "Acme — access + timeline", "acme onboarding",
               last_from_me=True, body="Sent creds + timeline. You're all set."),
        Signal("task", "Draft Q3 report", "q3 report",
               last_from_me=False, body="Due Friday."),
    ]


# ---------------------------------------------------------------------------
# STEP 2 — CORRELATE.  Connect signals into situations BEFORE you judge.
# This one you usually keep as-is: it groups by topic, the skipped step.
# ---------------------------------------------------------------------------
def correlate(signals: list[Signal]) -> list[Situation]:
    """Group signals that are about the same thing into one situation.

    Subject lines lie, so we cluster by `topic`, not by subject. This is the
    step everyone skips — and skipping it is what makes an agent cry wolf.
    """
    by_topic: dict[str, Situation] = {}
    for sig in signals:
        by_topic.setdefault(sig.topic, Situation(topic=sig.topic)).signals.append(sig)
    return list(by_topic.values())


# ---------------------------------------------------------------------------
# STEP 3 — JUDGE.  Decide what actually needs action. Default skeptical.
# ---------------------------------------------------------------------------
def judge(situations: list[Situation]) -> list[Situation]:
    """Keep only the situations where the ball is genuinely with me.

    Default skeptical: a situation is only 'owed' if, across the whole
    cluster, I did NOT have the last word. Everything else is already handled.
    """
    return [s for s in situations if s.who_has_the_ball == "me"]


# ---------------------------------------------------------------------------
# STEP 4 — ACT.  What happens here depends on the earned mode.
# <<< REPLACE draft()/execute() with your real action. >>>
# ---------------------------------------------------------------------------
def draft(situation: Situation) -> str:
    """Produce a DRAFT action for a human to approve. Never sends anything."""
    return f"[DRAFT reply for '{situation.topic}'] — review before sending."


def execute(situation: Situation) -> str:
    """Actually perform the low-risk action. Only reached in ACT mode.

    Keep this genuinely low-risk. High-stakes actions (sending to clients,
    deleting, paying) should stay in PROPOSE — drafts only — no matter how
    much trust the agent has earned.
    """
    # A real implementation would send/update here. We only record intent so
    # this template can never do anything destructive when you run it.
    return f"[EXECUTED low-risk action for '{situation.topic}']"


def act(owed: list[Situation], mode: EarnedMode) -> list[str]:
    """Apply the trust ladder. OBSERVE takes no action at all."""
    if mode is EarnedMode.OBSERVE:
        return [f"[OBSERVE] noted '{s.topic}' — no action taken." for s in owed]
    if mode is EarnedMode.PROPOSE:
        return [draft(s) for s in owed]
    return [execute(s) for s in owed]  # EarnedMode.ACT


# ---------------------------------------------------------------------------
# STEP 5 — REPORT.  Leave a status record you can trust at a glance.
# ---------------------------------------------------------------------------
def report(
    mode: EarnedMode,
    sensed: list[Signal],
    situations: list[Situation],
    owed: list[Situation],
    actions: list[str],
    out_dir: Path,
) -> Path:
    """Write a run record: counts, what was closed as already-resolved, actions."""
    already_resolved = [s.topic for s in situations if s.who_has_the_ball != "me"]
    record = {
        "run_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": mode.value,
        "sensed_count": len(sensed),
        "situations_count": len(situations),
        "owed_count": len(owed),
        "owed_topics": [s.topic for s in owed],
        "closed_as_already_resolved": already_resolved,
        "actions": actions,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d")
    path = out_dir / f"run-{stamp}.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def run(mode: EarnedMode, out_dir: Path) -> dict:
    sensed = sense()
    situations = correlate(sensed)
    owed = judge(situations)
    actions = act(owed, mode)
    path = report(mode, sensed, situations, owed, actions, out_dir)

    print(f"mode: {mode.value}")
    print(f"sensed {len(sensed)} signals -> {len(situations)} situations")
    print(f"owed (ball is with me): {[s.topic for s in owed]}")
    print(f"closed as already-resolved: "
          f"{[s.topic for s in situations if s.who_has_the_ball != 'me']}")
    for line in actions:
        print(f"  action: {line}")
    print(f"report written: {path}")
    return {"report": str(path), "owed": [s.topic for s in owed]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--mode",
        choices=[m.value for m in EarnedMode],
        default=EarnedMode.OBSERVE.value,
        help="trust-ladder mode: observe (default), propose, or act",
    )
    parser.add_argument(
        "--out",
        default="reports/agent",
        help="directory for the run record (default: reports/agent)",
    )
    args = parser.parse_args(argv)
    run(EarnedMode(args.mode), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
