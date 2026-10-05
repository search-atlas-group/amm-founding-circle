"""Away mode's wiring: candidate collection, the Happy gate, and batch launch."""

from __future__ import annotations

import json

import pytest

from scripts import shep
from scripts import shep_afk as afk


@pytest.fixture(autouse=True)
def _isolate_afk_receipts(tmp_path, monkeypatch):
    """Never file a real away-batch receipt from a test run."""
    monkeypatch.setattr(shep, "AFK_RECEIPTS", tmp_path / "afk-batches.jsonl")


def _deck(*ids, excluded=()):
    return {
        "schema": afk.SCHEMA,
        "repos_mode": "all",
        "count": len(ids),
        "missions": [{"id": i, "short_goal": i, "blended": 50.0} for i in ids],
        "excluded": [{"id": i, "afk_fit": 10, "reason": "needs research"} for i in excluded],
    }


def _stage(monkeypatch, ids):
    monkeypatch.setattr(shep, "_AFK_MISSIONS", {i: {"id": i, "cwd": "/repo"} for i in ids})


# --- repo pool: the safety knob ---------------------------------------------


def test_delivery_mode_reads_the_guarded_repos_file(monkeypatch):
    seen = {}

    def fake_launchable(path):
        seen["path"] = path
        return ["/a"], []

    monkeypatch.setattr(shep, "launchable_repos", fake_launchable)
    monkeypatch.setattr(shep, "discover_beads_repos", lambda: pytest.fail("must not widen"))
    assert shep.afk_repo_pool("delivery") == (["/a"], None)
    assert seen["path"] == shep.MISSION_REPOS_FILE, "the guard file is the whole point"


def test_all_mode_reads_every_repo_with_beads(monkeypatch):
    monkeypatch.setattr(
        shep, "launchable_repos", lambda path: pytest.fail("must not narrow"),
    )
    monkeypatch.setattr(shep, "discover_beads_repos", lambda: ["/a", "/b"])
    assert shep.afk_repo_pool("all") == (["/a", "/b"], None)


def test_an_empty_pool_reports_why_rather_than_ranking_nothing(monkeypatch):
    monkeypatch.setattr(shep, "discover_beads_repos", lambda: [])
    repos, error = shep.afk_repo_pool("all")
    assert repos == [] and error


# --- verifier probe ----------------------------------------------------------


def test_a_repo_with_a_test_config_can_verify_itself(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]")
    assert shep.repo_has_verifier(tmp_path) is True


def test_a_repo_with_nothing_to_run_cannot(tmp_path):
    assert shep.repo_has_verifier(tmp_path) is False


# --- the Happy gate ----------------------------------------------------------


def test_a_batch_is_refused_when_happy_is_not_installed(monkeypatch):
    monkeypatch.setattr(shep.shutil, "which", lambda _name: None)
    ready, message = shep.happy_ready()
    assert ready is False and "not on PATH" in message


def test_a_batch_is_refused_when_the_daemon_is_unhealthy(monkeypatch):
    monkeypatch.setattr(shep.shutil, "which", lambda _name: "/bin/happy")
    monkeypatch.setattr(
        shep, "_run",
        lambda *a, **k: shep.subprocess.CompletedProcess(a[0], 1, "", "daemon not running"),
    )
    ready, message = shep.happy_ready()
    assert ready is False and "not healthy" in message


def test_nothing_launches_when_the_phone_could_not_reach_it(monkeypatch):
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (False, "happy is not on PATH"))
    monkeypatch.setattr(
        shep, "launch_mission_by_id",
        lambda *a, **k: pytest.fail("must not launch behind a failed Happy gate"),
    )
    results, error = shep.afk_launch(_deck("m1"), ["m1"])
    assert results == [] and "not on PATH" in error


# --- batch launch ------------------------------------------------------------


