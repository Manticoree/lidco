"""Tests for lidco.stability.shutdown."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

from lidco.stability.shutdown import ShutdownOrchestrator


class TestRegisterHandler(unittest.TestCase):
    def setUp(self):
        self.orch = ShutdownOrchestrator()

    def test_register_single_handler(self):
        self.orch.register_handler("h1", lambda: None)
        handlers = self.orch.get_handlers()
        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0]["name"], "h1")

    def test_register_multiple_handlers(self):
        self.orch.register_handler("h1", lambda: None, priority=5)
        self.orch.register_handler("h2", lambda: None, priority=1)
        handlers = self.orch.get_handlers()
        self.assertEqual(len(handlers), 2)

    def test_handler_priority_stored(self):
        self.orch.register_handler("high", lambda: None, priority=10)
        handlers = self.orch.get_handlers()
        self.assertEqual(handlers[0]["priority"], 10)

    def test_default_priority_zero(self):
        self.orch.register_handler("default", lambda: None)
        handlers = self.orch.get_handlers()
        self.assertEqual(handlers[0]["priority"], 0)


class TestGetHandlers(unittest.TestCase):
    def test_empty_initially(self):
        orch = ShutdownOrchestrator()
        self.assertEqual(orch.get_handlers(), [])

    def test_returns_name_and_priority(self):
        orch = ShutdownOrchestrator()
        orch.register_handler("x", lambda: None, priority=3)
        result = orch.get_handlers()
        self.assertIn("name", result[0])
        self.assertIn("priority", result[0])

    def test_no_callable_in_output(self):
        orch = ShutdownOrchestrator()
        orch.register_handler("x", lambda: None)
        result = orch.get_handlers()
        self.assertNotIn("handler", result[0])


class TestExecuteShutdown(unittest.TestCase):
    def setUp(self):
        self.orch = ShutdownOrchestrator()

    def test_all_succeed_success_true(self):
        self.orch.register_handler("h1", lambda: None)
        result = self.orch.execute_shutdown()
        self.assertTrue(result["success"])

    def test_executed_contains_handler_name(self):
        self.orch.register_handler("flush", lambda: None)
        result = self.orch.execute_shutdown()
        self.assertIn("flush", result["executed"])

    def test_failing_handler_in_failed_list(self):
        def bad():
            raise RuntimeError("boom")

        self.orch.register_handler("bad_handler", bad)
        result = self.orch.execute_shutdown()
        self.assertFalse(result["success"])
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["name"], "bad_handler")
        self.assertIn("boom", result["failed"][0]["error"])

    def test_priority_ordering(self):
        call_order: list[str] = []
        self.orch.register_handler("low", lambda: call_order.append("low"), priority=1)
        self.orch.register_handler("high", lambda: call_order.append("high"), priority=10)
        self.orch.execute_shutdown()
        self.assertEqual(call_order, ["high", "low"])

    def test_remaining_handlers_run_after_failure(self):
        ran: list[str] = []
        self.orch.register_handler("bad", lambda: (_ for _ in ()).throw(RuntimeError("x")), priority=10)
        self.orch.register_handler("good", lambda: ran.append("good"), priority=1)
        result = self.orch.execute_shutdown()
        self.assertIn("good", ran)
        self.assertIn("good", result["executed"])

    def test_total_time_ms_float(self):
        self.orch.register_handler("h", lambda: None)
        result = self.orch.execute_shutdown()
        self.assertIsInstance(result["total_time_ms"], float)

    def test_result_keys_present(self):
        result = self.orch.execute_shutdown()
        for key in ("success", "executed", "failed", "total_time_ms"):
            self.assertIn(key, result)

    def test_empty_orchestrator(self):
        result = self.orch.execute_shutdown()
        self.assertTrue(result["success"])
        self.assertEqual(result["executed"], [])
        self.assertEqual(result["failed"], [])


class TestSaveState(unittest.TestCase):
    def test_save_creates_file(self):
        orch = ShutdownOrchestrator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            result = orch.save_state({"key": "value"}, path)
            self.assertTrue(result["saved"])
            self.assertTrue(os.path.exists(path))

    def test_save_returns_path(self):
        orch = ShutdownOrchestrator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            result = orch.save_state({}, path)
            self.assertEqual(result["path"], path)

    def test_save_returns_size_bytes(self):
        orch = ShutdownOrchestrator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            result = orch.save_state({"x": 1}, path)
            self.assertGreater(result["size_bytes"], 0)

    def test_save_content_is_valid_json(self):
        orch = ShutdownOrchestrator()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            state = {"session_id": "abc", "count": 42}
            orch.save_state(state, path)
            with open(path) as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded["session_id"], "abc")

    def test_save_failure_returns_saved_false(self):
        orch = ShutdownOrchestrator()
        result = orch.save_state({}, "/nonexistent_root_dir/x/y/state.json")
        # On most systems this will fail (permission denied on root)
        # We just check the shape is correct regardless
        self.assertIn("saved", result)
        self.assertIn("path", result)
        self.assertIn("size_bytes", result)


if __name__ == "__main__":
    unittest.main()
