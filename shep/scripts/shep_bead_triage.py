"""Model-led Beads triage: what to work on next, and what to close unworked.

Shep already knows which beads are *ready* — open, unblocked, and in a repo that
may receive autonomous code. Ready is not the same as worth doing: a fleet
backlog of ~660 open beads sorted by priority puts a vague year-old P1 above a
concrete P2 that unblocks four other beads, and it never says which beads are
dead weight. That is a judgement call, so this module asks a model for it.

Two rules shape everything here:

  - It routes through the canonical `agent-command` lane contract, trying each
    lane in order. One gateway going down degrades the ordering back to
    priority-sort; it must never remove the feature or block the TUI.
  - Its verdict is advisory. Callers filter `work` against the launchable set
    themselves (see shep.bead_missions) — a model naming a repo that must never
    receive autonomous code is a bug we contain here, not a launch.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "shep-bead-triage/v1"
TRIAGE_TTL = 1800  # 30 min, matching the mission deck: a backlog does not turn over faster
# The whole open backlog is ~660 rows / ~16k tokens, which one mid-tier call
# swallows fine. The cap only exists so an unexpectedly huge fleet cannot turn a
# 30-minute refresh into a multi-minute stall.
MAX_BEADS = 700
MAX_WORK = 5
MAX_PRUNE = 12
MAX_REASON_CHARS = 90

# Provider failover, in order. Resolution goes through `agent-command` so the
# workstation's single provider contract stays the only place binaries are
# named. Two lanes by default because both print shapes are already proven in
# this codebase; add more with SHEP_TRIAGE_LANES=claude,codex,kimi.
LANES = tuple(
    lane.strip()
    for lane in (os.environ.get("SHEP_TRIAGE_LANES") or "claude,codex").split(",")
    if lane.strip()
)
# Sensible, not maximal. Ranking ~660 one-line bead summaries is a judgement
# task, not a reasoning problem: a frontier model at high effort costs minutes
# and dollars per refresh to produce the same ordering. Mid-tier, medium effort.
LANE_MODELS = {
    "claude": os.environ.get("SHEP_TRIAGE_CLAUDE_MODEL") or "claude-sonnet-5",
    "codex": os.environ.get("SHEP_TRIAGE_CODEX_MODEL") or "gpt-5.6-terra",
}
LANE_TIMEOUT = int(os.environ.get("SHEP_TRIAGE_TIMEOUT") or "150")


def cache_path():
    """Where the verdict lives. Sits with the deck cache it is a sibling of."""
    root = Path(
        os.environ.get("MISSION_ENGINE_DIR", str(Path.home() / ".mission-engine"))
    ).expanduser()
    return root / "shep-bead-triage.json"


def resolve_lane(lane):
    """The command for one provider lane, or None when it is not installed.

    `agent-command` is the workstation's canonical resolver and rejects
    non-gateway overrides; the shutil fallback only covers a machine where the
    resolver itself is missing.
    """
    resolver = shutil.which("agent-command")
    if resolver:
        result = subprocess.run(
            [resolver, "resolve", lane], capture_output=True, text=True, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return shutil.which(f"{lane}-gw")


def _age_days(updated_at, now):
    """Whole days since a bead last moved; -1 when the record has no timestamp."""
    if not updated_at:
        return -1
    try:
        stamp = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
    except ValueError:
        return -1
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return max(0, int((now - stamp.timestamp()) // 86400))


def candidate_rows(beads, launchable_repos=(), now=None):
    """Compact one-line-per-bead view of the backlog for the prompt.

    Priority-ordered before the cap so truncating a very large fleet drops the
    beads least likely to be picked, not an arbitrary slice.
    """
    now = time.time() if now is None else now
    launchable = {Path(repo).name for repo in launchable_repos}
    rows = [
        {
            "id": bead["id"],
            "repo": bead.get("repo") or "?",
            "priority": bead["priority"],
            "status": bead.get("status") or "open",
            "age_days": _age_days(bead.get("updated_at"), now),
            "title": " ".join(str(bead.get("title") or "").split())[:110],
            "launchable": (bead.get("repo") or "?") in launchable,
        }
        for bead in beads
        if isinstance(bead.get("id"), str) and bead.get("id")
    ]
    rows.sort(key=lambda row: (row["priority"], row["repo"], row["id"]))
    return rows[:MAX_BEADS]


def triage_prompt(rows):
    """The full triage question. Returns None when there is nothing to judge."""
    if not rows:
        return None
    lines = "\n".join(
        f"{row['id']} | {row['repo']} | P{row['priority']} | {row['status']} | "
        f"{row['age_days']}d | {'launchable' if row['launchable'] else 'read-only'} | "
        f"{row['title']}"
        for row in rows
    )
    return (
        "You are triaging an engineering backlog held in Beads, a dependency-aware "
        "issue tracker. Every bead below is open and has no unresolved blocker.\n"
        "Format: ID | repo | priority | status | days since last touched | "
        "launchable | title\n\n"
        f"{lines}\n\n"
        "Produce two lists.\n\n"
        f"1. work — up to {MAX_WORK} beads an autonomous coding agent should start "
        "RIGHT NOW, best first. ONLY beads marked `launchable` are eligible; naming "
        "a `read-only` bead here is an error. Favour beads that are concrete enough "
        "to verify, small enough to finish in one session, and that unblock or "
        "de-risk other work. Skip anything vague, anything needing a human decision "
        "first, and anything that duplicates a bead already on your list. Priority "
        "is a strong signal, not the answer — a specific P2 beats a hand-wavy P0.\n\n"
        f"2. prune — up to {MAX_PRUNE} beads that should be closed WITHOUT being "
        "done: obsolete, superseded, duplicated, or too vague to ever act on. Age "
        "alone is not a reason. Be conservative: a wrong prune deletes real intent, "
        "and an empty prune list is a perfectly good answer.\n\n"
        "Reply with ONLY this JSON. No prose, no markdown fence:\n"
        '{"work":[{"id":"...","reason":"under 12 words"}],'
        '"prune":[{"id":"...","reason":"under 12 words"}]}'
    )


def _json_blob(text):
    """The outermost JSON object in a model reply, fences and preamble included."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def parse_triage(text, known_ids=None):
    """Validate a model reply into {"work": [...], "prune": [...]}, or None.

    Unknown ids are dropped rather than failing the whole verdict: one
    hallucinated id must not cost the four real picks beside it. A reply with no
    surviving entries in either list is still valid — "nothing to prune" is a
    real answer — but an unparseable one is not, so the caller can fail over.
    """
    value = _json_blob(text or "")
    if value is None:
        return None
    known = set(known_ids) if known_ids is not None else None

    def clean(key, limit):
        seen, out = set(), []
        for entry in value.get(key) or []:
            if not isinstance(entry, dict):
                continue
            bead_id = entry.get("id")
            if not isinstance(bead_id, str) or bead_id in seen:
                continue
            if known is not None and bead_id not in known:
                continue
            seen.add(bead_id)
            reason = " ".join(str(entry.get("reason") or "").split())
            out.append({"id": bead_id, "reason": reason[:MAX_REASON_CHARS]})
            if len(out) >= limit:
                break
        return out

    if not isinstance(value.get("work"), list) and not isinstance(value.get("prune"), list):
        return None
    return {"work": clean("work", MAX_WORK), "prune": clean("prune", MAX_PRUNE)}


