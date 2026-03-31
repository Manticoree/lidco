"""Tests for RetryExecutor."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from lidco.resilience.retry_executor import RetryConfig, RetryExecutor, RetryResult


def _run(coro):
    return asyncio.run(coro)


class TestRetryConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = RetryConfig()
        self.assertEqual(cfg.max_retries, 3)
        self.assertEqual(cfg.base_delay, 1.0)
        self.assertEqual(cfg.max_delay, 30.0)
        self.assertEqual(cfg.backoff_factor, 2.0)
        self.assertEqual(cfg.retryable_exceptions, (Exception,))

    def test_custom(self):
        cfg = RetryConfig(max_retries=5, base_delay=0.5, max_delay=10.0, backoff_factor=3.0)
        self.assertEqual(cfg.max_retries, 5)
        self.assertEqual(cfg.base_delay, 0.5)


class TestRetryResult(unittest.TestCase):
    def test_success_result(self):
        r = RetryResult(success=True, result=42, attempts=1, total_time=0.1)
        self.assertTrue(r.success)
        self.assertEqual(r.result, 42)
        self.assertIsNone(r.last_error)

    def test_failure_result(self):
        err = ValueError("boom")
        r = RetryResult(success=False, result=None, attempts=3, total_time=1.0, last_error=err)
        self.assertFalse(r.success)
        self.assertIs(r.last_error, err)


class TestRetryExecutor(unittest.TestCase):
    def _fast_config(self, max_retries=3):
        return RetryConfig(max_retries=max_retries, base_delay=0.0, max_delay=0.0)

    def test_success_first_try(self):
        ex = RetryExecutor(self._fast_config())
        result = ex.execute(lambda: 42)
        self.assertTrue(result.success)
        self.assertEqual(result.result, 42)
        self.assertEqual(result.attempts, 1)

    def test_failure_then_success(self):
        counter = {"n": 0}

        def flaky():
            counter["n"] += 1
            if counter["n"] < 3:
                raise RuntimeError("flaky")
            return "ok"

        ex = RetryExecutor(self._fast_config())
        result = ex.execute(flaky)
        self.assertTrue(result.success)
        self.assertEqual(result.result, "ok")
        self.assertEqual(result.attempts, 3)

    def test_all_retries_exhausted(self):
        def always_fail():
            raise ValueError("always")

        ex = RetryExecutor(self._fast_config(max_retries=2))
        result = ex.execute(always_fail)
        self.assertFalse(result.success)
        self.assertIsNone(result.result)
        self.assertEqual(result.attempts, 3)  # 1 initial + 2 retries
        self.assertIsInstance(result.last_error, ValueError)

    def test_non_retryable_exception(self):
        cfg = RetryConfig(max_retries=3, base_delay=0.0, retryable_exceptions=(ValueError,))
        ex = RetryExecutor(cfg)

        def raise_type_error():
            raise TypeError("wrong type")

        with self.assertRaises(TypeError):
            ex.execute(raise_type_error)

    def test_stats_tracking(self):
        ex = RetryExecutor(self._fast_config())
        ex.execute(lambda: 1)
        s = ex.stats
        self.assertEqual(s["total_executions"], 1)
        self.assertEqual(s["total_failures"], 0)

    def test_stats_after_failure(self):
        ex = RetryExecutor(self._fast_config(max_retries=1))
        ex.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        s = ex.stats
        self.assertEqual(s["total_executions"], 1)
        self.assertEqual(s["total_failures"], 1)
        self.assertEqual(s["total_retries"], 1)

    def test_reset_stats(self):
        ex = RetryExecutor(self._fast_config())
        ex.execute(lambda: 1)
        ex.reset_stats()
        s = ex.stats
        self.assertEqual(s["total_executions"], 0)

    def test_calculate_delay_exponential(self):
        cfg = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=30.0)
        ex = RetryExecutor(cfg)
        with patch("lidco.resilience.retry_executor.random.uniform", return_value=0.0):
            d0 = ex._calculate_delay(0)
            d1 = ex._calculate_delay(1)
            d2 = ex._calculate_delay(2)
        self.assertAlmostEqual(d0, 1.0)
        self.assertAlmostEqual(d1, 2.0)
        self.assertAlmostEqual(d2, 4.0)

    def test_calculate_delay_capped(self):
        cfg = RetryConfig(base_delay=10.0, backoff_factor=10.0, max_delay=15.0)
        ex = RetryExecutor(cfg)
        with patch("lidco.resilience.retry_executor.random.uniform", return_value=0.0):
            delay = ex._calculate_delay(5)
        self.assertAlmostEqual(delay, 15.0)

    def test_calculate_delay_jitter(self):
        cfg = RetryConfig(base_delay=1.0, backoff_factor=2.0, max_delay=30.0)
        ex = RetryExecutor(cfg)
        # jitter adds up to 10% of delay
        delay = ex._calculate_delay(0)
        self.assertGreaterEqual(delay, 1.0)
        self.assertLessEqual(delay, 1.1)

    def test_default_config_when_none(self):
        ex = RetryExecutor(None)
        self.assertEqual(ex._config.max_retries, 3)

    def test_zero_retries(self):
        ex = RetryExecutor(self._fast_config(max_retries=0))
        result = ex.execute(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 1)

    def test_total_time_tracked(self):
        ex = RetryExecutor(self._fast_config())
        result = ex.execute(lambda: 1)
        self.assertGreaterEqual(result.total_time, 0.0)

    # --- Async tests ---

    def test_async_success(self):
        async def ok():
            return 99

        ex = RetryExecutor(self._fast_config())
        result = _run(ex.async_execute(ok))
        self.assertTrue(result.success)
        self.assertEqual(result.result, 99)
        self.assertEqual(result.attempts, 1)

    def test_async_retry_then_success(self):
        counter = {"n": 0}

        async def flaky():
            counter["n"] += 1
            if counter["n"] < 2:
                raise RuntimeError("flaky")
            return "async-ok"

        ex = RetryExecutor(self._fast_config())
        result = _run(ex.async_execute(flaky))
        self.assertTrue(result.success)
        self.assertEqual(result.result, "async-ok")
        self.assertEqual(result.attempts, 2)

    def test_async_all_fail(self):
        async def fail():
            raise ValueError("async-fail")

        ex = RetryExecutor(self._fast_config(max_retries=1))
        result = _run(ex.async_execute(fail))
        self.assertFalse(result.success)
        self.assertEqual(result.attempts, 2)

    def test_async_non_retryable(self):
        cfg = RetryConfig(max_retries=3, base_delay=0.0, retryable_exceptions=(ValueError,))
        ex = RetryExecutor(cfg)

        async def raise_type():
            raise TypeError("wrong")

        with self.assertRaises(TypeError):
            _run(ex.async_execute(raise_type))

    def test_async_stats(self):
        async def ok():
            return 1

        ex = RetryExecutor(self._fast_config())
        _run(ex.async_execute(ok))
        self.assertEqual(ex.stats["total_executions"], 1)

    def test_multiple_executions_stats(self):
        ex = RetryExecutor(self._fast_config())
        ex.execute(lambda: 1)
        ex.execute(lambda: 2)
        self.assertEqual(ex.stats["total_executions"], 2)

    def test_args_forwarded(self):
        def add(a, b):
            return a + b

        ex = RetryExecutor(self._fast_config())
        result = ex.execute(add, 3, 4)
        self.assertEqual(result.result, 7)

    def test_kwargs_forwarded(self):
        def greet(name="world"):
            return f"hello {name}"

        ex = RetryExecutor(self._fast_config())
        result = ex.execute(greet, name="test")
        self.assertEqual(result.result, "hello test")

    def test_async_args_forwarded(self):
        async def add(a, b):
            return a + b

        ex = RetryExecutor(self._fast_config())
        result = _run(ex.async_execute(add, 5, 6))
        self.assertEqual(result.result, 11)

    def test_retries_counted_on_partial_success(self):
        counter = {"n": 0}

        def flaky():
            counter["n"] += 1
            if counter["n"] < 2:
                raise RuntimeError("x")
            return "ok"

        ex = RetryExecutor(self._fast_config())
        ex.execute(flaky)
        s = ex.stats
        self.assertEqual(s["total_retries"], 1)


if __name__ == "__main__":
    unittest.main()
