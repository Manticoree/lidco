"""Tests for RulePersistence (Task 1050)."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.hookify.persistence import RulePersistence, _parse_frontmatter, _rule_to_frontmatter
from lidco.hookify.rule import ActionType, EventType, HookifyRule


def _sample_rule(**overrides) -> HookifyRule:
    defaults = dict(
        name="test_rule",
        event_type=EventType.BASH,
        pattern=r"rm\s+-rf",
        action=ActionType.BLOCK,
        message="Do not use rm -rf",
        enabled=True,
        created_at="2026-03-31T00:00:00Z",
        priority=5,
    )
    defaults.update(overrides)
    return HookifyRule(**defaults)


class TestFrontmatterSerialize(unittest.TestCase):
    def test_contains_frontmatter_markers(self):
        text = _rule_to_frontmatter(_sample_rule())
        self.assertTrue(text.startswith("---\n"))
        self.assertIn("\n---\n", text)

    def test_contains_all_fields(self):
        text = _rule_to_frontmatter(_sample_rule())
        self.assertIn("name: test_rule", text)
        self.assertIn("event_type: bash", text)
        self.assertIn("action: block", text)
        self.assertIn("priority: 5", text)

    def test_message_after_frontmatter(self):
        text = _rule_to_frontmatter(_sample_rule())
        parts = text.split("---\n")
        self.assertEqual(len(parts), 3)
        self.assertIn("Do not use rm -rf", parts[2])


class TestFrontmatterParse(unittest.TestCase):
    def test_roundtrip(self):
        rule = _sample_rule()
        text = _rule_to_frontmatter(rule)
        parsed = _parse_frontmatter(text)
        self.assertEqual(parsed.name, rule.name)
        self.assertEqual(parsed.event_type, rule.event_type)
        self.assertEqual(parsed.pattern, rule.pattern)
        self.assertEqual(parsed.action, rule.action)
        self.assertEqual(parsed.message, rule.message)
        self.assertEqual(parsed.priority, rule.priority)

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            _parse_frontmatter("no frontmatter here")

    def test_disabled_rule(self):
        rule = _sample_rule(enabled=False)
        text = _rule_to_frontmatter(rule)
        parsed = _parse_frontmatter(text)
        self.assertFalse(parsed.enabled)


class TestSaveRule(unittest.TestCase):
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            path = p.save_rule(_sample_rule(), tmpdir)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.endswith("test_rule.md"))

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "rules")
            p = RulePersistence()
            p.save_rule(_sample_rule(), subdir)
            self.assertTrue(os.path.isdir(subdir))

    def test_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            path = p.save_rule(_sample_rule(), tmpdir)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("name: test_rule", content)


class TestLoadRule(unittest.TestCase):
    def test_load_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            path = p.save_rule(_sample_rule(), tmpdir)
            loaded = p.load_rule(path)
            self.assertEqual(loaded.name, "test_rule")
            self.assertEqual(loaded.action, ActionType.BLOCK)


class TestLoadAll(unittest.TestCase):
    def test_loads_all_md_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            p.save_rule(_sample_rule(name="rule_a"), tmpdir)
            p.save_rule(_sample_rule(name="rule_b"), tmpdir)
            rules = p.load_all(tmpdir)
            self.assertEqual(len(rules), 2)
            names = {r.name for r in rules}
            self.assertEqual(names, {"rule_a", "rule_b"})

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            self.assertEqual(p.load_all(tmpdir), ())

    def test_nonexistent_directory(self):
        p = RulePersistence()
        self.assertEqual(p.load_all("/nonexistent/path/q187"), ())


class TestDeleteRule(unittest.TestCase):
    def test_deletes_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            p.save_rule(_sample_rule(), tmpdir)
            self.assertTrue(p.delete_rule("test_rule", tmpdir))
            self.assertEqual(p.load_all(tmpdir), ())

    def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = RulePersistence()
            self.assertFalse(p.delete_rule("nope", tmpdir))


class TestAllExports(unittest.TestCase):
    def test_all_defined(self):
        from lidco.hookify import persistence
        self.assertIn("RulePersistence", persistence.__all__)


if __name__ == "__main__":
    unittest.main()
