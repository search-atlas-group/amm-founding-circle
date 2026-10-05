"""Which missions are worth leaving running when nobody is watching.

Shep's mission deck already answers "what is worth doing". Away mode asks a
different question: *which of these survives four hours with the operator gone?*
An important mission that stalls on a clarifying question ten minutes after the
door closes is worth less than a smaller one that lands. So the deck is scored
by six independent lenses and the operator sees the breakdown, not just a rank —
an ordering you cannot interrogate is one you cannot trust at the moment you are
least able to check it.

Pure and stdlib-only on purpose. Every fact that needs the filesystem, git, or a
provider is passed in by the caller (see ``rank``), so the whole ranking is
unit-testable without touching a repo, and a scoring bug cannot take the TUI
down with it.

This module never launches anything and never imports ``shep``; ``shep`` imports
it.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path


SCHEMA = "shep-afk-deck/v1"
WEIGHTS_PATH = Path(__file__).with_name("afk_weights.json")

# The six lenses, in the order the deck renders them.
LENSES = ("bead", "unblocks", "momentum", "afk_fit", "loop", "rot")

# Below this an unattended launch is a bad trade regardless of how much the work
# matters: the agent is more likely to burn its turns stuck than to land. Such
# missions stay visible in the deck with their reason — excluded from --go, never
# silently dropped, because "why is my most important bead not here" is exactly
# the question the operator cannot ask once they have left.
AFK_FIT_FLOOR = 35

# How many dependents saturate the leverage lens. Past about five the marginal
# bead unblocked stops changing the decision.
UNBLOCK_SATURATION = 5

# A mission whose text matches any of these wants a human in the loop partway
# through — approval, a credential, a decision, or an irreversible action that
# should never happen unattended. Matched case-insensitively on word boundaries
# against the mission's goal and spec.
INTERACTIVE_PATTERNS = (
    r"deploy(?:ment|ing|s)?",
    r"migrat(?:e|ion|ions|ing)",
    r"rollout|roll out",
    r"production|prod\s+data",
    r"\bdns\b",
    r"credential\s+rotation|rotate\s+(?:the\s+)?(?:credential|secret|key|token)",
    r"\bsend\b|notify|announce|\bpost\s+to\b",
    r"force[- ]push|filter-repo",
)
_INTERACTIVE_RE = re.compile("|".join(INTERACTIVE_PATTERNS), re.IGNORECASE)

# Phrases that mark work on the closed loop — signal to recommendation to
# approval to shipped change to measured impact — rather than new surface area.
# Deliberately a small keyword table and not a model call: this lens is a nudge
# worth 10% of the blend, and a lens that can fail or bill is a lens that will
# eventually take the deck down with it.
LOOP_PHRASES = (
    "closed loop", "closed-loop", "end to end", "end-to-end",
    "measure", "measurement", "measured", "baseline", "impact",
    "approval", "approve", "audit trail", "receipt", "evidence",
    "ship", "shipped", "recommendation", "signal",
    "customer", "client", "renewal", "activation",
    "scorecard", "benchmark", "visibility", "citation",
)

# Rot: how long an open bead has been ignored before its age starts counting,
# and the age at which the lens saturates. A bead untouched for a fortnight is
# drifting; past a quarter, more waiting tells us nothing new.
ROT_GRACE_DAYS = 14
ROT_SATURATION_DAYS = 90
_DAY = 86400.0


class WeightsError(ValueError):
    """The weights file is unusable. Raised rather than silently defaulted."""


def load_weights(path=None):
    """Read and validate the lens weights. -> dict.

    The weights decide the ordering of work that runs unsupervised, so a
    malformed file fails loudly here rather than quietly re-weighting the deck.
    """
    destination = Path(path) if path else WEIGHTS_PATH
    try:
        raw = json.loads(destination.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WeightsError(f"AFK weights file is missing: {destination}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise WeightsError(f"AFK weights file is unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise WeightsError("AFK weights file must contain a JSON object")
    missing = [lens for lens in LENSES if lens not in raw]
    if missing:
        raise WeightsError(f"AFK weights are missing lenses: {', '.join(missing)}")
    unknown = [key for key in raw if key not in LENSES]
    if unknown:
        raise WeightsError(f"AFK weights name unknown lenses: {', '.join(sorted(unknown))}")
    weights = {}
    for lens in LENSES:
        value = raw[lens]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            raise WeightsError(f"AFK weight for {lens!r} must be a non-negative number")
        weights[lens] = float(value)
    total = sum(weights.values())
    # Exact float equality would reject a perfectly good hand-edited file; a
    # tolerance this tight still catches every realistic typo.
    if abs(total - 1.0) > 1e-6:
        raise WeightsError(f"AFK weights must sum to 1.0, got {total:g}")
    return weights


# Bead types an unattended coding agent cannot close, no matter how well
# specified or how important they are. A `decision` bead is a record of a call
# someone needs to MAKE; a `question` wants an answer; an `epic` is a container
# for other work. Sending an autonomous builder at one produces exactly what it
# produced live on 2026-08-06: a mission that starts, finds nothing to build,
# and exits clean after six minutes having burned a worktree and a bead.
#
# Verified against the real export — the field is `issue_type` on the raw bead
# record (the trimmed BEADS-tab rows drop it, which is why this went unnoticed).
NON_BUILDABLE_BEAD_TYPES = frozenset({
    "decision", "question", "discussion", "epic", "meeting", "note",
})


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, float(value)))


def _text(mission):
    """Everything about a mission a keyword lens should see."""
    return " ".join(
        str(mission.get(field) or "")
        for field in ("short_goal", "next_step", "rationale", "launch_spec")
    )


def lens_bead(mission, issue):
    """Is there a real, written-down, ready bead behind this? -> (score, reason).

    A bead is work someone already decided mattered and wrote down. That beats
    an inferred next step, which is Shep's guess from repo activity — and a
    guess is a poor thing to hand an agent that nobody will be watching.
    """
    if not issue:
        return 30.0, "no bead behind it — inferred from repo activity"
    priority = int(issue.get("priority", 4))
    score = _clamp(100 - 15 * max(0, priority), low=40.0)
    dependents = int(issue.get("dependent_count") or 0)
    waiting = f", {dependents} waiting on it" if dependents else ""
    return score, f"ready P{priority} bead{waiting}"


def lens_unblocks(mission, issue):
    """How much other work does closing this free? -> (score, reason)."""
    if not issue:
        return 0.0, "no bead, so nothing is waiting on it"
    dependents = int(issue.get("dependent_count") or 0)
    if dependents <= 0:
        return 0.0, "nothing is blocked on this"
    score = _clamp(100.0 * min(dependents, UNBLOCK_SATURATION) / UNBLOCK_SATURATION)
    return score, f"unblocks {dependents} bead(s)"


def lens_momentum(mission, issue):
    """Is the repo warm and cheap to land in? -> (score, reason)."""
    score = _clamp(mission.get("momentum_score") or 0)
    return score, f"momentum {score:g}"


def lens_afk_fit(mission, issue, facts=None):
    """Can this run about four hours with nobody watching? -> (score, reason).

    The lens away mode exists for. Starts from "yes" and subtracts every reason
    the mission will instead sit waiting for a human. The penalties are additive
    because the failure modes are: a mission that is both under-specified *and*
    needs a deploy decision is worse than either alone.
    """
    facts = facts or {}
    score = 100.0
    reasons = []

    # Categorical, not a penalty: no amount of priority, leverage or momentum
    # makes a decision or a question closable by an unattended builder. Scoring
    # it low would still let a P0 with five dependents float back over the line.
    bead_type = str((issue or {}).get("issue_type") or "").strip().lower()
    if bead_type in NON_BUILDABLE_BEAD_TYPES:
        article = "an" if bead_type[0] in "aeiou" else "a"
        return 0.0, f"{article} {bead_type} bead is not work a builder can close"

    if mission.get("needs_research"):
        score -= 40
        reasons.append("needs research first")

    has_bead = bool(issue)
    if not has_bead:
        score -= 10
        reasons.append("no bead, weaker definition of done")
    else:
        described = bool(str(issue.get("description") or "").strip())
        criteria = bool(str(issue.get("acceptance_criteria") or "").strip())
        if not described and not criteria:
            score -= 30
            reasons.append("bead has no description or acceptance criteria")

    if _INTERACTIVE_RE.search(_text(mission)):
        score -= 25
        reasons.append("names a step that wants a human (deploy/migrate/send)")

    # Absent knowledge is not good news: a caller that could not determine
    # whether the repo has a verifier must not be scored as though it does. The
    # exit condition requires printing test results, so a repo that cannot
    # produce them loops until it runs out of turns.
    if not facts.get("has_verifier", False):
        score -= 15
        reasons.append("no test/lint command found")

    if not facts.get("worktree_ok", False):
        # Stated as a penalty for absence rather than a bonus for presence: a
        # bonus pushes a flawed mission back to a pristine-looking 100 and hides
        # the very deduction the operator needs to see. 100 means "nothing is
        # wrong with leaving this running", and every subtraction stays visible.
        score -= 10
        reasons.append("no clean worktree available")

    score = _clamp(score)
    return score, "; ".join(reasons) if reasons else "well-specified and self-verifying"


def lens_loop(mission, issue):
    """Does this move signal to shipped to measured, or just add surface? -> (score, reason)."""
    haystack = _text(mission).lower()
    hits = sorted({phrase for phrase in LOOP_PHRASES if phrase in haystack})
    if not hits:
        return 20.0, "no closed-loop signal in the text"
    # Three distinct hits is already a strong signal; more says little extra.
    score = _clamp(20.0 + 80.0 * min(len(hits), 3) / 3)
    return score, f"closed-loop terms: {', '.join(hits[:3])}"


def lens_rot(mission, issue, now=None):
    """Has this open, high-priority bead been skipped for too long? -> (score, reason)."""
    if not issue:
        return 0.0, "no bead to age"
    created = issue.get("created_at") or issue.get("created")
    stamp = _as_epoch(created)
    if stamp is None:
        return 0.0, "no creation date on the bead"
    now = time.time() if now is None else float(now)
    age_days = max(0.0, (now - stamp) / _DAY)
    if age_days <= ROT_GRACE_DAYS:
        return 0.0, f"only {age_days:.0f}d old"
    span = ROT_SATURATION_DAYS - ROT_GRACE_DAYS
    aged = min(1.0, (age_days - ROT_GRACE_DAYS) / span)
    # Weight by priority: a P0 ignored for a month is a different problem from a
    # P4 ignored for a month, and only the first is evidence of something stuck.
    priority = int(issue.get("priority", 4))
    weight = max(0.2, 1.0 - 0.2 * max(0, priority))
    return _clamp(100.0 * aged * weight), f"open {age_days:.0f}d at P{priority}"


def _as_epoch(value):
    """Best-effort epoch seconds from the shapes Beads exports use. -> float|None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        from datetime import datetime

        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


