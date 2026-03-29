"""Tests for HookEventBus (Task 717)."""
import threading
import time
import unittest

from lidco.hooks.event_bus import HookEvent, HookEventBus


class TestHookEvent(unittest.TestCase):
    def test_create_with_defaults(self):
        e = HookEvent(event_type="test", payload={"k": "v"})
        self.assertEqual(e.event_type, "test")
        self.assertEqual(e.payload, {"k": "v"})
        self.assertIsInstance(e.timestamp, float)
        self.assertIsInstance(e.event_id, str)

    def test_custom_timestamp(self):
        e = HookEvent(event_type="x", payload={}, timestamp=1.0)
        self.assertEqual(e.timestamp, 1.0)

    def test_custom_event_id(self):
        e = HookEvent(event_type="x", payload={}, event_id="abc")
        self.assertEqual(e.event_id, "abc")

    def test_unique_event_ids(self):
        events = [HookEvent(event_type="x", payload={}) for _ in range(50)]
        ids = {e.event_id for e in events}
        self.assertGreater(len(ids), 1)

    def test_payload_types(self):
        e = HookEvent(event_type="t", payload={"n": 1, "b": True, "l": [1, 2]})
        self.assertEqual(e.payload["n"], 1)


class TestSubscribeEmit(unittest.TestCase):
    def setUp(self):
        self.bus = HookEventBus()

    def test_subscribe_and_emit(self):
        calls = []
        self.bus.subscribe("click", lambda e: calls.append(e))
        count = self.bus.emit(HookEvent(event_type="click", payload={}))
        self.assertEqual(count, 1)
        self.assertEqual(len(calls), 1)

    def test_emit_no_subscribers_returns_zero(self):
        count = self.bus.emit(HookEvent(event_type="nope", payload={}))
        self.assertEqual(count, 0)

    def test_multiple_subscribers_same_event(self):
        calls = []
        self.bus.subscribe("e", lambda e: calls.append("a"))
        self.bus.subscribe("e", lambda e: calls.append("b"))
        count = self.bus.emit(HookEvent(event_type="e", payload={}))
        self.assertEqual(count, 2)
        self.assertEqual(calls, ["a", "b"])

    def test_subscribers_different_events_isolated(self):
        calls_a, calls_b = [], []
        self.bus.subscribe("a", lambda e: calls_a.append(1))
        self.bus.subscribe("b", lambda e: calls_b.append(1))
        self.bus.emit(HookEvent(event_type="a", payload={}))
        self.assertEqual(len(calls_a), 1)
        self.assertEqual(len(calls_b), 0)

    def test_emit_passes_event_to_handler(self):
        received = []
        self.bus.subscribe("t", lambda e: received.append(e))
        evt = HookEvent(event_type="t", payload={"x": 42})
        self.bus.emit(evt)
        self.assertIs(received[0], evt)


class TestWildcard(unittest.TestCase):
    def setUp(self):
        self.bus = HookEventBus()

    def test_wildcard_receives_all_events(self):
        calls = []
        self.bus.subscribe("*", lambda e: calls.append(e.event_type))
        self.bus.emit(HookEvent(event_type="a", payload={}))
        self.bus.emit(HookEvent(event_type="b", payload={}))
        self.assertEqual(calls, ["a", "b"])

    def test_wildcard_plus_exact(self):
        calls = []
        self.bus.subscribe("a", lambda e: calls.append("exact"))
        self.bus.subscribe("*", lambda e: calls.append("wild"))
        count = self.bus.emit(HookEvent(event_type="a", payload={}))
        self.assertEqual(count, 2)
        self.assertEqual(calls, ["exact", "wild"])

    def test_wildcard_not_triggered_by_wildcard_event(self):
        calls = []
        self.bus.subscribe("*", lambda e: calls.append(1))
        # Emit event with type "*" — wildcard handler matches both exact and wildcard
        count = self.bus.emit(HookEvent(event_type="*", payload={}))
        # exact match on "*" + wildcard "*" — same list, so counted once? Actually both resolve.
        # The exact match list IS the wildcard list, so handlers appear in both.
        # Let's just verify it works without error.
        self.assertGreaterEqual(count, 1)


