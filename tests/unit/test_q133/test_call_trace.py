"""Tests for Q133 CallTracer."""
from __future__ import annotations
import unittest
from lidco.debug.call_trace import CallTracer, TraceEntry


class TestTraceEntry(unittest.TestCase):
    def test_defaults(self):
        entry = TraceEntry(fn_name="f", args=(), kwargs={}, result=None)
        self.assertEqual(entry.error, "")
        self.assertEqual(entry.elapsed, 0.0)
        self.assertEqual(entry.timestamp, 0.0)


class TestCallTracer(unittest.TestCase):
    def setUp(self):
        self.tracer = CallTracer()

    def test_trace_records_entry(self):
        @self.tracer.trace
        def add(x, y):
            return x + y

        result = add(1, 2)
        self.assertEqual(result, 3)
        entries = self.tracer.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].fn_name, "add")

    def test_trace_records_result(self):
        @self.tracer.trace
        def double(n):
            return n * 2

        double(5)
        self.assertEqual(self.tracer.entries()[0].result, 10)

    def test_trace_records_args(self):
        @self.tracer.trace
        def fn(a, b):
            return a + b

        fn(3, 4)
        entry = self.tracer.entries()[0]
        self.assertEqual(entry.args, (3, 4))

    def test_trace_records_kwargs(self):
        @self.tracer.trace
        def fn(x, y=0):
            return x + y

        fn(1, y=5)
        entry = self.tracer.entries()[0]
        self.assertEqual(entry.kwargs, {"y": 5})

    def test_trace_records_error(self):
        @self.tracer.trace
        def broken():
            raise ValueError("oops")

        with self.assertRaises(ValueError):
            broken()

        entry = self.tracer.entries()[0]
        self.assertIn("oops", entry.error)

    def test_trace_elapsed_positive(self):
        @self.tracer.trace
        def noop():
            pass

        noop()
        self.assertGreaterEqual(self.tracer.entries()[0].elapsed, 0.0)

    def test_trace_timestamp_set(self):
        @self.tracer.trace
        def noop():
            pass

        noop()
        self.assertGreater(self.tracer.entries()[0].timestamp, 0.0)

    def test_entries_returns_copy(self):
        entries = self.tracer.entries()
        self.assertIsInstance(entries, list)

    def test_last_returns_none_when_empty(self):
        self.assertIsNone(self.tracer.last())

    def test_last_returns_last_entry(self):
        @self.tracer.trace
        def fn():
            return "x"

        fn()
        fn()
        self.assertIsNotNone(self.tracer.last())

    def test_last_by_name(self):
        @self.tracer.trace
        def alpha():
            return "a"

        @self.tracer.trace
        def beta():
            return "b"

        alpha()
        beta()
        last_alpha = self.tracer.last("alpha")
        self.assertIsNotNone(last_alpha)
        self.assertEqual(last_alpha.result, "a")

    def test_last_by_name_not_found(self):
        self.assertIsNone(self.tracer.last("nonexistent"))

    def test_clear(self):
        @self.tracer.trace
        def fn():
            pass

        fn()
        self.tracer.clear()
        self.assertEqual(len(self.tracer.entries()), 0)

    def test_summary_empty(self):
        self.assertEqual(self.tracer.summary(), {})

    def test_summary_keys(self):
        @self.tracer.trace
        def fn():
            return 1

        fn()
        fn()
        summary = self.tracer.summary()
        self.assertIn("fn", summary)
        self.assertEqual(summary["fn"]["calls"], 2)
        self.assertEqual(summary["fn"]["errors"], 0)

    def test_summary_errors_counted(self):
        @self.tracer.trace
        def broken():
            raise RuntimeError("bad")

        for _ in range(3):
            try:
                broken()
            except RuntimeError:
                pass

        summary = self.tracer.summary()
        self.assertEqual(summary["broken"]["errors"], 3)

    def test_preserves_fn_name(self):
        @self.tracer.trace
        def my_function():
            pass

        self.assertEqual(my_function.__name__, "my_function")


if __name__ == "__main__":
    unittest.main()
