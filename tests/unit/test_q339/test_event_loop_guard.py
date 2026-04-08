"""Tests for EventLoopGuard (Q339)."""
from __future__ import annotations

import unittest

from lidco.stability.event_loop_guard import EventLoopGuard


class TestCheckLoopConflicts(unittest.TestCase):
    def setUp(self):
        self.guard = EventLoopGuard()

    def test_get_event_loop_flagged(self):
        code = "loop = asyncio.get_event_loop()\n"
        results = self.guard.check_loop_conflicts(code)
        self.assertGreater(len(results), 0)

    def test_run_until_complete_flagged(self):
        code = "loop.run_until_complete(main())\n"
        results = self.guard.check_loop_conflicts(code)
        self.assertTrue(any("run_until_complete" in r["issue"] for r in results))

    def test_mixing_both_apis_flagged(self):
        code = (
            "asyncio.run(setup())\n"
            "loop = asyncio.get_event_loop()\n"
            "loop.run_until_complete(teardown())\n"
        )
        results = self.guard.check_loop_conflicts(code)
        self.assertGreater(len(results), 0)

    def test_clean_asyncio_run_no_conflicts(self):
        code = (
            "import asyncio\n\n"
            "async def main():\n"
            "    pass\n\n"
            "if __name__ == '__main__':\n"
            "    asyncio.run(main())\n"
        )
        results = self.guard.check_loop_conflicts(code)
        # No get_event_loop or run_until_complete → no conflicts.
        self.assertEqual(results, [])

    def test_result_keys_present(self):
        code = "loop = asyncio.get_event_loop()\n"
        results = self.guard.check_loop_conflicts(code)
        for r in results:
            self.assertIn("line", r)
            self.assertIn("issue", r)
            self.assertIn("fix", r)


class TestEnforceAsyncioRun(unittest.TestCase):
    def setUp(self):
        self.guard = EventLoopGuard()

    def test_run_until_complete_replaced(self):
        code = "asyncio.get_event_loop().run_until_complete(main())\n"
        results = self.guard.enforce_asyncio_run(code)
        self.assertGreater(len(results), 0)
        r = results[0]
        self.assertIn("old_pattern", r)
        self.assertIn("new_pattern", r)
        self.assertIn("asyncio.run", r["new_pattern"])

    def test_loop_variable_assignment(self):
        code = "loop = asyncio.get_event_loop()\n"
        results = self.guard.enforce_asyncio_run(code)
        self.assertGreater(len(results), 0)

    def test_loop_close_flagged(self):
        code = "loop.close()\n"
        results = self.guard.enforce_asyncio_run(code)
        self.assertGreater(len(results), 0)

    def test_clean_code_no_deprecations(self):
        code = "asyncio.run(main())\n"
        results = self.guard.enforce_asyncio_run(code)
        self.assertEqual(results, [])

    def test_result_has_line_number(self):
        code = "loop = asyncio.get_event_loop()\nloop.close()\n"
        results = self.guard.enforce_asyncio_run(code)
        for r in results:
            self.assertIsInstance(r["line"], int)
            self.assertGreater(r["line"], 0)


class TestCheckLoopCleanup(unittest.TestCase):
    def setUp(self):
        self.guard = EventLoopGuard()

    def test_new_event_loop_without_close(self):
        code = "loop = asyncio.new_event_loop()\ndo_work(loop)\n"
        results = self.guard.check_loop_cleanup(code)
        self.assertTrue(
            any("close" in r["issue"] for r in results)
            or any("new_event_loop" in r["issue"] for r in results)
        )

    def test_set_event_loop_flagged(self):
        code = "asyncio.set_event_loop(loop)\n"
        results = self.guard.check_loop_cleanup(code)
        self.assertGreater(len(results), 0)

    def test_run_forever_without_stop(self):
        code = "loop.run_forever()\n"
        results = self.guard.check_loop_cleanup(code)
        self.assertTrue(any("run_forever" in r["issue"] for r in results))

    def test_result_keys(self):
        code = "asyncio.set_event_loop(loop)\n"
        results = self.guard.check_loop_cleanup(code)
        for r in results:
            self.assertIn("line", r)
            self.assertIn("issue", r)
            self.assertIn("suggestion", r)

    def test_clean_code_no_issues(self):
        code = "x = 1\ny = x + 1\n"
        results = self.guard.check_loop_cleanup(code)
        self.assertEqual(results, [])


class TestCheckIsolation(unittest.TestCase):
    def setUp(self):
        self.guard = EventLoopGuard()

    def test_deprecated_run_until_complete_in_test(self):
        code = (
            "def test_something(self):\n"
            "    result = asyncio.get_event_loop().run_until_complete(coro())\n"
        )
        results = self.guard.check_isolation(code)
        self.assertGreater(len(results), 0)

    def test_class_level_shared_loop(self):
        code = (
            "class MyTests(unittest.TestCase):\n"
            "    @classmethod\n"
            "    def setUpClass(cls):\n"
            "        cls.loop = asyncio.new_event_loop()\n"
        )
        results = self.guard.check_isolation(code)
        self.assertGreater(len(results), 0)

    def test_clean_test_no_issues(self):
        code = (
            "def test_something(self):\n"
            "    result = asyncio.run(coro())\n"
            "    self.assertEqual(result, 42)\n"
        )
        results = self.guard.check_isolation(code)
        self.assertEqual(results, [])

    def test_result_keys(self):
        code = "result = asyncio.get_event_loop().run_until_complete(coro())\n"
        results = self.guard.check_isolation(code)
        for r in results:
            self.assertIn("line", r)
            self.assertIn("issue", r)
            self.assertIn("fix", r)


if __name__ == "__main__":
    unittest.main()
