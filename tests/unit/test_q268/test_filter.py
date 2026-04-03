"""Tests for ContentFilter."""
from __future__ import annotations

import unittest

from lidco.dlp.filter import ContentFilter, FilterRule, FilterResult


class TestFilterRule(unittest.TestCase):
    def test_frozen(self):
        r = FilterRule(name="x", pattern="y", action="deny")
        with self.assertRaises(AttributeError):
            r.name = "z"  # type: ignore[misc]

    def test_default_priority(self):
        r = FilterRule(name="x", pattern="y", action="allow")
        self.assertEqual(r.priority, 0)


class TestContentFilter(unittest.TestCase):
    def test_add_and_list_rules(self):
        cf = ContentFilter()
        rule = cf.add_rule(FilterRule(name="no-secrets", pattern=r"secret", action="deny"))
        self.assertEqual(rule.name, "no-secrets")
        self.assertEqual(len(cf.rules()), 1)

    def test_remove_rule(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="r1", pattern="x", action="allow"))
        self.assertTrue(cf.remove_rule("r1"))
        self.assertFalse(cf.remove_rule("r1"))

    def test_filter_deny(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="block-key", pattern=r"API_KEY", action="deny"))
        filtered, result = cf.filter("My API_KEY is abc")
        self.assertTrue(result.blocked)
        self.assertIn("block-key", result.rules_applied)

    def test_filter_redact(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="redact-email", pattern=r"\S+@\S+", action="redact"))
        filtered, result = cf.filter("Send to user@example.com now")
        self.assertIn("[REDACTED]", filtered)
        self.assertFalse(result.blocked)

    def test_filter_allow(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="pass", pattern=r"hello", action="allow"))
        filtered, result = cf.filter("hello world")
        self.assertEqual(filtered, "hello world")
        self.assertFalse(result.blocked)

    def test_check_does_not_modify(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="redact", pattern=r"secret", action="redact"))
        result = cf.check("my secret data")
        self.assertIsInstance(result, FilterResult)
        # check returns FilterResult but original content is unchanged in the caller
        self.assertIn("redact", result.rules_applied)

    def test_priority_ordering(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="low", pattern="x", action="allow", priority=1))
        cf.add_rule(FilterRule(name="high", pattern="x", action="deny", priority=10))
        _, result = cf.filter("x marks the spot")
        # high priority deny should fire first
        self.assertTrue(result.blocked)
        self.assertEqual(result.rules_applied[0], "high")

    def test_summary(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="a", pattern="x", action="allow"))
        s = cf.summary()
        self.assertEqual(s["rule_count"], 1)
        self.assertIn("a", s["rules"])

    def test_filter_no_match(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="no-match", pattern=r"zzzzz", action="deny"))
        filtered, result = cf.filter("nothing here")
        self.assertFalse(result.blocked)
        self.assertEqual(result.rules_applied, [])

    def test_filter_result_lengths(self):
        cf = ContentFilter()
        cf.add_rule(FilterRule(name="r", pattern=r"abc", action="redact"))
        filtered, result = cf.filter("xyzabcxyz")
        self.assertEqual(result.original_length, 9)
        self.assertEqual(result.filtered_length, len(filtered))


if __name__ == "__main__":
    unittest.main()
