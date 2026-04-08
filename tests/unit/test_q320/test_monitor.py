"""Tests for cicd.monitor module."""

import json
import os
import tempfile
import time
import unittest

from lidco.cicd.monitor import (
    DurationTrend,
    FlakyTest,
    PipelineMonitor,
    PipelineRun,
    PipelineStats,
)


class TestPipelineRun(unittest.TestCase):
    def test_create(self):
        r = PipelineRun(
            run_id="1", pipeline="ci", status="running", started_at=1000.0
        )
        self.assertEqual(r.run_id, "1")
        self.assertEqual(r.status, "running")

    def test_finish_immutable(self):
        r = PipelineRun(run_id="1", pipeline="ci", status="running", started_at=1000.0)
        finished = r.finish("success")
        # Original unchanged
        self.assertEqual(r.status, "running")
        # New run has finished state
        self.assertEqual(finished.status, "success")
        self.assertGreater(finished.finished_at, 0)
        self.assertGreater(finished.duration, 0)

    def test_finish_failure(self):
        r = PipelineRun(run_id="2", pipeline="ci", status="running", started_at=time.time())
        finished = r.finish("failure", failure_reason="test failed")
        self.assertEqual(finished.status, "failure")
        self.assertEqual(finished.failure_reason, "test failed")

    def test_default_fields(self):
        r = PipelineRun(run_id="1", pipeline="ci", status="running", started_at=0.0)
        self.assertEqual(r.duration, 0.0)
        self.assertEqual(r.stages, {})
        self.assertEqual(r.failure_reason, "")
        self.assertEqual(r.commit_sha, "")


class TestDurationTrend(unittest.TestCase):
    def test_frozen(self):
        t = DurationTrend(
            pipeline="ci", avg_duration=10, min_duration=5, max_duration=15,
            p50_duration=10, p95_duration=14, total_runs=5,
        )
        with self.assertRaises(AttributeError):
            t.avg_duration = 20  # type: ignore[misc]


class TestFlakyTest(unittest.TestCase):
    def test_frozen(self):
        f = FlakyTest(name="test_x", failure_count=2, total_runs=10, flake_rate=0.2)
        with self.assertRaises(AttributeError):
            f.name = "y"  # type: ignore[misc]


class TestPipelineMonitor(unittest.TestCase):
    def _make_monitor(self):
        return PipelineMonitor()

    def test_record_and_get(self):
        mon = self._make_monitor()
        run = PipelineRun(run_id="1", pipeline="ci", status="success", started_at=1000.0, duration=30.0)
        mon.record_run(run)
        runs = mon.get_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].run_id, "1")

    def test_get_runs_filter_pipeline(self):
        mon = self._make_monitor()
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="success", started_at=1000.0, duration=10.0))
        mon.record_run(PipelineRun(run_id="2", pipeline="deploy", status="success", started_at=1001.0, duration=20.0))
        ci_runs = mon.get_runs(pipeline="ci")
        self.assertEqual(len(ci_runs), 1)
        self.assertEqual(ci_runs[0].pipeline, "ci")

    def test_get_runs_limit(self):
        mon = self._make_monitor()
        for i in range(20):
            mon.record_run(PipelineRun(run_id=str(i), pipeline="ci", status="success", started_at=float(i), duration=10.0))
        runs = mon.get_runs(limit=5)
        self.assertEqual(len(runs), 5)

    def test_get_stats_empty(self):
        mon = self._make_monitor()
        stats = mon.get_stats("ci")
        self.assertEqual(stats.total_runs, 0)
        self.assertEqual(stats.success_rate, 0.0)

    def test_get_stats_basic(self):
        mon = self._make_monitor()
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=30.0))
        mon.record_run(PipelineRun(run_id="2", pipeline="ci", status="failure", started_at=200.0, duration=20.0))
        mon.record_run(PipelineRun(run_id="3", pipeline="ci", status="success", started_at=300.0, duration=40.0))

        stats = mon.get_stats("ci")
        self.assertEqual(stats.total_runs, 3)
        self.assertEqual(stats.success_count, 2)
        self.assertEqual(stats.failure_count, 1)
        self.assertAlmostEqual(stats.success_rate, 2 / 3, places=2)
        self.assertAlmostEqual(stats.avg_duration, 30.0, places=1)

    def test_get_stats_ignores_running(self):
        mon = self._make_monitor()
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="running", started_at=100.0))
        stats = mon.get_stats("ci")
        self.assertEqual(stats.total_runs, 0)

    def test_duration_trend(self):
        mon = self._make_monitor()
        for i in range(10):
            mon.record_run(PipelineRun(
                run_id=str(i), pipeline="ci", status="success",
                started_at=float(i * 100), duration=10.0 + i,
            ))
        stats = mon.get_stats("ci")
        self.assertIsNotNone(stats.trend)
        self.assertEqual(stats.trend.total_runs, 10)
        self.assertGreater(stats.trend.p95_duration, stats.trend.p50_duration)


class TestFlakyDetection(unittest.TestCase):
    def test_flaky_detection(self):
        mon = PipelineMonitor()
        # Report a test that sometimes fails
        for _ in range(7):
            mon.report_test_result("test_flaky", True)
        for _ in range(3):
            mon.report_test_result("test_flaky", False)

        # Also a stable test
        for _ in range(10):
            mon.report_test_result("test_stable", True)

        # Need at least one run for stats
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=10.0))
        stats = mon.get_stats("ci")
        flaky_names = [f.name for f in stats.flaky_tests]
        self.assertIn("test_flaky", flaky_names)
        self.assertNotIn("test_stable", flaky_names)

    def test_no_flaky_when_all_pass(self):
        mon = PipelineMonitor()
        for _ in range(10):
            mon.report_test_result("test_good", True)
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=10.0))
        stats = mon.get_stats("ci")
        self.assertEqual(stats.flaky_tests, [])

    def test_no_flaky_below_threshold(self):
        mon = PipelineMonitor()
        # Only 2 runs, need >= 3
        mon.report_test_result("test_x", True)
        mon.report_test_result("test_x", False)
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=10.0))
        stats = mon.get_stats("ci")
        self.assertEqual(stats.flaky_tests, [])


class TestPersistence(unittest.TestCase):
    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            mon = PipelineMonitor(storage_path=path)
            mon.record_run(PipelineRun(
                run_id="1", pipeline="ci", status="success",
                started_at=100.0, finished_at=130.0, duration=30.0,
                commit_sha="abc123",
            ))

            # Load in new instance
            mon2 = PipelineMonitor(storage_path=path)
            runs = mon2.get_runs()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].run_id, "1")
            self.assertEqual(runs[0].commit_sha, "abc123")
        finally:
            os.unlink(path)

    def test_no_persistence_without_path(self):
        mon = PipelineMonitor()
        mon.record_run(PipelineRun(run_id="1", pipeline="ci", status="success", started_at=100.0, duration=10.0))
        # No error, just no file written


if __name__ == "__main__":
    unittest.main()
