"""Model-led bead triage: ranking, pruning, provider failover, and the strip."""

from __future__ import annotations

import json
import os
import time

import pytest

from scripts import shep
from scripts import shep_bead_triage as triage


def _bead(bead_id, priority=1, repo="bug-hunter", title="Do the thing", status="open"):
    return {
        "id": bead_id, "title": title, "status": status,
        "priority": priority, "repo": repo, "updated_at": "2026-08-01T00:00:00Z",
    }


def _issue(bead_id, priority=1, title="Do the thing"):
    return {"id": bead_id, "title": title, "status": "open", "priority": priority}


# --- candidate rows ---------------------------------------------------------


def test_candidate_rows_mark_only_the_delivery_repos_launchable() -> None:
    """The prompt has to say which beads an agent may actually be pointed at."""
    rows = triage.candidate_rows(
        [_bead("bh-1"), _bead("st-4", repo="searchatlas-static")],
        ["/repos/bug-hunter"],
    )

    assert [(row["id"], row["launchable"]) for row in rows] == [
        ("bh-1", True), ("st-4", False),
    ]


def test_candidate_rows_cap_drops_the_least_likely_picks(monkeypatch) -> None:
    """A very large fleet must truncate from the bottom of the priority order,
    not from an arbitrary slice that could drop every P0."""
    monkeypatch.setattr(triage, "MAX_BEADS", 2)
    beads = [_bead("p4", priority=4), _bead("p0", priority=0), _bead("p1", priority=1)]

    rows = triage.candidate_rows(beads, ["/repos/bug-hunter"])

    assert [row["id"] for row in rows] == ["p0", "p1"]


# --- parsing ----------------------------------------------------------------


def test_parse_triage_survives_a_fenced_reply_and_drops_invented_ids() -> None:
    """One hallucinated id must not cost the real picks beside it."""
    reply = (
        'Sure!\n```json\n{"work":[{"id":"bh-1","reason":"concrete"},'
        '{"id":"ghost-9","reason":"invented"}],"prune":[]}\n```'
    )

    assert triage.parse_triage(reply, {"bh-1"}) == {
        "work": [{"id": "bh-1", "reason": "concrete"}], "prune": [],
    }


def test_parse_triage_rejects_a_reply_it_cannot_read() -> None:
    """Unparseable is the signal that makes run_triage try the next provider."""
    assert triage.parse_triage("the gateway is down", {"bh-1"}) is None
    assert triage.parse_triage('{"missions": []}', {"bh-1"}) is None


def test_parse_triage_accepts_an_empty_prune_list() -> None:
    """"Nothing is worth closing unworked" is a real answer, not a failure."""
    assert triage.parse_triage('{"work":[],"prune":[]}', set()) == {"work": [], "prune": []}


def test_parse_triage_caps_and_dedupes_each_list(monkeypatch) -> None:
    monkeypatch.setattr(triage, "MAX_WORK", 2)
    reply = json.dumps({
        "work": [{"id": "a"}, {"id": "a"}, {"id": "b"}, {"id": "c"}], "prune": [],
    })

    assert [entry["id"] for entry in triage.parse_triage(reply, {"a", "b", "c"})["work"]] == [
        "a", "b",
    ]


# --- provider failover ------------------------------------------------------


def test_run_triage_falls_over_to_the_next_lane_when_a_provider_is_down(monkeypatch) -> None:
    """The whole point of the lane chain: one gateway dying costs latency, not
    the feature."""
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv[0])
        if argv[0] == "claude-gw":
            return _completed(1, "Error: 429 pool exhausted")
        return _completed(0, '{"work":[{"id":"bh-1","reason":"ready"}],"prune":[]}')

    monkeypatch.setattr(triage, "resolve_lane", lambda lane: f"{lane}-gw")
    monkeypatch.setattr(triage.subprocess, "run", fake_run)

    verdict, lane, error = triage.run_triage(
        triage.candidate_rows([_bead("bh-1")], ["/repos/bug-hunter"]),
        lanes=("claude", "codex"),
    )

    assert calls == ["claude-gw", "codex-gw"]
    assert lane == "codex" and error is None
    assert verdict["work"] == [{"id": "bh-1", "reason": "ready"}]


