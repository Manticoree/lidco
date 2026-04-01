"""Tests for HookifyEngine (Task 1048)."""
from __future__ import annotations

import unittest

from lidco.hookify.engine import HookifyEngine
from lidco.hookify.rule import ActionType, EventType, HookifyRule


def _rule(name: str = "r", evt: EventType = EventType.BASH, pattern: str = "rm",
          action: ActionType = ActionType.BLOCK, msg: str = "blocked",
          enabled: bool = True, priority: int = 0) -> HookifyRule:
    return HookifyRule(name=name, event_type=evt, pattern=pattern,
                       action=action, message=msg, enabled=enabled, priority=priority)


class TestInit(unittest.TestCase):
    def test_empty(self):
        e = HookifyEngine()
        self.assertEqual(e.rules, ())

    def test_with_rules(self):
        r = _rule()
        e = HookifyEngine((r,))
        self.assertEqual(len(e.rules), 1)


class TestAddRule(unittest.TestCase):
    def test_returns_new_instance(self):
        e = HookifyEngine()
        e2 = e.add_rule(_rule())
        self.assertIsNot(e, e2)
        self.assertEqual(len(e.rules), 0)
        self.assertEqual(len(e2.rules), 1)

    def test_add_multiple(self):
        e = HookifyEngine()
        e = e.add_rule(_rule("a")).add_rule(_rule("b"))
        self.assertEqual(len(e.rules), 2)


class TestRemoveRule(unittest.TestCase):
    def test_removes_by_name(self):
        e = HookifyEngine((_rule("a"), _rule("b")))
        e2 = e.remove_rule("a")
        self.assertIsNot(e, e2)
        self.assertEqual(len(e.rules), 2)
        self.assertEqual(len(e2.rules), 1)
        self.assertEqual(e2.rules[0].name, "b")

    def test_remove_nonexistent_is_noop(self):
        e = HookifyEngine((_rule("a"),))
        e2 = e.remove_rule("z")
        self.assertEqual(len(e2.rules), 1)


class TestEvaluate(unittest.TestCase):
    def test_matches_regex(self):
        e = HookifyEngine((_rule(pattern=r"rm\s+-rf"),))
        matches = e.evaluate(EventType.BASH, "rm -rf /tmp")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_text, "rm -rf")

    def test_no_match(self):
        e = HookifyEngine((_rule(pattern=r"rm\s+-rf"),))
        matches = e.evaluate(EventType.BASH, "ls -la")
        self.assertEqual(len(matches), 0)

    def test_disabled_rule_skipped(self):
        e = HookifyEngine((_rule(enabled=False),))
        matches = e.evaluate(EventType.BASH, "rm something")
        self.assertEqual(len(matches), 0)

    def test_event_type_mismatch(self):
        e = HookifyEngine((_rule(evt=EventType.FILE),))
        matches = e.evaluate(EventType.BASH, "rm something")
        self.assertEqual(len(matches), 0)

    def test_all_event_type_matches_any(self):
        e = HookifyEngine((_rule(evt=EventType.ALL),))
        matches = e.evaluate(EventType.BASH, "rm something")
        self.assertEqual(len(matches), 1)

    def test_priority_ordering(self):
        r1 = _rule(name="low", pattern="x", priority=1)
        r2 = _rule(name="high", pattern="x", priority=10)
        e = HookifyEngine((r1, r2))
        matches = e.evaluate(EventType.BASH, "x")
        self.assertEqual(matches[0].rule.name, "high")
        self.assertEqual(matches[1].rule.name, "low")

    def test_invalid_regex_skipped(self):
        e = HookifyEngine((_rule(pattern="[invalid"),))
        matches = e.evaluate(EventType.BASH, "anything")
        self.assertEqual(len(matches), 0)


class TestIsBlocked(unittest.TestCase):
    def test_blocked(self):
        e = HookifyEngine((_rule(action=ActionType.BLOCK, pattern="rm"),))
        self.assertTrue(e.is_blocked(EventType.BASH, "rm -rf"))

    def test_not_blocked_with_warn(self):
        e = HookifyEngine((_rule(action=ActionType.WARN, pattern="rm"),))
        self.assertFalse(e.is_blocked(EventType.BASH, "rm -rf"))

    def test_not_blocked_no_match(self):
        e = HookifyEngine((_rule(action=ActionType.BLOCK, pattern="rm"),))
        self.assertFalse(e.is_blocked(EventType.BASH, "ls"))


class TestGetWarnings(unittest.TestCase):
    def test_returns_messages(self):
        e = HookifyEngine((_rule(action=ActionType.WARN, pattern="eval", msg="Avoid eval"),))
        warnings = e.get_warnings(EventType.BASH, "eval('code')")
        self.assertEqual(warnings, ("Avoid eval",))

    def test_no_warnings_for_block(self):
        e = HookifyEngine((_rule(action=ActionType.BLOCK, pattern="rm", msg="blocked"),))
        warnings = e.get_warnings(EventType.BASH, "rm -rf")
        self.assertEqual(warnings, ())

    def test_empty_when_no_match(self):
        e = HookifyEngine((_rule(action=ActionType.WARN, pattern="rm", msg="hi"),))
        self.assertEqual(e.get_warnings(EventType.BASH, "ls"), ())


class TestAllExports(unittest.TestCase):
    def test_all_defined(self):
        from lidco.hookify import engine
        self.assertIn("HookifyEngine", engine.__all__)


if __name__ == "__main__":
    unittest.main()
