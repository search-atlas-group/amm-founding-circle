#!/usr/bin/env python3
"""Tests for escalation_guard. Run: python3 test_escalation_guard.py"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import escalation_guard as g  # noqa: E402


def _state_file(case, targets):
    """A throwaway nudge-state file containing exactly `targets`."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    path = Path(tmp.name) / "shep-nudge-state.json"
    path.write_text(json.dumps({"nudge": {t: {} for t in targets}}))
    return path

LIVE = {"w5M:p1", "w6Y:p3", "w7E:pA"}
# Targets the local ladder has tracked. `wY:p1` is in here because the case the
# guard exists for is OUR pane, nudged six times, then destroyed.
OURS = {"herdr:w5M:p1", "herdr:w6Y:p3", "herdr:w7E:pA", "herdr:wY:p1"}


def _proc(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def _pane_list(ids):
    return json.dumps({"result": {"panes": [{"pane_id": i} for i in ids]}})


class PaneOf(unittest.TestCase):
    def test_strips_prefix(self):
        self.assertEqual(g.pane_of("herdr:wY:p1"), "wY:p1")

    def test_bare_pane_passthrough(self):
        self.assertEqual(g.pane_of("w5M:p1"), "w5M:p1")


class ShouldEscalate(unittest.TestCase):
    def test_live_pane_escalates(self):
        self.assertTrue(g.should_escalate("herdr:w6Y:p3", LIVE, OURS))

    def test_phantom_pane_suppressed(self):
        """The defect this exists to fix: wY:p1 paged the owner 5x."""
        self.assertFalse(g.should_escalate("herdr:wY:p1", LIVE, OURS))

    def test_non_herdr_target_always_escalates(self):
        """tmux/t3/warp are not addressable by herdr; never silence them."""
        for target in ("tmux:foo", "t3:abc123", "warp:xyz"):
            self.assertTrue(g.should_escalate(target, LIVE, OURS), target)

    def test_empty_target_escalates(self):
        self.assertTrue(g.should_escalate("", LIVE, OURS))


class FailOpen(unittest.TestCase):
    """A guard that silences real pages when its dependency is down is worse
    than the noise it removes."""

    def test_herdr_missing_binary_escalates(self):
        with mock.patch.object(g.subprocess, "run", side_effect=OSError("no herdr")):
            self.assertTrue(g.should_escalate("herdr:wY:p1", tracked=OURS))

    def test_herdr_nonzero_exit_escalates(self):
        with mock.patch.object(g.subprocess, "run", return_value=_proc(returncode=1, stderr="boom")):
            self.assertTrue(g.should_escalate("herdr:wY:p1", tracked=OURS))

    def test_herdr_timeout_escalates(self):
        with mock.patch.object(
            g.subprocess, "run",
            side_effect=subprocess.TimeoutExpired(cmd="herdr", timeout=60),
        ):
            self.assertTrue(g.should_escalate("herdr:wY:p1", tracked=OURS))

    def test_unparseable_output_escalates(self):
        with mock.patch.object(g.subprocess, "run", return_value=_proc(stdout="not json")):
            self.assertTrue(g.should_escalate("herdr:wY:p1", tracked=OURS))

    def test_zero_panes_escalates(self):
        """A half-started server returns an empty fleet; that must not silence
        the entire deck at once."""
        with mock.patch.object(g.subprocess, "run", return_value=_proc(stdout=_pane_list([]))):
            self.assertTrue(g.should_escalate("herdr:wY:p1", tracked=OURS))


class LivePanes(unittest.TestCase):
    def test_parses_ids(self):
        with mock.patch.object(g.subprocess, "run", return_value=_proc(stdout=_pane_list(sorted(LIVE)))):
            self.assertEqual(g.live_panes(), LIVE)

    def test_zero_panes_raises(self):
        with mock.patch.object(g.subprocess, "run", return_value=_proc(stdout=_pane_list([]))):
            with self.assertRaises(g.HerdrUnavailable):
                g.live_panes()


class ForeignFleet(unittest.TestCase):
    """The defect this class exists for.

    On 2026-09-12 every NEEDS-HUMAN page named a workspace id-space this host
    does not own (wY, wZ, wW, w0, w12, w14) while the local fleet was entirely
    w5M/w60/w6T/w6Y/w7B-w7G. The first guard suppressed all of them and its
    --audit reported "100% phantom", which is a false negative dressed up as a
    fix: our pane list is not evidence about another host's panes.
    """

    def test_untracked_target_escalates_even_though_pane_is_absent(self):
        self.assertNotIn("wZ:p7", LIVE)
        self.assertTrue(g.should_escalate("herdr:wZ:p7", LIVE, OURS))

    def test_tracked_but_destroyed_pane_is_still_suppressed(self):
        """Ownership must not disable the real fix."""
        self.assertFalse(g.should_escalate("herdr:wY:p1", LIVE, OURS))

    def test_every_foreign_workspace_from_the_incident_escalates(self):
        for target in ("herdr:wY:p5", "herdr:wZ:p7", "herdr:wW:pD",
                       "herdr:w0:p1", "herdr:w12:p1", "herdr:w14:p2"):
            self.assertTrue(g.should_escalate(target, LIVE, OURS), target)

    def test_empty_ladder_keeps_pre_ownership_behaviour(self):
        """No ladder => no ownership claim; the pane check still decides."""
        self.assertFalse(g.should_escalate("herdr:wZ:p7", LIVE, set()))

    def test_is_ours_reads_nudge_dict(self):
        with mock.patch.object(g, "NUDGE_STATE", _state_file(self, OURS)):
            self.assertTrue(g.is_ours("herdr:wY:p1"))
            self.assertFalse(g.is_ours("herdr:wZ:p7"))

    def test_unreadable_ladder_is_not_an_ownership_claim(self):
        with mock.patch.object(g, "NUDGE_STATE", Path("/nonexistent/ladder.json")):
            self.assertEqual(g.ladder_targets(), set())
            # Empty ladder => fall back to the pane check, not blanket silence.
            self.assertTrue(g.should_escalate("herdr:w6Y:p3", LIVE))


class RealWorld(unittest.TestCase):
    def test_this_escalation_is_suppressed(self):
        """herdr:wY:p1 against the real fleet observed on 2026-09-12."""
        real = {
            "w5M:p1", "w5M:p8", "w5M:pB", "w6T:p3", "w6T:pF", "w6T:pG",
            "w6T:pH", "w6Y:p1", "w6Y:p3", "w60:p1", "w60:pD",
        }
        self.assertFalse(g.should_escalate("herdr:wY:p1", real, OURS))
        self.assertTrue(g.should_escalate("herdr:w6Y:p3", real, OURS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