def test_run_triage_skips_a_lane_whose_binary_is_not_installed(monkeypatch) -> None:
    monkeypatch.setattr(triage, "resolve_lane", lambda lane: None if lane == "claude" else "codex-gw")
    monkeypatch.setattr(
        triage.subprocess, "run",
        lambda argv, **_kw: _completed(0, '{"work":[],"prune":[]}'),
    )

    _verdict, lane, error = triage.run_triage(
        triage.candidate_rows([_bead("bh-1")], []), lanes=("claude", "codex"),
    )

    assert (lane, error) == ("codex", None)


def test_run_triage_reports_the_last_failure_when_every_lane_is_down(monkeypatch) -> None:
    """A None verdict is what makes the caller fall back to priority order."""
    monkeypatch.setattr(triage, "resolve_lane", lambda lane: f"{lane}-gw")
    monkeypatch.setattr(triage.subprocess, "run", lambda argv, **_kw: _completed(1, "boom"))

    verdict, lane, error = triage.run_triage(
        triage.candidate_rows([_bead("bh-1")], []), lanes=("claude", "codex"),
    )

    assert verdict is None and lane is None
    assert "codex" in error


def test_run_triage_reads_the_codex_answer_from_its_output_file(monkeypatch, tmp_path) -> None:
    """codex-gw answers into -o rather than stdout, so stdout alone loses it."""
    overflow = tmp_path / "out.json"

    def fake_run(argv, **_kwargs):
        overflow.write_text('{"work":[{"id":"bh-1","reason":"ok"}],"prune":[]}')
        return _completed(0, "")

    monkeypatch.setattr(triage, "resolve_lane", lambda lane: f"{lane}-gw")
    monkeypatch.setattr(
        triage, "lane_call",
        lambda lane, command, prompt: ([command], {}, str(overflow)),
    )
    monkeypatch.setattr(triage.subprocess, "run", fake_run)

    verdict, lane, _error = triage.run_triage(
        triage.candidate_rows([_bead("bh-1")], []), lanes=("codex",),
    )

    assert lane == "codex" and verdict["work"][0]["id"] == "bh-1"


def test_run_triage_ignores_a_stale_overflow_file_from_an_earlier_run(monkeypatch, tmp_path) -> None:
    """The codex lane's answer file is its ONLY output channel, so a leftover
    file made a failing provider serve last run's ranking as if it were fresh —
    the exact opposite of falling through to the next lane."""
    overflow = tmp_path / "out.json"
    overflow.write_text('{"work":[{"id":"bh-1","reason":"yesterday"}],"prune":[]}')
    monkeypatch.setattr(triage, "resolve_lane", lambda lane: f"{lane}-gw")
    monkeypatch.setattr(
        triage, "lane_call",
        lambda lane, command, prompt: ([command], {}, str(overflow)),
    )
    monkeypatch.setattr(triage.subprocess, "run", lambda argv, **_kw: _completed(1, ""))

    verdict, lane, error = triage.run_triage(
        triage.candidate_rows([_bead("bh-1")], []), lanes=("codex",),
    )

    assert verdict is None and lane is None and "codex" in error
    assert not overflow.exists()


def test_lane_call_gives_each_process_its_own_overflow_file() -> None:
    """Two Shep instances triaging at once must not read each other's answer."""
    _argv, _env, overflow = triage.lane_call("codex", "codex-gw", "prompt")

    assert str(os.getpid()) in overflow


def test_lane_call_pins_a_mid_tier_model_per_lane() -> None:
    """Ranking one-line summaries is a judgement task; a frontier model at high
    effort costs minutes per refresh for the same ordering."""
    _argv, env, overflow = triage.lane_call("claude", "claude-gw", "prompt")
    assert env["CLAUDE_GW_MODEL"] == triage.LANE_MODELS["claude"] and overflow is None

    argv, env, overflow = triage.lane_call("codex", "codex-gw", "prompt")
    assert env["CODEX_GW_MODEL"] == triage.LANE_MODELS["codex"]
    assert env["CODEX_GW_REASONING"] == "medium"
    assert overflow and overflow in argv


# --- caching ----------------------------------------------------------------


