"""Tests for ErrorBoundary."""
from __future__ import annotations

import asyncio
import unittest

from lidco.resilience.error_boundary import BoundaryResult, ErrorBoundary


def _run(coro):
    return asyncio.run(coro)


class TestBoundaryResult(unittest.TestCase):
    def test_success(self):
        r = BoundaryResult(success=True, value=42)
        self.assertTrue(r.success)
        self.assertIsNone(r.error)
        self.assertIsNone(r.error_type)

    def test_failure(self):
        exc = ValueError("v")
        r = BoundaryResult(success=False, value=None, error=exc, error_type="ValueError")
        self.assertFalse(r.success)
        self.assertEqual(r.error_type, "ValueError")


class TestErrorBoundary(unittest.TestCase):
    def test_catch_success(self):
        eb = ErrorBoundary()
        result = eb.catch(lambda: 42)
        self.assertTrue(result.success)
        self.assertEqual(result.value, 42)
        self.assertIsNone(result.error)

    def test_catch_error(self):
        eb = ErrorBoundary()
        result = eb.catch(lambda: (_ for _ in ()).throw(ValueError("boom")))
        self.assertFalse(result.success)
        self.assertIsNone(result.value)
        self.assertIsInstance(result.error, ValueError)
        self.assertEqual(result.error_type, "ValueError")

    def test_catch_with_default(self):
        eb = ErrorBoundary()
        result = eb.catch(lambda: (_ for _ in ()).throw(RuntimeError("x")), default="fallback")
        self.assertFalse(result.success)
        self.assertEqual(result.value, "fallback")

    def test_catch_traceback_str(self):
        eb = ErrorBoundary()
        result = eb.catch(lambda: (_ for _ in ()).throw(RuntimeError("trace")))
        self.assertIsNotNone(result.traceback_str)
        self.assertIn("RuntimeError", result.traceback_str)

    def test_catch_never_raises(self):
        eb = ErrorBoundary()
        # Should not raise
        result = eb.catch(lambda: 1 / 0)
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ZeroDivisionError")

    def test_error_logged(self):
        eb = ErrorBoundary()
        eb.catch(lambda: (_ for _ in ()).throw(RuntimeError("logged")))
        self.assertEqual(eb.error_count, 1)
        self.assertEqual(len(eb.log), 1)
        self.assertEqual(eb.log[0]["error_type"], "RuntimeError")

    def test_log_has_timestamp(self):
        eb = ErrorBoundary()
        eb.catch(lambda: (_ for _ in ()).throw(RuntimeError("t")))
        self.assertIn("timestamp", eb.log[0])
        self.assertIsInstance(eb.log[0]["timestamp"], float)

    def test_log_has_message(self):
        eb = ErrorBoundary()
        eb.catch(lambda: (_ for _ in ()).throw(ValueError("msg123")))
        self.assertEqual(eb.log[0]["message"], "msg123")

    def test_clear_log(self):
        eb = ErrorBoundary()
        eb.catch(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        eb.clear_log()
        self.assertEqual(eb.error_count, 0)
        self.assertEqual(len(eb.log), 0)

    def test_error_count(self):
        eb = ErrorBoundary()
        self.assertEqual(eb.error_count, 0)
        eb.catch(lambda: (_ for _ in ()).throw(RuntimeError("a")))
        eb.catch(lambda: (_ for _ in ()).throw(ValueError("b")))
        self.assertEqual(eb.error_count, 2)

    def test_success_not_logged(self):
        eb = ErrorBoundary()
        eb.catch(lambda: 42)
        self.assertEqual(eb.error_count, 0)

    def test_catch_with_handler(self):
        eb = ErrorBoundary()

        def handler(exc):
            return f"handled: {exc}"

        result = eb.catch_with_handler(
            lambda: (_ for _ in ()).throw(RuntimeError("x")),
            handler,
        )
        self.assertFalse(result.success)
        self.assertEqual(result.value, "handled: x")
        self.assertEqual(result.error_type, "RuntimeError")

    def test_catch_with_handler_success(self):
        eb = ErrorBoundary()
        result = eb.catch_with_handler(lambda: 99, lambda e: None)
        self.assertTrue(result.success)
        self.assertEqual(result.value, 99)

    def test_catch_with_handler_handler_fails(self):
        eb = ErrorBoundary()

        def bad_handler(exc):
            raise TypeError("handler broke")

        result = eb.catch_with_handler(
            lambda: (_ for _ in ()).throw(RuntimeError("orig")),
            bad_handler,
        )
        self.assertFalse(result.success)
        self.assertIsNone(result.value)
        self.assertEqual(result.error_type, "RuntimeError")

    def test_catch_with_handler_logged(self):
        eb = ErrorBoundary()
        eb.catch_with_handler(
            lambda: (_ for _ in ()).throw(RuntimeError("x")),
            lambda e: None,
        )
        self.assertEqual(eb.error_count, 1)

    def test_args_forwarded(self):
        eb = ErrorBoundary()
        result = eb.catch(lambda a, b: a + b, 3, 4)
        self.assertEqual(result.value, 7)

    def test_kwargs_forwarded(self):
        eb = ErrorBoundary()
        result = eb.catch(lambda name="x": f"hi {name}", name="world")
        self.assertEqual(result.value, "hi world")

    # --- Async tests ---

    def test_async_catch_success(self):
        eb = ErrorBoundary()

        async def ok():
            return 88

        result = _run(eb.async_catch(ok))
        self.assertTrue(result.success)
        self.assertEqual(result.value, 88)

    def test_async_catch_error(self):
        eb = ErrorBoundary()

        async def fail():
            raise ValueError("async-err")

        result = _run(eb.async_catch(fail))
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "ValueError")

    def test_async_catch_default(self):
        eb = ErrorBoundary()

        async def fail():
            raise RuntimeError("x")

        result = _run(eb.async_catch(fail, default="def"))
        self.assertEqual(result.value, "def")

    def test_async_catch_logged(self):
        eb = ErrorBoundary()

        async def fail():
            raise RuntimeError("x")

        _run(eb.async_catch(fail))
        self.assertEqual(eb.error_count, 1)

    def test_multiple_errors_accumulated(self):
        eb = ErrorBoundary()
        for i in range(5):
            eb.catch(lambda: (_ for _ in ()).throw(RuntimeError(f"err{i}")))
        self.assertEqual(eb.error_count, 5)
        self.assertEqual(len(eb.log), 5)


if __name__ == "__main__":
    unittest.main()
