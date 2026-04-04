"""Tests for lidco.goals.monitor."""
from __future__ import annotations

import unittest

from lidco.goals.monitor import ProgressMonitor, SubtaskStatus


class TestProgressMonitor(unittest.TestCase):
    def setUp(self):
        self.mon = ProgressMonitor()

    def test_add_subtask(self):
        self.mon.add_subtask("st-1")
        self.assertIn("st-1", self.mon._statuses)

    def test_add_subtask_idempotent(self):
        self.mon.add_subtask("st-1")
        self.mon.update("st-1", "done")
        self.mon.add_subtask("st-1")  # should not reset
        self.assertEqual(self.mon._statuses["st-1"].status, "done")

    def test_update_valid_status(self):
        self.mon.add_subtask("st-1")
        self.mon.update("st-1", "in_progress")
        self.assertEqual(self.mon._statuses["st-1"].status, "in_progress")

    def test_update_invalid_status_raises(self):
        self.mon.add_subtask("st-1")
        with self.assertRaises(ValueError):
            self.mon.update("st-1", "invalid")

    def test_update_unknown_subtask_raises(self):
        with self.assertRaises(KeyError):
            self.mon.update("nonexistent", "done")

    def test_completion_pct_empty(self):
        self.assertEqual(self.mon.completion_pct(), 0.0)

    def test_completion_pct_partial(self):
        self.mon.add_subtask("st-1")
        self.mon.add_subtask("st-2")
        self.mon.update("st-1", "done")
        self.assertAlmostEqual(self.mon.completion_pct(), 50.0)

    def test_completion_pct_all_done(self):
        self.mon.add_subtask("st-1")
        self.mon.add_subtask("st-2")
        self.mon.update("st-1", "done")
        self.mon.update("st-2", "done")
        self.assertAlmostEqual(self.mon.completion_pct(), 100.0)

    def test_add_blocker(self):
        self.mon.add_blocker("Waiting for API key")
        self.assertEqual(self.mon.blockers(), ["Waiting for API key"])

    def test_remove_blocker(self):
        self.mon.add_blocker("blocked")
        self.mon.remove_blocker("blocked")
        self.assertEqual(self.mon.blockers(), [])

    def test_report_structure(self):
        self.mon.add_subtask("st-1")
        self.mon.add_subtask("st-2")
        self.mon.update("st-1", "done")
        self.mon.add_blocker("issue")
        rpt = self.mon.report()
        self.assertEqual(rpt["total"], 2)
        self.assertEqual(rpt["done"], 1)
        self.assertEqual(rpt["pending"], 1)
        self.assertAlmostEqual(rpt["completion_pct"], 50.0)
        self.assertEqual(rpt["blockers"], ["issue"])

    def test_report_all_statuses(self):
        for sid in ("a", "b", "c", "d"):
            self.mon.add_subtask(sid)
        self.mon.update("a", "done")
        self.mon.update("b", "in_progress")
        self.mon.update("c", "blocked")
        rpt = self.mon.report()
        self.assertEqual(rpt["done"], 1)
        self.assertEqual(rpt["in_progress"], 1)
        self.assertEqual(rpt["blocked"], 1)
        self.assertEqual(rpt["pending"], 1)


class TestSubtaskStatus(unittest.TestCase):
    def test_default_status(self):
        s = SubtaskStatus(subtask_id="st-1")
        self.assertEqual(s.status, "pending")


if __name__ == "__main__":
    unittest.main()
