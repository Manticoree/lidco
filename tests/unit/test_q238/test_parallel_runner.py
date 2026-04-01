"""Tests for ParallelToolRunner (Q238)."""
from __future__ import annotations

import unittest

from lidco.tools.parallel_runner import (
    ToolCallStatus,
    ToolCall,
    ParallelResult,
    ParallelToolRunner,
)


class TestToolCallStatus(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ToolCallStatus.PENDING.value, "pending")
        self.assertEqual(ToolCallStatus.TIMEOUT.value, "timeout")

    def test_all_statuses(self):
        self.assertEqual(len(ToolCallStatus), 5)


class TestToolCall(unittest.TestCase):
    def test_frozen(self):
        c = ToolCall(id="abc", tool_name="read")
        with self.assertRaises(AttributeError):
            c.status = ToolCallStatus.RUNNING  # type: ignore[misc]

    def test_defaults(self):
        c = ToolCall(id="abc", tool_name="read")
        self.assertEqual(c.status, ToolCallStatus.PENDING)
        self.assertEqual(c.result, "")
        self.assertEqual(c.duration, 0.0)


class TestParallelResult(unittest.TestCase):
    def test_frozen(self):
        r = ParallelResult()
        with self.assertRaises(AttributeError):
            r.completed = 5  # type: ignore[misc]


class TestParallelToolRunner(unittest.TestCase):
    def setUp(self):
        self.runner = ParallelToolRunner(max_concurrent=3, timeout=10.0)

    def test_add_call(self):
        call = self.runner.add_call("read", "file.py")
        self.assertEqual(call.tool_name, "read")
        self.assertEqual(call.args, "file.py")
        self.assertEqual(call.status, ToolCallStatus.PENDING)
        self.assertTrue(len(call.id) > 0)

    def test_get_pending(self):
        self.runner.add_call("read")
        self.runner.add_call("write")
        pending = self.runner.get_pending()
        self.assertEqual(len(pending), 2)

    def test_detect_dependencies_different_tools(self):
        calls = [
            self.runner.add_call("read"),
            self.runner.add_call("write"),
            self.runner.add_call("grep"),
        ]
        batches = self.runner.detect_dependencies(calls)
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 3)

    def test_detect_dependencies_same_tool(self):
        calls = [
            self.runner.add_call("read"),
            self.runner.add_call("read"),
        ]
        batches = self.runner.detect_dependencies(calls)
        self.assertEqual(len(batches), 2)

    def test_simulate_run(self):
        calls = [self.runner.add_call("read"), self.runner.add_call("write")]
        result = self.runner.simulate_run(calls)
        self.assertEqual(result.completed, 2)
        self.assertEqual(result.failed, 0)
        for c in result.calls:
            self.assertEqual(c.status, ToolCallStatus.COMPLETED)

    def test_mark_completed(self):
        call = self.runner.add_call("read")
        done = self.runner.mark_completed(call.id, "data", 0.5)
        self.assertEqual(done.status, ToolCallStatus.COMPLETED)
        self.assertEqual(done.result, "data")
        self.assertEqual(done.duration, 0.5)

    def test_mark_failed(self):
        call = self.runner.add_call("read")
        failed = self.runner.mark_failed(call.id, "timeout")
        self.assertEqual(failed.status, ToolCallStatus.FAILED)
        self.assertEqual(failed.error, "timeout")

    def test_mark_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.runner.mark_completed("nonexistent", "data")

    def test_summary(self):
        calls = [self.runner.add_call("read")]
        result = self.runner.simulate_run(calls)
        s = self.runner.summary(result)
        self.assertIn("1 completed", s)
        self.assertIn("0 failed", s)


if __name__ == "__main__":
    unittest.main()
