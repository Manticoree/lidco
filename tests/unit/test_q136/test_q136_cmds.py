"""Tests for Q136 CLI commands."""
from __future__ import annotations

import asyncio
import json
import time
import unittest
from lidco.cli.commands import q136_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ136Commands(unittest.TestCase):
    def setUp(self):
        q136_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q136_cmds.register(MockRegistry())
        self.handler = self.registered["schedule"].handler

    def test_command_registered(self):
        self.assertIn("schedule", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("zzz"))
        self.assertIn("Usage", result)

    # --- priority ---

    def test_priority_add(self):
        data = json.dumps({"name": "build", "priority": 1, "category": "ci"})
        result = _run(self.handler(f"priority add {data}"))
        self.assertIn("Scheduled task", result)

    def test_priority_add_invalid_json(self):
        result = _run(self.handler("priority add notjson"))
        self.assertIn("Usage", result)

    def test_priority_next_empty(self):
        result = _run(self.handler("priority next"))
        self.assertIn("No tasks", result)

    def test_priority_next_returns_task(self):
        data = json.dumps({"name": "job", "priority": 1})
        _run(self.handler(f"priority add {data}"))
        result = _run(self.handler("priority next"))
        self.assertIn("job", result)

    def test_priority_peek_empty(self):
        result = _run(self.handler("priority peek"))
        self.assertIn("empty", result.lower())

    def test_priority_size(self):
        result = _run(self.handler("priority size"))
        self.assertIn("0", result)

    def test_priority_list_empty_category(self):
        result = _run(self.handler("priority list build"))
        self.assertIn("No tasks", result)

    def test_priority_no_action(self):
        result = _run(self.handler("priority"))
        self.assertIn("size", result.lower())

    # --- deps ---

    def test_deps_add(self):
        data = json.dumps({"task_id": "a", "depends_on": []})
        result = _run(self.handler(f"deps add {data}"))
        self.assertIn("Added", result)

    def test_deps_add_invalid(self):
        result = _run(self.handler("deps add notjson"))
        self.assertIn("Usage", result)

    def test_deps_resolve(self):
        data = json.dumps({"task_id": "a"})
        _run(self.handler(f"deps add {data}"))
        result = _run(self.handler("deps resolve"))
        parsed = json.loads(result)
        self.assertIn("a", parsed["order"])

    def test_deps_ready(self):
        data = json.dumps({"task_id": "a"})
        _run(self.handler(f"deps add {data}"))
        result = _run(self.handler("deps ready"))
        self.assertIn("a", result)

    def test_deps_done(self):
        result = _run(self.handler("deps done taskA"))
        self.assertIn("Marked", result)

    def test_deps_done_no_id(self):
        result = _run(self.handler("deps done"))
        self.assertIn("Usage", result)

    def test_deps_no_action(self):
        result = _run(self.handler("deps"))
        self.assertIn("Usage", result)

    # --- deadline ---

    def test_deadline_add(self):
        data = json.dumps({"task_id": "t1", "name": "Ship", "due_at": time.time() + 3600})
        result = _run(self.handler(f"deadline add {data}"))
        self.assertIn("Deadline added", result)

    def test_deadline_add_invalid(self):
        result = _run(self.handler("deadline add bad"))
        self.assertIn("Usage", result)

    def test_deadline_complete(self):
        data = json.dumps({"task_id": "t1", "name": "Ship", "due_at": time.time() + 3600})
        _run(self.handler(f"deadline add {data}"))
        result = _run(self.handler("deadline complete t1"))
        self.assertIn("True", result)

    def test_deadline_overdue_empty(self):
        result = _run(self.handler("deadline overdue"))
        self.assertIn("No overdue", result)

    def test_deadline_summary(self):
        result = _run(self.handler("deadline summary"))
        parsed = json.loads(result)
        self.assertEqual(parsed["total"], 0)

    def test_deadline_no_action(self):
        result = _run(self.handler("deadline"))
        parsed = json.loads(result)
        self.assertIn("total", parsed)

    # --- batch ---

    def test_batch_add(self):
        data = json.dumps({"item": "x", "group_key": "g1"})
        result = _run(self.handler(f"batch add {data}"))
        self.assertIn("Pending", result)

    def test_batch_add_invalid(self):
        result = _run(self.handler("batch add bad"))
        self.assertIn("Usage", result)

    def test_batch_flush_empty(self):
        result = _run(self.handler("batch flush"))
        self.assertIn("Nothing", result)

    def test_batch_stats(self):
        result = _run(self.handler("batch stats"))
        parsed = json.loads(result)
        self.assertEqual(parsed["batches_created"], 0)

    def test_batch_pending(self):
        result = _run(self.handler("batch pending"))
        self.assertIn("0", result)

    def test_batch_no_action(self):
        result = _run(self.handler("batch"))
        parsed = json.loads(result)
        self.assertIn("batches_created", parsed)


if __name__ == "__main__":
    unittest.main()