def test_each_selected_mission_is_launched_once_under_the_away_runtime(monkeypatch):
    _stage(monkeypatch, ["m1", "m2"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    calls = []

    def fake_launch(mission_id, mission=None, goal_runtime=None):
        calls.append((mission_id, goal_runtime))
        return True, "launched"

    monkeypatch.setattr(shep, "launch_mission_by_id", fake_launch)
    results, error = shep.afk_launch(_deck("m1", "m2"), ["m1", "m2"])
    assert error is None
    assert calls == [("m1", shep.AFK_RUNTIME), ("m2", shep.AFK_RUNTIME)]
    assert all(row["ok"] for row in results)


def test_the_away_runtime_reaches_the_launcher_subprocess(monkeypatch):
    """launch.py reads MISSION_GOAL_ROUTER_RUNTIME at its own import.

    It must be set WHILE each mission launches — and only then; see the
    restore-after-batch regression below.
    """
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    seen = {}

    def capture(*a, **k):
        seen["runtime"] = shep.os.environ.get("MISSION_GOAL_ROUTER_RUNTIME")
        return True, "ok"

    monkeypatch.setattr(shep, "launch_mission_by_id", capture)
    monkeypatch.delenv("MISSION_GOAL_ROUTER_RUNTIME", raising=False)
    shep.afk_launch(_deck("m1"), ["m1"], runtime="happy-cc")
    assert seen["runtime"] == "happy-cc"


def test_a_dry_run_touches_nothing(monkeypatch):
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(
        shep, "happy_ready",
        lambda runtime=None: pytest.fail("a dry run must not probe the daemon"),
    )
    monkeypatch.setattr(
        shep, "launch_mission_by_id", lambda *a, **k: pytest.fail("dry run must not launch"),
    )
    results, error = shep.afk_launch(_deck("m1"), ["m1"], dry_run=True)
    assert error is None and results[0]["dry_run"] is True


def test_a_batch_stops_after_three_consecutive_failures(monkeypatch):
    ids = [f"m{index}" for index in range(8)]
    _stage(monkeypatch, ids)
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    attempts = []

    def always_fails(mission_id, mission=None, goal_runtime=None):
        attempts.append(mission_id)
        return False, "gateway down"

    monkeypatch.setattr(shep, "launch_mission_by_id", always_fails)
    results, error = shep.afk_launch(_deck(*ids), ids)
    assert len(attempts) == shep.AFK_MAX_CONSECUTIVE_FAILURES
    assert "systemic" in error
    assert len(results) == shep.AFK_MAX_CONSECUTIVE_FAILURES


def test_a_success_resets_the_failure_run(monkeypatch):
    ids = ["m1", "m2", "m3", "m4"]
    _stage(monkeypatch, ids)
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    outcomes = {"m1": False, "m2": False, "m3": True, "m4": False}
    monkeypatch.setattr(
        shep, "launch_mission_by_id",
        lambda mission_id, **k: (outcomes[mission_id], "detail"),
    )
    results, error = shep.afk_launch(_deck(*ids), ids)
    assert error is None, "two failures either side of a success is not systemic"
    assert len(results) == 4


def test_a_mission_that_left_the_pool_is_refused_not_launched_stale(monkeypatch):
    _stage(monkeypatch, [])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    monkeypatch.setattr(
        shep, "launch_mission_by_id", lambda *a, **k: pytest.fail("no record to launch from"),
    )
    results, _error = shep.afk_launch(_deck("m1"), ["m1"])
    assert results[0]["ok"] is False
    assert "no longer" in results[0]["detail"]


def test_selecting_nothing_is_refused_rather_than_launching_everything(monkeypatch):
    results, error = shep.afk_launch(_deck("m1"), [])
    assert results == [] and "nothing selected" in error


# --- receipts ----------------------------------------------------------------


def test_every_batch_files_a_receipt(monkeypatch):
    _stage(monkeypatch, ["m1", "m2"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    monkeypatch.setattr(
        shep, "launch_mission_by_id",
        lambda mission_id, **k: (mission_id == "m1", "detail"),
    )
    shep.afk_launch(_deck("m1", "m2", excluded=("m9",)), ["m1", "m2"])
    receipt = json.loads(shep.AFK_RECEIPTS.read_text().strip())
    assert receipt["launched"] == ["m1"]
    assert receipt["failed"] == ["m2"]
    assert receipt["excluded"] == ["m9"]
    assert receipt["runtime"] == shep.AFK_RUNTIME


def test_a_receipt_failure_never_loses_a_launch(monkeypatch, tmp_path):
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(shep, "AFK_RECEIPTS", tmp_path / "no-such-dir" / "x" / "r.jsonl")
    monkeypatch.setattr(
        shep.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")),
    )
    results, error = shep.afk_launch(_deck("m1"), ["m1"])
    assert error is None and results[0]["ok"] is True


# --- the goal-runtime trap ---------------------------------------------------


def test_the_staged_mission_carries_the_runtime_it_launches_under(monkeypatch, tmp_path):
    """launch.py rejects a goal_mode mission whose goal_runtime disagrees with it.

    Shep freezes BEAD_GOAL_RUNTIME at import, so without an explicit restamp
    every away launch would fail validation before a pane was ever created.
    """
    staged = {}
    launcher = tmp_path / "launch.py"
    launcher.write_text("# stand-in for mission-launch")
    monkeypatch.setattr(shep, "MISSION_LAUNCH_SCRIPT", launcher)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: (str(tmp_path), None))
    monkeypatch.setattr(shep, "repoint_mission", lambda m, w: dict(m, cwd=w))
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)

    def capture(cmd, **kwargs):
        payload = json.loads((tmp_path / f"shep-launch-{cmd[-1]}.json").read_text())
        staged.update(payload["missions"][0])
        return shep.subprocess.CompletedProcess(cmd, 0, "launched", "")

    monkeypatch.setattr(shep, "_run", capture)
    shep._MISSIONS_LAUNCHED.discard("m1")
    ok, _detail = shep.launch_mission_by_id(
        "m1",
        mission={"id": "m1", "cwd": "/repo", "goal_runtime": "codex-gw", "goal_mode": True},
        goal_runtime="happy-cc",
    )
    assert ok is True
    assert staged["goal_runtime"] == "happy-cc"


def test_launching_from_the_cache_is_unchanged_when_no_runtime_is_given(monkeypatch, tmp_path):
    """The existing single-mission launch path must not change behaviour."""
    staged = {}
    launcher = tmp_path / "launch.py"
    launcher.write_text("# stand-in for mission-launch")
    monkeypatch.setattr(shep, "MISSION_LAUNCH_SCRIPT", launcher)
    monkeypatch.setattr(shep, "prepare_mission_worktree", lambda m: (str(tmp_path), None))
    monkeypatch.setattr(shep, "repoint_mission", lambda m, w: dict(m, cwd=w))
    monkeypatch.setattr(shep, "MISSION_ENGINE_DIR", tmp_path)
    monkeypatch.setattr(
        shep, "_run",
        lambda cmd, **k: staged.update(
            json.loads((tmp_path / f"shep-launch-{cmd[-1]}.json").read_text())["missions"][0]
        ) or shep.subprocess.CompletedProcess(cmd, 0, "launched", ""),
    )
    shep._MISSIONS_LAUNCHED.discard("m2")
    shep.launch_mission_by_id(
        "m2", mission={"id": "m2", "cwd": "/repo", "goal_runtime": "codex-gw"},
    )
    assert staged["goal_runtime"] == "codex-gw"


# --- the away view -----------------------------------------------------------


def test_the_away_view_renders_every_lens_for_every_mission():
    deck = {
        "repos_mode": "all", "count": 1,
        "missions": [{
            "id": "m1", "short_goal": "close m1", "project_name": "p", "cwd": "/repo",
            "blended": 70.0,
            "lenses": {name: [50.0, f"{name} reason"] for name in afk.LENSES},
        }],
        "excluded": [],
    }
    lines = shep.afk_view_lines(deck)
    body = "\n".join(lines)
    assert "close m1" in body
    for name in afk.LENSES:
        assert f"{name} reason" in body, f"{name} must show why it scored"


def test_the_away_view_names_what_it_is_holding_back():
    deck = {
        "repos_mode": "all", "count": 0, "missions": [],
        "excluded": [{"id": "m9", "afk_fit": 10.0, "reason": "needs research first"}],
    }
    body = "\n".join(shep.afk_view_lines(deck))
    assert "not safe to leave running" in body
    assert "needs research first" in body, "an excluded mission must never be silent"


# --- regressions found by auditing MR 33 -------------------------------------


def test_the_away_runtime_is_restored_so_normal_launches_keep_working(monkeypatch):
    """An away batch must not poison the process for later single launches.

    A normal Enter/l launch still stamps the frozen BEAD_GOAL_RUNTIME on its
    mission. A leftover away runtime in the environment makes launch.py's
    validate_goal_contract reject every one of them for the rest of the session.
    """
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda *a, **k: (True, "ok"))
    monkeypatch.setenv("MISSION_GOAL_ROUTER_RUNTIME", "codex-gw")
    shep.afk_launch(_deck("m1"), ["m1"], runtime="happy-cc")
    assert shep.os.environ["MISSION_GOAL_ROUTER_RUNTIME"] == "codex-gw"


def test_an_unset_runtime_is_left_unset_after_a_batch(monkeypatch):
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    monkeypatch.setattr(shep, "launch_mission_by_id", lambda *a, **k: (True, "ok"))
    monkeypatch.delenv("MISSION_GOAL_ROUTER_RUNTIME", raising=False)
    shep.afk_launch(_deck("m1"), ["m1"], runtime="happy-cc")
    assert "MISSION_GOAL_ROUTER_RUNTIME" not in shep.os.environ


def test_the_runtime_is_restored_even_when_the_batch_raises(monkeypatch):
    _stage(monkeypatch, ["m1"])
    monkeypatch.setattr(shep, "happy_ready", lambda runtime=None: (True, "up"))
    monkeypatch.setattr(
        shep, "launch_mission_by_id",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("herdr exploded")),
    )
    monkeypatch.setenv("MISSION_GOAL_ROUTER_RUNTIME", "codex-gw")
    with pytest.raises(RuntimeError):
        shep.afk_launch(_deck("m1"), ["m1"], runtime="happy-cc")
    assert shep.os.environ["MISSION_GOAL_ROUTER_RUNTIME"] == "codex-gw"


