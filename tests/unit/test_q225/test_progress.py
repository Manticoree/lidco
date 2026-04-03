"""Tests for JobProgress (Q225)."""
import time
import unittest

from lidco.jobs.progress import JobProgress, ProgressUpdate


class TestJobProgress(unittest.TestCase):
    def setUp(self):
        self.progress = JobProgress()

    # -- update ----------------------------------------------------

    def test_update_returns_progress(self):
        pu = self.progress.update("j1", 25.0, "step 1")
        self.assertEqual(pu.job_id, "j1")
        self.assertEqual(pu.percentage, 25.0)
        self.assertEqual(pu.message, "step 1")
        self.assertIsNone(pu.substep)

    def test_update_with_substep(self):
        pu = self.progress.update("j1", 50.0, "halfway", substep="parsing")
        self.assertEqual(pu.substep, "parsing")

    def test_update_clamps_percentage(self):
        pu_low = self.progress.update("j1", -10.0, "neg")
        self.assertEqual(pu_low.percentage, 0.0)
        pu_high = self.progress.update("j2", 200.0, "over")
        self.assertEqual(pu_high.percentage, 100.0)

    def test_update_sets_timestamp(self):
        before = time.time()
        pu = self.progress.update("j1", 10.0, "msg")
        self.assertGreaterEqual(pu.timestamp, before)

    # -- get -------------------------------------------------------

    def test_get_latest(self):
        self.progress.update("j1", 10.0, "a")
        self.progress.update("j1", 50.0, "b")
        latest = self.progress.get("j1")
        self.assertEqual(latest.percentage, 50.0)
        self.assertEqual(latest.message, "b")

    def test_get_nonexistent(self):
        self.assertIsNone(self.progress.get("nope"))

    # -- history ---------------------------------------------------

    def test_history(self):
        self.progress.update("j1", 10.0, "a")
        self.progress.update("j1", 50.0, "b")
        self.progress.update("j1", 100.0, "c")
        hist = self.progress.history("j1")
        self.assertEqual(len(hist), 3)
        self.assertEqual(hist[0].percentage, 10.0)
        self.assertEqual(hist[2].percentage, 100.0)

    def test_history_empty(self):
        self.assertEqual(self.progress.history("nope"), [])

    # -- is_complete -----------------------------------------------

    def test_is_complete_true(self):
        self.progress.update("j1", 100.0, "done")
        self.assertTrue(self.progress.is_complete("j1"))

    def test_is_complete_false(self):
        self.progress.update("j1", 50.0, "half")
        self.assertFalse(self.progress.is_complete("j1"))

    def test_is_complete_no_data(self):
        self.assertFalse(self.progress.is_complete("nope"))

    # -- summary ---------------------------------------------------

    def test_summary_shows_active(self):
        self.progress.update("j1", 30.0, "working")
        self.progress.update("j2", 100.0, "done")
        summary = self.progress.summary()
        self.assertIn("j1", summary)
        self.assertNotIn("j2", summary)
        self.assertEqual(summary["j1"]["percentage"], 30.0)

    def test_summary_empty(self):
        self.assertEqual(self.progress.summary(), {})


if __name__ == "__main__":
    unittest.main()
