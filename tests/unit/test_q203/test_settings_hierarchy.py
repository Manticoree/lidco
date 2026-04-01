"""Tests for SettingsHierarchy."""
from __future__ import annotations

import unittest

from lidco.enterprise.settings_hierarchy import SettingsHierarchy, SettingsLayer


class TestSettingsLayerFrozen(unittest.TestCase):
    def test_frozen(self):
        layer = SettingsLayer(name="user", data={"a": 1}, priority=0)
        with self.assertRaises(AttributeError):
            layer.name = "other"  # type: ignore[misc]


class TestAddRemoveLayer(unittest.TestCase):
    def test_add_and_list(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1}, priority=0)
        h.add_layer("org", {"b": 2}, priority=10)
        layers = h.list_layers()
        self.assertEqual(len(layers), 2)
        self.assertEqual(layers[0].name, "user")
        self.assertEqual(layers[1].name, "org")

    def test_remove_existing(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1}, priority=0)
        self.assertTrue(h.remove_layer("user"))
        self.assertEqual(len(h.list_layers()), 0)

    def test_remove_nonexistent(self):
        h = SettingsHierarchy()
        self.assertFalse(h.remove_layer("nope"))

    def test_replace_layer(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1}, priority=0)
        h.add_layer("user", {"a": 99}, priority=0)
        self.assertEqual(len(h.list_layers()), 1)
        self.assertEqual(h.resolve("a"), 99)


class TestResolve(unittest.TestCase):
    def test_higher_priority_wins(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"theme": "dark"}, priority=0)
        h.add_layer("org", {"theme": "light"}, priority=10)
        self.assertEqual(h.resolve("theme"), "light")

    def test_dot_notation(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": {"b": {"c": 42}}}, priority=0)
        self.assertEqual(h.resolve("a.b.c"), 42)

    def test_default(self):
        h = SettingsHierarchy()
        self.assertEqual(h.resolve("missing", "fallback"), "fallback")

    def test_lower_priority_fallback(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"x": 1, "y": 2}, priority=0)
        h.add_layer("org", {"x": 99}, priority=10)
        self.assertEqual(h.resolve("x"), 99)
        self.assertEqual(h.resolve("y"), 2)


class TestResolveAll(unittest.TestCase):
    def test_merge_all_layers(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1, "b": 2}, priority=0)
        h.add_layer("org", {"b": 99, "c": 3}, priority=10)
        merged = h.resolve_all()
        self.assertEqual(merged, {"a": 1, "b": 99, "c": 3})

    def test_deep_merge(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"nested": {"x": 1, "y": 2}}, priority=0)
        h.add_layer("org", {"nested": {"y": 99}}, priority=10)
        merged = h.resolve_all()
        self.assertEqual(merged["nested"]["x"], 1)
        self.assertEqual(merged["nested"]["y"], 99)


class TestDiff(unittest.TestCase):
    def test_diff_keys(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1, "b": 2}, priority=0)
        h.add_layer("org", {"a": 1, "b": 99, "c": 3}, priority=10)
        d = h.diff("user", "org")
        self.assertIn("b", d)
        self.assertEqual(d["b"], (2, 99))
        self.assertIn("c", d)
        self.assertNotIn("a", d)

    def test_diff_nonexistent_layer(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1}, priority=0)
        d = h.diff("user", "nope")
        self.assertEqual(d, {})

    def test_diff_nested(self):
        h = SettingsHierarchy()
        h.add_layer("a", {"n": {"x": 1}}, priority=0)
        h.add_layer("b", {"n": {"x": 2}}, priority=1)
        d = h.diff("a", "b")
        self.assertIn("n.x", d)
        self.assertEqual(d["n.x"], (1, 2))


class TestSummary(unittest.TestCase):
    def test_summary_content(self):
        h = SettingsHierarchy()
        h.add_layer("user", {"a": 1}, priority=0)
        s = h.summary()
        self.assertIn("1 layers", s)
        self.assertIn("user", s)


if __name__ == "__main__":
    unittest.main()