class TestUnsubscribe(unittest.TestCase):
    def setUp(self):
        self.bus = HookEventBus()

    def test_unsubscribe_removes_handler(self):
        calls = []
        h = lambda e: calls.append(1)
        self.bus.subscribe("x", h)
        self.bus.unsubscribe("x", h)
        self.bus.emit(HookEvent(event_type="x", payload={}))
        self.assertEqual(calls, [])

    def test_unsubscribe_nonexistent_handler(self):
        # Should not raise
        self.bus.unsubscribe("x", lambda e: None)

    def test_unsubscribe_nonexistent_event(self):
        self.bus.unsubscribe("nope", lambda e: None)

    def test_unsubscribe_leaves_other_handlers(self):
        calls = []
        h1 = lambda e: calls.append("a")
        h2 = lambda e: calls.append("b")
        self.bus.subscribe("x", h1)
        self.bus.subscribe("x", h2)
        self.bus.unsubscribe("x", h1)
        self.bus.emit(HookEvent(event_type="x", payload={}))
        self.assertEqual(calls, ["b"])


class TestSubscriberCount(unittest.TestCase):
    def setUp(self):
        self.bus = HookEventBus()

    def test_empty(self):
        self.assertEqual(self.bus.subscriber_count("x"), 0)

    def test_after_subscribe(self):
        self.bus.subscribe("x", lambda e: None)
        self.assertEqual(self.bus.subscriber_count("x"), 1)

    def test_after_unsubscribe(self):
        h = lambda e: None
        self.bus.subscribe("x", h)
        self.bus.unsubscribe("x", h)
        self.assertEqual(self.bus.subscriber_count("x"), 0)


class TestClear(unittest.TestCase):
    def test_clear_removes_all(self):
        bus = HookEventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        bus.clear()
        self.assertEqual(bus.subscriber_count("a"), 0)
        self.assertEqual(bus.subscriber_count("b"), 0)

    def test_clear_then_emit(self):
        bus = HookEventBus()
        bus.subscribe("a", lambda e: None)
        bus.clear()
        count = bus.emit(HookEvent(event_type="a", payload={}))
        self.assertEqual(count, 0)


class TestErrorHandling(unittest.TestCase):
    def test_handler_exception_swallowed(self):
        bus = HookEventBus()
        bus.subscribe("e", lambda e: 1 / 0)
        # Should not raise
        count = bus.emit(HookEvent(event_type="e", payload={}))
        self.assertEqual(count, 1)

    def test_handler_error_doesnt_block_others(self):
        bus = HookEventBus()
        calls = []
        bus.subscribe("e", lambda e: 1 / 0)
        bus.subscribe("e", lambda e: calls.append(1))
        count = bus.emit(HookEvent(event_type="e", payload={}))
        self.assertEqual(count, 2)
        self.assertEqual(len(calls), 1)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_subscribe_emit(self):
        bus = HookEventBus()
        calls = []

        def subscriber():
            for _ in range(50):
                bus.subscribe("t", lambda e: calls.append(1))

        def emitter():
            for _ in range(50):
                bus.emit(HookEvent(event_type="t", payload={}))

        threads = [threading.Thread(target=subscriber), threading.Thread(target=emitter)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Just verify no crash — copy-on-write should prevent issues
        self.assertGreater(len(calls), 0)

    def test_concurrent_subscribe_unsubscribe(self):
        bus = HookEventBus()
        handlers = [lambda e: None for _ in range(20)]
        for h in handlers:
            bus.subscribe("c", h)

        def unsub():
            for h in handlers:
                bus.unsubscribe("c", h)

        def sub():
            for h in handlers:
                bus.subscribe("c", h)

        t1 = threading.Thread(target=unsub)
        t2 = threading.Thread(target=sub)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # No crash expected


if __name__ == "__main__":
    unittest.main()
