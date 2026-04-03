"""Tests for QuickActionRegistry."""
from __future__ import annotations

import unittest

from lidco.actions.registry import ActionResult, QuickAction, QuickActionRegistry


class TestQuickAction(unittest.TestCase):
    def test_defaults(self):
        a = QuickAction(name="x", description="d", handler_name="h")
        self.assertEqual(a.priority, 0)
        self.assertEqual(a.shortcut, "")
        self.assertEqual(a.context, "global")
        self.assertTrue(a.enabled)


class TestQuickActionRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = QuickActionRegistry()
        self.a1 = QuickAction("fmt", "Format code", "format_handler", priority=10, shortcut="ctrl+f")
        self.a2 = QuickAction("lint", "Lint code", "lint_handler", priority=5, context="editor")
        self.a3 = QuickAction("save", "Save file", "save_handler", priority=20, shortcut="ctrl+s")

    def test_register_and_get(self):
        ret = self.reg.register(self.a1)
        self.assertIs(ret, self.a1)
        self.assertIs(self.reg.get("fmt"), self.a1)

    def test_unregister(self):
        self.reg.register(self.a1)
        self.assertTrue(self.reg.unregister("fmt"))
        self.assertFalse(self.reg.unregister("fmt"))
        self.assertIsNone(self.reg.get("fmt"))

    def test_find_by_context(self):
        self.reg.register(self.a1)
        self.reg.register(self.a2)
        self.reg.register(self.a3)
        global_actions = self.reg.find("global")
        self.assertEqual([a.name for a in global_actions], ["save", "fmt"])

    def test_find_excludes_disabled(self):
        self.reg.register(self.a1)
        self.reg.disable("fmt")
        self.assertEqual(self.reg.find("global"), [])

    def test_execute_success(self):
        self.reg.register(self.a1)
        result = self.reg.execute("fmt")
        self.assertTrue(result.success)
        self.assertIn("format_handler", result.message)

    def test_execute_not_found(self):
        result = self.reg.execute("nope")
        self.assertFalse(result.success)
        self.assertIn("not found", result.message)

    def test_execute_disabled(self):
        self.reg.register(self.a1)
        self.reg.disable("fmt")
        result = self.reg.execute("fmt")
        self.assertFalse(result.success)
        self.assertIn("disabled", result.message)

    def test_enable_disable(self):
        self.reg.register(self.a1)
        self.assertTrue(self.reg.disable("fmt"))
        self.assertFalse(self.reg.get("fmt").enabled)
        self.assertTrue(self.reg.enable("fmt"))
        self.assertTrue(self.reg.get("fmt").enabled)
        self.assertFalse(self.reg.enable("no_such"))

    def test_by_shortcut(self):
        self.reg.register(self.a1)
        self.reg.register(self.a3)
        found = self.reg.by_shortcut("ctrl+f")
        self.assertEqual(found.name, "fmt")
        self.assertIsNone(self.reg.by_shortcut("ctrl+z"))

    def test_all_actions(self):
        self.reg.register(self.a1)
        self.reg.register(self.a2)
        self.assertEqual(len(self.reg.all_actions()), 2)

    def test_summary(self):
        self.reg.register(self.a1)
        self.reg.register(self.a2)
        self.reg.disable("lint")
        s = self.reg.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["enabled"], 1)
        self.assertEqual(s["disabled"], 1)
        self.assertIn("global", s["contexts"])
        self.assertIn("editor", s["contexts"])


if __name__ == "__main__":
    unittest.main()
