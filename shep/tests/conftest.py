"""Repository-wide pytest invariants for the extracted Shep corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import shep


SKIP_BASELINE = Path(__file__).with_name("pinned-skip-baseline.json")


@pytest.fixture(autouse=True)
def _isolate_action_ledger(tmp_path, monkeypatch):
    """Never let a test run write receipts into the operator's real logs.

    ``reap_session`` and ``send_nudge`` append a genuine audit receipt, and the
    default ledger path is inside the repo — so every unredirected test run was
    filing fake reaps that then showed up in the LOGS view as real fleet
    history. Tests that need a specific ledger still override this themselves.

    ``send_nudge`` also records a genuine `sent` outcome event now that the
    recording lives with the transport rather than at each call site, so the
    outcome log needs the same redirection or a test send would land in the
    operator's scorecard.
    """
    monkeypatch.setenv("SHEP_ACTION_LOG", str(tmp_path / "action-ledger.jsonl"))
    monkeypatch.setenv("SHEP_OUTCOMES_DIR", str(tmp_path / "outcomes"))


@pytest.fixture(autouse=True)
def _forget_reaped_panes():
    """Start every test with no memory of panes closed by an earlier one.

    ``_REAPED`` is process-global by design — it debounces a held key within a
    run — so without this a test that closes ``herdr:w1:p1`` makes the next test
    closing the same id get ``already closed`` back instead of exercising the
    transport.
    """
    shep._REAPED.clear()
    yield
    shep._REAPED.clear()


@pytest.fixture(autouse=True)
def _isolate_delivery_repos(tmp_path, monkeypatch):
    """Never let the deck read the operator's real delivery repos.

    ``bead_missions`` opens MISSION_REPOS_FILE and every ``.beads/`` export
    behind it, so without this a deck test's result depends on whatever work is
    open on this machine today — the mission-deck suite failed or passed by
    accident of the live backlog. Bead tests point it at their own tree. Kept
    under the real file name so the "this constant is not env-overridable"
    invariant still reads what it is meant to read.
    """

    monkeypatch.setattr(shep, "MISSION_REPOS_FILE", tmp_path / "delivery-repos.txt")


@pytest.fixture(autouse=True)
def _isolate_nudge_state(tmp_path, monkeypatch):
    """Never let a test read -- or write -- the operator's live nudge state.

    ``snapshot_payload`` opens with ``load_nudge_state()``, which merges
    ``~/.mission-engine/shep-nudge-state.json`` straight into the process
    globals. Tests fabricate panes under ids like ``herdr:w1:p1``, and that id
    exists on a real machine, so the operator's live pane silently replaced the
    fabricated one mid-test: `test_the_snapshot_says_which_panes_need_a_human`
    set ``needs_human``, then read back ``sent_unresolved`` from the real
    fleet's copy.

    It passed in CI because a clean container has no such file, and failed on
    the machine that owns the fleet -- the suite's result depended on which
    panes happened to be open. Redirected rather than merely cleared, because
    ``save_nudge_state`` writes to the same constant and a test must never be
    able to overwrite the live ladder.

    The globals are cleared alongside it: they are process-global by design and
    keyed by the same shared ids, so one test's pane history would otherwise
    decide whether the next one sees movement at all. ``_TAB_BADGES`` rides here
    for the same reason — it is keyed by tab name, so a seeded count and its
    timestamp survive into whatever test renders a tab bar next.

    ``test_the_live_nudge_ledger_is_never_reachable_from_a_test`` asserts this
    fixture is actually in effect. Without that, weakening this function is
    invisible: the suite still passes in CI and fails only on the machine that
    owns the fleet, in an unrelated test, once in a while.
    """
    monkeypatch.setattr(shep, "NUDGE_STATE_FILE", tmp_path / "nudge-state.json")
    for state in (shep._SIG_STATE, shep._NUDGE_STATE, shep._NUDGE_EVENTS,
                  shep._TAB_BADGES):
        state.clear()
    yield
    for state in (shep._SIG_STATE, shep._NUDGE_STATE, shep._NUDGE_EVENTS,
                  shep._TAB_BADGES):
        state.clear()


@pytest.fixture(autouse=True)
def _isolate_t3_auth_cache(tmp_path, monkeypatch):
    """Never let a test read -- or write -- the operator's live T3 auth cache.

    ``_t3_token`` falls back to a file under ``~/.mission-engine`` shared
    across real ``shep.py`` subprocesses, so without this a test run would
    plant a fake bearer where the live fleet looks for a real one (and a
    live run's cached bearer would make a test think it minted its own).
    The in-process mirror is process-global for the same reason the nudge
    ladder above is: it has to be cleared, not just redirected.
    """
    monkeypatch.setattr(shep, "T3_AUTH_CACHE_FILE", tmp_path / "t3-auth-cache.json")
    shep._T3_TOKEN.update(value=None, expires=0.0)
    yield
    shep._T3_TOKEN.update(value=None, expires=0.0)


@pytest.fixture(autouse=True)
def _isolate_bead_triage(tmp_path, monkeypatch):
    """Never let a test reach a provider or touch the operator's triage cache.

    ``run_beads_view`` asks a model to rank the backlog, and on a cold cache
    that is a real billed gateway call whose answer then overwrites the real
    ``~/.mission-engine/shep-bead-triage.json`` — so an unredirected suite run
    both spent money and rewrote live state. Point the cache at the test's own
    tmp dir and give the lane list nothing to resolve; tests that exercise
    triage itself override one or both.
    """
    monkeypatch.setattr(
        shep.bead_triage, "cache_path", lambda: tmp_path / "bead-triage.json"
    )
    monkeypatch.setattr(shep.bead_triage, "LANES", ())


@pytest.fixture(autouse=True)
def _isolate_escalation_channel(monkeypatch):
    """Never let a test post an escalation to the operator's real ClickUp DM.

    ``post_escalation`` fires from inside ``sweep`` and ``send_daily_digest``,
    and the channel is on by default (the outage postmortem's whole point), so
    without this a suite run on the operator's machine — where the ClickUp
    token resolves from the shared env files — would DM them a test handoff.
    Tests that exercise escalation override the channel themselves.
    """
    monkeypatch.setattr(shep, "CLICKUP_ESCALATION_CHANNEL", "")
    monkeypatch.setattr(shep, "CLICKUP_TELEMETRY_CHANNEL", "")


@pytest.fixture(autouse=True)
def _isolate_live_pane_lookup(monkeypatch):
    """Never let tests query the developer's live Herdr fleet."""
    monkeypatch.setattr(shep, "_live_panes_or_none", lambda: None)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail when tests silently gain or lose skips relative to the reviewed seed."""

    expected = json.loads(SKIP_BASELINE.read_text(encoding="utf-8"))["skip_count"]
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    actual = len(reporter.stats.get("skipped", ())) if reporter is not None else 0
    if actual != expected:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        session.config.issue_config_time_warning(
            pytest.PytestWarning(
                f"skip inventory drift: expected {expected}, observed {actual}"
            ),
            stacklevel=2,
        )
