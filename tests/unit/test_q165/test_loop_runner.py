"""Tests for LoopRunner (Q165/Task 940)."""
from __future__ import annotations

import unittest

from lidco.session.loop_runner import LoopConfig, LoopRunner


class TestLoopConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = LoopConfig(command="/status", interval_seconds=5)
        self.assertEqual(cfg.max_iterations, 0)
        self.assertFalse(cfg.stop_on_error)

    def test_custom(self):
        cfg = LoopConfig(command="cmd", interval_seconds=10, max_iterations=3, stop_on_error=True)
        self.assertEqual(cfg.max_iterations, 3)
        self.assertTrue(cfg.stop_on_error)


class TestParseInterval(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(LoopRunner.parse_interval("30s"), 30)

    def test_minutes(self):
        self.assertEqual(LoopRunner.parse_interval("5m"), 300)

    def test_hours(self):
        self.assertEqual(LoopRunner.parse_interval("1h"), 3600)

    def test_plain_number(self):
        self.assertEqual(LoopRunner.parse_interval("10"), 10)

    def test_whitespace(self):
        self.assertEqual(LoopRunner.parse_interval("  15s  "), 15)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            LoopRunner.parse_interval("")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            LoopRunner.parse_interval("abc")

    def test_case_insensitive(self):
        self.assertEqual(LoopRunner.parse_interval("5M"), 300)


class TestLoopRunnerExecution(unittest.TestCase):
    def test_single_iteration(self):
        cfg = LoopConfig(command="echo", interval_seconds=0, max_iterations=1)
        runner = LoopRunner(cfg)
        runner.start(lambda cmd: f"out:{cmd}")
        results = runner.results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["output"], "out:echo")
        self.assertIsNone(results[0]["error"])

    def test_multiple_iterations(self):
        cfg = LoopConfig(command="x", interval_seconds=0, max_iterations=3)
        runner = LoopRunner(cfg)
        runner.start(lambda cmd: "ok")
        self.assertEqual(len(runner.results()), 3)

    def test_stop_on_error(self):
        cfg = LoopConfig(command="fail", interval_seconds=0, max_iterations=5, stop_on_error=True)
        runner = LoopRunner(cfg)

        def _fail(cmd):
            raise RuntimeError("boom")

        runner.start(_fail)
        results = runner.results()
        self.assertEqual(len(results), 1)
        self.assertIn("boom", results[0]["error"])

    def test_continue_on_error(self):
        cfg = LoopConfig(command="x", interval_seconds=0, max_iterations=3, stop_on_error=False)
        runner = LoopRunner(cfg)
        call_count = 0

        def _sometimes_fail(cmd):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("oops")
            return "ok"

        runner.start(_sometimes_fail)
        results = runner.results()
        self.assertEqual(len(results), 3)
        self.assertIsNotNone(results[1]["error"])
        self.assertEqual(results[0]["output"], "ok")

    def test_is_running_false_after_done(self):
        cfg = LoopConfig(command="x", interval_seconds=0, max_iterations=1)
        runner = LoopRunner(cfg)
        runner.start(lambda cmd: "ok")
        self.assertFalse(runner.is_running)

    def test_results_are_timestamped(self):
        cfg = LoopConfig(command="x", interval_seconds=0, max_iterations=1)
        runner = LoopRunner(cfg)
        runner.start(lambda cmd: "ok")
        r = runner.results()[0]
        self.assertIn("timestamp", r)
        self.assertIsInstance(r["timestamp"], float)

    def test_results_returns_copy(self):
        cfg = LoopConfig(command="x", interval_seconds=0, max_iterations=1)
        runner = LoopRunner(cfg)
        runner.start(lambda cmd: "ok")
        r1 = runner.results()
        r2 = runner.results()
        self.assertIsNot(r1, r2)


if __name__ == "__main__":
    unittest.main()
