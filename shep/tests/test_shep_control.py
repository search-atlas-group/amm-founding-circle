import plistlib
import subprocess
from pathlib import Path

from scripts import shep_control_loop
from scripts.shep_action_log import load
from scripts.shep_control import control_once


def test_launchagent_template_is_disabled_and_path_portable() -> None:
    path = (
        Path(__file__).parents[1]
        / "scripts/launchd/com.searchatlas.shep-control.plist.in"
    )
    with path.open("rb") as stream:
        config = plistlib.load(stream)

    arguments = config["ProgramArguments"]
    assert arguments == ["@PYTHON@", "@SHEP_ROOT@/scripts/shep_control_loop.py"]
    assert "--auto-nudge" not in arguments
    assert "--auto-reap" not in arguments
    assert config["RunAtLoad"] is False
    assert config["KeepAlive"] is False
    assert "/Users/" not in path.read_text()


def _paths(tmp_path):
    return {
        "ledger_path": tmp_path / "events.jsonl",
        "state_path": tmp_path / "state.json",
        "lock_path": tmp_path / "control.lock",
    }


def test_control_once_sends_safe_herdr_nudge_and_reaps_revalidated_session(tmp_path):
    rows = [
        {"source": "herdr", "target": "herdr:n", "label": "nudge", "status": "idle", "cwd": "/repo"},
        {"source": "herdr", "target": "herdr:r", "label": "reap", "status": "done", "reap_ready": True, "cwd": "/repo"},
        {"source": "tmux", "target": "%1", "status": "idle"},
    ]
    sent, reaped = [], []
    paths = _paths(tmp_path)
    report = control_once(
        lambda: list(rows),
        send=lambda row, text: (sent.append((row["target"], text)) or (True, "accepted")),
        reap=lambda row: (reaped.append(row["target"]) or (True, "closed")),
        auto_nudge=True, auto_reap=True, now=1000, **paths,
    )
    assert sent == [("herdr:n", "Continue with the next task.")]
    assert reaped == ["herdr:r"]
    assert report["nudged"] == 1 and report["reaped"] == 1
    assert [(e["action"], e["lifecycle"]) for e in load(paths["ledger_path"])] == [
        ("nudge", "intent"), ("nudge", "sent"), ("reap", "candidate"),
        ("reap", "intent"), ("reap", "reaped")
    ]


def test_control_once_dry_run_never_calls_mutators_or_writes_state(tmp_path):
    paths = _paths(tmp_path)
    called = []
    report = control_once(
        lambda: [{"source": "herdr", "target": "herdr:n", "status": "idle"}],
        send=lambda *_: called.append("send") or (True, "bad"),
        reap=lambda *_: called.append("reap") or (True, "bad"),
        auto_nudge=True, dry_run=True, **paths,
    )
    assert called == []
    assert report["planned"][0]["action"] == "nudge"
    assert not paths["ledger_path"].exists()
    assert not paths["state_path"].exists()


def test_control_once_refuses_changed_or_unsafe_reap(tmp_path):
    paths = _paths(tmp_path)
    first = {"source": "herdr", "target": "herdr:r", "status": "done", "reap_ready": True}
    current = {**first, "operator_attached": True}
    reaped = []
    report = control_once(
        lambda: [current], send=lambda *_: (True, "ok"),
        reap=lambda *_: reaped.append(1) or (True, "closed"),
        auto_reap=True, **paths,
    )
    assert reaped == []
    assert report["refused"] == 1
    assert [event["lifecycle"] for event in load(paths["ledger_path"])] == ["candidate", "refused"]


def test_control_once_caps_actions_without_sleep(tmp_path):
    paths = _paths(tmp_path)
    rows = [{"source": "herdr", "target": f"herdr:{i}", "status": "idle"} for i in range(8)]
    sent = []
    report = control_once(
        lambda: rows, send=lambda row, text: sent.append(row["target"]) or (True, "ok"),
        reap=lambda *_: (True, "closed"), auto_nudge=True, max_actions=99, **paths,
    )
    assert len(sent) == 3
    assert len(report["planned"]) == 3


