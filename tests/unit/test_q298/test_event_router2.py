"""Tests for EventRouter2 (Q298)."""
import unittest

from lidco.webhooks.router import EventRouter2, RoutedEvent


class TestEventRouter2(unittest.TestCase):
    def _make(self):
        return EventRouter2()

    # -- add_route -------------------------------------------------

    def test_add_route_returns_id(self):
        router = self._make()
        rid = router.add_route("user.*", lambda e: "ok")
        self.assertTrue(len(rid) > 0)

    def test_add_route_stores_entry(self):
        router = self._make()
        router.add_route("order.*", lambda e: "ok")
        self.assertEqual(len(router._routes), 1)

    def test_remove_route(self):
        router = self._make()
        rid = router.add_route("x.*", lambda e: "ok")
        self.assertTrue(router.remove_route(rid))
        self.assertEqual(len(router._routes), 0)

    def test_remove_route_unknown(self):
        router = self._make()
        self.assertFalse(router.remove_route("nonexistent"))

    # -- route ----------------------------------------------------

    def test_route_matches_exact(self):
        router = self._make()
        router.add_route("user.created", lambda e: "matched")
        ev = RoutedEvent(type="user.created", data={})
        results = router.route(ev)
        self.assertEqual(results, ["matched"])

    def test_route_matches_glob(self):
        router = self._make()
        router.add_route("user.*", lambda e: "glob")
        ev = RoutedEvent(type="user.deleted", data={})
        results = router.route(ev)
        self.assertEqual(results, ["glob"])

    def test_route_no_match_empty(self):
        router = self._make()
        router.add_route("order.*", lambda e: "nope")
        ev = RoutedEvent(type="user.created", data={})
        results = router.route(ev)
        self.assertEqual(results, [])

    def test_route_multiple_handlers(self):
        router = self._make()
        router.add_route("user.*", lambda e: "a")
        router.add_route("user.created", lambda e: "b")
        ev = RoutedEvent(type="user.created", data={})
        results = router.route(ev)
        self.assertEqual(len(results), 2)
        self.assertIn("a", results)
        self.assertIn("b", results)

    def test_route_priority_order(self):
        router = self._make()
        router.add_route("user.*", lambda e: "low", priority=1)
        router.add_route("user.*", lambda e: "high", priority=10)
        ev = RoutedEvent(type="user.created", data={})
        results = router.route(ev)
        self.assertEqual(results[0], "high")
        self.assertEqual(results[1], "low")

    def test_route_handler_exception_captured(self):
        router = self._make()
        router.add_route("err.*", lambda e: 1 / 0)
        ev = RoutedEvent(type="err.boom", data={})
        results = router.route(ev)
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])

    # -- filter_chain --------------------------------------------

    def test_filter_chain_all_pass(self):
        ev = RoutedEvent(type="user.created", data={"role": "admin"})
        filters = [
            lambda e: e.type.startswith("user"),
            lambda e: e.data.get("role") == "admin",
        ]
        self.assertTrue(EventRouter2.filter_chain(ev, filters))

    def test_filter_chain_one_fails(self):
        ev = RoutedEvent(type="user.created", data={"role": "guest"})
        filters = [
            lambda e: e.type.startswith("user"),
            lambda e: e.data.get("role") == "admin",
        ]
        self.assertFalse(EventRouter2.filter_chain(ev, filters))

    def test_filter_chain_empty_filters(self):
        ev = RoutedEvent(type="any", data={})
        self.assertTrue(EventRouter2.filter_chain(ev, []))

    # -- priority_dispatch ----------------------------------------

    def test_priority_dispatch_multiple_events(self):
        router = self._make()
        router.add_route("*", lambda e: e.type)
        events = [
            RoutedEvent(type="a", data={}),
            RoutedEvent(type="b", data={}),
        ]
        results = router.priority_dispatch(events)
        self.assertEqual(results, ["a", "b"])

    # -- RoutedEvent defaults -------------------------------------

    def test_routed_event_auto_id(self):
        ev = RoutedEvent(type="test", data={})
        self.assertTrue(len(ev.id) > 0)

    def test_routed_event_auto_timestamp(self):
        ev = RoutedEvent(type="test", data={})
        self.assertGreater(ev.timestamp, 0)


if __name__ == "__main__":
    unittest.main()
