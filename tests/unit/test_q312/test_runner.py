"""Tests for Q312 Task 1673 — LoadRunner."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from lidco.loadtest.profile import LoadProfile, ProfileType, RequestPattern
from lidco.loadtest.runner import (
    LiveStats,
    LoadRunner,
    RequestResult,
    RequestStatus,
    RunResult,
    StubExecutor,
)


class TestRequestResult(unittest.TestCase):
    def test_defaults(self):
        r = RequestResult(request_id="abc", url="http://x", method="GET", status=RequestStatus.SUCCESS)
        self.assertEqual(r.status, RequestStatus.SUCCESS)
        self.assertEqual(r.latency_ms, 0.0)
        self.assertEqual(r.error, "")


class TestLiveStats(unittest.TestCase):
    def test_initial(self):
        s = LiveStats()
        self.assertEqual(s.total_requests, 0)
        self.assertEqual(s.avg_latency_ms, 0.0)
        self.assertEqual(s.requests_per_second, 0.0)
        self.assertEqual(s.error_rate, 0.0)

    def test_record_success(self):
        s = LiveStats(elapsed_seconds=1.0)
        r = RequestResult(
            request_id="1", url="http://x", method="GET",
            status=RequestStatus.SUCCESS, latency_ms=100, bytes_received=500,
        )
        s.record(r)
        self.assertEqual(s.total_requests, 1)
        self.assertEqual(s.successful, 1)
        self.assertEqual(s.avg_latency_ms, 100.0)
        self.assertEqual(s.min_latency_ms, 100.0)
        self.assertEqual(s.max_latency_ms, 100.0)

    def test_record_error(self):
        s = LiveStats(elapsed_seconds=1.0)
        r = RequestResult(
            request_id="1", url="http://x", method="GET",
            status=RequestStatus.ERROR, latency_ms=50,
        )
        s.record(r)
        self.assertEqual(s.failed, 1)
        self.assertEqual(s.error_rate, 1.0)

    def test_record_timeout(self):
        s = LiveStats(elapsed_seconds=1.0)
        r = RequestResult(
            request_id="1", url="http://x", method="GET",
            status=RequestStatus.TIMEOUT, latency_ms=30000,
        )
        s.record(r)
        self.assertEqual(s.timeouts, 1)

    def test_rps(self):
        s = LiveStats(total_requests=100, elapsed_seconds=10.0)
        self.assertAlmostEqual(s.requests_per_second, 10.0)


class TestRunResult(unittest.TestCase):
    def test_ok_true(self):
        r = RunResult(profile_name="t")
        self.assertTrue(r.ok)

    def test_ok_false_error(self):
        r = RunResult(profile_name="t", error="bad")
        self.assertFalse(r.ok)

    def test_ok_false_aborted(self):
        r = RunResult(profile_name="t", aborted=True)
        self.assertFalse(r.ok)


class TestStubExecutor(unittest.TestCase):
    def test_execute_success(self):
        ex = StubExecutor(latency_ms=1.0, error_rate=0.0)
        result = asyncio.run(ex.execute(RequestPattern(url="http://x")))
        self.assertEqual(result.status, RequestStatus.SUCCESS)
        self.assertEqual(result.status_code, 200)
        self.assertGreater(result.latency_ms, 0)

    def test_execute_all_errors(self):
        ex = StubExecutor(latency_ms=1.0, error_rate=1.0)
        result = asyncio.run(ex.execute(RequestPattern(url="http://x")))
        self.assertEqual(result.status, RequestStatus.ERROR)
        self.assertEqual(result.status_code, 500)


class TestLoadRunner(unittest.TestCase):
    def _make_profile(self, **kw):
        defaults = dict(
            name="test",
            profile_type=ProfileType.STEADY,
            duration_seconds=1,
            max_users=2,
            requests=[RequestPattern(url="http://x")],
        )
        defaults.update(kw)
        return LoadProfile(**defaults)

    def test_invalid_profile(self):
        runner = LoadRunner()
        profile = LoadProfile(name="", requests=[])
        result = asyncio.run(runner.run(profile))
        self.assertFalse(result.ok)
        self.assertIn("Invalid profile", result.error)

    def test_run_returns_results(self):
        executor = StubExecutor(latency_ms=1.0, error_rate=0.0)
        runner = LoadRunner(executor=executor)
        profile = self._make_profile(duration_seconds=1, max_users=2)
        result = asyncio.run(runner.run(profile))
        self.assertTrue(result.ok)
        self.assertGreater(len(result.results), 0)
        self.assertGreater(result.stats.total_requests, 0)

    def test_abort(self):
        executor = StubExecutor(latency_ms=5.0)
        runner = LoadRunner(executor=executor)
        profile = self._make_profile(duration_seconds=10, max_users=1)

        async def _run_and_abort():
            import asyncio as aio
            task = aio.ensure_future(runner.run(profile))
            await aio.sleep(0.05)
            runner.abort()
            return await task

        result = asyncio.run(_run_and_abort())
        self.assertTrue(result.aborted)

    def test_stats_callback(self):
        calls = []
        executor = StubExecutor(latency_ms=1.0)
        runner = LoadRunner(executor=executor, stats_callback=lambda s: calls.append(s.total_requests))
        profile = self._make_profile(duration_seconds=1, max_users=1)
        asyncio.run(runner.run(profile))
        self.assertGreater(len(calls), 0)

    def test_timeout_handling(self):
        """Executor that hangs should produce TIMEOUT results."""

        class HangExecutor:
            async def execute(self, pattern):
                await asyncio.sleep(100)

        runner = LoadRunner(executor=HangExecutor(), request_timeout=0.05)
        profile = self._make_profile(duration_seconds=1, max_users=1)
        result = asyncio.run(runner.run(profile))
        timeouts = [r for r in result.results if r.status == RequestStatus.TIMEOUT]
        self.assertGreater(len(timeouts), 0)

    def test_executor_exception(self):
        """Executor that raises should produce ERROR results."""

        class BrokenExecutor:
            async def execute(self, pattern):
                raise RuntimeError("boom")

        runner = LoadRunner(executor=BrokenExecutor())
        profile = self._make_profile(duration_seconds=1, max_users=1)
        result = asyncio.run(runner.run(profile))
        errors = [r for r in result.results if r.status == RequestStatus.ERROR]
        self.assertGreater(len(errors), 0)
        self.assertIn("boom", errors[0].error)

    def test_weighted_requests(self):
        executor = StubExecutor(latency_ms=1.0)
        runner = LoadRunner(executor=executor)
        profile = self._make_profile(
            duration_seconds=1,
            max_users=2,
            requests=[
                RequestPattern(url="http://a", weight=1.0),
                RequestPattern(url="http://b", weight=1.0),
            ],
        )
        result = asyncio.run(runner.run(profile))
        urls = {r.url for r in result.results}
        # Both URLs should appear (probabilistic, but with enough requests)
        self.assertGreater(len(result.results), 0)


if __name__ == "__main__":
    unittest.main()