def test_control_once_refuses_mutation_when_intent_receipt_fails(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    from scripts import shep_control

    def unavailable(*_args, **_kwargs):
        raise shep_control.ActionLogError("ledger unavailable")

    monkeypatch.setattr(shep_control, "append", unavailable)
    called = []
    report = control_once(
        lambda: [{"source": "herdr", "target": "herdr:n", "status": "idle"}],
        send=lambda *_: called.append("send") or (True, "accepted"),
        reap=lambda *_: called.append("reap") or (True, "closed"),
        auto_nudge=True, **paths,
    )
    assert called == []
    assert report["refused"] == 1


def test_manual_shep_transport_has_intent_and_terminal_receipts(monkeypatch):
    from types import SimpleNamespace
    from scripts import shep

    receipts = []
    calls = []
    monkeypatch.setattr(shep, "record_action", lambda action, lifecycle, **fields: receipts.append((action, lifecycle, fields)))
    monkeypatch.setattr(
        shep, "_run",
        lambda argv, **kwargs: calls.append(argv) or SimpleNamespace(returncode=0, stdout="accepted", stderr=""),
    )
    assert shep.send_nudge({"source": "herdr", "target": "herdr:a"}, "Continue with the next task.") == (True, "accepted")
    assert [item[:2] for item in receipts] == [("nudge", "intent"), ("nudge", "sent")]
    assert calls[0][-2:] == ["herdr:a", "Continue with the next task."]


def test_installer_renders_a_scheduled_agent_for_the_given_checkout() -> None:
    from scripts.launchd.install import render

    root = Path(__file__).parents[1]
    config = render(root, 300)

    assert config["ProgramArguments"][1] == str(root / "scripts/shep_control_loop.py")
    assert config["EnvironmentVariables"]["SHEP_ROOT"] == str(root)
    assert config["StartInterval"] == 300
    assert "@PYTHON@" not in str(config) and "@SHEP_ROOT@" not in str(config)


def test_control_loop_draft_lane_is_overridable(monkeypatch) -> None:
    from scripts import shep_control_loop

    assert shep_control_loop._env()["SHEP_NUDGE_CMD"] == "codex-gw exec --skip-git-repo-check"

    monkeypatch.setenv("SHEP_NUDGE_CMD", "claude-gw -p")
    env = shep_control_loop._env()
    assert env["SHEP_NUDGE_CMD"] == "claude-gw -p"
    # State and transport paths stay owned by the loop, not the environment.
    monkeypatch.setenv("SHEP_TELEMETRY_CHANNEL", "leaked")
    assert shep_control_loop._env()["SHEP_TELEMETRY_CHANNEL"] == ""


def test_scheduled_pass_never_closes_sessions_and_runs_capacity_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(shep_control_loop, "STATE_DIR", tmp_path)
    monkeypatch.setattr(shep_control_loop, "LOCK_PATH", tmp_path / "loop.lock")
    calls = _timed_run(monkeypatch, [0.0, 0.0, 0.0])

    assert shep_control_loop.main() == 0
    assert not any("reap" in args or "--close" in args for args, _ in calls)
    assert calls[-1][0][-3:] == ["--capacity-plan", "--json", "--capacity-plan-summary"]
    assert calls[-1][1] == shep_control_loop.CAPACITY_PLAN_TIMEOUT


def _timed_run(monkeypatch, durations):
    """Drive _run with a scripted duration per step and a fake clock.

    Returns the recorded (args, timeout) calls. The clock advances by each
    step's scripted duration so the pass budget sees realistic elapsed time
    without the test taking that long.

    The pass also fires an advisory ``git fetch`` that ``_run`` does not wrap,
    so it is stubbed here too: left real it reaches the network, and on a
    machine whose remote is unreachable it blocks for its full 60s timeout per
    test. Keeping it hermetic makes the budget arithmetic the only variable.
    """
    calls = []
    clock = {"now": 1_000.0}
    monkeypatch.setattr(shep_control_loop.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        shep_control_loop.subprocess, "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 0, "", ""),
    )

    def fake_run(args, cwd, env, timeout):
        calls.append((args, timeout))
        clock["now"] += durations[len(calls) - 1]
        return 0

    monkeypatch.setattr(shep_control_loop, "_run", fake_run)
    return calls


def test_a_long_sweep_shrinks_the_capacity_plan_budget_instead_of_timing_out(
    tmp_path, monkeypatch
):
    """The plan gets the time the pass has left, not a fixed 120s.

    The sweep and the plan both drive the gateway, so a sweep that runs long
    squeezes the plan; with a fixed budget the plan hit its own timeout and
    turned the whole launchd job red even though the sweep had already sent
    its nudges.
    """
    monkeypatch.setattr(shep_control_loop, "STATE_DIR", tmp_path)
    monkeypatch.setattr(shep_control_loop, "LOCK_PATH", tmp_path / "loop.lock")
    # Sweep 200s + reconcile 20s leaves 80s of the 300s pass.
    calls = _timed_run(monkeypatch, [200.0, 20.0, 0.0])

    assert shep_control_loop.main() == 0
    plan_args, plan_timeout = calls[-1]
    assert plan_args[-3:] == ["--capacity-plan", "--json", "--capacity-plan-summary"]
    assert plan_timeout == 80
    assert plan_timeout < shep_control_loop.CAPACITY_PLAN_TIMEOUT


def test_a_pass_with_no_time_left_skips_the_advisory_plan_rather_than_failing(
    tmp_path, monkeypatch
):
    """Skipping beats a guaranteed timeout: the plan never launches anything.

    A plan that cannot finish before the next pass is due is worth nothing,
    and running it anyway only produced a 124 that masked an otherwise healthy
    pass. The sweep has already sent by this point.
    """
    monkeypatch.setattr(shep_control_loop, "STATE_DIR", tmp_path)
    monkeypatch.setattr(shep_control_loop, "LOCK_PATH", tmp_path / "loop.lock")
    # Sweep alone overruns the whole pass window.
    calls = _timed_run(monkeypatch, [310.0, 5.0, 0.0])

    assert shep_control_loop.main() == 0
    assert not any("--capacity-plan" in args for args, _ in calls)


def test_a_short_pass_still_gives_the_plan_its_full_budget(tmp_path, monkeypatch):
    """The budget is a ceiling on a squeezed pass, not a cut to the normal one."""
    monkeypatch.setattr(shep_control_loop, "STATE_DIR", tmp_path)
    monkeypatch.setattr(shep_control_loop, "LOCK_PATH", tmp_path / "loop.lock")
    calls = _timed_run(monkeypatch, [20.0, 2.0, 0.0])

    assert shep_control_loop.main() == 0
    assert calls[-1][1] == shep_control_loop.CAPACITY_PLAN_TIMEOUT


def _pinned_clone(tmp_path):
    """A runtime root that looks like a real checkout to the shim."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "scripts").mkdir()
    target = tmp_path / "scripts" / "shep_control_loop.py"
    target.write_text("")
    return target


def _trap_exec(monkeypatch, calls):
    monkeypatch.setattr(shep_control_loop.os, "chdir", lambda p: calls.append(("chdir", str(p))))
    monkeypatch.setattr(
        shep_control_loop.os, "execv",
        lambda binary, argv: calls.append(("execv", argv[1])),
    )


def test_the_scheduled_pass_runs_pinned_main_not_the_shared_checkout(tmp_path, monkeypatch):
    """The scheduler entry cannot be edited, so the entrypoint redirects itself.

    Without this the unattended loop runs whatever branch the shared working
    folder was last left on, and a half-finished feature branch drives live
    panes until a human happens to notice.
    """
    target = _pinned_clone(tmp_path)
    monkeypatch.setattr(shep_control_loop, "RUNTIME_ROOT", tmp_path)
    monkeypatch.delenv("SHEP_RUNTIME_PINNED", raising=False)
    pulled = []
    monkeypatch.setattr(
        shep_control_loop.subprocess, "run",
        lambda args, **kw: pulled.append(args) or None,
    )
    calls = []
    _trap_exec(monkeypatch, calls)

    shep_control_loop._reexec_from_pinned_main()

    assert calls == [("chdir", str(tmp_path)), ("execv", str(target))]
    assert pulled[0][-3:] == ["--quiet", "origin", "main"]
    # --ff-only, never a reset: a diverged runtime clone must stall on the last
    # good commit and be looked at, not be overwritten by an unwatched job.
    assert "--ff-only" in pulled[0] and "reset" not in pulled[0]


def test_the_redirect_happens_once_and_cannot_loop(tmp_path, monkeypatch):
    _pinned_clone(tmp_path)
    monkeypatch.setattr(shep_control_loop, "RUNTIME_ROOT", tmp_path)
    monkeypatch.setenv("SHEP_RUNTIME_PINNED", "1")
    calls = []
    _trap_exec(monkeypatch, calls)

    shep_control_loop._reexec_from_pinned_main()

    assert calls == []


def test_an_unreachable_remote_still_runs_the_last_pinned_copy(tmp_path, monkeypatch):
    """Being offline is not a reason to start running an arbitrary branch."""
    target = _pinned_clone(tmp_path)
    monkeypatch.setattr(shep_control_loop, "RUNTIME_ROOT", tmp_path)
    monkeypatch.delenv("SHEP_RUNTIME_PINNED", raising=False)

    def _boom(args, **kwargs):
        raise shep_control_loop.subprocess.TimeoutExpired(args, 120)

    monkeypatch.setattr(shep_control_loop.subprocess, "run", _boom)
    calls = []
    _trap_exec(monkeypatch, calls)

    shep_control_loop._reexec_from_pinned_main()

    assert calls == [("chdir", str(tmp_path)), ("execv", str(target))]


def test_a_machine_with_nothing_pinned_keeps_working(tmp_path, monkeypatch):
    """The shim must not be able to stop the loop on an un-migrated machine."""
    monkeypatch.setattr(shep_control_loop, "RUNTIME_ROOT", tmp_path / "absent")
    monkeypatch.delenv("SHEP_RUNTIME_PINNED", raising=False)
    calls = []
    _trap_exec(monkeypatch, calls)

    shep_control_loop._reexec_from_pinned_main()

    assert calls == []
