import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import StateStore  # noqa: E402


class FakeResult:
    def __init__(self, name, healthy, detail="", fix_hint=""):
        self.name = name
        self.healthy = healthy
        self.detail = detail
        self.fix_hint = fix_hint


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        os.unlink(tmp.name)  # start from "state file doesn't exist yet"
        self.state_path = tmp.name
        self.addCleanup(self._cleanup)
        self.store = StateStore(self.state_path)

    def _cleanup(self):
        for suffix in ("", ".tmp"):
            p = self.state_path + suffix
            if os.path.exists(p):
                os.unlink(p)

    def test_first_sighting_is_a_silent_baseline(self):
        alerts = self.store.apply([FakeResult("A", True)])
        self.assertEqual(alerts, [])

    def test_healthy_to_down_alerts_once_with_fix_hint(self):
        self.store.apply([FakeResult("A", True)])
        alerts = self.store.apply([FakeResult("A", False, detail="HTTP 401", fix_hint="reconnect it")])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].kind, "down")
        self.assertIn("A", alerts[0].message)
        self.assertIn("HTTP 401", alerts[0].message)
        self.assertIn("reconnect it", alerts[0].message)

    def test_staying_down_never_re_alerts(self):
        self.store.apply([FakeResult("A", True)])
        self.store.apply([FakeResult("A", False)])
        alerts = self.store.apply([FakeResult("A", False)])
        self.assertEqual(alerts, [])

    def test_down_to_healthy_alerts_recovered(self):
        self.store.apply([FakeResult("A", True)])
        self.store.apply([FakeResult("A", False)])
        alerts = self.store.apply([FakeResult("A", True)])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].kind, "recovered")

    def test_staying_healthy_never_re_alerts(self):
        self.store.apply([FakeResult("A", True)])
        alerts = self.store.apply([FakeResult("A", True)])
        self.assertEqual(alerts, [])

    def test_multiple_connections_are_independent(self):
        self.store.apply([FakeResult("A", True), FakeResult("B", True)])
        alerts = self.store.apply([FakeResult("A", False), FakeResult("B", True)])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].name, "A")

    def test_daily_heartbeat_fires_once_per_day_when_all_healthy(self):
        first = self.store.apply([FakeResult("A", True)], daily_heartbeat=True)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].kind, "heartbeat")
        second = self.store.apply([FakeResult("A", True)], daily_heartbeat=True)
        self.assertEqual(second, [], "heartbeat must not fire twice in the same day")

    def test_daily_heartbeat_skipped_when_something_is_down(self):
        alerts = self.store.apply([FakeResult("A", False)], daily_heartbeat=True)
        # first sighting of A (down): silent baseline, and no heartbeat since not all healthy
        self.assertEqual(alerts, [])

    def test_state_persists_across_store_instances(self):
        self.store.apply([FakeResult("A", True)])
        fresh_store = StateStore(self.state_path)
        alerts = fresh_store.apply([FakeResult("A", False)])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].kind, "down")


if __name__ == "__main__":
    unittest.main()
