"""Tests for Preset and PresetLibrary."""
from __future__ import annotations

import unittest

from lidco.presets.library import Preset, PresetLibrary
from lidco.presets.template import SessionTemplate


class TestPreset(unittest.TestCase):
    def test_frozen(self):
        p = Preset(
            name="test",
            category="dev",
            template=SessionTemplate(name="test"),
        )
        with self.assertRaises(AttributeError):
            p.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        p = Preset(name="x", category="c", template=SessionTemplate(name="x"))
        self.assertEqual(p.author, "system")
        self.assertEqual(p.version, "1.0")


class TestPresetLibrary(unittest.TestCase):
    def setUp(self):
        self.lib = PresetLibrary()

    def test_builtin_names(self):
        names = self.lib.builtin_names()
        self.assertIn("bug-fix", names)
        self.assertIn("feature", names)
        self.assertIn("refactor", names)
        self.assertIn("review", names)
        self.assertIn("docs", names)
        self.assertEqual(len(names), 5)

    def test_get_builtin(self):
        p = self.lib.get("bug-fix")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "bug-fix")
        self.assertEqual(p.category, "development")

    def test_get_missing(self):
        self.assertIsNone(self.lib.get("nonexistent"))

    def test_by_category(self):
        dev = self.lib.by_category("development")
        self.assertTrue(len(dev) >= 3)
        self.assertTrue(all(p.category == "development" for p in dev))

    def test_add_user_preset(self):
        t = SessionTemplate(name="custom", description="Custom")
        p = Preset(name="custom", category="user", template=t, author="me")
        self.lib.add(p)
        self.assertIs(self.lib.get("custom"), p)

    def test_remove_user_preset(self):
        t = SessionTemplate(name="custom", description="Custom")
        p = Preset(name="custom", category="user", template=t, author="me")
        self.lib.add(p)
        self.assertTrue(self.lib.remove("custom"))
        self.assertIsNone(self.lib.get("custom"))

    def test_remove_builtin_fails(self):
        self.assertFalse(self.lib.remove("bug-fix"))
        self.assertIsNotNone(self.lib.get("bug-fix"))

    def test_remove_missing(self):
        self.assertFalse(self.lib.remove("nonexistent"))

    def test_categories(self):
        cats = self.lib.categories()
        self.assertIn("development", cats)
        self.assertIn("quality", cats)
        self.assertIn("documentation", cats)

    def test_all_presets(self):
        self.assertEqual(len(self.lib.all_presets()), 5)

    def test_summary(self):
        s = self.lib.summary()
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["builtin"], 5)
        self.assertEqual(s["user"], 0)


if __name__ == "__main__":
    unittest.main()