def lane_call(lane, command, prompt):
    """(argv, env, overflow_path) for one lane's one-shot print invocation.

    codex-gw answers into `-o` rather than stdout, so its reply has a second
    place to look; the claude lane has none and reports that as None. The
    overflow path carries the pid because two Shep instances triaging at once
    would otherwise read each other's answer out of the same temp file.
    """
    env = dict(os.environ)
    model = LANE_MODELS.get(lane)
    if lane == "codex":
        overflow = f"/tmp/shep_bead_triage.{os.getpid()}.json"
        if model:
            env["CODEX_GW_MODEL"] = model
        env["CODEX_GW_REASONING"] = os.environ.get("SHEP_TRIAGE_CODEX_REASONING") or "medium"
        argv = [
            command, "exec", "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check", "-o", overflow, prompt,
        ]
        return argv, env, overflow
    env["CLAUDE_GW_QUIET"] = "1"
    env["CLAUDE_GW_NO_HEALTH"] = "1"
    if lane == "claude" and model:
        env["CLAUDE_GW_MODEL"] = model
    return [command, "-p", "--effort", "medium", prompt], env, None


def run_triage(rows, lanes=None):
    """Ask the first working provider lane. -> (verdict, lane, error).

    Every failure mode is the same failure mode — this lane did not answer —
    so each one falls through to the next lane and the last one reported wins
    the error message. The caller degrades to priority order from there.

    ``lanes`` resolves at call time rather than as a default argument so the
    configured chain stays overridable after import.
    """
    lanes = LANES if lanes is None else lanes
    prompt = triage_prompt(rows)
    if not prompt:
        return None, None, "no open beads to triage"
    known = {row["id"] for row in rows}
    error = "no provider lane available"
    for lane in lanes:
        command = resolve_lane(lane)
        if not command:
            error = f"{lane}: not installed"
            continue
        argv, env, overflow = lane_call(lane, command, prompt)
        # Clear the overflow file BEFORE the call. It is the only place the
        # codex lane's answer lands, so a leftover file from an earlier run
        # reads as this run's verdict — a failing provider would silently serve
        # a stale ranking instead of falling through to the next lane.
        if overflow:
            Path(overflow).unlink(missing_ok=True)
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=LANE_TIMEOUT, env=env, check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            error = f"{lane}: {exc}"
            continue
        replies = [result.stdout or ""]
        if overflow:
            try:
                replies.append(Path(overflow).read_text(encoding="utf-8"))
            except OSError:
                pass
        for reply in replies:
            verdict = parse_triage(reply, known)
            if verdict is not None:
                return verdict, lane, None
        error = f"{lane}: unusable reply" if result.returncode == 0 else (
            f"{lane}: exit {result.returncode}"
        )
    return None, None, error


