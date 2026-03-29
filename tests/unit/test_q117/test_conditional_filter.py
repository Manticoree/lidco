"""Tests for ConditionalFilter and HookRegistry (Task 719)."""
import unittest

from lidco.hooks.event_bus import HookEvent, HookEventBus
from lidco.hooks.conditional_filter import (
    ConditionalFilter,
    HookDefinition,
    HookRegistry,
)


def _evt(event_type: str = "test", **payload) -> HookEvent:
    return HookEvent(event_type=event_type, payload=payload)


class TestConditionalFilter(unittest.TestCase):
    def test_empty_pattern_always_fires(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern="")
        cf(_evt())
        self.assertEqual(len(calls), 1)

    def test_matching_pattern_fires(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern="hello")
        cf(_evt(msg="hello world"))
        self.assertEqual(len(calls), 1)

    def test_non_matching_pattern_does_not_fire(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern="^xyz$")
        cf(_evt(msg="hello"))
        self.assertEqual(len(calls), 0)

    def test_regex_pattern(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern=r"\d+")
        cf(_evt(count=42))
        self.assertEqual(len(calls), 1)

    def test_regex_no_match(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern=r"^zzz$")
        cf(_evt(msg="hello"))
        self.assertEqual(len(calls), 0)

    def test_passes_event_to_handler(self):
        received = []
        cf = ConditionalFilter(lambda e: received.append(e))
        evt = _evt(x=1)
        cf(evt)
        self.assertIs(received[0], evt)

    def test_pattern_searches_payload_string(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern="secret")
        cf(_evt(key="my_secret_key"))
        self.assertEqual(len(calls), 1)

    def test_case_sensitive(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern="ABC")
        cf(_evt(msg="abc"))
        self.assertEqual(len(calls), 0)

    def test_case_insensitive_regex(self):
        calls = []
        cf = ConditionalFilter(lambda e: calls.append(1), if_pattern="(?i)abc")
        cf(_evt(msg="ABC"))
        self.assertEqual(len(calls), 1)


class TestHookDefinition(unittest.TestCase):
    def test_creation(self):
        d = HookDefinition(name="h1", event_type="click", handler=lambda e: None)
        self.assertEqual(d.name, "h1")
        self.assertEqual(d.event_type, "click")
        self.assertEqual(d.if_pattern, "")

    def test_with_pattern(self):
        d = HookDefinition(name="h2", event_type="*", handler=lambda e: None, if_pattern="err")
        self.assertEqual(d.if_pattern, "err")


class TestHookRegistry(unittest.TestCase):
    def setUp(self):
        self.bus = HookEventBus()
        self.reg = HookRegistry(bus=self.bus)

    def test_register_adds_to_list(self):
        defn = HookDefinition(name="h1", event_type="e", handler=lambda e: None)
        self.reg.register(defn)
        self.assertEqual(len(self.reg.list_definitions()), 1)

    def test_register_subscribes_to_bus(self):
        defn = HookDefinition(name="h1", event_type="e", handler=lambda e: None)
        self.reg.register(defn)
        self.assertEqual(self.bus.subscriber_count("e"), 1)

    def test_unregister_removes(self):
        defn = HookDefinition(name="h1", event_type="e", handler=lambda e: None)
        self.reg.register(defn)
        self.reg.unregister("h1")
        self.assertEqual(len(self.reg.list_definitions()), 0)
        self.assertEqual(self.bus.subscriber_count("e"), 0)

    def test_unregister_nonexistent(self):
        self.reg.unregister("nope")  # no error

    def test_emit_forwards_to_bus(self):
        calls = []
        defn = HookDefinition(name="h1", event_type="e", handler=lambda e: calls.append(1))
        self.reg.register(defn)
        count = self.reg.emit(_evt("e"))
        self.assertEqual(count, 1)
        self.assertEqual(len(calls), 1)

    def test_conditional_filter_applied(self):
        calls = []
        defn = HookDefinition(
            name="h1", event_type="e", handler=lambda e: calls.append(1), if_pattern="magic"
        )
        self.reg.register(defn)
        self.reg.emit(_evt("e", msg="no match"))
        self.assertEqual(len(calls), 0)
        self.reg.emit(_evt("e", msg="magic word"))
        self.assertEqual(len(calls), 1)

    def test_no_filter_when_no_pattern(self):
        calls = []
        defn = HookDefinition(name="h1", event_type="e", handler=lambda e: calls.append(1))
        self.reg.register(defn)
        self.reg.emit(_evt("e"))
        self.assertEqual(len(calls), 1)

    def test_list_definitions_returns_all(self):
        self.reg.register(HookDefinition(name="a", event_type="e", handler=lambda e: None))
        self.reg.register(HookDefinition(name="b", event_type="f", handler=lambda e: None))
        names = [d.name for d in self.reg.list_definitions()]
        self.assertIn("a", names)
        self.assertIn("b", names)

    def test_re_register_same_name_replaces(self):
        calls_a, calls_b = [], []
        self.reg.register(HookDefinition(name="h", event_type="e", handler=lambda e: calls_a.append(1)))
        self.reg.register(HookDefinition(name="h", event_type="e", handler=lambda e: calls_b.append(1)))
        self.reg.emit(_evt("e"))
        self.assertEqual(len(calls_a), 0)
        self.assertEqual(len(calls_b), 1)
        self.assertEqual(len(self.reg.list_definitions()), 1)

    def test_default_bus_created(self):
        reg = HookRegistry()
        self.assertIsNotNone(reg.bus)

    def test_bus_property(self):
        self.assertIs(self.reg.bus, self.bus)

    def test_wildcard_definition(self):
        calls = []
        defn = HookDefinition(name="w", event_type="*", handler=lambda e: calls.append(1))
        self.reg.register(defn)
        self.reg.emit(_evt("anything"))
        self.assertEqual(len(calls), 1)

    def test_multiple_definitions_same_event(self):
        calls = []
        self.reg.register(HookDefinition(name="a", event_type="e", handler=lambda e: calls.append("a")))
        self.reg.register(HookDefinition(name="b", event_type="e", handler=lambda e: calls.append("b")))
        self.reg.emit(_evt("e"))
        self.assertEqual(calls, ["a", "b"])

    def test_unregister_one_leaves_other(self):
        calls = []
        self.reg.register(HookDefinition(name="a", event_type="e", handler=lambda e: calls.append("a")))
        self.reg.register(HookDefinition(name="b", event_type="e", handler=lambda e: calls.append("b")))
        self.reg.unregister("a")
        self.reg.emit(_evt("e"))
        self.assertEqual(calls, ["b"])


if __name__ == "__main__":
    unittest.main()
