"""Tests for hookify rule types (Task 1047)."""
from __future__ import annotations

import unittest

from lidco.hookify.rule import ActionType, EventType, HookifyRule, RuleMatch


class TestEventType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(EventType.BASH.value, "bash")
        self.assertEqual(EventType.FILE.value, "file")
        self.assertEqual(EventType.STOP.value, "stop")
        self.assertEqual(EventType.PROMPT.value, "prompt")
        self.assertEqual(EventType.ALL.value, "all")

    def test_from_string(self):
        self.assertIs(EventType("bash"), EventType.BASH)
        self.assertIs(EventType("all"), EventType.ALL)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            EventType("nonexistent")


class TestActionType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(ActionType.WARN.value, "warn")
        self.assertEqual(ActionType.BLOCK.value, "block")

    def test_from_string(self):
        self.assertIs(ActionType("warn"), ActionType.WARN)
        self.assertIs(ActionType("block"), ActionType.BLOCK)


class TestHookifyRule(unittest.TestCase):
    def test_frozen(self):
        rule = HookifyRule(name="r", event_type=EventType.BASH, pattern="rm", action=ActionType.BLOCK, message="no")
        with self.assertRaises(AttributeError):
            rule.name = "x"  # type: ignore[misc]

    def test_defaults(self):
        rule = HookifyRule(name="r", event_type=EventType.ALL, pattern=".", action=ActionType.WARN, message="hi")
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.created_at, "")
        self.assertEqual(rule.priority, 0)

    def test_all_fields(self):
        rule = HookifyRule(
            name="guard",
            event_type=EventType.FILE,
            pattern=r"\.env$",
            action=ActionType.WARN,
            message="Careful with .env",
            enabled=False,
            created_at="2026-03-31T00:00:00Z",
            priority=10,
        )
        self.assertEqual(rule.name, "guard")
        self.assertFalse(rule.enabled)
        self.assertEqual(rule.priority, 10)
        self.assertEqual(rule.created_at, "2026-03-31T00:00:00Z")

    def test_equality(self):
        kwargs = dict(name="a", event_type=EventType.BASH, pattern="x", action=ActionType.BLOCK, message="m")
        self.assertEqual(HookifyRule(**kwargs), HookifyRule(**kwargs))

    def test_hash(self):
        kwargs = dict(name="a", event_type=EventType.BASH, pattern="x", action=ActionType.BLOCK, message="m")
        self.assertEqual(hash(HookifyRule(**kwargs)), hash(HookifyRule(**kwargs)))


class TestRuleMatch(unittest.TestCase):
    def test_frozen(self):
        rule = HookifyRule(name="r", event_type=EventType.BASH, pattern="x", action=ActionType.WARN, message="m")
        match = RuleMatch(rule=rule, matched_text="x", event_type=EventType.BASH)
        with self.assertRaises(AttributeError):
            match.matched_text = "y"  # type: ignore[misc]

    def test_fields(self):
        rule = HookifyRule(name="r", event_type=EventType.BASH, pattern="x", action=ActionType.WARN, message="m")
        match = RuleMatch(rule=rule, matched_text="hello", event_type=EventType.PROMPT)
        self.assertIs(match.rule, rule)
        self.assertEqual(match.matched_text, "hello")
        self.assertEqual(match.event_type, EventType.PROMPT)

    def test_equality(self):
        rule = HookifyRule(name="r", event_type=EventType.BASH, pattern="x", action=ActionType.WARN, message="m")
        m1 = RuleMatch(rule=rule, matched_text="x", event_type=EventType.BASH)
        m2 = RuleMatch(rule=rule, matched_text="x", event_type=EventType.BASH)
        self.assertEqual(m1, m2)


class TestAllExports(unittest.TestCase):
    def test_all_defined(self):
        from lidco.hookify import rule
        self.assertIn("EventType", rule.__all__)
        self.assertIn("ActionType", rule.__all__)
        self.assertIn("HookifyRule", rule.__all__)
        self.assertIn("RuleMatch", rule.__all__)


if __name__ == "__main__":
    unittest.main()