def test_load_triage_reuses_a_fresh_cache_without_calling_a_provider(tmp_path, monkeypatch) -> None:
    """The 30-minute cache is the only reason this is cheap enough to sit on a
    tab the operator opens all day."""
    path = tmp_path / "triage.json"
    triage.write_cache({"work": [{"id": "bh-1", "reason": "cached"}], "prune": []}, "claude", path=path)
    monkeypatch.setattr(
        triage, "run_triage",
        lambda *_a, **_kw: pytest.fail("a fresh cache must not reach a provider"),
    )

    verdict, error = triage.load_triage([_bead("bh-1")], [], path=path)

    assert error is None and verdict["work"][0]["reason"] == "cached"


def test_load_triage_ignores_a_cache_older_than_the_ttl(tmp_path) -> None:
    path = tmp_path / "triage.json"
    stale = time.time() - triage.TRIAGE_TTL - 1
    triage.write_cache({"work": [], "prune": []}, "claude", path=path, now=stale)

    assert triage.read_cache(path=path) is None


def test_load_triage_forced_bypasses_a_fresh_cache(tmp_path, monkeypatch) -> None:
    """[r] means the operator judged the verdict stale; returning it anyway
    makes the key look broken."""
    path = tmp_path / "triage.json"
    triage.write_cache({"work": [], "prune": []}, "claude", path=path)
    monkeypatch.setattr(
        triage, "run_triage",
        lambda *_a, **_kw: ({"work": [{"id": "bh-1", "reason": "fresh"}], "prune": []}, "codex", None),
    )

    verdict, _error = triage.load_triage([_bead("bh-1")], [], force=True, path=path)

    assert verdict["work"][0]["reason"] == "fresh" and verdict["lane"] == "codex"


def test_read_cache_ignores_a_foreign_schema(tmp_path) -> None:
    path = tmp_path / "triage.json"
    path.write_text(json.dumps({"schema": "something-else/v9", "at": time.time()}))

    assert triage.read_cache(path=path) is None


# --- ranking feeds the missions --------------------------------------------


def _delivery_repo(tmp_path, monkeypatch, issues, name="bug-hunter"):
    repo = tmp_path / name
    (repo / ".beads").mkdir(parents=True)
    (repo / ".beads" / "issues.jsonl").write_text(
        "\n".join(json.dumps(issue) for issue in issues), encoding="utf-8"
    )
    repos_file = tmp_path / "delivery-repos.txt"
    repos_file.write_text(str(repo))
    monkeypatch.setattr(shep, "MISSION_REPOS_FILE", repos_file)
    monkeypatch.setattr(shep, "launchable_repos", lambda _f: ([str(repo)], []))
    monkeypatch.setattr(shep, "repo_default_branch", lambda _repo: "develop")
    return repo


def test_bead_missions_put_the_ranked_bead_ahead_of_a_higher_priority_one(
    tmp_path, monkeypatch,
) -> None:
    """The whole reason to ask a model: a specific P2 beats a hand-wavy P0."""
    _delivery_repo(tmp_path, monkeypatch, [
        _issue("bh-vague", priority=0, title="Rethink the architecture"),
        _issue("bh-sharp", priority=2, title="Fix the null deref in parse()"),
    ])

    missions, error = shep.bead_missions(rank={"bh-sharp": (0, "concrete and verifiable")})

    assert error is None
    assert [mission["id"] for mission in missions] == ["bh-sharp", "bh-vague"]
    assert "concrete and verifiable" in missions[0]["rationale"]


def test_bead_missions_without_a_rank_stay_in_priority_order(tmp_path, monkeypatch) -> None:
    """A dead provider lane costs the ordering, never the deck."""
    _delivery_repo(tmp_path, monkeypatch, [
        _issue("bh-two", priority=2), _issue("bh-zero", priority=0),
    ])

    missions, _error = shep.bead_missions()

    assert [mission["id"] for mission in missions] == ["bh-zero", "bh-two"]


def test_bead_missions_ignore_a_rank_naming_a_bead_they_never_produced(
    tmp_path, monkeypatch,
) -> None:
    """Containment: a model naming a repo that must never receive autonomous
    code cannot introduce a mission, because rank only ever reorders."""
    _delivery_repo(tmp_path, monkeypatch, [_issue("bh-1")])

    missions, _error = shep.bead_missions(rank={"secret-repo-42": (0, "do this")})

    assert [mission["id"] for mission in missions] == ["bh-1"]


