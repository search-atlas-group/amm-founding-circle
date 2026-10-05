#!/usr/bin/env python3
"""Bounded unattended Shep/mission maintenance loop.

Each pass inventories Herdr sessions, drafts and sends only Shep's
``safe_continuation`` nudges through Codex Gateway, then reconciles mission
state without closing sessions. New mission dispatch remains an explicit
operator action; this loop must never turn a recommendation deck into
autonomous code work.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path


SHEP_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(
    os.environ.get("SHEP_RUNTIME_ROOT", str(Path.home() / ".shep-runtime"))
).expanduser()
AGENTIC_ENGINEERING = Path(
    os.environ.get("SHEP_AGENTIC_ENGINEERING", str(Path.home() / "Sync/searchatlas-eng/forge-repos/org-internal/agentic-engineering"))
).expanduser()
PYTHON = sys.executable
STATE_DIR = Path(os.environ.get("MISSION_ENGINE_DIR", str(Path.home() / ".mission-engine")))
# One pass should finish inside the scheduler's interval. The step timeouts sum
# to more than this on purpose -- they bound a single hung step -- but the
# advisory capacity plan at the end is fitted to what the pass has actually got
# left, so a slow sweep degrades the plan instead of failing the whole job.
PASS_BUDGET = int(os.environ.get("SHEP_PASS_BUDGET", "300"))
CAPACITY_PLAN_TIMEOUT = int(os.environ.get("SHEP_CAPACITY_PLAN_TIMEOUT", "120"))
# Below this the plan cannot realistically finish (it runs ~10-45s healthy, and
# the floor leaves room for a slow gateway), so spending the pass's last seconds
# on a near-certain timeout is worse than skipping it.
CAPACITY_PLAN_FLOOR = int(os.environ.get("SHEP_CAPACITY_PLAN_FLOOR", "60"))
LOCK_PATH = STATE_DIR / "shep-control-loop.lock"
LOG_PATH = STATE_DIR / "shep-control-loop.log"
HERDR_CTL = Path(
    os.environ.get(
        "SHEP_HERDR_CTL",
        str(Path.home() / "Sync/.agent-config/skills-shared/herdr/scripts/herdr_ctl.py"),
    )
).expanduser()
SHEP = SHEP_ROOT / "scripts" / "shep.py"
LAUNCH = Path(
    os.environ.get(
        "SHEP_MISSION_LAUNCH_SCRIPT",
        str(Path.home() / "Sync/.agent-config/skills/mission-launch/scripts/launch.py"),
    )
).expanduser()


def _env(**updates: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "SHEP_HERDR_CTL": str(HERDR_CTL),
            "SHEP_NUDGE_STATE": str(STATE_DIR / "shep-nudge-state.json"),
            "SHEP_OUTCOMES_DIR": str(STATE_DIR / "shep-nudge-outcomes"),
            "SHEP_TELEMETRY_CHANNEL": "",
            "AGENT_GOAL_RUNTIME": "codex-gw",
            "AGENT_BUILD_HARNESS": "codex-gw",
            "MISSION_BUILD_HARNESS_DEFAULT": "codex-gw",
        }
    )
    # The drafting lane is a preference, not a policy: when a pool is out of
    # capacity every pass records `gateway_unavailable` and nudges silently
    # stop, so the operator has to be able to point this at a healthy gateway
    # without editing the loop.
    for key, value in {
        "SHEP_NUDGE_CMD": "codex-gw exec --skip-git-repo-check",
        "CODEX_GW_MODEL": "gpt-5.6-luna",
        "CODEX_GW_REASONING": "high",
    }.items():
        env.setdefault(key, value)
    env.update(updates)
    return env


def _run(args: list[str], cwd: Path, env: dict[str, str], timeout: int) -> int:
    started = time.monotonic()
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        print(f"$ {' '.join(args)} [timeout] {elapsed:.1f}s", file=sys.stderr)
        if exc.stdout:
            print(str(exc.stdout).rstrip(), file=sys.stderr)
        if exc.stderr:
            print(str(exc.stderr).rstrip(), file=sys.stderr)
        return 124
    elapsed = time.monotonic() - started
    print(f"$ {' '.join(args)} [{result.returncode}] {elapsed:.1f}s")
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode


def _reexec_from_pinned_main() -> None:
    """Hand the pass to a checkout pinned to main, then never return.

    The scheduler invokes this file by absolute path inside the shared working
    checkout, so the unattended loop has always run whatever branch someone
    last left that folder on — a half-finished feature branch drives live panes
    until a human notices. The scheduler entry cannot be changed from here, but
    what sits at that path can, so the entrypoint re-executes itself out of a
    clone that only ever fast-forwards to origin/main.

    Every failure keeps the last known-good runtime copy rather than falling
    back to the shared checkout: an unreachable network is not a reason to
    start running an arbitrary branch against live sessions.
    """
    if os.environ.get("SHEP_RUNTIME_PINNED") or SHEP_ROOT == RUNTIME_ROOT:
        return
    target = RUNTIME_ROOT / "scripts" / "shep_control_loop.py"
    if not (RUNTIME_ROOT / ".git").exists() or not target.exists():
        # Nothing pinned on this machine yet. Running the shared checkout is
        # the pre-existing behaviour, so this stays a no-op rather than a
        # hard failure that would silently stop the loop entirely.
        return
    try:
        # --ff-only, never reset: a runtime clone that has somehow diverged or
        # gone dirty must stall on the last good commit and be looked at, not
        # be silently overwritten by a scheduled job nobody is watching.
        subprocess.run(
            ["git", "-C", str(RUNTIME_ROOT), "pull", "--ff-only", "--quiet",
             "origin", "main"],
            check=True, timeout=120, capture_output=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"shep-control-loop: pinned runtime not updated ({exc})")
    os.environ["SHEP_RUNTIME_PINNED"] = "1"
    os.chdir(RUNTIME_ROOT)
    os.execv(PYTHON, [PYTHON, str(target), *sys.argv[1:]])


def main() -> int:
    # RETRY-LOOP-SAFETY: bounded by design — do not add a naive retry handler here.
    #   concurrency: one nonblocking fcntl singleton lock; overlap exits cleanly.
    #   attempts: three gateway or transport failures per unchanged context, then exhausted.
    #   backoff: scheduled 5m/30m/2h eligibility; no inline sleep or recursive retry.
    #   why no retry handler: sleeping under this lock would block later fleet passes.
    os.umask(0o077)
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    with LOCK_PATH.open("a+") as lock:
        os.chmod(LOCK_PATH, 0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("shep-control-loop: another pass is already running")
            return 0

        # Version integrity: refresh origin/main so bin/shep's behind-checkout
        # warning can see upstream movement. Single-shot, advisory, never
        # fails the pass -- a network outage must not skip the sweep.
        try:
            subprocess.run(
                ["git", "-C", str(SHEP_ROOT), "fetch", "--quiet", "origin", "main"],
                timeout=60,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # advisory only; RETRY-LOOP-SAFETY: no retries
            pass

        started = time.monotonic()
        nudge_rc = _run(
            [PYTHON, str(SHEP), "--sweep", "--send"],
            SHEP_ROOT,
            _env(),
            240,
        )
        reconcile_rc = _run(
            [PYTHON, str(LAUNCH), "reconcile"],
            LAUNCH.parent,
            _env(),
            120,
        )
        # Advisory only: capacity planning never launches or reserves work.
        #
        # The plan gets whatever the pass has left rather than a fixed budget.
        # It drives the same gateway the sweep just did, so a long sweep
        # squeezes it -- and on a fixed 120s it then timed out and turned the
        # whole scheduled job red even though the sweep had already sent its
        # nudges, which is the failure this budget removes. With nothing left,
        # skip: a plan that cannot finish before the next pass is due is worth
        # nothing, and running it anyway only buys a guaranteed 124.
        remaining = int(PASS_BUDGET - (time.monotonic() - started))
        capacity_rc = 0
        if remaining >= CAPACITY_PLAN_FLOOR:
            capacity_rc = _run(
                [PYTHON, str(SHEP), "--capacity-plan", "--json", "--capacity-plan-summary"],
                SHEP_ROOT,
                _env(),
                min(CAPACITY_PLAN_TIMEOUT, remaining),
            )
        else:
            print(
                "shep-control-loop: skipped advisory capacity plan "
                f"({remaining}s left of the {PASS_BUDGET}s pass)"
            )
        return 1 if nudge_rc or reconcile_rc or capacity_rc else 0


if __name__ == "__main__":
    _reexec_from_pinned_main()
    raise SystemExit(main())