def test_a_pane_command_herdr_could_not_exec_stops_the_batch(monkeypatch):
    """happy being installed says nothing about the shim being runnable."""
    monkeypatch.setattr(shep.shutil, "which", lambda name: "/bin/happy" if name == "happy" else None)
    monkeypatch.setattr(shep.os, "access", lambda *a, **k: False)
    ready, message = shep.happy_ready("happy-cc")
    assert ready is False
    assert "not executable" in message


def test_an_absolute_shim_path_is_accepted_when_it_is_executable(monkeypatch, tmp_path):
    shim = tmp_path / "happy-cc"
    shim.write_text("#!/bin/sh\n")
    shim.chmod(0o755)
    monkeypatch.setattr(shep.shutil, "which", lambda name: "/bin/happy" if name == "happy" else None)
    monkeypatch.setattr(
        shep, "_run", lambda *a, **k: shep.subprocess.CompletedProcess(a[0], 0, "ok", ""),
    )
    ready, _message = shep.happy_ready(str(shim))
    assert ready is True


def test_the_shipped_shim_is_what_the_default_runtime_resolves_to():
    """A bare name would fail to exec in herdr's fresh shell."""
    runtime = shep._resolve_afk_runtime()
    assert runtime == "happy-cc" or shep.Path(runtime).name == "happy-cc"
    if runtime != "happy-cc":
        assert shep.os.access(runtime, shep.os.X_OK), "the shipped shim must be executable"