# --- the strip the BEADS tab renders ---------------------------------------


def test_bead_strip_drops_prune_advice_for_a_bead_that_is_no_longer_open(
    tmp_path, monkeypatch,
) -> None:
    """The verdict is up to half an hour old; a bead closed since then must not
    still be offered up for closing."""
    _delivery_repo(tmp_path, monkeypatch, [_issue("bh-1")])
    monkeypatch.setattr(shep, "load_bead_triage", lambda _b, force=False: (
        {"work": [], "prune": [{"id": "bh-1", "reason": "vague"},
                               {"id": "gone-7", "reason": "stale"}], "lane": "claude"},
        None,
    ))

    _missions, prune, _message = shep.bead_strip([_bead("bh-1")])

    assert prune == {"bh-1": "vague"}


def test_bead_strip_says_when_no_provider_answered(tmp_path, monkeypatch) -> None:
    """Silent degradation would let a broken lane read as an empty backlog."""
    _delivery_repo(tmp_path, monkeypatch, [_issue("bh-1")])
    monkeypatch.setattr(shep, "load_bead_triage", lambda _b, force=False: (None, "codex: exit 1"))

    missions, prune, message = shep.bead_strip([_bead("bh-1")])

    assert [mission["id"] for mission in missions] == ["bh-1"]
    assert prune == {}
    assert "triage unavailable" in message and "codex: exit 1" in message


def test_bead_triage_message_flags_a_verdict_past_its_ttl() -> None:
    verdict = {"lane": "claude", "at": time.time() - triage.TRIAGE_TTL - 60}

    assert "press r to refresh" in shep.bead_triage_message(verdict, None, [], {})


def test_bead_triage_message_separates_model_picks_from_priority_fill() -> None:
    """Crediting the model for beads priority order chose would misreport what
    the ranking actually did."""
    verdict = {"lane": "claude", "at": time.time(), "work": [{"id": "bh-1"}, {"id": "bh-2"}]}

    message = shep.bead_triage_message(verdict, None, [{}, {}, {}, {}, {}], {"x": "y"})

    assert "5 to run (2 model-picked) · 1 to prune" in message


def test_sort_beads_for_triage_pulls_the_prunable_beads_to_the_front() -> None:
    """A verdict buried 600 rows down is a verdict nobody acts on."""
    beads = [_bead("a"), _bead("b"), _bead("c")]

    ordered = shep.sort_beads_for_triage(beads, {"c": "stale"})

    assert [bead["id"] for bead in ordered] == ["c", "a", "b"]


def test_sort_beads_for_triage_keeps_the_existing_order_within_each_group() -> None:
    """Below the prune block the list must read exactly as it always has."""
    beads = [_bead("a"), _bead("b"), _bead("c"), _bead("d")]

    ordered = shep.sort_beads_for_triage(beads, {"b": "x", "d": "y"})

    assert [bead["id"] for bead in ordered] == ["b", "d", "a", "c"]


# --- rendering --------------------------------------------------------------


def test_bead_mission_row_shows_the_reason_it_was_picked() -> None:
    """A ranking you cannot see the reasoning for is not one you can trust."""
    row = shep.bead_mission_row(0, {
        "momentum_score": 85, "project_name": "bug-hunter",
        "short_goal": "Close bh-1: fix parse()", "rationale": "unblocks four beads",
    })

    assert row.startswith("1. [ 85] bug-hunter · Close bh-1: fix parse()")
    assert "unblocks four beads" in row


def test_bead_mission_row_marks_a_mission_that_is_already_running() -> None:
    row = shep.bead_mission_row(0, {"project_name": "bug-hunter"}, running=True)

    assert "RUNNING" in row


def test_bead_row_carries_the_prune_verdict_inline() -> None:
    row = shep.bead_row(_bead("bh-1"), "superseded by bh-9")

    assert row.endswith("· PRUNE: superseded by bh-9")
    assert "PRUNE" not in shep.bead_row(_bead("bh-1"))


def _completed(returncode, stdout):
    import subprocess

    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


# --- closing a pruned bead --------------------------------------------------


