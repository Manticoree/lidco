"""Tests for StatusTracker."""
from __future__ import annotations

import unittest

from lidco.cloud.status_tracker import AgentLog, StatusTracker


class TestAgentLog(unittest.TestCase):
    def test_defaults(self):
        log = AgentLog(agent_id="a1")
        self.assertEqual(log.agent_id, "a1")
        self.assertEqual(log.entries, [])
        self.assertEqual(log.output, "")
        self.assertEqual(log.diff, "")
        self.assertIsNone(log.finished_at)
        self.assertEqual(log.error, "")

    def test_entries_isolation(self):
        l1 = AgentLog(agent_id="a")
        l2 = AgentLog(agent_id="b")
        l1.entries.append("x")
        self.assertEqual(len(l2.entries), 0)


class TestStatusTrackerStartTracking(unittest.TestCase):
    def setUp(self):
        self.tracker = StatusTracker()

    def test_start_tracking(self):
        self.tracker.start_tracking("a1")
        log = self.tracker.get_log("a1")
        self.assertIsNotNone(log)
        self.assertEqual(log.agent_id, "a1")
        self.assertGreater(log.started_at, 0)

    def test_running_after_start(self):
        self.tracker.start_tracking("a1")
        self.assertIn("a1", self.tracker.running())


class TestStatusTrackerLog(unittest.TestCase):
    def setUp(self):
        self.tracker = StatusTracker()

    def test_log_entries(self):
        self.tracker.start_tracking("a1")
        self.tracker.log("a1", "step 1")
        self.tracker.log("a1", "step 2")
        log = self.tracker.get_log("a1")
        self.assertEqual(len(log.entries), 2)
        self.assertEqual(log.entries[0], "step 1")

    def test_log_unknown_agent(self):
        # Should not raise
        self.tracker.log("nope", "msg")


class TestStatusTrackerComplete(unittest.TestCase):
    def setUp(self):
        self.tracker = StatusTracker()

    def test_complete(self):
        self.tracker.start_tracking("a1")
        self.tracker.complete("a1", "done", diff="+line")
        log = self.tracker.get_log("a1")
        self.assertEqual(log.output, "done")
        self.assertEqual(log.diff, "+line")
        self.assertIsNotNone(log.finished_at)

    def test_complete_removes_from_running(self):
        self.tracker.start_tracking("a1")
        self.tracker.complete("a1", "ok")
        self.assertNotIn("a1", self.tracker.running())
        self.assertIn("a1", self.tracker.completed())

    def test_complete_unknown_noop(self):
        self.tracker.complete("nope", "ok")


class TestStatusTrackerFail(unittest.TestCase):
    def setUp(self):
        self.tracker = StatusTracker()

    def test_fail(self):
        self.tracker.start_tracking("a1")
        self.tracker.fail("a1", "boom")
        log = self.tracker.get_log("a1")
        self.assertEqual(log.error, "boom")
        self.assertIsNotNone(log.finished_at)
        self.assertNotIn("a1", self.tracker.running())

    def test_fail_unknown_noop(self):
        self.tracker.fail("nope", "err")


class TestStatusTrackerSummary(unittest.TestCase):
    def test_empty_summary(self):
        tracker = StatusTracker()
        s = tracker.summary()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["running"], 0)

    def test_summary_counts(self):
        tracker = StatusTracker()
        tracker.start_tracking("a1")
        tracker.start_tracking("a2")
        tracker.complete("a1", "ok")
        tracker.fail("a2", "err")
        s = tracker.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["completed"], 1)
        self.assertEqual(s["failed"], 1)
        self.assertEqual(s["running"], 0)


class TestStatusTrackerTrim(unittest.TestCase):
    def test_trim_oldest(self):
        tracker = StatusTracker(max_history=3)
        for i in range(5):
            tracker.start_tracking(f"a{i}")
            tracker.complete(f"a{i}", "ok")
        self.assertLessEqual(len(tracker._logs), 3)


if __name__ == "__main__":
    unittest.main()
