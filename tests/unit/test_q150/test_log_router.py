"""Tests for Q150 LogRouter."""
from __future__ import annotations

import unittest

from lidco.logging.structured_logger import LogRecord
from lidco.logging.log_router import LogRouter, Route


def _make_record(level="info", msg="test", name="app") -> LogRecord:
    return LogRecord(level=level, message=msg, timestamp=1.0, logger_name=name)


class TestRoute(unittest.TestCase):
    def test_defaults(self):
        r = Route(name="r", handler=lambda _: None)
        self.assertEqual(r.min_level, "debug")
        self.assertIsNone(r.filter_fn)
        self.assertTrue(r.enabled)


class TestLogRouter(unittest.TestCase):
    def setUp(self):
        self.router = LogRouter()
        self.captured: list[LogRecord] = []

    def _handler(self, record: LogRecord) -> None:
        self.captured.append(record)

    def test_add_route(self):
        route = self.router.add_route("sink", self._handler)
        self.assertEqual(route.name, "sink")
        self.assertEqual(len(self.router.list_routes()), 1)

    def test_remove_route(self):
        self.router.add_route("x", self._handler)
        self.assertTrue(self.router.remove_route("x"))
        self.assertEqual(len(self.router.list_routes()), 0)

    def test_remove_nonexistent(self):
        self.assertFalse(self.router.remove_route("nope"))

    def test_route_delivers(self):
        self.router.add_route("s", self._handler)
        self.router.route(_make_record())
        self.assertEqual(len(self.captured), 1)

    def test_route_respects_min_level(self):
        self.router.add_route("s", self._handler, min_level="error")
        self.router.route(_make_record(level="info"))
        self.assertEqual(len(self.captured), 0)
        self.router.route(_make_record(level="error"))
        self.assertEqual(len(self.captured), 1)

    def test_route_with_filter_fn(self):
        self.router.add_route("s", self._handler, filter_fn=lambda r: "important" in r.message)
        self.router.route(_make_record(msg="boring"))
        self.assertEqual(len(self.captured), 0)
        self.router.route(_make_record(msg="important stuff"))
        self.assertEqual(len(self.captured), 1)

    def test_multiple_routes(self):
        other: list[LogRecord] = []
        self.router.add_route("a", self._handler)
        self.router.add_route("b", lambda r: other.append(r))
        self.router.route(_make_record())
        self.assertEqual(len(self.captured), 1)
        self.assertEqual(len(other), 1)

    def test_disable_route(self):
        self.router.add_route("s", self._handler)
        self.router.disable("s")
        self.router.route(_make_record())
        self.assertEqual(len(self.captured), 0)

    def test_enable_route(self):
        self.router.add_route("s", self._handler)
        self.router.disable("s")
        self.router.enable("s")
        self.router.route(_make_record())
        self.assertEqual(len(self.captured), 1)

    def test_routed_count(self):
        self.assertEqual(self.router.routed_count, 0)
        self.router.add_route("s", self._handler)
        self.router.route(_make_record())
        self.router.route(_make_record())
        self.assertEqual(self.router.routed_count, 2)

    def test_routed_count_multi_routes(self):
        self.router.add_route("a", self._handler)
        self.router.add_route("b", lambda _: None)
        self.router.route(_make_record())
        self.assertEqual(self.router.routed_count, 2)

    def test_list_routes_returns_copy(self):
        self.router.add_route("s", self._handler)
        routes = self.router.list_routes()
        routes.clear()
        self.assertEqual(len(self.router.list_routes()), 1)

    def test_disable_nonexistent_no_error(self):
        self.router.disable("nope")  # should not raise

    def test_enable_nonexistent_no_error(self):
        self.router.enable("nope")

    def test_route_level_ordering_critical(self):
        self.router.add_route("s", self._handler, min_level="critical")
        self.router.route(_make_record(level="error"))
        self.assertEqual(len(self.captured), 0)
        self.router.route(_make_record(level="critical"))
        self.assertEqual(len(self.captured), 1)

    def test_route_level_debug_passes_all(self):
        self.router.add_route("s", self._handler, min_level="debug")
        for lvl in ["debug", "info", "warning", "error", "critical"]:
            self.router.route(_make_record(level=lvl))
        self.assertEqual(len(self.captured), 5)

    def test_add_route_replaces_same_name(self):
        other: list = []
        self.router.add_route("s", self._handler)
        self.router.add_route("s", lambda r: other.append(r))
        self.router.route(_make_record())
        self.assertEqual(len(self.captured), 0)
        self.assertEqual(len(other), 1)

    def test_filter_and_min_level_combined(self):
        self.router.add_route(
            "s", self._handler, min_level="warning",
            filter_fn=lambda r: r.logger_name == "auth"
        )
        self.router.route(_make_record(level="warning", name="app"))
        self.assertEqual(len(self.captured), 0)
        self.router.route(_make_record(level="warning", name="auth"))
        self.assertEqual(len(self.captured), 1)

    def test_routed_count_starts_zero(self):
        self.assertEqual(LogRouter().routed_count, 0)


if __name__ == "__main__":
    unittest.main()
