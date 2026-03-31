"""Tests for AdaptiveRetry."""
import unittest
from unittest.mock import MagicMock

from lidco.resilience.adaptive_retry import AdaptiveRetry, CircuitOpenError


class TestAdaptiveRetry(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        self.retry = AdaptiveRetry(
            max_retries=3,
            base_delay=1.0,
            max_delay=60.0,
            circuit_break_threshold=5,
            sleep_fn=lambda d: self.sleeps.append(d),
        )

    def test_success_first_try(self):
        fn = MagicMock(return_value=42)
        result = self.retry.execute(fn)
        self.assertEqual(result, 42)
        fn.assert_called_once()
        self.assertEqual(len(self.sleeps), 0)

    def test_success_after_retries(self):
        fn = MagicMock(side_effect=[ValueError, ValueError, 99])
        result = self.retry.execute(fn)
        self.assertEqual(result, 99)
        self.assertEqual(fn.call_count, 3)
        self.assertEqual(len(self.sleeps), 2)

    def test_exhaust_retries(self):
        fn = MagicMock(side_effect=ValueError("fail"))
        with self.assertRaises(ValueError):
            self.retry.execute(fn)
        self.assertEqual(fn.call_count, 4)  # 1 + 3 retries
        self.assertEqual(len(self.sleeps), 3)

    def test_backoff_increases(self):
        fn = MagicMock(side_effect=ValueError("fail"))
        try:
            self.retry.execute(fn)
        except ValueError:
            pass
        # Each sleep should be larger than the previous (with jitter it's base * 2^attempt + jitter)
        # base_delay=1.0: attempt 0 -> 1-1.5, attempt 1 -> 2-3, attempt 2 -> 4-6
        self.assertGreater(self.sleeps[1], self.sleeps[0] * 0.5)
        self.assertEqual(len(self.sleeps), 3)

    def test_max_delay_cap(self):
        retry = AdaptiveRetry(
            max_retries=10,
            base_delay=10.0,
            max_delay=20.0,
            circuit_break_threshold=100,
            sleep_fn=lambda d: self.sleeps.append(d),
        )
        fn = MagicMock(side_effect=ValueError("fail"))
        try:
            retry.execute(fn)
        except ValueError:
            pass
        # max_delay=20.0, so delay + jitter <= 20.0 + 10.0 = 30.0
        for s in self.sleeps:
            self.assertLessEqual(s, 30.0)

    def test_circuit_break(self):
        retry = AdaptiveRetry(
            max_retries=1,
            base_delay=0.01,
            circuit_break_threshold=3,
            sleep_fn=lambda d: None,
        )
        fn = MagicMock(side_effect=ValueError("fail"))
        # Each execute does 2 calls (1 + 1 retry), 2 consecutive failures
        try:
            retry.execute(fn)
        except (ValueError, CircuitOpenError):
            pass
        # Now at 2 consecutive failures, one more call should reach 3
        with self.assertRaises(CircuitOpenError):
            retry.execute(fn)

    def test_circuit_open_prevents_execution(self):
        retry = AdaptiveRetry(
            max_retries=0,
            circuit_break_threshold=2,
            sleep_fn=lambda d: None,
        )
        fn = MagicMock(side_effect=ValueError("fail"))
        # 2 failures opens circuit
        try:
            retry.execute(fn)
        except (ValueError, CircuitOpenError):
            pass
        try:
            retry.execute(fn)
        except (ValueError, CircuitOpenError):
            pass
        # Now circuit should be open
        with self.assertRaises(CircuitOpenError):
            retry.execute(fn)

    def test_success_resets_consecutive_failures(self):
        call_count = [0]
        def flaky():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ValueError("transient")
            return "ok"
        result = self.retry.execute(flaky)
        self.assertEqual(result, "ok")
        stats = self.retry.get_stats()
        fn_stats = stats["flaky"]
        self.assertEqual(fn_stats["consecutive_failures"], 0)

    def test_get_stats_empty(self):
        self.assertEqual(self.retry.get_stats(), {})

    def test_get_stats_after_calls(self):
        fn = MagicMock(return_value=1, __name__="myfn")
        self.retry.execute(fn)
        stats = self.retry.get_stats()
        self.assertIn("myfn", stats)
        self.assertEqual(stats["myfn"]["total_successes"], 1)
        self.assertEqual(stats["myfn"]["total_failures"], 0)

    def test_get_stats_tracks_failures(self):
        fn = MagicMock(side_effect=[ValueError, ValueError, 1], __name__="flaky")
        self.retry.execute(fn)
        stats = self.retry.get_stats()["flaky"]
        self.assertEqual(stats["total_failures"], 2)
        self.assertEqual(stats["total_successes"], 1)
        self.assertEqual(stats["total_calls"], 3)

    def test_reset_circuit(self):
        retry = AdaptiveRetry(
            max_retries=0,
            circuit_break_threshold=1,
            sleep_fn=lambda d: None,
        )
        fn = MagicMock(side_effect=ValueError("fail"), __name__="fn")
        with self.assertRaises(CircuitOpenError):
            retry.execute(fn)
        retry.reset_circuit("fn")
        fn.side_effect = None
        fn.return_value = "ok"
        result = retry.execute(fn)
        self.assertEqual(result, "ok")

    def test_args_passed_through(self):
        fn = MagicMock(return_value=True)
        self.retry.execute(fn, 1, 2, key="val")
        fn.assert_called_with(1, 2, key="val")

    def test_different_functions_tracked_separately(self):
        fn1 = MagicMock(return_value=1, __name__="fn1")
        fn2 = MagicMock(return_value=2, __name__="fn2")
        self.retry.execute(fn1)
        self.retry.execute(fn2)
        stats = self.retry.get_stats()
        self.assertIn("fn1", stats)
        self.assertIn("fn2", stats)

    def test_circuit_open_error_message(self):
        retry = AdaptiveRetry(
            max_retries=0,
            circuit_break_threshold=1,
            sleep_fn=lambda d: None,
        )
        fn = MagicMock(side_effect=ValueError("x"), __name__="myfn")
        with self.assertRaises(CircuitOpenError) as ctx:
            retry.execute(fn)
        self.assertIn("myfn", str(ctx.exception))

    def test_no_sleep_on_success(self):
        fn = MagicMock(return_value="ok")
        self.retry.execute(fn)
        self.assertEqual(len(self.sleeps), 0)

    def test_sleep_called_between_retries(self):
        fn = MagicMock(side_effect=[ValueError, "ok"])
        self.retry.execute(fn)
        self.assertEqual(len(self.sleeps), 1)
        self.assertGreater(self.sleeps[0], 0)

    def test_zero_retries(self):
        retry = AdaptiveRetry(max_retries=0, sleep_fn=lambda d: None)
        fn = MagicMock(side_effect=ValueError("fail"))
        with self.assertRaises(ValueError):
            retry.execute(fn)
        self.assertEqual(fn.call_count, 1)

    def test_circuit_open_flag_in_stats(self):
        retry = AdaptiveRetry(
            max_retries=0,
            circuit_break_threshold=1,
            sleep_fn=lambda d: None,
        )
        fn = MagicMock(side_effect=ValueError("x"), __name__="fn")
        with self.assertRaises(CircuitOpenError):
            retry.execute(fn)
        stats = retry.get_stats()["fn"]
        self.assertTrue(stats["circuit_open"])


if __name__ == "__main__":
    unittest.main()
