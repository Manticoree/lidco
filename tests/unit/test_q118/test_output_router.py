"""Tests for AutomationOutputRouter (Task 725)."""
from __future__ import annotations

import unittest

from lidco.scheduler.output_router import (
    DeliveryResult,
    LogOutputHandler,
    OutputHandler,
    OutputRouter,
    StubOutputHandler,
)


class TestDeliveryResult(unittest.TestCase):
    def test_success_result(self):
        r = DeliveryResult(success=True, output_type="log", message="ok")
        self.assertTrue(r.success)
        self.assertEqual(r.error, "")

    def test_error_result(self):
        r = DeliveryResult(success=False, output_type="pr", error="failed")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "failed")


class TestLogOutputHandler(unittest.TestCase):
    def test_deliver_stores_result(self):
        h = LogOutputHandler()
        h.deliver("hello", {"k": "v"})
        self.assertEqual(len(h.delivered), 1)
        self.assertEqual(h.delivered[0], ("hello", {"k": "v"}))

    def test_deliver_returns_success(self):
        h = LogOutputHandler()
        r = h.deliver("msg", {})
        self.assertTrue(r.success)
        self.assertEqual(r.output_type, "log")

    def test_deliver_multiple(self):
        h = LogOutputHandler()
        h.deliver("a", {})
        h.deliver("b", {})
        self.assertEqual(len(h.delivered), 2)

    def test_deliver_message_in_result(self):
        h = LogOutputHandler()
        r = h.deliver("test msg", {})
        self.assertEqual(r.message, "test msg")


class TestStubOutputHandler(unittest.TestCase):
    def test_deliver_returns_success(self):
        h = StubOutputHandler("pr")
        r = h.deliver("content", {})
        self.assertTrue(r.success)
        self.assertEqual(r.output_type, "pr")

    def test_deliver_message_prefix(self):
        h = StubOutputHandler("slack")
        r = h.deliver("my message", {})
        self.assertTrue(r.message.startswith("stub:"))

    def test_deliver_truncates(self):
        h = StubOutputHandler("pr")
        long_msg = "x" * 200
        r = h.deliver(long_msg, {})
        self.assertLessEqual(len(r.message), 60)  # "stub:" + 50 chars


class TestOutputRouter(unittest.TestCase):
    def setUp(self):
        self.router = OutputRouter()

    # -- pre-registered types -----------------------------------------------

    def test_log_pre_registered(self):
        r = self.router.route("msg", "log")
        self.assertTrue(r.success)

    def test_pr_pre_registered(self):
        r = self.router.route("msg", "pr")
        self.assertTrue(r.success)

    def test_slack_pre_registered(self):
        r = self.router.route("msg", "slack")
        self.assertTrue(r.success)

    def test_linear_pre_registered(self):
        r = self.router.route("msg", "linear")
        self.assertTrue(r.success)

    def test_comment_pre_registered(self):
        r = self.router.route("msg", "comment")
        self.assertTrue(r.success)

    # -- unknown type -------------------------------------------------------

    def test_unknown_type_fails(self):
        r = self.router.route("msg", "email")
        self.assertFalse(r.success)
        self.assertIn("No handler", r.error)

    # -- custom handler -----------------------------------------------------

    def test_register_custom_handler(self):
        class MyHandler(OutputHandler):
            def deliver(self, result, context):
                return DeliveryResult(success=True, output_type="custom", message="custom:" + result)

        self.router.register("custom", MyHandler())
        r = self.router.route("test", "custom")
        self.assertTrue(r.success)
        self.assertEqual(r.message, "custom:test")

    def test_override_existing_handler(self):
        class MyLog(OutputHandler):
            def deliver(self, result, context):
                return DeliveryResult(success=True, output_type="log", message="override")

        self.router.register("log", MyLog())
        r = self.router.route("test", "log")
        self.assertEqual(r.message, "override")

    # -- handler exception --------------------------------------------------

    def test_handler_exception_returns_error(self):
        class BadHandler(OutputHandler):
            def deliver(self, result, context):
                raise RuntimeError("handler crash")

        self.router.register("bad", BadHandler())
        r = self.router.route("msg", "bad")
        self.assertFalse(r.success)
        self.assertIn("handler crash", r.error)

    # -- list_types ---------------------------------------------------------

    def test_list_types(self):
        types = self.router.list_types()
        self.assertIn("log", types)
        self.assertIn("pr", types)
        self.assertIn("slack", types)
        self.assertIn("linear", types)
        self.assertIn("comment", types)

    def test_list_types_sorted(self):
        types = self.router.list_types()
        self.assertEqual(types, sorted(types))

    def test_list_types_includes_custom(self):
        self.router.register("zebra", StubOutputHandler("zebra"))
        self.assertIn("zebra", self.router.list_types())

    # -- context parameter --------------------------------------------------

    def test_route_with_context(self):
        r = self.router.route("msg", "log", context={"key": "val"})
        self.assertTrue(r.success)

    def test_route_none_context(self):
        r = self.router.route("msg", "log", context=None)
        self.assertTrue(r.success)


if __name__ == "__main__":
    unittest.main()