def _closeable(bead_id="bh-1", repo="/repos/bug-hunter"):
    return {"id": bead_id, "repo": "bug-hunter", "repo_path": repo,
            "title": "t", "status": "open", "priority": 2}


def test_close_bead_runs_bd_close_then_refreshes_the_export(monkeypatch) -> None:
    """Both commands are required: `bd close` writes the database but leaves
    issues.jsonl untouched, and that export is all the BEADS tab ever reads."""
    calls = []
    monkeypatch.setattr(shep, "_run", lambda cmd, **_kw: (
        calls.append(cmd) or _completed(0, "")
    ))

    ok, detail = shep.close_bead(_closeable(), "too vague to ever act on")

    assert ok and "closed bh-1" in detail
    assert calls[0][:5] == ["bd", "-C", "/repos/bug-hunter", "close", "bh-1"]
    assert calls[0][5:] == ["--reason", "shep triage: too vague to ever act on"]
    assert calls[1] == [
        "bd", "-C", "/repos/bug-hunter", "export",
        "-o", "/repos/bug-hunter/.beads/issues.jsonl",
    ]


def test_close_bead_does_not_export_when_the_close_failed(monkeypatch) -> None:
    """Re-exporting after a failed close would rewrite a tracked file for nothing."""
    calls = []

    def run(cmd, **_kw):
        calls.append(cmd)
        return _completed(1, "no such issue")

    monkeypatch.setattr(shep, "_run", run)

    ok, detail = shep.close_bead(_closeable(), "stale")

    assert not ok and "no such issue" in detail
    assert len(calls) == 1


def test_close_bead_warns_when_the_export_did_not_refresh(monkeypatch) -> None:
    """The close stuck, so reporting failure would invite a pointless retry —
    but staying silent would leave the bead looking open forever."""
    monkeypatch.setattr(shep, "_run", lambda cmd, **_kw: _completed(
        0 if cmd[3] == "close" else 1, ""
    ))

    ok, detail = shep.close_bead(_closeable(), "stale")

    assert ok and "export did not refresh" in detail


def test_close_bead_refuses_a_bead_with_no_repo_on_disk(monkeypatch) -> None:
    monkeypatch.setattr(shep, "_run", lambda *_a, **_kw: pytest.fail("ran bd with no repo"))

    ok, detail = shep.close_bead({"id": "bh-1"}, "stale")

    assert not ok and "no repo on disk" in detail


def test_close_bead_gives_bd_room_for_two_dolt_boots(monkeypatch) -> None:
    """The 8s default in _run is not enough: bd boots an embedded database per
    invocation and closing runs two."""
    timeouts = []
    monkeypatch.setattr(shep, "_run", lambda cmd, timeout=8, **_kw: (
        timeouts.append(timeout) or _completed(0, "")
    ))

    shep.close_bead(_closeable(), "stale")

    assert timeouts == [shep.BEAD_CLOSE_TIMEOUT, shep.BEAD_CLOSE_TIMEOUT]
    assert shep.BEAD_CLOSE_TIMEOUT >= 30


def test_bead_close_reason_marks_it_as_a_triage_prune() -> None:
    """A bare reason in the bead history reads as though a human investigated
    and closed it, which is the opposite of what happened."""
    assert shep.bead_close_reason("duplicate of bh-9") == "shep triage: duplicate of bh-9"


def test_bead_close_reason_survives_an_empty_reason() -> None:
    assert shep.bead_close_reason("") == "shep triage: flagged as prunable by triage"
    assert len(shep.bead_close_reason("x" * 999)) <= 280


def test_read_repo_beads_carries_the_path_needed_to_close(tmp_path) -> None:
    """The bare repo name cannot be turned back into a path — two checkouts
    share one name — so the row has to carry it."""
    repo = tmp_path / "bug-hunter"
    (repo / ".beads").mkdir(parents=True)
    (repo / ".beads" / "issues.jsonl").write_text(
        json.dumps({"id": "bh-1", "title": "t", "status": "open", "priority": 1})
    )

    rows, error = shep.read_repo_beads(repo)

    assert error is None
    assert rows[0]["repo_path"] == str(repo)
    assert rows[0]["repo"] == "bug-hunter"
