#!/usr/bin/env python3
"""Shep — interactive terminal view of every agentic session on this box.

Watches herdr-managed panes (Claude Code / Codex launched via herdr) and raw
tmux sessions started outside herdr, plus read-only Warp-native shell
sessions — one live table, arrow keys to select, `n` to nudge the selected
session.

This does not reimplement session discovery or control: it shells out to the
existing tools (herdr_ctl.py, tmux) that already do it. See the plan this was
built from for why each transport was chosen.

Usage:
  python3 scripts/shep.py              # live curses TUI
  python3 scripts/shep.py --dump-json  # one-shot: print collected rows, no curses
  python3 scripts/shep.py --snapshot    # panel/status/nudge list, no curses
  python3 scripts/shep.py --snapshot-json --propose
  python3 scripts/shep.py --snapshot --deliver  # send safe proposals only
  python3 scripts/shep.py --capacity-plan --json  # read-only model/capacity plan
"""

import argparse
import contextlib
import colorsys
import curses
import datetime
import fnmatch
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import termios
import concurrent.futures
import threading
import time
import textwrap
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import NamedTuple

try:
    # Suppress NEEDS-HUMAN escalations for panes Herdr no longer lists.
    # Missing/unreachable guard dependencies fail open so a real handoff is
    # never silently dropped.
    import escalation_guard
except ImportError:  # pragma: no cover - direct script/package imports differ
    try:
        from scripts import escalation_guard
    except ImportError:
        escalation_guard = None


def _live_panes_or_none():
    """Return Herdr's live pane ids, or None when the lookup is inconclusive."""
    if escalation_guard is None:
        return None
    try:
        return escalation_guard.live_panes()
    except Exception:  # noqa: BLE001 - escalation guard must fail open
        return None

try:
    # The pure nudge reducer. Only its text helpers are wired in so far; the
    # lifecycle (step/project/run_cycle) still has no caller here. Kept
    # non-fatal like the other sibling imports so a partial checkout still
    # starts, with the local definitions below as the fallback.
    from shep_nudge_core import nudge_evidence_identity, nudge_tokens
except ImportError:  # pragma: no cover - direct script and package imports differ
    try:
        from scripts.shep_nudge_core import (
            nudge_evidence_identity,
            nudge_tokens,
        )
    except ImportError:
        nudge_evidence_identity = None
        nudge_tokens = None

try:
    # Observe-only outcome telemetry. Optional on purpose: Shep must run even
    # if this module is missing or unimportable.
    from shep_nudge_outcomes import edit_fields as outcome_edit_fields
    from shep_nudge_outcomes import events_dir as _outcomes_events_dir
    from shep_nudge_outcomes import record as record_outcome
except ImportError:  # pragma: no cover - shims keep every call site harmless
    def record_outcome(event, **fields):
        return None

    def outcome_edit_fields(original, final):
        return {}

    def _outcomes_events_dir():
        # Same default the module uses, so the header still counts a log a
        # previous run left behind even on a checkout missing the module.
        return Path(
            os.environ.get("SHEP_OUTCOMES_DIR")
            or Path.home() / ".mission-engine" / "shep-nudge-outcomes"
        )

try:
    from shep_action_log import (
        ActionLogError,
        append as record_action,
        ledger_path as action_ledger_path,
        load as action_log_load,
    )
except ImportError:  # pragma: no cover - direct script and package imports differ
    try:
        from scripts.shep_action_log import (
            ActionLogError,
            append as record_action,
            ledger_path as action_ledger_path,
            load as action_log_load,
        )
    except ImportError:
        class ActionLogError(RuntimeError):
            pass

        def record_action(*_args, **_kwargs):
            raise ActionLogError("Shep action ledger is unavailable")

        def action_log_load(*_args, **_kwargs):
            # The LOGS view degrades to "nothing recorded", never to a crash.
            return []

        def action_ledger_path(*_args, **_kwargs):
            return Path(os.devnull)

try:
    from shep_control import ControlBusy, control_once
except ImportError:  # pragma: no cover - package imports differ from direct runs
    from scripts.shep_control import ControlBusy, control_once

try:
    from shep_missions import list_missions, queue_mission
except ImportError:  # pragma: no cover - package imports differ from direct runs
    from scripts.shep_missions import list_missions, queue_mission

try:
    import shep_bead_triage as bead_triage
except ImportError:  # pragma: no cover - package imports differ from direct runs
    from scripts import shep_bead_triage as bead_triage

try:
    import shep_afk as afk
except ImportError:  # pragma: no cover - package imports differ from direct runs
    from scripts import shep_afk as afk



def _resolve_herdr_ctl(home=None):
    """Find the shared Herdr controller without depending on a legacy link."""
    override = os.environ.get("SHEP_HERDR_CTL")
    if override:
        return Path(override).expanduser()

    home = Path.home() if home is None else Path(home)
    candidates = (
        home / "Sync/.agent-config/skills-shared/herdr/scripts/herdr_ctl.py",
        home / ".claude/skills/herdr/scripts/herdr_ctl.py",
    )
    return next((path for path in candidates if path.exists()), candidates[0])


HERDR_CTL = _resolve_herdr_ctl()
# Match herdr_ctl.py's supported override so an operator can select a client
# compatible with a still-running server during a non-destructive recovery.
HERDR_BIN = os.environ.get("HERDR_BIN", "herdr")
# T3 Code — the mobile control plane. Its sessions are threads on a local HTTP
# server, not panes, so it is collected over the API rather than scraped.
T3_BASE_URL = os.environ.get("T3_BASE_URL", "http://127.0.0.1:3773")
T3_BIN = os.environ.get("T3_BIN", "t3")
T3_TIMEOUT = 15
# The bearer is minted by the CLI (~1s per call), which is far too slow for a
# 5s redraw. Issued at 5m, cached under that so a pass never uses a stale one.
T3_TOKEN_TTL_SECONDS = 240
_T3_TOKEN = {"value": None, "expires": 0.0}
# Cross-process mirror of _T3_TOKEN. shep_control_loop.py runs several
# `shep.py` subprocesses per pass (sweep, then a capacity plan), each starting
# with an empty in-process cache, so without this every subprocess minted --
# and never revoked -- its own 5-minute T3 auth session. Kept outside the git
# checkout, next to shep's other cross-process state.
T3_AUTH_CACHE_FILE = Path(
    os.environ.get("SHEP_T3_AUTH_CACHE",
                   str(Path.home() / ".mission-engine" / "shep-t3-auth-cache.json"))
)
# Warp has no installed CLI/API for enumerating or controlling native tabs.
# Process metadata is enough to show their existence, but never enough to
# capture output or safely type into them. Those rows remain read-only.
WARP_PROCESS_SCAN_TIMEOUT = 5
WARP_SQLITE_DB_PATH = Path(
    os.environ.get(
        "SHEP_WARP_SQLITE_DB",
        str(
            Path.home()
            / "Library/Group Containers/2BBY89MBSN.dev.warp/Library/Application Support/dev.warp.Warp-Stable/warp.sqlite"
        ),
    )
).expanduser()
WARP_SIDECAR_PATH = Path(
    os.environ.get(
        "SHEP_WARP_SIDECAR",
        str(Path.home() / ".local/state/shep/warp/sessions.json"),
    )
).expanduser()
REFRESH_SECONDS = 5
KEY_POLL_MS = 1000
DRAFT_CONCURRENCY = 3
# Both the selected-session panel and the full-screen session view use the same
# bounded scrollback budget. The panel then clips it to whatever height the
# current frame can actually display.
SESSION_VIEW_LINES = 400


def _resolve_agent_command(lane):
    """Resolve a provider through the canonical agent-command contract.

    Falls back to the conventional wrapper name rather than None: every caller
    here needs something to exec, and a missing binary is reported by the
    subprocess that runs it, not by a resolver that returned nothing.
    """
    return bead_triage.resolve_lane(lane) or f"{lane}-gw"

# --- Mission deck (suggested missions to launch) -----------------------------
#
# Reuses the mission-sense -> mission-recommend -> mission-launch engine as-is
# (see the skills under ~/Sync/.agent-config/skills/mission-*). Shep never
# reimplements scoring/dispatch — it shells out and caches the deck, since
# sense.py walks bd/git per repo and is too slow to rerun on every poll.
MISSION_ENGINE_DIR = Path(
    os.environ.get("MISSION_ENGINE_DIR", str(Path.home() / ".mission-engine"))
)

# SAFETY INVARIANT — the repos file IS the guard.
#
# delivery-repos.txt claims enforcement lives in "recommend.py delivery-mode
# guard", but recommend.py contains no repo allowlist (verified 2026-07-31): it
# scores whatever sense.py hands it. So the ONLY thing keeping autonomous
# code-writing missions off product/personal repos is which repos file feeds
# implementation mode. Do not point MISSION_REPOS_FILE at atlas-repos.txt.
#
# Research missions are artifact-only (launch.py forbids product-code changes,
# commits, pushes, and outbound messages for mission_kind == "research"), so the
# wider atlas-repos.txt is safe for those and is used only to top the deck up.
# Deliberately NOT env-overridable: an override here silently defeats the only
# guard keeping autonomous code missions off product/personal repos.
MISSION_REPOS_FILE = MISSION_ENGINE_DIR / "delivery-repos.txt"
MISSION_RESEARCH_REPOS_FILE = MISSION_ENGINE_DIR / "atlas-repos.txt"
MISSION_DECK_CACHE = MISSION_ENGINE_DIR / "shep-deck-cache.json"
# The BEADS tab reads every repo on disk that has one, discovered by scan. A
# curated file only ever showed 4 of the 64 real workspaces, so work outside
# the delivery set was invisible. Widening what is *read* is safe: it never
# widens what autonomous code missions may be launched against, which stays
# gated by MISSION_REPOS_FILE.
BEADS_ROOT = Path(
    os.environ.get("SHEP_BEADS_ROOT", str(Path.home() / "Sync/searchatlas-eng/forge-repos"))
).expanduser()
# Repos nest a few levels under group dirs; 4 covers every real layout and
# stops the scan well short of node_modules-style trees.
BEADS_SCAN_DEPTH = 4
BEADS_REPO_TTL = 300  # 5 min — a repo gaining a .beads/ is rare; the scan is the slow part
_BEADS_REPO_CACHE = {"at": 0.0, "repos": []}
# The BEADS tab is opened from the curses thread, but its source spans every
# checkout and its triage lane may call a model. Keep the last completed view
# snapshot so opening the tab never has to wait for either operation.
_BEADS_VIEW_LOCK = threading.Lock()
_BEADS_VIEW_CACHE = {
    "beads": None,
    "error": None,
    "missions": None,
    "prune": {},
    "triage_note": "triage pending",
    "at": 0.0,
}
MISSION_DECK_TTL = 1800  # 30 min
# Twelve, not five. Five was chosen to fit on screen, but the view scrolls
# (mission_scroll_window), so the cap was never a display limit — it was a
# supply limit, and it bound hardest exactly where it hurt: beads are collected
# first and only top up from build/research `if len(beads) < MISSION_DECK_TOP`,
# so five ready beads in one repo ended the deck before the other two sources
# were ever consulted. A live deck sat at five bug-hunter beads for days with
# no way to see anything else.
MISSION_DECK_TOP = 12
# No single project may hold more than this many slots. The per-source caps
# could not prevent monopoly on their own: `bead_missions` sorts every repo's
# ready beads into one global list and slices the top N, which is by design
# (priority should cross repos) but means one busy backlog takes every slot.
# Raising MISSION_DECK_TOP alone would have bought twelve bug-hunter beads
# instead of five.
MISSION_DECK_PER_PROJECT = 3
MISSION_MIN_SCORE = 20  # below this a build mission is busywork, not momentum
# recommend.py bypasses --min-score entirely in research mode, so the floor for
# top-up scouts has to be applied here. Without it a quiet day fills the deck
# with near-zero-momentum template scouts and calls them "missions ready".
# Set at 5, not 10: at 10 the live deck sits at exactly 3 with its lowest scout
# 0.3 points above the line, so normal momentum decay silently drops the deck
# below the 3-5 the view promises. Scores are shown per row so thin scouts are
# visible for what they are rather than hidden behind a count.
MISSION_RESEARCH_MIN_SCORE = 5


def _mission_skill_script(skill, script):
    override = os.environ.get(f"SHEP_{skill.upper().replace('-', '_')}_SCRIPT")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Sync/.agent-config/skills" / skill / "scripts" / script


MISSION_SENSE_SCRIPT = _mission_skill_script("mission-sense", "sense.py")
MISSION_RECOMMEND_SCRIPT = _mission_skill_script("mission-recommend", "recommend.py")
MISSION_LAUNCH_SCRIPT = _mission_skill_script("mission-launch", "launch.py")
RESEARCH_CYCLE_SCRIPT = _mission_skill_script("mission-launch", "research_cycle.py")

# Fixed product identity. This is deliberately not configurable through an
# environment variable, CLI option, or theme: every supported interactive
# Shep view belongs to Commander M. Source-level ownership still belongs to
# repository access controls; the regression tests catch accidental drift.
COMMANDER_M_INSIGNIA = "◆M◆"
COMMANDER_M_NAME = "Commander M"

# A pane whose content hasn't meaningfully changed for this long while it still
# claims to be "working" is wedged, not busy. Overridable so the threshold can be
# tuned per box without editing the script.
STALL_AFTER_SECONDS = int(os.environ.get("SHEP_STALL_SECONDS") or "1800")
# Floor between two LLM draft calls for the SAME target, regardless of escalation.
NUDGE_COOLDOWN_SECONDS = 60
# How long a pane must have produced no new output before it is worth a model
# call. A NUDGEABLE status alone is not evidence of quiet — see pane_is_quiet.
# 45s is comfortably longer than the gap an agent leaves between two tool calls
# and far shorter than a real wedge, which lasts minutes.
NUDGE_QUIET_SECONDS = int(os.environ.get("SHEP_NUDGE_QUIET_SECONDS") or "45")
# Backoff before each escalation attempt after the first. Front-loaded, then
# flat at five minutes: the early rungs are where a nudge actually lands, and
# the later ones must not stretch past RATE_LIMIT_BACKOFF_SECONDS[0] — a quota
# wait has to stay longer than any escalation wait, or a 429 gets retried on the
# escalation cadence and just burns the same quota. That ordering is pinned by
# test; widen this ladder and the rate-limit ladder has to move with it.
NUDGE_BACKOFF_SECONDS = (60, 180, 300, 300, 300, 300)
# After this many, hand the target to a human. Raised from 3 on the operator's
# call: 3 made the per-pane ceiling — not the 5-minute tick, which has no cap —
# the binding limit on fleet throughput. Kept finite and env-tunable, because
# the whole job of this number is to stop shep typing forever at a pane it
# cannot move; removing the ceiling would just relabel a wedged pane as busy.
MAX_NUDGE_ATTEMPTS = int(os.environ.get("SHEP_MAX_NUDGE_ATTEMPTS") or "6")
# How many cleaned pane lines the drafter and the content gate reason over.
# Four was the original budget, and on a Claude Code pane the last four lines
# are the recap footer plus the status bar -- the branch name, the MR state and
# the "Next:" step the agent itself wrote sit just above that window. Measured
# live (2026-09-10): a pane that had said "branch pushed, no MR yet, next: open
# the MR" drafted NO_NUDGE because the drafter never saw that sentence.
NUDGE_EVIDENCE_LINES = int(os.environ.get("SHEP_NUDGE_EVIDENCE_LINES") or "12")
# Long enough to swallow a held key (bursts measured 0.4s apart), short enough
# that a deliberate second close still lands.
REAP_DEBOUNCE_SECONDS = 5
# Same held-key lesson, cheaper consequence: refocusing a herdr tab is
# idempotent, so this only has to stop the repeat storm — six presses measured
# twelve subprocess calls on the curses thread — not protect anything.
FOCUS_DEBOUNCE_SECONDS = 1
DRAFT_FAILURE_BACKOFF_SECONDS = (300, 1800, 7200)
MAX_DRAFT_FAILURES = len(DRAFT_FAILURE_BACKOFF_SECONDS)
SEND_FAILURE_BACKOFF_SECONDS = (300, 1800, 7200)
MAX_SEND_FAILURES = len(SEND_FAILURE_BACKOFF_SECONDS)
# A provider quota clears on its own schedule, so these wait far longer than the
# escalation ladder: retrying a 429 every minute just burns the same quota.
RATE_LIMIT_BACKOFF_SECONDS = (300, 1800, 7200)
MAX_RATE_LIMIT_RETRIES = len(RATE_LIMIT_BACKOFF_SECONDS)
MIN_NUDGE_QUALITY_SCORE = 70
MAX_NUDGE_CHARS = 160
NUDGE_ENGINE_FILE = Path(
    os.environ.get(
        "SHEP_NUDGE_ENGINE",
        str(Path(__file__).with_name("shep_nudge_engine.md")),
    )
)
UNRESPONSIVE = "[UNRESPONSIVE — needs human]"
# Statuses that mean "this pane is not making progress and can take an instruction".
NUDGEABLE = ("idle", "done", "stalled")

READY_GLYPHS = ("❯", "›")

# A pane sitting at an OS shell prompt, or holding an agent that already exited,
# has no agent to instruct. Treating it as "working" (the old else-branch default)
# both hid it from the operator and eventually fed a drafted nudge into bash.
# "shell" is deliberately absent from NUDGEABLE — there is nobody to nudge.
_SHELL_PROMPT_RE = re.compile(
    r"\S+@\S+.*[%$#]\s*$"                                        # user@host … % / $
    r"|^(?:d?quote|heredoc|cmdsubst|pipe|for|while|if|then|else)>\s*$"  # zsh continuation
    r"|^\s*[%$#]\s*$"                                            # bare prompt
    r"|^\s*➜\s"                                                  # oh-my-zsh prompt
)
_DEAD_AGENT_RE = re.compile(
    r"\bstatus:\s*(?:stopped|exited|failed)\b|\bcancelled by user\b", re.IGNORECASE
)
# Shep's own key-hint footer. A herdr tab running this TUI reads as `idle`
# (no spinner, no prompt glyph) and was handed to the drafter as a target --
# the one pane a nudge must never be typed into is the one sending them.
_SHEP_TUI_RE = re.compile(r"\[n\]\s*nudge\b.*\[q\]\s*quit\b")
# Claude Code and Codex render a status footer BELOW their input box, so the
# ready prompt is never the last line — checking only `lines[-1]` reported every
# idle agent as working, which is why idle panes were never nudgeable. Scan the
# tail instead, and let the explicit in-progress marker win: the input box is
# drawn while the agent is thinking too, so a visible prompt alone is not idle.
_PANE_TAIL_LINES = 6
_BUSY_RE = re.compile(r"esc to interrupt|ctrl\+c to (?:stop|interrupt)", re.IGNORECASE)
# happy-wrapped sessions report their own state on a status line instead of
# drawing a prompt glyph, so a session literally printing "Status: idle" was
# being reported as working and never became nudgeable.
_IDLE_STATUS_RE = re.compile(r"\bstatus:\s*(?:idle|waiting|ready)\b", re.IGNORECASE)
# `❯` is Claude's prompt AND one of the most common zsh prompts (starship/pure),
# so the glyph alone cannot tell an idle agent from a bare shell — and guessing
# "agent" is what let a nudge get typed into a live zsh. An agent pane always
# draws chrome around its input box; a shell prompt is a naked line. Require the
# chrome before believing a glyph.
_AGENT_CHROME_RE = re.compile(
    r"[─│╭╮╰╯━┃┌┐└┘┏┓┗┛]"
    r"|esc to interrupt|bypass permissions|shift\+tab|ContextQ|Eff:|tokens used",
    re.IGNORECASE,
)

_SAFE_CLOSE_RE = re.compile(
    r"^\s*(?:"
    r"SAFE_TO_CLOSE\s*:\s*\S.*"
    r"|(?:session\s+(?:is\s+)?)?(?:yes,?\s+)?safe\s+to\s+(?:close|reap)\b.*"
    r"|ready\s+(?:for\s+you\s+)?to\s+(?:close|reap)\s+(?:this\s+)?session\b.*"
    r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CLOSE_EVIDENCE_RE = re.compile(
    r"\bnothing\s+(?:is\s+)?left\s+hanging\b"
    r"|\bnothing\s+(?:is\s+)?(?:left\s+)?pending\b"
    r"|\bno\s+(?:work|tasks?|changes?)\s+(?:is\s+|are\s+)?(?:left|remaining|pending)\b"
    r"|\ball\s+(?:scoped\s+)?work\s+(?:is\s+)?(?:complete|committed|verified)\b",
    re.IGNORECASE,
)
# Codex and Claude render submitted user text with these prompt glyphs. A close
# declaration is stale once a later submission exists: the agent must answer
# that request and emit a fresh declaration before the pane can be reaped.
_USER_SUBMISSION_RE = re.compile(r"^\s*[›❯]\s+(\S.*)$", re.MULTILINE)
_EMPTY_AGENT_PROMPT_RE = re.compile(
    r"ask\s+(?:codex|claude)\s+to\s+(?:do anything|code)", re.IGNORECASE
)
_NEW_MISSION_RE = re.compile(r"(?:^|\n)\s*NEW_MISSION\s*:\s*([^\n]+)", re.IGNORECASE)
# Deliberately looser than the line-anchored lifecycle regex above: for risk
# scoring we need the brief gone wherever it starts, and drafts routinely embed
# it mid-sentence ("...plus 'NEW_MISSION: <brief>'"). Line-anchoring here left
# the brief in the scored text and kept mis-holding nudges.
_NEW_MISSION_BRIEF_RE = re.compile(r"NEW_MISSION\s*:", re.IGNORECASE)

# Distinct on purpose: a draft that was never sent is not a nudge.
NUDGES_DRAFTED = 0
NUDGES_SENT = 0

# target -> {"sig": <pane signature>, "since": <ts it last changed>}
_SIG_STATE = {}
# target -> {"attempt": int, "last_nudge": str|None, "prior_nudges": [str],
#            "next_at": ts, "flagged": bool}
# prior_nudges is what makes the escalation ladder real: without it every
# attempt re-drafted from the same pane excerpt and produced the same words.
_NUDGE_STATE = {}
# target -> latest user-visible nudge lifecycle event
_NUDGE_EVENTS = {}
_CONTINUATIONS_SPAWNED = set()
# target -> ts of the last successful close, so a repeating key cannot reap the
# same pane dozens of times. Process-local on purpose: it guards a burst, not a
# lifetime, and nothing downstream should treat it as history.
_REAPED = {}
# target -> ts of the last herdr tab focus, for the same held-key reason and
# with the same process-local scope. Focusing is idempotent, so this bounds
# cost, not damage.
_FOCUSED = {}
_MISSIONS_LAUNCHED = set()
_DROPPED_REPOS = set()  # configured repos that are missing / not git checkouts


# Escalation lives in memory, which is right for the long-running TUI and wrong
# for `--sweep`: each run started at attempt 1 and re-sent the same gentle poke
# to a pane that had already ignored it, so the ladder never climbed unattended.
# BOTH dicts have to persist — with an empty _SIG_STATE the first observation of
# any pane looks like fresh movement and clears the attempt counter anyway.
NUDGE_STATE_FILE = Path(
    os.environ.get("SHEP_NUDGE_STATE",
                   str(Path.home() / ".mission-engine" / "shep-nudge-state.json"))
)


def load_nudge_state(path=None, events_only=False):
    """Restore escalation + signature state from disk. Best-effort.

    ``events_only`` reloads just the display events, for the TUI's refresh tick.
    The ladder is deliberately excluded there: the TUI keeps its own drafting
    bookkeeping (``assessed_fingerprint``, ``proposed``, suppression) in the
    same dict, and re-merging the sweep's copy every few seconds would reset it
    mid-draft and re-draft the same pane on a loop. Ladder state is read once at
    startup, which is all it takes to stop the TUI re-nudging a pane the sweep
    just wrote to.
    """
    try:
        data = json.loads((path or NUDGE_STATE_FILE).read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if not events_only:
        _SIG_STATE.update(data.get("sig") or {})
        _NUDGE_STATE.update(data.get("nudge") or {})
    # Reloaded on the TUI's refresh tick too, unlike the ladder: the pile is
    # append-only facts about finished work, so merging the sweep's copy in can
    # only ever add rows the operator has not seen. The ladder is excluded there
    # because re-merging it mid-draft resets drafting bookkeeping; that hazard
    # does not exist here.
    #
    # Shape-guarded because this function is documented best-effort and the
    # `try` above wraps only the JSON parse: a `done` key holding a list raised
    # AttributeError straight out of a loader whose contract is to return False
    # on anything it cannot read.
    stored_done = data.get("done")
    if isinstance(stored_done, dict):
        _DONE_PILE.update(prune_done_pile(stored_done))
    for target, event in (data.get("events") or {}).items():
        current = _NUDGE_EVENTS.get(target)
        # Newest wins, rather than a blind update. The TUI reloads this every
        # few seconds while also recording its own sends, so letting disk win
        # unconditionally would replace the event the operator just created
        # with an older pass from the sweep -- their own action visibly
        # reverting on screen a moment after they took it.
        if not isinstance(event, dict):
            continue
        if not current or event.get("at", 0) >= current.get("at", 0):
            _NUDGE_EVENTS[target] = event
    return True


# Sessions that declared themselves finished, {target: record}. Durable because
# the declaration is a fact about work that happened, not a property of a pane
# that happens to still be on screen.
_DONE_PILE = {}
# Long enough that a weekend's finished work is still there on Monday. This pile
# is a review queue, so expiry is the only thing that removes an entry the
# operator never looked at — closing is always their keypress.
DONE_PILE_TTL = 14 * 24 * 3600
# The pile is a review queue, and a queue nobody can finish reading is one the
# operator learns to skip -- the same failure the TTL and the persisted
# `clear_done` exist to avoid. At the observed rate (66 sessions finished in
# three days) fourteen days is ~300 CLOSE rows, so age alone is not a bound.
# Oldest are dropped first: the newest finished work is the most likely to still
# be worth reviewing, and anything genuinely important is reaped, not aged out.
DONE_PILE_MAX = 60


def prune_done_pile(pile, now=None):
    """Drop finished-work records past DONE_PILE_TTL. -> new dict.

    Snapshots the mapping before iterating. `collect_all` writes `_DONE_PILE`
    from the background refresh thread while the curses thread reads it here to
    render, and an insert landing mid-comprehension raises "dictionary changed
    size during iteration" on the render thread -- which kills the TUI. Every
    other cross-thread structure in the loop is behind io_lock or draft_lock;
    this one is not, and a copy is cheaper than adding a third lock.

    Validates the whole shape, not just the timestamp. This is the only
    boundary a record crosses coming off disk, and `pending_actions` reads
    target/label/reason/repo by bare subscript -- so a partial entry (a
    hand-edit, a schema skew between the sweep and the TUI on the shared state
    file) raised KeyError on every redraw, unrecoverable without deleting the
    state file.
    """
    now = time.time() if now is None else now
    kept = {}
    for target, record in list((pile or {}).items()):
        if not isinstance(record, dict) or not record.get("target"):
            continue
        if not isinstance(record.get("at"), (int, float)):
            continue
        if now - record["at"] >= DONE_PILE_TTL:
            continue
        kept[target] = {
            "target": record["target"],
            "label": record.get("label") or record["target"],
            "reason": record.get("reason") or "declared itself done",
            "repo": record.get("repo") or "",
            # Carried through, not rebuilt away. This validator reconstructs
            # each record field by field, so a key it does not name is silently
            # dropped on every load -- which for `identity` would mean every
            # reloaded pane looked like a new session and the pane-id-reuse
            # guard would quietly stop working.
            "identity": (
                record["identity"] if isinstance(record.get("identity"), list)
                else [record.get("label") or "", record.get("repo") or ""]
            ),
            "at": record["at"],
        }
    if len(kept) <= DONE_PILE_MAX:
        return kept
    newest = sorted(kept.items(), key=lambda kv: kv[1]["at"], reverse=True)
    return dict(newest[:DONE_PILE_MAX])


def _session_identity(row):
    """What makes this a different session on the same pane id.

    herdr recycles pane ids (see the note in `reap_session`), and the done pile
    is keyed on the pane, so identity has to come from something the next
    occupant would change. Label and checkout are what the operator reads in the
    queue, so a mismatch there is exactly the case where a stale record would be
    shown against the wrong work.
    """
    return (
        str(row.get("label") or session_name(row) or ""),
        repo_name(row.get("cwd")),
    )


def record_done(row, reason, now=None):
    """Remember that this session declared itself finished. -> the record.

    Keeps the label and reason, not just the id, because the pile has to stay
    readable after the pane is gone — "9298c4bddef9 is done" is not a review
    queue. First declaration wins: a pane can re-render SAFE_TO_CLOSE on every
    collection, and letting each one overwrite would keep resetting the age of
    work that finished hours ago.

    "First" is scoped to one session, not to one pane id. herdr reuses pane ids,
    and with a 14-day TTL a pane that finished mission A on Monday would hand
    back Monday's label, reason and age for mission B on Wednesday — and B's own
    completion would never be recorded, because the slot was already taken.
    A different session on the same id replaces the record instead.
    """
    target = row.get("target") or row.get("id")
    if not target:
        return None
    existing = _DONE_PILE.get(target)
    if existing and existing.get("identity") == list(_session_identity(row)):
        return existing
    label, repo = _session_identity(row)
    record = {
        "target": target,
        "label": label or target,
        "reason": " ".join(str(reason or "declared itself done").split())[:160],
        "repo": repo,
        # Listified because this round-trips through JSON, which has no tuples:
        # a tuple written now reads back as a list and would never compare equal
        # again, quietly turning every pane into "a new session" after a reload.
        "identity": [label, repo],
        "at": time.time() if now is None else now,
    }
    _DONE_PILE[target] = record
    return record


def done_pile(now=None):
    """The finished-work review queue, newest first."""
    return sorted(
        prune_done_pile(_DONE_PILE, now).values(),
        key=lambda record: record.get("at", 0),
        reverse=True,
    )


def clear_done(target):
    """Forget one finished-work record, once the operator has dealt with it.

    Persists the removal. Popping only the in-memory dict left the entry on
    disk, and `load_nudge_state` merges that file back on every refresh tick --
    so a reviewed row reappeared within seconds and the queue could never empty.
    """
    if _DONE_PILE.pop(target, None) is None:
        return False
    persist_nudge_target(target)
    return True


def save_nudge_state(targets, path=None):
    """Persist state for the targets just observed.

    Filtering to live targets is most of the garbage collection story: a pane
    that no longer exists simply stops being written, so the file cannot grow
    without bound and no TTL has to be tuned. Close-ask memory and the finished
    -work pile are the two deliberate exceptions — see below.
    """
    targets = set(targets or ())
    payload = {
        "sig": {k: v for k, v in _SIG_STATE.items() if k in targets},
        # A pane missing from one listing must not forget it was already asked to
        # close. Dropping it re-arms the ask, and under --sweep — a fresh process
        # per run — one absent listing is enough. Close memory therefore outlives
        # the live-target filter. It is the only field that does, and it is one
        # small entry per pane ever asked, so the growth story stays bounded in
        # practice without a TTL to tune.
        "nudge": {
            k: v
            for k, v in _NUDGE_STATE.items()
            if k in targets or v.get("close_requested")
        },
        # The unattended sweep is a separate process that exits after every
        # pass, so each nudge it drafted, held, or sent died with that process's
        # memory. The TUI — the one place an operator actually watches — reads
        # these for the NUDGE column and the selected-row detail line, and so
        # rendered "-" and no detail for a fleet that had been nudged all night.
        # Same live-target filter as `sig`, so it cannot grow without bound.
        "events": {k: v for k, v in _NUDGE_EVENTS.items() if k in targets},
        # Finished work outlives the pane that produced it, which is the whole
        # point: `reap_ready` is re-derived from pane text on every collection,
        # so a session that declared SAFE_TO_CLOSE dropped off the queue the
        # moment that line scrolled away or the pane went. Sixty-six sessions
        # declared themselves done across three days and the operator could only
        # ever see the handful still showing it. Kept whole rather than filtered
        # to live targets, and pruned by DONE_PILE_TTL instead.
        "done": prune_done_pile(_DONE_PILE),
    }
    return _write_nudge_state(payload, path or NUDGE_STATE_FILE)


@contextlib.contextmanager
def _nudge_state_lock(destination):
    """Serialize cross-process state read/modify/write operations."""
    lock_path = destination.with_name(f"{destination.name}.lock")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # The caller's state write remains best-effort. If the lock itself
        # cannot be created, yield so a restricted filesystem does not turn a
        # nudge into a crash; atomic replace still prevents torn JSON.
        yield
        return
    try:
        lock = lock_path.open("a+", encoding="utf-8")
    except OSError:
        yield
        return
    with lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _write_nudge_state(payload, destination):
    """Replace the shared state file in one step. Best-effort.

    Atomic, because two processes share this file: the sweep rewrites it every
    five minutes and the TUI reads it at startup. `write_text` truncates first,
    so a read landing inside that window gets invalid JSON, and
    `load_nudge_state` answers a torn read the same way it answers a missing one
    -- by starting blank. That is the exact empty screen this file exists to
    prevent, and it would have been an intermittent one, which is worse. It also
    means a crash mid-write leaves the whole fleet's ladder and dedupe history
    truncated rather than merely stale.

    The staging name carries the pid because both processes now write: sharing
    one `.tmp` path lets two writers interleave into it, and `os.replace` would
    then atomically publish a file that is half one payload and half the other.
    """
    with _nudge_state_lock(destination):
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged = destination.with_name(f"{destination.name}.{os.getpid()}.tmp")
            staged.write_text(json.dumps(payload))
            os.replace(staged, destination)
            return True
        except OSError:
            return False


def persist_nudge_target(target, path=None):
    """Merge ONE target's ladder state and latest event into the shared file.

    Every route to a pane goes through `_deliver_nudge`, and until this existed
    none of the TUI's routes reached disk. The unattended sweep is a separate
    process that reloads this file each pass, so it never learned that a nudge
    the operator approved had been sent: its dedupe history still said those
    words were unused, it redrafted them, the risk gate held them again, and the
    item the operator had just cleared was back in the pending queue minutes
    later -- approving it only ever dispatched it, never resolved it.

    One target rather than `save_nudge_state`, which dumps this process's whole
    memory: the TUI reads the ladder once at startup and then diverges, so a
    full save from it would put hours-old entries over the sweep's current ones
    for every other pane in the fleet.
    """
    if not target:
        return False
    destination = path or NUDGE_STATE_FILE
    with _nudge_state_lock(destination):
        try:
            data = json.loads(destination.read_text())
        except (OSError, json.JSONDecodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        for section, source in (("nudge", _NUDGE_STATE), ("events", _NUDGE_EVENTS)):
            entry = source.get(target)
            if entry is None:
                continue
            if not isinstance(data.get(section), dict):
                data[section] = {}
            data[section][target] = entry
        if isinstance(data.get("done"), dict) and target not in _DONE_PILE:
            data["done"].pop(target, None)
        # The lock is held across the read-modify-replace; bypass the wrapper's
        # second lock so another process cannot interleave between those steps.
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            staged = destination.with_name(f"{destination.name}.{os.getpid()}.tmp")
            staged.write_text(json.dumps(data))
            os.replace(staged, destination)
            return True
        except OSError:
            return False


def _run(cmd, cwd=None, env=None, timeout=8):
    try:
        return subprocess.run(
            cmd, cwd=cwd, env=env, timeout=timeout,
            capture_output=True, text=True, check=False,
        )
    except subprocess.TimeoutExpired:
        # subprocess.run RAISES on timeout, and this runs on the curses thread —
        # an unhandled raise here kills the whole TUI. Every caller already
        # branches on returncode, so degrade to a normal non-zero result.
        return subprocess.CompletedProcess(
            cmd, 124, "", f"timed out after {timeout}s"
        )
    except OSError as exc:
        # Missing optional CLIs (including bd on a machine without Beads) must
        # become visible unavailable state, never tear down the curses loop.
        return subprocess.CompletedProcess(
            cmd, 127, "", f"{type(exc).__name__}: {exc}"
        )


def _process_failure_detail(proc, limit=120):
    """Return a compact diagnostic from a failed JSON-capable subprocess.

    ``herdr_ctl.py`` writes structured failures to stdout and leaves stderr
    empty. Looking only at stderr reduced protocol mismatches and other useful
    controller errors to the unhelpful ``non-zero exit`` shown in the fleet
    table, leaving the operator without a recovery path.
    """
    for stream in (getattr(proc, "stderr", ""), getattr(proc, "stdout", "")):
        raw = str(stream or "").strip()
        if not raw:
            continue
        detail = raw
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            pass
        else:
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                code = str(error.get("code") or "").strip()
                message = str(error.get("message") or "").strip()
                detail = ": ".join(part for part in (code, message) if part)
            elif isinstance(error, str) and error.strip():
                detail = error.strip()
                # herdr_ctl wraps the raw herdr JSON error in a human-readable
                # prefix before emitting its own JSON error envelope.
                marker = detail.find("{")
                if marker >= 0:
                    try:
                        nested = json.loads(detail[marker:])
                    except json.JSONDecodeError:
                        pass
                    else:
                        nested_error = (
                            nested.get("error")
                            if isinstance(nested, dict)
                            else None
                        )
                        if isinstance(nested_error, dict):
                            code = str(nested_error.get("code") or "").strip()
                            message = str(
                                nested_error.get("message") or ""
                            ).strip()
                            parsed = ": ".join(
                                part for part in (code, message) if part
                            )
                            if parsed:
                                detail = parsed
        detail = " ".join(detail.split())
        if detail:
            return detail[:limit]
    return "non-zero exit"


def _error_row(source, err):
    return [{
        "source": source, "id": "-", "label": f"[unavailable: {err}]",
        "status": "error", "cwd": "-", "target": None,
    }]


# --- Pane capture ------------------------------------------------------------
#
# One capture path per transport, shared by the status/stall tracker and the
# context preview so both reason over exactly the same bytes.

def capture_pane(source, target, lines=15, ansi=False):
    """Raw pane text for a row. `ansi=True` keeps the SGR escapes.

    herdr goes through `herdr pane read --format ansi`, which passes the pane's
    real colour bytes through; herdr_ctl.py's `session read` hardcodes
    `--format text` and would flatten them.
    """
    if not target:
        return ""
    try:
        if source == "herdr":
            proc = _run([
                HERDR_BIN, "pane", "read", target.removeprefix("herdr:"),
                "--source", "visible", "--lines", str(lines),
                "--format", "ansi" if ansi else "text",
            ])
            return proc.stdout if proc.returncode == 0 else ""
        if source == "t3":
            # A T3 thread is not a pty. Without this the tmux fallback below
            # would run `capture-pane -t <uuid>` and report someone else's pane.
            return ""
        if source == "warp":
            # Warp's terminal-server owns the pty, but exposes no supported
            # capture API. Never fall through to tmux with a Warp PID.
            return ""
        cmd = ["tmux", "capture-pane", "-p", "-t", target, "-S", f"-{lines}"]
        if ansi:
            cmd.insert(2, "-e")
        proc = _run(cmd)
        if proc.returncode != 0 and ansi:  # older tmux without -e — retry plain
            proc = _run(["tmux", "capture-pane", "-p", "-t", target, "-S", f"-{lines}"])
        return proc.stdout if proc.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        return ""


# --- Stall detection ---------------------------------------------------------

# Spinner frames and elapsed-time readouts churn every frame without meaning any
# real progress, so they're stripped before hashing. Token counters ("↑ 1.2k
# tokens") are deliberately KEPT — those only move when work actually happens.
_SPINNER_RE = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏◐◓◑◒·✢✳∗✻✽*]")
_ELAPSED_RE = re.compile(r"(?<![\w.])(?:\d+h\s*)?(?:\d+m\s*)?\d+s\b|(?<![\w.])\d+m\b")


def is_shell_pane(pane_text):
    """Whether a pane is an OS shell / exited agent rather than a live agent.

    Shared by BOTH collectors on purpose. It first shipped for tmux only, which
    left herdr panes trusting herdr's own agent_status — so a herdr pane sitting
    at a shell prompt could still be reported `done`, land in NUDGEABLE, and get
    a drafted nudge typed into bash. That is not hypothetical: it is how a live
    shell ended up wedged at zsh's `quote>` on an unterminated quote.
    """
    lines = [ln for ln in (pane_text or "").splitlines() if ln.strip()]
    if not lines:
        return False
    last = lines[-1].strip()
    return bool(
        _SHELL_PROMPT_RE.search(last)
        or _DEAD_AGENT_RE.search(last)
        or _SHEP_TUI_RE.search(last)
    )


# An agent holding an open questionnaire — Claude Code's AskUserQuestion and
# permission prompts, and Codex's approval prompts — all render the same way: a
# short list of numbered options with a selection cursor on one of them. Without
# this the box read as `idle` (cursor glyph plus box chrome), so the question
# never reached the operator AND the pane became NUDGEABLE, which types a drafted
# sentence into a live selector and answers it at random.
_ASK_TAIL_LINES = 20
_OPTION_RE = re.compile(r"^(?:[❯›>]\s*)?\d+[.)]\s+\S")
_OPTION_CURSOR_RE = re.compile(r"^[❯›>]\s*\d+[.)]\s+\S")
_BOX_EDGE_CHARS = "│|┃╎┆╭╮╰╯─━ \t"


def _unbox(line):
    """Strip the frame an agent UI draws around its option rows."""
    return line.strip().strip(_BOX_EDGE_CHARS).strip()


def _ask_tail(pane_text):
    lines = [_unbox(ln) for ln in strip_ansi(pane_text or "").splitlines()]
    return [ln for ln in lines if ln][-_ASK_TAIL_LINES:]


def is_asking_pane(pane_text):
    """Whether a pane is blocked on an operator answer rather than working.

    Shared by BOTH collectors for the same reason as ``is_shell_pane``: herdr
    reports the tab's configured agent, not that the agent has stopped to ask.
    The cursor glyph is required — a numbered list in ordinary agent output is
    prose, only an active selector marks one row as chosen.
    """
    options = [ln for ln in _ask_tail(pane_text) if _OPTION_RE.match(ln)]
    return len(options) >= 2 and any(_OPTION_CURSOR_RE.match(ln) for ln in options)


def pane_question_text(pane_text):
    """The question an asking pane is blocked on, for the operator's table."""
    tail = _ask_tail(pane_text)
    first_option = next((i for i, ln in enumerate(tail) if _OPTION_RE.match(ln)), None)
    if first_option is None:
        return "awaiting an answer"
    for line in reversed(tail[:first_option]):
        if not _is_noise(line):
            return line
    return "awaiting an answer"


def pane_question_options(pane_text):
    """The numbered choices of an open questionnaire, in the order shown.

    Returned as ``(number, label)`` so the operator can be shown what a keypress
    is about to accept — an option list is the one place a single keystroke can
    approve a destructive tool call.
    """
    options = []
    for line in _ask_tail(pane_text):
        match = re.match(r"^(?:[❯›>]\s*)?(\d+)[.)]\s+(\S.*)$", line)
        if match and match.group(1) not in {number for number, _ in options}:
            options.append((match.group(1), match.group(2).strip()))
    return options


def pane_signature(text):
    """Content fingerprint of a pane, blind to purely cosmetic churn."""
    text = _ELAPSED_RE.sub("", _SPINNER_RE.sub("", strip_ansi(text)))
    return "\n".join(" ".join(ln.split()) for ln in text.splitlines()).strip()


def _nudge_state(target):
    state = _NUDGE_STATE.setdefault(
        target,
        {
            "attempt": 0,
            "last_nudge": None,
            "proposed": None,
            "prior_nudges": [],
            "next_at": 0.0,
            "flagged": False,
            "exhausted_reason": None,
            "draft_failures": 0,
            "last_sent": None,
            "assessed_fingerprint": None,
            "send_failures": 0,
            "close_requested": False,
        },
    )
    # State persisted before prior_nudges existed rehydrates without the key.
    state.setdefault("prior_nudges", [])
    state.setdefault("proposed", None)
    state.setdefault("exhausted_reason", None)
    state.setdefault("draft_failures", 0)
    state.setdefault("last_sent", None)
    state.setdefault("assessed_fingerprint", None)
    state.setdefault("send_failures", 0)
    state.setdefault("close_requested", False)
    legacy_last = state.get("last_nudge")
    if legacy_last and legacy_last not in state["prior_nudges"]:
        state["prior_nudges"].append(legacy_last)
        del state["prior_nudges"][:-NUDGE_HISTORY_DEPTH]
    proposed = state.get("proposed")
    if (
        not state.get("last_sent")
        and isinstance(proposed, dict)
        and proposed.get("status") == "sent"
    ):
        state["last_sent"] = dict(proposed)
    return state


# How many previously-sent nudges to show the drafter. Tracks the ladder rather
# than being pinned at a literal: this is what stops attempt 6 re-sending what
# attempt 1 said, and `is_repeat_nudge` compares against exactly this window, so
# a history shorter than MAX_NUDGE_ATTEMPTS makes the oldest rungs invisible to
# both the drafter and the dedupe. Bounded by MAX_NUDGE_CHARS per entry, so the
# whole history costs under a kilobyte of prompt.
NUDGE_HISTORY_DEPTH = MAX_NUDGE_ATTEMPTS
# Containment above which two drafts are "the same message reworded". Biased
# toward over-suppression on purpose: a wrongly-suppressed nudge costs one
# cooldown and ends at the existing human handoff, while a wrongly-sent repeat
# is exactly the noise this guards against.
NUDGE_REPEAT_RATIO = 0.70
_NUDGE_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]+")
# Words carried by almost every nudge; counting them makes unrelated drafts look
# similar and would suppress genuinely new instructions.
_NUDGE_STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from has have if in is it its "
    "of on or that the then there this to up was what when which who will with "
    "you your now next please make sure just after once still".split()
)


def _stem(word):
    """Crude suffix strip so 'fix'/'fixing' and 'test'/'tests' compare equal.

    ponytail: naive suffix rules, not a real stemmer — swap in one only if
    duplicate detection is measurably missing rewordings.
    """
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _nudge_tokens(text):
    """Content words of a draft, stemmed, for near-duplicate comparison.

    The reducer owns this: verified identical to the local implementation over
    400 randomised drafts before the switch, so dedupe here and dedupe inside
    the reducer cannot drift apart into two different answers about whether one
    nudge repeats another. The fallback below is only for a partial checkout.
    """
    if nudge_tokens is not None:
        return nudge_tokens(text)
    cleaned = _NUDGE_NORMALIZE_RE.sub(" ", (text or "").lower())
    return {_stem(w) for w in cleaned.split() if w not in _NUDGE_STOPWORDS}


def nudge_similarity(a, b):
    """How much of the shorter draft's content is already in the longer, 0.0-1.0.

    Containment rather than Jaccard: a follow-up that repeats the whole
    instruction but drops the boilerplate ("...end with SAFE_TO_CLOSE") scores
    low on Jaccard purely because it is shorter, which let real rewordings
    through.
    """
    ta, tb = _nudge_tokens(a), _nudge_tokens(b)
    if not ta or not tb:
        return 1.0 if ta == tb else 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def is_close_request(text):
    """True when a draft asks the target to declare itself safe to close."""
    return bool(text) and "safe_to_close" in text.lower()


def is_repeat_nudge(draft, state):
    """True when this draft says what an earlier attempt already said.

    Exact-equality dedup let a cosmetically reworded repeat through as "new",
    so a wedged pane got the same instruction three times in different words.
    Compares against the whole recent history, not just the last one.

    A close request is deduped by kind rather than by wording. Every one of
    them carries a reason written fresh from whatever is on screen, so a repeat
    ask scored a median 0.40 against the repeat ratio: word-similarity caught
    6 of 33 repeats and the other 27 read as new. Across one day that meant 33
    of 68 close asks were repeats, one pane was asked six times, and only 5 asks
    were ever answered. Asking again in new words is the same ask, so the
    wording is not what to compare.
    """
    if not draft:
        return False
    if is_close_request(draft) and state.get("close_requested"):
        return True
    history = list(state.get("prior_nudges") or [])
    if state.get("last_nudge"):
        history.append(state["last_nudge"])
    return any(
        nudge_similarity(draft, prior) >= NUDGE_REPEAT_RATIO for prior in history
    )


def remember_nudge(state, text):
    """Record a draft as sent so later attempts can escalate past it."""
    if not text:
        return
    history = state.setdefault("prior_nudges", [])
    history.append(text)
    del history[:-NUDGE_HISTORY_DEPTH]
    state["last_nudge"] = text


def novel_context_lines(recent_lines, state):
    """Remove Shep's own visible input echoes from the evidence sent to the model."""
    lines = list(recent_lines or [])
    history = list(state.get("prior_nudges") or [])
    if not lines or not history:
        return lines
    remaining = " ".join(" ".join(lines).split())
    for prior in sorted(history, key=len, reverse=True):
        echo = " ".join(str(prior).split())
        if echo:
            remaining = re.sub(re.escape(echo), " ", remaining, flags=re.IGNORECASE)
    last_sent = state.get("last_sent") if isinstance(state, dict) else None
    assessed_context = last_sent.get("context") if isinstance(last_sent, dict) else None
    if assessed_context:
        old_evidence = " ".join(str(assessed_context).split())
        remaining = re.sub(
            re.escape(old_evidence), " ", remaining, flags=re.IGNORECASE
        )
    remaining = " ".join(remaining.split()).strip(" -:;,.`'")
    return [remaining] if re.search(r"[A-Za-z0-9]", remaining) else []


def nudge_evidence_fingerprint(context_text, state=None):
    """Stable identity for the complete cleaned evidence, excluding Shep echoes.

    The echo stripping is Shep's; the hash is the reducer's, so an observation
    built here and one built inside the reducer agree on what counts as the
    same evidence. Verified identical over 200 randomised captures.
    """
    evidence = "\n".join(clean_context_lines(context_text or ""))
    for prior in sorted((state or {}).get("prior_nudges") or (), key=len, reverse=True):
        echo = " ".join(str(prior).split())
        if echo:
            evidence = re.sub(re.escape(echo), " ", evidence, flags=re.IGNORECASE)
    if nudge_evidence_identity is not None:
        return nudge_evidence_identity(evidence)
    normalized = " ".join(evidence.split())
    return hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()


def stalled_seconds(target, now=None):
    """How long this pane's content has been unchanged, or None if unknown."""
    prev = _SIG_STATE.get(target)
    if not prev or not prev.get("since"):
        return None
    return max(0, int((time.time() if now is None else now) - prev["since"]))


def _squashed(text):
    """Whitespace-free form of a pane fragment, for echo matching only."""
    return "".join((text or "").split())


def _change_is_only_sent_nudge_echo(previous, current, state):
    """Whether the pane changed only because our sent text became visible.

    Matched with whitespace removed rather than collapsed: herdr hard-wraps the
    echoed nudge at the pane width, often mid-word, so a nudge longer than the
    pane is never present verbatim. Collapsing left a stray space inside the
    broken word, the match missed, and our own echo was then credited as agent
    progress on nearly every send.
    """
    if not isinstance(state, dict) or not state.get("prior_nudges"):
        return False
    prior = _squashed(previous)
    observed = _squashed(current)
    for text in state.get("prior_nudges") or ():
        echo = _squashed(pane_signature(text))
        if echo:
            prior = prior.replace(echo, "")
            observed = observed.replace(echo, "")
    return observed == prior


def update_stall(target, pane_text, status):
    """Fold pane-signature history into the status.

    A pane that still says "working" but whose signature hasn't moved for
    STALL_AFTER_SECONDS is wedged. Once escalation is exhausted it becomes a
    single human-facing marker instead of more nudges.
    """
    now = time.time()
    sig = pane_signature(pane_text)
    prev = _SIG_STATE.get(target)
    if prev is None or prev["sig"] != sig:
        state = _nudge_state(target) if target in _NUDGE_STATE else {}
        if prev is not None and _change_is_only_sent_nudge_echo(
            prev["sig"], sig, state
        ):
            # Herdr echoes typed input into the pane. That is transport proof,
            # not agent progress: advance the signature baseline while keeping
            # cooldown, attempt count, and dedupe history intact.
            prev["sig"] = sig
            return status
        # Real movement — reset the stall clock and the escalation ladder, but
        # retain the sent text and its assessed context so the next decision
        # sees only genuinely new evidence rather than the accumulated pane.
        proposed = state.get("proposed") if isinstance(state, dict) else None
        last_sent = state.get("last_sent") if isinstance(state, dict) else None
        # An outstanding nudge is one we sent that has not yet resolved the
        # pane. Movement while one is outstanding is movement we prompted.
        outstanding_nudge = (
            isinstance(last_sent, dict) and last_sent.get("status") == "sent"
        )
        # Progress is credited once per send; the ladder is held for as long as
        # the nudge stays unresolved. These are deliberately different spans —
        # crediting once but releasing the ladder on the very next frame is why
        # the cap still could not bind.
        nudge_caused = outstanding_nudge and not last_sent.get("progress_recorded")
        if nudge_caused:
            # Once per send, not once per poll. last_sent survives the ladder
            # reset below, so without this flag every later frame of the same
            # burst of work re-credited the same nudge — 2543 "advanced" events
            # for 62 sends in the first full day of telemetry.
            last_sent["progress_recorded"] = True
            record_outcome("progress", target=target, outcome="advanced")
        _SIG_STATE[target] = {"sig": sig, "since": now}
        _NUDGE_STATE.pop(target, None)
        if state:
            fresh = _nudge_state(target)
            fresh["prior_nudges"] = list(state.get("prior_nudges") or [
                state.get("last_nudge")
            ])[-NUDGE_HISTORY_DEPTH:]
            fresh["prior_nudges"] = [text for text in fresh["prior_nudges"] if text]
            fresh["last_nudge"] = state.get("last_nudge")
            fresh["last_sent"] = dict(last_sent) if isinstance(last_sent, dict) else None
            fresh["assessed_fingerprint"] = state.get("assessed_fingerprint")
            # Survives the reset for the same reason prior_nudges does: the pane
            # moving is what clears the ladder, and an agent replying to a close
            # ask moves the pane. Drop this and the reply re-arms the same ask.
            fresh["close_requested"] = bool(state.get("close_requested"))
            if outstanding_nudge:
                # A pane moving in response to a nudge we sent has not earned a
                # fresh escalation budget. Resetting `attempt` on any movement
                # is what let one target absorb 35 nudges in four days: each
                # nudge moved the pane, the movement cleared the ladder, and
                # MAX_NUDGE_ATTEMPTS — whose entire job is to hand a target
                # nudging cannot fix to a human — could never bind. The budget
                # refills only once the pane moves with no nudge outstanding.
                fresh["attempt"] = state.get("attempt", 0)
                if fresh["attempt"] >= MAX_NUDGE_ATTEMPTS:
                    # Past the cap the honest move is to say so where the
                    # operator can see it, not to keep drafting into a pane that
                    # never resolves.
                    #
                    # The cap was 3, on evidence: across the first four days of
                    # sends, 11 of 12 resolutions arrived within two nudges and
                    # only one ever arrived later. It is now 6 by the operator's
                    # call, because 3 made the per-pane ceiling the binding
                    # limit on fleet throughput and they would rather spend the
                    # extra attempts. That evidence is recorded, not deleted —
                    # if the later rungs turn out to resolve nothing, this is
                    # the number to put back.
                    fresh["exhausted_reason"] = "needs_human"
                    if not state.get("exhausted_reason"):
                        record_outcome(
                            "terminal", target=target, outcome="human_handoff",
                        )
            if isinstance(proposed, dict) and proposed.get("status") == "sent":
                fresh["proposed"] = dict(proposed)
        return status
    if status != "working":
        # Only a "working" pane can be promoted to "stalled", but `since` is
        # left alone for every status: it is this pane's quiet clock, and
        # `should_nudge` needs it to tell a settled pane from one that herdr
        # merely labelled idle a moment ago. Resetting it here pinned
        # `stalled_seconds` at ~0 for every idle pane, so the drafter was told
        # "stalled for 0s" and the gate had no way to wait for quiet.
        return status
    if now - prev["since"] < STALL_AFTER_SECONDS:
        return status
    if _nudge_state(target)["attempt"] >= MAX_NUDGE_ATTEMPTS:
        record_outcome("terminal", target=target, outcome="human_handoff")
        return UNRESPONSIVE
    return "stalled"


def pane_is_quiet(row, now=None):
    """Whether this pane has actually stopped producing output.

    A NUDGEABLE status is a claim, not an observation: `idle` comes from herdr's
    own agent_status, and a pane it calls idle is routinely still printing. That
    is what made drafting so wasteful — measured over one 5-second window (the
    median draft round-trip), 7 of 11 "idle"/"done" panes had moved by the time
    a draft came back, and 6 of those 7 had produced genuinely new output rather
    than a ticking spinner. Every one of those drafts was written against a pane
    that had already answered its own question, and was thrown away on arrival.

    So the gate waits for shep's own evidence instead of the label. The clock is
    kept by update_stall against the cosmetic-churn-blind pane_signature, so a
    spinner tick does not reset it but real output does.
    """
    quiet = row.get("quiet_for")
    if quiet is None:
        # Collector rows always carry this; a row that does not is either an
        # error placeholder or a pane seen only once, and neither is evidence
        # of quiet. Fall back to the live clock, then decline.
        quiet = stalled_seconds(row.get("target") or row.get("id"), now)
    return quiet is not None and quiet >= NUDGE_QUIET_SECONDS


def should_nudge(row, state):
    return (
        row.get("status") in NUDGEABLE
        and not row.get("reap_ready")
        and not state.get("exhausted_reason")
        and state.get("attempt", 0) < MAX_NUDGE_ATTEMPTS
        and time.time() >= state.get("next_at", 0.0)
        and pane_is_quiet(row)
    )


def note_draft_failure(state, now=None):
    """Apply the shared bounded gateway-failure schedule to one evidence state."""
    failures = state.get("draft_failures", 0) + 1
    state["draft_failures"] = failures
    state["next_at"] = (time.time() if now is None else now) + DRAFT_FAILURE_BACKOFF_SECONDS[
        min(failures, MAX_DRAFT_FAILURES) - 1
    ]
    if failures >= MAX_DRAFT_FAILURES:
        state["exhausted_reason"] = "draft_unavailable"
    return failures


def note_send_failure(state, now=None):
    """Schedule a bounded retry of the same drafted nudge after transport failure."""
    failures = state.get("send_failures", 0) + 1
    state["send_failures"] = failures
    state["next_at"] = (time.time() if now is None else now) + SEND_FAILURE_BACKOFF_SECONDS[
        min(failures, MAX_SEND_FAILURES) - 1
    ]
    if failures >= MAX_SEND_FAILURES:
        state["exhausted_reason"] = "send_failed"
    return failures


# --- Risk classification (fail-closed) --------------------------------------
#
# Applied to the DRAFTED NUDGE TEXT, not the pane content. Ordered most
# dangerous first, first match wins. Only `safe_continuation` may auto-send;
# `unknown` must never auto-fire. Bias is toward over-blocking: a false
# "needs review" costs one keypress, a false "safe" could push or delete.

_RISK_PATTERNS = (
    ("destructive", "destructive command", re.compile(
        r"\brm\s+-[a-z]*[rf]|\bgit\s+push\b[^\n]*(?:--force\S*|-f\b)|\bpush\s+-f\b"
        r"|\bfilter-repo\b|\breset\s+--hard\b|\b(?:drop|truncate)\s+table\b"
        r"|\bdelete\s+from\b", re.IGNORECASE)),
    ("send_gated", "sends something externally", re.compile(
        r"\b(?:e-?mail|slack|dm)\b|\bpost\s+(?:to|in)\b|\bnotify\s+(?:the\s+)?(?:customer|client)\b"
        r"|\bmessage\s+(?:the\s+)?(?:customer|client|team)\b", re.IGNORECASE)),
    ("credential", "rotates or exposes a secret", re.compile(
        r"\b(?:rotate|revoke|regenerate|reissue|reset)\b[^.\n]{0,40}"
        r"\b(?:key|token|secret|credential|password|api[_\s-]?key)\b"
        # Underscores are word characters, so \bKEY\b never matches inside
        # AI_GATEWAY_API_KEY — the prefix has to absorb them explicitly.
        r"|\b[A-Z][A-Z0-9_]*_(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?)\b"
        r"|\bvault\s+secret\b", re.IGNORECASE)),
    ("merge", "merges or closes without review", re.compile(
        r"\bmerge\s+(?:the\s+)?(?:mr|pr|merge request|pull request)\b"
        r"|\bmerge\s+(?:this|it|these\s+changes?|the\s+changes?)\s+in\b"
        r"|\bland\s+(?:this|it|the\s+(?:mr|pr|changes?))\b"
        r"|\bclose\b[^\n]*\bwithout\s+review\b|\bapprove\s+and\s+merge\b", re.IGNORECASE)),
    ("push", "pushes, deploys, or touches prod", re.compile(
        r"\bgit\s+push\b"
        r"|\bpush\b[^\n]{0,60}\b(?:commits?|changes?|branch|remote)\b"
        r"|\bcommit(?:\s+(?:the\s+)?(?:changes?|work|code))?\s+and\s+push\b"
        r"|\bdeploy\b|\brelease\b|\bprod(?:uction)?\b", re.IGNORECASE)),
)

# A drafted nudge that says "do NOT merge the MR" was scored identically to one
# saying "merge the MR" — the filter matched the verb and never saw the negator
# in front of it. Over half of one live review queue was nudges blocked for
# instructing an agent NOT to do the risky thing.
_NEGATOR_RE = re.compile(
    r"\b(?:do\s?n[o']?t|does\s?n[o']?t|did\s?n[o']?t|cannot|can\s?n[o']?t|never|not|no"
    r"|without|avoid|skip|refrain\s+from|rather\s+than|instead\s+of|hold\s+off\s+on)\b",
    re.IGNORECASE,
)
# Negation does not cross a clause boundary: in "don't merge; then git push"
# the push is a real instruction, not a negated one. Dashes count as boundaries
# because "do not merge the MR — just git push it" is the dangerous shape: the
# negation binds only to the first verb, and reading it as covering both would
# auto-send a push.
_CLAUSE_SPLIT_RE = re.compile(r"[.;!?\n—–]|--")
_NEGATION_WINDOW = 48


def _is_negated(text, start):
    """Whether the risky verb at `start` sits inside a negated clause."""
    window = text[max(0, start - _NEGATION_WINDOW):start]
    return bool(_NEGATOR_RE.search(_CLAUSE_SPLIT_RE.split(window)[-1]))


# Every regex below is ASCII, but the terminal renders Unicode: a soft hyphen
# inside "merge", a zero-width space inside "git", or a fullwidth "ｐ" in
# "push" all displayed as the real action while the patterns saw nothing.
def _normalize_risk_text(text):
    """An agent terminal renders a soft hyphen or zero-width space as nothing,
    so `mer­ge the MR` reads as a merge instruction to the agent while
    defeating an ASCII pattern. Fold the draft to the form the agent will
    actually act on before scoring it."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    return "".join(c for c in text if unicodedata.category(c) != "Cf" and c != "\u00ad")


# Nominalized and gerund forms name the risky action without the verb shapes
# the patterns above recognise ("the merge of MR !2", "by merging the MR").
# A draft that names one of these can never auto-send, whatever verb led it.
_RISKY_NOUN_RE = re.compile(
    r"\bmerg(?:e|es|ing)\b"
    r"|\bforce[-\s]?push\w*\b|\bpush(?:es|ing)?\b|\brebas(?:e|ing)\b"
    # "deployment" only counts with a target: "deployment smoke test" names a
    # test, not an action, and is pinned safe in the quality-eval suite.
    r"|\bdeploy(?:s|ed|ing)?\b|\bdeployments?\s+(?:of|to|into)\b"
    r"|\brelease(?:s|ing)?\b|\bprod(?:uction)?\b"
    r"|\bdelet(?:e|es|ing|ion)\b|\bremoval\b|\bdrop(?:s|ping)?\b|\btruncat(?:e|es|ing|ion)\b"
    r"|\brotat(?:e|es|ing|ion)\b|\brevocation\b|\breissue\b|\bfilter-repo\b"
    r"|\bhard\s+reset\b|\breset\s+--hard\b"
    r"|\breset\s+(?:the\s+|this\s+)?(?:branch|head|main|master|origin|repo\w*)\b",
    re.IGNORECASE)

# The safe-verb set is the allowlist gate in classify_risk. It mirrors the
# drafter-facing lexicon (canonical_nudge_phrases) phrase for
# safe_continuation: only a draft that contains one of these verbs AND names
# no risky thing anywhere may auto-send.
#
# `safe_to_close` is the agent's own completion signal, and `commit` writes only
# to the local repo — pushing, merging, and deploying are separate risky verbs
# that still gate on their own. Both were missing, so the drafts that say them
# fell through to `unknown` and were held: 24 of 65 held drafts in one measured
# run were withheld for lacking a verb form, not for naming anything risky.
#
# Only the imperative `commit`/`commits` is listed. `committed`/`committing`
# show up in descriptive tails ("nothing is committed yet"), where matching them
# would pass a draft on a clause that is not its instruction.
_SAFE_VERB_RE = re.compile(
    r"\b(?:continue|proceed|carry on|keep going|resume|fix|next\s+todo"
    r"|next\s+task|wrap\s+up|finish|verify|run|rerun|stop"
    r"|safe_to_close|commits?)\b",
    re.IGNORECASE,
)


_CANONICAL_NUDGE_PHRASES = {
    "destructive": "git push --force",
    "credential": "rotate the API key",
    "send_gated": "email the customer",
    "merge": "merge the MR",
    "push": "git push",
    "safe_continuation": "continue",
}


def canonical_nudge_phrases():
    """Return the shared producer/sensor vocabulary for drafted nudges."""
    return dict(_CANONICAL_NUDGE_PHRASES)


def nudge_lexicon_prompt():
    """Render the sensor vocabulary as drafting guidance for both producers."""
    lines = [
        ("CANONICAL NUDGE LEXICON: when an action applies, use its exact phrase so "
        "the safety sensor can route it; never introduce an action just to use a phrase.")
    ]
    lines.extend(
        f'- {category}: use "{phrase}"'
        for category, phrase in canonical_nudge_phrases().items()
    )
    return "\n".join(lines)


# Task runners hide what they actually do behind a name. `classify_risk` is
# lexical over a fixed vocabulary of risky verbs, so it reads `make ship`,
# `npm publish` and `scripts/rollout.sh` as ordinary safe continuations -- there
# is no "ship" or "rollout" token to match, and there cannot be, because the
# dangerous part lives in a Makefile the classifier never sees.
#
# That gap became reachable the moment the drafting prompt started asking for
# "the safe step immediately before" a risky action: the most natural rendering
# of the step before a deploy is "run the script that deploys". Prose alone
# could not hold this -- every other safety rule here has an enforcement point,
# and this is that point.
_TASK_RUNNERS = (
    "make", "npm", "yarn", "pnpm", "just", "task", "rake", "nx", "turbo",
    "tox", "nox", "hatch", "poetry", "mage", "gradle", "mvn", "dotnet",
)
# Targets whose whole job is to report rather than change anything. Deliberately
# short: a false hold costs one keypress, a false auto-send can deploy. `build`
# and `compile` are included because they are local and overwhelmingly the
# legitimate next step -- holding them on every pass would train the operator to
# click through holds, which is its own failure.
_SAFE_RUNNER_TARGETS = frozenset(
    "test tests check checks lint lints typecheck types fmt format verify "
    "coverage cov unit e2e spec ci precommit build compile install".split()
)
# Requires an explicit run verb ahead of the runner. Without it "Make sure the
# tests pass" reads as the target `sure` and every such draft would be held --
# a gate nobody can keep is worse than no gate.
_RUN_VERB_RUNNER_RE = re.compile(
    r"\b(?:re)?run(?:s|ning)?\b[^.!?\n]{0,24}?\b(" + "|".join(_TASK_RUNNERS) + r")\b"
    r"(?:\s+run)?\s+(?:-{1,2}[\w-]+\s+)*([\w:./-]+)",
    re.IGNORECASE,
)
# Only things actually being EXECUTED. An earlier version also matched any path
# under scripts/ or bin/, which held "Commit uncommitted scripts/shep.py edits."
# -- naming a source file is not running it, and a gate that fires on ordinary
# file references is one the operator learns to click through.
_SCRIPT_PATH_RE = re.compile(
    r"(?:^|\s)\.{1,2}/[\w./-]+"                      # ./deploy.sh, ../x
    r"|\b[\w./-]+\.(?:sh|bash|zsh|ps1)\b",           # any shell script
    re.IGNORECASE,
)
# A run verb pointed at a path is an invocation whatever the extension, which is
# what catches `run scripts/deploy.py`. Kept separate from the bare-path rule so
# a mere mention of the same file stays untouched.
_RUN_VERB_PATH_RE = re.compile(
    r"\b(?:re)?run(?:s|ning)?\b\s+(?:-{1,2}[\w-]+\s+)*([\w.-]+/[\w./-]+)",
    re.IGNORECASE,
)


def opaque_execution_reason(text):
    """Why this draft delegates to something shep cannot read, or None.

    Answers "can I see what this does?", which is separate from both
    `classify_risk`'s "does it name something dangerous" and
    `nudge_content_quality_reason`'s "is it useful". A target whose body lives
    in a Makefile or a shell script is unreviewable by construction, so it is
    held for a human rather than guessed at.
    """
    text = str(text or "")
    script = _SCRIPT_PATH_RE.search(text) or _RUN_VERB_PATH_RE.search(text)
    if script:
        target = (script.groups() or (None,))[-1] or script.group(0)
        return f"runs a script shep cannot read ({target.strip()})"
    match = _RUN_VERB_RUNNER_RE.search(text)
    if not match:
        return None
    runner, target = match.group(1).lower(), match.group(2).lower().strip(".:/-")
    if target in _SAFE_RUNNER_TARGETS:
        return None
    # A bare runner with no target runs its default, which is no more visible.
    return f"runs an unrecognised {runner} target ({target or 'default'})"


def classify_risk(text):
    """-> (category, reason). Unmatched text is `unknown`, which never auto-sends.

    The draft is normalized first, so a soft hyphen, zero-width space, or
    fullwidth letter cannot smuggle a risky verb past the ASCII patterns.

    A negated risky verb ("do not merge the MR") does not count as that risk —
    but negation can only DOWNGRADE: a draft whose only risk match is negated
    lands on `unknown` for human review, never on `safe_continuation`. Double
    negation ("remember not to skip the merge; proceed") used to discount the
    merge and then promote the draft to safe on the strength of "proceed".

    A trailing NEW_MISSION brief is excluded from deciding the CATEGORY: by
    construction it describes work the agent is explicitly told NOT to start
    here, so its verbs are not instructions for now. But it still gates
    auto-send, because send_nudge types the whole draft, brief included.

    `safe_continuation` is an allowlist, not the fallback it used to be: it
    requires a safe verb AND no risky noun or gerund anywhere in the draft.
    Anything else is `unknown`, which never auto-fires.
    """
    text = _normalize_risk_text(text)
    parts = _NEW_MISSION_BRIEF_RE.split(text, maxsplit=1)
    head, tail = parts[0], parts[1] if len(parts) > 1 else ""
    negated_risk = False
    for category, reason, pattern in _RISK_PATTERNS:
        matches = list(pattern.finditer(head))
        if any(not _is_negated(head, m.start()) for m in matches):
            return category, reason
        if matches:
            negated_risk = True
    if negated_risk:
        # Negation may only downgrade a risk to needs-review. Promoting a
        # negated draft to safe_continuation let "not to skip the merge"
        # auto-send the merge it was double-negating.
        return "unknown", "negated risky instruction"
    if _RISKY_NOUN_RE.search(head):
        return "unknown", "names a risky action without a recognised verb form"
    if tail and (
        any(p.search(tail) for _c, _r, p in _RISK_PATTERNS)
        or _RISKY_NOUN_RE.search(tail)
    ):
        # The brief is excluded from choosing the CATEGORY — it describes work
        # the agent is told not to start yet — but it is still delivered
        # verbatim, so a risky brief must never ride out on an auto-send.
        return "unknown", "mission brief names a risky action"
    opaque = opaque_execution_reason(head) or (
        opaque_execution_reason(tail) and "mission brief runs an opaque target"
    )
    if opaque:
        return "unknown", opaque
    if _SAFE_VERB_RE.search(head):
        return "safe_continuation", "safe continuation"
    return "unknown", "unrecognised instruction"


def nudge_quality_reason(assessment, engine):
    """Return a hold reason when the judge scored a generated draft too low."""
    score = ((assessment or {}).get("scores") or {}).get(engine)
    if score is not None and int(score) < MIN_NUDGE_QUALITY_SCORE:
        return f"quality score {int(score)} is below {MIN_NUDGE_QUALITY_SCORE}"
    return None


_NUDGE_QUALITY_BOILERPLATE = frozenset(
    "continue current objective task work session next keep going resume proceed "
    "where left off finish wrap up verified completion safe close safe_to_close".split()
)
_NUDGE_QUALITY_NOISE_RE = re.compile(
    r"(?:^\s*saw\s*:|codex-gw\s*[▸>-]|claude code|happy session id|"
    r"api/v\d+/proxy|esc to interrupt|contextq:|tokens used)",
    re.IGNORECASE,
)
_NUDGE_QUALITY_URL_RE = re.compile(r"https?://|\bwww\.", re.IGNORECASE)


def nudge_content_quality_reason(text, context=None):
    """Return a deterministic hold reason for an auto-send candidate.

    Risk classification answers whether an instruction is dangerous; this
    answers whether it is useful. Automatic delivery requires at least one
    concrete content anchor shared with the current pane. Human-selected text
    can still use the existing explicit approval path.
    """
    text = str(text or "").strip()
    if not text or is_abstention(text):
        return "no candidate"
    if len(text) > MAX_NUDGE_CHARS:
        return f"candidate exceeds {MAX_NUDGE_CHARS} characters"
    if "?" in text:
        return "question-shaped candidate"
    if _NUDGE_QUALITY_NOISE_RE.search(text) or _NUDGE_QUALITY_URL_RE.search(text):
        return "candidate contains pane or UI noise"
    if re.search(
        r"\b(?:continue|resume|keep going)\b[^.!?]{0,48}"
        r"\b(?:current|objective|task|work|session)\b",
        text,
        re.IGNORECASE,
    ):
        return "generic continuation without a concrete objective"
    context_text = "\n".join(context) if isinstance(context, (list, tuple)) else str(context or "")
    if not context_text.strip():
        return "pane context unavailable"
    candidate_tokens = _nudge_tokens(text) - _NUDGE_QUALITY_BOILERPLATE
    context_tokens = _nudge_tokens(context_text) - _NUDGE_QUALITY_BOILERPLATE
    if not candidate_tokens:
        return "no concrete objective anchor"
    # The close request is a fixed phrase by design and names no file, test or
    # MR, so it never shares a token with a "done" recap -- every one the sweep
    # drafted for a finished pane was held as "not grounded" and the pane sat
    # there. The anchor check exists to keep vague drafts out; this one is not
    # vague, and reaping still needs the agent's own SAFE_TO_CLOSE declaration.
    if is_close_request(text):
        return None
    if not candidate_tokens & context_tokens:
        return "candidate is not grounded in current pane context"
    return None


def bulk_nudge_candidates(
    rows, planned_cache, verified_cache, assessment_cache=None, selected_engine=None
):
    """Return fleet drafts safe for one human-approved bulk send, plus held count."""
    row_by_key = {(row.get("target") or row.get("id")): row for row in rows}
    candidates = []
    held = 0
    for key, planned in planned_cache.items():
        row = row_by_key.get(key)
        if not row or not planned:
            continue
        if row.get("status") not in NUDGEABLE or row.get("reap_ready"):
            held += 1
            continue
        # A missing assessment is not a low score, so this gate passes anything
        # no model graded — which is the intended exemption for a rate-limit
        # recovery: that text is the operator's own words being resent, not a
        # draft a judge needs to rule on. Recorded because it reads like an
        # oversight otherwise, and because it is the one path by which text
        # reaches a bulk send ungraded. The risk and content gates below still
        # apply to it in full.
        if assessment_cache is not None and nudge_quality_reason(
            assessment_cache.get(key), (selected_engine or {}).get(key)
        ):
            held += 1
            continue
        if nudge_content_quality_reason(planned, row.get("context")):
            held += 1
            continue
        category, _reason = classify_risk(planned)
        verified_text, verdict = verified_cache.get(key, (None, None))
        panel_cleared = (
            category in ("merge", "push")
            and verified_text == planned
            and verdict
        )
        if category == "safe_continuation" or panel_cleared:
            candidates.append((row, planned))
        else:
            held += 1
    return candidates, held


def nudge_hold_reason(text, context=None):
    """Return the operator-visible reason a proposal cannot be auto-sent."""
    quality_reason = nudge_content_quality_reason(text, context)
    if quality_reason:
        return quality_reason
    category, risk_reason = classify_risk(text)
    return None if category == "safe_continuation" else risk_reason


def record_nudge_event(target, status, text="", detail=""):
    if target:
        _NUDGE_EVENTS[target] = {
            "status": status,
            "text": text,
            "detail": detail,
            "at": time.time(),
        }


def nudge_row_text(
    row, planned_cache, verified_cache, drafting_keys, verifying_keys,
    assessment=None, engine=None,
):
    """Compact lifecycle status plus nudge text for the fleet table."""
    key = row.get("target") or row.get("id")
    if row.get("reap_ready"):
        reason = row.get("reap_reason") or "explicit completion declaration"
        return f"REAP READY: {reason}"
    if row.get("continuation"):
        if key in _CONTINUATIONS_SPAWNED:
            return f"MISSION SPAWNED: {row['continuation']}"
        return f"NEW MISSION: {row['continuation']}"
    if key in drafting_keys:
        return "DRAFTING"
    planned = planned_cache.get(key)
    if planned:
        category, _reason = classify_risk(planned)
        verified_text, verdict = verified_cache.get(key, (None, None))
        if key in verifying_keys:
            status = "VERIFYING"
        elif nudge_quality_reason(assessment, engine):
            status = "HELD"
        elif nudge_content_quality_reason(planned, row.get("context")):
            status = "HELD"
        elif category == "safe_continuation" or (
            category in ("merge", "push")
            and verified_text == planned
            and verdict
        ):
            status = "READY"
        else:
            status = "HELD"
        return f"{status}: {planned}"
    event = _NUDGE_EVENTS.get(key)
    if not event:
        return "-"
    text = event.get("text") or event.get("detail") or ""
    return f"{event['status'].upper()}: {text}".rstrip(": ")


def _without_sent_echo(text, target):
    """Drop the lines that are only our own nudge echoed back into the pane.

    herdr types a nudge into the pane, so every close request we send is on
    screen moments later. The close detector reads the screen, and the request
    we send carries both the token and an evidence phrase, so an unanswered ask
    satisfied the very test meant to prove the agent finished — shep could reap
    a session on the strength of its own typing.

    The engine prompt already says never to open an instruction with the token.
    A prompt is guidance to a model, not an enforcement point, and the model
    broke that rule fifteen times in a single day. This is the enforcement.

    Line-based and whitespace-squashed for the same reason the stall echo guard
    is: herdr hard-wraps the echo at the pane width, often mid-word, so our text
    is never present verbatim but each wrapped fragment is a substring of it.
    """
    state = _NUDGE_STATE.get(target) if target else None
    echoes = [
        squashed
        for squashed in (
            _squashed(pane_signature(t)) for t in (state or {}).get("prior_nudges") or ()
        )
        if squashed
    ]
    if not echoes:
        return text
    return "\n".join(
        line
        for line in text.split("\n")
        if not (_squashed(line) and any(_squashed(line) in echo for echo in echoes))
    )


def lifecycle_cues(status, pane_text, target=None):
    """Extract explicit close and continuation declarations from terminal output."""
    text = _without_sent_echo(strip_ansi(pane_text or ""), target)
    safe_matches = list(_SAFE_CLOSE_RE.finditer(text))
    safe_match = safe_matches[-1] if safe_matches else None
    newer_user_request = bool(
        safe_match
        and any(
            match.end() > safe_match.end()
            and not _EMPTY_AGENT_PROMPT_RE.fullmatch(match.group(1).strip())
            for match in _USER_SUBMISSION_RE.finditer(text)
        )
    )
    mission_matches = list(_NEW_MISSION_RE.finditer(text))
    continuation = mission_matches[-1].group(1).strip() if mission_matches else None
    explicit_token = re.search(r"\bSAFE_TO_CLOSE\b", text, re.IGNORECASE)
    close_evidence = _CLOSE_EVIDENCE_RE.search(text)
    reap_ready = (
        status in ("done", "idle")
        and safe_match is not None
        and not newer_user_request
        and (explicit_token is not None or close_evidence is not None)
    )
    reason = None
    if reap_ready:
        line_start = text.rfind("\n", 0, safe_match.start()) + 1
        line_end = text.find("\n", safe_match.end())
        if line_end < 0:
            line_end = len(text)
        reason = " ".join(text[line_start:line_end].split())[:160]
    if reap_ready and target:
        # The target declared itself finished; whether a nudge got it there is
        # exactly what the outcome report is trying to answer.
        record_outcome("terminal", target=target, outcome="resolved")
    return {
        "reap_ready": reap_ready,
        "reap_reason": reason,
        "continuation": continuation,
    }


# --- Rate-limit recovery -----------------------------------------------------
#
# A pane can go quiet with nothing wrong with the agent and nothing left to
# think about: the provider answered 429 and the harness gave up retrying. The
# operator's instruction was correct, it simply never ran. Drafting a fresh
# nudge is the wrong move — the fix is to send that same instruction again once
# the quota has had time to clear.

_RATE_LIMIT_RE = re.compile(
    r"^[^\n]*?(?:exceeded retry limit|\b429\b|\btoo many requests\b|"
    r"\brate[ _-]?limit(?:ed|s)?\b)[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)
# The prompt glyphs agents actually echo with: `›` (Codex/Luna) and `❯`
# (Claude Code). A bare `>` is deliberately excluded — it is indistinguishable
# from a diff line, a quoted mail line, or ordinary output, and mistaking one
# for something the operator typed would re-send text nobody wrote.
_PROMPT_ECHO_RE = re.compile(r"^[ \t]*[›❯][ \t]+(\w[^\n]*?)[ \t]*$", re.MULTILINE)


def rate_limited_instruction(pane_text):
    """Return the operator instruction a rate limit swallowed, or None.

    Only fires when the failure is the pane's last word. A prompt echoed after
    the error means the operator already moved on, and re-sending a superseded
    instruction is worse than staying quiet — that is the difference between
    recovering a dropped merge and re-running one nobody asked for twice.
    """
    text = strip_ansi(pane_text or "")
    last_error = None
    for match in _RATE_LIMIT_RE.finditer(text):
        last_error = match
    if last_error is None:
        return None
    if _PROMPT_ECHO_RE.search(text, last_error.end()):
        return None
    instruction = None
    for match in _PROMPT_ECHO_RE.finditer(text[: last_error.start()]):
        instruction = match.group(1).strip()
    return instruction or None


# A quota banner almost always says when the window reopens — "try again in
# 2h 14m", "resets 3pm". Taking it at its word beats the fixed ladder in both
# directions: retrying at 5 minutes against a 3-hour window spends the whole
# retry budget on more 429s, and waiting the full 2-hour rung when the quota
# came back in ten minutes leaves a correct instruction unsent for an hour fifty.
_QUOTA_RETRY_IN_RE = re.compile(
    r"(?:try again|retry|retries|resets?|available|back)\b[^\n]{0,24}?\bin\s+"
    r"((?:\d+\s*(?:hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b[\s,]*"
    r"(?:and\s+)?)+)",
    re.IGNORECASE,
)
_QUOTA_UNIT_RE = re.compile(r"(\d+)\s*([hms])", re.IGNORECASE)
# A clock time is only read as one when it carries `:MM` or am/pm. A bare
# "resets 5" is indistinguishable from "resets 5 minutes" and guessing wrong
# there parks a live pane until tomorrow.
_QUOTA_RESET_AT_RE = re.compile(
    r"resets?\b(?:\s+at)?\s+(?:(\d{1,2}):(\d{2})\s*(am|pm)?|(\d{1,2})\s*(am|pm))",
    re.IGNORECASE,
)
_QUOTA_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}
# Retry a beat after the stated reset, never exactly on it: providers round the
# banner and a resend one second early just draws another 429.
QUOTA_RESET_GRACE_SECONDS = 60
# Bounds a misparse. A real window never runs longer than the clock parse can
# express anyway; this only stops "in 9000 hours" from parking a pane forever.
MAX_QUOTA_WAIT_SECONDS = 24 * 3600


def _seconds_until_clock(hour, minute, meridiem, now=None):
    """Seconds from ``now`` to the next occurrence of a wall-clock time."""
    if meridiem:
        hour = hour % 12 + (12 if meridiem.lower() == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    local = time.localtime(time.time() if now is None else now)
    delta = (
        (hour - local.tm_hour) * 3600
        + (minute - local.tm_min) * 60
        - local.tm_sec
    )
    return delta + 86400 if delta <= 0 else delta


def quota_reset_wait(pane_text, now=None):
    """The quota banner's own reset deadline as ``(banner, seconds)``, or None.

    The banner text comes back with the wait so the caller can freeze the
    deadline the first time it sees a given banner. A clock-time banner still
    reads as "resets 3pm" at half past three, and recomputing it then would roll
    the wait forward a full day for a quota that has already come back.
    """
    text = strip_ansi(pane_text or "")
    best = None  # (position, banner, seconds) — latest statement in the pane wins
    for match in _QUOTA_RETRY_IN_RE.finditer(text):
        seconds = sum(
            int(value) * _QUOTA_UNIT_SECONDS[unit.lower()]
            for value, unit in _QUOTA_UNIT_RE.findall(match.group(1))
        )
        if seconds:
            best = (match.start(), match.group(0).strip(), seconds)
    for match in _QUOTA_RESET_AT_RE.finditer(text):
        if best and match.start() < best[0]:
            continue
        seconds = _seconds_until_clock(
            int(match.group(1) or match.group(4)),
            int(match.group(2) or 0),
            match.group(3) or match.group(5),
            now,
        )
        if seconds:
            best = (match.start(), match.group(0).strip(), seconds)
    if best is None:
        return None
    return best[1], min(best[2] + QUOTA_RESET_GRACE_SECONDS, MAX_QUOTA_WAIT_SECONDS)


def rate_limit_recovery(row, state, pane_text, recent, now=None, persisted=True):
    """Recover the instruction a 429 dropped -> ``(text, suppressed_reason)``.

    ``(None, None)`` means no rate limit is in the way and the caller should
    draft as usual. A reason means the pane is held this pass — quota not yet
    back, per the banner's own deadline — and the caller must skip it. Text is
    the operator's own instruction, to be resent verbatim rather than reworded
    by the drafter.

    The retry ladder never gives up: it escalates through
    ``RATE_LIMIT_BACKOFF_SECONDS`` and then holds at the final rung, resending
    the same instruction for as long as the provider keeps 429ing. A capacity
    outage is not a wedge the operator can unblock by hand, so this is the one
    ladder in shep that must not exhaust to a human handoff — see the
    RETRY-LOOP-SAFETY comment below.

    Shared because both nudge lanes need it and only the sweep had it: a pane
    that hit its quota while the TUI was open never got its dropped instruction
    resent, because the interactive drafter goes straight from the evidence
    fingerprint to the model. Callers must run this BEFORE that fingerprint
    check — a quota-blocked pane emits the same bytes every pass, so a recovery
    placed after it is suppressed as `no_new_evidence` forever.

    `persisted` says whether the caller's nudge state survives the process. The
    banner freeze below is only trustworthy when it does: a pane capture is
    static, so "resets 3pm" still reads that way at half past three, and a
    caller that starts every run with an empty `quota_hold` would re-parse that
    banner as a fresh wait and park a live pane until tomorrow. The sweep loads
    and saves state and takes the banner at its word; the TUI does neither, so
    it falls through to the bounded ladder instead.

    The recovered text still flows through the caller's risk and quality gates,
    so `merge it, force it through` stays held for a human exactly as it would
    if the drafter had proposed it.
    """
    now = time.time() if now is None else now
    key = row.get("target") or row.get("id")
    recovered = rate_limited_instruction(pane_text)
    if not recovered:
        return None, None
    # Deliberately does NOT set `exhausted_reason`: a quota-blocked pane is not
    # moving by definition, and only pane movement clears that field — setting
    # it here would wedge the target permanently instead of holding it until the
    # window reopens.
    hold = state.get("quota_hold") or {}
    stated = quota_reset_wait(pane_text, now=now) if persisted else None
    if stated and stated[0] != hold.get("banner"):
        hold = {"banner": stated[0], "until": now + stated[1]}
        state["quota_hold"] = hold
    if hold.get("until", 0) > now:
        state["next_at"] = hold["until"]
        record_outcome(
            "suppressed", target=key, engine="operational",
            reason="quota_resets_later",
        )
        return None, "quota_resets_later"
    retries = state.get("rate_limit_retries", 0)
    # RETRY-LOOP-SAFETY: bounded by design — do not add a naive rate-limit
    # retry handler on top of this.
    #   concurrency: one `_nudge_state` per target; the sweep runs it
    #     single-threaded and the TUI's non-persisted lane never writes
    #     `exhausted_reason`, so there is nothing here for two callers to race.
    #   attempts:    deliberately UNBOUNDED, on the operator's call
    #     (2026-09-16). A provider capacity outage is not a wedge a human can
    #     unblock by hand — there is nothing to do but wait for the window to
    #     reopen — so this path must never write `exhausted_reason` and hand
    #     the pane to a human. That is what MAX_NUDGE_ATTEMPTS is for (a
    #     stuck pane a human CAN move); capping retries here would instead
    #     strand every session behind an outage until someone notices and
    #     manually resends, which is exactly what this path exists to avoid.
    #   backoff:     RATE_LIMIT_BACKOFF_SECONDS (300, 1800, 7200s), then held
    #     at the final 7200s rung forever — never an inline sleep. Each call
    #     pushes `next_at` out by the rung; the caller's `should_nudge` reads
    #     that field, which is what stops the TUI's 5-second redraw from
    #     spending the whole budget in under a minute.
    #   why no retry handler: this already retries on its own schedule: a
    #     handler bolted on top would just drain the same quota twice.
    state["rate_limit_retries"] = retries + 1
    state["next_at"] = now + RATE_LIMIT_BACKOFF_SECONDS[min(retries, MAX_RATE_LIMIT_RETRIES - 1)]
    if recent:
        row["context"] = "\n".join(recent[-NUDGE_EVIDENCE_LINES:])
    state["proposed"] = {
        "text": recovered,
        "status": "queued",
        "category": classify_risk(recovered)[0],
        "context": row.get("context"),
        "at": now,
    }
    record_outcome(
        "recommended", target=key, engine="operational",
        mode="rate_limit_retry", text=recovered, draft=recovered,
        reason=nudge_content_quality_reason(recovered, row.get("context")),
    )
    return recovered, None


# --- Collectors --------------------------------------------------------------

def collect_herdr():
    if not HERDR_CTL.exists():
        return _error_row("herdr", "herdr_ctl.py not found")
    try:
        proc = _run([sys.executable, str(HERDR_CTL), "session", "list"])
        if proc.returncode != 0:
            return _error_row("herdr", _process_failure_detail(proc))
        data = json.loads(proc.stdout)
        panes = data.get("panes", data if isinstance(data, list) else [])
        rows = []
        for p in panes:
            pane_id = p.get("pane_id") or p.get("target", "").removeprefix("herdr:")
            target = p.get("target") or f"herdr:{pane_id}"
            status = p.get("agent_status", "unknown")
            pane_text = capture_pane("herdr", target)
            pane_tail = [
                line for line in pane_text.splitlines() if line.strip()
            ][-_PANE_TAIL_LINES:]
            # herdr names a pane's agent from the command it was launched with,
            # so a wrapper hides it: away-mode missions run under Happy (that is
            # what lets the phone reach them) and herdr reports agent=None with
            # agent_status="unknown". "unknown" is not in NUDGEABLE, so every
            # check below was skipped and the pane was never classed working,
            # never stall-checked, never nudged and never reaped — for exactly
            # the missions that run while nobody is watching, which is the one
            # case this whole engine exists for.
            #
            # Believe the pane's own chrome instead of the launch command. The
            # shell guard below still runs first and still wins, so promoting
            # this cannot type a nudge into a bare zsh.
            if status == "unknown" and _AGENT_CHROME_RE.search(pane_text):
                status = "idle"
            # A shell prompt overrides whatever herdr believes is running there:
            # herdr tracks the tab's configured agent, not whether it still has
            # one. Trusting it is how a nudge reaches a bare shell.
            status = (
                "shell" if is_shell_pane(pane_text)
                else "asking" if is_asking_pane(pane_text)
                else "working" if (
                    status in NUDGEABLE
                    and any(_BUSY_RE.search(line) for line in pane_tail)
                )
                else update_stall(target, pane_text, status)
            )
            cues = lifecycle_cues(status, pane_text, target)
            rows.append({
                "source": "herdr",
                "id": pane_id,
                "label": p.get("agent") or pane_id,
                "session_label": p.get("label") or p.get("agent") or pane_id,
                "status": status,
                "cwd": p.get("cwd", "-"),
                "target": target,
                "workspace_id": p.get("workspace_id"),
                "context": pane_context_summary(pane_text),
                "quiet_for": stalled_seconds(target),
                **cues,
            })
        return rows
    except Exception as e:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        return _error_row("herdr", str(e)[:120])


def _tmux_pane_state(pane_target):
    text = capture_pane("tmux", pane_target)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "unknown", lifecycle_cues("unknown", text), pane_context_summary(text)
    if is_shell_pane(text):
        # Not an agent, so nothing can stall and nothing can be nudged. Skip the
        # stall clock entirely — a shell prompt never changes signature and would
        # otherwise be escalated to UNRESPONSIVE for doing exactly what it should.
        return "shell", lifecycle_cues("shell", text), pane_context_summary(text)
    if is_asking_pane(text):
        # Blocked on a human, not wedged: the pane is frozen by design while the
        # questionnaire is open, so the stall clock would escalate it to
        # UNRESPONSIVE for doing exactly what it should.
        return "asking", lifecycle_cues("asking", text), pane_context_summary(text)
    tail = lines[-_PANE_TAIL_LINES:]
    glyph_ready = any(
        ln.strip()[:1] in READY_GLYPHS or "│ > │" in ln for ln in tail if ln.strip()
    )
    status_ready = any(_IDLE_STATUS_RE.search(ln) for ln in tail)
    chrome = any(_AGENT_CHROME_RE.search(ln) for ln in tail)
    busy = any(_BUSY_RE.search(ln) for ln in tail)
    if glyph_ready and not chrome and not status_ready:
        # A prompt glyph with no agent chrome around it is a shell wearing the
        # same hat, not an idle agent. Fail toward "nothing to nudge here".
        return "shell", lifecycle_cues("shell", text), pane_context_summary(text)
    ready = (glyph_ready and chrome) or status_ready
    status = "idle" if (ready and not busy) else "working"
    status = update_stall(pane_target, text, status)
    return status, lifecycle_cues(status, text, pane_target), pane_context_summary(text)


def collect_tmux(claimed_pane_ids):
    try:
        proc = _run(["tmux", "list-sessions", "-F", "#{session_name}"])
        if proc.returncode != 0:
            return []  # no tmux server running is not an error worth surfacing
        rows = []
        for sess_name in (ln for ln in proc.stdout.splitlines() if ln.strip()):
            panes = _run([
                "tmux", "list-panes", "-t", sess_name,
                "-F", "#{pane_id}|#{pane_current_path}",
            ])
            if panes.returncode != 0:
                continue
            for line in panes.stdout.splitlines():
                if "|" not in line:
                    continue
                pane_id, cwd = line.split("|", 1)
                if pane_id in claimed_pane_ids:
                    continue  # already reported by collect_herdr
                status, cues, context = _tmux_pane_state(pane_id)
                rows.append({
                    "source": "tmux",
                    "id": pane_id,
                    "label": sess_name,
                    "status": status,
                    "cwd": cwd,
                    "target": pane_id,
                    "context": context,
                    "quiet_for": stalled_seconds(pane_id),
                    **cues,
                })
        return rows
    except FileNotFoundError:
        return _error_row("tmux", "tmux not installed")
    except Exception as e:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        return _error_row("tmux", str(e)[:120])


_WARP_SHELLS = frozenset({"bash", "fish", "ksh", "sh", "zsh"})


def _process_executable(command):
    """Return only a process basename, without retaining command arguments."""
    token = str(command or "").strip().split(None, 1)[0] if str(command or "").strip() else ""
    return Path(token).name.lstrip("-").lower()


def _warp_child_label(command):
    """Classify a Warp shell's direct child without displaying its arguments."""
    executable = _process_executable(command)
    lowered = str(command or "").lower()
    if executable == "claude":
        return "claude"
    if executable == "kimi":
        return "kimi"
    if executable == "codex" or (executable == "node" and re.search(r"\bcodex\b", lowered)):
        return "codex"
    if executable == "herdr":
        return "herdr"
    if executable in {"python", "python3"} and "shep.py" in lowered:
        return "shep"
    if executable and executable not in _WARP_SHELLS:
        return executable[:24]
    return "shell"


def _warp_elapsed_seconds(value):
    """Parse macOS ``ps etime`` into seconds for PID-reuse checks."""
    raw = str(value or "").strip()
    try:
        days_text, clock = raw.split("-", 1) if "-" in raw else ("0", raw)
        fields = [float(part) for part in clock.split(":")]
        if len(fields) == 3:
            hours, minutes, seconds = fields
        elif len(fields) == 2:
            hours, minutes, seconds = 0.0, fields[0], fields[1]
        elif len(fields) == 1:
            hours, minutes, seconds = 0.0, 0.0, fields[0]
        else:
            return None
        return float(days_text) * 86400 + hours * 3600 + minutes * 60 + seconds
    except (TypeError, ValueError):
        return None


def _warp_cwds(pids):
    """Read Warp shell working directories in one bounded lsof call."""
    if not pids:
        return {}
    proc = _run(
        ["lsof", "-a", "-p", ",".join(pids), "-d", "cwd", "-Fn"],
        timeout=WARP_PROCESS_SCAN_TIMEOUT,
    )
    if proc.returncode != 0:
        return {}
    cwds = {}
    current = None
    for line in proc.stdout.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            current = line[1:]
        elif line.startswith("n") and current and line[1:]:
            cwds[current] = line[1:]
    return cwds


def _warp_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "on", "yes"}


def _warp_observations(processes):
    """Apply optional identity/transcript tiers without widening control.

    The process scan remains the baseline and is deliberately independent of
    this helper. A missing sidecar, private DB, changed schema, lock, or parse
    failure therefore leaves the original Warp rows visible as ``unobserved``
    instead of making the fleet collector fail.

    Unique active-pane cwd matches can identify a pane without a sidecar. An
    optional ``SHEP_WARP_SCHEMA_FINGERPRINT`` pin still rejects schema drift when
    set; without a pin, required columns are verified and cwd correlation may
    still read a bounded transcript.
    """
    sidecar = Path(
        os.environ.get("SHEP_WARP_SIDECAR", str(WARP_SIDECAR_PATH))
    ).expanduser()
    db_path = Path(
        os.environ.get("SHEP_WARP_SQLITE_DB", str(WARP_SQLITE_DB_PATH))
    ).expanduser()
    if not sidecar.is_file() and not db_path.is_file():
        return {}
    try:
        from tools.warp_sqlite import WarpConfig, WarpProcess, observe_warp
    except ImportError:
        # bin/shep runs scripts/shep.py with sys.path[0] == scripts/, so the
        # repo-root `tools` package is invisible unless we add the parent.
        repo_root = str(Path(__file__).resolve().parents[1])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        try:
            from tools.warp_sqlite import WarpConfig, WarpProcess, observe_warp
        except ImportError:
            return {}

    expected = os.environ.get("SHEP_WARP_SCHEMA_FINGERPRINT")
    # Never learn the expected fingerprint from the database being verified.
    # That would silently accept a Warp schema change after restart. Cwd
    # correlation may still open the DB when the file exists; a pin, when
    # present, remains a hard gate.
    config = WarpConfig(
        enabled=db_path.is_file(),
        db_path=db_path if db_path.is_file() else None,
        sidecar_path=sidecar if sidecar.is_file() else None,
        expected_schema_fingerprint=expected,
        expected_user_version=0,
        max_rows=50,
        max_transcript_chars=4_000,
        # Shell history can be older than the 15m default while a fullscreen
        # agent is running in the same pane; keep a day of block evidence.
        max_age_s=86400,
        allow_cwd_correlation=True,
    )
    observations = observe_warp(
        [
            WarpProcess(
                pid=int(process["pid"]),
                cwd=(
                    process.get("cwd")
                    if process.get("cwd") not in {None, "", "-"}
                    else None
                ),
                tty=process.get("tty"),
                started_at_s=process.get("started_at_s"),
            )
            for process in processes
        ],
        config,
    )
    return {observation.pid: observation for observation in observations}


def _warp_pane_state(text, target=None):
    """Derive working/idle/asking/shell from Warp transcript text.

    Same cues as tmux/herdr. Warp ``blocks`` are usually shell command history,
    not a fullscreen agent UI, so when no agent chrome, busy, idle, or asking
    evidence is present we report ``shell`` rather than inventing WORKING from
    a PID or from bare command output.
    """
    text = text or ""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    if is_shell_pane(text):
        return "shell", lifecycle_cues("shell", text), pane_context_summary(text)
    if is_asking_pane(text):
        return "asking", lifecycle_cues("asking", text), pane_context_summary(text)
    tail = lines[-_PANE_TAIL_LINES:]
    glyph_ready = any(
        ln.strip()[:1] in READY_GLYPHS or "│ > │" in ln for ln in tail if ln.strip()
    )
    status_ready = any(_IDLE_STATUS_RE.search(ln) for ln in tail)
    chrome = any(_AGENT_CHROME_RE.search(ln) for ln in tail)
    busy = any(_BUSY_RE.search(ln) for ln in tail)
    if not chrome and not busy and not status_ready:
        return "shell", lifecycle_cues("shell", text), pane_context_summary(text)
    if glyph_ready and not chrome and not status_ready:
        return "shell", lifecycle_cues("shell", text), pane_context_summary(text)
    ready = (glyph_ready and chrome) or status_ready
    status = "idle" if (ready and not busy) else "working"
    if target is not None:
        status = update_stall(target, text, status)
    return status, lifecycle_cues(status, text, target), pane_context_summary(text)



def _warp_session_label(agent, cwd, tty, pid, custom_title=None):
    """Operator-facing Warp session name: title, else agent@repo/tty, else pid.

    ``session_label`` is what the PANEL column shows. Hardcoding ``warp-<pid>``
    made every native Warp shell look identical even when the agent and cwd
    already distinguish them. Prefer an explicit Warp tab title when one is
    known; otherwise use the child agent plus a scan-friendly place name.
    """
    title = str(custom_title or "").strip()
    if title:
        return title[:64]
    agent_name = str(agent or "warp-shell").strip() or "warp-shell"
    cwd_value = str(cwd or "").strip()
    home = Path.home().resolve()
    if cwd_value and cwd_value not in {"", "-"}:
        try:
            cwd_path = Path(cwd_value).expanduser().resolve()
        except OSError:
            cwd_path = Path(cwd_value)
        repo = repo_name(str(cwd_path))
        if repo not in {"", "-", home.name} and cwd_path != home:
            return f"{agent_name}@{repo}"
    tty_name = str(tty or "").strip()
    if tty_name and tty_name not in {"", "-", "??"}:
        return f"{agent_name}@{tty_name}"
    return f"warp-{pid}"


def collect_warp():
    """Show Warp-native shells with fail-closed read-only observation tiers.

    Warp's terminal-server is the stable ownership boundary currently visible
    on macOS. Direct shell children represent native Warp tabs; their direct
    child process gives a useful, argument-free label such as ``codex``. This
    starts as process inventory only. An explicit sidecar can corroborate a
    pane identity; otherwise a unique active-pane cwd match may. A private
    SQLite adapter can add a bounded transcript used for context and the same
    working/idle/asking/shell cues as tmux. Neither tier provides send,
    capture, attach, or close control.
    """
    proc = _run(
        ["ps", "-axo", "pid=,ppid=,tty=,stat=,etime=,command="],
        timeout=WARP_PROCESS_SCAN_TIMEOUT,
    )
    if proc.returncode != 0:
        return []
    processes = {}
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 5)
        if len(parts) != 6 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        pid, ppid, tty, stat, elapsed, command = parts
        processes[pid] = {
            "pid": pid,
            "ppid": ppid,
            "tty": tty,
            "stat": stat,
            "elapsed": elapsed,
            "command": command,
        }
    server_pids = {
        pid for pid, process in processes.items()
        if "warp.app/" in process["command"].lower()
        and "terminal-server" in process["command"].lower()
    }
    shells = [
        process for process in processes.values()
        if process["ppid"] in server_pids
        and _process_executable(process["command"]) in _WARP_SHELLS
    ]
    cwds = _warp_cwds([process["pid"] for process in shells])
    children = {}
    for process in processes.values():
        children.setdefault(process["ppid"], []).append(process)
    rows = []
    for shell in sorted(shells, key=lambda process: int(process["pid"])):
        child_labels = sorted({
            _warp_child_label(child["command"])
            for child in children.get(shell["pid"], [])
            if _process_executable(child["command"]) not in _WARP_SHELLS
        })
        label = next(
            (name for name in ("codex", "claude", "kimi", "herdr", "shep") if name in child_labels),
            "warp-shell",
        )
        child_text = ", ".join(child_labels) if child_labels else "no foreground command"
        cwd = cwds.get(shell["pid"], "-")
        rows.append({
            "source": "warp",
            "id": shell["pid"],
            "target": f"warp:{shell['pid']}",
            "label": label,
            "session_label": _warp_session_label(
                label, cwd, shell["tty"], shell["pid"]
            ),
            # The process tree is a real observation of a live Warp shell, but
            # it cannot tell us whether the foreground agent is working or
            # waiting. Keep that distinction explicit instead of reporting a
            # successfully discovered process as UNOBSERVED.
            "status": "live-ro",
            "cwd": cwd,
            "context": (
                f"Warp native shell · PID {shell['pid']} · TTY {shell['tty']} · "
                f"{child_text} · live process · activity unavailable · read-only"
            ),
            "pid": int(shell["pid"]),
            "parent_pid": int(shell["ppid"]),
            "tty": shell["tty"],
            "elapsed": shell["elapsed"],
            "started_at_s": (
                time.time() - elapsed_seconds
                if (elapsed_seconds := _warp_elapsed_seconds(shell["elapsed"])) is not None
                else None
            ),
            "read_only": True,
            "reap_ready": False,
            "reap_reason": None,
            "continuation": None,
        })
    observations = _warp_observations(
        [
            {
                "pid": row["pid"],
                "cwd": row["cwd"],
                "tty": row["tty"],
                "started_at_s": row.get("started_at_s"),
            }
            for row in rows
        ]
    )
    for row in rows:
        observation = observations.get(row["pid"])
        if observation is None:
            continue
        row["warp_observation_status"] = observation.status
        row["warp_session_uuid"] = observation.session_uuid
        row["warp_reason"] = observation.reason
        row["warp_correlation"] = getattr(observation, "correlation", None)
        custom_title = getattr(observation, "custom_title", None)
        if custom_title:
            row["session_label"] = _warp_session_label(
                row["label"], row["cwd"], row.get("tty"), row["pid"], custom_title
            )
        if observation.cwd:
            row["cwd"] = observation.cwd
            if not custom_title:
                row["session_label"] = _warp_session_label(
                    row["label"], row["cwd"], row.get("tty"), row["pid"]
                )
        # Process discovery is still valid when optional sidecar/SQLite
        # enrichment fails. Preserve LIVE RO and expose the failed enrichment
        # tier as metadata rather than regressing a known-live row to the
        # misleading UNOBSERVED badge. When transcript evidence exists, replace
        # LIVE RO with the same working/idle/asking/shell cues tmux uses.
        if observation.transcript:
            row["transcript"] = observation.transcript
            state = _warp_pane_state(observation.transcript, row["target"])
            if state is not None:
                status, cues, context = state
                row["status"] = status
                row["context"] = context
                row.update(cues)
            else:
                row["status"] = "transcript-ro"
                row["context"] = pane_context_summary(observation.transcript)
        elif observation.status == "identified":
            row["status"] = "identified"
            row["context"] = row["context"].replace(
                " · read-only", " · identified read-only"
            )
        elif observation.status != "unobserved":
            row["status"] = observation.status

    return rows


def _t3_cache_read():
    """Best-effort read of the cross-process bearer cache. Never raises."""
    try:
        data = json.loads(T3_AUTH_CACHE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _t3_cache_write(token, session_id, expires):
    """Atomically replace the cross-process bearer cache, mode 0600.

    Permissioned at creation (not chmod'd after) so the bearer is never
    briefly world-readable. Best-effort: a write failure here just means the
    next subprocess mints its own token instead of reusing this one.
    """
    try:
        T3_AUTH_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        staged = T3_AUTH_CACHE_FILE.with_name(f"{T3_AUTH_CACHE_FILE.name}.{os.getpid()}.tmp")
        payload = json.dumps({"token": token, "session_id": session_id, "expires": expires})
        fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
        os.replace(staged, T3_AUTH_CACHE_FILE)
    except OSError:
        pass


def _t3_revoke_session(session_id):
    """Best-effort revoke of a superseded T3 auth session. Never raises.

    T3 exposes no bulk "purge expired sessions" call (checked the vendored
    apps/server/src/{cli/auth.ts,persistence/AuthSessions.ts,auth/
    EnvironmentAuth.ts}: only issue/list/revoke-by-id, and revoke merely sets
    revoked_at -- it never deletes the row). Revoking the session THIS cache
    just replaced, the moment it is replaced rather than leaving it to idle
    out its own 5-minute TTL, is the one piece of that lifecycle a caller can
    do through a supported command instead of reaching into T3's own store.
    """
    # A corrupted or hand-edited cache file could hand back a session_id of
    # any JSON type (int, list, ...); subprocess.run rejects a non-str/bytes
    # argv element outright, so guard the type here rather than let a bad
    # cache turn a best-effort revoke into a crash.
    if not isinstance(session_id, str) or not session_id:
        return
    _run([T3_BIN, "auth", "session", "revoke", session_id])


def _t3_token():
    """Cached bearer for the local T3 server, or None if one cannot be minted.

    Cached at two layers: an in-process dict for a single run's hot redraw
    loop, and a locked file (T3_AUTH_CACHE_FILE) so shep_control_loop's
    several `shep.py` subprocesses in one pass reuse the same bearer and
    T3 auth session instead of each minting -- and orphaning -- its own.

    The value is never logged: only its presence is ever reported.
    """
    now = time.time()
    if _T3_TOKEN["value"] and now < _T3_TOKEN["expires"]:
        return _T3_TOKEN["value"]

    stale_session_id = None
    with _nudge_state_lock(T3_AUTH_CACHE_FILE):
        cached = _t3_cache_read()
        if isinstance(cached, dict):
            token = cached.get("token")
            expires = cached.get("expires")
            if (isinstance(token, str) and token
                    and isinstance(expires, (int, float)) and now < expires):
                _T3_TOKEN["value"], _T3_TOKEN["expires"] = token, float(expires)
                return token
            stale_session_id = cached.get("session_id")

        # --json (not --token-only) so the issued session id is captured too --
        # otherwise the session this cache is about to replace can never be
        # revoked, only left to expire on its own.
        proc = _run([T3_BIN, "auth", "session", "issue", "--ttl", "5m", "--json"])
        issued = None
        if proc.returncode == 0 and (proc.stdout or "").strip():
            try:
                issued = json.loads(proc.stdout)
            except ValueError:
                issued = None
        token = issued.get("token") if isinstance(issued, dict) else None
        session_id = issued.get("sessionId") if isinstance(issued, dict) else None
        if not isinstance(token, str) or not token:
            _T3_TOKEN["value"], _T3_TOKEN["expires"] = None, 0.0
            return None

        expires = now + T3_TOKEN_TTL_SECONDS
        _T3_TOKEN["value"], _T3_TOKEN["expires"] = token, expires
        _t3_cache_write(token, session_id, expires)

    if stale_session_id and stale_session_id != session_id:
        _t3_revoke_session(stale_session_id)
    return token


def _t3_request(token, path, payload=None):
    """(status, parsed-body) against the T3 environment API. Never raises."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{T3_BASE_URL}{path}", data=data, method="POST" if data else "GET"
    )
    req.add_header("Authorization", f"Bearer {token}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=T3_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                # Unknown paths fall through to the SPA's index.html.
                return resp.status, None
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001 - the status is the part that matters
            return exc.code, None
    except Exception as exc:  # noqa: BLE001 - server down is the normal case
        return 0, str(exc)[:120]


def _t3_iso(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _t3_thread_state(thread, now):
    """(status, quiet_for) for one T3 thread, or None to omit it entirely.

    Maps T3's session/turn state machine onto shep's vocabulary. Only a ready
    session with a completed turn becomes `idle`; anything still holding a turn
    is `working`, which is outside NUDGEABLE and so can never be auto-sent to.
    """
    session = thread.get("session")
    if not isinstance(session, dict):
        return None  # no runtime attached — nothing to supervise
    status = session.get("status")
    if status == "stopped":
        return None  # no live process; a stopped thread is not a session
    if session.get("lastError"):
        return "error", 0
    if status == "running" or session.get("activeTurnId"):
        return "working", 0
    if status != "ready":
        return "error", 0  # unrecognised state is never assumed nudgeable

    turn = thread.get("latestTurn")
    if not isinstance(turn, dict):
        return None
    if turn.get("state") != "completed":
        # `running` is live work; `interrupted` is a deliberate human stop.
        return "working", 0
    # A settled turn is not a settled session: background work outlives the turn
    # that started it, and this is the only field that says so.
    if thread.get("backgroundLiveness"):
        return "working", 0
    if thread.get("hasPendingApprovals") or thread.get("hasPendingUserInput"):
        # Waiting on a specific human answer. `asking` is outside NUDGEABLE, so
        # a generic continuation can never be typed over a real question.
        return "asking", 0

    stamps = [
        _t3_iso(thread.get("updatedAt")),
        _t3_iso(session.get("updatedAt")),
        _t3_iso(turn.get("completedAt")),
        _t3_iso(turn.get("startedAt")),
        _t3_iso(turn.get("requestedAt")),
    ]
    stamps = [s for s in stamps if s is not None]
    if not stamps:
        return "error", 0  # undateable thread is never treated as quiet
    # The MAX: if any field says the thread moved recently, that is enough.
    quiet_for = int((now - max(stamps)).total_seconds())
    if quiet_for < 0:
        return "working", 0  # clock skew — assume busy, never assume idle
    return ("stalled" if quiet_for >= STALL_AFTER_SECONDS else "idle"), quiet_for


def _t3_send_turn(row, target, text):
    """Start a user turn on an existing T3 thread. Returns (ok, detail).

    `thread.turn.start` is the same command the web and mobile clients send;
    the HTTP dispatch route accepts the full command union, so this needs no
    WebSocket lifecycle. A thread already holding a turn is rejected by the
    server, which is the last guard against interleaving with live work.
    """
    token = _t3_token()
    if token is None:
        return False, "t3 auth unavailable"
    command = {
        "type": "thread.turn.start",
        "commandId": str(uuid.uuid4()),
        "threadId": target,
        "message": {
            "messageId": str(uuid.uuid4()),
            "role": "user",
            "text": text,
            "attachments": [],
        },
        "runtimeMode": row.get("runtime_mode") or "full-access",
        "interactionMode": row.get("interaction_mode") or "default",
        "createdAt": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }
    status, body = _t3_request(token, "/api/orchestration/dispatch", command)
    if status == 200:
        return True, "sent"
    return False, f"t3 dispatch failed: status={status} {str(body or '')[:120]}"


def collect_t3(_claimed=None):
    """Live T3 Code threads as agent rows.

    Fail-closed like the other collectors: a missing binary or an unreachable
    server yields no rows at all, so T3 being down can never be mistaken for a
    fleet of stalled agents waiting to be nudged.
    """
    try:
        if not shutil.which(T3_BIN) and not Path(T3_BIN).exists():
            return []
        token = _t3_token()
        if token is None:
            return []
        status, body = _t3_request(token, "/api/orchestration/shell")
        if status != 200 or not isinstance(body, dict):
            return []
        threads = body.get("threads")
        if not isinstance(threads, list):
            return []
        projects = {
            p.get("id"): p.get("workspaceRoot")
            for p in body.get("projects", [])
            if isinstance(p, dict)
        }
        now = datetime.datetime.now(datetime.timezone.utc)
        rows = []
        for thread in threads:
            if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
                continue
            if thread.get("deletedAt") or thread.get("archivedAt"):
                continue
            state = _t3_thread_state(thread, now)
            if state is None:
                continue
            status_name, quiet_for = state
            title = str(thread.get("title") or thread["id"])
            rows.append({
                "source": "t3",
                "id": thread["id"],
                "label": title,
                "session_label": title,
                "status": status_name,
                "cwd": thread.get("worktreePath")
                or projects.get(thread.get("projectId"))
                or "-",
                "target": thread["id"],
                # The thread title is the only cheap grounding text T3 exposes
                # here; the nudge quality gate needs it to score a draft.
                "context": title,
                "quiet_for": quiet_for,
                # Carried so a nudge can mirror the thread's own settings rather
                # than silently changing how the session runs.
                "runtime_mode": thread.get("runtimeMode") or "full-access",
                "interaction_mode": thread.get("interactionMode") or "default",
                **lifecycle_cues(status_name, title, thread["id"]),
            })
        return rows
    except Exception as e:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        return _error_row("t3", str(e)[:120])


def collect_all():
    herdr_rows = collect_herdr()
    claimed = {r["id"] for r in herdr_rows if r.get("target")}
    rows = []
    rows.extend(herdr_rows)
    rows.extend(collect_tmux(claimed))
    rows.extend(collect_t3(claimed))
    rows.extend(collect_warp())
    # Banked here rather than in either collector, because a finished session is
    # finished whichever transport reported it, and one insertion point cannot
    # drift from the other. This is the only write into the pile: everything
    # downstream reads it.
    for row in rows:
        if row.get("reap_ready"):
            record_done(row, row.get("reap_reason"))
    set_tab_badge("agents", len(rows))
    return rows


# --- Operator snapshot ------------------------------------------------------

def _happy_daemon_sessions():
    """Return Happy's live sessions without pretending headless work is idle.

    Shep's terminal collectors cannot see a Happy daemon process that has no
    Herdr/tmux panel.  These rows are deliberately marked ``unobserved``: a
    daemon PID proves liveness, not whether the agent is working or waiting.
    """
    proc = _run(["happy", "daemon", "list"], timeout=10)
    if proc.returncode != 0 or "[" not in proc.stdout:
        return []
    try:
        payload = proc.stdout[proc.stdout.index("[") : proc.stdout.rindex("]") + 1]
        sessions = json.loads(payload)
    except (ValueError, json.JSONDecodeError):
        return []
    rows = []
    for session in sessions if isinstance(sessions, list) else []:
        sid = str(session.get("happySessionId") or "").strip()
        if not sid:
            continue
        pid = session.get("pid")
        tty = "?"
        elapsed = None
        flavor = None
        if pid:
            info = _run(["ps", "-o", "tty=,etime=", "-p", str(pid)], timeout=5)
            parts = info.stdout.strip().split()
            if parts:
                tty = parts[0]
            if len(parts) > 1:
                elapsed = parts[1]
            command = _run(["ps", "-o", "command=", "-p", str(pid)], timeout=5).stdout
            if "index.mjs codex" in command:
                flavor = "codex"
            elif "index.mjs claude" in command:
                flavor = "claude"
            elif (
                "index.mjs" in command
                and not any(f"index.mjs {mode}" in command for mode in ("agy", "acp", "gemini"))
            ):
                # Bare `happy` starts Claude and its argv has flags immediately
                # after index.mjs rather than the literal word `claude`.
                flavor = "claude"
        suffix = sid[-8:]
        rows.append({
            "source": "happy",
            "id": sid,
            "target": f"happy:{sid}",
            "label": f"happy-{suffix}",
            "cwd": "-",
            "status": "unobserved",
            "shep_status": "outside_herdr",
            "reap_ready": False,
            "reap_reason": None,
            "continuation": None,
            "in_herdr": False,
            "happiness": "happy",
            "happy_session_id": sid,
            "flavor": flavor,
            "started_by": session.get("startedBy"),
            "pid": pid,
            "tty": tty,
            "elapsed": elapsed,
            "context": "Happy daemon is live but has no Herdr/tmux pane",
        })
    return rows


def snapshot_payload(rows=None, include_happy=True):
    """Build the operator-facing source of truth for every visible panel.

    ``snapshot_payload`` is intentionally read-only.  Nudge generation and
    delivery are separate CLI flags so a status query can never send work.
    """
    load_nudge_state()
    base_rows = list(rows if rows is not None else collect_all())
    observed_happy_ids = set()
    for row in base_rows:
        label = session_name(row)
        if label.startswith("happy-") and label.rsplit("-", 1)[-1]:
            observed_happy_ids.add(label.rsplit("-", 1)[-1])
    for row in base_rows:
        label = session_name(row)
        is_happy = label.startswith("happy-")
        row["in_herdr"] = row.get("source") == "herdr"
        row["happiness"] = "happy" if is_happy else "not_happy"
        row["shep_status"] = row.get("status", "unknown")
    if include_happy:
        happy_rows = _happy_daemon_sessions()
        happy_slots = {}
        for row in base_rows:
            label = session_name(row)
            if label.startswith("happy-"):
                flavor = label.removeprefix("happy-").split("-", 1)[0]
                if flavor in {"claude", "codex", "kimi"} and not row.get("happy_session_id"):
                    happy_slots.setdefault(flavor, []).append(row)
        for row in happy_rows:
            sid = row["happy_session_id"]
            if sid[-8:] in observed_happy_ids:
                for panel in base_rows:
                    label = session_name(panel)
                    if label.startswith("happy-") and label.endswith(sid[-8:]):
                        panel["happy_session_id"] = sid
                        flavor = label.removeprefix("happy-").split("-", 1)[0]
                        if flavor in happy_slots and panel in happy_slots[flavor]:
                            happy_slots[flavor].remove(panel)
                        break
                continue
            # Direct Happy sessions with a terminal are often already visible
            # as a `happy-codex`/`happy-claude` Herdr panel. Correlate those
            # slots by flavor so the snapshot does not double-count them.
            if row.get("tty") != "??" and row.get("flavor") in happy_slots:
                slots = happy_slots[row["flavor"]]
                if slots:
                    slots.pop(0)["happy_session_id"] = sid
                    continue
            base_rows.append(row)

    panels = []
    for row in base_rows:
        key = row.get("target") or row.get("id")
        state = _nudge_state(key)
        proposal = state.get("proposed")
        proposal_status = proposal.get("status") if isinstance(proposal, dict) else None
        proposal_text = proposal.get("text") if isinstance(proposal, dict) else None
        proposal_category = proposal.get("category") if isinstance(proposal, dict) else None
        proposal_reason = proposal.get("reason") if isinstance(proposal, dict) else None
        # Older state files recorded every draft as queued before the gate ran.
        # Derive the effective display state from the current pane so a read-only
        # snapshot cannot claim that a generic/risky proposal is sendable.
        if proposal_status == "queued" and proposal_text:
            gate_context = (
                proposal.get("context") if isinstance(proposal, dict) else None
            ) or row.get("context")
            hold_reason = nudge_hold_reason(proposal_text, gate_context)
            if hold_reason:
                proposal_status = "held"
                proposal_reason = hold_reason
        nudge = {
            "status": proposal_status,
            "text": proposal_text,
            "category": proposal_category,
            "reason": proposal_reason,
            "attempt": state.get("attempt", 0),
            "last_sent": state.get("last_nudge"),
            "next_eligible_at": state.get("next_at", 0.0),
        }
        if row.get("read_only") or row.get("source") == "happy":
            nudge["status"] = "unobserved"
            nudge["text"] = None
            nudge["reason"] = (
                "read-only transport; no supported pane control or context API"
            )
        elif not nudge["text"]:
            if state.get("last_nudge"):
                nudge["status"] = "sent"
                nudge["text"] = state["last_nudge"]
                nudge["reason"] = "last proposal was delivered"
            else:
                nudge["status"] = "none"
                nudge["reason"] = "no proposal currently queued"
        if (
            nudge["status"] == "sent"
            and isinstance(state.get("last_sent"), dict)
            and state["last_sent"].get("status") == "sent"
        ):
            nudge["status"] = "sent_unresolved"
            nudge["reason"] = "delivery confirmed; no subsequent pane progress observed"
        if state.get("exhausted_reason") == "needs_human":
            # Last, so it outranks every other display state: once nudging has
            # given up on a pane, that is the one thing the operator needs to
            # read off the row. Silently withholding drafts looks identical to
            # a healthy quiet pane, which is how targets sat unnudged and
            # unreported at the same time.
            nudge["status"] = "needs_human"
            nudge["reason"] = (
                f"{human_handoff_reason(state)}; nudging cannot fix it"
            )
        panels.append({**row, "nudge": nudge})

    counts = {
        "panels": len(panels),
        "in_herdr": sum(p["in_herdr"] for p in panels),
        "outside_herdr": sum(not p["in_herdr"] for p in panels),
        "happy": sum(p["happiness"] == "happy" for p in panels),
        "not_happy": sum(p["happiness"] == "not_happy" for p in panels),
        "working": sum(p["status"] == "working" for p in panels),
        "idle": sum(p["status"] == "idle" for p in panels),
        "blocked": sum(p["status"] == "blocked" for p in panels),
        "unobserved": sum(p["status"] == "unobserved" for p in panels),
        "reap_ready": sum(bool(p.get("reap_ready")) for p in panels),
        "nudge_proposed": sum(p["nudge"]["status"] == "queued" for p in panels),
        "nudge_held": sum(p["nudge"]["status"] == "held" for p in panels),
        "nudge_sent": sum(p["nudge"]["status"] == "sent" for p in panels),
        "nudge_sent_unresolved": sum(
            p["nudge"]["status"] == "sent_unresolved" for p in panels
        ),
        "nudge_needs_human": sum(
            p["nudge"]["status"] == "needs_human" for p in panels
        ),
    }
    return {"schema": "shep-snapshot/v1", "generated_at": time.time(),
            "counts": counts, "panels": panels}


def render_snapshot(payload):
    """Compact human-readable panel list; JSON remains the lossless form."""
    lines = [
        "PANEL                         LOCATION       HAPPY       SHEP STATUS   REAP        NUDGE",
        "-" * 118,
    ]
    for panel in payload["panels"]:
        label = str(
            panel.get("session_label")
            or panel.get("label")
            or panel.get("id")
            or "?"
        )
        target = str(panel.get("target") or "?")
        panel_name = f"{label} [{target}]"[:29]
        location = "Herdr" if panel.get("in_herdr") else panel.get("source", "outside")
        happy = panel.get("happiness", "unknown")
        status = panel.get("shep_status", panel.get("status", "unknown"))
        reap = "READY" if panel.get("reap_ready") else "-"
        nudge = panel.get("nudge") or {}
        nudge_status = nudge.get("status") or "none"
        nudge_text = str(
            nudge.get("reason") if nudge_status == "held"
            else nudge.get("text") or nudge.get("reason") or ""
        )
        lines.append(
            f"{panel_name:<30} {location:<14} {happy:<11} {status:<12} "
            f"{reap:<10} {nudge_status}: {nudge_text[:58]}"
        )
    c = payload["counts"]
    lines.append("-" * 118)
    lines.append(
        "counts: " + ", ".join(f"{key}={value}" for key, value in c.items())
    )
    return "\n".join(lines)


# --- Context preview --------------------------------------------------------

# Shep's own words about why there is no pane text — never text from a pane.
# The renderer and the drafter both have to tell these apart from real output,
# and neither can do it by shape: "[INFO] building auth module" and
# "[12:04:31] step 3/9" are ordinary pane lines. Sniffing for a leading bracket
# meant a capture that happened to open with one was drawn as a single
# unwrapped line instead of wrapped scrollback, AND silently excluded that
# session from nudge drafting for as long as its output stayed bracketed.
# Membership in a closed set shep itself writes is the test.
CONTEXT_LOADING = "[loading...]"
CONTEXT_NO_TARGET = "[no preview available for this row]"
CONTEXT_READ_FAILED = "[error reading pane]"
CONTEXT_DEMO = "[demo session output]"
CONTEXT_PLACEHOLDERS = frozenset(
    {CONTEXT_LOADING, CONTEXT_NO_TARGET, CONTEXT_READ_FAILED, CONTEXT_DEMO}
)


def is_context_placeholder(preview):
    """True when `preview` is shep explaining itself, not pane output."""
    return preview in CONTEXT_PLACEHOLDERS


def context_preview_segments(preview):
    """What the context panel draws for one session's captured pane.

    A placeholder is shep's own one-line sentence and is drawn as written; real
    output is wrapped line by line. Kept out of the render loop so the decision
    is reachable by a test — inline, the branch that collapsed a whole capture
    onto one line could only be caught by eye.
    """
    if is_context_placeholder(preview):
        return [[(preview, curses.A_NORMAL)]]
    return clean_context_segments(preview) or [
        [("[no recent output — pane shows only UI chrome]", SOFT)]
    ]


def get_pane_context(row, lines=SESSION_VIEW_LINES):
    """Return the last few lines of real pane output for a session, so you can
    tell what it's actually doing/left off on — not just an idle/working label.

    Colour-preserved for BOTH transports: tmux via `capture-pane -e`, herdr via
    `herdr pane read --format ansi`."""
    if row.get("read_only"):
        return row.get("context") or CONTEXT_NO_TARGET
    target = row.get("target")
    if not target:
        return CONTEXT_NO_TARGET
    text = capture_pane(row["source"], target, lines=lines, ansi=True)
    if not text:
        return CONTEXT_READ_FAILED
    return text


def session_name(row):
    """The herdr tab label that tells one session apart from another.

    Distinct from `label`, which is the AGENT (claude/codex/kimi) and is very
    nearly constant across the fleet — measured live, 21 of 22 panes rendered
    the identical agent badge, so a column showing it carries no information
    about which session you are looking at. The tab label is what does.
    """
    return str(row.get("session_label") or row.get("label") or "")


def repo_name(cwd):
    """Return the scan-friendly repository/worktree name, never its full path."""
    value = str(cwd or "-").rstrip("/")
    if value in ("", "-"):
        return "-"
    return Path(value).name or value


# Chrome/status-bar noise emitted by terminal-agent UIs (Claude Code, etc.) —
# never real session content, so it must never end up "the last line" of a draft.
NOISE_PATTERNS = [
    re.compile(r"^context:\s*\d+%", re.IGNORECASE),
    re.compile(r"^\(?\d+%\s*\(", re.IGNORECASE),                  # "36% (366k/1M)"
    re.compile(r"^\d+k?/\d+[km]?\s*tokens?$", re.IGNORECASE),
    re.compile(r"^thinking:?\s*(low|medium|high)$", re.IGNORECASE),
    re.compile(r"^(?:gpt|claude|kimi|gemini|qwen)[\w.-]*\s+\w+\s+·\s+.*\b(?:Main|default)\b", re.IGNORECASE),
    re.compile(r"^(?:gpt|claude|kimi|gemini|qwen)[\w.-]*\s+\w+\s+·\s+(?:~|/)", re.IGNORECASE),
    re.compile(r"^esc to interrupt", re.IGNORECASE),
    re.compile(r"^press enter to", re.IGNORECASE),
    re.compile(r"^press space .*switch to local mode.*ctrl-c to exit", re.IGNORECASE),
    re.compile(r"^for options$", re.IGNORECASE),
    re.compile(r"^codex-gw\s*[▸>-]", re.IGNORECASE),
    re.compile(r"^eff:\s*--(?:\s*\|.*)?$", re.IGNORECASE),
    re.compile(
        r"^(?:opus|sonnet|haiku|fable|atlas|gpt|claude|kimi|gemini|qwen).*\bcontextq:",
        re.IGNORECASE,
    ),
    re.compile(r"^\?\s*for shortcuts", re.IGNORECASE),
    re.compile(r"^-{3,}$"),
    re.compile(r"^\s*\d+\s+lines?\s+(changed|added|removed)", re.IGNORECASE),
    re.compile(r"^(auto|plan|accept edits)\b.*\bthinking:", re.IGNORECASE),   # agent status bar
    re.compile(r"shift\+tab to cycle", re.IGNORECASE),              # CC mode line (e.g. "▶▶ auto mode on (shift+tab to cycle)")
    re.compile(r"←\s*\d+\s+agents?\b"),                    # CC background-agents indicator
    re.compile(r"\bneed authentication\b.*\brun /mcp\b", re.IGNORECASE),  # CC MCP re-auth banner
    re.compile(r"\(\d+(?:\.\d+)?[kKmM] context\)\s*\|"),   # CC statusline "Opus 5 (1M context) | med | ..."
    re.compile(r"\b\d+[hd]:\d+%"),                         # CC usage-window quotas "5h:4%", "7d:15%"
    re.compile(r"^[✻✶✳✽✢✦]\s*\S.*\bfor \d+s\b"),          # CC spinner "✻ Brewed for 11s"
    re.compile(r"^\s*[│|]\s*>?\s*$"),                                # empty prompt box row
    re.compile(r"^\s*[>❯›]\s*$"),
]

# Box-drawing / block characters used by terminal-agent UIs to frame the input
# box. A line made mostly of these is pure chrome, never session content.
_BOX_CHARS = set("─│┌┐└┘├┤┬┴┼╭╮╯╰━┃═║╔╗╚╝╠╣╦╩╬▀▄█▌▐░▒▓ \t")


def _is_box_frame(line):
    stripped = line.strip()
    if not stripped:
        return False
    box = sum(1 for ch in stripped if ch in _BOX_CHARS)
    # >=70% frame glyphs, or any run of 8+ horizontal rules => it's a border
    return box / len(stripped) >= 0.7 or re.search(r"[─━═]{8,}", stripped) is not None


def _is_noise(line):
    return _is_box_frame(line) or any(p.search(line) for p in NOISE_PATTERNS)


# --- ANSI (SGR) -> curses attrs ---------------------------------------------
#
# tmux capture-pane -e hands back the pane's real escape sequences. Real agent
# CLIs (Claude Code / Codex / Kimi) only use a small slice of the SGR spec —
# verified by capturing live panes: 0, 1, 2, 30-37, 39, 90-97. That's what we
# support; anything else is skipped rather than emulated. This is deliberately
# not a vt100 emulator.

_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")
# Any other CSI / OSC sequence (cursor moves, title sets) is display noise here.
_OTHER_ESC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[A-Za-z]|\x1b[()][0-9A-Za-z]")

# curses colour pairs 10..17 map to ANSI fg 0..7. Bright (90-97) reuses the same
# pair plus A_BOLD, which is exactly how a real terminal renders them.
_FG_PAIR_BASE = 10
_COLORS_READY = False
_UI_COLORS_READY = False
_ACTIVE_THEME = "classic"

THEME_NAMES = ("classic", "ocean", "contrast", "mono")
_THEME_PALETTES = {
    "classic": (
        (curses.COLOR_GREEN, -1),
        (curses.COLOR_YELLOW, -1),
        (curses.COLOR_RED, -1),
        (curses.COLOR_CYAN, -1),
        (curses.COLOR_MAGENTA, -1),
        (curses.COLOR_BLACK, curses.COLOR_GREEN),   # Codex badge
        (curses.COLOR_BLACK, curses.COLOR_YELLOW),  # Claude badge
        (curses.COLOR_BLACK, curses.COLOR_CYAN),    # Kimi badge
        (curses.COLOR_WHITE, curses.COLOR_BLUE),    # tmux badge
    ),
    "ocean": (
        (curses.COLOR_CYAN, -1),
        (curses.COLOR_WHITE, -1),
        (curses.COLOR_RED, -1),
        (curses.COLOR_CYAN, -1),
        (curses.COLOR_BLUE, -1),
        (curses.COLOR_WHITE, curses.COLOR_BLUE),
        (curses.COLOR_BLACK, curses.COLOR_CYAN),
        (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
        (curses.COLOR_BLACK, curses.COLOR_CYAN),
    ),
    "contrast": (
        (curses.COLOR_BLACK, curses.COLOR_GREEN),
        (curses.COLOR_BLACK, curses.COLOR_YELLOW),
        (curses.COLOR_WHITE, curses.COLOR_RED),
        (curses.COLOR_BLACK, curses.COLOR_CYAN),
        (curses.COLOR_WHITE, curses.COLOR_MAGENTA),
        (curses.COLOR_BLACK, curses.COLOR_GREEN),
        (curses.COLOR_BLACK, curses.COLOR_YELLOW),
        (curses.COLOR_BLACK, curses.COLOR_CYAN),
        (curses.COLOR_WHITE, curses.COLOR_BLUE),
    ),
}


def normalize_theme(name):
    normalized = str(name or "classic").strip().lower()
    return normalized if normalized in THEME_NAMES else "classic"


def next_theme(name):
    current = normalize_theme(name)
    return THEME_NAMES[(THEME_NAMES.index(current) + 1) % len(THEME_NAMES)]


def init_ui_colors(theme_name="classic"):
    """Allocate Shep's semantic colors, degrading safely to monochrome."""
    global _ACTIVE_THEME, _UI_COLORS_READY
    _ACTIVE_THEME = normalize_theme(theme_name)
    _UI_COLORS_READY = False
    if _ACTIVE_THEME == "mono":
        return
    try:
        curses.start_color()
        if not curses.has_colors():
            return
        curses.use_default_colors()
        for pair_id, (foreground, background) in enumerate(
            _THEME_PALETTES[_ACTIVE_THEME], start=1,
        ):
            curses.init_pair(pair_id, foreground, background)
        _UI_COLORS_READY = True
    except curses.error:
        _UI_COLORS_READY = False


def _ui_pair(pair_id):
    return curses.color_pair(pair_id) if _UI_COLORS_READY and pair_id else 0


def apply_theme(theme_name):
    """Apply both Shep chrome and captured-pane color policy."""
    global _COLORS_READY
    theme_name = normalize_theme(theme_name)
    init_ui_colors(theme_name)
    if theme_name == "mono":
        _COLORS_READY = False
    else:
        init_ansi_colors()
    return theme_name


def init_ansi_colors():
    """Allocate the fg colour pairs. Safe to call when the terminal has no
    colour support — we just leave _COLORS_READY False and render plain."""
    global _COLORS_READY
    try:
        curses.start_color()
        curses.use_default_colors()
        if not curses.has_colors():
            return
        for i in range(8):
            curses.init_pair(_FG_PAIR_BASE + i, i, -1)
        _COLORS_READY = True
    except curses.error:
        _COLORS_READY = False


def strip_ansi(text):
    return _OTHER_ESC_RE.sub("", _SGR_RE.sub("", text)).replace("\x1b", "")


def _apply_sgr(params, attr):
    """Fold one SGR parameter list into a running curses attr.

    Two readability rules are enforced here rather than at paint time, because
    this is the only place that knows a colour came from the *pane* and not from
    Shep's own chrome:

    * SGR 2 (faint) is dropped. Agent CLIs mark most of their prose faint, and
      A_DIM on a light terminal background is grey-on-white — the least legible
      thing on the screen.
    * Black, white, and every grey fold to the terminal's DEFAULT foreground
      (see `_readable`) instead of to COLOR_BLACK / COLOR_WHITE. A fixed black
      disappears on a dark background and a fixed white disappears on a light
      one; the default foreground is by definition legible on whatever the
      operator is actually running.
    """
    codes = [int(p) if p else 0 for p in params.split(";")]
    i = 0
    while i < len(codes):
        c = codes[i]
        if c == 0:
            attr = curses.A_NORMAL
        elif c == 1:
            attr |= curses.A_BOLD
        elif c in (22, 21):
            attr &= ~(curses.A_BOLD | curses.A_DIM)
        elif c == 39:
            attr &= ~_pair_mask()
        elif 30 <= c <= 37:
            attr = (attr & ~_pair_mask()) | _pair(_readable(c - 30))
        elif 90 <= c <= 97:
            attr = (attr & ~_pair_mask()) | _pair(_readable(c - 90)) | curses.A_BOLD
        elif c == 38 and i + 1 < len(codes):
            # Extended foreground. herdr panes emit 24-bit truecolor almost
            # exclusively, so folding it down to the nearest of the 8 base
            # colours is what makes herdr rows render in colour at all.
            if codes[i + 1] == 2 and i + 4 < len(codes):
                attr = (attr & ~_pair_mask()) | _pair(_rgb_to_basic8(*codes[i + 2:i + 5]))
                i += 4
            elif codes[i + 1] == 5 and i + 2 < len(codes):
                attr = (attr & ~_pair_mask()) | _pair(_xterm256_to_basic8(codes[i + 2]))
                i += 2
        # 4x background / everything else: ignored on purpose
        i += 1
    return attr


def _readable(idx):
    """Fold black (0) and white (7) onto the terminal's default foreground.

    Those two are the only ANSI colours that can be invisible: one on a dark
    background, one on a light one. `None` means "leave the foreground alone",
    which is always legible.
    """
    return None if idx in (0, 7) else idx


def _rgb_to_basic8(r, g, b):
    """Nearest ANSI 0-7 for a 24-bit colour, by hue/saturation rather than RGB
    distance — plain Euclidean maps mid-greys onto yellow and most blues onto
    cyan, which looks wrong on a real pane. Anything achromatic (near-black,
    grey, near-white) returns None: the terminal's own foreground."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if v < 0.25 or s < 0.20:
        return None  # black / grey / white => default foreground
    deg = h * 360
    for limit, idx in ((30, 1), (90, 3), (150, 2), (195, 6), (280, 4), (330, 5)):
        if deg < limit:
            return idx
    return 1  # wraps back to red


def _xterm256_to_basic8(n):
    if n < 16:
        return _readable(n % 8)
    if n >= 232:  # greyscale ramp — never pinned to black or white
        return None
    n -= 16
    r, g, b = n // 36, (n % 36) // 6, n % 6
    return _rgb_to_basic8(r * 51, g * 51, b * 51)


def _pair(idx):
    return curses.color_pair(_FG_PAIR_BASE + idx) if _COLORS_READY and idx is not None else 0


def _pair_mask():
    return curses.A_COLOR if _COLORS_READY else 0


def ansi_segments(line):
    """Split a colour-preserved line into [(text, curses_attr), ...].

    Malformed / unsupported escapes degrade to plain text for that segment
    rather than raising — a bad byte in one pane must not kill the TUI."""
    try:
        segs, attr, pos = [], curses.A_NORMAL, 0
        for m in _SGR_RE.finditer(line):
            chunk = line[pos:m.start()]
            if chunk:
                segs.append((_OTHER_ESC_RE.sub("", chunk), attr))
            attr = _apply_sgr(m.group(1), attr)
            pos = m.end()
        tail = line[pos:]
        if tail:
            segs.append((_OTHER_ESC_RE.sub("", tail), attr))
        return [(t, a) for t, a in segs if t]
    except Exception:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        return [(strip_ansi(line), curses.A_NORMAL)]


def _slice_segments(segs, start, end):
    out, pos = [], 0
    for text, attr in segs:
        s, e = max(start, pos), min(end, pos + len(text))
        if s < e:
            out.append((text[s - pos:e - pos], attr))
        pos += len(text)
    return out


def _trim_segments(segs):
    """Drop surrounding whitespace and a leading/trailing input-box frame edge
    ("│ some text │") while keeping every remaining char's colour."""
    plain = "".join(t for t, _ in segs)
    left = len(plain) - len(plain.lstrip())
    body = plain.strip()
    m = re.match(r"^[│|┃║]\s?", body)
    if m:
        left += m.end()
        body = body[m.end():]
    trimmed = body.rstrip("│|┃║ ")
    return _slice_segments(segs, left, left + len(trimmed))


def clean_context_lines(context_text):
    """Plain-text (ANSI-stripped) view of the pane, chrome removed.

    Used by the nudge drafter so what you see is what gets reasoned over —
    previously the drafter quoted the raw input-box border verbatim, producing
    `planned nudge: Saw: "╭──────..."`."""
    return [plain for plain, _segs in _iter_clean(context_text)]


def nudge_context_fingerprint(context_text):
    """Stable fingerprint of the complete cleaned pane capture used for a draft."""
    normalized = "\n".join(clean_context_lines(context_text or ""))
    return hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()


def nudge_revalidation_reason(row, expected_context_hash, current_context):
    """Return why a cached draft is stale, or ``None`` when it is sendable."""
    status = row.get("status")
    if status not in NUDGEABLE:
        return f"session is now {status or 'unknown'}"
    if row.get("reap_ready"):
        return "session is ready to reap"
    if expected_context_hash is None:
        return "draft context is unavailable"
    if nudge_context_fingerprint(current_context) != expected_context_hash:
        return "session context changed"
    return None


def pane_context_summary(context_text):
    """The latest meaningful pane line for the fleet table's activity column."""
    if is_asking_pane(context_text):
        # The last meaningful line of an open questionnaire is one of its
        # options; showing that hid the actual question from the operator.
        return f"needs answer: {pane_question_text(context_text)}"[:280]
    lines = clean_context_lines(context_text or "")
    return lines[-1][:280] if lines else "waiting at prompt"


def table_activity_text(row, nudge_text):
    """Show the nudge lifecycle alongside the current agent output in one cell."""
    context = row.get("context") or "waiting for pane context"
    return context if nudge_text == "-" else f"{nudge_text} · {context}"


def table_row_values(row, activity_text, display_status, source_visible=False):
    """Build one table row's cell values for every responsive layout.

    Wide layouts name the activity column "activity"; narrow/medium layouts name
    it "nudge". Both must be populated here — a layout key with no matching value
    renders blank, which is how the context column silently disappeared on any
    terminal under 110 columns.
    """
    return {
        "source": source_badge(row["source"]),
        "agent": agent_badge(row, source_visible=source_visible),
        "session": session_name(row) or "-",
        "status": display_status,
        "activity": activity_text,
        "nudge": activity_text,
        "repo": repo_name(row.get("cwd")),
    }


def clean_context_segments(context_text):
    """Same filtering as clean_context_lines, but returns each surviving line as
    a list of (text, curses_attr) segments so the panel can render the pane's
    real colors. Filter on plain text, display styled text."""
    return [segs for _plain, segs in _iter_clean(context_text)]


def _iter_clean(context_text):
    out = []
    for raw in context_text.splitlines():
        segs = _trim_segments(ansi_segments(raw.rstrip()))
        plain = "".join(t for t, _ in segs)
        # The input-box line is never real output. An EMPTY box renders its
        # placeholder suggestion ("› Explain this codebase"), which was being
        # surfaced as the pane's activity — a mission actively building in its
        # worktree read as if it were sitting on a welcome screen.
        if not plain or plain.strip()[:1] in READY_GLYPHS or _is_noise(plain):
            continue
        out.append((plain, segs))
    return out


_CLAUDE_GW = _resolve_agent_command("claude")

# Drafting lane — configurable so the CLI and model can be swapped without a
# code change. SHEP_NUDGE_CMD is a shell-style command the prompt is appended
# to; SHEP_NUDGE_MODEL, when set, is passed as `--model <id>` (both claude-gw
# and codex-gw accept that flag). Examples:
#   SHEP_NUDGE_MODEL=claude-haiku-4-5-20251001
#   SHEP_NUDGE_CMD="~/.local/bin/codex-gw exec --skip-git-repo-check"
# The safety gate below deliberately does NOT read these — it stays pinned to
# claude-gw Opus + codex-gw so no env var can weaken the auto-send check.
_NUDGE_CMD = [
    os.path.expanduser(tok)
    for tok in shlex.split(os.environ.get("SHEP_NUDGE_CMD", "") or f"{_CLAUDE_GW} -p")
]
_NUDGE_MODEL = os.environ.get("SHEP_NUDGE_MODEL", "").strip()
_NUDGE_CLI_UNAVAILABLE = False


def nudge_argv(prompt):
    """Full argv for one nudge-drafting call: configured command + optional model."""
    argv = list(_NUDGE_CMD)
    if _NUDGE_MODEL:
        argv += ["--model", _NUDGE_MODEL]
    return argv + [prompt]


def _nudge_cli_available():
    """Lazy check, cached — gives up permanently on first failure so a missing
    binary doesn't retry the (slow) subprocess spawn every refresh."""
    global _NUDGE_CLI_UNAVAILABLE
    if _NUDGE_CLI_UNAVAILABLE:
        return False
    if not _NUDGE_CMD or not (
        Path(_NUDGE_CMD[0]).exists() or shutil.which(_NUDGE_CMD[0])
    ):
        _NUDGE_CLI_UNAVAILABLE = True
        return False
    return True


def nudge_assessed_state(row, stalled_for=None):
    """Translate collector state into the one fact the drafter needs."""
    status = str(row.get("status") or "unknown")
    if status == "stalled":
        if stalled_for and stalled_for >= 60:
            minutes = int(stalled_for) // 60
            return f"stalled for {minutes} minute{'s' if minutes != 1 else ''}"
        return "stalled"
    if status == "done":
        return "complete"
    if status == "idle":
        return "waiting"
    return status


def load_nudge_engine(path=None):
    """Load the human-editable nudge policy, failing closed when unavailable."""
    try:
        text = (path or NUDGE_ENGINE_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def render_nudge_engine_prompt(
    row, recent_lines, fleet_rows=None, prior=None, stalled_for=None, engine_text=None,
):
    """Append a bounded fleet-state snapshot to the Markdown nudge policy."""
    engine_text = engine_text if engine_text is not None else load_nudge_engine()
    if not engine_text:
        return None
    target = row.get("target") or row.get("id")
    sessions = []
    for session in fleet_rows or [row]:
        sessions.append({
            "target": session.get("target") or session.get("id"),
            "label": session.get("session_label") or session.get("label"),
            "state": nudge_assessed_state(
                session,
                stalled_for if (session.get("target") or session.get("id")) == target else None,
            ),
            "reap_ready": bool(session.get("reap_ready")),
            "visible_work": str(session.get("context") or "")[-280:],
        })
    payload = {
        "target": target,
        "target_recent_work": list(recent_lines)[-NUDGE_EVIDENCE_LINES:],
        "actions_already_tried": list(prior or [])[-NUDGE_HISTORY_DEPTH:],
        "sessions": sessions,
    }
    return f"{engine_text}\n\n## Current fleet state\n\n```json\n{json.dumps(payload)}\n```"


# The gateway answers a full 12.7k-char fleet prompt in ~4s, but a burst of ten
# concurrent drafts -- which is what a sweep over a 40-pane fleet actually is --
# was measured at up to 8.9s. Fifteen left barely six seconds of headroom, and a
# timeout was indistinguishable from a dead gateway in the log, so nobody could
# tell how many of the ~170 daily "gateway_unavailable" entries were really our
# own clock running out. Thirty is still well inside the five-minute sweep.
#
# Re-measured 2026-09-10 on the default lane with a 7.6k prompt: 13.8s, 15.7s,
# then a third draft cut off at exactly 30.0s. The evidence window is wider now,
# so forty-five buys the tail without letting a handful of panes outrun the
# control loop's 240s budget for the whole sweep.
NUDGE_DRAFT_TIMEOUT_SECONDS = 45
# Concurrent drafts per sweep. Ten at once measured 8.9s on the gateway; six
# keeps a 40-pane fleet from turning into a burst the gateway rate-limits.
SWEEP_DRAFT_WORKERS = int(os.environ.get("SHEP_SWEEP_DRAFT_WORKERS") or "6")


def llm_draft_nudge(
    row, recent_lines, attempt=1, prior=None, stalled_for=None, fleet_rows=None,
    failures=None,
):
    """Ask a small model to propose the actual nudge to send — a concrete
    instruction/decision, not a question that just restates the pane
    content. Returns None on any failure/timeout so the caller falls back
    to the heuristic draft; keeps the curses loop from ever hanging.

    Routes through a gateway wrapper CLI (`claude-gw -p` by default, see
    SHEP_NUDGE_CMD/SHEP_NUDGE_MODEL) rather than a direct Anthropic SDK call:
    this machine's interactive shells set ANTHROPIC_BASE_URL to an
    internal AI-gateway proxy that has no raw /v1/messages route, and the
    matching ANTHROPIC_API_KEY is gateway-scoped, not valid against the real
    Anthropic API directly. claude-gw is the sanctioned, already-authenticated
    path — same rule as never calling model-provider REST APIs directly."""
    def _fail(reason):
        # Mirrors llm_draft_intent's `reasons` convention so both drafting lanes
        # report failure the same way. Every return path names itself: the old
        # code answered None four different ways and the caller logged one flat
        # "gateway_unavailable" for all of them, so a timeout, a 429, a bad exit
        # code and a crash were the same entry and none could be acted on.
        if failures is not None:
            failures.append(reason)
        return None

    if not recent_lines:
        return _fail("no_context")
    if not _nudge_cli_available():
        return _fail("cli_unavailable")
    prompt = render_nudge_engine_prompt(
        row,
        recent_lines,
        fleet_rows=fleet_rows,
        prior=prior,
        stalled_for=stalled_for,
    )
    if not prompt:
        return _fail("engine_unavailable")
    try:
        env = dict(os.environ)
        env["CLAUDE_GW_QUIET"] = "1"
        env["CLAUDE_GW_NO_HEALTH"] = "1"
        result = subprocess.run(
            nudge_argv(prompt),
            capture_output=True,
            text=True,
            timeout=NUDGE_DRAFT_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
        if result.returncode != 0:
            return _fail(f"draft_exit:{result.returncode}")
        # Undecorated for the same reason the verdict tokens are: the model
        # answers in markdown. Measured live, it returned "`Fix the 2 failing
        # tests in test_api.py, then rerun pytest.`" -- which passed every gate
        # as a safe_continuation and would have been TYPED at the agent with its
        # backticks. Stripping the verdict path alone was half the problem.
        text = _undecorated(" ".join(result.stdout.split()))
    except subprocess.TimeoutExpired:
        return _fail("draft_timeout")
    except Exception as exc:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        # Result handling stays inside the try on purpose. This runs on the
        # curses thread and the contract is that it never raises; attributing
        # the failure must not cost that guarantee.
        return _fail(f"draft_error:{type(exc).__name__}")
    if not text:
        return _fail("draft_empty")
    if len(text) > MAX_NUDGE_CHARS:
        return _fail("draft_too_long")
    return text


def _applescript_string(text):
    """Quote text for AppleScript, collapsed to one line.

    The reason is written by a model and lands inside a script osascript then
    executes, so an unescaped quote would close the string and leave the rest
    running as code. Collapse and truncate first, escape second: escaping first
    and cutting afterwards can slice a backslash pair in half and reopen the
    exact hole this closes.
    """
    clean = " ".join(str(text).split())[:180]
    return '"' + clean.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify_operator(subtitle, message):
    """Put one thing on screen: a pane that cannot move without the operator.

    Only handoffs get a banner. Sends run about sixty times a day and a banner
    each time would train the operator to swipe them away unread, which ends in
    the same silence as no banner at all.
    """
    if os.environ.get("SHEP_NO_NOTIFY"):
        return
    try:
        subprocess.run(
            [
                "osascript", "-e",
                f"display notification {_applescript_string(message)} "
                f'with title "shep" subtitle {_applescript_string(subtitle)}',
            ],
            check=False, timeout=10, capture_output=True,
        )
    except (subprocess.SubprocessError, OSError):
        # A banner that fails must never take down an unattended pass. Losing
        # the notification is bad; losing the sweep behind it is worse.
        pass


DIGEST_HOUR = int(os.environ.get("SHEP_DIGEST_HOUR", "9"))
DIGEST_STAMP_FILE = NUDGE_STATE_FILE.parent / "shep-digest-stamp.txt"


def digest_due(now=None, path=None):
    """True on the first pass of a new day at or after the digest hour.

    The hour exists because the sweep runs around the clock: keyed on the date
    alone the digest lands at whatever minute past midnight the first pass
    happens, which is a notification nobody is awake to read and which then
    blocks the one they would have.
    """
    now = now or datetime.datetime.now()
    if now.hour < DIGEST_HOUR:
        return False
    stamp = path or DIGEST_STAMP_FILE
    try:
        if stamp.read_text().strip() == now.date().isoformat():
            return False
    except OSError:
        pass  # no stamp yet, or unreadable — treat as never sent today
    return True


def digest_message(escalated):
    """Render the daily digest for the owner's DM, reasons included.

    The banner stays a name list because a macOS notification is one line; the
    DM carries the why too, or the owner has to open the TUI to learn what
    "still waiting on you" means — the exact friction the outage postmortem
    found nobody crosses.
    """
    count = len(escalated)
    lines = [
        f"🧭 SHEP DIGEST · {count} pane{'' if count == 1 else 's'} "
        "still waiting on you"
    ]
    for row, reason in escalated:
        lines.append(f"• {repo_name(row.get('cwd'))} — {reason}")
    return "\n".join(lines)


def send_daily_digest(escalated, now=None, path=None):
    """Re-raise every pane still waiting on the operator. -> the log line, or None.

    The per-pane banner fires once and once only, so a dismissed one is gone:
    the pane keeps appearing in a log nobody opens and waits forever. This is
    the standing counterpart — it reports the whole stranded set, including
    panes escalated days ago, so forgetting costs a day rather than the pane.
    """
    if not escalated:
        # Silence is the correct daily report for an unblocked deck. A "0
        # waiting" banner every morning is the fastest way to teach the
        # operator that shep's notifications are noise.
        return None
    now = now or datetime.datetime.now()
    stamp = path or DIGEST_STAMP_FILE
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(now.date().isoformat())
    except OSError:
        # Stamped before notifying, and a failed stamp still notifies. Better a
        # repeated digest than a silent one: repetition is annoying, silence is
        # the bug this exists to fix.
        pass
    # The same name the report uses. `label` is the agent ("claude"), identical
    # on every pane, so a digest keyed on it reads "claude, claude, claude" and
    # names nothing — it tells the operator six panes are stuck and gives them
    # no way to find one.
    labels = [repo_name(row.get("cwd")) for row, _ in escalated]
    count = len(labels)
    # The DM is the standing escalation channel: the banner is gone the moment
    # it is dismissed, and the log is where handoffs went to die for 22h.
    # Stamped before posting (same trade as the banner: better a repeated
    # digest than a silent one).
    post_escalation(digest_message(escalated))
    notify_operator(
        f"{count} pane{'' if count == 1 else 's'} still waiting on you",
        ", ".join(labels),
    )
    return f"-- daily digest: {count} still waiting on you ({', '.join(labels)}) --"


def human_handoff_reason(state):
    """Why shep stopped working a pane, in the words the operator has to read.

    Two ways in, and they must not borrow each other's sentence: the ladder
    gives up after trying, the drafter gives up before trying. Reporting
    "3 nudges did not move this on" for a pane shep never nudged is a lie in
    the one line the unattended loop writes down.
    """
    reason = (state or {}).get("needs_human_reason")
    return reason or f"{MAX_NUDGE_ATTEMPTS} nudges did not move this on"


def release_targets(patterns):
    """Put panes shep handed to a human back into the engine -> [target, ...].

    The ladder's only exit is `update_stall` seeing the pane move on its own.
    That is right for an agent that resumed working and wrong for the operator:
    they read the handoff and cleared the blocker by hand — supplied the key,
    clicked the button, answered the question — and the pane has nothing left to
    print, so the latch never lifts and shep never speaks to that pane again.
    Nine of twenty-one live panes were stranded that way with no way back short
    of deleting the state file, which would take the whole fleet's dedupe
    history with it.

    Patterns are fnmatch globs over target ids, so `--release '*'` reopens the
    fleet and a single id reopens one pane.
    """
    released = []
    for target in sorted(_NUDGE_STATE):
        state = _NUDGE_STATE[target]
        if not state.get("exhausted_reason"):
            continue
        if not any(fnmatch.fnmatch(target, pattern) for pattern in patterns):
            continue
        # Same fields the movement reset keeps, minus `assessed_fingerprint`.
        # That omission is the whole point: movement keeps it because the pane
        # has produced new bytes since, while a released pane has produced
        # nothing, so carrying it over would re-suppress as `no_new_evidence`
        # on the very next pass and the release would be a no-op.
        keep = {
            key: state.get(key)
            for key in ("prior_nudges", "last_nudge", "last_sent", "close_requested")
        }
        del _NUDGE_STATE[target]
        fresh = _nudge_state(target)
        fresh.update({key: value for key, value in keep.items() if value})
        record_outcome("progress", target=target, outcome="released")
        released.append(target)
    return released


# --- Infra-blocked panes: retry on recovery -----------------------------------
#
# A pane stranded on "Reconnect Twingate…" is not waiting on the operator's
# judgment — it is waiting on a network. Shep parked three such panes as
# NEEDS-HUMAN for the whole of the 2026-09-07 Forge outage, and without this
# section they would have stayed parked after the tunnel recovered too, until a
# human noticed and ran --release by hand. Infra that heals itself must unblock
# the panes it stranded, automatically, once — the ladder then re-applies its
# own limits if the pane is actually stuck for some other reason.
INFRA_BLOCKER_RE = re.compile(
    r"\b(?:reconnect|restore|restart|fix)\b[^\n]{0,40}\b(?:twingate|tunnel|vpn)\b"
    r"|\b(?:twingate|tunnel|vpn)\b[^\n]{0,60}\b(?:connectivity|reachable|access|outage|down|unavailable)\b"
    r"|\b(?:network|connectivity|internet)\b[^\n]{0,30}\b(?:down|unreachable|outage)\b"
    r"|\b(?:forge|gitlab)\b[^\n]{0,60}\b(?:unreachable|not reachable|access)\b",
    re.I,
)
INFRA_PROBE_HOST = os.environ.get(
    "SHEP_INFRA_PROBE_HOST", "forge.example.invalid"
).strip()
INFRA_PROBE_PORT = int(os.environ.get("SHEP_INFRA_PROBE_PORT", "443"))
# One probe per sweep, not one per pane: the sweep runs every ~180s and a dead
# tunnel fails the TCP connect slowly, so a per-pane probe would multiply a
# multi-second timeout by the size of the stranded set.
INFRA_PROBE_TTL = float(os.environ.get("SHEP_INFRA_PROBE_TTL", "150"))
_INFRA_PROBE_CACHE = {"at": 0.0, "ok": False}


def infra_blocker(reason):
    """True when a NEEDS-HUMAN reason names shared infrastructure, not a choice.

    Deliberately narrow: a bare "pushes are blocked" can be auth or a typo, and
    a false positive releases a pane shep correctly parked. Only reasons that
    name the network itself count.
    """
    return bool(INFRA_BLOCKER_RE.search(str(reason or "")))


def infra_probe_healthy(now=None):
    """Cheap TCP reachability check for the named infra. -> bool

    Cached for one sweep window. Unknown DNS and refused connects both read as
    down — the same evidence the outage produced — and no result is ever
    cached as healthy for longer than the TTL.
    """
    now = time.time() if now is None else now
    if now - _INFRA_PROBE_CACHE["at"] < INFRA_PROBE_TTL:
        return _INFRA_PROBE_CACHE["ok"]
    try:
        with socket.create_connection(
            (INFRA_PROBE_HOST, INFRA_PROBE_PORT), timeout=3.0,
        ):
            ok = True
    except OSError:
        ok = False
    _INFRA_PROBE_CACHE.update(at=now, ok=ok)
    return ok


def release_infra_blocked(key, reason):
    """Reopen one infra-stranded pane. -> True when the pane was released.

    Same field discipline as `release_targets`: keep the history a drafter can
    learn from, drop `assessed_fingerprint` — carrying it over would re-suppress
    as `no_new_evidence` on the next pass because the pane produced no new
    bytes while the network was down. The world changed; that is the new
    evidence. The attempt count resets too: those nudges failed on a dead
    tunnel, not on the pane.
    """
    state = _nudge_state(key)
    if state.get("exhausted_reason") != "needs_human":
        return False
    if not infra_blocker(reason or state.get("needs_human_reason")):
        return False
    keep = {
        pattern_key: state.get(pattern_key)
        for pattern_key in ("prior_nudges", "last_nudge", "last_sent", "close_requested")
    }
    del _NUDGE_STATE[key]
    fresh = _nudge_state(key)
    fresh.update({k: v for k, v in keep.items() if v})
    record_nudge_event(
        key, "released", detail="infrastructure recovered; pane re-entered the ladder",
    )
    record_outcome("progress", target=key, outcome="released")
    return True


# Leading decoration a model wraps its own verdict in. Stripped before matching
# rather than folded into each pattern, so the abstention and handoff matchers
# cannot drift apart again.
_VERDICT_DECORATION = "\"'`*_ \t\r\n"
# IGNORECASE and a hyphen alternative because the drafter is a language model
# answering in prose, not a parser emitting a token. The first version of this
# matched only the exact casing and separator the prompt used, and the prompt
# itself presents the verdict inside backticks -- so the single most likely
# reply the guidance produces, `NO_NUDGE: still_working`, fell straight through
# as an ordinary draft and would have been typed at a live agent. Five spellings
# were reachable: casing, backticks, quotes, bold, and NO-NUDGE.
_NO_NUDGE_RE = re.compile(r"^NO[-_ ]?NUDGE", re.I)
_NEEDS_HUMAN_VERDICT_RE = re.compile(r"^NEEDS[-_ ]?HUMAN", re.I)
# What may sit between the verdict token and its reason. Whitespace counts as a
# separator on its own: the prompt asks for "TOKEN: reason", but a model that
# answers "NO_NUDGE still working" has still clearly declined.
_VERDICT_SEPARATOR_RE = re.compile(r"^[*_`'\"\s]*[:\-—]?\s*")


def _undecorated(text):
    """Drop the quoting/emphasis a model wraps a verdict token in.

    Both ends: a backticked reply closes with the character it opened with, and
    the trailing half is operator-visible -- it lands in the reason column and
    in telemetry, so leaving it produces `still_working``.
    """
    return str(text or "").strip().strip(_VERDICT_DECORATION)


def _verdict_reason(pattern, text):
    """The reason behind a verdict token, or None if `text` is not that verdict.

    Two steps rather than one regex because underscore is both markdown emphasis
    and part of the token itself, so a single pattern fights itself: widening it
    to accept ``__NO_NUDGE__`` also made it accept ``NO_NUDGE_STILL``, which is
    an ordinary sentence. Matching the token first and then *requiring* what
    follows to be a separator keeps both straight.

    Deliberately one-directional, like the callers depend on: every spelling
    accepted here turns a would-be instruction into silence, never the reverse.
    Being too permissive sends nothing; being too strict types "NO_NUDGE" at a
    working agent.
    """
    stripped = _undecorated(text)
    match = pattern.match(stripped)
    if not match:
        return None
    rest = stripped[match.end():]
    # Consume emphasis before judging, because underscore is both markdown bold
    # and a token character. The tail of ``__NO_NUDGE__`` is "__: x" (decoration)
    # and the tail of ``NO_NUDGE_STILL`` is "_STILL is a var" (a longer word).
    # Testing the raw first character cannot separate them -- it either rejects
    # the bold form or accepts the sentence. Stripping the run first is exact:
    # what remains is a separator, whitespace, or nothing for a real verdict,
    # and a word character for "NO_NUDGES are needed".
    if rest.lstrip("*_`'\"")[:1].isalnum():
        return None
    reason = _VERDICT_SEPARATOR_RE.sub("", rest)
    # Clamped like every other operator-visible reason (compare record_done):
    # DOTALL means an unbounded reply would otherwise become an unbounded
    # "reason" written verbatim into telemetry and the shared state file.
    return " ".join(reason.split())[:160] or "unspecified"


def abstention_reason(text):
    """The reason a drafter declined, or None when this is not an abstention.

    The engine used to answer a bare ``NO_NUDGE`` and five separate call sites
    compared against that string exactly. Asking it to name which rule fired
    would have broken every one of them the same way: ``NO_NUDGE: still_working``
    is not equal to ``NO_NUDGE``, so it would have fallen through as an ordinary
    draft and been typed into a live pane as an instruction. One matcher, used
    everywhere, is the only version of this that is safe to change again later.

    The first version of that matcher was case-sensitive and accepted no
    decoration -- and the prompt it reads back presents the verdict inside
    backticks, so the single most likely reply the guidance produces fell
    straight through. Five spellings were reachable: casing, backticks, quotes,
    bold, and ``NO-NUDGE``.

    Returns a sentence for a bare abstention rather than "", so callers can use
    a falsy result to mean "this is a real draft" without a second check.
    """
    return _verdict_reason(_NO_NUDGE_RE, text)


def is_abstention(text):
    """Whether a drafter reply declines to nudge, with or without a reason."""
    return abstention_reason(text) is not None





def needs_human_request(text):
    """The reason a drafter says only the operator can unblock this, or None.

    A reply of its own rather than a flavour of ``NO_NUDGE``, because
    abstention is the drafter's ordinary resting state and cannot stand in for
    this: across the first week of telemetry one healthy pane abstained 138
    times while still producing 84 usable nudges, and 50 targets abstained
    three or more times. Counting abstentions would have escalated most of the
    deck. Only the reply that names the blocker separates a pane waiting on the
    operator from one the drafter simply had nothing to add to.
    """
    reason = _verdict_reason(_NEEDS_HUMAN_VERDICT_RE, text)
    if reason is None:
        return None
    # "unspecified" is what the shared helper returns for a bare verdict. The
    # caller still has to treat that as a handoff, so give it a sentence and let
    # a falsy reason keep meaning "not blocked".
    return (
        "blocked on something only you can do" if reason == "unspecified" else reason
    )


def operational_candidate_or_fallback(text, row, recent_lines):
    """Preserve deliberate abstention; fail closed when model drafting fails.

    A quoted-pane fallback is not a nudge: it repeats status/UI text, asks a
    question instead of driving work, and can accidentally inherit a safe verb
    such as ``continue`` from the quote. Returning ``None`` keeps ambiguous
    context out of the automatic send queue and leaves the target for review.
    """
    if is_abstention(text):
        return None
    if needs_human_request(text):
        # Never a candidate. "NEEDS_HUMAN: reconnect ClickUp, it is your
        # account" is prose about the operator, and every gate below it judges
        # instructions — it would have passed as an ordinary draft and been
        # typed into the pane it was written about.
        return None
    if text and re.match(r"^\s*SAFE_TO_CLOSE\b", text, re.IGNORECASE):
        # The agent's answer to our own close ask, read back off the pane and
        # re-typed at it. `_without_sent_echo` already enforces this rule on the
        # read side so the close detector cannot reap a pane on shep's own
        # typing, but nothing enforced it on the write side, so the draft still
        # went out: two live panes were each sent their own completion report
        # back, twice. The prompt forbids it and the model does it anyway --
        # same reason the read-side guard exists rather than trusting guidance.
        return None
    return text


def nudge_draft_skip_detail(explicit_abstention):
    """Explain an empty draft without exposing the implementation seam."""
    if explicit_abstention:
        return "no actionable next step in visible work"
    return "Markdown engine returned no candidate"


INTENT_ENGINE_LIMITATION = (
    "prediction uses session label/status/pane context, not full chat history"
)
_INTENT_EVALUATION_RE = re.compile(
    r"\b(?:good|great|nice|perfect|excellent|thanks?|well done|looks good)\b", re.IGNORECASE
)


def validate_intent_candidate(text):
    """Normalize a Claude-style predicted operator prompt, or abstain.

    This is a format/voice check, not a send authorization check. Potentially
    risky but plausible predictions remain visible for comparison and still go
    through the existing risk classifier and human send boundary.
    """
    text = " ".join((text or "").strip().strip('"\'').split())
    if not text or is_abstention(text):
        return None
    # Length is bounded by what the engine can actually emit (MAX_NUDGE_CHARS),
    # not by a tighter guess: the old 12-word/100-char clamp rejected ~87% of
    # real drafts, so pressing [i] silently produced nothing most of the time.
    if len(text.split()) < 2 or len(text) > MAX_NUDGE_CHARS:
        return None
    if "?" in text:
        return None
    if _INTENT_EVALUATION_RE.search(text):
        return None
    return text


def llm_draft_intent(row, recent_lines, reasons=None, fleet_rows=None):
    """Expose the Markdown engine through the legacy short-intent UI slot."""
    def _abstain(reason):
        # Returns None so every call site can `return _abstain(...)` directly.
        if reasons is not None:
            reasons.append(reason)

    if not recent_lines:
        return _abstain("no_context")
    if not _nudge_cli_available() or not load_nudge_engine():
        return _abstain("engine_unavailable")
    text = llm_draft_nudge(
        row,
        recent_lines,
        fleet_rows=fleet_rows,
    )
    if text is None:
        # The engine returns None for any call failure — timeout, non-zero exit,
        # exception. A genuine NO_NUDGE comes back as text and is rejected below,
        # so this branch is never the model declining to answer.
        return _abstain("engine_unavailable")
    return validate_intent_candidate(text) or _abstain("invalid_format")


def _assessment_winner(scores, candidates):
    available = {
        engine: int(scores.get(engine, 0))
        for engine in ("operational", "intent")
        if candidates.get(engine)
    }
    if not available:
        return "none"
    best = max(available.values())
    winners = [engine for engine, score in available.items() if score == best]
    return winners[0] if len(winners) == 1 else "tie"


def fallback_candidate_assessment(candidates):
    """Explainable deterministic judge used when model scoring fails."""
    scores = {"operational": 0, "intent": 0}
    operational = candidates.get("operational")
    intent = candidates.get("intent")
    if operational:
        category, _reason = classify_risk(operational)
        scores["operational"] = 72 if category == "safe_continuation" else 48
        if "?" in operational:
            scores["operational"] -= 12
    if intent:
        scores["intent"] = 68 if validate_intent_candidate(intent) else 0
        if classify_risk(intent)[0] == "safe_continuation":
            scores["intent"] += 6
    return {
        "scores": scores,
        "winner": _assessment_winner(scores, candidates),
        "rationale": (
            "Fallback favors a grounded, actionable candidate and valid short intent format."
        ),
        "source": "fallback",
    }


def parse_candidate_assessment(output, candidates):
    """Parse judge JSON into a stable display schema; return None if malformed."""
    try:
        match = re.search(r"\{.*\}", output or "", re.DOTALL)
        data = json.loads(match.group(0))
        raw_scores = data["scores"]
        scores = {
            engine: max(0, min(100, int(raw_scores[engine])))
            for engine in ("operational", "intent")
        }
        for engine in scores:
            if not candidates.get(engine):
                scores[engine] = 0
        rationale = " ".join(
            str(data.get("rationale", "Model comparison.")).split()
        )[:160]
        return {
            "scores": scores,
            "winner": _assessment_winner(scores, candidates),
            "rationale": rationale or "Model comparison.",
            "source": "model",
        }
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def judge_candidates(row, recent_lines, candidates):
    """Legacy compatibility wrapper; never invokes another semantic model."""
    return fallback_candidate_assessment(candidates)


def select_candidate(candidates, assessment, requested=None):
    """Return (engine, text) for an explicit choice or the judge recommendation."""
    engine = requested or (assessment or {}).get("winner")
    if engine not in ("operational", "intent") or not candidates.get(engine):
        return None, None
    if requested is None:
        if nudge_quality_reason(assessment, engine):
            return None, None
    return engine, candidates[engine]


_CODEX_GW = _resolve_agent_command("codex")


def _gw_verdict(argv, env=None, timeout=45):
    """Run a gateway CLI, return True only on an unambiguous 'SAFE' verdict.
    Any error, timeout, or ambiguous output fails closed (False) — a verifier
    that can't be reached is not consulted, it's a NO vote."""
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env,
            check=False,
        )
        out = (result.stdout or "").strip().upper()
        return out.startswith("SAFE")
    except Exception:  # noqa: BLE001 - best-effort probe; must never crash the TUI
        return False


def llm_verify_risk(text, category, reason, context_excerpt):
    """Two-model panel judging whether a `merge`/`push`-category drafted nudge
    is safe to auto-send, per the project owner's 2026-07-28 correction: these aren't a
    keyword-matching bug, they're a genuine case-by-case judgment call (e.g.
    pushing a branch while he's actively watching the session IS sometimes the
    intended action). `destructive`/`send_gated` are NOT run through this —
    they stay always-human-gated regardless of verdict, matching the project's
    standing rule to confirm before irreversible/outward-facing actions.

    Requires BOTH claude-gw (Opus) and codex-gw to independently answer SAFE.
    Either disagreeing, erroring, or timing out means "needs review" — fails
    closed, never open. Routes through the sanctioned gateway wrappers only,
    never a direct model-provider API call."""
    prompt = (
        f"A coding agent is about to be sent this instruction by an automated nudge tool:\n"
        f'---\n{text}\n---\n'
        f"It was flagged as category '{category}' ({reason}). Recent terminal context:\n"
        f"---\n{context_excerpt[-1000:]}\n---\n"
        "Judge ONLY whether sending this exact instruction right now is safe to do "
        "WITHOUT a human reviewing it first. Consider: is this destructive, "
        "irreversible, or does it touch shared/production state in a way that could "
        "surprise someone? A push/merge/deploy that is clearly the expected next step "
        "in ordinary development flow can be SAFE. Reply with ONLY one word on the "
        "first line: SAFE or REVIEW. Optionally add one short reason on a second line."
    )
    # Both verifiers are pinned explicitly rather than inherited: this gate must
    # judge identically on every machine, and a stray CLAUDE_GW_MODEL /
    # CODEX_GW_* in the operator's shell must not be able to change what
    # "SAFE" means. Low/medium effort is deliberate — this is a one-word
    # SAFE-or-REVIEW call on a short excerpt, not deep reasoning, and the gate
    # fails closed on timeout, so a slow verifier is itself a failure mode.
    env = dict(os.environ)
    env["CLAUDE_GW_QUIET"] = "1"
    env["CLAUDE_GW_NO_HEALTH"] = "1"
    env["CLAUDE_GW_MODEL"] = "claude-opus-5"
    claude_verdict = _gw_verdict(
        [_CLAUDE_GW, "-p", "--effort", "low", prompt], env=env
    )

    codex_out = "/tmp/shep_risk_verify.md"
    codex_env = dict(os.environ)
    codex_env["CODEX_GW_MODEL"] = "gpt-5.6-terra"
    codex_env["CODEX_GW_REASONING"] = "medium"
    codex_verdict = _gw_verdict(
        [_CODEX_GW, "exec", "--dangerously-bypass-approvals-and-sandbox",
         "--skip-git-repo-check", "-o", codex_out, prompt],
        env=codex_env,
    )
    if not codex_verdict:
        # codex-gw writes its answer to -o rather than stdout; check the file too.
        try:
            codex_verdict = Path(codex_out).read_text().strip().upper().startswith("SAFE")
        except Exception:  # noqa: BLE001 - best-effort probe; must never crash the TUI
            codex_verdict = False

    return claude_verdict and codex_verdict


# --- Nudge transports ----------------------------------------------------

# --- ClickUp telemetry -------------------------------------------------------
#
# Every autonomous action leaves a readable trace, so the fleet can be followed
# without opening a pane. Inert until SHEP_TELEMETRY_CHANNEL names a channel —
# an unset channel must never block a nudge or a reap.
#
# The trace lives in the LOGS tab, NOT in a DM. Defaulting this to the operator's
# ClickUp self-DM turned every autonomous nudge into a message they had to read
# and dismiss, which is noise, not observability. A DM is now strictly opt-in:
# export SHEP_TELEMETRY_CHANNEL=<channel id> to turn the mirror back on
# (the operator's own self-DM is 8chy2nm-1327291).
CLICKUP_TELEMETRY_CHANNEL = os.environ.get("SHEP_TELEMETRY_CHANNEL", "").strip()
CLICKUP_WORKSPACE_ID = os.environ.get("CLICKUP_WORKSPACE_ID", "9011399348").strip()
_CLICKUP_TOKEN_CACHE = None

# --- ClickUp escalations -------------------------------------------------------
#
# The telemetry trace is chatty and stays opt-in; escalations are the opposite
# shape — rare, standing, and the one thing shep must never fail to say out
# loud. The 2026-09-07 Forge-outage postmortem found NEEDS-HUMAN handoffs
# living in an osascript banner and a log nobody opens: ~268 report lines
# across a 22h tunnel outage and zero owner-visible pings, while three sessions
# sat parked on "Reconnect Twingate". So this channel is ON by default and
# points at the operator's self-DM. Rare by construction: one post per new
# handoff (one-shot, exactly like the banner) plus the daily digest. Set
# SHEP_ESCALATION_CHANNEL="" to silence it.
CLICKUP_ESCALATION_CHANNEL = os.environ.get(
    "SHEP_ESCALATION_CHANNEL", "8chy2nm-1327291"
).strip()


def _clickup_token():
    """Token from the environment, else the resolved credential env file.

    Read into memory only — never logged, never echoed, never persisted.
    """
    global _CLICKUP_TOKEN_CACHE
    if _CLICKUP_TOKEN_CACHE is not None:
        return _CLICKUP_TOKEN_CACHE
    token = os.environ.get("CLICKUP_API_TOKEN", "")
    if not token:
        try:
            from dotenv import dotenv_values

            eng = os.environ.get("SEARCHATLAS_ENG_HOME") or str(
                Path.home() / "Sync" / "searchatlas-eng"
            )
            for candidate in (
                os.environ.get("FORGE_SYNC_ENV_FILE"),
                f"{eng}/mb-mgmt/.env",
                f"{eng}/mission-control/.env",
                f"{eng}/.env",
            ):
                if candidate and Path(candidate).is_file():
                    token = dotenv_values(candidate).get("CLICKUP_API_TOKEN", "") or ""
                    if token:
                        break
        except Exception:  # noqa: BLE001 - telemetry must never break the fleet loop
            token = ""
    _CLICKUP_TOKEN_CACHE = token
    return token


def session_headline(row):
    """One line naming WHICH session this is, in the operator's terms."""
    repo = repo_name(row.get("cwd")) or "?"
    label = row.get("label") or "session"
    target = row.get("target") or row.get("id") or "?"
    return f"{label} · {repo} · {target}"


def telemetry_message(action, row, detail="", activity="", attempt=None, category=None):
    """Render one telemetry post.

    Deliberately carries what the pane itself was doing: a bare "nudged session
    w34:pH" is unreadable a day later, and the whole point of the trace is to
    follow the fleet without opening it.
    """
    head = f"🧞 {action.upper()} · {session_headline(row)}"
    lines = [head]
    if activity:
        lines.append(f"was: {activity}")
    if detail:
        tag = ""
        if attempt is not None:
            tag = f" (attempt {attempt}/{MAX_NUDGE_ATTEMPTS}"
            tag += f", {category})" if category else ")"
        lines.append(f"{action.lower()}{tag}: {detail}")
    return "\n".join(lines)


def _clickup_chat_post(channel, content):
    """One message to one ClickUp chat channel. -> (posted, reason).

    The single network path for everything shep says to ClickUp: telemetry and
    escalations differ in volume and audience, not in transport.
    """
    token = _clickup_token()
    if not token:
        return False, "CLICKUP_API_TOKEN unavailable"
    body = json.dumps({"content": content}).encode()
    url = (
        f"https://api.clickup.com/api/v3/workspaces/{CLICKUP_WORKSPACE_ID}"
        f"/chat/channels/{channel}/messages"
    )
    request = urllib.request.Request(
        url, data=body,
        headers={"Authorization": token, "Content-Type": "application/json"},
    )
    # RETRY-LOOP-SAFETY: exactly one retry, only on a 429, only for as long as
    # one short sleep — the escalation path is the one message that must land
    # (the outage postmortem's whole point), and ClickUp rate-limits per token
    # that half the workstation shares. Everything else fails soft on attempt
    # one; nothing here loops, and the pass budget dwarfs the sleep.
    for attempt in (0, 1):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return 200 <= response.status < 300, str(response.status)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(5)
                continue
            return False, f"HTTP{exc.code}"
        except Exception as exc:  # noqa: BLE001 - a failed post must never stop the fleet
            return False, type(exc).__name__
    return False, "HTTP429"


def post_telemetry(action, row, detail="", activity="", attempt=None, category=None):
    """Best-effort ClickUp post. -> (posted, reason)."""
    if not CLICKUP_TELEMETRY_CHANNEL:
        return False, "no telemetry channel configured"
    return _clickup_chat_post(
        CLICKUP_TELEMETRY_CHANNEL,
        telemetry_message(
            action, row, detail, activity, attempt, category
        ),
    )


def escalation_message(row, reason):
    """Render one NEEDS-HUMAN handoff for the owner's DM.

    Carries the reason verbatim: the whole defect this fixes was an escalation
    that arrived without the sentence the operator needs to act on.
    """
    lines = [f"🚨 NEEDS-HUMAN · {session_headline(row)}"]
    if reason:
        lines.append(f"why: {reason}")
    lines.append("shep has stopped nudging this pane; it is waiting on you.")
    return "\n".join(lines)


def post_escalation(message):
    """Rare, owner-visible escalation to ClickUp. -> (posted, reason).

    Best-effort exactly like telemetry: a dead network, a bad token, or an
    unconfigured channel must never stop the sweep behind it.
    """
    if not CLICKUP_ESCALATION_CHANNEL:
        return False, "no escalation channel configured"
    return _clickup_chat_post(CLICKUP_ESCALATION_CHANNEL, message)


def _action_metadata(row):
    return {
        "session": row.get("label") or row.get("id"),
        "workspace": row.get("workspace_id") or row.get("cwd"),
        "repository": row.get("repository") or row.get("cwd"),
        "pane": row.get("pane_id") or row.get("target"),
        "source": row.get("source"),
    }


def send_nudge(row, text, mode="manual", audit=True, engine=None, path="single"):
    """The ONLY place a nudge actually reaches a pane — and so the only place
    NUDGES_SENT moves and the only place a `sent` outcome is recorded. Drafting
    a nudge is not sending one.

    Recording that outcome at the CALL SITES instead left the automatic
    continuations out of the outcome log entirely: they reach the transport
    straight through, past every interactive approval branch, so the scorecard
    saw roughly a third of the nudges actually delivered and could attribute no
    progress, close, or reap to the rest. Recording here means every route
    counts once, including routes written later.

    `engine` and `path` stay caller-supplied because only the caller knows which
    drafter won and which route it took. An automatic continuation is a fixed
    phrase from no drafter at all, so it records no engine rather than
    inventing one.
    """
    ok, detail = _deliver_nudge(row, text, mode=mode, audit=audit)
    record_outcome(
        "sent", target=row.get("target") or row.get("id"), engine=engine,
        ok=ok, path=path, risk_category=classify_risk(text)[0],
    )
    return ok, detail


def _deliver_nudge(row, text, mode="manual", audit=True):
    """Transport half of `send_nudge`. Never call this directly — going around
    `send_nudge` is exactly how a delivery goes unrecorded."""
    global NUDGES_SENT
    source = row["source"]
    target = row.get("target")
    if row.get("read_only"):
        detail = f"{source or 'this'} sessions are read-only in this tool"
        record_nudge_event(target, "failed", text, detail)
        return False, detail
    if audit and target:
        try:
            record_action(
                "nudge", "intent", mode=mode, target=target,
                metadata=_action_metadata(row), policy=classify_risk(text)[0],
                context=row.get("context_hash") or row.get("pane_signature") or row.get("context") or "",
                reason="operator-approved nudge" if mode == "manual" else "automatic continuation",
                text=text,
            )
        except ActionLogError as exc:
            record_nudge_event(target, "failed", text, "audit receipt unavailable")
            return False, f"audit receipt unavailable: {exc}"
    if source == "herdr" and target:
        proc = _run([sys.executable, str(HERDR_CTL), "session", "send", target, text])
        ok, detail = proc.returncode == 0, (proc.stdout or proc.stderr).strip()
    elif source == "tmux" and target:
        proc = _run(["tmux", "send-keys", "-t", target, text, "Enter"])
        ok, detail = proc.returncode == 0, (proc.stderr or "sent").strip()
    elif source == "t3" and target:
        ok, detail = _t3_send_turn(row, target, text)
    else:
        detail = f"{source} sessions are read-only in this tool — use its own CLI to act on it"
        record_nudge_event(target, "failed", text, detail)
        return False, detail
    if source in {"herdr", "tmux"} and proc.returncode == 124:
        # A timeout cannot distinguish "never reached the pane" from "the
        # input arrived but the CLI never acknowledged it". Retrying would
        # risk typing the same instruction twice, so require explicit human
        # reconciliation instead of treating this as an ordinary failure.
        state = _nudge_state(target)
        state["exhausted_reason"] = "delivery_unknown"
        state["delivery_unknown_at"] = time.time()
        detail = "delivery unknown: transport timed out; reconcile before retry"
        record_nudge_event(target, "delivery unknown", text, detail)
        return False, detail
    if ok:
        NUDGES_SENT += 1
        # Record into history, not just last_nudge: a manually-sent nudge has to
        # steer the next drafted one away from repeating it too.
        state = _nudge_state(target)
        remember_nudge(state, text)
        if is_close_request(text):
            # Recorded on send, never on draft: most drafts never reach a pane,
            # so flagging at draft time would swallow the first real ask.
            state["close_requested"] = True
        proposed = state.get("proposed")
        if not isinstance(proposed, dict) or proposed.get("text") != text:
            proposed = {}
            state["proposed"] = proposed
        proposed.update({
            "text": text,
            "status": "sent",
            "context": row.get("context") or "",
            "sent_at": time.time(),
        })
        state["last_sent"] = dict(proposed)
        record_nudge_event(target, "sent", text, detail)
    else:
        record_nudge_event(target, "failed", text, detail)
    if audit and target:
        try:
            record_action(
                "nudge", "sent" if ok else "failed", mode=mode, target=target,
                metadata=_action_metadata(row), policy=classify_risk(text)[0],
                context=row.get("context_hash") or row.get("pane_signature") or row.get("context") or "",
                reason="transport completed" if ok else "transport failed",
                text=text, result=detail, error="" if ok else detail,
            )
        except ActionLogError:
            # The intent receipt protected the mutation. A missing terminal
            # receipt is surfaced to the caller without pretending transport failed.
            detail = f"{detail}; terminal audit receipt unavailable"
    # Here rather than at the call sites, for the same reason the outcome is
    # recorded here: this is the only place a nudge reaches a pane, so every
    # route -- queue approval, typed nudge, sweep, automatic continuation --
    # tells the other process what it just did, including routes written later.
    persist_nudge_target(target)
    return ok, detail


def nudge_result_message(ok, text, detail=""):
    """Describe the user's action, not the transport's terse acknowledgement."""
    if ok:
        return f"sent: {text}"
    return f"failed: {detail or 'transport returned no detail'}"


def nudge_color_pair_id(text):
    """Map explicit nudge lifecycle text to a semantic terminal color."""
    state = str(text or "").split(":", 1)[0].strip().upper()
    if state in {"SENT", "MISSION SPAWNED"}:
        return 1  # green: completed
    if state in {"READY", "DRAFTING", "VERIFYING", "NEW MISSION"}:
        return 4  # cyan: informational/actionable
    if state in {"HELD", "FAILED"}:
        return 3  # red: needs attention
    if state == "REAP READY":
        return 5  # magenta: explicit lifecycle action
    return 0  # neutral/no lifecycle state


def nudge_event_detail(row):
    """Persistent, full-width detail for the selected row's latest nudge.

    Held and handed-off panes belong here as much as sent ones. The fleet
    column truncates, and it is precisely these two that carry the long text --
    a hold carries the reason it was withheld, a handoff carries what only the
    operator can do -- so the row the operator selects to find out what is being
    asked of them was the row that answered `None`. `sent`/`failed` were the
    only statuses that could cross a process boundary before events were
    persisted, which is the only reason the set was ever this narrow.
    """
    key = row.get("target") or row.get("id")
    event = _NUDGE_EVENTS.get(key)
    if not event or event.get("status") not in {
        "sent", "failed", "held", "needs human",
    }:
        return None
    text = event.get("text") or event.get("detail") or "no detail"
    timestamp = event.get("at")
    when = time.strftime("%H:%M", time.localtime(timestamp)) if timestamp else "--:--"
    return f"last nudge · {event['status'].upper()} {when}: {text}"


# One queue for everything shep needs a person for. Three different waits --
# a draft the risk gate will not send unattended, a pane only the operator can
# unblock, and a session that says it is finished -- were each discoverable only
# by scanning the fleet table for them, which is the scan an operator opens shep
# to avoid. The fleet table still carries all three; this is the shortlist.
PENDING_VERBS = {"approve": "APPROVE", "visit": "GO", "reap": "CLOSE"}
# Decisions first, by what answering costs: APPROVE is a yes/no settled from
# this screen, GO sends the operator somewhere else, CLOSE cannot be taken back.
PENDING_ORDER = ("approve", "visit", "reap")
PENDING_PANEL_ROWS = 5
PENDING_PANEL_ROWS_FOCUSED = 8


def pending_panel_visible_rows(focused=False):
    """Visible queue rows: compact during supervision, expanded during review."""
    return PENDING_PANEL_ROWS_FOCUSED if focused else PENDING_PANEL_ROWS


def pending_actions(rows):
    """Everything waiting on a person, decisions first. -> [item, ...]

    Within a kind the fleet order is preserved, so the queue does not reshuffle
    under the cursor between ticks -- a list that reorders itself every five
    seconds is one the operator cannot safely press Enter on.
    """
    found = {kind: [] for kind in PENDING_ORDER}
    for index, row in enumerate(rows):
        key = row.get("target") or row.get("id")
        state = _NUDGE_STATE.get(key) or {}
        event = _NUDGE_EVENTS.get(key) or {}
        # Checked in cost order, and each row claims exactly one slot: a pane
        # that is both reap-ready and holding a draft is finished, and asking
        # the operator to rule on a nudge for it would be asking twice.
        if row.get("reap_ready"):
            kind, summary = "reap", row.get("reap_reason") or "declared itself done"
        elif event.get("status") == "held":
            kind = "approve"
            summary = event.get("text") or event.get("detail") or "draft held"
        elif state.get("exhausted_reason") == "needs_human":
            kind, summary = "visit", human_handoff_reason(state)
        else:
            continue
        found[kind].append({
            "kind": kind,
            "verb": PENDING_VERBS[kind],
            "target": key,
            "row": row,
            "index": index,
            "summary": " ".join(str(summary).split()),
            "repo": repo_name(row.get("cwd")),
        })
    # Finished sessions the live rows no longer report. `reap_ready` is derived
    # from pane text every collection, so a session that declared SAFE_TO_CLOSE
    # left this queue as soon as the line scrolled off or the pane went away --
    # taking the completed work with it silently. These come from the durable
    # pile instead, so the finished list is the whole finished list.
    #
    # Liveness is read from the whole fleet, not from the reap bucket. Deriving
    # it from `found["reap"]` meant "not currently reap-ready" rather than "pane
    # is gone", so a session that declared itself done and then went back to
    # work got a second, phantom entry asserting its pane had exited -- while it
    # was actively running, banked for the full TTL and shared to every other
    # shep process. A row in `rows` means the pane exists, whatever it is doing.
    live = {row.get("target") or row.get("id") for row in rows}
    queued = {item["target"] for item in found["reap"]}
    for record in done_pile():
        target = record["target"]
        if target in queued or target in live:
            continue
        found["reap"].append({
            "kind": "reap",
            "verb": PENDING_VERBS["reap"],
            "target": target,
            # No live row behind it. Carried as a row-shaped dict so every
            # consumer (the label lookup, the fleet jump, the [x] confirm) reads
            # it the same way a live item is read, and `index` is None so a
            # caller cannot jump the fleet cursor to a pane that is not there.
            "row": {"label": record["label"], "target": target},
            "index": None,
            "summary": record["reason"],
            "repo": record["repo"],
            "gone": True,
        })
    return [item for kind in PENDING_ORDER for item in found[kind]]


def pending_panel_row_at_y(
    mouse_y, panel_height, total, selected, visible_rows=PENDING_PANEL_ROWS,
):
    """Map a click inside the queue panel to a queue index, or ``None``.

    The panel's first line is its title, so a click there selects nothing --
    it is a heading, and treating it as the first item would arm an action the
    operator did not aim at.
    """
    if panel_height <= 1 or total <= 0:
        return None
    offset = mouse_y - (SHEP_TAB_Y + 2)
    visible = min(visible_rows, panel_height - 1)
    if not 0 <= offset < visible:
        return None
    index = pending_panel_start(total, selected, visible_rows) + offset
    return index if index < total else None


def pending_panel_start(total, selected, visible_rows=PENDING_PANEL_ROWS):
    """First queue index visible in the panel, given where the cursor is.

    Shared with the renderer rather than recomputed beside it: the highlight is
    drawn from this and the lines are drawn from this, and two copies drifting
    apart would reverse-video a row the cursor is not actually on -- which is
    the row Enter would then act against.
    """
    if total <= visible_rows or selected < visible_rows:
        return 0
    return min(selected - visible_rows + 1, total - visible_rows)


def pending_panel_lines(
    items, width, selected=0, focused=False, ascii_only=False,
):
    """The queue as screen lines, or ``[]`` when nothing is waiting.

    Nothing at all rather than an empty box: a permanent "0 waiting" header
    would spend a line of fleet table on every screen to report the one state
    the operator wants, which is that there is nothing to do.
    """
    if not items:
        return []
    cursor = ">" if ascii_only else "›"
    total = len(items)
    visible_rows = pending_panel_visible_rows(focused)
    hint = "[tab] focus · [enter] act" if not focused else "[enter] act · [tab] back"
    # Counted separately because they are not the same kind of thing. A recalled
    # finished session is "go and look at this when you like"; a held draft or a
    # handoff is "shep is stopped until you answer". Summing them produced a
    # panel headed "24 waiting on you" on a fleet where nothing was actually
    # waiting -- all twenty-four were completed work -- which is how a queue
    # teaches an operator to stop reading it.
    finished = sum(1 for item in items if item.get("gone"))
    waiting = total - finished
    title = f"PENDING ACTIONS · {waiting} waiting on you"
    if finished:
        title += f" · {finished} finished"
    if not waiting:
        title = f"PENDING ACTIONS · nothing waiting · {finished} finished to review"
    lines = [f"{title}{' ' * max(1, width - len(title) - len(hint))}{hint}"[:width]]
    # Scroll so the cursor stays on screen once the queue outgrows the panel,
    # the same way the fleet table does. Without it a queue of twenty hides
    # everything past the fifth item and Enter acts on something unseen.
    start = pending_panel_start(total, selected, visible_rows)
    for offset, item in enumerate(items[start:start + visible_rows]):
        marker = cursor if (focused and start + offset == selected) else " "
        repo = f"[{item['repo']}]" if item.get("repo") else ""
        # A recalled record and a live reap-ready pane both read CLOSE, so the
        # operator could not tell finished-and-gone from finished-and-still-here
        # -- and only one of the two has anything left to close. The verb says
        # which, rather than relying on the row looking different somehow.
        verb = "REVIEWED" if item.get("gone") else item["verb"]
        head = f" {marker} {verb:<8} "
        room = max(0, width - len(head) - len(repo) - 1)
        summary = item["summary"][:room].rstrip()
        pad = " " * max(1, width - len(head) - len(summary) - len(repo))
        lines.append(f"{head}{summary}{pad}{repo}"[:width])
    hidden = total - (start + visible_rows)
    if hidden > 0:
        lines.append(f"   … {hidden} more"[:width])
    return lines


def pending_action_detail_lines(item, width, ascii_only=False):
    """Explain the selected queue item in the context panel.

    The queue is intentionally not the MISSIONS deck. Its rows are operator
    decisions about already-running or already-finished sessions: approve a
    held nudge, go answer a human handoff, or review completed work. The list
    stays compact so it does not consume the fleet's vertical space; selecting
    one exposes its full reason and payload here.
    """
    if not item or width <= 0:
        return []
    row = item.get("row") or {}
    kind = item.get("kind")
    descriptions = {
        "approve": "Approve and send this held nudge to the live session.",
        "visit": "Open the session and answer its human-only question.",
        "reap": "Review completed work; close only after confirmation.",
    }
    lines = [
        f"ACTION QUEUE · {item.get('verb', kind or 'REVIEW')}",
        f"session: {session_name(row) or row.get('label') or item.get('target') or '?'}",
        f"what: {descriptions.get(kind, 'Operator review required.')}",
    ]
    if item.get("summary"):
        lines.append(f"detail: {item['summary']}")
    if kind == "approve":
        event = _NUDGE_EVENTS.get(item.get("target"), {})
        if event.get("detail"):
            lines.append(f"held because: {event['detail']}")
    return [
        _fit_cell(line, width, ascii_only)
        for raw in lines
        for line in textwrap.wrap(
            str(raw), width=max(1, width), replace_whitespace=False,
            drop_whitespace=True,
        ) or [""]
    ]


def reap_session(row, mode="manual", audit=True):
    """Close exactly one selected session through its owning transport."""
    source = row.get("source")
    target = row.get("target")
    if row.get("read_only"):
        return False, f"{source or 'this'} sessions are read-only in this tool"
    # A held key repeats. The confirm handler has no debounce, so one pane took
    # 138 closes in bursts 0.4s apart, and reaps grew to 56% of the whole audit
    # ledger. Guarding here rather than in the handler covers every caller, and
    # the window is deliberately short: a pane id herdr later reuses for a new
    # session must still be closable.
    if target and time.time() - _REAPED.get(target, 0) < REAP_DEBOUNCE_SECONDS:
        return True, "already closed"
    # Captured BEFORE the close: afterwards the pane is gone and the trace would
    # only be able to say that something was reaped, not what it had been doing.
    activity = row.get("context") or ""
    reason = row.get("reap_reason") or "closed by operator"
    if audit and target:
        try:
            record_action(
                "reap", "intent", mode=mode, target=target,
                metadata=_action_metadata(row), policy="operator-confirmed close",
                context=row.get("context_hash") or row.get("pane_signature") or row.get("context") or "",
                reason=row.get("reap_reason") or "operator-confirmed session close",
            )
        except ActionLogError as exc:
            return False, f"audit receipt unavailable: {exc}"
    if source == "herdr" and target:
        proc = _run([sys.executable, str(HERDR_CTL), "session", "close", target])
        ok, detail = proc.returncode == 0, (proc.stdout or proc.stderr).strip()
    elif source == "tmux" and target:
        proc = _run(["tmux", "kill-pane", "-t", target])
        ok, detail = proc.returncode == 0, (proc.stderr or "closed").strip()
    else:
        ok, detail = False, f"cannot reap {source or 'unknown'} session"
    if ok:
        if target:
            _REAPED[target] = time.time()
            # Closing IS the review. Leaving the record behind would keep the
            # session in the finished list after the operator has dealt with it,
            # and a queue that does not empty stops being read.
            clear_done(target)
        post_telemetry("reaped", row, detail=reason, activity=activity)
        _, worktree_detail = remove_mission_worktree(row.get("cwd"))
        if worktree_detail:
            detail = f"{detail}; {worktree_detail}" if detail else worktree_detail
    if audit and target:
        try:
            record_action(
                "reap", "reaped" if ok else "failed", mode=mode, target=target,
                metadata=_action_metadata(row), policy="operator-confirmed close",
                context=row.get("context_hash") or row.get("pane_signature") or row.get("context") or "",
                reason="transport completed" if ok else "transport failed",
                result=detail, error="" if ok else detail,
            )
        except ActionLogError:
            detail = f"{detail}; terminal audit receipt unavailable"
    return ok, detail


def answer_session(row, choice, label="", mode="manual", audit=True):
    """Answer one open questionnaire in a live pane, from the fleet table.

    Sends ONLY the option key. Both agent UIs treat the number as a hotkey that
    selects and confirms, so appending Enter the way a nudge does would submit a
    second, empty line into whatever the pane draws next. Deliberately has no
    automatic caller: a single keystroke here can approve a destructive tool
    call, so the choice is always a human's.
    """
    source = row.get("source")
    target = row.get("target")
    choice = str(choice).strip()
    if row.get("status") != "asking":
        return False, "no open question in this session"
    if not choice.isdigit():
        return False, f"not an option key: {choice[:8]!r}"
    reason = f"operator selected option {choice}: {label}".strip()
    if audit and target:
        try:
            record_action(
                "answer", "intent", mode=mode, target=target,
                metadata=_action_metadata(row), policy="operator-selected option",
                context=row.get("context_hash") or row.get("pane_signature") or row.get("context") or "",
                reason=reason, text=f"{choice}. {label}".strip(),
            )
        except ActionLogError as exc:
            return False, f"audit receipt unavailable: {exc}"
    if source == "herdr" and target:
        proc = _run([
            sys.executable, str(HERDR_CTL), "session", "send",
            "--no-submit", target, choice,
        ])
        ok, detail = proc.returncode == 0, (proc.stderr or "sent").strip()
    elif source == "tmux" and target:
        proc = _run(["tmux", "send-keys", "-t", target, choice])
        ok, detail = proc.returncode == 0, (proc.stderr or "sent").strip()
    else:
        ok, detail = False, f"cannot answer a {source or 'unknown'} session"
    if audit and target:
        try:
            record_action(
                "answer", "answered" if ok else "failed", mode=mode, target=target,
                metadata=_action_metadata(row), policy="operator-selected option",
                context=row.get("context_hash") or row.get("pane_signature") or row.get("context") or "",
                reason="transport completed" if ok else "transport failed",
                text=f"{choice}. {label}".strip(), result=detail,
                error="" if ok else detail,
            )
        except ActionLogError:
            detail = f"{detail}; terminal audit receipt unavailable"
    return ok, detail


QA_WORKTREE_ROOT = Path(
    os.environ.get("SHEP_QA_WORKTREE_ROOT", str(Path.home() / ".qa-worktrees"))
).expanduser()


def remove_mission_worktree(cwd):
    """Delete the isolated worktree a reaped session was running in.

    Without this, reaping closes the pane but leaves ~/.qa-worktrees/<repo>/
    <mission-id>/ behind. Mission ids are deterministic per project+goal, so the
    same mission comes back in the deck forever while prepare_mission_worktree
    refuses it as "probably still running" — permanently unlaunchable.

    Deliberately scoped to QA_WORKTREE_ROOT: a reap must never be able to remove
    a primary checkout. Returns (removed, detail); detail is "" when the session
    was not running in a mission worktree, so ordinary reaps stay silent.
    """
    if not cwd:
        return False, ""
    path = Path(cwd).expanduser()
    try:
        path.relative_to(QA_WORKTREE_ROOT)
    except ValueError:
        return False, ""
    if not path.exists():
        return False, ""
    # --force because an agent's worktree is nearly always dirty; the operator
    # confirmed the reap, and a kept worktree blocks the mission forever.
    proc = _run(
        ["git", "-C", str(path), "worktree", "remove", "--force", str(path)],
        timeout=30,
    )
    if proc.returncode != 0:
        return False, f"worktree kept: {(proc.stderr or proc.stdout).strip()[:80]}"
    return True, f"worktree removed: {path.name}"


def _continuation_command(row):
    agent = (row.get("label") or "").lower()
    if agent not in {"claude", "codex", "kimi"}:
        return None
    return _resolve_agent_command(agent)


def spawn_continuation(row, brief):
    """Start explicit follow-up work in a fresh Herdr session, never the old pane."""
    if row.get("source") != "herdr":
        return False, "new missions require a Herdr-managed source session"
    workspace = row.get("workspace_id")
    command = _continuation_command(row)
    if not workspace or not command:
        return False, "source session has no reusable Herdr workspace/agent command"
    slug = re.sub(r"[^a-z0-9]+", "-", brief.lower()).strip("-")[:28] or "continuation"
    name = f"mission-{slug}-{time.strftime('%H%M%S')}"
    proc = _run([
        sys.executable,
        str(HERDR_CTL),
        "session",
        "start",
        "--name",
        name,
        "--cwd",
        row.get("cwd") or str(Path.home()),
        "--space",
        workspace,
        "--cmd",
        command,
        "--prompt",
        brief,
    ], timeout=30)
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


# --- Mission deck (suggested missions) ---------------------------------------

def _has_git_checkout(path):
    """Whether `path` is a usable checkout, decided without running git.

    A normal checkout carries `.git` as a directory. A linked worktree carries
    it as a FILE holding `gitdir: <path>`, and that pointer can dangle once the
    parent repo moves or the worktree is pruned -- so the file's mere existence
    is not enough. Following it keeps the old probe's guarantee while costing no
    subprocess and, crucially, no timeout: the probe's 5s ceiling against a cold
    Syncthing-backed tree was reporting healthy repos exactly the way it reports
    deleted ones.
    """
    marker = path / ".git"
    if marker.is_dir():
        return True
    if not marker.is_file():
        return False
    try:
        pointer = marker.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    if not pointer.startswith("gitdir:"):
        return False
    target = Path(pointer.split(":", 1)[1].strip()).expanduser()
    # Relative gitdir pointers are resolved against the worktree, not the cwd.
    return (target if target.is_absolute() else path / target).exists()


def launchable_repos(repos_file):
    """(repos, dropped) — paths a mission could actually run in, and the rest.

    The repo lists drift — a moved checkout or a plain directory that was never
    a git repo still scores fine in sense.py but fails mission-launch's worktree
    preflight, so the deck would offer a mission that can never start. Dropping
    them here keeps the top-up logic free to fill the slot with a live repo, but
    the dropped ones are returned rather than swallowed: a silently missing
    source is the worst failure mode for a deck that looks complete.
    """
    try:
        lines = repos_file.read_text().splitlines()
    except OSError:
        return [], []
    repos = []
    dropped = []
    for line in lines:
        path = line.split("#", 1)[0].strip()
        if not path:
            continue
        expanded = Path(path).expanduser()
        if not expanded.is_dir():
            dropped.append(f"{expanded} (no such directory)")
            continue
        # Filesystem check before any subprocess. The git probe carried a 5s
        # timeout, and these paths sit under a Syncthing-backed tree that can be
        # cold -- so a perfectly healthy repo was intermittently reported the
        # same way a deleted one is, silently shrinking the deck with no way to
        # tell the two apart. `.git` covers a normal checkout (directory) and a
        # linked worktree (gitfile) alike, costs no process, and cannot time out.
        if _has_git_checkout(expanded):
            repos.append(str(expanded))
            continue
        # Only the unusual shapes still pay for a probe: a bare repo, or a path
        # whose .git lives elsewhere. Given how rarely this runs now, the timeout
        # can afford to be generous rather than tuned against a cold disk.
        probe = _run(["git", "-C", str(expanded), "rev-parse", "--git-dir"], timeout=20)
        if probe.returncode == 0:
            repos.append(str(expanded))
        elif probe.returncode == 124:
            # A slow disk is not a dead repo. Kept distinct so the operator is
            # told to look again rather than to go delete the entry.
            dropped.append(f"{expanded} (probe timed out — retry before removing)")
        else:
            dropped.append(f"{expanded} (not a git repo)")
    # A repo listed twice would otherwise be scored twice and could take two
    # deck slots. Order-preserving so the file's own priority still holds.
    return list(dict.fromkeys(repos)), list(dict.fromkeys(dropped))


# --- Loop-3: feed decisions back to mission-learn ----------------------------
#
# sense -> recommend -> launch were wired; `learn` was built, unit-tested, and
# left orphaned — nothing wrote its ledger, so the engine could never get better
# at proposing missions you actually take. These three helpers close it.

MISSION_LEARN_SCRIPT = _mission_skill_script("mission-learn", "learn.py")
MISSION_SENSE_CACHE = MISSION_ENGINE_DIR / "shep-sense-contributions.json"
MISSION_DISMISSED_FILE = MISSION_ENGINE_DIR / "shep-dismissed-missions.json"
# A dismissal is a statement about now ("not this week"), not forever. Beads get
# reprioritised and momentum moves, so a permanent blocklist would quietly shrink
# the deck's supply over months with no way to notice. Seven days is long enough
# that regenerating on the same afternoon does not resurrect what you just
# rejected, and short enough that a genuinely changed backlog gets a second look.
MISSION_DISMISS_TTL = 7 * 24 * 3600


def read_dismissed_missions(now=None):
    """The still-current dismissals as {mission_id: at}, expiring old ones.

    Read at generation time rather than filtered in the view, because the view
    was the entire bug: `[d]` dropped the row from the in-memory list and wrote
    a learn-ledger record that nothing ever read back, so pressing [r] brought
    every dismissed mission straight back. Dismissing five bug-hunter beads and
    regenerating returned the same five.
    """
    now = time.time() if now is None else now
    try:
        raw = json.loads(MISSION_DISMISSED_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if isinstance(value, (int, float)) and now - value < MISSION_DISMISS_TTL
    }


def dismiss_mission(mission, now=None):
    """Persist one dismissal so regeneration stops offering it. -> bool written."""
    mission_id = str((mission or {}).get("id") or "")
    if not mission_id:
        return False
    current = read_dismissed_missions(now)
    current[mission_id] = time.time() if now is None else now
    try:
        MISSION_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        MISSION_DISMISSED_FILE.write_text(json.dumps(current))
        return True
    except OSError:
        return False


def drop_dismissed(missions, now=None):
    """Remove missions the operator has already rejected inside the TTL."""
    dismissed = read_dismissed_missions(now)
    return [m for m in missions if str(m.get("id") or "") not in dismissed]


def _cache_sense_contributions(sense_stdout):
    """Persist per-project `weighted_contributions` from a sense analysis.

    learn.py attributes a decision to the signals that drove it, and those live
    in the sense output, not in the deck. Merged rather than replaced: build and
    research decks come from different repo sets in two separate sense runs, and
    the second must not erase the first's projects.
    """
    try:
        projects = json.loads(sense_stdout).get("projects", [])
    except (json.JSONDecodeError, AttributeError):
        return
    contributions = mission_drivers_map()
    for project in projects:
        if project.get("name") and project.get("weighted_contributions"):
            contributions[project["name"]] = project["weighted_contributions"]
    try:
        MISSION_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        MISSION_SENSE_CACHE.write_text(json.dumps(contributions))
    except OSError:
        pass  # telemetry for the learner; never worth failing a deck over


def mission_drivers_map():
    try:
        return json.loads(MISSION_SENSE_CACHE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def record_mission_decision(event, mission):
    """Append one accept/dismiss to the mission-learn ledger. -> bool recorded.

    Best-effort: a missing learner must never block launching a mission.
    """
    if not MISSION_LEARN_SCRIPT.exists() or not mission:
        return False
    cmd = [
        "python3", str(MISSION_LEARN_SCRIPT), "record", "--event", event,
        "--mission", str(mission.get("id") or ""),
        "--project", str(mission.get("project_name") or ""),
        "--score", str(mission.get("momentum_score") or 0),
    ]
    drivers = mission_drivers_map().get(mission.get("project_name"))
    if drivers:
        cmd += ["--drivers", json.dumps(drivers)]
    return _run(cmd, timeout=15).returncode == 0


def _generate_deck(repos_file, mode, top, min_score=None):
    """Run sense -> recommend for one repo set. Returns (missions, error).

    `_DROPPED_REPOS` collects unusable entries so the view can say which
    configured sources are missing instead of quietly shrinking the deck.
    """
    if not repos_file.exists():
        return [], f"no repos file: {repos_file}"
    repos, dropped = launchable_repos(repos_file)
    _DROPPED_REPOS.update(dropped)
    if not repos:
        return [], f"no launchable git repos in {repos_file.name}"
    sense_cmd = ["python3", str(MISSION_SENSE_SCRIPT), "analyze"]
    for repo in repos:
        sense_cmd += ["--repo", repo]
    sense = _run(sense_cmd, timeout=120)
    if sense.returncode != 0:
        return [], f"mission-sense failed: {sense.stderr.strip()[:160]}"
    _cache_sense_contributions(sense.stdout)
    cmd = ["python3", str(MISSION_RECOMMEND_SCRIPT), "deck", "--mode", mode, "--top", str(top)]
    if min_score is not None:
        cmd += ["--min-score", str(min_score)]
    try:
        recommend = subprocess.run(
            cmd, input=sense.stdout, capture_output=True, text=True, timeout=60, check=False,
        )
    except subprocess.TimeoutExpired:
        return [], "mission-recommend timed out"
    if recommend.returncode != 0:
        return [], f"mission-recommend failed: {recommend.stderr.strip()[:160]}"
    try:
        # Dismissals are dropped here so both callers (build and research) get
        # them for free, and so the caller's `len(...) < MISSION_DECK_TOP`
        # top-up gates count only missions that can actually be offered.
        return drop_dismissed(
            json.loads(recommend.stdout).get("missions", [])
        ), None
    except json.JSONDecodeError as exc:
        return [], f"bad deck json: {exc}"


def gate_research(missions):
    """Drop scouts the mission engine's own research gate rejects.

    Fail-soft on purpose: if the gate script is missing or errors, we keep the
    unfiltered scouts rather than silently emptying the deck — a duplicate
    scout is a nuisance, an empty deck is a broken feature.
    """
    if not missions or not RESEARCH_CYCLE_SCRIPT.exists():
        return missions
    deck = {"schema": "atlas-mission-deck/v1", "mode": "research",
            "count": len(missions), "missions": missions}
    gate_path = MISSION_ENGINE_DIR / "shep-gate-input.json"
    try:
        MISSION_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        gate_path.write_text(json.dumps(deck))
    except OSError:
        return missions
    try:
        result = _run(
            ["python3", str(RESEARCH_CYCLE_SCRIPT), "gate", "--deck", str(gate_path)],
            timeout=30,
        )
    finally:
        gate_path.unlink(missing_ok=True)
    if result.returncode != 0:
        return missions
    try:
        return json.loads(result.stdout).get("missions", missions)
    except json.JSONDecodeError:
        return missions


def cap_per_project(items, per_project=MISSION_DECK_PER_PROJECT, top=None, key=None):
    """Keep each project to `per_project` slots, preserving rank order.

    Applied to the bead source, which is the one that sorts globally across
    repos and so is the one a single backlog can monopolise -- it took all five
    slots of the live deck for days. Build and research missions come back
    already ranked per project and are deduped by `merge_decks`, so they do not
    route through here; this is deliberately not "every deck source". Order is
    preserved rather than round-robined — the ranking above this is the model's
    and priority's, and reordering it to spread projects out would discard the
    judgement that produced it. Overflow is dropped, not deferred: the whole
    point is to leave room for the other sources.

    ``key`` reads the project from an item, so this runs on raw `(issue, repo)`
    candidate pairs as well as on built mission dicts. Bead candidates have to
    be capped while they are still pairs — the mission dicts do not exist until
    after the slice this is here to constrain.
    """
    read = key or (lambda item: (item or {}).get("project_name"))
    kept, counts = [], {}
    for item in items:
        project = read(item)
        if counts.get(project, 0) >= per_project:
            continue
        counts[project] = counts.get(project, 0) + 1
        kept.append(item)
        if top and len(kept) >= top:
            break
    return kept


def merge_decks(build_missions, research_missions, top=MISSION_DECK_TOP):
    """Build missions first, then research scouts to top the deck up to `top`.

    Deduped by project so one repo never occupies two slots — a build mission
    already covers that project, and a second research scout on it is noise.
    Pure function so the ordering/dedup contract is testable without shelling out.
    """
    merged = list(build_missions[:top])
    seen = {m.get("project_name") for m in merged}
    for mission in research_missions:
        if len(merged) >= top:
            break
        if mission.get("project_name") in seen:
            continue
        seen.add(mission.get("project_name"))
        merged.append(mission)
    return merged


def load_mission_deck(force=False, allow_generate=True):
    """Deck plus the tab badge, so MISSIONS shows a count from any view.

    The cache-only teaser is allowed to prime the badge but never to zero it:
    a cold cache means "not loaded yet", and showing 0 there would claim there
    is nothing to launch when nobody has actually looked.
    """
    missions, error = _load_mission_deck(force=force, allow_generate=allow_generate)
    if missions or allow_generate:
        set_tab_badge("missions", len(missions))
    return missions, error


def _load_mission_deck(force=False, allow_generate=True):
    """Ranked mission suggestions, bead-led. Returns (missions, error).

    Three sources, in strict order of how much we trust them:
      - bead missions: an open, unblocked bead in a delivery repo is work
        someone already decided mattered and wrote down. It leads the deck, and
        the mission's whole objective is closing it;
      - build missions inferred by mission-sense/recommend, only from
        MISSION_REPOS_FILE (delivery-eligible), and only above MISSION_MIN_SCORE
        or they are busywork;
      - artifact-only research scouts from the wider MISSION_RESEARCH_REPOS_FILE
        (see the SAFETY INVARIANT above), which top the deck up so it reliably
        offers a full slate.

    Each source only runs when the ones above it left the deck thin: the
    sense+recommend sweep shells out to bd/git per repo and costs ~2 minutes,
    which is pure waste when the deck is already full of real, closable beads.

    Disk-cached for MISSION_DECK_TTL. allow_generate=False only reads the
    existing cache (cheap, used for the startup teaser) and never shells out.
    """
    try:
        if not force and MISSION_DECK_CACHE.exists():
            age = time.time() - MISSION_DECK_CACHE.stat().st_mtime
            if age < MISSION_DECK_TTL:
                # Filtered on the way out, not only when regenerating. The
                # cache lives for MISSION_DECK_TTL and the view reads it with
                # force=False, so a mission dismissed a minute ago was served
                # straight back from disk on the next visit to the tab -- the
                # dismissal only appeared to stick until you left and returned.
                return drop_dismissed(
                    json.loads(MISSION_DECK_CACHE.read_text()).get("missions", [])
                ), None
    except (OSError, json.JSONDecodeError):
        pass
    if not allow_generate:
        return [], None

    _DROPPED_REPOS.clear()  # re-derived every sweep, else a fixed repo stays "skipped"
    # Cache-only on purpose. The BEADS tab owns generating a triage verdict,
    # where the operator is looking at the backlog and a painted "thinking…"
    # makes sense; the deck sweep is already a ~2-minute blocking call and must
    # not grow a model call on top of it. A cold cache just means the deck falls
    # back to priority order until the BEADS tab has been opened once.
    beads, bead_err = bead_missions(
        MISSION_DECK_TOP, rank=bead_triage.work_rank(bead_triage.read_cache())
    )
    # No filter here: bead_missions now drops dismissals on the raw candidate
    # list, before the per-project cap, so a freed slot is refilled from the same
    # backlog rather than simply lost.

    # Bead missions need only mission-launch, so a missing sense/recommend now
    # costs the top-up rather than the whole deck.
    engine_ready = MISSION_SENSE_SCRIPT.exists() and MISSION_RECOMMEND_SCRIPT.exists()
    build, build_err = [], None
    if len(beads) < MISSION_DECK_TOP:
        if not engine_ready:
            build_err = "mission engine skills not installed"
        else:
            build, build_err = _generate_deck(
                MISSION_REPOS_FILE, "implementation", MISSION_DECK_TOP, MISSION_MIN_SCORE
            )
    # Deduped by project, so an inferred build mission never takes a second slot
    # on a repo whose real bead is already on the deck.
    missions = merge_decks(beads, build, MISSION_DECK_TOP)

    # Research top-up is best-effort: a full deck, or a missing/broken research
    # repo set, must never block launching the missions we already have.
    research, research_err = [], None
    if engine_ready and len(missions) < MISSION_DECK_TOP:
        research, research_err = _generate_deck(
            MISSION_RESEARCH_REPOS_FILE, "research", MISSION_DECK_TOP * 2
        )
        # Two independent filters. The mission_kind check is defence-in-depth:
        # these missions come from the wider repo list, which includes product
        # and personal repos, so anything that is not explicitly artifact-only
        # must never become launchable from here — we do not stake that on
        # recommend.py continuing to stamp the field (delivery-repos.txt already
        # claims a guard there that does not exist).
        research = [
            m for m in research
            if m.get("mission_kind") == "research"
            and m.get("momentum_score", 0) >= MISSION_RESEARCH_MIN_SCORE
        ]
        # The engine's own gate knows what research is already in flight and
        # what was previously rejected as duplicate — state a per-deck dedup
        # cannot see. Reuse it rather than offering a scout on a project that
        # already has one running.
        research = gate_research(research)
    missions = merge_decks(missions, research, MISSION_DECK_TOP)
    if not missions:
        return [], build_err or research_err or bead_err or "no missions above threshold"

    deck = {
        "schema": "atlas-mission-deck/v1",
        "mode": "shep-merged",
        "count": len(missions),
        "missions": missions,
    }
    try:
        MISSION_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        MISSION_DECK_CACHE.write_text(json.dumps(deck))
    except OSError as exc:
        # Launch reads the deck from disk — if we could not persist it, say so
        # rather than offering missions that would fail to launch.
        return missions, f"deck cache write failed: {exc}"
    # Only report a collector error when it actually cost the user missions —
    # a full deck with a failed top-up is not worth an error banner, a thin one is.
    # bead_err is deliberately not reported here: "no ready beads" is the normal
    # steady state of a healthy backlog, not a failure, and banner-ing it would
    # make a working deck look broken. It only surfaces when nothing survives.
    if len(missions) < MISSION_DECK_TOP:
        return missions, build_err or research_err
    return missions, None


QA_WORKTREE_SCRIPT = Path(
    os.environ.get("SHEP_QA_WORKTREE", str(Path.home() / ".claude/scripts/qa-worktree.sh"))
)


def prepare_mission_worktree(mission):
    """Cut the verified isolated worktree a mission needs. Returns (path, error).

    mission-launch refuses to run in a repository's primary checkout, so every
    deck mission fails without this. We use the sanctioned qa-worktree.sh rather
    than passing --allow-primary-checkout: agent work must never move or dirty
    the branch the primary checkout is parked on.
    """
    cwd = mission.get("cwd")
    if not cwd:
        return None, "mission has no cwd"
    if not QA_WORKTREE_SCRIPT.exists():
        return None, f"qa-worktree.sh not found at {QA_WORKTREE_SCRIPT}"
    # qa-worktree.sh force-removes an existing track (worktree + branch) before
    # recreating it. Mission ids are deterministic hashes, so a relaunch would
    # delete a live agent's uncommitted work. The worktree on disk is the only
    # guard that survives a shep restart or a second shep instance — an
    # in-memory set does not.
    if mission_worktree_exists(cwd, mission.get("id") or ""):
        return None, (
            "a worktree for this mission already exists — it is probably still "
            "running; reap it before relaunching"
        )
    cmd = ["bash", str(QA_WORKTREE_SCRIPT), cwd, mission.get("id") or "mission"]
    base = mission_base_branch(cwd, mission.get("default_branch"))
    if base:
        cmd.append(base)
    result = _run(cmd, timeout=120)
    if result.returncode != 0:
        return None, (result.stderr or result.stdout).strip()[:200]
    for line in result.stdout.splitlines():
        if line.startswith("WORKTREE_PATH="):
            return line.split("=", 1)[1].strip(), None
    return None, "qa-worktree.sh printed no WORKTREE_PATH"


def mission_base_branch(repo, default_branch):
    """Branch to cut the mission worktree from — `develop` when the repo has one.

    sense.py derives default_branch from origin/HEAD, which is `main` for some
    repos that nevertheless integrate through `develop`. Cutting an SDLC branch
    off main is explicitly forbidden and forces a painful MR re-target, so
    prefer a real local develop and fall back to what the mission declared.
    """
    probe = _run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "develop"], timeout=5
    )
    if probe.returncode == 0:
        return "develop"
    return default_branch


def mission_worktree_path(repo, mission_id):
    """The exact path qa-worktree.sh would use for this mission's track."""
    return Path.home() / ".qa-worktrees" / Path(repo).name / mission_id


def mission_worktree_exists(repo, mission_id):
    """True when this mission's worktree directory already exists.

    Deliberately PATH-based, not branch-based: qa-worktree.sh destroys by path
    (`[ -e "$WT_PATH" ] && rm -rf "$WT_PATH"`, unconditionally), and the mission
    spec tells the agent to switch to feat/<id> once it starts. A branch check
    therefore goes blind exactly when the agent is running — and detached HEAD
    would evade it too. Checking the directory matches what actually gets
    deleted, and survives a shep restart or a second shep instance.
    """
    if not mission_id:
        return False
    return mission_worktree_path(repo, mission_id).exists()


def repoint_mission(mission, worktree):
    """Rewrite every reference to the primary checkout to the isolated worktree.

    Re-pointing `cwd` alone is not enough and the gap is dangerous: `launch_spec`
    is a string pre-rendered by recommend.py that names the repo path, and
    launch.py injects it verbatim as the agent's first prompt. Left unrewritten,
    the agent starts in the worktree but is *told* to work in the primary
    checkout, edits by absolute path, and commits to the live branch — exactly
    what the worktree exists to prevent.
    """
    old = mission.get("cwd")
    if not old:
        return dict(mission)

    # research_cycle.reconcile() harvests the artifact at
    # <cwd>/reports/research/mission-engine/<cwd.name>-research.md. Because the
    # worktree is named after the mission id, cwd.name is no longer the project
    # slug the spec tells the agent to write — so without this the artifact is
    # written somewhere reconcile never looks, the mission stays "active"
    # forever, and no follow-up research is ever generated.
    replacements = [(old, worktree)]
    old_artifact = mission.get("artifact_path")
    if old_artifact:
        replacements.append((
            old_artifact,
            f"reports/research/mission-engine/{Path(worktree).name}-research.md",
        ))

    def rewrite(value):
        # Must recurse: recommend.py emits `evidence` as a list of bead titles
        # and launch.py copies it into the bead the agent reads, so a top-level
        # -only rewrite still leaks the primary checkout to the agent.
        if isinstance(value, str):
            for stale, fresh in replacements:
                value = value.replace(stale, fresh)
            return value
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return value

    return rewrite(mission)


def launch_mission_by_id(mission_id, mission=None, goal_runtime=None):
    """Dispatch one approved deck mission via mission-launch (Beads bead + herdr pane).

    ``mission`` lets a caller that already holds the record (away mode ranks a
    wider pool than the shared deck cache keeps, and the BEADS tab builds its
    bead missions straight from the backlog) skip the cache lookup.
    ``goal_runtime`` restamps the mission's goal-owning runtime; see the note in
    ``afk_launch`` for why setting the environment variable alone is not enough.
    """
    if not MISSION_LAUNCH_SCRIPT.exists():
        return False, "mission-launch script not found"
    if not mission_id:
        return False, "mission has no id"
    if mission is None:
        if not MISSION_DECK_CACHE.exists():
            return False, "no cached deck — press r to generate one first"
        try:
            deck = json.loads(MISSION_DECK_CACHE.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"unreadable deck cache: {exc}"
        mission = next(
            (m for m in deck.get("missions", []) if m.get("id") == mission_id), None
        )
        if mission is None:
            return False, f"{mission_id} is not in the cached deck"
    else:
        deck = {"schema": "atlas-mission-deck/v1"}
    # Second, cheaper guard for the same session; prepare_mission_worktree
    # holds the authoritative on-disk check that also survives a restart.
    if mission_id in _MISSIONS_LAUNCHED:
        return False, "already launched this session — reap it before relaunching"

    worktree, error = prepare_mission_worktree(mission)
    if error:
        return False, f"worktree setup failed: {error}"

    # Point the mission at its isolated worktree and hand mission-launch a deck
    # holding only this mission, so an --all typo elsewhere cannot fan out.
    staged = repoint_mission(mission, worktree)
    if goal_runtime:
        # launch.py's validate_goal_contract() rejects any goal_mode mission
        # whose goal_runtime does not equal ITS OWN import-time
        # MISSION_GOAL_ROUTER_RUNTIME. Shep froze BEAD_GOAL_RUNTIME at its own
        # import, so without this restamp an away-mode batch fails validation
        # before a single pane is created.
        staged["goal_runtime"] = goal_runtime
    deck_path = MISSION_ENGINE_DIR / f"shep-launch-{mission_id}.json"
    try:
        MISSION_ENGINE_DIR.mkdir(parents=True, exist_ok=True)
        deck_path.write_text(json.dumps({
            "schema": "atlas-mission-deck/v1", "mode": "shep-launch",
            "count": 1, "missions": [staged],
        }))
    except OSError as exc:
        return False, f"could not stage deck: {exc}"

    cmd = ["python3", str(MISSION_LAUNCH_SCRIPT), "launch",
           "--deck", str(deck_path), "--mission", mission_id]
    if mission.get("mission_kind") == "research":
        # research_cycle.reconcile() only harvests launches recorded in the
        # "research" space. Launching a research mission into the default
        # "missions" space strands its artifact outside the lifecycle: the
        # mission never completes, never gets reviewed, and never unblocks
        # follow-up research.
        cmd += ["--space-label", "research"]
    if mission.get("needs_research"):
        # Otherwise the spec tells the agent to read a research brief that was
        # never generated.
        cmd.append("--research")
    try:
        result = _run(cmd, timeout=300)
    finally:
        deck_path.unlink(missing_ok=True)

    if result.returncode == 124:
        # A timeout is NOT a failure: launch.py may already have created the
        # pane, bead and worktree. Reporting "failed" invites a retry, and a
        # retry force-removes the worktree of the agent that just started.
        # Record it as launched — a false positive costs one manual reap, a
        # false negative costs an agent's work.
        _MISSIONS_LAUNCHED.add(mission_id)
        return False, (
            f"timed out after 300s — it MAY still be starting in {worktree}. "
            "Check the missions workspace before retrying."
        )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()[:300]
    _MISSIONS_LAUNCHED.add(mission_id)
    tail = result.stdout.strip().splitlines()
    detail = tail[-1] if tail else "launched"
    # Name the worktree: for research missions it is the only place their
    # artifact is written, and it is not otherwise discoverable from the TUI.
    return True, f"{detail} · {worktree}"


# --- Curses TUI ------------------------------------------------------------

# Secondary text — labels, hints, timestamps, the last-nudge recap line. This
# used to be A_DIM, which most terminals render as mid-grey: invisible on a
# light background, and those are exactly the lines an operator has to read.
# De-emphasis is done with weight instead (payload BOLD, chrome plain), so the
# hierarchy survives on any background. One name so it stays one decision.
SOFT = curses.A_NORMAL

# Everything below the fleet table — the pane preview and the recap/plan detail
# lines — shares this floor.
MIN_CTX_LINES = 6

LOADING_SPINNERS = ("◒", "◐", "◓", "◑")
ASCII_LOADING_SPINNERS = ("|", "/", "-", "\\")


def loading_indicator(frame=0, ascii_only=False):
    """Return the deterministic startup/refresh indicator for one frame."""
    spinners = ASCII_LOADING_SPINNERS if ascii_only else LOADING_SPINNERS
    return f"{spinners[max(0, int(frame)) % len(spinners)]} LOADING"


def loading_panel_lines(frame=0, ascii_only=False):
    """Return a compact centered status card for an empty/loading fleet."""
    if ascii_only:
        edge, side = "+" + "-" * 20 + "+", "|"
    else:
        edge, side = "╭" + "─" * 20 + "╮", "│"
    content = loading_indicator(frame, ascii_only)
    return edge, f"{side}{content.center(20)}{side}", edge.replace(
        "╭", "╰").replace("╮", "╯").replace("+", "+")


def agents_table_height(row_count, height, panel_h=0, split=False):
    """How many fleet rows the AGENTS table may occupy.

    A floor under the context panel is not enough on its own. With a long fleet
    the table grew until the panel held its detail lines and zero lines of
    real pane output — the one thing it exists to show — so a busy machine hid
    exactly the context the operator opened Shep for. The table therefore also
    never takes more than half the body; the rest of the fleet is one [j]/[k]
    away, and a full-screen read of any single session is one [→] away.

    `panel_h` is the pending-actions panel above the table, which competes for
    the same rows: charge it to the table's budget, never to the context.

    `split` means the context sits in its own column beside the table rather
    than underneath it, so the two no longer compete for rows: the halving and
    the MIN_CTX_LINES reserve both exist only to protect a context panel that
    is no longer there, and applying them anyway would waste half the column.
    """
    body = height - 9 - max(0, panel_h)  # chrome: header, tabs, column header, footers
    if split:
        return max(2, min(row_count, body))
    return max(2, min(row_count, body - MIN_CTX_LINES, body // 2))


# The AGENTS view can put the session context beside the fleet instead of under
# it. Ratios are the LEFT (fleet) share; the operator walks them with [ and ].
# Ratios are the LEFT (fleet) share. Context is deliberately the larger side
# at the automatic setting: the table identifies sessions, while the selected
# pane output is what lets the operator decide what to do next.
AGENTS_SPLIT_RATIOS = (0.4, 0.5, 0.6, 0.67)
# Keep the fleet and selected-session context side by side on ordinary
# terminal sizes too. At 88 columns the compact fleet table still has a
# 44-column left pane and the context pane has 41; narrower terminals remain
# stacked so neither view becomes unreadable.
AGENTS_SPLIT_MIN_WIDTH = 88
AGENTS_SPLIT_MIN_LEFT = 40   # below this the fleet table loses its status column
AGENTS_SPLIT_MIN_RIGHT = 24  # below this pane output is too clipped to read


def agents_split(width, index):
    """Column geometry for the AGENTS view: ``(left_w, right_x, right_w)``.

    Returns None for the stacked layout — either because the operator walked
    the divider off the left edge, or because the terminal is too narrow to
    give both columns a readable width. Splitting a small terminal is the worse
    failure: two unreadable columns instead of one readable one.
    """
    if index is None or width < AGENTS_SPLIT_MIN_WIDTH:
        return None
    ratio = AGENTS_SPLIT_RATIOS[max(0, min(index, len(AGENTS_SPLIT_RATIOS) - 1))]
    left = int(width * ratio)
    right_x = left + 3  # gutter, divider rule, gutter
    right = width - right_x
    if left < AGENTS_SPLIT_MIN_LEFT or right < AGENTS_SPLIT_MIN_RIGHT:
        return None
    return left, right_x, right


def auto_split_index(width):
    """Choose the best automatic side-by-side layout, or None.

    Splitting is not worth a downgrade nobody asked for. `table_layout` drops
    the AGENT and REPO columns below 110, so a fixed default ratio quietly cost
    a 160-column terminal two columns of fleet — while that same terminal had
    room for both. Prefer the first ratio that keeps the wide table. On a
    smaller terminal, prefer the first readable split instead of falling back
    to the stacked layout: the fleet then gets the full available height and
    the selected session remains visible beside it.
    """
    readable = None
    for index in range(len(AGENTS_SPLIT_RATIOS)):
        geometry = agents_split(width, index)
        if not geometry:
            continue
        if readable is None:
            readable = index
        if "repo" in {key for key, _l, _w in table_layout(geometry[0])}:
            return index
    return readable


def fleet_row_attr(is_selected, queue_focused):
    """Highlight for one fleet table row. -> curses attribute

    The queue cursor now drags the fleet cursor with it, so both lists carry a
    highlight at the same time, and each needs to say which one the arrows
    drive. Both keep the reverse bar -- what varies is the underline.

    The followed row used to be bold+underline with no bar, which is the exact
    attribute pair the table's own column header is drawn with one line above
    it. Clicking a queue item therefore looked like it had selected nothing:
    the fleet cursor really had moved, it just rendered as a second header.
    Which list holds the keys is already said by the queue's own cursor glyph,
    so the fleet row no longer has to give up its bar to say it.
    """
    if not is_selected:
        return curses.A_NORMAL
    if queue_focused:
        return curses.A_REVERSE | curses.A_UNDERLINE
    return curses.A_REVERSE


def _char_columns(char):
    category = unicodedata.category(char)
    if category in {"Cf", "Me", "Mn"}:
        return 0
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


def _clip_to_columns(text, max_width):
    """Clip text by terminal cells instead of Python character count."""
    clipped = []
    used = 0
    for char in text:
        width = _char_columns(char)
        if used + width > max_width:
            break
        clipped.append(char)
        used += width
    return "".join(clipped)


def _text_columns(text):
    """Terminal-cell width, including wide glyphs and zero-width marks."""
    return sum(_char_columns(char) for char in text)


def _ascii_text(text):
    """Keep live pane text readable on limited-font or remote terminals."""
    replacements = str.maketrans({
        "…": "...", "—": "-", "–": "-", "·": "|", "•": "*",
        "“": '"', "”": '"', "‘": "'", "’": "'", "✓": "OK",
        "◆": "*", "│": "|", "─": "-", "╭": "+", "╮": "+",
        "╰": "+", "╯": "+",
    })
    return str(text or "").translate(replacements).encode("ascii", "replace").decode()


def _fit_cell(text, width, ascii_only=False):
    """Pad or ellipsize text to exactly ``width`` terminal cells."""
    text = str(text or "")
    if ascii_only:
        text = _ascii_text(text)
    if width <= 0:
        return ""
    current = _text_columns(text)
    if current > width:
        if width == 1:
            return "." if ascii_only else "…"
        suffix = "..." if ascii_only and width >= 3 else "…"
        text = _clip_to_columns(text, width - _text_columns(suffix)) + suffix
        current = _text_columns(text)
    return text + (" " * max(0, width - current))


TABLE_SEPARATOR = " │ "
ASCII_TABLE_SEPARATOR = " | "
CONTROLS = "click/j/k select · → live · esc back · q quit · n nudge · r refresh · t theme · N fleet · x reap · m new mission · a drafts"


def use_ascii_ui(env=None):
    """Use conservative glyphs for limited-font, remote, or older terminals."""
    env = os.environ if env is None else env
    return env.get("SHEP_ASCII", "").lower() in {
        "1",
        "true",
        "yes",
    } or (
        env.get("TERM", "").lower() in {"dumb", "unknown"}
    )


def source_badge(source):
    """Retain readable source names without font-specific glyphs."""
    return {
        "herdr": "Herdr", "tmux": "tmux", "t3": "T3", "warp": "Warp",
    }.get(str(source or "").lower(), "?")


def agent_badge(row, source_visible=False):
    """Prefix known agents with a compact badge while retaining their name."""
    label = str(row.get("label") or "-")
    if row.get("source") == "tmux":
        return label if source_visible else f"[T] {label}"
    lowered = label.lower()
    badges = (("codex", "[CX]"), ("claude", "[CL]"), ("kimi", "[KI]"))
    badge = next((mark for name, mark in badges if name in lowered), "[?]")
    return f"{badge} {label}"


def agent_badge_token(row, source_visible=False):
    """Return the exact cell fragment that receives badge background styling."""
    if row.get("source") == "tmux":
        return "" if source_visible else "[T]"
    label = str(row.get("label") or "").lower()
    for name, badge in (("codex", "[CX]"), ("claude", "[CL]"), ("kimi", "[KI]")):
        if name in label:
            return badge
    return "[?]"


def agent_badge_pair_id(row):
    """Theme pair reserved for each independently styled agent badge."""
    if row.get("source") == "tmux":
        return 9
    label = str(row.get("label") or "").lower()
    if "codex" in label:
        return 6
    if "claude" in label:
        return 7
    if "kimi" in label:
        return 8
    return 0


def status_display(row):
    """Shape plus text keeps status legible without color."""
    status = str(row.get("status") or "unknown")
    if row.get("reap_ready"):
        return "! REAP READY"
    if status == "stalled" or status.startswith("[UNRESPONSIVE"):
        return "! stalled"
    if status == "asking":
        return "? needs answer"
    if status == "error":
        return "x error"
    if status in {"idle", "done"}:
        return f"o {status}"
    if status == "working":
        return "> working"
    if status == "shell":
        return "_ shell"
    if status == "live-ro":
        return "~ live ro"
    return f"? {status}"


def status_color_pair_id(row):
    status = str(row.get("status") or "unknown")
    if (
        row.get("reap_ready")
        or status in {"stalled", "asking"}
        or status.startswith("[UNRESPONSIVE")
    ):
        return 5
    if status in {"idle", "done"}:
        return 1
    if status == "error":
        return 3
    if status == "working":
        return 2
    if status == "live-ro":
        return 4
    return 0


# Cached on the outcome log's identity, not on a clock: the header redraws
# every few seconds and the log is hundreds of KB by evening, so re-parsing it
# per frame would spend more time reading telemetry than drawing the fleet.
_SENT_TALLY = {"key": None, "count": 0}


def nudges_sent_today(now=None):
    """How many nudges actually reached a pane today. -> int

    Read back out of the outcome log rather than kept as an in-memory counter,
    because the process that sends almost all of them is not this one. The
    unattended sweep runs every five minutes and exits; a counter held in the
    TUI would show the operator only the handful their own session sent and
    none of the engine's, which is the opposite of the question being asked.

    Only today's file is counted. It is the number that answers "is the engine
    working right now" -- an all-time total climbs forever and stops being
    informative about the thing the operator is looking at.
    """
    stamp = time.strftime("%Y-%m-%d", time.localtime(now)) if now else time.strftime("%Y-%m-%d")
    path = _outcomes_events_dir() / f"events-{stamp}.jsonl"
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        # No log yet today is a real answer (zero), not an error to surface in
        # a header that has nowhere to put one.
        _SENT_TALLY.update({"key": None, "count": 0})
        return 0
    if _SENT_TALLY["key"] == key:
        return _SENT_TALLY["count"]
    count = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                # Substring-gated before the JSON parse: this runs over tens of
                # thousands of lines and all but a few percent cannot match.
                if '"sent"' in line:
                    try:
                        if json.loads(line).get("event") == "sent":
                            count += 1
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return _SENT_TALLY["count"]
    _SENT_TALLY.update({"key": key, "count": count})
    return count


def fleet_counts(rows):
    """Return command-deck counters for the current fleet."""
    counts = {"total": len(rows), "working": 0, "idle": 0, "attention": 0, "reap": 0}
    for row in rows:
        status = str(row.get("status", "")).lower()
        if row.get("reap_ready"):
            counts["reap"] += 1
        if status == "working":
            counts["working"] += 1
        elif status in {"idle", "done"}:
            counts["idle"] += 1
        if status in {"stalled", "error", "asking"} or "unresponsive" in status:
            counts["attention"] += 1
    return counts


def status_badge(row, ascii_only=False):
    """Semantic status label; color may decorate it but never carries meaning."""
    status = str(row.get("status", "unknown")).lower()
    if row.get("reap_ready"):
        label, glyph = "REAP READY", "✓"
    elif status == "working":
        label, glyph = "WORKING", "●"
    elif status in {"idle", "done"}:
        label, glyph = "IDLE", "○"
    elif status == "stalled" or "unresponsive" in status:
        label, glyph = "ATTENTION", "!"
    elif status == "asking":
        label, glyph = "NEEDS ANSWER", "?"
    elif status == "shell":
        label, glyph = "SHELL", "_"
    elif status == "live-ro":
        label, glyph = "LIVE RO", "◌"
    elif status == "identified":
        label, glyph = "IDENTIFIED", "◎"
    elif status == "transcript-ro":
        label, glyph = "TRANSCRIPT RO", "◌"
    elif status == "unobserved":
        label, glyph = "UNOBSERVED", "~"
    elif "error" in status:
        label, glyph = "ERROR", "!"
    else:
        label, glyph = status.upper() or "UNKNOWN", "?"
    return f"[{label}]" if ascii_only else f"{glyph} {label}"


def commander_header(rows, width, refresh_age=0, ascii_only=False, theme="classic"):
    """Build the fixed Commander M command-deck header."""
    width = max(1, width)
    left, fill, side, right = (
        ("+", "-", "|", "+") if ascii_only else ("╭", "─", "│", "╮")
    )
    lower_left, lower_right = (("+", "+") if ascii_only else ("╰", "╯"))
    insignia = "[M]" if ascii_only else COMMANDER_M_INSIGNIA
    title = f" {insignia} {COMMANDER_M_NAME.upper()}  /  SHEP  /  {theme.upper()} "
    body_width = max(0, width - 2)
    visible_title = _fit_cell(title, body_width, ascii_only).rstrip()
    top = left + visible_title + fill * max(0, body_width - _text_columns(visible_title)) + right
    counts = fleet_counts(rows)
    # What the engine has actually done today, next to what the fleet looks
    # like right now. Every other counter here is a snapshot of state; without
    # this one the header can show a quiet fleet and give no hint whether that
    # is because nothing needed nudging or because nudging stopped working.
    sent = nudges_sent_today()
    compact = (
        f"FLEET{counts['total']:02d} RUN{counts['working']:02d} "
        f"IDLE{counts['idle']:02d} !{counts['attention']:02d} "
        f"REAP{counts['reap']:02d} SENT{sent:d}"
    )
    full = (
        f"FLEET {counts['total']:02d}  RUN {counts['working']:02d}  "
        f"IDLE {counts['idle']:02d}  ALERT {counts['attention']:02d}  "
        f"REAP {counts['reap']:02d}  SENT {sent:d} today  "
        f"REFRESH {int(refresh_age):02d}s"
    )
    summary = full if _text_columns(" " + full) <= body_width else compact
    middle = side + _fit_cell(" " + summary, body_width, ascii_only) + side
    bottom = lower_left + fill * body_width + lower_right
    return top, middle, bottom


def panel_rule(label, width, ascii_only=False):
    """Render a fixed-width selected-session divider."""
    marker = "-" if ascii_only else "─"
    title = f" {label} "
    return _fit_cell(title + marker * max(0, width - _text_columns(title)), width, ascii_only)


def command_footer(width, safe=0, held=0, drafting=0, message="", ascii_only=False):
    """Return key help that retains navigation and quit at supported widths.

    The optional hints are added one at a time rather than in blocks: a block
    that did not fit used to take four other keys down with it, so a 120-column
    terminal advertised fewer keys than the width could actually hold.
    """
    if width < 60:
        # No room for anything but move/nudge/refresh/quit — and [q] must never
        # be the hint that gets ellipsized away.
        return _fit_cell("[j/k]move [n]nudge [r]refresh [q]quit", width, ascii_only)
    text = (
        f"[j/k] select  {'[>] live' if ascii_only else '[→] live'}  "
        "[n] nudge  [r] refresh  [q] quit"
    )
    optional = [
        "  |  [click] select",
        "  [i] intent",
        "  [N] fleet",
        "  [enter/x] close",
        "  [m] mission",
        "  [M] missions",
        "  [A] answer",
        "  [I] terminal",
        "  [[/]] split",
        f"  |  queue {safe} safe / {held} held / {drafting} drafting",
    ]
    if message:
        optional.append(f"  |  {message}")
    for suffix in optional:
        if _text_columns(text + suffix) > width:
            break
        text += suffix
    return _fit_cell(text, width, ascii_only)


def mission_kind_label(mission):
    """BEAD closes tracked work, BUILD writes inferred code, RESEARCH is
    artifact-only. Never let them look alike."""
    if mission.get("mission_kind") == "research":
        return "RESEARCH"
    return "BEAD" if mission.get("bead_id") else "BUILD"


def mission_teaser(missions, ascii_only=False):
    """One-line hint for the status bar; empty string when nothing to show."""
    if not missions:
        return ""
    rocket = "" if ascii_only else "\U0001f680 "
    return f"{rocket}{len(missions)} missions ready [M]"


def mission_status_message(missions, error):
    """Status line for the missions view — never hides a dropped repo source."""
    if error:
        base = str(error)
    elif missions:
        base = f"{len(missions)} missions ready"
    else:
        base = "no missions found — press r"
    if _DROPPED_REPOS:
        base += f" · unusable path: {', '.join(sorted(_DROPPED_REPOS))}"
    return base


def mission_regen_message(before_ids, missions, error):
    """Say what regenerating actually changed, not just how many came back.

    `[r]` already bypassed the cache and re-ran the whole sweep, so the reported
    bug — "R doesn't regen the deck" — was really "R regenerates and I cannot
    tell". Generation is deterministic over an unchanged backlog, so an
    identical deck is the correct answer and looked exactly like a dead key.
    Naming the outcome distinguishes a no-op from a failure, which is the
    difference between waiting and going to look for the real problem.

    "Unchanged" is decided by comparing both id sets, not by the absence of new
    ids. Testing only for new ones called any regeneration that gained nothing
    unchanged however much it *lost*: a deck going 3 -> 0 printed "same 0
    missions (backlog unchanged)" over an empty screen, and advised dismissing
    one of the nothing shown to make room. That is the exact no-op-versus-
    failure confusion this function exists to remove, in the one case where the
    operator most needs to know something went wrong.
    """
    if error:
        return mission_status_message(missions, error)
    before = {mission_id for mission_id in (before_ids or []) if mission_id}
    # Same falsy filter on both sides. `before` dropped id-less entries and this
    # did not, so a deck carrying them counted them new on every pass and could
    # never report itself unchanged.
    current = {m.get("id") for m in missions if m.get("id")}
    if not before:
        return mission_status_message(missions, error)
    if before == current:
        return (
            f"regenerated — same {len(missions)} missions "
            "(backlog unchanged; [d] dismisses one to make room)"
        )
    base = mission_status_message(missions, error)
    gained = len(current - before)
    lost = len(before - current)
    # Losses are reported first and always. A shrinking deck is the signal worth
    # acting on; a gain is self-evident from the rows now on screen.
    changes = [f"{lost} gone"] if lost else []
    if gained:
        changes.append(f"{gained} new")
    return f"{base} · {', '.join(changes)}" if changes else base


SHEP_TAB_Y = 3
SHEP_TABS = (
    ("agents", "AGENTS", "1"),
    ("beads", "BEADS", "2"),
    ("missions", "MISSIONS", "3"),
    ("logs", "LOGS", "4"),
)

# A tab label alone cannot answer the two questions an operator actually has —
# how many, and is this still true? Both live here rather than in each view so
# every tab reads the same whichever view is on screen. Layout and hit-testing
# both derive from this, so a badge can never shift a tab out from under a click.
_TAB_BADGES = {}  # key -> {"count": int, "at": float, "rising": bool}


def set_tab_badge(key, count, now=None):
    """Record a tab's live count and when it was refreshed."""
    at = time.time() if now is None else float(now)
    previous = _TAB_BADGES.get(key)
    rising = bool(previous and count > previous["count"])
    _TAB_BADGES[key] = {"count": int(count), "at": at, "rising": rising}


def compact_age(seconds):
    """Age in the fewest characters that stay unambiguous: 9s, 4m, 3h, 2d."""
    seconds = max(0, int(seconds))
    for limit, divisor, suffix in ((60, 1, "s"), (3600, 60, "m"), (86400, 3600, "h")):
        if seconds < limit:
            return f"{seconds // divisor}{suffix}"
    return f"{seconds // 86400}d"


def bead_age(iso_str, now=None):
    """Compact age since an ISO-8601 bead timestamp, or `?` when unreadable.

    Bead exports carry `Z`, `+00:00`, and fraction-less stamps interchangeably,
    and older rows carry none at all — so an unparseable value has to render as
    a visible `?` rather than a plausible-looking zero.
    """
    parsed = _t3_iso(iso_str.strip() if isinstance(iso_str, str) else iso_str)
    if parsed is None:
        return "?"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    now = time.time() if now is None else float(now)
    return compact_age(now - parsed.timestamp())


# A live badge changes width as it counts (9s -> 10s, 9 -> 10), and a tab that
# changes width moves every tab to its right — so the thing you are aiming at
# slides out from under the cursor mid-click. The badge therefore occupies an
# exact-width slot: padded when short, and trimmed age-first when long, because
# the count is what the operator is reading and the age is the hint.
TAB_BADGE_WIDTH = 10


def tab_badge_text(key, now=None, ascii_only=False):
    """`12^ 4m` — count, a rise marker, and how stale. Empty until first load."""
    badge = _TAB_BADGES.get(key)
    if not badge:
        return ""
    marker = ("^" if ascii_only else "▲") if badge["rising"] else ""
    now = time.time() if now is None else float(now)
    return f"{badge['count']}{marker} {compact_age(now - badge['at'])}"


def tab_badge_cell(key, now=None, ascii_only=False):
    """The badge in an exact-width slot, so a tab never changes size in place."""
    badge = _TAB_BADGES.get(key)
    if not badge:
        return ""
    text = tab_badge_text(key, now=now, ascii_only=ascii_only)
    if _text_columns(text) > TAB_BADGE_WIDTH:
        marker = ("^" if ascii_only else "▲") if badge["rising"] else ""
        text = f"{badge['count']}{marker}"
    while _text_columns(text) > TAB_BADGE_WIDTH:
        text = text[:-1]
    return text + " " * (TAB_BADGE_WIDTH - _text_columns(text))


def shep_tab_layout(width, ascii_only=False):
    """Return terminal-cell bounds for the top-level Shep views."""
    x = 0
    layout = []
    for key, label, shortcut in SHEP_TABS:
        text = f"[{shortcut}] {label}"
        badge = tab_badge_cell(key, ascii_only=ascii_only)
        if badge:
            text = f"{text} {badge}"
        tab_width = _text_columns(text) + 2
        if x + tab_width > max(0, width):
            break
        layout.append((key, text, x, tab_width))
        x += tab_width + 1
    return layout


def shep_tab_bar(width, active="agents", ascii_only=False):
    """Render a clickable tab row without making color carry meaning."""
    line = [" "] * max(0, width)
    for key, text, start, tab_width in shep_tab_layout(width, ascii_only):
        label = f" {text} "
        if key == active:
            label = f">{text}<"
        label = _fit_cell(label, tab_width, ascii_only)
        line[start:start + tab_width] = label[:tab_width]
    return "".join(line)


def mouse_tab_target(mouse_x, mouse_y, button_state, width, ascii_only=False):
    """Map a primary click in the tab row to one of the named Shep views."""
    left_click = button_state & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED)
    if mouse_y != SHEP_TAB_Y or not left_click:
        return None
    for key, _text, start, tab_width in shep_tab_layout(width, ascii_only):
        if start <= mouse_x < start + tab_width:
            return key
    return None


def discover_beads_repos():
    """Every repo under BEADS_ROOT holding a .beads/, TTL-cached.

    Bounded-depth and stops descending the moment it finds a .beads/, so it
    never walks into node_modules. The scan is ~0.6s and dominates a load; the
    read that follows is ~0.02s, hence the cache sits here and not on the rows.
    """
    now = time.time()
    if _BEADS_REPO_CACHE["repos"] and now - _BEADS_REPO_CACHE["at"] < BEADS_REPO_TTL:
        return list(_BEADS_REPO_CACHE["repos"])
    found = []

    def scan(directory, depth):
        if depth > BEADS_SCAN_DEPTH:
            return
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return
        subdirs = [e for e in entries if e.is_dir(follow_symlinks=False)]
        if any(e.name == ".beads" for e in subdirs):
            found.append(directory)
            return  # a repo's own subdirectories are never separate workspaces
        for entry in subdirs:
            if not entry.name.startswith("."):
                scan(entry.path, depth + 1)

    scan(str(BEADS_ROOT), 0)
    found.sort()
    _BEADS_REPO_CACHE.update(at=now, repos=found)
    return list(found)


OPEN_BEAD_STATUSES = ("open", "in_progress")


def _read_beads_jsonl(repo):
    """Every issue record in one repo's tracked JSONL export. -> (issues, error).

    Reads .beads/issues.jsonl rather than shelling out to `bd list`. Each `bd`
    invocation spins up an embedded Dolt database (~1s), so the fleet-wide view
    cost ~64s of subprocesses; the export is the same data as pure file I/O and
    was verified row-for-row identical against live `bd` on every curated repo.
    A malformed line is skipped rather than failing the repo — one bad row must
    not blank out the other 700 beads.

    Returns the raw records, closed ones included: the BEADS tab wants only what
    is open, but resolving a bead's blockers needs the status of beads that are
    already done.
    """
    path = Path(repo) / ".beads" / "issues.jsonl"
    issues = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    issue = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(issue, dict):
                    issues.append(issue)
    except FileNotFoundError:
        return [], None  # a repo with .beads/ but no export yet is not an error
    except OSError as exc:
        return [], f"{Path(repo).name}: {exc.strerror or exc}"
    return issues, None


def bead_is_usable(issue):
    """True when a record carries the fields every bead view and mission needs."""
    return bool(
        isinstance(issue.get("id"), str) and issue["id"].strip()
        and isinstance(issue.get("title"), str) and issue["title"].strip()
        and isinstance(issue.get("priority"), int)
        and not isinstance(issue["priority"], bool)
    )


def read_repo_beads(repo):
    """Open beads from one repo's tracked JSONL export. -> (rows, error).

    Each row carries ``repo_path`` as well as the display name: closing a bead
    means running ``bd`` against the workspace that owns it, and the bare repo
    name cannot be turned back into a path (two checkouts share one name).
    """
    issues, error = _read_beads_jsonl(repo)
    if error:
        return [], error
    name = Path(repo).name
    return [
        {
            "id": issue["id"],
            "title": issue["title"],
            "status": issue["status"],
            "priority": issue["priority"],
            "repo": name,
            "repo_path": str(repo),
            "created_at": issue.get("created_at") or "",
            "updated_at": issue.get("updated_at") or "",
        }
        for issue in issues
        if issue.get("status") in OPEN_BEAD_STATUSES and bead_is_usable(issue)
    ], None


def _remember_loaded_beads(beads, error):
    """Publish raw bead rows for a non-blocking BEADS tab refresh."""
    with _BEADS_VIEW_LOCK:
        _BEADS_VIEW_CACHE.update(
            beads=[dict(bead) for bead in beads],
            error=error,
            missions=None,
            prune={},
            triage_note="triage pending",
            at=time.time(),
        )


def _remember_beads_view(beads, error, missions, prune, triage_note):
    """Publish one complete, render-ready BEADS snapshot."""
    with _BEADS_VIEW_LOCK:
        _BEADS_VIEW_CACHE.update(
            beads=[dict(bead) for bead in beads],
            error=error,
            missions=[dict(mission) for mission in missions],
            prune=dict(prune),
            triage_note=str(triage_note or "triage unavailable"),
            at=time.time(),
        )


def _beads_view_snapshot():
    """Return the latest rows, even while a newer refresh is in flight."""
    with _BEADS_VIEW_LOCK:
        if _BEADS_VIEW_CACHE["beads"] is None:
            return None
        return {
            "beads": [dict(bead) for bead in _BEADS_VIEW_CACHE["beads"]],
            "error": _BEADS_VIEW_CACHE["error"],
            "missions": (
                None if _BEADS_VIEW_CACHE["missions"] is None
                else [dict(mission) for mission in _BEADS_VIEW_CACHE["missions"]]
            ),
            "prune": dict(_BEADS_VIEW_CACHE["prune"]),
            "triage_note": _BEADS_VIEW_CACHE["triage_note"],
            "at": _BEADS_VIEW_CACHE["at"],
        }


def load_beads(limit=0):
    """Open beads across every repo on disk; never creates or mutates issues.

    Beads is per-repo: `bd` resolves a .beads/ workspace by walking up from its
    cwd. Shep's own checkout has none, so an implicit-cwd `bd list` reported
    "no beads database found" no matter how much work was in flight — the tab
    was structurally empty. Read every discovered repo's export instead,
    tagging each row with its repo so one fleet-wide list stays unambiguous.
    limit=0 means unlimited: the point of the tab is to see everything.
    """
    repos = discover_beads_repos()
    if not repos:
        result = [], f"no repos with a .beads/ found under {BEADS_ROOT}"
        _remember_loaded_beads(*result)
        return result
    beads, errors = [], []
    for repo in repos:
        rows, error = read_repo_beads(repo)
        if error:
            errors.append(error)
            continue
        beads.extend(rows)
    # One repo cloned to two paths (linkgraph-static lives under both
    # linkgraph/ and web-dev/internal-sites/) is scanned twice, and both
    # copies carry the same repo name and bead ids — so the tab listed the
    # same bead twice with nothing to tell the rows apart. Keep the freshest
    # record per (repo, id); the stale checkout can only lose.
    newest = {}
    for bead in beads:
        key = (bead["repo"], bead["id"])
        if key not in newest or bead["updated_at"] > newest[key]["updated_at"]:
            newest[key] = bead
    beads = list(newest.values())
    # Priority first so the fleet-wide list leads with what actually blocks,
    # then repo/id so the order is stable between refreshes.
    beads.sort(key=lambda bead: (bead["priority"], bead["repo"], bead["id"]))
    detail = "; ".join(errors)[:160] or None
    set_tab_badge("beads", len(beads))
    if not beads:
        result = [], detail or "no open beads in any repo"
    else:
        result = (beads[:limit] if limit else beads), detail
    _remember_loaded_beads(beads, detail)
    return result


_BEADS_EXPORT_MTIME = {"at": None}


def beads_export_mtime(repos=None):
    """Newest mtime across every repo's bead export; 0.0 when none is readable.

    The staleness probe for the badge below — stat calls only, no parsing, so
    it is cheap enough to run on every fleet poll.
    """
    newest = 0.0
    for repo in discover_beads_repos() if repos is None else repos:
        try:
            newest = max(newest, (Path(repo) / ".beads" / "issues.jsonl").stat().st_mtime)
        except OSError:
            continue  # a repo with .beads/ but no export yet is not an error
    return newest


def refresh_beads_badge():
    """Keep the BEADS count live without re-parsing unchanged exports.

    Same contract as refresh_log_badge, and for the same reason: the badge was
    only ever set from inside load_beads(), which only runs when the operator
    opens the tab. So the one number saying how much tracked work is open — and
    how long since it moved — was blank on the AGENTS screen they actually
    watch, until they had gone and looked at BEADS at least once.
    """
    mtime = beads_export_mtime()
    if not mtime or _BEADS_EXPORT_MTIME["at"] == mtime:
        return
    _BEADS_EXPORT_MTIME["at"] = mtime
    load_beads()


# --- Bead missions (close the work that is already ready to close) -----------
#
# The deck's first question is "which open bead could I close right now?".
# mission-sense infers a next step from repo activity; a ready bead is work
# someone already decided mattered and wrote down, so it outranks an inference.
# These missions are field-for-field compatible with recommend.py's — launch.py
# validates goal_mode contracts strictly — with the bead id AS the mission id,
# so the branch, worktree and /goal condition all name the bead they close.
BEAD_BLOCKING_DEP_TYPES = {"blocks", "blocked-by"}
# Mirrors launch.py's GOAL_ROUTER_RUNTIME / REQUIRED_GOAL_SKILLS. Duplicated
# deliberately: shep shells out to those scripts and must not import them, and
# launch.py rejects a mission that disagrees rather than silently launching it.
# It reads launch.py's own env var, and that is the point: a pool-wide 429 on
# codex-gw kills every launch at /goal registration, and launch.py exposes this
# knob to route the fleet at a healthy gateway. Hardcoding the default here made
# shep the one thing that could not follow, so the knob turned a gateway outage
# into a rejected mission instead of the escape hatch it exists to be.
BEAD_GOAL_RUNTIME = os.environ.get("MISSION_GOAL_ROUTER_RUNTIME", "").strip() or "codex-gw"
BEAD_DELIVERY_SKILLS = [
    "mission-launch", "herdr", "goal-mode", "sdlc-protocol", "santa-method",
]
# Claude's native `/goal` rejects an argument over 4000 characters, and launch.py
# submits the goal condition, its protocol blocks, and this whole spec as one
# atomic first prompt — so the spec's budget is 4000 minus launch.py's fixed
# ~2,200. Over the line the goal never registers and the launcher times out
# *after* creating a bead, a worktree, and a pane, leaving stale artifacts and no
# agent. Set at 1700, not the ~1810 that just fits: measured against the real
# launcher the worst live mission composed to 3974 of 4000, and 26 characters of
# slack is not a margin — a one-line edit to launch.py's wrapper would silently
# break every launch again. Only the bead's own prose is trimmed to hold this
# line; the exit condition and the `bd close` requirement are what the mission is
# for, so they always survive.
BEAD_SPEC_MAX_CHARS = 1700


def bead_is_ready(issue, status_by_id):
    """True when no open bead still blocks this one.

    Only `blocks`/`blocked-by` edges gate work. A `parent-child` edge to an open
    epic is the normal shape of a child bead — counting it as a blocker would
    hide most of the backlog. An edge pointing at a bead we cannot see (another
    repo's export) is not treated as blocking either: an invisible edge must
    never silently remove real, launchable work from the deck.
    """
    for dep in issue.get("dependencies") or []:
        if not isinstance(dep, dict):
            continue
        if dep.get("type") not in BEAD_BLOCKING_DEP_TYPES:
            continue
        if status_by_id.get(dep.get("depends_on_id")) in OPEN_BEAD_STATUSES:
            return False
    return True


def repo_ready_beads(repo):
    """Open, unblocked beads in one repo, priority first. -> (issues, error).

    Returns whole issue records rather than the trimmed BEADS-tab rows: a
    mission has to brief its agent, and the description and acceptance criteria
    are the brief.
    """
    issues, error = _read_beads_jsonl(repo)
    if error:
        return [], error
    status_by_id = {
        issue.get("id"): issue.get("status") for issue in issues
        if isinstance(issue.get("id"), str)
    }
    ready = [
        issue for issue in issues
        if issue.get("status") in OPEN_BEAD_STATUSES
        and bead_is_usable(issue)
        and bead_is_ready(issue, status_by_id)
    ]
    ready.sort(key=lambda issue: (issue["priority"], issue["id"]))
    return ready, None


def bead_momentum(priority):
    """Deck score from bead priority: P0 leads, P4 still clears MISSION_MIN_SCORE.

    The view prints this number and the operator reads it as "how much does this
    matter" — a bead's priority is exactly that judgement, already made.
    """
    return max(40, 100 - 15 * max(0, int(priority)))


def repo_default_branch(repo):
    """The branch a mission on this repo should be cut from."""
    probe = _run(
        ["git", "-C", str(repo), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        timeout=5,
    )
    origin_head = probe.stdout.strip().rsplit("/", 1)[-1] if probe.returncode == 0 else ""
    # mission_base_branch holds the develop-over-main preference; reuse it so
    # there is one place that decides, not two that can drift.
    return mission_base_branch(repo, origin_head or "main")


def render_bead_launch_spec(mission, issue):
    """The spec body launch.py injects as the agent's first prompt.

    Section headings match recommend.py's because launch.py parses them —
    `exit_condition()` lifts the bullet under `### Exit Condition` and makes it
    the goal. The one substantive difference is that closing the bead is stated
    as part of the exit, not as a nicety: a mission that ships the code and
    leaves the bead open puts the deck straight back where it started.

    It carries no execution/safety contract: launch.py's goal-mode block already
    injects the skills list, the guarded builder lane, dual Santa review, the
    human merge/deploy/send approval, and the credential-safety protocol into
    this same prompt. Restating them only spent budget we do not have.
    """
    bead_id = issue["id"]

    def render(description, criteria):
        return (
            f"## Task: {mission['short_goal']}\n"
            f"### Context\n"
            f"- Repo/dir: {mission['cwd']}\n"
            f"- Base branch: {mission['default_branch']}\n"
            f"- Bead: {bead_id} (P{issue['priority']}, {issue.get('status')}) — "
            f"this mission exists to close it.\n"
            f"- Why now: {mission['rationale']}\n"
            f"- Bead description: {description or '(none recorded)'}\n"
            f"### Requirements\n"
            f"- Deliver everything {bead_id} asks for. Partially advancing it is a failure: "
            f"the bead must end CLOSED.\n"
            f"- No test.skip, no stubs, no new runtime deps without justification.\n"
            f"### Acceptance Criteria (DoD)\n"
            f"- {criteria or f'Everything {bead_id} describes is implemented and demonstrated.'}\n"
            f"- Tests/lint for the touched area pass.\n"
            f"- `bd close {bead_id}` is run WITH a close_reason naming the evidence. Run it from "
            f"the repo's primary checkout — the Beads database is not present in a worktree.\n"
            f"### Verification Commands\n"
            f"- Run the repo's test + lint for the changed scope (print the commands + results).\n"
            f"### Exit Condition\n"
            f"- bead {bead_id} is CLOSED with an evidence-bearing close_reason, MR open + CI green "
            f"+ review passed; PRINT the MR URL, the CI status, and the `bd close` output; "
            f"stop after 30 turns.\n"
            f"### Branch/PR\n"
            f"- feat/{mission['id']} off {mission['default_branch']}; conventional commits; "
            f"link bead {bead_id}."
        )

    # The bead's own prose is the only unbounded part, so it gets whatever the
    # fixed sections leave rather than a flat cap — a long bead description must
    # not be what pushes the goal over the limit (see BEAD_SPEC_MAX_CHARS).
    description = " ".join((issue.get("description") or "").split())
    criteria = " ".join(str(issue.get("acceptance_criteria") or "").split())
    room = max(0, BEAD_SPEC_MAX_CHARS - len(render("", "")))
    criteria = criteria[: room // 3]
    return render(description[: room - len(criteria)], criteria)


def bead_mission(issue, repo, default_branch=None, picked_because=""):
    """One launchable mission whose entire objective is closing `issue`.

    ``picked_because`` is the triage model's one-line reason for putting this
    bead ahead of the rest. It rides in the rationale the operator reads before
    launching — the ranking is only trustworthy if you can see why it ranked.
    """
    bead_id = issue["id"]
    dependents = issue.get("dependent_count") or 0
    waiting = f" and {dependents} bead(s) wait on it" if dependents else ""
    rationale = f"Ready P{issue['priority']} bead — nothing blocks it{waiting}."
    if picked_because:
        rationale = f"{picked_because.rstrip('.')}. {rationale}"
    mission = {
        "id": bead_id,
        "bead_id": bead_id,
        "project_name": Path(repo).name,
        "cwd": str(repo),
        "default_branch": default_branch or repo_default_branch(repo),
        "momentum_score": bead_momentum(issue["priority"]),
        "short_goal": f"Close {bead_id}: {issue['title']}"[:120],
        "next_step": f"[{bead_id}] {issue['title']}",
        "rationale": rationale,
        "needs_research": False,
        "goal_mode": True,
        "goal_runtime": BEAD_GOAL_RUNTIME,
        # launch.py requires the exact mission id inside the condition.
        "goal_condition": (
            f"bead {bead_id} is closed: everything it describes is implemented, tests and "
            f"lint pass for the touched scope, an MR is open with green CI, two independent "
            f"Santa reviewers PASS, and `bd close {bead_id}` has been run with a close_reason "
            f"naming that evidence, while merge, deploy, and send remain human-approved"
        ),
        "santa_required": True,
        "required_skills": list(BEAD_DELIVERY_SKILLS),
        "evidence": [
            f"bead {bead_id} P{issue['priority']} {issue.get('status')}",
            f"{dependents} dependent bead(s)",
            "no open blockers",
        ],
    }
    mission["launch_spec"] = render_bead_launch_spec(mission, issue)
    return mission


def bead_missions(top=None, rank=None, per_project=MISSION_DECK_PER_PROJECT):
    """The ready beads worth closing next, as launchable missions. -> (missions, error).

    Restricted to MISSION_REPOS_FILE for exactly the reason build missions are:
    these write code autonomously and the repos file is the only guard (see the
    SAFETY INVARIANT above). The BEADS *tab* still reads the whole fleet —
    widening what is read is not widening what may be launched.

    ``rank`` is the optional model verdict from bead_triage.work_rank(): a
    {bead_id: (position, reason)} map that promotes the beads a model judged
    worth starting now and supplies the rationale the operator reads. It only
    ever reorders and annotates candidates this function already produced, so a
    hallucinated id cannot introduce a mission and a dead provider lane costs
    the ordering, not the deck.
    """
    repos, dropped = launchable_repos(MISSION_REPOS_FILE)
    _DROPPED_REPOS.update(dropped)
    if not repos:
        return [], f"no launchable git repos in {MISSION_REPOS_FILE.name}"
    candidates, errors = [], []
    for repo in repos:
        ready, error = repo_ready_beads(repo)
        if error:
            errors.append(error)
            continue
        candidates += [(issue, repo) for issue in ready]
    # Ranked beads first in the model's own order, then everything else by
    # priority and repo/id so the tail of the deck is stable between
    # regenerations rather than reshuffling on every refresh.
    rank = rank or {}
    candidates.sort(
        key=lambda pair: (
            rank.get(pair[0]["id"], (len(rank), ""))[0],
            pair[0]["priority"],
            Path(pair[1]).name,
            pair[0]["id"],
        )
    )
    # Dismissals come off before the cap, not after the deck is built. Filtering
    # downstream deleted slots instead of freeing them: with one repo capped at
    # three, dismissing those three returned the same three next pass (nothing
    # upstream changed), they were removed again, and the bead source contributed
    # nothing for the whole dismissal window while the rest of that backlog sat
    # unoffered. The [d] message promises "press [r] to refill"; this is what
    # makes that true.
    dismissed = read_dismissed_missions()
    candidates = [pair for pair in candidates if pair[0]["id"] not in dismissed]
    # Diversify before slicing, never after. The sort above is global across
    # repos on purpose — a P0 somewhere else should outrank a P2 here — but that
    # same globality is what let one busy backlog take every slot: five ready
    # bug-hunter beads filled the whole deck and, because the build and research
    # top-ups only run when beads leave room, silently suppressed both other
    # sources for days. Capping after the slice would not help; by then the
    # other repos are already gone.
    # per_project comes from the caller, because the two consumers want
    # different things and one constant could not serve both. The MISSIONS deck
    # wants variety across repos; the BEADS strip is a shortlist of one backlog
    # and a 3-per-project cap silently made its own BEAD_STRIP_TOP=5 unreachable
    # on a single-repo fleet. `top=None` also used to mean "everything" and the
    # cap quietly overrode that, which changed what callers asking for all ready
    # beads actually received.
    candidates = cap_per_project(
        candidates,
        per_project=per_project,
        top=top,
        key=lambda pair: Path(pair[1]).name,
    )
    # One git probe per repo, not per bead: repo_default_branch shells out.
    branches = {repo: repo_default_branch(repo) for _issue, repo in candidates}
    missions = [
        bead_mission(issue, repo, branches[repo], picked_because=rank.get(issue["id"], (0, ""))[1])
        for issue, repo in candidates
    ]
    detail = "; ".join(errors)[:160] or None
    if not missions and not detail:
        detail = "no ready beads in the delivery repos"
    return missions, detail


# How many bead missions the BEADS tab offers above the backlog. Five is what
# fits above the list without pushing the beads themselves off a normal
# terminal. It used to alias MISSION_DECK_TOP so the two views agreed on "the
# shortlist"; that tie is now broken deliberately. The MISSIONS deck scrolls and
# wants supply, this strip does not scroll and wants to stay short, so one
# constant could not serve both — raising the deck to 12 through this alias
# would have pushed the backlog itself off the BEADS tab.
BEAD_STRIP_TOP = 5


def load_bead_triage(beads, force=False):
    """The model's verdict on the whole open backlog. -> (verdict, error).

    Cache-backed (see shep_bead_triage.TRIAGE_TTL), so this is free on every
    call but the first of each half-hour. ``force`` pays for a fresh call.
    """
    repos, _dropped = launchable_repos(MISSION_REPOS_FILE)
    return bead_triage.load_triage(beads, repos, force=force)


def bead_triage_message(verdict, error, missions, prune):
    """One line saying who ranked the backlog, how fresh it is, and what it said.

    Reports the model's own pick count separately from the strip size. They
    differ whenever the model named fewer than BEAD_STRIP_TOP beads and priority
    order filled the rest, and conflating them would credit the model for a
    ranking it did not make.
    """
    if verdict is None:
        return f"triage unavailable ({error or 'no verdict'}) — priority order"
    age = bead_triage.triage_age(verdict)
    when = f"{int(age // 60)}m old" if age is not None else "cached"
    stale = " · press r to refresh" if age is not None and age >= bead_triage.TRIAGE_TTL else ""
    picked = len(bead_triage.work_rank(verdict))
    return (
        f"triage: {verdict.get('lane') or 'cached'} · {when} · "
        f"{len(missions)} to run ({picked} model-picked) · {len(prune)} to prune{stale}"
    )


def sort_beads_for_triage(beads, prune):
    """Backlog order with the prunable beads pulled to the front.

    A verdict you have to scroll 660 rows to find is not one anyone acts on.
    Within each group the existing priority/repo/id order is preserved, so the
    list below the prune block reads exactly as it always has.
    """
    return sorted(beads, key=lambda bead: bead["id"] not in prune)


def bead_strip(beads, force=False):
    """(missions, prune_reasons, message) for the BEADS tab's mission strip.

    Cheap enough to call on tab entry: bead_missions reads two JSONL exports and
    probes one branch per delivery repo. The only slow part is the triage model
    call, and that only runs when the cached verdict has expired or ``force``.
    """
    verdict, error = load_bead_triage(beads, force=force)
    missions, mission_error = bead_missions(
        BEAD_STRIP_TOP,
        rank=bead_triage.work_rank(verdict),
        # The strip is "the top of this backlog", not a varied deck, so it takes
        # its whole length from one repo if that is where the work is.
        per_project=BEAD_STRIP_TOP,
    )
    # A prune verdict outlives its bead: the model saw the backlog as it was up
    # to half an hour ago, and a bead closed since then must not still be
    # offered up for closing.
    open_ids = {bead["id"] for bead in beads}
    prune = {
        bead_id: reason
        for bead_id, reason in bead_triage.prune_reasons(verdict).items()
        if bead_id in open_ids
    }
    message = bead_triage_message(verdict, error, missions, prune)
    if mission_error:
        message = f"{message} · {mission_error}"
    return missions, prune, message


# `bd` boots an embedded Dolt database per invocation (~1s), and closing runs
# two of them, so the 8s default in _run is not enough headroom.
BEAD_CLOSE_TIMEOUT = 60
BEAD_CLOSE_PREFIX = "shep triage"


def bead_close_reason(reason):
    """The close_reason written to the bead, naming who decided and why.

    Prefixed so anyone reading the bead later can tell a triage prune from work
    that was actually done — a bare "too vague to act on" in the history looks
    like a human closed it after investigating.
    """
    text = " ".join(str(reason or "").split()) or "flagged as prunable by triage"
    return f"{BEAD_CLOSE_PREFIX}: {text}"[:280]


def close_bead(bead, reason):
    """Close one bead as pruned and refresh the export the tab reads. -> (ok, detail).

    Two commands, both required. `bd close` writes the database, but it does
    NOT rewrite `.beads/issues.jsonl` — and that export is the only thing the
    BEADS tab reads (see _read_beads_jsonl). Without the second command the
    bead reappears as open on the next refresh, so the keystroke would look
    broken while having actually worked.

    `bd -C` rather than a cwd: the Beads database lives in the primary
    checkout, never in a worktree, and -C is how bd is pointed at one.
    """
    repo = bead.get("repo_path")
    bead_id = bead.get("id")
    if not repo or not bead_id:
        return False, "this bead has no repo on disk to close it in"
    closed = _run(
        ["bd", "-C", repo, "close", bead_id, "--reason", bead_close_reason(reason)],
        timeout=BEAD_CLOSE_TIMEOUT,
    )
    if closed.returncode != 0:
        detail = (closed.stderr or closed.stdout).strip()[:180]
        return False, detail or f"bd close exited {closed.returncode}"
    export = _run(
        ["bd", "-C", repo, "export", "-o", str(Path(repo) / ".beads" / "issues.jsonl")],
        timeout=BEAD_CLOSE_TIMEOUT,
    )
    if export.returncode != 0:
        # The close itself stuck, so this is a warning, not a failure — say
        # exactly that, or the operator retries a close that already happened.
        return True, f"closed {bead_id}, but the export did not refresh — it will look open until `bd export` runs"
    return True, f"closed {bead_id} · export refreshed (commit it)"
# --- AFK (away) mode ---------------------------------------------------------
#
# "I am leaving" as a first-class operation. The deck already answers what is
# worth doing; away mode asks which of it survives four hours unwatched, and
# launches a batch into a runtime the operator's phone can reach.
#
# Ranking lives in shep_afk (pure, unit-tested). This half owns only the I/O the
# lenses need and the batch loop, because a scoring bug must not be able to take
# the TUI down and a launch bug must not be hidden inside a scoring function.
AFK_TOP = 10  # the review deck the operator reads before leaving
AFK_DEFAULT_COUNT = 5
AFK_MAX_COUNT = 10
# The pane command for away launches. Happy wraps Claude Code and mirrors the
# session to the phone; because launch.py passes this straight to herdr as the
# pane command, the mission stays an ordinary herdr pane and Shep's stall
# detection, auto-reap and nudge engine keep working on it unchanged.
#
# Resolved to the shipped shim's absolute path when the bare name is not on
# PATH. herdr starts the pane in a fresh shell that has no idea about this
# repo's bin/, so a bare "happy-cc" there fails to exec — AFTER launch.py has
# already created the bead and the worktree. An absolute path needs no install
# step and cannot be defeated by a login shell that orders PATH differently.
def _resolve_afk_runtime():
    override = os.environ.get("SHEP_AFK_RUNTIME", "").strip()
    if override:
        return override
    if shutil.which("happy-cc"):
        return "happy-cc"
    shipped = Path(__file__).resolve().parents[1] / "bin" / "happy-cc"
    return str(shipped) if shipped.exists() else "happy-cc"


AFK_RUNTIME = _resolve_afk_runtime()
# Three launches failing in a row is a systemic problem (gateway down, herdr
# wedged, disk full), not three unlucky missions. Walking away while a loop
# keeps creating worktrees and beads for launches that cannot start is the
# expensive version of this mistake.
AFK_MAX_CONSECUTIVE_FAILURES = 3
# One line per away batch: what was ranked, what launched, what was held back.
AFK_RECEIPTS = Path(
    os.environ.get("SHEP_AFK_RECEIPTS", str(MISSION_ENGINE_DIR / "afk-batches.jsonl"))
).expanduser()
# Files that prove a repo can verify its own work. The exit condition requires
# printing test results, so a repo with none of these will loop until it runs
# out of turns rather than finishing.
VERIFIER_MARKERS = (
    "pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg", "noxfile.py",
    "package.json", "Makefile", "justfile", "Cargo.toml", "go.mod",
)


def repo_has_verifier(repo):
    """True when the repo carries something that can run its own tests/lint."""
    root = Path(repo)
    return any((root / marker).exists() for marker in VERIFIER_MARKERS)


def afk_repo_pool(repos_mode="all"):
    """The repos away mode may draw candidates from. -> (repos, error).

    SAFETY: ``delivery`` is the historical guard (see the SAFETY INVARIANT at
    the top of this file) — MISSION_REPOS_FILE is the only thing keeping
    autonomous code-writing missions off product and personal repos. ``all``
    deliberately steps outside it at the operator's explicit instruction
    (2026-08-06) and is the default. Away-mode panes run unattended, so this
    knob is the difference between a wide and a narrow blast radius: keep it,
    and do not change the default without asking.
    """
    if repos_mode == "delivery":
        repos, dropped = launchable_repos(MISSION_REPOS_FILE)
        _DROPPED_REPOS.update(dropped)
        if not repos:
            return [], f"no launchable git repos in {MISSION_REPOS_FILE.name}"
        return repos, None
    repos = discover_beads_repos()
    if not repos:
        return [], f"no repos with a .beads/ found under {BEADS_ROOT}"
    return repos, None


def afk_candidates(repos_mode="all"):
    """Every mission away mode could launch, with the facts its lenses need.

    -> (candidates, error). Each candidate is the ``{mission, issue, facts}``
    shape shep_afk.rank expects. Ready beads come first because a bead is work
    someone already wrote down; the cached mission deck tops the pool up with
    inferred build work, which the lenses then score lower for exactly that
    reason.
    """
    repos, error = afk_repo_pool(repos_mode)
    if error:
        return [], error

    candidates, errors = [], []
    for repo in repos:
        ready, read_error = repo_ready_beads(repo)
        if read_error:
            errors.append(read_error)
            continue
        if not ready:
            continue
        # One git probe and one verifier probe per repo, never per bead.
        branch = repo_default_branch(repo)
        has_verifier = repo_has_verifier(repo)
        for issue in ready:
            mission = bead_mission(issue, repo, branch)
            candidates.append({
                "mission": mission,
                "issue": issue,
                "facts": {
                    "has_verifier": has_verifier,
                    "worktree_ok": not mission_worktree_exists(repo, mission["id"]),
                },
            })

    # Cache-only: generating a fresh deck walks bd and git for every repo, and
    # the operator is holding their coat. A stale top-up is fine — the beads
    # above are read live and are what away mode is actually for.
    deck_missions, _deck_error = load_mission_deck(force=False, allow_generate=False)
    known = {candidate["mission"]["id"] for candidate in candidates}
    for mission in deck_missions or []:
        if mission.get("id") in known:
            continue
        cwd = mission.get("cwd") or ""
        candidates.append({
            "mission": mission,
            "issue": None,
            "facts": {
                "has_verifier": bool(cwd) and repo_has_verifier(cwd),
                "worktree_ok": bool(cwd)
                and not mission_worktree_exists(cwd, mission.get("id") or ""),
            },
        })

    detail = "; ".join(errors)[:160] or None
    if not candidates and not detail:
        detail = "no ready beads and no cached deck missions"
    return candidates, detail


def afk_deck(repos_mode="all", top=AFK_TOP, now=None):
    """The away-mode review deck. -> (deck, error).

    Also refreshes ``_AFK_MISSIONS`` so a launch can use the record ranking
    already built instead of re-deriving it — and so a mission that has since
    left the pool is refused rather than launched from a stale copy.
    """
    candidates, error = afk_candidates(repos_mode)
    try:
        deck = afk.rank(candidates, top=top, now=now)
    except afk.WeightsError as exc:
        return None, str(exc)
    _AFK_MISSIONS.clear()
    for candidate in candidates:
        mission = candidate.get("mission") or {}
        if mission.get("id"):
            _AFK_MISSIONS[mission["id"]] = mission
    deck["repos_mode"] = repos_mode
    return deck, error


def happy_ready(runtime=None):
    """Is Happy installed, its daemon up, and the pane command runnable?

    -> (ready, message). Checked before a batch, never after: a half-launched
    batch the phone cannot reach is the worst outcome of away mode, because the
    operator only finds out once they are no longer at the keyboard.

    The pane command is checked as well as ``happy`` itself. herdr execs the
    runtime in a fresh shell, so a shim that this process can see but that shell
    cannot is a launch that dies after the bead and worktree already exist.
    """
    runtime = runtime or AFK_RUNTIME
    if not shutil.which("happy"):
        return False, "happy is not on PATH — the phone could not reach these sessions"
    if not (shutil.which(runtime) or os.access(runtime, os.X_OK)):
        return False, (
            f"the away runtime {runtime!r} is not executable — herdr could not "
            "start these panes"
        )
    proc = _run(["happy", "daemon", "status"], timeout=15)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, f"happy daemon is not healthy: {detail[-1] if detail else 'no status'}"
    return True, "happy daemon is up"


def afk_launch(deck, ids, dry_run=False, runtime=None):
    """Launch a batch of away missions. -> (results, error).

    Sequential, not parallel: each launch creates a worktree and a bead and then
    waits on a herdr pane, and three of those racing is how you get a half-built
    worktree adopted by the wrong mission.
    """
    runtime = runtime or AFK_RUNTIME
    rows = {row["id"]: row for row in deck.get("missions", [])}
    chosen = [mission_id for mission_id in ids if mission_id in rows]
    if not chosen:
        return [], "nothing selected to launch"

    if not dry_run:
        ready, message = happy_ready(runtime)
        if not ready:
            return [], message

    try:
        if not dry_run:
            # launch.py reads MISSION_GOAL_ROUTER_RUNTIME at ITS import; _run
            # passes env=None so the subprocess inherits ours. The staged
            # mission is restamped too (see launch_mission_by_id) because Shep's
            # own BEAD_GOAL_RUNTIME was frozen long before this point.
            _previous_runtime = os.environ.get("MISSION_GOAL_ROUTER_RUNTIME")
            os.environ["MISSION_GOAL_ROUTER_RUNTIME"] = runtime
        results, error = _afk_launch_each(chosen, runtime, dry_run)
    finally:
        if not dry_run:
            # Restoring is not tidiness, it is correctness: a normal Enter/l
            # launch later in this same session still stamps the frozen
            # BEAD_GOAL_RUNTIME on its mission, so a leftover away runtime here
            # makes launch.py's validate_goal_contract reject every one of them
            # for the rest of the session.
            if _previous_runtime is None:
                os.environ.pop("MISSION_GOAL_ROUTER_RUNTIME", None)
            else:
                os.environ["MISSION_GOAL_ROUTER_RUNTIME"] = _previous_runtime

    if not dry_run:
        record_afk_batch(deck, results, runtime)
    return results, error


def _afk_launch_each(chosen, runtime, dry_run):
    """The batch loop itself. -> (results, error)."""
    results, consecutive = [], 0
    for mission_id in chosen:
        candidate = _AFK_MISSIONS.get(mission_id)
        if candidate is None:
            results.append({"id": mission_id, "ok": False,
                            "detail": "mission is no longer in the ranked pool"})
            consecutive += 1
        elif dry_run:
            results.append({"id": mission_id, "ok": True,
                            "detail": f"would launch under {runtime}", "dry_run": True})
            consecutive = 0
        else:
            ok, detail = launch_mission_by_id(
                mission_id, mission=candidate, goal_runtime=runtime
            )
            results.append({"id": mission_id, "ok": ok, "detail": detail})
            consecutive = 0 if ok else consecutive + 1

        if consecutive >= AFK_MAX_CONSECUTIVE_FAILURES:
            return results, (
                f"stopped after {consecutive} consecutive failures — "
                "this looks systemic, not per-mission"
            )
    return results, None


def record_afk_batch(deck, results, runtime):
    """File one receipt per away batch. Leaving is exactly when it matters.

    Deliberately its own file rather than the action ledger: that ledger has a
    closed, validated vocabulary (nudge/reap/answer) which its loader, the LOGS
    view, and the golden baseline all depend on. Prising it open for one receipt
    costs more than it buys.
    """
    launched = [row["id"] for row in results if row.get("ok")]
    failed = [row["id"] for row in results if not row.get("ok")]
    receipt = {
        "at": time.time(),
        "runtime": runtime,
        "repos_mode": deck.get("repos_mode"),
        "ranked": deck.get("count"),
        "launched": launched,
        "failed": failed,
        "excluded": [row["id"] for row in deck.get("excluded") or []],
    }
    try:
        AFK_RECEIPTS.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(AFK_RECEIPTS, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    except OSError:
        # A receipt must never be the thing that stops a launch that already
        # succeeded; the operator has left and the panes are the real record.
        pass


#: Full mission records for the current deck, so a launch does not have to
#: re-derive what ranking already built. Keyed by mission id.
_AFK_MISSIONS = {}


def afk_run(repos_mode="all", go=False, count=AFK_DEFAULT_COUNT, ids=None,
            dry_run=False, as_json=False):
    """The `--afk` entry point. -> exit status."""
    deck, error = afk_deck(repos_mode)
    if deck is None:
        print(f"afk: {error}", file=sys.stderr)
        return 1

    if not go and not ids:
        print(json.dumps(deck, indent=2, sort_keys=True) if as_json
              else render_afk_deck(deck, error))
        return 0

    selected, refusal = afk.selection(deck, count=min(count, AFK_MAX_COUNT), ids=ids)
    if refusal:
        print(f"afk: {refusal}", file=sys.stderr)
        if not selected:
            return 1
    results, launch_error = afk_launch(deck, selected, dry_run=dry_run)
    if as_json:
        print(json.dumps({"results": results, "error": launch_error}, indent=2))
    else:
        for row in results:
            mark = "ok " if row.get("ok") else "FAIL"
            print(f"{mark} {row['id']}: {row['detail']}")
        if launch_error:
            print(f"afk: {launch_error}", file=sys.stderr)
    return 0 if results and all(row.get("ok") for row in results) else 1


def render_afk_deck(deck, error=None):
    """The review deck as text: what would run, and what would not, and why."""
    lines = [
        f"AFK deck — {deck.get('count', 0)} safe to leave running "
        f"(repos={deck.get('repos_mode')})",
        "",
    ]
    for index, row in enumerate(deck.get("missions", []), start=1):
        lines.append(f"{index:2}. [{row['blended']:5.1f}] {row['short_goal']}")
        lines.append(f"      {row['project_name']} · {row['cwd']}")
        for lens in afk.LENSES:
            value, reason = row["lenses"][lens]
            lines.append(f"      {lens:<9} {value:5.1f}  {reason}")
        lines.append("")
    excluded = deck.get("excluded") or []
    if excluded:
        lines.append(f"not safe to leave running ({len(excluded)}):")
        for row in excluded:
            lines.append(f"  [{row['afk_fit']:5.1f}] {row['id']}: {row['reason']}")
        lines.append("")
    if error:
        lines.append(f"note: {error}")
    return "\n".join(lines)


def afk_view_lines(deck, error=None):
    """The away deck as display rows. Shared with the CLI's text rendering."""
    return render_afk_deck(deck, error).splitlines()


def run_afk_view(stdscr, ascii_only, missions, error, message):
    """The away-mode deck: what would run unattended, and why. -> (missions, error, message).

    Read-only until the operator presses A and then confirms. Walking away is a
    decision worth two keystrokes; every other view here launches one mission at
    a time, and this one launches several at once.
    """
    _paint_mission_status(stdscr, "ranking missions for unattended work…", ascii_only)
    deck, deck_error = afk_deck()
    if deck is None:
        return missions, error, f"afk unavailable: {deck_error}"

    lines = afk_view_lines(deck, deck_error)
    top = 0
    while True:
        h, w = stdscr.getmaxyx()
        stdscr.erase()
        _paint_shep_tabs(stdscr, "missions", ascii_only)
        visible = max(1, h - SHEP_TAB_Y - 4)
        top = max(0, min(top, max(0, len(lines) - visible)))
        for offset, line in enumerate(lines[top : top + visible]):
            safe_addstr(
                stdscr, SHEP_TAB_Y + 2 + offset, 0,
                _clip_to_columns(line, w - 1), max_width=w - 1,
            )
        safe_addstr(
            stdscr, h - 1, 0,
            f"[A] launch top {min(AFK_DEFAULT_COUNT, deck['count'])} under {AFK_RUNTIME} · "
            "j/k scroll · q back",
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        safe_refresh(stdscr)

        key = stdscr.getch()
        if key in (ord("q"), 27):
            return missions, error, message
        if key in (ord("j"), curses.KEY_DOWN):
            top += 1
        elif key in (ord("k"), curses.KEY_UP):
            top -= 1
        elif key == ord("A") and deck["count"]:
            count = min(AFK_DEFAULT_COUNT, deck["count"])
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0,
                f"Launch {count} missions unattended (each WRITES CODE on its own "
                f"branch)? [Y] launch / other=cancel",
                curses.A_BOLD | _ui_pair(1), max_width=w - 1,
            )
            safe_refresh(stdscr)
            if blocking_getch(stdscr) != ord("Y"):
                return missions, error, "away batch cancelled"
            _paint_mission_status(
                stdscr, f"launching {count} missions under {AFK_RUNTIME}…", ascii_only,
            )
            selected_ids, refusal = afk.selection(deck, count=count)
            results, launch_error = afk_launch(deck, selected_ids)
            launched = sum(1 for row in results if row.get("ok"))
            note = launch_error or refusal or ""
            return missions, error, (
                f"away batch: {launched}/{len(results)} launched"
                + (f" · {note}" if note else "")
            )


def _paint_shep_tabs(stdscr, active, ascii_only):
    """Draw the shared tab row used by every top-level Shep view."""
    _h, w = stdscr.getmaxyx()
    safe_addstr(
        stdscr,
        SHEP_TAB_Y,
        0,
        shep_tab_bar(w - 1, active, ascii_only),
        curses.A_BOLD | _ui_pair(4),
        max_width=w - 1,
    )


MISSION_ROW_HEIGHT = 4  # headline + next: + why: + spacer


def mission_scroll_window(selected, count, height):
    """(top, visible) so the selected mission is always actually on screen.

    Without this the list silently truncates at the bottom while `selected`
    still ranges over every mission — j/k parks the cursor on an invisible row
    and Enter launches a mission the operator cannot see.
    """
    content_height = height - (SHEP_TAB_Y + 2) - 3
    visible = max(1, content_height // MISSION_ROW_HEIGHT)
    if count <= visible or selected < visible:
        return 0, visible
    return min(selected - visible + 1, max(0, count - visible)), visible


def mission_content_bottom(height):
    """Return the exclusive row bound while reserving a tiny headline slot."""
    first_row = SHEP_TAB_Y + 2
    return max(height - 3, first_row + 1)


def _paint_mission_status(stdscr, text, ascii_only):
    """One frame showing `text` — so a slow deck load never looks like a freeze."""
    stdscr.erase()
    _h, w = stdscr.getmaxyx()
    safe_addstr(
        stdscr, 0, 0,
        panel_rule(f"{commander_m_brand()} · SUGGESTED MISSIONS", w - 1, ascii_only),
        curses.A_BOLD | _ui_pair(4), max_width=w - 1,
    )
    safe_addstr(stdscr, 2, 0, text, curses.A_BOLD, max_width=w - 1)
    safe_refresh(stdscr)


def _paint_beads_status(stdscr, text, ascii_only):
    """One frame showing `text` — so a slow fleet scan never looks like a freeze."""
    stdscr.erase()
    _h, w = stdscr.getmaxyx()
    safe_addstr(
        stdscr, 0, 0,
        panel_rule(f"{commander_m_brand()} · BEADS", w - 1, ascii_only),
        curses.A_BOLD | _ui_pair(4), max_width=w - 1,
    )
    safe_addstr(stdscr, 2, 0, text, curses.A_BOLD, max_width=w - 1)
    safe_refresh(stdscr)


def _beads_message(beads, error, now=None):
    repos = len({bead["repo"] for bead in beads})
    if error:
        return error
    message = f"{len(beads)} open beads across {repos} repos"
    newest = max((bead.get("updated_at") or "" for bead in beads), default="")
    age = bead_age(newest, now=now)
    return message if age == "?" else f"{message} · newest update {age} ago"


def bead_mission_row(index, mission, running=False):
    """One strip line: rank, score, repo, and why this bead was picked."""
    reason = mission.get("rationale") or ""
    state = "RUNNING " if running else ""
    return (
        f"{index + 1}. [{mission.get('momentum_score', 0):>3}] {state}"
        f"{mission.get('project_name') or '?'} · {mission.get('short_goal') or '(no goal)'}"
        f"{f'  ← {reason}' if reason else ''}"
    )


def bead_row(bead, prune_reason=""):
    """One backlog line, carrying the triage verdict when there is one."""
    # Dates sit ahead of the title: a 700-row backlog truncates titles first at
    # narrow widths, and "how stale is this?" is the column that decides whether
    # a row is worth opening at all.
    line = (
        f"{bead.get('repo', '?')} · {bead['id']} · {bead['status']} · "
        f"P{bead['priority']} · c:{bead_age(bead.get('created_at'))} "
        f"u:{bead_age(bead.get('updated_at'))} · {bead['title']}"
    )
    return f"{line}  · PRUNE: {prune_reason}" if prune_reason else line
def beads_status_line(message, ascii_only=False, now=None):
    """The BEADS status line with a LIVE scan age appended.

    Computed per frame rather than baked into `message` at load: the message is
    rendered every frame but only rebuilt on load or [r], so an age folded into
    it would freeze at "0s" and read as permanently fresh — worse than saying
    nothing. Inside the view nothing rescans on its own, so this climbing number
    is the honest answer to "how old is this list?".
    """
    badge = _TAB_BADGES.get("beads")
    if not badge:
        return message
    now = time.time() if now is None else float(now)
    separator = " | " if ascii_only else " · "
    return f"{message}{separator}scanned {compact_age(now - badge['at'])} ago"


def _build_beads_view(force=False):
    """Load and prepare the BEADS view without touching curses."""
    beads, error = load_beads()
    try:
        missions, prune, triage_note = bead_strip(beads, force=force)
    except Exception as exc:  # noqa: BLE001 - preserve rows when triage fails
        return (
            beads,
            f"refresh failed: {str(exc)[:160]}",
            [],
            {},
            "triage unavailable",
        )
    beads = sort_beads_for_triage(beads, prune)
    return beads, error, missions, prune, triage_note


def run_beads_view(stdscr, ascii_only):
    """Open Beads state, led by the missions the triage model says to run next.

    Two focusable lists in one view: the mission strip on top (Enter launches
    the selected one straight into an isolated worktree) and the fleet backlog
    below, where beads the model judged prunable carry their reason inline.
    ``tab`` moves focus, ``r`` re-scans and re-asks the model.
    """
    selected = 0
    mission_selected = 0
    focus = "missions"
    cached = _beads_view_snapshot()
    if cached is None:
        beads, error, missions, prune = [], None, [], {}
        triage_note = "loading…"
        message = "loading beads…"
    else:
        beads = cached["beads"]
        error = cached["error"]
        missions = cached["missions"] or []
        prune = cached["prune"]
        triage_note = cached["triage_note"]
        message = _beads_message(beads, error)

    # Repo discovery and triage can both be slow. They must never run between a
    # tab click and the next getch(): the operator should be able to leave this
    # view immediately, even when a provider or a checkout is wedged.
    completed = []
    worker = None
    loading = False
    force_pending = False
    return_after_frame = None

    def request_load(force=False):
        nonlocal worker, loading, message, triage_note, force_pending
        if worker is not None and worker.is_alive():
            if force:
                # Do not interrupt the current scan, but remember that [r]
                # requested a genuinely fresh triage once it completes.
                force_pending = True
                _BEADS_REPO_CACHE["at"] = 0.0
            message = "refresh already in progress…"
            return
        if force:
            _BEADS_REPO_CACHE["at"] = 0.0
        loading = True
        message = "refreshing beads…" if force else "loading beads…"
        triage_note = "triage pending"

        def load():
            try:
                result = _build_beads_view(force=force)
            except Exception as exc:  # noqa: BLE001 - a tab must never tear down curses
                previous = _beads_view_snapshot()
                if previous is None:
                    result = ([], f"beads unavailable: {str(exc)[:160]}", [], {}, "triage unavailable")
                else:
                    result = (
                        previous["beads"],
                        f"refresh failed: {str(exc)[:160]}",
                        previous["missions"] or [],
                        previous["prune"],
                        previous["triage_note"],
                    )
            _remember_beads_view(*result)
            completed.append(result)

        worker = threading.Thread(target=load, daemon=True, name="shep-beads-load")
        worker.start()

    # Paint before starting the worker so a cold scan has an honest visible
    # state. The normal frame below immediately replaces this with cached rows
    # when a prior scan exists.
    _paint_beads_status(
        stdscr,
        "refreshing beads…" if cached is not None else "scanning repos for open beads…",
        ascii_only,
    )
    request_load()
    stdscr.timeout(KEY_POLL_MS)
    while True:
        if completed:
            beads, error, missions, prune, triage_note = completed.pop(0)
            beads = sort_beads_for_triage(beads, prune)
            message = _beads_message(beads, error)
            loading = False
            worker = None
            selected = min(selected, max(0, len(beads) - 1))
            mission_selected = min(mission_selected, max(0, len(missions) - 1))
            if force_pending:
                force_pending = False
                request_load(force=True)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        safe_addstr(
            stdscr, 0, 0,
            panel_rule(f"{commander_m_brand()} · BEADS", w - 1, ascii_only),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        safe_addstr(
            stdscr, SHEP_TAB_Y, 0,
            shep_tab_bar(w - 1, "beads", ascii_only),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        mission_hits = []
        bead_hits = []
        y = SHEP_TAB_Y + 1
        safe_addstr(
            stdscr, y, 0,
            _fit_cell(f"MISSIONS FROM BEADS — {triage_note}", w - 1, ascii_only),
            curses.A_UNDERLINE | (_ui_pair(1) if focus == "missions" else 0),
            max_width=w - 1,
        )
        y += 1
        if not missions:
            safe_addstr(
                stdscr, y, 0, "[no launchable bead missions]",
                curses.A_DIM, max_width=w - 1,
            )
            y += 1
        for index, mission in enumerate(missions):
            running = mission_is_running(mission)
            attr = curses.A_REVERSE if (focus == "missions" and index == mission_selected) else 0
            safe_addstr(
                stdscr, y, 0,
                _fit_cell(bead_mission_row(index, mission, running), w - 1, ascii_only),
                attr | curses.A_BOLD | (_ui_pair(2) if running else 0),
                max_width=w - 1,
            )
            mission_hits.append(RenderedHit(index, 0, y, max(1, w - 1)))
            y += 1
        y += 1
        safe_addstr(
            stdscr, y, 0,
            _fit_cell("REPO · ID · STATUS · PRIORITY · TITLE", w - 1, ascii_only),
            curses.A_UNDERLINE | (_ui_pair(1) if focus == "beads" else 0),
            max_width=w - 1,
        )
        y += 1
        # Whatever the strip left over, minus the message and footer rows.
        visible = max(1, h - y - 2)
        top = 0 if selected < visible else selected - visible + 1
        if not beads:
            safe_addstr(stdscr, y, 0, f"[{message}]", SOFT, max_width=w - 1)
        for index, bead in enumerate(beads[top:top + visible], start=top):
            reason = prune.get(bead["id"], "")
            attr = curses.A_REVERSE if (focus == "beads" and index == selected) else curses.A_NORMAL
            safe_addstr(
                stdscr, y + index - top, 0,
                _fit_cell(bead_row(bead, reason), w - 1, ascii_only),
                attr | (_ui_pair(2) if reason else 0), max_width=w - 1,
            )
            bead_hits.append(
                RenderedHit(index, 0, y + index - top, max(1, w - 1))
            )
        safe_addstr(
            stdscr, h - 2, 0, beads_status_line(message, ascii_only),
            curses.A_NORMAL, max_width=w - 1,
        )
        footer = (
            "[tab] focus  [j/k] select  [enter] launch  [x] close pruned  "
            "[r] refresh + retriage  [1] agents  [3] missions  [4] logs  [q] back"
        )
        safe_addstr(
            stdscr, h - 1, 0, _fit_cell(footer, w - 1, ascii_only),
            curses.A_NORMAL, max_width=w - 1,
        )
        safe_refresh(stdscr)
        if return_after_frame is not None:
            return beads, return_after_frame
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1
        if key in (ord("q"), 27, ord("1")):
            # A quick cached/test load can finish between the frame and this
            # key. Give it a tiny, bounded chance to publish one final frame;
            # a slow provider still returns immediately and never owns the UI.
            if worker is not None and worker.is_alive():
                worker.join(timeout=0.05)
            if completed:
                beads, error, missions, prune, triage_note = completed.pop(0)
                beads = sort_beads_for_triage(beads, prune)
                message = _beads_message(beads, error)
                loading = False
                worker = None
                selected = min(selected, max(0, len(beads) - 1))
                mission_selected = min(mission_selected, max(0, len(missions) - 1))
                return_after_frame = "agents"
                continue
            return beads, "agents"
        if key == ord("2"):
            continue
        if key == ord("3"):
            return beads, "missions"
        if key == ord("4"):
            return beads, "logs"
        if key == ord("\t"):
            focus = "beads" if focus == "missions" else "missions"
        elif key in (ord("j"), curses.KEY_DOWN):
            if focus == "missions":
                mission_selected = min(mission_selected + 1, max(0, len(missions) - 1))
            else:
                selected = min(selected + 1, max(0, len(beads) - 1))
        elif key in (ord("k"), curses.KEY_UP):
            if focus == "missions":
                mission_selected = max(mission_selected - 1, 0)
            else:
                selected = max(selected - 1, 0)
        elif key == ord("r"):
            request_load(force=True)
        elif key in (10, 13, curses.KEY_ENTER, ord("l")) and focus == "missions" and missions:
            mission = missions[mission_selected]
            if mission_is_running(mission):
                message = "already running — reap it first to relaunch"
                continue
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0,
                f"Launch '{mission.get('id')}' (WRITES CODE on its own branch, "
                "new worktree)? [Y] launch / other=cancel",
                curses.A_BOLD | _ui_pair(1), max_width=w - 1,
            )
            safe_refresh(stdscr)
            if blocking_getch(stdscr) != ord("Y"):
                message = "launch cancelled"
                continue
            _paint_beads_status(
                stdscr,
                f"launching {mission.get('id')} — cutting isolated worktree, "
                "then starting the agent (may take a few minutes)…",
                ascii_only,
            )
            ok, detail = launch_mission_by_id(mission.get("id"), mission=mission)
            message = ("launched: " if ok else "launch failed: ") + detail[:150]
            if ok:
                # Launching IS the accept signal, and it is the only one the
                # learner ever sees from this tab.
                record_mission_decision("accept", mission)
        elif key == ord("x") and focus == "beads" and beads:
            bead = beads[selected]
            reason = prune.get(bead["id"], "")
            if not reason:
                # Deliberately not offered on an unflagged bead. Closing work
                # nobody judged prunable is the one mistake this key could make
                # that the operator would not notice until the work went missing.
                message = "only beads the triage flagged as prunable can be closed here"
                continue
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0,
                _fit_cell(
                    f"Close {bead['id']} unworked ({reason})? "
                    "Press [x] again to confirm / other=cancel",
                    w - 1, ascii_only,
                ),
                curses.A_BOLD | _ui_pair(2), max_width=w - 1,
            )
            safe_refresh(stdscr)
            # Same-key confirmation, matching the reap key in the fleet view:
            # in this TUI a destructive action is confirmed by repeating its
            # own key, not by a separate [Y]. Launch keeps [Y] because that is
            # what the missions view already uses for the same action.
            if not confirms_with_same_key(blocking_getch(stdscr), ord("x")):
                message = "close cancelled"
                continue
            _paint_beads_status(stdscr, f"closing {bead['id']}…", ascii_only)
            ok, detail = close_bead(bead, reason)
            if ok:
                # Drop it here rather than re-scanning the fleet: load_beads
                # costs a full multi-repo walk, and the export was just
                # rewritten to agree with this.
                beads = [row for row in beads if row["id"] != bead["id"]]
                prune.pop(bead["id"], None)
                selected = min(selected, max(0, len(beads) - 1))
            message = detail if ok else f"close failed: {detail}"
        elif key == curses.KEY_MOUSE:
            mouse = read_mouse_event()
            if mouse.kind == "unsupported":
                message = mouse.detail
                continue
            wheel = -1 if mouse.kind == "wheel_up" else 1 if mouse.kind == "wheel_down" else 0
            if wheel:
                if focus == "missions":
                    mission_selected = scrolled(mission_selected, wheel, len(missions))
                else:
                    selected = scrolled(selected, wheel, len(beads))
                continue
            target = mouse_tab_target(
                mouse.x, mouse.y, mouse.button_state, w - 1, ascii_only
            )
            if target and target != "beads":
                return beads, target
            clicked = rendered_hit_index(
                mission_hits, mouse.x, mouse.y, mouse.button_state
            )
            if clicked is not None:
                mission_selected = clicked
                focus = "missions"
                continue
            clicked = rendered_hit_index(
                bead_hits, mouse.x, mouse.y, mouse.button_state
            )
            if clicked is not None:
                selected = clicked
                focus = "beads"
        # All remaining navigation stays local to this view while the worker
        # runs. The next frame drains its result; no curses calls occur in the
        # worker itself.


# --- LOGS view ---------------------------------------------------------------
#
# What Shep actually did, on screen. The nudges are autonomous, so without this
# the only readable trace was a ClickUp DM per action — which is why that mirror
# is now opt-in (see SHEP_TELEMETRY_CHANNEL). The action ledger already records
# every attempt; this view just reads it.

# Intent receipts are written before the transport runs and are always followed
# by a terminal receipt, so showing both lists every action twice.
LOG_TERMINAL_LIFECYCLES = ("sent", "failed", "refused", "reaped", "answered")

# Outcome carries BOTH a shape and a colour. Colour is what makes one failure
# impossible to miss among three hundred near-identical receipts; the shape is
# what survives the mono theme and a terminal with no colour at all. Neither is
# decoration, which is why a lifecycle may not be added here without both.
LOG_LIFECYCLE_STYLE = {
    "sent": ("→", "->", 1),
    "answered": ("✓", "+", 1),
    "reaped": ("⌫", "<-", 4),
    "failed": ("✗", "x", 3),
    "refused": ("⊘", "!", 2),
}
LOG_UNKNOWN_STYLE = ("·", ".", 0)

# The ledger's own boilerplate. "transport completed" and a bare "ok" are true
# of nearly every receipt, so printing them filled the widest column with the
# one thing that carries no information — 220 of 305 rows read "ok" and nothing
# else. Dropping them lets the rows that DO say something stand alone.
LOG_BOILERPLATE = frozenset({"transport completed", "transport failed", "ok"})

LOG_TIME_WIDTH = 5      # HH:MM
LOG_OUTCOME_WIDTH = 10  # glyph + space + the longest lifecycle ("answered")
LOG_BADGE_WIDTH = 4     # the [CL]-style chips the AGENTS tab already uses
LOG_REPO_MIN_WIDTH = 8
LOG_REPO_MAX_WIDTH = 18


def log_gutter_glyph(event, ascii_only=False):
    """Mark the autonomous actions, not the manual ones.

    Nearly every receipt is manual, so tagging those put a "(manual)" on almost
    every row — and left the handful Shep took on its own looking exactly like
    the ones a human asked for. In an audit view the autonomous action is the
    exceptional one, so it is the one that earns a mark.
    """
    if event.get("mode") != "auto":
        return " "
    # The mark must be a narrow glyph: a wide one (⚡ is EAW=W, two cells)
    # pushes every column after the gutter one cell right of the header.
    return "*" if ascii_only else "↯"


def log_said(event):
    """What Shep actually said, or the closest thing to why it did not.

    Skips the ledger's boilerplate rather than printing it: a receipt whose only
    payload is "ok" is better shown as an empty column, because the outcome cell
    beside it already carries that meaning in both shape and colour.
    """
    for value in (
        event.get("text"), event.get("error"), event.get("result"), event.get("reason"),
    ):
        value = " ".join(str(value or "").split())
        if value and value.lower() not in LOG_BOILERPLATE:
            return value
    return ""


def log_repo_width(entries):
    """Size the repo column to the data, so a short fleet gets no dead gutter."""
    widest = max(
        (
            _text_columns(str((event.get("metadata") or {}).get("repository") or ""))
            for event in entries
        ),
        default=0,
    )
    return max(LOG_REPO_MIN_WIDTH, min(LOG_REPO_MAX_WIDTH, widest))


def log_header_line(repo_width, ascii_only=False):
    """Column headings aligned to the same grid the rows use."""
    separator = ASCII_TABLE_SEPARATOR if ascii_only else TABLE_SEPARATOR
    return "  " + separator.join(
        (
            _fit_cell("WHEN", LOG_TIME_WIDTH, ascii_only),
            _fit_cell("OUTCOME", LOG_OUTCOME_WIDTH, ascii_only),
            _fit_cell("WHO", LOG_BADGE_WIDTH, ascii_only),
            _fit_cell("REPO", repo_width, ascii_only),
            "WHAT SHEP SAID",
        )
    )


def log_row_segments(event, repo_width, previous_stamp=None, ascii_only=False):
    """Styled cells for one receipt: a list of ``(text, colour_pair, attr)``.

    Segments rather than one string because each column has earned a different
    weight. The outcome needs its own colour, the metadata should recede so it
    reads as a label rather than content, and the words Shep actually sent are
    the payload and carry the extra weight. A single attr per line cannot say
    any of that, which is why the old renderer was a wall of identical text.
    Recession is plain-vs-bold, never grey: see SOFT.
    """
    separator = ASCII_TABLE_SEPARATOR if ascii_only else TABLE_SEPARATOR
    stamp = time.strftime("%H:%M", time.localtime(float(event.get("ts") or 0)))
    lifecycle = str(event.get("lifecycle") or "?")
    glyph, ascii_glyph, pair = LOG_LIFECYCLE_STYLE.get(lifecycle, LOG_UNKNOWN_STYLE)
    metadata = event.get("metadata") or {}
    session = str(metadata.get("session") or "")
    badge_row = {"label": session} if session else {}
    repo = str(metadata.get("repository") or event.get("target") or "?")
    # A run of actions in the same minute repeats one timestamp down the column;
    # printing it once lets the eye use the blank as a grouping instead.
    minute = "" if stamp == previous_stamp else stamp
    dim = SOFT
    said = log_said(event)
    segments = [
        # The gutter is a one-cell grid slot: fitting it guarantees no glyph
        # choice can ever push the WHEN column off the header's grid again.
        (_fit_cell(log_gutter_glyph(event, ascii_only), 1, ascii_only),
         0, curses.A_BOLD),
        (" ", 0, 0),
        (_fit_cell(minute, LOG_TIME_WIDTH, ascii_only), 0, dim),
        (separator, 0, dim),
        (
            _fit_cell(
                f"{ascii_glyph if ascii_only else glyph} {lifecycle}",
                LOG_OUTCOME_WIDTH, ascii_only,
            ),
            pair, curses.A_BOLD,
        ),
        (separator, 0, dim),
        (
            _fit_cell(
                agent_badge_token(badge_row) if session else "[-]",
                LOG_BADGE_WIDTH, ascii_only,
            ),
            agent_badge_pair_id(badge_row), curses.A_BOLD,
        ),
        (separator, 0, dim),
        (_fit_cell(repo, repo_width, ascii_only), 0, dim),
    ]
    # A receipt whose only payload was boilerplate ends here: a trailing divider
    # with nothing after it reads as a truncated row rather than a quiet one.
    if said:
        segments += [(separator, 0, dim), (said, 0, curses.A_BOLD)]
    return segments


def log_entry_line(event, repo_width=LOG_REPO_MIN_WIDTH, previous_stamp=None,
                   ascii_only=False):
    """The same row as plain text, for exports and colourless terminals."""
    return "".join(
        text for text, _pair, _attr in
        log_row_segments(event, repo_width, previous_stamp, ascii_only)
    ).rstrip()



def load_action_log(limit=500):
    """Recent terminal action receipts, newest first. Returns (entries, error)."""
    try:
        events = action_log_load()
    except OSError as exc:
        set_tab_badge("logs", 0)
        result = [], f"action ledger unreadable: {exc}"
        _remember_loaded_logs(*result)
        return result
    entries = [
        event for event in events
        if event.get("lifecycle") in LOG_TERMINAL_LIFECYCLES
    ]
    entries.reverse()  # newest first: the last thing Shep did is the thing you want
    set_tab_badge("logs", len(entries))
    if not entries:
        result = [], "no actions recorded yet"
    else:
        result = (entries[:limit] if limit else entries), None
    _remember_loaded_logs(entries, result[1])
    return result


_LOG_LEDGER_MTIME = {"at": None}
_LOG_VIEW_CACHE = {"entries": None, "error": None}


def _remember_loaded_logs(entries, error):
    """Retain the latest ledger snapshot for non-blocking tab entry."""
    _LOG_VIEW_CACHE.update(
        entries=[dict(entry) for entry in entries],
        error=error,
    )


def refresh_log_badge():
    """Keep the LOGS count live without re-reading an unchanged ledger.

    Called from the background fleet refresh, so it must stay cheap: an mtime
    stat on every poll, and a full read only when Shep actually did something.
    """
    try:
        mtime = action_ledger_path().stat().st_mtime
    except OSError:
        return
    if _LOG_LEDGER_MTIME["at"] == mtime:
        return
    _LOG_LEDGER_MTIME["at"] = mtime
    load_action_log(limit=0)


def _paint_logs_status(stdscr, text, ascii_only):
    """One frame showing `text` — so a slow ledger read never looks like a freeze."""
    stdscr.erase()
    _h, w = stdscr.getmaxyx()
    safe_addstr(
        stdscr, 0, 0,
        panel_rule(f"{commander_m_brand()} · LOGS", w - 1, ascii_only),
        curses.A_BOLD | _ui_pair(4), max_width=w - 1,
    )
    safe_addstr(stdscr, 2, 0, text, curses.A_BOLD, max_width=w - 1)
    safe_refresh(stdscr)


def _paint_log_row(window, y, segments, width, selected=False):
    """Paint one receipt, each column keeping its own colour and weight.

    A selected row drops per-column colour and pads to full width: reverse video
    over dim text is unreadable on several terminals, and a highlight that stops
    at the last character reads as a rendering bug rather than a cursor.
    """
    x = 0
    for text, pair, attr in segments:
        if x >= width:
            return
        cell = _clip_to_columns(str(text), width - x)
        if not cell:
            continue
        style = curses.A_REVERSE if selected else (_ui_pair(pair) | attr)
        safe_addstr(window, y, x, cell, style, max_width=width - x)
        x += _text_columns(cell)
    if selected and x < width:
        safe_addstr(window, y, x, " " * (width - x), curses.A_REVERSE,
                    max_width=width - x)


def run_logs_view(stdscr, ascii_only):
    """Show what Shep actually did; return ``(entries, next_tab)``."""
    selected = 0
    cached = _LOG_VIEW_CACHE.get("entries")
    entries = [dict(entry) for entry in cached] if cached is not None else []
    error = _LOG_VIEW_CACHE.get("error") if cached is not None else None
    message = (
        (error or f"{len(entries)} actions · newest first")
        if cached is not None else "reading the action ledger…"
    )
    completed = []
    worker = None
    force_pending = False
    return_after_frame = None

    def request_load(force=False):
        nonlocal worker, message, force_pending
        if worker is not None and worker.is_alive():
            if force:
                force_pending = True
            message = "refresh already in progress…"
            return
        message = "re-reading the action ledger…" if force else "reading the action ledger…"

        def load():
            try:
                result = load_action_log()
            except Exception as exc:  # noqa: BLE001 - a tab must never tear down curses
                result = (entries, f"action ledger unavailable: {str(exc)[:160]}")
            completed.append(result)

        worker = threading.Thread(target=load, daemon=True, name="shep-logs-load")
        worker.start()

    _paint_logs_status(
        stdscr,
        "re-reading the action ledger…" if cached is not None else "reading the action ledger…",
        ascii_only,
    )
    request_load()
    stdscr.timeout(KEY_POLL_MS)
    while True:
        if completed:
            entries, error = completed.pop(0)
            message = error or f"{len(entries)} actions · newest first"
            selected = min(selected, max(0, len(entries) - 1))
            if force_pending:
                force_pending = False
                request_load(force=True)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        repo_width = log_repo_width(entries)
        safe_addstr(
            stdscr, 0, 0,
            panel_rule(f"{commander_m_brand()} · LOGS", w - 1, ascii_only),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        _paint_shep_tabs(stdscr, "logs", ascii_only)
        safe_addstr(
            stdscr, SHEP_TAB_Y + 1, 0,
            _fit_cell(log_header_line(repo_width, ascii_only), w - 1, ascii_only),
            curses.A_UNDERLINE | SOFT, max_width=w - 1,
        )
        visible = max(1, h - SHEP_TAB_Y - 5)
        top = 0 if selected < visible else selected - visible + 1
        if not entries:
            safe_addstr(
                stdscr, SHEP_TAB_Y + 2, 0,
                f"[{message}]", SOFT, max_width=w - 1,
            )
        page = entries[top:top + visible]
        log_hits = []
        for index, event in enumerate(page, start=top):
            # Compared against the row above ON SCREEN, so the repeated-minute
            # blank stays correct no matter where the list is scrolled to.
            previous = page[index - top - 1] if index > top else None
            previous_stamp = (
                time.strftime("%H:%M", time.localtime(float(previous.get("ts") or 0)))
                if previous else None
            )
            _paint_log_row(
                stdscr, SHEP_TAB_Y + 2 + index - top,
                log_row_segments(event, repo_width, previous_stamp, ascii_only),
                w - 1, selected=index == selected,
            )
            log_hits.append(
                RenderedHit(
                    index,
                    0,
                    SHEP_TAB_Y + 2 + index - top,
                    max(1, w - 1),
                )
            )
        safe_addstr(stdscr, h - 2, 0, message, curses.A_NORMAL, max_width=w - 1)
        footer = "[j/k] select  [1] agents  [2] beads  [3] missions  [4] logs  [r] refresh  [q] back"
        safe_addstr(
            stdscr, h - 1, 0, _fit_cell(footer, w - 1, ascii_only),
            curses.A_NORMAL, max_width=w - 1,
        )
        safe_refresh(stdscr)
        if return_after_frame is not None:
            return entries, return_after_frame
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1
        if key in (ord("q"), 27, ord("1")):
            if worker is not None and worker.is_alive():
                worker.join(timeout=0.05)
            if completed:
                entries, error = completed.pop(0)
                message = error or f"{len(entries)} actions · newest first"
                return_after_frame = "agents"
                continue
            return entries, "agents"
        if key == ord("2"):
            return entries, "beads"
        if key == ord("3"):
            return entries, "missions"
        if key == ord("4"):
            continue
        if key == curses.KEY_MOUSE:
            mouse = read_mouse_event()
            if mouse.kind == "unsupported":
                message = mouse.detail
                continue
            wheel = -1 if mouse.kind == "wheel_up" else 1 if mouse.kind == "wheel_down" else 0
            if wheel:
                selected = scrolled(selected, wheel, len(entries))
                continue
            target = mouse_tab_target(
                mouse.x, mouse.y, mouse.button_state, w - 1, ascii_only
            )
            if target and target != "logs":
                return entries, target
            clicked = rendered_hit_index(
                log_hits, mouse.x, mouse.y, mouse.button_state
            )
            if clicked is not None:
                selected = clicked
                message = f"selected {entries[selected].get('target') or '?'}"
        elif key in (ord("j"), curses.KEY_DOWN):
            selected = min(selected + 1, max(0, len(entries) - 1))
        elif key in (ord("k"), curses.KEY_UP):
            selected = max(selected - 1, 0)
        elif key == ord("r"):
            request_load(force=True)


def mission_is_running(mission):
    """True when this mission already has a live worktree.

    The same on-disk check prepare_mission_worktree guards with, so the deck
    shows exactly what the launcher would refuse. Deliberately not an in-memory
    flag: a launched mission must still read as RUNNING after a shep restart,
    a second shep instance, or a deck regenerate.
    """
    return mission_worktree_exists(mission.get("cwd") or "", mission.get("id") or "")


def mission_session(mission, rows):
    """The live session running this mission, or None. -> row

    Matched on the worktree path rather than on a label, because that path is
    what `mission_is_running` already decides RUNNING from -- so the deck and
    the reap agree by construction instead of by a naming convention that would
    drift. A pane whose cwd is the mission worktree, or anywhere inside it, is
    that mission's session.
    """
    wt = mission_worktree_path(mission.get("cwd") or "", mission.get("id") or "")
    for row in rows or ():
        cwd = (row.get("cwd") or "").strip()
        if not cwd:
            continue
        try:
            candidate = Path(cwd).expanduser().resolve()
        except OSError:
            continue
        if candidate == wt or wt in candidate.parents:
            return row
    return None


def run_missions_view(stdscr, ascii_only, rows=None, initial_missions=None):
    """Full-screen list of suggested missions (mission-sense/recommend deck).

    Blocking sub-loop, mirrors the confirm/redraw style of the main TUI loop.
    Enter/[l] launches the selected mission via mission-launch; [r] regenerates
    the deck (shells out, can take a few seconds); q/Esc or a tab click returns
    ``(missions, requested_tab)`` to the tab shell.
    """
    selected = 0
    missions = [dict(mission) for mission in (initial_missions or [])]
    error = None
    message = (
        mission_status_message(missions, error)
        if initial_missions is not None else "loading mission deck…"
    )
    completed = []
    worker = None
    force_pending = False
    refresh_before_ids = None
    return_after_frame = None

    def request_load(force=False):
        nonlocal worker, message, force_pending
        if worker is not None and worker.is_alive():
            if force:
                force_pending = True
            message = "refresh already in progress…"
            return
        message = "regenerating deck…" if force else "loading mission deck…"

        def load():
            try:
                result = load_mission_deck(force=force, allow_generate=True)
            except Exception as exc:  # noqa: BLE001 - a tab must never tear down curses
                result = (missions, f"mission deck unavailable: {str(exc)[:160]}")
            completed.append(result)

        worker = threading.Thread(target=load, daemon=True, name="shep-missions-load")
        worker.start()

    _paint_mission_status(
        stdscr,
        "refreshing mission deck…" if initial_missions is not None else "loading mission deck…",
        ascii_only,
    )
    request_load()
    stdscr.timeout(KEY_POLL_MS)
    while True:
        if completed:
            missions, error = completed.pop(0)
            if refresh_before_ids is not None:
                message = mission_regen_message(refresh_before_ids, missions, error)
                refresh_before_ids = None
            else:
                message = mission_status_message(missions, error)
            selected = min(selected, max(0, len(missions) - 1))
            if force_pending:
                force_pending = False
                refresh_before_ids = [mission.get("id") for mission in missions]
                request_load(force=True)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        safe_addstr(
            stdscr, 0, 0,
            panel_rule(f"{commander_m_brand()} · SUGGESTED MISSIONS", w - 1, ascii_only),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        _paint_shep_tabs(stdscr, "missions", ascii_only)
        y = SHEP_TAB_Y + 2
        mission_hits = []
        if not missions:
            safe_addstr(stdscr, y, 0, f"[{message}]", SOFT, max_width=w - 1)
        top, visible = mission_scroll_window(selected, len(missions), h)
        content_bottom = mission_content_bottom(h)
        for i, mission in enumerate(missions[top:top + visible], start=top):
            if y >= content_bottom:
                break
            row_y = y
            attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
            score = mission.get("momentum_score", 0)
            project = mission.get("project_name") or "?"
            goal = mission.get("short_goal") or "(no goal)"
            kind = mission_kind_label(mission)
            running = mission_is_running(mission)
            state = "RUNNING " if running else ""
            headline = f"{i + 1}. [{score:>3}] {state}{kind} {project} — {goal}"
            row_attr = attr | curses.A_BOLD | (_ui_pair(2) if running else 0)
            safe_addstr(stdscr, y, 0, headline, row_attr, max_width=w - 1)
            y += 1
            for label, field in (("next", "next_step"), ("why", "rationale")):
                text = mission.get(field)
                if text and y < content_bottom:
                    safe_addstr(
                        stdscr, y, 3, _fit_cell(f"{label}: {text}", w - 4, ascii_only),
                        SOFT, max_width=w - 1,
                    )
                    y += 1
            mission_hits.append(
                RenderedHit(i, 0, row_y, max(1, w - 1), y - row_y)
            )
            y += 1
        offscreen = len(missions) - (top + visible)
        if missions and (top or offscreen > 0):
            safe_addstr(
                stdscr, h - 3, 0,
                f"showing {top + 1}-{min(top + visible, len(missions))} of {len(missions)}"
                " · resize taller for more",
                SOFT, max_width=w - 1,
            )
        safe_addstr(stdscr, h - 2, 0, message[: w - 1], curses.A_NORMAL, max_width=w - 1)
        footer = (
            "[j/k] select  [enter/l] launch  [a] away  [d] dismiss  "
            "[r] regen deck  [1/2/4] tabs  [q] back"
        )
        safe_addstr(stdscr, h - 1, 0, _fit_cell(footer, w - 1, ascii_only), curses.A_NORMAL, max_width=w - 1)
        safe_refresh(stdscr)
        if return_after_frame is not None:
            return missions, return_after_frame

        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key in (ord("q"), 27, ord("1")):
            if worker is not None and worker.is_alive():
                worker.join(timeout=0.05)
            if completed:
                missions, error = completed.pop(0)
                if refresh_before_ids is not None:
                    message = mission_regen_message(refresh_before_ids, missions, error)
                    refresh_before_ids = None
                else:
                    message = mission_status_message(missions, error)
                return_after_frame = "agents"
                continue
            return missions, "agents"
        elif key == ord("2"):
            return missions, "beads"
        elif key == ord("3"):
            continue
        elif key == ord("4"):
            return missions, "logs"
        elif key == curses.KEY_MOUSE:
            mouse = read_mouse_event()
            if mouse.kind == "unsupported":
                message = mouse.detail
                continue
            wheel = -1 if mouse.kind == "wheel_up" else 1 if mouse.kind == "wheel_down" else 0
            if wheel:
                selected = scrolled(selected, wheel, len(missions))
                continue
            target = mouse_tab_target(
                mouse.x, mouse.y, mouse.button_state, w - 1, ascii_only
            )
            if target and target != "missions":
                return missions, target
            clicked = rendered_hit_index(
                mission_hits, mouse.x, mouse.y, mouse.button_state
            )
            if clicked is not None:
                selected = clicked
        elif key in (ord("j"), curses.KEY_DOWN):
            selected = min(selected + 1, max(0, len(missions) - 1))
        elif key in (ord("k"), curses.KEY_UP):
            selected = max(selected - 1, 0)
        elif key == ord("r"):
            refresh_before_ids = [mission.get("id") for mission in missions]
            request_load(force=True)
        elif key == ord("x") and missions:
            # Disabled after it closed live sessions that were doing work.
            #
            # Three things compounded. `rows` is the fleet as it looked when this
            # tab was opened and is never refreshed, so the deck acts on a stale
            # snapshot. RUNNING comes from mission_worktree_exists, which tests
            # the worktree DIRECTORY — reaping the pane does not remove it, so a
            # mission still reads RUNNING after a successful close and the deck
            # never acknowledges the operator's action. So they press [x] again.
            # mission_session then re-resolves the same pane id out of the stale
            # snapshot, and once the reap debounce has expired that id is closed
            # for real — by which time herdr may have recycled it for a different
            # session, which is the failure cb3346c exists to prevent.
            #
            # Reaping from the AGENTS tab is unaffected: it acts on live rows it
            # re-collects itself, and its list visibly loses the row.
            message = "close from the AGENTS tab — [x] here acted on a stale list"
        elif key == ord("a"):
            missions, error, message = run_afk_view(
                stdscr, ascii_only, missions, error, message,
            )
            selected = min(selected, max(0, len(missions) - 1))
        elif key == ord("d") and missions:
            # A dismissal is the other half of the training signal. Without it
            # the ledger only ever sees accepts and the weights can rise but
            # never fall — the deck would drift toward whatever it already likes.
            dismissed = missions[selected]
            recorded = record_mission_decision("dismiss", dismissed)
            # The ledger above is write-only — nothing reads it back when the
            # deck is built. That is why dismissing every bug-hunter bead and
            # pressing [r] returned the same five: the only thing a dismissal
            # changed was this in-memory list, which regeneration replaces.
            # This is the half that makes it stick.
            persisted = dismiss_mission(dismissed)
            missions = [m for m in missions if m.get("id") != dismissed.get("id")]
            selected = min(selected, max(0, len(missions) - 1))
            if not persisted:
                message = "dismissed for now — could not save, it will return on regen"
            elif recorded:
                message = (
                    f"dismissed {dismissed.get('project_name')} — hidden for "
                    f"{MISSION_DISMISS_TTL // 86400}d, press [r] to refill"
                )
            else:
                message = (
                    f"dismissed {dismissed.get('project_name')} — hidden for "
                    f"{MISSION_DISMISS_TTL // 86400}d (learner unavailable)"
                )
        elif key in (10, 13, curses.KEY_ENTER, ord("l")) and missions:
            mission = missions[selected]
            mission_id = mission.get("id")
            if mission_is_running(mission):
                message = "already running — reap it first to relaunch"
                continue
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            effect = (
                "artifact-only research"
                if mission.get("mission_kind") == "research"
                else "WRITES CODE on its own branch"
            )
            safe_addstr(
                stdscr, h - 1, 0,
                f"Launch '{mission_id}' ({effect}, new worktree)? [Y] launch / other=cancel",
                curses.A_BOLD | _ui_pair(1), max_width=w - 1,
            )
            safe_refresh(stdscr)
            if blocking_getch(stdscr) != ord("Y"):
                message = "launch cancelled"
                continue
            _paint_mission_status(
                stdscr,
                f"launching {mission_id} — cutting isolated worktree, "
                "then starting the agent (may take a few minutes)…",
                ascii_only,
            )
            ok, detail = launch_mission_by_id(mission_id)
            message = ("launched: " if ok else "launch failed: ") + detail[:150]
            if ok:
                # Launching IS the accept signal — record it before the mission
                # leaves the deck, or the learner never sees what you picked.
                record_mission_decision("accept", mission)
                # Deliberately NOT dropped from the deck. Dropping hid the fact
                # that the mission was running: it vanished, then reappeared
                # unmarked on the next regenerate, so the deck looked like a
                # backlog that never progressed. It now stays put and renders
                # as RUNNING, and the mission_is_running guard above is what
                # stops a second Enter from destroying the live worktree.

    return missions, "agents"


# --- SESSION view (step into one pane) ---------------------------------------
#
# The fleet table can only ever show one line of a session. Stepping into it —
# [→] in, [←] out — gives that session the whole screen without leaving Shep and
# without attaching, so the operator's keys still belong to Shep and coming back
# is one keystroke rather than a detach sequence. Reading is the default because
# it is the safe one; [o] is the deliberate door out to the live session for
# when the operator actually wants to type at the agent.

def _pane_lines(pane_text):
    """Captured pane as per-line (text, attr) segments, blank tail removed.

    A pane padded out to its full height would otherwise push the real output
    off the top of the window and show a screen of nothing.
    """
    lines = [ansi_segments(raw.rstrip()) for raw in pane_text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def session_view_lines(pane_text, height, offset=0):
    """The visible window of a captured pane, as (text, attr) segment lists.

    `offset` is how many lines back from the live tail to show, so scrolling up
    is a slice and not a second capture.
    """
    lines = _pane_lines(pane_text)
    if not lines:
        return [[("[no output captured from this pane]", curses.A_NORMAL)]]
    if height <= 0:
        return []
    end = max(1, len(lines) - max(0, offset))
    return lines[max(0, end - height):end]


def max_session_scroll(pane_text, height):
    """Furthest [k] may scroll back before it would show only blank space."""
    return max(0, len(_pane_lines(pane_text)) - max(1, height))


def herdr_tab_id(target):
    """Tab holding a herdr pane, or "" — `tab focus` addresses tabs, not panes."""
    if not target:
        return ""
    # str() before removeprefix: herdr's JSON reaches this unvalidated, and a
    # non-string target would raise AttributeError straight through
    # run_session_view and take the whole TUI down with it. capture_pane makes
    # the same call inside a blanket except; this is the same guarantee.
    proc = _run([HERDR_BIN, "pane", "get", str(target).removeprefix("herdr:")])
    if proc.returncode != 0:
        return ""
    try:
        return str(json.loads(proc.stdout)["result"]["pane"]["tab_id"] or "")
    except (ValueError, KeyError, TypeError):
        return ""


def attach_command(row, inside_tmux=False, tab_id=""):
    """Command that puts the operator in front of a live session, or None.

    tmux takes this terminal over — and from inside tmux that has to be
    switch-client, because attach refuses to nest and would only print a
    warning. It is deliberately NOT pinned with `-c`: the only tty a process
    inside a pane can name is the PANE's pty, which tmux rejects outright
    ("can't find client"), and a pane is shared by every client viewing it so
    there is no way to ask which one pressed the key. Bare switch-client moves
    the most recently active client, and a real keypress is what makes a client
    the most recently active one — so tmux already resolves this correctly.

    A herdr pane lives in herdr's own window instead, so getting in front of it
    means focusing its tab: that call returns immediately and never wants the
    tty, which is why the caller only suspends curses for tmux.

    An unresolved herdr tab returns None rather than guessing an id. Focusing
    the wrong tab would put the operator's keystrokes into somebody else's
    agent, which is the exact failure the read-only session view exists to
    prevent.
    """
    target = row.get("target")
    if not target:
        return None
    if row.get("source") == "tmux":
        return ["tmux", "switch-client" if inside_tmux else "attach", "-t", target]
    if row.get("source") == "herdr" and tab_id:
        return [HERDR_BIN, "tab", "focus", tab_id]
    return None


_SESSION_SPECIAL_KEYS = {
    curses.KEY_UP: "up",
    curses.KEY_DOWN: "down",
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
    curses.KEY_HOME: "home",
    curses.KEY_END: "end",
    curses.KEY_NPAGE: "pagedown",
    curses.KEY_PPAGE: "pageup",
    curses.KEY_BACKSPACE: "backspace",
    curses.KEY_DC: "delete",
    curses.KEY_ENTER: "enter",
}


def session_key_token(key):
    """Translate one curses key into a transport-neutral pane key.

    The session view normally owns the keyboard. Interactive mode is the
    deliberate exception: every key other than Escape is forwarded to the
    selected pane. Keeping this translation pure makes it possible to test the
    dangerous boundary without a live terminal.
    """
    if key in _SESSION_SPECIAL_KEYS:
        return _SESSION_SPECIAL_KEYS[key]
    if key in (10, 13, "\n", "\r"):
        return "enter"
    if key in (9, "\t"):
        return "tab"
    if key in (8, 127, "\b", "\x7f"):
        return "backspace"
    # Ctrl-A through Ctrl-Z arrive from curses as their control byte.
    if isinstance(key, int) and 1 <= key <= 26:
        return f"ctrl-{chr(key + 96)}"
    if isinstance(key, str) and len(key) == 1 and 1 <= ord(key) <= 26:
        return f"ctrl-{chr(ord(key) + 96)}"
    if isinstance(key, int) and 32 <= key <= 126:
        return chr(key)
    return None


_TMUX_SESSION_KEYS = {
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End", "pagedown": "PageDown",
    "pageup": "PageUp", "backspace": "BSpace", "delete": "DC",
    "enter": "Enter", "tab": "Tab",
}


BRACKETED_PASTE_START = "\x1b[200~"
BRACKETED_PASTE_END = "\x1b[201~"


class SessionInputDecoder:
    """Decode one-at-a-time ``get_wch`` events into session input events.

    Curses returns a single wide character (or one integer function key) per
    call. Terminal bracketed paste is therefore a stream of individual marker
    and payload characters, not one multi-character value. A complete paste is
    the sole exception emitted here: its payload becomes one literal text event
    so the transport cannot alter repeated spaces, Unicode, punctuation, or
    embedded newlines by sending them piecemeal.
    """

    def __init__(self):
        self._start = ""
        self._paste = None
        self._end = ""

    @property
    def pending(self):
        return bool(self._start or self._paste is not None)

    def feed(self, event):
        """Consume one ``get_wch``-shaped event and return decoded events."""
        if self._paste is not None:
            return self._feed_paste(event)
        if event == -1:
            if not self._start:
                return [-1]
            self._start = ""
            return ["\x1b"]
        if not isinstance(event, str) or len(event) != 1:
            if not self._start:
                return [event]
            self._start = ""
            return ["\x1b", event]
        if not self._start and event != "\x1b":
            return [event]

        candidate = self._start + event
        if candidate == BRACKETED_PASTE_START:
            self._start = ""
            self._paste = []
            return []
        if BRACKETED_PASTE_START.startswith(candidate):
            self._start = candidate
            return []

        # Escape remains a logical navigation key. If the following characters
        # were not the paste opener, consume that unrecognised terminal escape
        # sequence rather than leaking its bytes into the live pane.
        self._start = ""
        return ["\x1b"]

    def _feed_paste(self, event):
        if event == -1:
            return []
        if not isinstance(event, str) or len(event) != 1:
            return []

        candidate = self._end + event
        if candidate == BRACKETED_PASTE_END:
            payload = "".join(self._paste)
            self._paste = None
            self._end = ""
            return [payload] if payload else []

        keep = next(
            (
                size
                for size in range(min(len(candidate), len(BRACKETED_PASTE_END) - 1), 0, -1)
                if BRACKETED_PASTE_END.startswith(candidate[-size:])
            ),
            0,
        )
        literal = candidate[:-keep] if keep else candidate
        self._paste.extend(literal)
        self._end = candidate[-keep:] if keep else ""
        return []


def send_session_key(row, key):
    """Forward one operator key to the selected live session.

    This is intentionally separate from ``send_nudge``: interactive mode is a
    human-owned terminal handoff, not an autonomous instruction and not a
    draft. T3 is a message/thread API rather than a pty, so it stays on the
    existing nudge path instead of pretending arbitrary terminal keys exist.
    """
    source = row.get("source")
    target = row.get("target") or row.get("id")
    token = session_key_token(key)
    text = None
    if isinstance(key, str):
        if len(key) > 1 or (len(key) == 1 and token is None and key != "\x1b"):
            text = key
    elif isinstance(key, int) and 32 <= key <= 126:
        text = chr(key)
    if not target or (not text and not token):
        return False, "key is not supported by this terminal"
    try:
        if source == "herdr":
            proc = _run([
                HERDR_BIN, "pane", "send-text" if text is not None else "send-keys",
                str(target).removeprefix("herdr:"), text if text is not None else token,
            ], timeout=3)
        elif source == "tmux":
            tmux_key = _TMUX_SESSION_KEYS.get(token) if text is None else None
            args = [tmux_key] if tmux_key else ["-l", text or token]
            proc = _run(["tmux", "send-keys", "-t", str(target), *args], timeout=3)
        else:
            return False, f"{source or 'this'} sessions do not expose terminal keys"
    except Exception as exc:  # noqa: BLE001 - input must never take down TUI
        detail = str(exc).strip()
        message = f"input failed: {type(exc).__name__}"
        return False, f"{message}: {detail}"[:120] if detail else message
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "transport failed").strip()
        return False, detail[:120]
    return True, text if text is not None else token


def attach_to_session(stdscr, row):
    """Hand the real terminal to a live session. Returns a footer message.

    The session view is normally interactive, so ``[o]`` is the explicit
    transport handoff for operators who want the owning tmux/herdr UI itself;
    curses is SUSPENDED rather than torn down
    (def_prog_mode/reset_prog_mode): `tmux attach` holds the terminal until the
    operator detaches, `switch-client` returns immediately, and either way the
    saved mode is restored so the view repaints instead of leaving a
    half-painted screen.

    Input is flushed around the tmux handover. A held [o] otherwise queues
    repeats that tmux reads once it owns the tty — and types them at the live
    agent, which is what the read-only mirror exists to prevent. Two flushes,
    and neither closes it: `flushinp` clears everything queued at that instant
    (kernel buffer included — it calls tcflush), then a second flush runs as
    late as this process can reach, immediately before the exec. What is left
    is the window between that exec and tmux actually reading, which shep
    cannot touch because its code has stopped running by then. A probe leaked
    two bytes there at a 25ms repeat rate. Mitigation, not elimination — only
    letting go of the key ends it. The leak is always "o" and never Enter, so
    nothing submits itself; in a pane running vim it still opens a line.

    herdr gets a cooldown instead, because there is no handover to flush around
    and nothing else rate-limits it: six held repeats measured seven `_run`
    calls at timeout=8 each, all on the curses thread, which is up to 56s of
    frozen TUI. reap_session carries a debounce for the same lesson.
    """
    source = row.get("source")
    target = row.get("target")
    if not target:
        return "this row has no live pane to attach to"
    tab_id = ""
    if source == "herdr":
        # Both guards sit AHEAD of the tab lookup, because resolving the tab is
        # itself a _run at timeout=8 — checking after it would still pay one
        # freeze per repeat and only save the second call. And the stamp lands
        # on ATTEMPT, not success: a dead pane is exactly what a held [o] finds,
        # it is the expensive path (two calls, not one), and arming only on
        # success left it completely unguarded. The cost of stamping early is a
        # one-second wait before a deliberate retry.
        if time.time() - _FOCUSED.get(target, 0) < FOCUS_DEBOUNCE_SECONDS:
            return "already focused — release [o]"
        _FOCUSED[target] = time.time()
        tab_id = herdr_tab_id(target)
    cmd = attach_command(row, inside_tmux=bool(os.environ.get("TMUX")), tab_id=tab_id)
    if not cmd:
        if source == "herdr":
            return "herdr did not report a tab for this pane — cannot attach"
        return f"{source or 'this'} sessions cannot be attached from Shep"
    if source != "tmux":
        proc = _run(cmd)
        if proc.returncode != 0:
            return f"attach failed: {(proc.stderr or proc.stdout).strip()[:60]}"
        return "focused in herdr — this view stays open behind it"
    curses.flushinp()
    curses.def_prog_mode()
    curses.endwin()
    try:
        # The last moment this process can reach. flushinp ran before endwin,
        # and a held key kept emitting across it; this drops that fresh batch so
        # only tmux's own startup window is left. fd 0 rather than
        # sys.stdin.fileno(): under a capturing harness the wrapper has no
        # fileno and the flush would silently never run. Outside the try below
        # on purpose — a raise here is "not a tty", never a failed attach, and
        # must not be reported as one.
        termios.tcflush(0, termios.TCIFLUSH)
    except (termios.error, OSError, ValueError):
        pass
    try:
        proc = subprocess.run(cmd, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        # A missing tmux or a killed client must not take the TUI down with it.
        detail = f"attach failed: {type(exc).__name__}"
    else:
        # tmux writes "can't find pane: %9999" to a terminal this repaints over
        # within one frame, so an unchecked rc makes a failed attach look
        # identical to an attach the operator detached from.
        detail = (
            "back from attach" if proc.returncode == 0
            else f"attach failed (tmux rc={proc.returncode})"
        )
    finally:
        curses.flushinp()
        curses.reset_prog_mode()
        stdscr.redrawwin()
        stdscr.refresh()
    return detail


def run_session_view(stdscr, row, ascii_only, interactive=False):
    """Full-screen session detail with an explicit nested input mode.

    The safe path is list -> read-only detail -> interactive input. Escape or
    Left removes exactly one level, so neither navigation key can leak into the
    live agent session.
    """
    target = row.get("target") or row.get("id")
    pane, offset, last, notice = "", 0, 0.0, ""
    input_decoder = SessionInputDecoder()
    stdscr.timeout(KEY_POLL_MS)
    while True:
        if time.time() - last > REFRESH_SECONDS:
            pane = (
                row.get("context") or CONTEXT_NO_TARGET
                if row.get("read_only")
                else capture_pane(
                    row.get("source"), row.get("target"),
                    lines=SESSION_VIEW_LINES, ansi=True,
                )
            )
            last = time.time()
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        separator = " | " if ascii_only else " · "
        safe_addstr(
            stdscr, 0, 0,
            panel_rule(
                f"{session_name(row)}{separator}{agent_badge(row)}{separator}"
                f"{status_badge(row, ascii_only)}{separator}{target}"
                + (f"{separator}INTERACTIVE" if interactive else "")
                + (f"{separator}scrolled back {offset}" if offset else ""),
                w - 1, ascii_only,
            ),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        for i, segs in enumerate(session_view_lines(pane, max(1, h - 2), offset)):
            x = 0
            for text, attr in segs:
                if x >= w - 1:
                    break
                visible = _ascii_text(text) if ascii_only else text
                visible = _clip_to_columns(visible, (w - 1) - x)
                safe_addstr(stdscr, 1 + i, x, visible, attr)
                x += _text_columns(visible)
        footer = (
            ("[esc] stop input  [j/k] send  [r] refresh"
             if interactive else
             "[i] interact  [<-] back  [o] attach  [j/k] scroll  [r] refresh  [q] back")
            if ascii_only
            else ("[esc] stop input  ·  every other key goes to the session"
                  if interactive else
                  "[i] interact  ·  [←] back to AGENTS  ·  [o] attach  ·  "
                  "[j/k] scroll  ·  [r] refresh  ·  [q] back")
        )
        if row.get("read_only"):
            footer = "read-only Warp metadata  ·  " + footer
        if notice:
            # Notice FIRST: the base footer is 79 columns, so on an 80-wide
            # terminal _fit_cell ellipsizes it before a single character of the
            # notice survives — and the longest notices are the failures, the
            # one thing the operator cannot afford to have clipped. Losing the
            # tail of a key legend they already know is the cheaper trade.
            footer = notice + (" | " if ascii_only else "  ·  ") + footer
        safe_addstr(
            stdscr, h - 1, 0, _fit_cell(footer, w - 1, ascii_only),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        safe_refresh(stdscr)
        try:
            raw_key = getattr(stdscr, "get_wch", stdscr.getch)()
        except curses.error:
            raw_key = -1
        keys = (
            input_decoder.feed(raw_key)
            if interactive or input_decoder.pending
            else [raw_key]
        )
        for key in keys:
            if interactive:
                if key in (27, "\x1b", curses.KEY_LEFT):
                    interactive = False
                    if not notice.startswith("input unavailable:"):
                        notice = "input stopped — read-only detail"
                    last = 0.0
                    continue
                if key == -1:
                    continue
                ok, detail = send_session_key(row, key)
                notice = "input sent" if ok else f"input unavailable: {detail}"
                offset = 0
                last = 0.0
                continue
            if key in (
                curses.KEY_LEFT,
                ord("h"),
                "h",
                ord("q"),
                "q",
                27,
                "\x1b",
            ):
                return
            if key != -1:
                # Any deliberate key clears the notice, which paints FIRST — a
                # stale one clips "[r] refresh  [q] back" off the legend for the
                # rest of the visit. Guarded on -1 so an idle poll tick does not
                # wipe it within KEY_POLL_MS; [o] reassigns below, so it still
                # shows. One clear ahead of the chain, not one per branch, or the
                # next key added here quietly misses it.
                notice = ""
            if key in (ord("k"), "k", curses.KEY_UP):
                offset = min(offset + 1, max_session_scroll(pane, h - 2))
            elif key in (ord("j"), "j", curses.KEY_DOWN):
                offset = max(offset - 1, 0)
            elif key in (ord("o"), "o"):
                notice = attach_to_session(stdscr, row)
                # Cheap insurance, not a fix for a known loss: a pty probe shows
                # the poll timeout does survive endwin/reset_prog_mode (it lives on
                # the window, not the tty). A subprocess that leaves the tty odd
                # would cost the live refresh until the next keypress, so re-arm.
                stdscr.timeout(KEY_POLL_MS)
                last = 0.0
            elif key in (ord("i"), "i"):
                interactive = True
                offset = 0
                notice = "interactive mode — Escape returns to Shep"
                last = 0.0
            elif key in (ord("r"), "r"):
                last = 0.0


def fleet_summary(rows):
    """Compact at-a-glance fleet health for the title bar."""
    def needs_attention(row):
        return (
            bool(row.get("reap_ready"))
            or row.get("status") in {"stalled", "error", "asking"}
            or str(row.get("status", "")).startswith("[UNRESPONSIVE")
        )

    attention = sum(needs_attention(row) for row in rows)
    active = sum(row.get("status") == "working" and not needs_attention(row) for row in rows)
    idle = sum(
        row.get("status") in {"idle", "done"} and not needs_attention(row)
        for row in rows
    )
    return (
        f"{commander_m_brand()} · SHEP · {len(rows)} sessions · {active} active · "
        f"{idle} idle · {attention} attention"
    )


def commander_m_brand():
    """Return the fixed identity; supported runtime settings cannot rename it."""
    return "◆M◆ Commander M"


def terminal_too_small_message(width, height, min_width=40, min_height=16):
    """Keep the fixed identity visible even when the full TUI cannot render."""
    return (
        f"{commander_m_brand()} · Terminal too small ({width}x{height}). "
        f"Resize to at least {min_width}x{min_height} to use shep."
    )


def table_layout(width):
    """Responsive fleet columns whose widths always total the terminal width.

    SESSION is the herdr tab label, and it sits immediately left of the nudge so
    the two read together: which session, then what it is being told. AGENT (the
    [CL]/[CX]/[KI] badge) is a separate, narrow column and only earns space on
    wide terminals — it is near-constant across a fleet, so it identifies far
    less than the tab label does.

    NUDGE / CONTEXT is the column that absorbs extra width, not REPO. REPO used
    to take every leftover column, which on a 200-wide terminal meant ~110
    characters of whitespace after a 13-character repo name while the nudge text
    stayed clipped at 42.
    """
    width = max(1, width)
    if width >= 110:
        # 5 separators between the 6 columns below.
        fixed = 6 + 11 + 12 + 20 + 12 + len(TABLE_SEPARATOR) * 5
        return [
            ("source", "SRC", 6),
            ("agent", "AGENT", 11),
            ("status", "STATUS", 12),
            ("session", "SESSION", 20),
            ("activity", "NUDGE / CONTEXT", width - fixed),
            ("repo", "REPO", 12),
        ]
    if width >= 60:
        fixed = 6 + 16 + 12 + len(TABLE_SEPARATOR) * 3
        return [
            ("source", "SRC", 6),
            ("session", "SESSION", 16),
            ("status", "STATUS", 12),
            ("nudge", "NUDGE", width - fixed),
        ]
    fixed = 10 + 10 + len(TABLE_SEPARATOR) * 2
    return [
        ("session", "SESSION", 10),
        ("status", "STATUS", 10),
        ("nudge", "NUDGE", max(1, width - fixed)),
    ]


def format_table_line(layout, values, ascii_only=False):
    """Render one table line and return each column's cell coordinates."""
    parts = []
    positions = {}
    x = 0
    for index, (key, _label, width) in enumerate(layout):
        cell = _fit_cell(values.get(key, ""), width, ascii_only)
        positions[key] = (x, width)
        parts.append(cell)
        x += width
        if index < len(layout) - 1:
            separator = ASCII_TABLE_SEPARATOR if ascii_only else TABLE_SEPARATOR
            parts.append(separator)
            x += len(separator)
    return "".join(parts), positions


def table_row_at_y(mouse_y, top, table_height, row_count, header_rows=5):
    """Map a terminal click to the underlying scrolled fleet row."""
    visible_index = mouse_y - header_rows
    visible_count = min(table_height, max(0, row_count - top))
    if 0 <= visible_index < visible_count:
        return top + visible_index
    return None


def mouse_selected_row(
    mouse_y, button_state, top, table_height, row_count, header_rows=5,
):
    """Return the clicked fleet row, ignoring non-primary mouse events.

    ``header_rows`` is a parameter because the pending queue sits above the
    table and changes height as work arrives. Left at the old constant, every
    click landed one row off for each line the queue was showing.
    """
    left_click = button_state & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED)
    if not left_click:
        return None
    return table_row_at_y(mouse_y, top, table_height, row_count, header_rows)


class RenderedHit(NamedTuple):
    """Clickable geometry emitted by a list renderer for one logical row."""

    index: int
    x: int
    y: int
    width: int
    height: int = 1


def rendered_hit_index(hits, mouse_x, mouse_y, button_state):
    """Resolve a primary click against the exact geometry drawn this frame."""
    if mouse_x is None or mouse_y is None:
        return None
    if not button_state & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
        return None
    return next(
        (
            hit.index
            for hit in hits
            if hit.x <= mouse_x < hit.x + hit.width
            and hit.y <= mouse_y < hit.y + hit.height
        ),
        None,
    )


# ncurses 6 reports the scroll wheel as buttons 4 and 5. macOS ships ncurses 5,
# whose mouse protocol only has four buttons, so BUTTON5_PRESSED does not exist
# there at all -- hence the getattr rather than a direct reference, which would
# make importing shep fail on the platform it is developed on.
WHEEL_DOWN_MASK = getattr(curses, "BUTTON5_PRESSED", 0)


class MouseInput(NamedTuple):
    """One decoded mouse input, including capability failures."""

    kind: str
    x: int | None = None
    y: int | None = None
    button_state: int = 0
    detail: str = ""


def read_mouse_event():
    """Decode the pending mouse event without guessing after capability errors.

    A failed ``getmouse`` call is not a wheel event: it means this curses build
    or terminal cannot report the event. Keeping that state distinct lets each
    public loop show the operator what happened instead of silently scrolling.
    """
    try:
        _mouse_id, x, y, _mouse_z, button_state = curses.getmouse()
    except curses.error as exc:
        detail = " ".join(str(exc).split()) or type(exc).__name__
        return MouseInput("unsupported", detail=f"mouse unavailable: {detail}"[:120])
    if button_state & curses.BUTTON4_PRESSED:
        return MouseInput("wheel_up", x, y, button_state)
    if WHEEL_DOWN_MASK and button_state & WHEEL_DOWN_MASK:
        return MouseInput("wheel_down", x, y, button_state)
    return MouseInput("click", x, y, button_state)


def scrolled(selected, wheel, count):
    """Move a list cursor by one wheel notch, clamped to the list."""
    return max(0, min(selected + wheel, max(0, count - 1)))


def reselect(rows, held_key, previous_index):
    """Where the fleet cursor belongs after a fresh collection. -> index

    Follows the session, not the slot. `previous_index` is a position, and a
    collection is free to add, drop and reorder sessions -- herdr rows come
    first and tmux only fills what herdr did not claim, so a single pane
    appearing or exiting renumbers everything after it. Carrying the position
    through, which is all this used to do, slid the cursor onto a different
    session on every refresh and took the context panel with it: the operator
    picked one session and seconds later the right-hand column was describing
    another, with nothing on screen to say it had moved.

    The clamped position stays as the fallback for the one case identity cannot
    survive, which is the selected pane itself having exited.
    """
    if not rows:
        return 0
    return next(
        (
            index for index, row in enumerate(rows)
            if (row.get("target") or row.get("id")) == held_key
        ),
        min(previous_index, len(rows) - 1),
    )


def safe_addstr(window, y, x, text, attr=0, max_width=None):
    """Draw within a terminal boundary without letting curses end the TUI.

    Curses can return ERR when a resize races a redraw or when wide Unicode
    reaches the lower-right boundary. Status messages may contain pane output,
    so both cases must be non-fatal.
    """
    if max_width is not None:
        if max_width <= 0:
            return
        text = _clip_to_columns(text, max_width)
    try:
        window.addstr(y, x, text, attr)
    except curses.error:
        pass


def safe_refresh(window):
    """Refresh without crashing when the terminal is resized mid-redraw."""
    try:
        window.refresh()
    except curses.error:
        pass


def blocking_getch(window):
    """Wait for a confirmation key, then restore the TUI's polling timeout."""
    window.timeout(-1)
    try:
        return window.getch()
    finally:
        window.timeout(KEY_POLL_MS)


def confirms_with_same_key(key, action_key):
    """Return whether a destructive action received its deliberate repeat key."""
    return key == action_key


def _edit_line_key(buffer, cursor, key):
    """Apply one curses key to an editable line."""
    if key in ("\n", "\r", curses.KEY_ENTER, 10, 13):
        return buffer, cursor, "submit"
    if key in ("\x1b", 27):
        return buffer, cursor, "cancel"
    if key == curses.KEY_LEFT:
        return buffer, max(0, cursor - 1), None
    if key == curses.KEY_RIGHT:
        return buffer, min(len(buffer), cursor + 1), None
    if key == curses.KEY_HOME:
        return buffer, 0, None
    if key == curses.KEY_END:
        return buffer, len(buffer), None
    if key in (curses.KEY_BACKSPACE, "\b", "\x7f", 8, 127):
        if cursor:
            del buffer[cursor - 1]
            cursor -= 1
        return buffer, cursor, None
    if key == curses.KEY_DC:
        if cursor < len(buffer):
            del buffer[cursor]
        return buffer, cursor, None
    if isinstance(key, str) and key.isprintable():
        buffer.insert(cursor, key)
        cursor += 1
    return buffer, cursor, None


def blocking_edit_line(window, y, prompt, initial, max_width):
    """Edit a real prefilled nudge with arrows/backspace; Enter submits, Esc cancels."""
    buffer = list(initial)
    cursor = len(buffer)
    available = max(1, max_width - len(prompt))
    window.timeout(-1)
    try:
        while True:
            start = max(0, cursor - available + 1)
            visible = "".join(buffer[start:start + available])
            try:
                safe_addstr(window, y, 0, " " * max_width, max_width=max_width)
                safe_addstr(window, y, 0, prompt + visible, max_width=max_width)
                cursor_text = prompt + "".join(buffer[start:cursor])
                window.move(y, min(max_width - 1, _text_columns(cursor_text)))
                safe_refresh(window)
            except curses.error:
                pass
            key = window.get_wch()
            buffer, cursor, action = _edit_line_key(buffer, cursor, key)
            if action == "submit":
                return "".join(buffer)
            if action == "cancel":
                return None
    finally:
        window.timeout(KEY_POLL_MS)


def recalled_context_lines(item, now=None):
    """What the context panel should say for a finished session with no pane.

    Pure so it can be asserted without a screen. The panel is otherwise driven
    entirely by the fleet cursor, which cannot point at a session whose pane has
    exited -- so without this the operator reads one session's output beneath
    another session's name.
    """
    label = (item.get("row") or {}).get("label") or item.get("target") or "?"
    lines = [
        f"{label} finished and its pane has since closed.",
        "",
        f"It said: {item.get('summary') or 'declared itself done'}",
    ]
    if item.get("repo"):
        lines.append(f"Repo: {item['repo']}")
    lines += [
        "",
        "Nothing to preview — there is no live pane to read.",
        "Press [enter] to clear it from the finished list.",
    ]
    return lines


def _draw_recalled_context_panel(stdscr, item, ctx_x, ctx_y, ctx_w, ctx_bottom, ascii_only):
    """Render the recalled-record panel in place of a live session preview."""
    label = (item.get("row") or {}).get("label") or item.get("target") or "?"
    separator = " | " if ascii_only else " · "
    try:
        stdscr.addstr(
            ctx_y, ctx_x,
            panel_rule(
                f"FINISHED{separator}{label}{separator}pane closed", ctx_w, ascii_only,
            ),
            curses.A_BOLD | _ui_pair(4),
        )
    except curses.error:
        pass
    for offset, line in enumerate(recalled_context_lines(item)):
        row_y = ctx_y + 1 + offset
        if row_y >= ctx_bottom:
            break
        safe_addstr(
            stdscr, row_y, ctx_x,
            _fit_cell(line, ctx_w, ascii_only),
            SOFT, max_width=ctx_w,
        )


def record_draft_verdict(key, text, context):
    """Record whether a freshly drafted nudge is ready or waiting on a person.

    The pending queue keys on this event, and only `sweep` ever wrote a "held"
    one -- so a draft the TUI held rendered "HELD:" in the fleet table (computed
    live from planned_cache) while never appearing in the queue that exists to
    collect exactly those decisions. Observed on a live fleet: a panel titled
    "24 waiting on you" holding twenty-four finished sessions and none of the
    three drafts actually waiting on the operator.

    The intent lane additionally recorded every draft as "ready" regardless, so
    a held draft could overwrite a real held event from the sweep -- newest wins
    on merge -- and remove the decision from the queue rather than add it.
    """
    reason = nudge_hold_reason(text, context)
    if reason:
        record_nudge_event(key, "held", text, reason)
    else:
        record_nudge_event(key, "ready", text)
    return reason


def run_tui(stdscr, initial_theme="classic", initial_rows=None):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.nodelay(True)
    stdscr.timeout(KEY_POLL_MS)
    theme_name = apply_theme(initial_theme)
    ascii_only = use_ascii_ui()
    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
        curses.mouseinterval(0)
    except curses.error:
        pass  # keyboard navigation remains available in terminals without mouse support
    fixture_mode = initial_rows is not None
    # Never collect panes in the curses thread.  A single unresponsive tmux or
    # herdr command may take its full subprocess timeout; doing that work here
    # made the entire monitor look wedged and also made a mouse click feel like
    # it had been ignored.
    rows = list(initial_rows) if fixture_mode else []
    selected = 0
    # Cursor into AGENTS_SPLIT_RATIOS: where the fleet/context divider sits.
    # None is the stacked layout. Until the operator moves the divider
    # themselves the position is re-derived from the terminal width on every
    # frame, so a resize lands on the best layout the new width can afford
    # instead of keeping one chosen for a width that is gone.
    split_index = None
    split_auto = True
    # The queue keeps its own cursor. Sharing the fleet cursor would mean
    # arrowing through the shortlist scrolled the table underneath it, and the
    # two lists are different lengths and different orders.
    pending_sel = 0
    pending_focus = False
    last_refresh = time.time()
    auto_draft = True
    message = "ready"
    loading_frame = 0
    refresh_pending = not fixture_mode
    refresh_error = None
    # Cache-only (never shells out here): shows the last generated deck, if
    # any, without slowing startup. [M] opens the full view and can generate.
    cached_missions, _mission_err = load_mission_deck(force=False, allow_generate=False)

    def open_tab(target):
        """Enter tab views until one of them requests the Agents view."""
        nonlocal cached_missions
        while target != "agents":
            if target == "beads":
                _beads, target = run_beads_view(stdscr, ascii_only)
            elif target == "missions":
                cached_missions, target = run_missions_view(
                    stdscr, ascii_only, rows, cached_missions,
                )
            elif target == "logs":
                _entries, target = run_logs_view(stdscr, ascii_only)
            else:
                target = "agents"
        return target

    context_cache = {}  # key -> preview text
    planned_cache = {}  # key -> drafted nudge text (or None)
    candidate_cache = {}  # key -> operational and intent candidates
    assessment_cache = {}  # key -> per-engine scores, winner, rationale
    selected_engine = {}  # key -> engine currently exposed to send safety
    planned_hash = {}   # key -> hash of the context that produced planned_cache[key]
    verified_cache = {}  # key -> (category, verdict) from llm_verify_risk, for merge/push drafts
    drafting_keys = set()  # keys with a background draft in flight
    verifying_keys = set()  # keys with a background risk-verify in flight
    context_selected = None
    draft_lock = threading.Lock()
    draft_slots = threading.Semaphore(DRAFT_CONCURRENCY)
    io_lock = threading.Lock()
    refresh_in_flight = False
    context_fetching = set()
    completed_context = []  # (row snapshot, ANSI pane text), written by daemon workers
    completed_refreshes = []  # (rows, error), applied by the curses thread

    def _clear_draft(key, reason):
        planned_cache[key] = None
        candidate_cache.pop(key, None)
        assessment_cache.pop(key, None)
        selected_engine.pop(key, None)
        planned_hash.pop(key, None)
        verified_cache.pop(key, None)
        record_nudge_event(key, "invalidated", detail=reason)
        record_outcome("invalidated", target=key, reason=reason)

    def _row_for_key(key):
        return next(
            (row for row in rows if (row.get("target") or row.get("id")) == key),
            None,
        )

    def _request_fleet_refresh():
        """Collect the fleet away from curses; coalesce overlapping refreshes."""
        nonlocal refresh_in_flight, refresh_pending, refresh_error
        if fixture_mode:
            return
        with io_lock:
            if refresh_in_flight:
                return
            refresh_in_flight = True
            refresh_pending = True
            refresh_error = None

        def collect():
            nonlocal refresh_in_flight
            try:
                fresh_rows = collect_all()
                # The nudges are autonomous, so the LOGS count has to move on
                # its own too — otherwise it only ever grows when the operator
                # happens to open the tab, which is the opposite of live. Beads
                # move without Shep at all (any repo, any agent, any human), so
                # BEADS needs the same treatment for the same reason.
                refresh_log_badge()
                refresh_beads_badge()
                with io_lock:
                    completed_refreshes.append((fresh_rows, None))
            except Exception as exc:  # noqa: BLE001 - a collector cannot kill TUI
                detail = " ".join(str(exc).split())[:160] or type(exc).__name__
                with io_lock:
                    completed_refreshes.append(
                        (None, f"refresh failed: {type(exc).__name__}: {detail}")
                    )
            finally:
                with io_lock:
                    refresh_in_flight = False

        threading.Thread(target=collect, daemon=True).start()

    def _request_context(row):
        """Fetch a pane preview asynchronously, once per target at a time."""
        key = row.get("target") or row.get("id")
        if not key:
            return
        if fixture_mode:
            context_cache[key] = row.get("preview", CONTEXT_DEMO)
            return
        with io_lock:
            if key in context_fetching:
                return
            context_fetching.add(key)

        # Keep a copy: refresh workers replace `rows` while this command runs.
        row_snapshot = dict(row)

        def capture():
            try:
                preview = get_pane_context(row_snapshot)
                with io_lock:
                    completed_context.append((row_snapshot, preview))
            finally:
                with io_lock:
                    context_fetching.discard(key)

        threading.Thread(target=capture, daemon=True).start()

    def _drain_io_results():
        """Apply worker results from the curses thread before rendering."""
        nonlocal rows, selected, refresh_pending, refresh_error, message
        with io_lock:
            fresh_batches = completed_refreshes[:]
            completed_refreshes.clear()
            contexts = completed_context[:]
            completed_context.clear()
        if fresh_batches:
            fresh_rows, error = fresh_batches[-1]
            refresh_pending = False
            refresh_error = error
            if error:
                message = error
                return
            # Read before `rows` is replaced: which session the cursor is on,
            # as opposed to which slot.
            held_key = (
                rows[selected].get("target") or rows[selected].get("id")
                if rows else None
            )
            rows = fresh_rows or []
            for key, planned in list(planned_cache.items()):
                current_row = _row_for_key(key)
                if planned and (
                    current_row is None
                    or current_row.get("status") not in NUDGEABLE
                    or current_row.get("reap_ready")
                ):
                    status = current_row.get("status") if current_row else "missing"
                    _clear_draft(key, f"session is now {status}")
            selected = reselect(rows, held_key, selected)
            selected_key = rows[selected].get("target") if rows else None
            if selected_key:
                _request_context(rows[selected])
        for row, preview in contexts:
            key = row.get("target") or row.get("id")
            current_row = _row_for_key(key) or row
            if planned_cache.get(key):
                stale_reason = nudge_revalidation_reason(
                    current_row, planned_hash.get(key), preview
                )
                if stale_reason:
                    _clear_draft(key, stale_reason)
            context_cache[key] = preview
            # The fleet queue receives rows, not context_cache. Preserve the
            # same bounded, cleaned context used by the drafter so an
            # interactively drafted safe nudge is not held as "context
            # unavailable" when the operator presses N.
            current_row["context"] = "\n".join(clean_context_lines(preview)[-NUDGE_EVIDENCE_LINES:])
            _maybe_draft(current_row, preview)

    def _background_draft(
        key, row, recent, attempt, context_hash, evidence_fingerprint,
    ):
        global NUDGES_DRAFTED
        # Read-only snapshot for prompt context; the authoritative state read
        # happens under draft_lock below.
        prompt_state = _nudge_state(key)
        with draft_slots:
            operational_failures = []
            operational_raw = llm_draft_nudge(
                row, recent, attempt,
                prior=prompt_state.get("prior_nudges"),
                stalled_for=stalled_seconds(key),
                fleet_rows=rows,
                failures=operational_failures,
            )
        operational = operational_candidate_or_fallback(
            operational_raw, row, recent
        )
        explicit_abstention = bool(
            operational_raw
            and (
                is_abstention(operational_raw)
                # A deliberate verdict, not a quality failure. Without this the
                # TUI labels a blocked pane "low_quality", which reads as the
                # drafter having written something bad rather than having said
                # this needs the operator.
                or needs_human_request(operational_raw)
            )
        )
        candidates = {"operational": operational}
        record_outcome(
            "drafted", target=key, engine="operational", present=bool(operational),
            attempt=attempt, **({"text": operational} if operational else {}),
        )
        # The Markdown policy is the sole semantic drafting lane. Python keeps
        # this stable compatibility assessment only for existing UI/telemetry
        # fields; no second model grades or rewrites the proposal.
        assessment = {
            "scores": {"operational": 100, "intent": 0},
            "winner": "operational" if operational else "none",
            "rationale": "Single Markdown nudge policy.",
            "source": "markdown",
        }
        record_outcome(
            "judged", target=key, scores=(assessment or {}).get("scores"),
            winner=(assessment or {}).get("winner"),
            source=(assessment or {}).get("source"),
        )
        engine, text = select_candidate(candidates, assessment)
        with draft_lock:
            state = _nudge_state(key)
            current_row = _row_for_key(key) or row
            stale_reason = nudge_revalidation_reason(
                current_row, context_hash, context_cache.get(key, "")
            )
            if stale_reason:
                drafting_keys.discard(key)
                _clear_draft(key, stale_reason)
                return
            candidate_cache[key] = candidates
            assessment_cache[key] = assessment
            selected_engine[key] = engine
            if not text:
                recommended_engine = (assessment or {}).get("winner")
                quality_reason = nudge_quality_reason(
                    assessment, recommended_engine
                )
                planned_cache[key] = None
                if operational_raw is None:
                    failures = note_draft_failure(state)
                    # Same attribution as the headless lane, and the operator
                    # sees it too: "gateway unavailable" was shown for a draft
                    # that timed out on our own 15s clock, which sent people
                    # looking at the wrong system.
                    why = (
                        operational_failures[0] if operational_failures
                        else "gateway_unavailable"
                    )
                    detail = f"{why.replace('_', ' ')} ({failures}/{MAX_DRAFT_FAILURES})"
                    record_outcome(
                        "draft_failed", target=key, engine="operational",
                        reason=why, attempt=failures,
                    )
                else:
                    state["draft_failures"] = 0
                    state["exhausted_reason"] = (
                        "abstained" if explicit_abstention else "low_quality"
                    )
                    state["assessed_fingerprint"] = evidence_fingerprint
                    state["next_at"] = time.time() + NUDGE_COOLDOWN_SECONDS
                    if explicit_abstention:
                        detail = nudge_draft_skip_detail(True)
                    else:
                        detail = quality_reason or nudge_draft_skip_detail(False)
                    record_outcome(
                        "abstained" if explicit_abstention else "suppressed",
                        target=key, engine=recommended_engine,
                        reason=(
                            "explicit_no_nudge" if explicit_abstention else "low_quality"
                        ),
                    )
                record_nudge_event(key, "skipped", detail)
            elif is_repeat_nudge(text, state):
                planned_cache[key] = None  # dedupe: don't re-offer the same words
                state["draft_failures"] = 0
                state["exhausted_reason"] = "duplicate"
                state["assessed_fingerprint"] = evidence_fingerprint
                record_nudge_event(key, "skipped", "duplicate draft")
                record_outcome(
                    "suppressed", target=key, engine=engine, reason="duplicate"
                )
            else:
                NUDGES_DRAFTED += 1
                state["draft_failures"] = 0
                state["assessed_fingerprint"] = evidence_fingerprint
                state["attempt"] = attempt
                remember_nudge(state, text)
                state["next_at"] = time.time() + NUDGE_BACKOFF_SECONDS[
                    min(attempt, len(NUDGE_BACKOFF_SECONDS)) - 1
                ]
                state["proposed"] = {
                    "text": text,
                    "status": "queued",
                    "category": classify_risk(text)[0],
                    "at": time.time(),
                }
                planned_cache[key] = text
                record_draft_verdict(key, text, current_row.get("context") or recent)
                record_outcome(
                    "recommended", target=key, engine=engine, mode="auto",
                    text=text, draft=text,
                    # Which content rule (if any) will hold this draft back from
                    # auto-send, recorded once here rather than per render frame.
                    # Judged against the row's stored context — what the real gate
                    # uses — NOT the `recent` slice, which is the novel-lines
                    # subset and would report "not grounded" for drafts the gate
                    # actually clears. A null reason means it passed.
                    reason=nudge_content_quality_reason(
                        text, current_row.get("context") or recent
                    ),
                )
            drafting_keys.discard(key)
        if planned_cache.get(key):
            category, reason = classify_risk(planned_cache[key])
            if category in ("merge", "push"):
                _dispatch_verify(key, planned_cache[key], category, reason, recent)

    def _background_intent_draft(key, row, recent):
        """Draft an operator-intent direction on demand, including for working panes."""
        global NUDGES_DRAFTED
        reasons = []
        with draft_slots:
            intent = llm_draft_intent(row, recent, reasons=reasons, fleet_rows=rows)
        with draft_lock:
            candidates = dict(candidate_cache.get(key, {}))
            candidates["intent"] = intent
            candidate_cache[key] = candidates
            assessment = fallback_candidate_assessment(candidates)
            assessment_cache[key] = assessment
            _engine, text = select_candidate(candidates, assessment, requested="intent")
            # Mirror the operational lane: one `drafted` event either way, so the
            # report's abstention_rate (derived from drafted events, not from the
            # reason events) can see this lane at all. Until now [i] wrote nothing
            # here and read as though it had never run. A gateway outage is not an
            # abstention — tag it the way the operational lane does, or every blip
            # reads as the intent engine declining to answer.
            gateway_down = not text and reasons[:1] == ["engine_unavailable"]
            record_outcome(
                "drafted", target=key, engine="intent", present=bool(text),
                **({"text": text} if text else {}),
                reason="gateway_unavailable" if gateway_down else None,
            )
            if text:
                NUDGES_DRAFTED += 1
                selected_engine[key] = "intent"
                planned_cache[key] = text
                record_draft_verdict(key, text, recent)
                # The gate verdict rides on `recommended` in both lanes — that is
                # the event the report tallies held reasons from.
                record_outcome(
                    "recommended", target=key, engine="intent", mode="manual",
                    text=text, draft=text,
                    reason=nudge_content_quality_reason(text, recent),
                )
            else:
                planned_cache[key] = None
                if gateway_down:
                    record_nudge_event(key, "skipped", "gateway unavailable")
                    record_outcome(
                        "draft_failed", target=key, engine="intent",
                        reason="gateway_unavailable",
                    )
                else:
                    record_nudge_event(key, "skipped", "intent engine abstained")
                    record_outcome(
                        "abstained", target=key, engine="intent",
                        reason=(reasons[0] if reasons else "engine_abstained"),
                    )
            drafting_keys.discard(key)
        if text:
            category, reason = classify_risk(text)
            if category in ("merge", "push"):
                _dispatch_verify(key, text, category, reason, recent)

    def _dispatch_intent_draft(row):
        """Queue a user-requested intent direction without the idle/stalled gate."""
        key = row.get("target") or row.get("id")
        preview = context_cache.get(key, "")
        recent = clean_context_lines(preview)[-NUDGE_EVIDENCE_LINES:]
        if not recent:
            return False, "no usable pane context for an intent direction"
        with draft_lock:
            if key in drafting_keys:
                return False, "intent direction is already drafting"
            drafting_keys.add(key)
            record_nudge_event(key, "drafting")
        threading.Thread(
            target=_background_intent_draft, args=(key, row, recent), daemon=True
        ).start()
        return True, "drafting intent direction"

    def _background_verify(key, text, category, reason, recent_lines):
        excerpt = "\n".join(recent_lines)
        verdict = llm_verify_risk(text, category, reason, excerpt)
        with draft_lock:
            # Only apply if the plan hasn't changed underneath us (redraft, new
            # context) while the two gateway calls were in flight.
            if planned_cache.get(key) == text:
                verified_cache[key] = (text, verdict)
            verifying_keys.discard(key)

    def _dispatch_verify(key, text, category, reason, recent_lines):
        with draft_lock:
            if key in verifying_keys:
                return
            verifying_keys.add(key)
        threading.Thread(
            target=_background_verify, args=(key, text, category, reason, recent_lines),
            daemon=True,
        ).start()

    def _maybe_draft(row, preview):
        key = row.get("target") or row.get("id")
        if fixture_mode or not auto_draft or is_context_placeholder(preview):
            return
        state = _nudge_state(key)
        # Ahead of the evidence fingerprint, exactly as the sweep does it: a
        # quota-blocked pane repeats the same bytes every poll, so a recovery
        # placed below would be suppressed as `no_new_evidence` and the dropped
        # instruction would never be resent while an operator sat watching.
        #
        # `should_nudge` is what bounds the retry ladder here — each recovery
        # pushes `next_at` out by a whole rung, so the 5-second redraw cannot
        # spend the budget. The two cache guards are what keep it from racing
        # the drafter: a recovery landing while a draft is in flight is wiped by
        # that draft's own staleness check moments later, taking a rung with it,
        # and one landing on top of an operator's `[i]` intent direction would
        # replace text they asked for with text they did not.
        #
        # Safe to read unlocked, and only because of two orderings: nothing but
        # the curses thread ever ADDS to `drafting_keys` (workers only discard),
        # and `_background_draft` writes `planned_cache` before discarding the
        # key under `draft_lock`. Calling `_maybe_draft` from a worker thread
        # would turn both reads into a race.
        if (
            planned_cache.get(key) is None
            and key not in drafting_keys
            and should_nudge(row, state)
        ):
            recovered, suppressed = rate_limit_recovery(
                row, state, preview, clean_context_lines(preview), persisted=False,
            )
            if recovered:
                # planned_hash pairs with the draft: `_revalidate_for_send`
                # refuses to send any proposal whose pane context has moved
                # since, and a recovery with no hash reads as unavailable.
                planned_hash[key] = nudge_context_fingerprint(preview)
                planned_cache[key] = recovered
                record_nudge_event(
                    key,
                    "held" if nudge_hold_reason(recovered, row.get("context"))
                    else "ready",
                    recovered,
                )
                return
            if suppressed:
                return
        evidence_fingerprint = nudge_evidence_fingerprint(preview, state)
        if state.get("assessed_fingerprint") == evidence_fingerprint:
            return
        recent = novel_context_lines(clean_context_lines(preview), state)
        if not recent:
            state["exhausted_reason"] = "no_new_evidence"
            state["assessed_fingerprint"] = evidence_fingerprint
            return
        h = nudge_context_fingerprint(preview)
        # `planned_cache[key] is not None` matters: toggling drafts off stores an
        # explicit None, and without this check toggling back on would hit the
        # unchanged-hash early return and never re-draft.
        if planned_hash.get(key) == h and planned_cache.get(key) is not None:
            return  # unchanged pane content — don't re-draft on every 5s poll
        # Deterministic gate BEFORE the LLM: only a stuck target whose cooldown
        # has expired is worth spending a model call on.
        if not should_nudge(row, state):
            return
        planned_hash[key] = h
        attempt = state["attempt"] + 1
        with draft_lock:
            if key in drafting_keys:
                return
            drafting_keys.add(key)
            record_nudge_event(key, "drafting")
        planned_cache.setdefault(key, None)
        threading.Thread(
            target=_background_draft,
            args=(key, row, recent[-NUDGE_EVIDENCE_LINES:], attempt, h, evidence_fingerprint),
            daemon=True,
        ).start()

    def refresh_context():
        nonlocal context_selected
        if not rows:
            return
        row = rows[selected]
        key = row.get("target") or row.get("id")
        context_selected = key
        _request_context(row)

    def _reap_selected(row):
        """Close one session and report it, shared by [x] and Enter.

        The confirm belongs to the caller, not here: [x] must confirm because it
        can force-close a session that never declared itself done, while Enter
        only ever reaches a row already marked reap-ready.
        """
        ok, detail = reap_session(row)
        if ok:
            row_key = row.get("target") or row.get("id")
            record_outcome(
                "terminal", target=row_key, outcome="reaped",
                engine=selected_engine.get(row_key),
            )
            _request_fleet_refresh()
            refresh_context()
        return ("reaped: " if ok else "reap failed: ") + detail[:100]

    def follow_pending(item):
        """Point the fleet cursor at the queue item under the queue cursor.

        The table row and the context pane are both driven by `selected`, so
        moving it is what makes the queue, the table and the preview describe
        one session instead of three. Without this, arrowing through the queue
        left the table and the pane frozen on whatever was selected before —
        the mouse already did this on click, the keyboard did not.

        A finished-work row recalled from the durable pile has no live pane and
        carries index=None; there is nothing to preview and nothing to scroll
        to, so the cursor stays put rather than moving somewhere arbitrary (and
        rather than being assigned None, which crashes the next row lookup).
        Staying put is the only safe move but it is not a silent one: the
        context panel is still describing whichever session the cursor was left
        on, which is not the one the queue is now pointing at, so it says so.
        """
        nonlocal selected, message
        if item is None:
            return
        if item.get("index") is None:
            message = (
                f"{item['row'].get('label', '?')} has already exited — no pane "
                "to show; [enter] clears it from the finished list"
            )
            return
        selected = item["index"]
        refresh_context()

    def refresh_fleet_drafts():
        """Queue drafts for every eligible pane, bounded by draft_slots."""
        if fixture_mode or not auto_draft:
            return
        for row in rows:
            key = row.get("target") or row.get("id")
            state = _nudge_state(key)
            if (
                planned_cache.get(key) is not None
                or key in drafting_keys
                or not should_nudge(row, state)
            ):
                continue
            # Context collection is deliberately selected-session only.  The
            # former fleet-wide synchronous capture loop could queue N x 8s
            # subprocess waits during every redraw and lock up the monitor.
            preview = context_cache.get(key)
            if preview is not None:
                _maybe_draft(row, preview)

    def _revalidate_for_send(key):
        """Resolve fresh status and pane context immediately before transport."""
        current_rows = rows if fixture_mode else collect_all()
        current_row = next(
            (
                row for row in current_rows
                if (row.get("target") or row.get("id")) == key
            ),
            None,
        )
        if current_row is None:
            reason = "session is no longer in the fleet"
            _clear_draft(key, reason)
            return None, reason
        preview = (
            current_row.get("preview", context_cache.get(key, ""))
            if fixture_mode
            else get_pane_context(current_row)
        )
        reason = nudge_revalidation_reason(
            current_row, planned_hash.get(key), preview
        )
        if reason:
            _clear_draft(key, reason)
            return None, reason
        context_cache[key] = preview
        return current_row, None

    refresh_context()
    _request_fleet_refresh()

    while True:
        now = time.time()
        try:
            _drain_io_results()
        except Exception as exc:  # noqa: BLE001 - render loop must stay alive
            detail = " ".join(str(exc).split())[:160] or type(exc).__name__
            refresh_pending = False
            refresh_error = f"refresh failed: {type(exc).__name__}: {detail}"
            message = refresh_error
        if now - last_refresh > REFRESH_SECONDS:
            _request_fleet_refresh()
            last_refresh = now
            selected = min(selected, max(0, len(rows) - 1))
            # Picks up what the unattended sweep did since the last tick. Doing
            # this only at startup made the fleet table a snapshot: the operator
            # watching shep would see whatever had happened before they opened
            # it and then nothing ever again, while the loop kept nudging the
            # same panes every five minutes behind the screen. Skipped under
            # fixtures, which must render the rows they were handed and nothing
            # from this machine's live state.
            if not fixture_mode:
                load_nudge_state(events_only=True)
            refresh_context()
            refresh_fleet_drafts()

        stdscr.erase()
        loading_frame += 1
        h, w = stdscr.getmaxyx()

        MIN_H, MIN_W = 18, 40
        if h < MIN_H or w < MIN_W:
            msg = terminal_too_small_message(w, h, MIN_W, MIN_H)
            try:
                stdscr.addstr(0, 0, msg[: max(0, w - 1)], curses.A_BOLD)
            except curses.error:
                pass
            safe_refresh(stdscr)
            try:
                key = stdscr.getch()
            except curses.error:
                key = -1
            if key in (ord("q"), 27):
                break
            continue

        for header_y, header_line in enumerate(
            commander_header(
                rows, w - 1, now - last_refresh, ascii_only, theme_name
            )
        ):
            header_attr = curses.A_BOLD | _ui_pair(4) if header_y == 0 else SOFT
            safe_addstr(
                stdscr, header_y, 0, header_line, header_attr, max_width=w - 1
            )
        # Fleet on the left, the selected session's own context on the right.
        # Everything from the tab bar down is bounded by `left_w` rather than
        # the terminal width so a long nudge cell cannot run under the context
        # column. `split` is None for the stacked layout, and then left_w is
        # simply the whole width and every bound below is unchanged.
        split = agents_split(w - 1, auto_split_index(w - 1) if split_auto else split_index)
        left_w = split[0] if split else w - 1
        layout = table_layout(left_w)
        header, _header_positions = format_table_line(
            layout, {key: label for key, label, _width in layout}, ascii_only
        )
        safe_addstr(
            stdscr, SHEP_TAB_Y, 0,
            shep_tab_bar(w - 1, "agents", ascii_only),
            curses.A_BOLD | _ui_pair(4), max_width=w - 1,
        )
        # The queue sits between the tabs and the fleet table, so everything
        # below shifts by its height. It collapses to nothing when the queue is
        # empty, which is why the offset is a variable rather than a constant.
        pending = pending_actions(rows)
        pending_sel = max(0, min(pending_sel, len(pending) - 1)) if pending else 0
        pending_focus = pending_focus and bool(pending)
        pending_visible_rows = pending_panel_visible_rows(pending_focus)
        panel = pending_panel_lines(
            pending, left_w, pending_sel, pending_focus, ascii_only,
        )
        panel_h = len(panel)
        selected_panel_y = (
            1 + pending_sel - pending_panel_start(
                len(pending), pending_sel, pending_visible_rows,
            )
            if pending_focus and pending else None
        )
        for panel_y, panel_line in enumerate(panel):
            panel_attr = curses.A_BOLD | _ui_pair(4) if panel_y == 0 else curses.A_NORMAL
            if panel_y == selected_panel_y:
                panel_attr = curses.A_REVERSE | curses.A_BOLD
            safe_addstr(
                stdscr, SHEP_TAB_Y + 1 + panel_y, 0, panel_line, panel_attr,
                max_width=left_w,
            )

        safe_addstr(
            stdscr, SHEP_TAB_Y + 1 + panel_h, 0, header,
            curses.A_BOLD | curses.A_UNDERLINE,
            max_width=left_w,
        )

        table_h = agents_table_height(len(rows), h, panel_h, split=bool(split))
        # scroll the table so the selected row is always on screen — without this
        # the highlight vanishes as soon as you move past the visible window.
        top = 0 if selected < table_h else selected - table_h + 1
        fleet_hits = []
        for i, row in enumerate(rows[top:top + table_h]):
            y = SHEP_TAB_Y + 2 + panel_h + i
            fleet_hits.append(RenderedHit(top + i, 0, y, max(1, left_w)))
            attr = fleet_row_attr((top + i) == selected, pending_focus)
            display_status = status_badge(row, ascii_only)
            nudge_text = nudge_row_text(
                row, planned_cache, verified_cache, drafting_keys, verifying_keys
            )
            activity_text = table_activity_text(row, nudge_text)
            source_visible = any(key == "source" for key, _label, _width in layout)
            values = table_row_values(
                row, activity_text, display_status, source_visible=source_visible,
            )
            line, positions = format_table_line(layout, values, ascii_only)
            # Every cell draws through safe_addstr with its own bound. These
            # used to be four raw addstr calls sharing one try/except, so a
            # single curses ERR — which safe_addstr exists to absorb, and which
            # pane text reaches through wide Unicode — truncated the line AND
            # skipped every later cell. The visible symptom was the selected
            # row losing its REPO column while the rest of the table was fine.
            safe_addstr(stdscr, y, 0, line, attr, max_width=left_w)
            if "status" in positions:
                status_x, status_width = positions["status"]
                safe_addstr(
                    stdscr, y, status_x,
                    _fit_cell(display_status, status_width, ascii_only),
                    attr | curses.A_BOLD | _ui_pair(status_color_pair_id(row)),
                    max_width=max(0, left_w - status_x),
                )
            badge = agent_badge_token(row, source_visible=source_visible)
            if badge and "agent" in positions:
                badge_x, _agent_width = positions["agent"]
                safe_addstr(
                    stdscr, y, badge_x, badge,
                    attr | curses.A_BOLD | _ui_pair(agent_badge_pair_id(row)),
                    max_width=max(0, left_w - badge_x),
                )
            if "activity" in positions:
                nudge_x, nudge_width = positions["activity"]
                safe_addstr(
                    stdscr, y, nudge_x,
                    _fit_cell(activity_text, nudge_width, ascii_only),
                    attr | curses.A_BOLD | _ui_pair(nudge_color_pair_id(nudge_text)),
                    max_width=max(0, min(nudge_width, left_w - nudge_x)),
                )
            # Repaint every column that follows the activity cell, last. That
            # cell carries raw pane text, and a glyph whose width
            # _char_columns undercounts makes the overlay run past its own cell
            # and blank whatever sits to its right — measured at 12 of 180
            # sampled rows once the cell became flex (83 columns of pane text
            # instead of a fixed 42), against 0 of 180 before. Drawing the
            # trailing columns after the overlay means they cannot be
            # clobbered by it, so the last column stops depending on the width
            # math being exactly right about somebody else's terminal output.
            keys = [key for key, _label, _width in layout]
            if "activity" in keys:
                separator = ASCII_TABLE_SEPARATOR if ascii_only else TABLE_SEPARATOR
                for key, _label, cell_width in layout[keys.index("activity") + 1:]:
                    cell_x, _ = positions[key]
                    start = cell_x - len(separator)
                    safe_addstr(
                        stdscr, y, start,
                        separator + _fit_cell(values.get(key, ""), cell_width, ascii_only),
                        attr, max_width=max(0, left_w - start),
                    )

        hidden = len(rows) - table_h
        if hidden > 0:
            try:
                visible_end = min(top + table_h, len(rows))
                hidden_text = (
                    f"sessions {top + 1}-{visible_end} of {len(rows)} | resize taller"
                    if ascii_only
                    else f"sessions {top + 1}-{visible_end} of {len(rows)} · resize taller for more"
                )
                stdscr.addstr(
                    SHEP_TAB_Y + 2 + panel_h + table_h, 0,
                    hidden_text[:left_w], SOFT,
                )
            except curses.error:
                pass
        # Where the context panel lives: beside the fleet when split, otherwise
        # the strip under the table it has always been. Both forms paint through
        # (ctx_x, ctx_y, ctx_w) and stop at ctx_bottom.
        if split:
            _left, ctx_x, ctx_w = split
            ctx_y = SHEP_TAB_Y + 1
            divider = "|" if ascii_only else "│"
            for divider_y in range(SHEP_TAB_Y + 1, h - 2):
                safe_addstr(stdscr, divider_y, left_w + 1, divider, SOFT, max_width=1)
        else:
            ctx_x, ctx_w = 0, w - 1
            # panel_h belongs in this sum. Without it the context rule was drawn
            # over the last rows of the fleet whenever the pending queue had
            # anything in it — the queue pushes the table down, but this offset
            # was still measuring from where the table used to start.
            ctx_y = SHEP_TAB_Y + 3 + panel_h + table_h
        ctx_bottom = h - 2  # exclusive; the two footer lines own everything below
        if refresh_pending and not rows:
            # Keep the first frame useful even when collection is waiting on a
            # slow or temporarily unavailable transport. The footer also gets
            # the indicator below, but this centered status card cannot be
            # lost to a narrow command legend.
            loading_lines = loading_panel_lines(loading_frame, ascii_only)
            panel_top = max(SHEP_TAB_Y + 3, (h - len(loading_lines)) // 2)
            for offset, loading_line in enumerate(loading_lines):
                visible = _ascii_text(loading_line) if ascii_only else loading_line
                loading_x = max(0, ((w - 1) - _text_columns(visible)) // 2)
                safe_addstr(
                    stdscr,
                    panel_top + offset,
                    loading_x,
                    visible,
                    curses.A_BOLD | _ui_pair(4),
                    max_width=max(0, (w - 1) - loading_x),
                )
        # A finished-work row recalled from the durable pile has no live pane, so
        # `follow_pending` deliberately leaves the fleet cursor where it was --
        # there is no row to move it to. The consequence was that the panel below
        # kept describing whatever session was selected BEFORE, so arrowing onto
        # a recalled row showed another session's live output under the recalled
        # one's name. Frozen would have been tolerable; mislabelled is not.
        queue_recall = (
            pending[pending_sel]
            if pending_focus and pending
            and pending[min(pending_sel, len(pending) - 1)].get("gone")
            else None
        )
        if queue_recall:
            _draw_recalled_context_panel(
                stdscr, queue_recall, ctx_x, ctx_y, ctx_w, ctx_bottom, ascii_only,
            )
        elif rows:
            sel_key = rows[selected].get("target") or rows[selected].get("id")
            label = agent_badge(rows[selected])
            queue_item = (
                pending[pending_sel]
                if pending_focus and pending
                and not pending[min(pending_sel, len(pending) - 1)].get("gone")
                else None
            )
            try:
                separator = " | " if ascii_only else " · "
                lifecycle = (
                    f"{separator}REAP READY [enter]" if rows[selected].get("reap_ready") else ""
                )
                if rows[selected].get("continuation"):
                    lifecycle += f"{separator}NEW MISSION [m]"
                lifecycle += f"{separator}[I] terminal"
                selected_position = f"{selected + 1}/{len(rows)}"
                selected_status = status_badge(rows[selected], ascii_only)
                panel_label = (
                    f"SELECTED {selected_position}{separator}{label}{separator}"
                    f"{selected_status}{separator}{sel_key}{lifecycle}"
                )
                stdscr.addstr(
                    ctx_y,
                    ctx_x,
                    panel_rule(panel_label, ctx_w, ascii_only),
                    curses.A_BOLD | _ui_pair(4),
                )
            except curses.error:
                pass
            preview = context_cache.get(sel_key, CONTEXT_LOADING)
            preview_lines = context_preview_segments(preview)
            planned = planned_cache.get(sel_key)
            displayed_plan = planned
            candidates = candidate_cache.get(sel_key, {})
            assessment = assessment_cache.get(sel_key, {})
            selected_nudge_state = nudge_row_text(
                rows[selected], planned_cache, verified_cache,
                drafting_keys, verifying_keys, assessment,
                selected_engine.get(sel_key),
            )
            plan_color = _ui_pair(nudge_color_pair_id(selected_nudge_state))
            if planned:
                category, reason = classify_risk(planned)
                quality_reason = nudge_quality_reason(
                    assessment, selected_engine.get(sel_key)
                )
                if quality_reason:
                    displayed_plan = f"[NEEDS REVIEW: {quality_reason}] {planned}"
                elif category != "safe_continuation":
                    verified_text, verdict = verified_cache.get(sel_key, (None, None))
                    if category in ("merge", "push") and verified_text == planned and verdict:
                        displayed_plan = f"[panel-verified safe: {reason}] {planned}"
                    elif category in ("merge", "push") and sel_key in verifying_keys:
                        displayed_plan = f"[verifying via codex-gw + claude-gw…] {planned}"
                    else:
                        displayed_plan = f"[NEEDS REVIEW: {reason}] {planned}"
            elif sel_key in drafting_keys:
                displayed_plan = "[drafting…]"
            last_nudge = nudge_event_detail(rows[selected])
            queue_detail = pending_action_detail_lines(queue_item, ctx_w, ascii_only)
            comparison_lines = []
            if candidates:
                scores = assessment.get("scores", {})
                op_mark = "*" if selected_engine.get(sel_key) == "operational" else " "
                intent_mark = "*" if selected_engine.get(sel_key) == "intent" else " "
                operational = candidates.get("operational") or "[abstained]"
                intent = candidates.get("intent") or "[abstained]"
                left = (
                    f"{op_mark} ACTION [{scores.get('operational', 0):3}]: "
                    f"{operational}"
                )
                right = (
                    f"{intent_mark} INTENT [{scores.get('intent', 0):3}]: {intent}"
                )
                if ctx_w >= 100:
                    half = max(1, (ctx_w - 4) // 2)
                    comparison_lines.append(
                        f"{_fit_cell(left, half)} │ {_fit_cell(right, half)}"
                    )
                else:
                    comparison_lines.extend((left, right))
                comparison_lines.append(
                    f"judge: {assessment.get('winner', 'none')} "
                    f"({assessment.get('source', 'pending')}) — "
                    f"{assessment.get('rationale', '')}"
                )
                comparison_lines.append(
                    f"intent limitation: {INTENT_ENGINE_LIMITATION}"
                )
            detail_count = (
                int(bool(last_nudge))
                + int(bool(displayed_plan))
                + len(queue_detail)
                + len(comparison_lines)
            )
            reserved = detail_count + int(detail_count > 0)
            avail = max(0, ctx_bottom - (ctx_y + 1) - reserved)
            shown = preview_lines[-avail:] if avail > 0 else []
            for j, segs in enumerate(shown):
                x = ctx_x
                for text, attr in segs:
                    if x >= ctx_x + ctx_w:
                        break
                    visible_text = _ascii_text(text) if ascii_only else text
                    visible_text = _clip_to_columns(visible_text, ctx_x + ctx_w - x)
                    try:
                        stdscr.addstr(ctx_y + 1 + j, x, visible_text, attr)
                    except curses.error:
                        pass
                    x += _text_columns(visible_text)
            detail_y = ctx_y + 1 + min(len(shown), avail) + 1
            for queue_line in queue_detail:
                safe_addstr(
                    stdscr, detail_y, ctx_x, queue_line,
                    curses.A_BOLD | _ui_pair(4), max_width=ctx_w,
                )
                detail_y += 1
            if last_nudge:
                try:
                    event = _NUDGE_EVENTS.get(sel_key, {})
                    event_color = _ui_pair(
                        nudge_color_pair_id(f"{event.get('status', '')}:")
                    )
                    stdscr.addstr(
                        detail_y, ctx_x, last_nudge[:ctx_w],
                        curses.A_BOLD | event_color,
                    )
                except curses.error:
                    pass
                detail_y += 1
            for comparison in comparison_lines:
                safe_addstr(
                    stdscr,
                    detail_y,
                    ctx_x,
                    comparison,
                    curses.A_BOLD,
                    max_width=ctx_w,
                )
                detail_y += 1
            if displayed_plan:
                safe_addstr(
                    stdscr,
                    detail_y,
                    ctx_x,
                    f"selected nudge: {displayed_plan}",
                    curses.A_BOLD | plan_color,
                    max_width=ctx_w,
                )

        fleet_safe, fleet_held = bulk_nudge_candidates(
            rows, planned_cache, verified_cache, assessment_cache, selected_engine
        )
        teaser = mission_teaser(cached_missions, ascii_only)
        status_message = (
            loading_indicator(loading_frame, ascii_only)
            if refresh_pending
            else refresh_error or message
        )
        safe_addstr(
            stdscr,
            h - 2,
            0,
            f"queue {len(fleet_safe)} safe / {fleet_held} held / {len(drafting_keys)} drafting · "
            f"{status_message} · drafted {NUDGES_DRAFTED} / sent {NUDGES_SENT}"
            + (f" · {teaser}" if teaser else ""),
            curses.A_NORMAL,
            max_width=w - 1,
        )
        safe_addstr(
            stdscr, h - 1, 0,
            command_footer(
                w - 1,
                len(fleet_safe),
                fleet_held,
                len(drafting_keys),
                status_message,
                ascii_only,
            ),
            curses.A_NORMAL, max_width=w - 1,
        )
        safe_refresh(stdscr)

        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key in (ord("q"), 27):
            break
        elif key == curses.KEY_MOUSE:
            try:
                mouse = read_mouse_event()
                if mouse.kind == "unsupported":
                    message = mouse.detail
                    continue
                wheel = -1 if mouse.kind == "wheel_up" else 1 if mouse.kind == "wheel_down" else 0
                if wheel:
                    # Routed by focus, not by where the pointer sits: a
                    # wheel-down carries no coordinates on ncurses 5, and
                    # routing the two directions differently would scroll two
                    # different lists depending on which way you turned it.
                    # This is the rule [j]/[k] already follows.
                    if pending_focus and pending:
                        pending_sel = scrolled(pending_sel, wheel, len(pending))
                        follow_pending(pending[pending_sel])
                    else:
                        selected = scrolled(selected, wheel, len(rows))
                        refresh_context()
                    continue
                target_tab = mouse_tab_target(
                    mouse.x, mouse.y, mouse.button_state, w - 1, ascii_only
                )
                if target_tab in {"beads", "missions", "logs"}:
                    open_tab(target_tab)
                    stdscr.nodelay(True)
                    stdscr.timeout(KEY_POLL_MS)
                    message = f"back from {target_tab}"
                    continue
                if split and mouse.x > left_w:
                    # A click in the context column is not a fleet click. It
                    # used to be — before the split every column at that y was
                    # the table — so the hit tests below only ever looked at y,
                    # and clicking the pane text silently moved the selection
                    # to whatever session shared its row. That is worth fixing
                    # on its own, and Enter now closes a reap-ready selection.
                    continue
                if mouse.button_state & (
                    curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED
                ):
                    hit = pending_panel_row_at_y(
                        mouse.y, panel_h, len(pending), pending_sel,
                        pending_visible_rows,
                    )
                    if hit is not None:
                        # Selects and focuses; it does not fire. A stray click
                        # must not merge a branch or close a session, and the
                        # queue's actions are exactly the ones worth a second
                        # keystroke. Enter is that keystroke.
                        pending_sel = hit
                        pending_focus = True
                        item = pending[hit]
                        follow_pending(item)
                        # An item whose pane has already exited has nothing to
                        # confirm and follow_pending has already explained why
                        # the fleet cursor did not move; overwriting that with
                        # "close? enter to confirm" would promise an action
                        # against a session that is no longer there.
                        if item.get("index") is not None:
                            message = (
                                f"{item['verb'].lower()}? enter to confirm — "
                                f"{item['summary'][:70]}"
                            )
                        continue
                clicked = rendered_hit_index(
                    fleet_hits, mouse.x, mouse.y, mouse.button_state
                )
                if clicked is not None:
                    selected = clicked
                    pending_focus = False
                    message = f"selected {rows[selected]['label']}"
                    refresh_context()
            except curses.error:
                pass
        elif key == ord("\t"):
            if pending:
                pending_focus = not pending_focus
                message = (
                    "queue focused — enter to act, tab to go back"
                    if pending_focus else "back to the fleet"
                )
            else:
                message = "nothing waiting on you"
        elif key in (ord("j"), curses.KEY_DOWN):
            # Routed by focus, not by a second keybinding: the operator should
            # not have to remember a different arrow for the shortlist.
            if pending_focus and pending:
                pending_sel = min(pending_sel + 1, len(pending) - 1)
                follow_pending(pending[pending_sel])
            else:
                selected = min(selected + 1, max(0, len(rows) - 1))
                refresh_context()
        elif key in (ord("k"), curses.KEY_UP):
            if pending_focus and pending:
                pending_sel = max(pending_sel - 1, 0)
                follow_pending(pending[pending_sel])
            else:
                selected = max(selected - 1, 0)
                refresh_context()
        elif key in (curses.KEY_ENTER, 10, 13) and pending_focus and pending:
            item = pending[min(pending_sel, len(pending) - 1)]
            # Always lands the fleet cursor on the pane first, whatever the
            # verb. Acting on something the table is not showing is how an
            # operator approves the wrong thing, and for GO the jump IS the
            # action. follow_pending absorbs the index=None case.
            follow_pending(item)
            if item.get("gone"):
                # Nothing to visit, approve, or close — the pane has already
                # exited. Acknowledging is the only action left, and it is what
                # takes the row out of the review queue.
                pending_focus = False
                cleared = clear_done(item["target"])
                message = (
                    f"{item['row'].get('label', '?')} reviewed — cleared from the "
                    "finished list" if cleared else "already cleared"
                )
            elif item["kind"] == "visit":
                pending_focus = False
                message = f"{item['row'].get('label', '?')}: {item['summary'][:90]}"
            elif item["kind"] == "approve":
                # Reuses the existing single-send path rather than a second
                # one, so the risk classifier, the quality gate, and the audit
                # receipt all still apply to a queue approval.
                ok, detail = send_nudge(
                    item["row"], item["summary"],
                    engine=selected_engine.get(item["target"]), path="pending",
                )
                message = nudge_result_message(ok, item["summary"], detail)
                if ok:
                    planned_cache[item["target"]] = None
                    candidate_cache.pop(item["target"], None)
                    record_nudge_event(item["target"], "sent", item["summary"], detail)
                refresh_context()
            else:
                # Closing is the one queue action that cannot be undone, so it
                # does not fire from here. It arms the existing [x] confirm,
                # which already debounces a held key and prints what it is
                # about to close.
                pending_focus = False
                message = (
                    f"{item['row'].get('label', '?')} is ready to close — "
                    "press [x] to confirm"
                )
        elif key in (curses.KEY_ENTER, 10, 13) and rows and rows[selected].get("reap_ready"):
            # Enter IS the consent. The row already says REAP READY — the agent
            # declared itself safe to close and its last output has been sitting
            # in the context panel the whole time the operator was arrowing onto
            # this row, so there is nothing a second keystroke would show them
            # that they have not already read. [x] keeps its confirm because it
            # can also force-close a session that never said it was done.
            message = _reap_selected(rows[selected])
            continue
        elif key in (curses.KEY_RIGHT, ord("l"), curses.KEY_ENTER, 10, 13) and rows:
            # Step into the session, the way you step into an agent in Claude
            # Code. [←] inside comes straight back here with the same row still
            # selected — no attach, no detach sequence, no lost keystrokes.
            run_session_view(stdscr, rows[selected], ascii_only)
            stdscr.nodelay(True)
            stdscr.timeout(KEY_POLL_MS)
            message = f"back from {session_name(rows[selected]) or 'session'}"
            refresh_context()
            continue
        elif key == ord("I") and rows:
            # Keep the hierarchy explicit even for the old deck shortcut: it
            # opens detail, where [i] is the deliberate input-mode action.
            run_session_view(stdscr, rows[selected], ascii_only)
            stdscr.nodelay(True)
            stdscr.timeout(KEY_POLL_MS)
            message = f"back from {session_name(rows[selected]) or 'session'}"
            refresh_context()
            continue
        elif key == ord("A") and rows:
            row = rows[selected]
            if row.get("status") != "asking":
                message = "no open question in this session"
                continue
            options = pane_question_options(
                capture_pane(row["source"], row.get("target"))
            )
            if not options:
                message = "the question box closed before it could be answered"
                continue
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0,
                "answer: "
                + "  ".join(f"[{number}] {text[:24]}" for number, text in options[:5])
                + "  other=cancel",
                curses.A_BOLD | _ui_pair(1),
                max_width=w - 1,
            )
            safe_refresh(stdscr)
            pressed = blocking_getch(stdscr)
            typed = chr(pressed) if 0 <= pressed < 128 else ""
            chosen = next((opt for opt in options if opt[0] == typed), None)
            if not chosen:
                message = "answer cancelled"
                continue
            # The pane may have moved on since the option list was read, and one
            # keystroke here can approve a destructive tool call — so confirm the
            # exact text about to be accepted, never just its number.
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0,
                f"Answer {row['label']} with [{chosen[0]}. {chosen[1][:40]}]? "
                "[Y] send / other=cancel",
                curses.A_BOLD | _ui_pair(3),
                max_width=w - 1,
            )
            safe_refresh(stdscr)
            if blocking_getch(stdscr) != ord("Y"):
                message = "answer cancelled"
                continue
            ok, detail = answer_session(row, chosen[0], chosen[1])
            message = ("answered: " if ok else "answer failed: ") + detail[:100]
            if ok:
                _request_fleet_refresh()
                refresh_context()
            continue
        elif key == ord("r"):
            _request_fleet_refresh()
            last_refresh = time.time()
            message = "refresh requested"
            refresh_context()
            refresh_fleet_drafts()
        elif key == ord("a"):
            auto_draft = not auto_draft
            message = f"planned-nudge drafting: {'on' if auto_draft else 'off'} (applies to every session)"
            refresh_context()
            refresh_fleet_drafts()
        elif key == ord("t"):
            theme_name = apply_theme(next_theme(theme_name))
            message = f"theme: {theme_name}"
        elif key in (ord("["), ord("]")):
            # The divider, not a mode toggle: [ walks it left until the context
            # goes back under the table, ] walks it right. The first press also
            # ends auto-placement — from here the operator owns the position,
            # and a resize must not overrule what they just chose.
            step = 1 if key == ord("]") else -1
            if split_auto:
                split_index = auto_split_index(w - 1)
                split_auto = False
            if split_index is None:
                split_index = 0 if step > 0 else None
            else:
                moved = split_index + step
                split_index = None if moved < 0 else min(moved, len(AGENTS_SPLIT_RATIOS) - 1)
            if split_index is None:
                message = "context panel: below the fleet"
            elif agents_split(w - 1, split_index):
                share = int(AGENTS_SPLIT_RATIOS[split_index] * 100)
                message = f"context panel: beside the fleet ({share}/{100 - share})"
            else:
                message = (
                    f"terminal too narrow to split — needs {AGENTS_SPLIT_MIN_WIDTH}"
                    f" columns, has {w - 1}"
                )
        elif key == ord("i") and rows:
            queued, message = _dispatch_intent_draft(rows[selected])
            if queued:
                message += " — press n when ready to review/send"
            continue
        elif key == ord("x") and rows:
            row = rows[selected]
            ready = bool(row.get("reap_ready"))
            warning = (
                f"Reap {row['label']} now? Press [x] again to confirm / other=cancel"
                if ready
                else f"NOT marked safe to close. FORCE reap {row['label']}? Press [x] again / other=cancel"
            )
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0, warning,
                curses.A_BOLD | _ui_pair(3),
                max_width=w - 1,
            )
            safe_refresh(stdscr)
            if not confirms_with_same_key(blocking_getch(stdscr), ord("x")):
                message = "reap cancelled"
                continue
            message = _reap_selected(row)
            continue
        elif key == ord("m") and rows:
            row = rows[selected]
            target = row.get("target") or row.get("id")
            continuation = row.get("continuation")
            if not continuation:
                message = "no NEW_MISSION declaration in this session"
                continue
            if target in _CONTINUATIONS_SPAWNED:
                message = "continuation already spawned from this session"
                continue
            curses.curs_set(1)
            brief = blocking_edit_line(stdscr, h - 1, "mission> ", continuation, w - 1)
            curses.curs_set(0)
            if not brief or not brief.strip():
                message = "new mission cancelled"
                continue
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr, h - 1, 0,
                "Spawn this follow-up in a NEW Herdr session? [Y] spawn / other=cancel",
                curses.A_BOLD | _ui_pair(1),
                max_width=w - 1,
            )
            safe_refresh(stdscr)
            if blocking_getch(stdscr) != ord("Y"):
                message = "new mission cancelled"
                continue
            ok, detail = spawn_continuation(row, brief.strip())
            if ok:
                _CONTINUATIONS_SPAWNED.add(target)
            message = ("mission spawned: " if ok else "mission failed: ") + detail[:100]
            continue
        elif key == ord("M"):
            open_tab("missions")
            stdscr.nodelay(True)
            stdscr.timeout(KEY_POLL_MS)
            message = "back from missions"
            continue
        elif key in (ord("2"), ord("b")):
            open_tab("beads")
            stdscr.nodelay(True)
            stdscr.timeout(KEY_POLL_MS)
            message = "back from beads"
            continue
        elif key == ord("3"):
            open_tab("missions")
            stdscr.nodelay(True)
            stdscr.timeout(KEY_POLL_MS)
            message = "back from missions"
            continue
        elif key == ord("4"):
            open_tab("logs")
            stdscr.nodelay(True)
            stdscr.timeout(KEY_POLL_MS)
            message = "back from logs"
            continue
        elif key == ord("N") and rows:
            candidates, held = bulk_nudge_candidates(
                rows, planned_cache, verified_cache, assessment_cache, selected_engine
            )
            if not candidates:
                message = (
                    f"fleet queue: no safe nudges ready · {held} held · "
                    f"{len(drafting_keys)} still drafting"
                )
                continue
            safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
            safe_addstr(
                stdscr,
                h - 1,
                0,
                f"Send {len(candidates)} safe fleet nudges? {held} held for review · [Y] send / other=cancel",
                curses.A_BOLD | _ui_pair(1),
                max_width=w - 1,
            )
            safe_refresh(stdscr)
            if blocking_getch(stdscr) != ord("Y"):
                message = "fleet send cancelled"
                continue
            sent = 0
            failed = 0
            invalidated = 0
            for row, planned in candidates:
                key_for_row = row.get("target") or row.get("id")
                current_row, stale_reason = _revalidate_for_send(key_for_row)
                if stale_reason:
                    invalidated += 1
                    continue
                record_outcome(
                    "selected", target=key_for_row,
                    engine=selected_engine.get(key_for_row), mode="fleet",
                    text=planned, draft=planned,
                )
                ok, _detail = send_nudge(
                    current_row, planned,
                    engine=selected_engine.get(key_for_row), path="fleet",
                )
                if ok:
                    sent += 1
                    planned_cache[key_for_row] = None
                    candidate_cache.pop(key_for_row, None)
                    assessment_cache.pop(key_for_row, None)
                    selected_engine.pop(key_for_row, None)
                else:
                    failed += 1
            message = (
                f"fleet send: {sent} sent / {failed} failed / "
                f"{held} held / {invalidated} stale"
            )
            refresh_context()
            continue
        elif key == ord("n") and rows:
            sel_key = rows[selected].get("target") or rows[selected].get("id")
            planned = planned_cache.get(sel_key)
            prefill = ""
            candidates = candidate_cache.get(sel_key, {})
            available_candidates = {
                name: text for name, text in candidates.items() if text
            }
            if len(available_candidates) > 1:
                safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
                safe_addstr(
                    stdscr,
                    h - 1,
                    0,
                    "choose candidate: [o] ACTION · [i] INTENT · other=cancel",
                    curses.A_BOLD,
                    max_width=w - 1,
                )
                safe_refresh(stdscr)
                engine_key = blocking_getch(stdscr)
                requested = {
                    ord("o"): "operational",
                    ord("O"): "operational",
                    ord("i"): "intent",
                    ord("I"): "intent",
                }.get(engine_key)
                if not requested:
                    message = "candidate selection cancelled"
                    continue
                engine, planned = select_candidate(
                    candidates,
                    assessment_cache.get(sel_key),
                    requested=requested,
                )
                if not planned:
                    message = f"{requested} engine abstained — not selected"
                    continue
                selected_engine[sel_key] = engine
                planned_cache[sel_key] = planned
                record_outcome(
                    "selected", target=sel_key, engine=engine, mode="manual",
                    text=planned, draft=planned,
                )
                verified_cache.pop(sel_key, None)
                category, reason = classify_risk(planned)
                if category in ("merge", "push"):
                    recent = clean_context_lines(context_cache.get(sel_key, ""))[-NUDGE_EVIDENCE_LINES:]
                    _dispatch_verify(sel_key, planned, category, reason, recent)
            if planned:
                safe_addstr(stdscr, h - 1, 0, " " * (w - 1), max_width=w - 1)
                safe_addstr(
                    stdscr,
                    h - 1,
                    0,
                    "[n] send · [d] AI redraft · [e] replace text · other=cancel",
                    max_width=w - 1,
                )
                safe_refresh(stdscr)
                choice = blocking_getch(stdscr)
                if choice in (ord("n"), ord("N")):
                    # The red HELD/NEEDS REVIEW label is the warning. Opening the
                    # exact draft with the first `n` and pressing `n` again is the
                    # human approval; never demand a redundant third keypress.
                    current_row, stale_reason = _revalidate_for_send(sel_key)
                    if stale_reason:
                        message = f"nudge cancelled: {stale_reason}"
                        refresh_context()
                        continue
                    ok, detail = send_nudge(
                        current_row, planned,
                        engine=selected_engine.get(sel_key), path="single",
                    )
                    message = nudge_result_message(ok, planned, detail)
                    if ok:
                        planned_cache[sel_key] = None
                        candidate_cache.pop(sel_key, None)
                        assessment_cache.pop(sel_key, None)
                        selected_engine.pop(sel_key, None)
                    refresh_context()
                    continue
                elif choice in (ord("d"), ord("D")):
                    # Redraft: clear the cached plan + its hash so the background
                    # drafter treats this like fresh context and drafts again.
                    # Also reset the per-target cooldown — otherwise should_nudge()
                    # keeps blocking the next background draft until the existing
                    # 60-300s backoff window (set by the PREVIOUS draft/send) expires,
                    # so "redrafting…" shows but nothing new ever appears.
                    planned_cache[sel_key] = None
                    candidate_cache.pop(sel_key, None)
                    assessment_cache.pop(sel_key, None)
                    selected_engine.pop(sel_key, None)
                    planned_hash.pop(sel_key, None)
                    verified_cache.pop(sel_key, None)
                    _nudge_state(sel_key)["next_at"] = 0.0
                    message = "redrafting…"
                    refresh_context()
                    continue
                elif choice in (ord("e"), ord("E")):
                    # Replacement starts clean. The original was visible in the
                    # red row/context; erasing it manually is needless friction.
                    prefill = ""
                else:
                    message = "cancelled"
                    continue
            curses.curs_set(1)
            text = blocking_edit_line(
                stdscr,
                h - 1,
                "nudge> ",
                prefill,
                w - 1,
            )
            curses.curs_set(0)
            if text is None:
                message = "edit cancelled"
                continue
            if not text.strip():
                message = "empty nudge — not sent"
                continue
            if planned:
                record_outcome(
                    "edited", target=sel_key, engine=selected_engine.get(sel_key),
                    **outcome_edit_fields(planned, text),
                )
            ok, detail = send_nudge(
                rows[selected], text,
                engine=selected_engine.get(sel_key), path="single",
            )
            message = nudge_result_message(ok, text, detail)
            if ok:
                planned_cache[sel_key] = None
                candidate_cache.pop(sel_key, None)
                assessment_cache.pop(sel_key, None)
                selected_engine.pop(sel_key, None)
                verified_cache.pop(sel_key, None)
            refresh_context()


# --- Headless sweep ----------------------------------------------------------

def sweep(send=False, rows=None):
    """One nudge pass with nobody sitting in curses. -> (results, held, escalated).

    The TUI only drafts while an operator is watching it, which is why the
    outcome log held 3 drafts and 0 sends across its first week: the nudge
    engine could not be tuned because it was never exercised. This runs the
    same pipeline headless — same deterministic gate (`should_nudge`), same
    drafter, same risk classifier, same single `send_nudge` path.

    Auto-send is opt-in and delegated to `bulk_nudge_candidates` with an empty
    verified cache, so it can only ever release `safe_continuation` drafts.
    merge / push / send_gated / destructive / unknown stay held for a human
    exactly as they do in the TUI — this widens WHEN nudges happen, never WHAT
    may be sent without review.
    """
    # Load BEFORE collecting: collect_all() runs update_stall, which is what
    # legitimately clears the ladder when a pane has actually moved on.
    persist = rows is None
    if persist:
        load_nudge_state()
        rows = collect_all()
    planned = {}
    escalated = []
    # Ask Herdr once per pass, not once per pane. None means the dependency
    # could not answer and therefore must fail open.
    live = _live_panes_or_none()
    jobs = []
    for row in rows:
        key = row.get("target") or row.get("id")
        state = _nudge_state(key)
        if state.get("exhausted_reason") == "needs_human":
            # A destroyed pane cannot be waiting for the operator. Suppress
            # only when this host positively tracked the target and Herdr
            # positively reports it gone; foreign or unknown targets escalate.
            if (
                live is not None
                and escalation_guard is not None
                and not escalation_guard.should_escalate(key, live)
            ):
                state["handoff_announced"] = True
                continue
            handoff_reason = human_handoff_reason(state)
            if infra_blocker(handoff_reason) and infra_probe_healthy():
                # The network healed without the operator lifting a finger, so
                # "waiting on a human" is now the wrong state to be in: this is
                # exactly the pane that would have sat parked for days after
                # the 2026-09-07 tunnel outage recovered. Release it back into
                # the ladder and let this same pass draft for it.
                release_infra_blocked(key, handoff_reason)
                state = _nudge_state(key)
            else:
                # Reported every pass, announced only once. The announcement is
                # a one-shot event; needing a human is a standing condition, and
                # a pane that stays stranded has to keep appearing in the
                # report or the log falls silent again while the pane still
                # waits.
                escalated.append((row, handoff_reason))
                # Restated on the fleet table for the same reason. This is the
                # strongest signal shep produces -- "stop reading, this one is
                # yours" -- and it was the one the NUDGE column left blank,
                # because a handoff records no draft and the column only ever
                # showed drafts.
                record_nudge_event(
                    key, "needs human", detail=handoff_reason,
                )
                if not state.get("handoff_announced"):
                    # Announced on the same channel as an autonomous send. The
                    # unattended loop is the whole reason this matters: with
                    # nobody in the TUI, giving up quietly is indistinguishable
                    # from having nothing to say, and the pane waits forever.
                    state["handoff_announced"] = True
                    post_telemetry(
                        "handoff", row,
                        detail=f"{handoff_reason}; needs a human",
                        activity=row.get("context") or "",
                        attempt=state.get("attempt"),
                    )
                    # Tied to the announcement, not to the report, so it fires
                    # once per pane. The report has to repeat every pass to
                    # keep a stranded pane visible in the log; a banner that
                    # repeated the same way would be a notification every five
                    # minutes until the operator gave up on all of them.
                    notify_operator(
                        f"{row.get('label', '?')} needs you",
                        handoff_reason,
                    )
                    # The escalation the 2026-09-07 postmortem found missing:
                    # the banner and the log line were the entire surface, and
                    # neither leaves the workstation. One rare DM per handoff —
                    # the same one-shot gate as the banner, so no spam.
                    post_escalation(escalation_message(row, handoff_reason))
        if not should_nudge(row, state):
            continue
        raw_context = get_pane_context(row)
        recent = clean_context_lines(raw_context)
        if not recent:
            continue
        # Preempts drafting: a 429 did not leave a gap for a better-worded
        # instruction, it dropped a correct one. Re-send that exact text. It
        # still flows through the same risk and quality gates below, so
        # `merge it, force it through` stays held for a human just as it would
        # if the drafter had proposed it.
        recovered, suppressed = rate_limit_recovery(row, state, raw_context, recent)
        if suppressed:
            continue
        if recovered:
            planned[key] = recovered
            continue
        evidence_fingerprint = nudge_evidence_fingerprint(raw_context, state)
        if state.get("assessed_fingerprint") == evidence_fingerprint:
            proposal = state.get("proposed")
            if (
                isinstance(proposal, dict)
                and proposal.get("status") == "send_failed"
                and state.get("send_failures", 0) < MAX_SEND_FAILURES
                and proposal.get("text")
            ):
                row["context"] = proposal.get("context") or ""
                planned[key] = proposal["text"]
            else:
                state["exhausted_reason"] = "no_new_evidence"
                record_outcome(
                    "suppressed", target=key, engine="operational",
                    reason="no_new_evidence",
                )
            continue
        recent = novel_context_lines(recent, state)
        if not recent:
            state["exhausted_reason"] = "no_new_evidence"
            state["assessed_fingerprint"] = evidence_fingerprint
            if not state.get("last_sent"):
                state["proposed"] = {
                    "status": "suppressed",
                    "reason": "no_new_evidence",
                    "at": time.time(),
                }
            record_outcome(
                "suppressed", target=key, engine="operational",
                reason="no_new_evidence",
            )
            continue
        # The automatic quality gate must judge the same bounded context that
        # produced the candidate, rather than a stale summary from collection.
        row["context"] = "\n".join(recent[-NUDGE_EVIDENCE_LINES:])
        jobs.append((key, row, state, recent, state["attempt"] + 1, evidence_fingerprint))

    # Drafts run side by side, results are applied in fleet order below. One
    # pane at a time was sum-of-latencies: five nudgeable panes at 25-45s each
    # is 125-225s of the control loop's 240s budget for the whole sweep, and on
    # 2026-09-10 two of five drafts were cut off at the timeout for exactly that
    # reason. Every job's state and row were fixed above, so the only thing the
    # threads share is the read-only fleet snapshot the prompt is rendered from.
    def _draft(job):
        key, row, state, recent, attempt, _fingerprint = job
        failures = []
        raw = llm_draft_nudge(
            row, recent, attempt,
            prior=state.get("prior_nudges"),
            stalled_for=stalled_seconds(key),
            fleet_rows=rows,
            failures=failures,
        )
        return raw, failures

    if jobs:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(SWEEP_DRAFT_WORKERS, len(jobs))
        ) as pool:
            drafted = list(pool.map(_draft, jobs))
    else:
        drafted = []
    for (key, row, state, recent, attempt, evidence_fingerprint), (
        raw_draft, draft_failures,
    ) in zip(jobs, drafted):
        # Named, not assumed. A measured gateway answers this prompt in ~4s and
        # survived ten concurrent drafts, so "gateway_unavailable" was the wrong
        # label for most of what it counted -- it just happened to be the only
        # one the code could emit.
        draft_failure = draft_failures[0] if draft_failures else "gateway_unavailable"
        blocked_on_operator = needs_human_request(raw_draft)
        if blocked_on_operator:
            # Ends the pane's nudging for good, on the drafter's word alone and
            # without waiting out the ladder. The ladder measures failure by
            # repetition, which cannot see this: a pane waiting on a credential
            # will absorb all three nudges and look no different from a slow
            # one. The drafter is the only part of shep that reads the pane and
            # can say the blocker is not addressable by typing.
            state["exhausted_reason"] = "needs_human"
            state["needs_human_reason"] = blocked_on_operator
            state["assessed_fingerprint"] = evidence_fingerprint
            # Reported on the pass that finds it, not the next one. The block at
            # the top of the loop only sees panes already carrying the flag.
            escalated.append((row, blocked_on_operator))
            # On the pass that finds it, not the next one -- same reason the
            # report does it here. Five minutes is a long time to leave the
            # freshest handoff off the screen the operator is watching.
            record_nudge_event(key, "needs human", detail=blocked_on_operator)
            record_outcome(
                "terminal", target=key, engine="operational",
                outcome="human_handoff", reason="blocked_on_operator",
            )
            continue
        # The reason, not just the fact. Three days of telemetry recorded 233
        # abstentions as one undifferentiated `explicit_no_nudge`, which is
        # nearly half of every draft attempt and said nothing about why — so
        # there was no way to tell a prompt that is too cautious from a fleet
        # that genuinely had nothing to do. The engine now names which rule
        # fired and it is recorded verbatim.
        abstained_because = abstention_reason(raw_draft)
        explicit_abstention = abstained_because is not None
        draft = operational_candidate_or_fallback(
            raw_draft,
            row, recent,
        )
        record_outcome(
            "drafted", target=key, engine="operational", present=bool(draft),
            attempt=attempt,
            **({"text": draft} if draft else {
                "reason": (
                    f"no_nudge:{abstained_because}" if explicit_abstention
                    else draft_failure
                ),
            }),
        )
        if not draft:
            if explicit_abstention:
                state["draft_failures"] = 0
                state["exhausted_reason"] = "abstained"
                state["assessed_fingerprint"] = evidence_fingerprint
                if not state.get("last_sent"):
                    state["proposed"] = {
                        "status": "abstained",
                        "context": row.get("context"),
                        "at": time.time(),
                    }
                record_outcome(
                    # Prefixed rather than flat. The granular reason was landing
                    # only on `drafted`, while the outcome report groups on
                    # `abstained` -- so the whole point of asking the engine to
                    # name its rule was invisible in the one place it is read.
                    # The prefix keeps existing `explicit_no_nudge` grouping
                    # working for reports that match on it.
                    "abstained", target=key, engine="operational",
                    reason=f"explicit_no_nudge:{abstained_because}",
                )
            else:
                failures = note_draft_failure(state)
                record_outcome(
                    "draft_failed", target=key, engine="operational",
                    reason=draft_failure,
                    attempt=failures,
                )
            continue
        state["draft_failures"] = 0
        state["assessed_fingerprint"] = evidence_fingerprint
        if is_repeat_nudge(draft, state):
            # Re-sending the same instruction to a pane that already ignored it
            # is noise, not escalation — the ladder is in the prompt, not
            # repetition. Catches rewordings, not just byte-identical repeats.
            state["exhausted_reason"] = "duplicate"
            state["proposed"] = {
                "text": draft,
                "status": "suppressed",
                "reason": "duplicate",
                "context": row.get("context"),
                "at": time.time(),
            }
            record_outcome(
                "suppressed", target=key, engine="operational", reason="duplicate"
            )
            continue
        state["attempt"] = attempt
        remember_nudge(state, draft)
        state["next_at"] = time.time() + NUDGE_BACKOFF_SECONDS[
            min(attempt, len(NUDGE_BACKOFF_SECONDS)) - 1
        ]
        state["proposed"] = {
            "text": draft,
            "status": "queued",
            "category": classify_risk(draft)[0],
            "context": row.get("context"),
            "at": time.time(),
        }
        planned[key] = draft
        record_outcome(
            "recommended", target=key, engine="operational", mode="sweep",
            text=draft, draft=draft,
            # Same gate verdict the interactive path records. Without it every
            # swept draft counted as one that passed the gate, so the report
            # understated exactly the rule that was blocking the sweep.
            reason=nudge_content_quality_reason(draft, row.get("context")),
        )
    candidates, _held_count = bulk_nudge_candidates(rows, planned, {})
    # Held drafts are the ones a human actually has to rule on, so a bare count
    # makes the only reviewable output unreviewable. Carry the text and the
    # reason it was withheld instead.
    cleared = {id(row) for row, _text in candidates}
    row_by_key = {(r.get("target") or r.get("id")): r for r in rows}
    held = []
    for key, text in planned.items():
        row = row_by_key.get(key)
        if not row or id(row) in cleared:
            continue
        category, _risk_reason = classify_risk(text)
        reason = nudge_hold_reason(text, row.get("context"))
        proposal = _nudge_state(key).get("proposed")
        if isinstance(proposal, dict) and proposal.get("text") == text:
            proposal["status"] = "held"
            proposal["reason"] = reason
        held.append((row, text, category, reason))
        # A held draft is the one output of an unattended pass that a human has
        # to rule on, and the TUI is where that human sits. Without this the
        # sweep's holds existed only in the loop's log file, so the operator
        # watching the fleet table saw "-" on the very rows waiting for them.
        record_nudge_event(key, "held", text, reason)
    results = []
    fresh_rows = None
    if send and persist:
        # The scheduled process may spend several seconds drafting. Recollect
        # once immediately before any transport so a pane that resumed,
        # exited, or changed owners cannot receive a stale draft.
        try:
            fresh_rows = {
                (row.get("target") or row.get("id")): row
                for row in collect_all()
            }
        except Exception:  # noqa: BLE001 - fail closed at the send boundary
            fresh_rows = {}
    for row, text in candidates:
        key = row.get("target") or row.get("id")
        if not send:
            results.append((row, text, None, "dry-run"))
            continue
        if fresh_rows is not None:
            current_row = fresh_rows.get(key)
            state = _nudge_state(key)
            proposed = state.get("proposed")
            fresh_context = get_pane_context(current_row) if current_row else ""
            stale_reason = "session is no longer in the fleet" if current_row is None else None
            if current_row is not None:
                if current_row.get("status") not in NUDGEABLE:
                    stale_reason = f"session is now {current_row.get('status') or 'unknown'}"
                elif current_row.get("reap_ready"):
                    stale_reason = "session is ready to reap"
                elif (
                    state.get("assessed_fingerprint")
                    and nudge_evidence_fingerprint(fresh_context, state)
                    != state.get("assessed_fingerprint")
                ):
                    stale_reason = "session context changed"
            if stale_reason:
                state["assessed_fingerprint"] = None
                state["next_at"] = 0.0
                if isinstance(proposed, dict) and proposed.get("text") == text:
                    proposed["status"] = "invalidated"
                    proposed["reason"] = stale_reason
                record_nudge_event(key, "invalidated", text, stale_reason)
                record_outcome("invalidated", target=key, reason=stale_reason)
                results.append((row, text, False, f"stale draft: {stale_reason}"))
                continue
            row = current_row
        record_outcome(
            "selected", target=key, engine="operational", mode="sweep",
            text=text, draft=text,
        )
        ok, detail = send_nudge(
            row, text, mode="auto", engine="operational", path="sweep",
        )
        state = _nudge_state(key)
        if ok:
            state["send_failures"] = 0
        else:
            failures = note_send_failure(state)
            proposal = state.get("proposed")
            if isinstance(proposal, dict) and proposal.get("text") == text:
                proposal["status"] = "send_failed"
                proposal["failure_attempt"] = failures
        category = classify_risk(text)[0]
        if ok:
            # Only autonomous sends are announced. A nudge the operator typed or
            # approved in the TUI is already known to them; echoing it back is
            # noise that would bury the unattended actions worth reviewing.
            post_telemetry(
                "nudged", row, detail=text, activity=row.get("context") or "",
                attempt=_nudge_state(key).get("attempt"), category=category,
            )
        results.append((row, text, ok, detail))
    if persist:
        save_nudge_state({r.get("target") or r.get("id") for r in rows})
    if send and digest_due():
        # Gated on send so a manual dry-run `--sweep` cannot silently consume
        # the day's digest and leave the unattended pass with nothing to say.
        line = send_daily_digest(escalated)
        if line:
            print(line)
    return results, held, escalated


def render_sweep(results, held, send, escalated=()):
    lines = []
    for row, text, ok, detail in results:
        mark = "DRY-RUN" if ok is None else ("SENT" if ok else f"FAILED ({detail})")
        lines.append(f"{mark:<10} {row.get('label', '?'):<16} {repo_name(row.get('cwd'))}")
        lines.append(f"           {text}")
    for row, text, category, reason in held:
        lines.append(
            f"{'HELD':<10} {row.get('label', '?'):<16} {repo_name(row.get('cwd'))}"
            f"  [{category}: {reason}]"
        )
        lines.append(f"           {text}")
    for row, reason in escalated:
        # No draft to print: the point of the row is that there is nothing left
        # worth typing. Silence here was the bug — an escalated pane skipped the
        # loop exactly like a pane the drafter abstained on, so the report read
        # "0 ready to send, 0 held" while a session sat stranded.
        lines.append(
            f"{'NEEDS-HUMAN':<10} {row.get('label', '?'):<16} "
            f"{repo_name(row.get('cwd'))}"
            f"  [{reason}]"
        )
    verb = "sent" if send else "ready to send"
    summary = f"-- {len(results)} {verb}, {len(held)} held for review"
    if escalated:
        needs = "needs" if len(escalated) == 1 else "need"
        summary += f", {len(escalated)} {needs} a human"
    lines.append(f"{summary} --")
    return "\n".join(lines)


def run_control_pass(args):
    """Run one headless pass; all mutation remains behind existing transports."""
    try:
        report = control_once(
            collect_all,
            send=lambda row, text: send_nudge(
                row, text, mode="auto", audit=False, path="control",
            ),
            reap=lambda row: reap_session(row, mode="auto", audit=False),
            ledger_path=args.action_log,
            state_path=args.control_state,
            lock_path=args.control_lock,
            auto_nudge=args.auto_nudge,
            auto_reap=args.auto_reap,
            dry_run=args.dry_run,
            max_actions=args.max_actions,
        )
    except ControlBusy as exc:
        print(json.dumps({"status": "busy", "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def run_capacity_plan(as_json=False, summary=False):
    """Print one read-only capacity plan from Shep's canonical sources."""
    try:
        try:
            from shep_capacity import collect_cycle, render_text, summary_payload
        except ImportError:  # pragma: no cover - package imports differ
            from scripts.shep_capacity import collect_cycle, render_text, summary_payload

        cycle = collect_cycle(
            lambda: afk_candidates("all"),
            list_missions,
            afk.score_mission,
            herdr_ctl=HERDR_CTL,
        )
    except (OSError, RuntimeError, TypeError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    if as_json:
        payload = summary_payload(cycle) if summary else cycle
        print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    else:
        print(render_text(cycle))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-json", action="store_true",
                         help="print collected rows as JSON and exit (no curses)")
    parser.add_argument("--control-once", action="store_true",
                        help="run one bounded headless control pass and exit")
    parser.add_argument("--auto-nudge", action="store_true",
                        help="allow safe Herdr continuation nudges during control pass")
    parser.add_argument("--auto-reap", action="store_true",
                        help="allow explicit SAFE_TO_CLOSE Herdr reaping during control pass")
    parser.add_argument("--dry-run", action="store_true",
                        help="plan a control pass without sends, closes, state, or ledger writes")
    parser.add_argument("--max-actions", type=int, default=3,
                        help="maximum actions in one control pass (hard capped at 3)")
    parser.add_argument("--action-log", help="Shep action ledger JSONL path")
    parser.add_argument("--control-state", help="persistent control cooldown state path")
    parser.add_argument("--control-lock", help="singleton control lock path")
    parser.add_argument(
        "--snapshot", action="store_true",
        help="print the operator panel list, including Happy headless sessions",
    )
    parser.add_argument(
        "--snapshot-json", action="store_true",
        help="print the lossless operator snapshot as JSON",
    )
    parser.add_argument(
        "--propose", action="store_true",
        help="with --snapshot, draft and persist current safe/risky nudge proposals",
    )
    parser.add_argument(
        "--deliver", action="store_true",
        help="with --snapshot, deliver only proposals classified safe_continuation",
    )
    parser.add_argument(
        "--theme",
        choices=THEME_NAMES,
        default=normalize_theme(
            os.environ.get("SHEP_THEME", "classic")
        ),
        help="appearance theme (also SHEP_THEME; press 't' to cycle)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="render deterministic sample sessions for terminal checks",
    )
    parser.add_argument(
        "--sweep", action="store_true",
        help="headless nudge pass (no curses); drafts only unless --send is given",
    )
    parser.add_argument(
        "--send", action="store_true",
        help="with --sweep, auto-send drafts the risk gate calls a safe continuation",
    )
    parser.add_argument(
        "--release", metavar="TARGET", nargs="+",
        help="clear the needs-a-human latch on these panes (fnmatch globs; '*' for all)",
    )
    parser.add_argument(
        "--mission-create", metavar="GOAL",
        help="queue a mission in Shep's canonical store; does not launch it",
    )
    parser.add_argument(
        "--mission-list", action="store_true",
        help="print Shep's canonical mission store",
    )
    parser.add_argument(
        "--capacity-plan", action="store_true",
        help="print one read-only capacity-aware mission plan",
    )
    parser.add_argument(
        "--capacity-plan-summary", action="store_true",
        help="with --capacity-plan, print bounded loop telemetry instead of the full plan",
    )
    parser.add_argument("--mission-mode", choices=("inline", "fleet"), default="fleet")
    parser.add_argument("--mission-base", default="develop")
    parser.add_argument(
        "--afk", action="store_true",
        help="away mode: rank the missions worth leaving running unattended",
    )
    parser.add_argument(
        "--go", action="store_true",
        help="with --afk, launch the top --count missions without review",
    )
    parser.add_argument(
        "--count", type=int, default=AFK_DEFAULT_COUNT,
        help=f"with --afk --go, how many to launch (max {AFK_MAX_COUNT})",
    )
    parser.add_argument(
        "--launch", help="with --afk, launch these mission ids (comma-separated)",
    )
    parser.add_argument(
        "--repos", choices=("delivery", "all"), default="all",
        help="with --afk, which repos may supply missions (default: all)",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()

    if args.capacity_plan:
        return run_capacity_plan(as_json=args.json, summary=args.capacity_plan_summary)

    if args.afk:
        return afk_run(
            repos_mode=args.repos,
            go=args.go,
            count=args.count,
            ids=[part.strip() for part in (args.launch or "").split(",") if part.strip()],
            dry_run=args.dry_run,
            as_json=args.json,
        )

    if args.mission_create:
        try:
            mission = queue_mission(
                args.mission_create,
                mode=args.mission_mode,
                base=args.mission_base,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
        if args.json:
            print(json.dumps({"ok": True, "mission": mission}, sort_keys=True))
        else:
            print(f"queued mission {mission['id']} · {mission['mode']} · Shep")
        return 0

    if args.mission_list:
        try:
            missions = list_missions()
        except (OSError, RuntimeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
        if args.json:
            print(json.dumps({"ok": True, "missions": missions}, sort_keys=True))
        else:
            for mission in missions:
                print(f"{mission['status']:<8} {mission['id']}  {mission['goal']}")
        return 0

    if args.control_once:
        return run_control_pass(args)

    if args.release:
        load_nudge_state()
        released = release_targets(args.release)
        # Saved against every key already in memory, not just the released
        # ones: `save_nudge_state` filters to the targets it is handed, so
        # passing the release list would drop every other pane's dedupe and
        # close-ask history on the way out.
        save_nudge_state(set(_NUDGE_STATE) | set(_SIG_STATE))
        if args.json:
            print(json.dumps({"ok": True, "released": released}, sort_keys=True))
        else:
            for target in released:
                print(f"released  {target}")
            print(f"-- {len(released)} back in the nudge engine --")
        return

    if args.sweep:
        results, held, escalated = sweep(send=args.send)
        print(render_sweep(results, held, args.send, escalated))
        return

    if args.deliver:
        args.propose = True
        args.snapshot = True
    if args.propose and not (args.snapshot or args.snapshot_json):
        parser.error("--propose requires --snapshot or --snapshot-json")
    if args.snapshot or args.snapshot_json:
        action = None
        if args.propose:
            results, held, _escalated = sweep(send=args.deliver)
            action = {
                "proposed_or_sent": len(results),
                "held_for_review": len(held),
                "delivered": sum(1 for _row, _text, ok, _detail in results if ok),
            }
        payload = snapshot_payload()
        if action is not None:
            payload["action"] = action
        print(json.dumps(payload, indent=2) if args.snapshot_json else render_snapshot(payload))
        return

    if args.dump_json:
        print(json.dumps(collect_all(), indent=2))
        return

    demo_rows = None
    if args.demo:
        demo_rows = [
            {
                "source": "demo", "id": "alpha", "target": "alpha",
                "label": "Codex atlas-build", "status": "working",
                "cwd": "/workspace/atlas", "preview": "Running scoped verification...",
            },
            {
                "source": "demo", "id": "beta", "target": "beta",
                "label": "Claude review-gate", "status": "idle",
                "cwd": "/workspace/review", "preview": "Waiting for operator approval.",
            },
            {
                "source": "demo", "id": "gamma", "target": "gamma",
                "label": "Kimi stalled-job", "status": "stalled",
                "cwd": "/workspace/ops", "preview": "No progress signal received.",
            },
        ]
    if not demo_rows:
        # The TUI started blind. Every other entrypoint loads this — the sweep,
        # the snapshot, the release — but the one an operator sits and watches
        # did not, so it opened knowing nothing about the unattended loop that
        # had been nudging the same fleet every five minutes: an empty NUDGE
        # column, no detail line, and no cooldowns, which also left it free to
        # re-nudge a pane the sweep had just written to. The TUI writes only
        # through `persist_nudge_target`, one pane at a time as it sends, so it
        # still never dumps this startup snapshot back over the loop's work.
        load_nudge_state()
    curses.wrapper(lambda stdscr: run_tui(stdscr, args.theme, demo_rows))


if __name__ == "__main__":
    raise SystemExit(main())