# --- away-mode panes must stay visible to the control loop -------------------


def _herdr_pane(monkeypatch, tmp_path, pane_text, agent=None, agent_status="unknown"):
    """One herdr pane as `session list` would report it.

    HERDR_CTL is redirected at a real file: collect_herdr bails out early when
    the controller is missing, and CI runs in a clean image that has no herdr —
    so without this these tests only pass on a workstation that happens to have
    it installed.
    """
    controller = tmp_path / "herdr_ctl.py"
    controller.write_text("# stand-in for the herdr controller")
    monkeypatch.setattr(shep, "HERDR_CTL", controller)
    payload = {"panes": [{
        "pane_id": "w1:p1", "target": "herdr:w1:p1", "label": "mission-bh-hhj",
        "cwd": "/repo", "agent": agent, "agent_status": agent_status,
    }]}
    monkeypatch.setattr(
        shep, "_run",
        lambda *a, **k: shep.subprocess.CompletedProcess(a[0], 0, json.dumps(payload), ""),
    )
    monkeypatch.setattr(shep, "capture_pane", lambda *a, **k: pane_text)
    return shep.collect_herdr()


HAPPY_CLAUDE_PANE = (
    "  Work until this exit condition is met: bead bh-hhj is CLOSED\n"
    "                                        ◎ /goal active (41s)\n"
    "──────────────────────────────────────────────────────────────\n"
    "❯ Press up to edit queued messages\n"
    "──────────────────────────────────────────────────────────────\n"
    "  Atlas Max | med | bh-hhj | ContextQ:--\n"
    "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← 1 agent\n"
)

BARE_SHELL_PANE = "developer@Developer-Mac bug-hunter % \n"


def test_a_happy_wrapped_mission_pane_is_not_invisible_to_shep(monkeypatch, tmp_path):
    """herdr cannot name the agent behind a wrapper; the chrome still can.

    Away-mode missions run under Happy so the phone can reach them. Before this,
    herdr reported agent=None/status=unknown and Shep skipped stall detection,
    nudging and reaping for precisely the panes nobody is watching.
    """
    rows = _herdr_pane(monkeypatch, tmp_path, HAPPY_CLAUDE_PANE)
    assert len(rows) == 1
    assert rows[0]["status"] != "unknown", "an away mission must not be invisible"
    assert rows[0]["status"] in shep.NUDGEABLE + ("working", "asking")


def test_promoting_an_unknown_pane_never_reaches_a_bare_shell(monkeypatch, tmp_path):
    """The shell guard must still win — a nudge typed into zsh is the old bug."""
    rows = _herdr_pane(monkeypatch, tmp_path, BARE_SHELL_PANE)
    assert rows[0]["status"] == "shell"


def test_a_pane_herdr_does_identify_is_left_alone(monkeypatch, tmp_path):
    """Only unknown status is promoted; herdr's own verdict is not overridden."""
    rows = _herdr_pane(monkeypatch, tmp_path, HAPPY_CLAUDE_PANE, agent="claude", agent_status="working")
    assert rows[0]["status"] == "working"


def test_an_unknown_pane_with_no_agent_chrome_stays_unknown(monkeypatch, tmp_path):
    """Absent evidence is not evidence of an agent."""
    rows = _herdr_pane(monkeypatch, tmp_path, "some scrollback with no agent chrome at all\n")
    assert rows[0]["status"] != "idle"
