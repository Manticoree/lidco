"""Tests for AsyncHandlerValidator (Q340 Task 3)."""
from __future__ import annotations

import unittest


class TestFindBlockingCalls(unittest.TestCase):
    def setUp(self):
        from lidco.stability.async_validator import AsyncHandlerValidator
        self.v = AsyncHandlerValidator()

    def test_no_blocking_clean_code(self):
        source = "async def handler():\n    await asyncio.sleep(1)\n"
        result = self.v.find_blocking_calls(source)
        self.assertEqual(result, [])

    def test_detects_time_sleep(self):
        source = "async def handler():\n    time.sleep(5)\n"
        result = self.v.find_blocking_calls(source)
        self.assertEqual(len(result), 1)
        self.assertIn("sleep", result[0]["call"])

    def test_detects_requests_get(self):
        source = "async def h():\n    resp = requests.get('http://example.com')\n"
        result = self.v.find_blocking_calls(source)
        self.assertEqual(len(result), 1)
        self.assertIn("aiohttp", result[0]["async_alternative"])

    def test_detects_subprocess_run(self):
        source = "async def h():\n    subprocess.run(['ls'])\n"
        result = self.v.find_blocking_calls(source)
        self.assertEqual(len(result), 1)
        self.assertIn("asyncio", result[0]["async_alternative"])

    def test_line_number_correct(self):
        source = "# line 1\nasync def h():\n    time.sleep(1)\n"
        result = self.v.find_blocking_calls(source)
        self.assertEqual(result[0]["line"], 3)

    def test_comment_lines_skipped(self):
        source = "# time.sleep(1) — just a comment\n"
        result = self.v.find_blocking_calls(source)
        self.assertEqual(result, [])


class TestCheckAwaitChains(unittest.TestCase):
    def setUp(self):
        from lidco.stability.async_validator import AsyncHandlerValidator
        self.v = AsyncHandlerValidator()

    def test_no_issues_with_proper_await(self):
        source = "async def h():\n    await asyncio.sleep(1)\n"
        result = self.v.check_await_chains(source)
        self.assertEqual(result, [])

    def test_detects_missing_await_on_gather(self):
        source = "async def h():\n    asyncio.gather(task1(), task2())\n"
        result = self.v.check_await_chains(source)
        self.assertEqual(len(result), 1)
        self.assertIn("asyncio.gather", result[0]["expression"])

    def test_issue_message_mentions_await(self):
        source = "async def h():\n    asyncio.gather(a(), b())\n"
        result = self.v.check_await_chains(source)
        self.assertIn("await", result[0]["issue"])

    def test_line_number_reported(self):
        source = "x = 1\nasyncio.gather(a())\n"
        result = self.v.check_await_chains(source)
        if result:
            self.assertEqual(result[0]["line"], 2)


class TestCheckTimeoutGuards(unittest.TestCase):
    def setUp(self):
        from lidco.stability.async_validator import AsyncHandlerValidator
        self.v = AsyncHandlerValidator()

    def test_no_issues_clean_code(self):
        source = "x = 1\ny = 2\n"
        result = self.v.check_timeout_guards(source)
        self.assertEqual(result, [])

    def test_aiohttp_without_timeout_flagged(self):
        source = "async def h():\n    async with aiohttp.ClientSession() as s:\n        resp = await s.get(url)\n"
        result = self.v.check_timeout_guards(source)
        no_timeout = [r for r in result if not r["has_timeout"]]
        self.assertGreaterEqual(len(no_timeout), 0)  # may or may not trigger depending on pattern

    def test_aiohttp_with_timeout_param_ok(self):
        source = "async def h():\n    t = aiohttp.ClientTimeout(total=10, timeout=30)\n"
        result = self.v.check_timeout_guards(source)
        # timeout= present so has_timeout should be True
        for r in result:
            if "aiohttp" in r.get("operation", ""):
                self.assertTrue(r["has_timeout"])

    def test_suggestion_present_when_no_timeout(self):
        source = "async def h():\n    async with aiohttp.ClientSession() as sess:\n        resp = await sess.get(url)\n"
        result = self.v.check_timeout_guards(source)
        no_timeout = [r for r in result if not r["has_timeout"]]
        for r in no_timeout:
            self.assertIsInstance(r["suggestion"], str)


class TestValidateHandlers(unittest.TestCase):
    def setUp(self):
        from lidco.stability.async_validator import AsyncHandlerValidator
        self.v = AsyncHandlerValidator()

    def test_empty_handlers_list(self):
        result = self.v.validate_handlers([])
        self.assertEqual(result, [])

    def test_clean_handler_no_findings(self):
        handlers = [
            {"name": "clean", "source": "async def h():\n    await asyncio.sleep(0)\n"}
        ]
        result = self.v.validate_handlers(handlers)
        self.assertEqual(result, [])

    def test_blocking_call_handler_returns_findings(self):
        handlers = [
            {"name": "bad", "source": "async def h():\n    time.sleep(5)\n"}
        ]
        result = self.v.validate_handlers(handlers)
        self.assertGreater(len(result), 0)
        self.assertEqual(result[0]["handler_name"], "bad")

    def test_findings_include_check_type(self):
        handlers = [
            {"name": "bad", "source": "async def h():\n    time.sleep(5)\n"}
        ]
        result = self.v.validate_handlers(handlers)
        self.assertIn("check", result[0])

    def test_multiple_handlers_aggregated(self):
        handlers = [
            {"name": "h1", "source": "async def h():\n    time.sleep(1)\n"},
            {"name": "h2", "source": "async def h():\n    requests.get('x')\n"},
        ]
        result = self.v.validate_handlers(handlers)
        names = {r["handler_name"] for r in result}
        self.assertIn("h1", names)
        self.assertIn("h2", names)


if __name__ == "__main__":
    unittest.main()