def read_cache(path=None, ttl=TRIAGE_TTL, now=None):
    """The cached verdict when it is still fresh, else None."""
    path = path or cache_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return None
    now = time.time() if now is None else now
    if ttl and now - float(value.get("at") or 0) >= ttl:
        return None
    return value


def write_cache(verdict, lane, path=None, now=None):
    """Persist a verdict. Best-effort: a failed write costs freshness, not the answer."""
    path = path or cache_path()
    payload = {
        "schema": SCHEMA,
        "at": time.time() if now is None else now,
        "lane": lane,
        "work": verdict.get("work", []),
        "prune": verdict.get("prune", []),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        return False
    return True


def load_triage(beads, launchable_repos=(), force=False, path=None, now=None):
    """Cached triage of the fleet backlog. -> (verdict, error).

    ``force`` skips the cache and pays for a fresh model call; otherwise a
    verdict younger than TRIAGE_TTL is reused, which is what keeps this off the
    hot path of the TUI.
    """
    if not force:
        cached = read_cache(path=path, now=now)
        if cached is not None:
            return cached, None
    rows = candidate_rows(beads, launchable_repos, now=now)
    verdict, lane, error = run_triage(rows)
    if verdict is None:
        return None, error
    write_cache(verdict, lane, path=path, now=now)
    return {**verdict, "lane": lane, "at": time.time() if now is None else now}, None


def work_rank(verdict):
    """{bead_id: (rank, reason)} from a verdict — the ordering callers apply."""
    return {
        entry["id"]: (index, entry.get("reason") or "")
        for index, entry in enumerate((verdict or {}).get("work") or [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def prune_reasons(verdict):
    """{bead_id: reason} for beads the model says to close unworked."""
    return {
        entry["id"]: entry.get("reason") or ""
        for entry in (verdict or {}).get("prune") or []
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def triage_age(verdict, now=None):
    """Seconds since the verdict was produced, or None when it carries no stamp."""
    stamp = (verdict or {}).get("at")
    if not stamp:
        return None
    return max(0.0, (time.time() if now is None else now) - float(stamp))


def demo():
    """Self-check: the parse/rank/prune contract, with no provider call."""
    beads = [
        {"id": "bh-1", "title": "Fix the crash", "priority": 1, "repo": "bug-hunter",
         "status": "open", "updated_at": "2026-08-01T00:00:00Z"},
        {"id": "pm-9", "title": "Someday: rethink everything", "priority": 2,
         "repo": "linkgraph-pm-skills", "status": "open", "updated_at": ""},
    ]
    rows = candidate_rows(beads, ["/x/bug-hunter"], now=1786060800.0)
    assert [row["id"] for row in rows] == ["bh-1", "pm-9"], rows
    assert rows[0]["launchable"] and not rows[1]["launchable"]
    assert rows[0]["age_days"] == 6, rows[0]
    assert rows[1]["age_days"] == -1, rows[1]

    prompt = triage_prompt(rows)
    assert "bh-1 | bug-hunter | P1 | open | 6d | launchable |" in prompt
    assert triage_prompt([]) is None

    reply = (
        'here you go\n```json\n{"work":[{"id":"bh-1","reason":"concrete crash"},'
        '{"id":"nope-7","reason":"invented"}],'
        '"prune":[{"id":"pm-9","reason":"too vague to act on"}]}\n```'
    )
    verdict = parse_triage(reply, {"bh-1", "pm-9"})
    assert verdict == {
        "work": [{"id": "bh-1", "reason": "concrete crash"}],
        "prune": [{"id": "pm-9", "reason": "too vague to act on"}],
    }, verdict
    assert parse_triage("not json at all", {"bh-1"}) is None
    assert work_rank(verdict) == {"bh-1": (0, "concrete crash")}
    assert prune_reasons(verdict) == {"pm-9": "too vague to act on"}
    print("shep_bead_triage: ok")


if __name__ == "__main__":
    demo()