#: Every lens, keyed as it appears in the weights file and the deck output.
LENS_FUNCS = {
    "bead": lens_bead,
    "unblocks": lens_unblocks,
    "momentum": lens_momentum,
    "afk_fit": lens_afk_fit,
    "loop": lens_loop,
    "rot": lens_rot,
}


def score_mission(mission, issue=None, facts=None, weights=None, now=None):
    """Run every lens over one mission. -> dict with per-lens detail and a blend."""
    weights = weights or load_weights()
    lenses = {}
    for name in LENSES:
        func = LENS_FUNCS[name]
        if name == "afk_fit":
            value, reason = func(mission, issue, facts)
        elif name == "rot":
            value, reason = func(mission, issue, now)
        else:
            value, reason = func(mission, issue)
        lenses[name] = [round(float(value), 1), reason]
    blended = sum(lenses[name][0] * weights[name] for name in LENSES)
    afk_fit = lenses["afk_fit"][0]
    return {
        "lenses": lenses,
        "blended": round(blended, 1),
        "afk_fit": afk_fit,
        "afk_safe": afk_fit >= AFK_FIT_FLOOR,
    }


def rank(candidates, weights=None, top=10, now=None):
    """Score and order candidate missions. -> the ``shep-afk-deck/v1`` deck.

    ``candidates`` is a list of ``{"mission": {...}, "issue": {...}|None,
    "facts": {...}}``. Every filesystem and git fact a lens needs arrives in
    ``facts`` (``has_verifier``, ``worktree_ok``) so this stays pure: the caller
    owns the I/O, this owns the judgement.

    Missions below ``AFK_FIT_FLOOR`` are separated into ``excluded`` rather than
    dropped — they are still shown, with the reason they are not safe to leave
    running, so the deck never quietly loses the operator's most important work.

    Deterministic: the same candidates produce the same deck. Ties break on
    mission id so a refresh does not reshuffle rows under a cursor.
    """
    weights = weights or load_weights()
    now = time.time() if now is None else float(now)
    scored, excluded = [], []
    for candidate in candidates or []:
        mission = candidate.get("mission") or {}
        if not mission.get("id"):
            continue
        verdict = score_mission(
            mission,
            issue=candidate.get("issue"),
            facts=candidate.get("facts"),
            weights=weights,
            now=now,
        )
        row = {
            "id": mission["id"],
            "short_goal": mission.get("short_goal", ""),
            "project_name": mission.get("project_name", ""),
            "cwd": mission.get("cwd", ""),
            "blended": verdict["blended"],
            "afk_fit": verdict["afk_fit"],
            "afk_safe": verdict["afk_safe"],
            "lenses": verdict["lenses"],
        }
        if verdict["afk_safe"]:
            scored.append(row)
        else:
            excluded.append({
                "id": row["id"],
                "short_goal": row["short_goal"],
                "afk_fit": row["afk_fit"],
                "reason": verdict["lenses"]["afk_fit"][1],
            })
    scored.sort(key=lambda row: (-row["blended"], row["id"]))
    excluded.sort(key=lambda row: (-row["afk_fit"], row["id"]))
    if top:
        scored = scored[:top]
    return {
        "schema": SCHEMA,
        "generated_at": now,
        "count": len(scored),
        "missions": scored,
        "excluded": excluded,
    }


def selection(deck, count=5, ids=None):
    """The mission ids an operator's --go/--launch actually resolves to. -> (ids, error).

    Only ever selects from the deck's safe missions: an explicit --launch of an
    excluded mission is refused with its reason rather than honoured, because
    "I named it" is not evidence it can run unattended.
    """
    safe = {row["id"]: row for row in deck.get("missions", [])}
    if ids:
        chosen, refused = [], []
        blocked = {row["id"]: row.get("reason", "") for row in deck.get("excluded", [])}
        for mission_id in ids:
            if mission_id in safe:
                chosen.append(mission_id)
            elif mission_id in blocked:
                refused.append(f"{mission_id} ({blocked[mission_id]})")
            else:
                refused.append(f"{mission_id} (not in the deck)")
        if refused:
            return chosen, "refused: " + "; ".join(refused)
        return chosen, None
    ordered = [row["id"] for row in deck.get("missions", [])]
    return ordered[: max(0, int(count))], None
