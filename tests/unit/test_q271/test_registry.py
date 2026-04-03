"""Tests for ShortcutRegistry — Q271."""
from __future__ import annotations

import unittest

from lidco.shortcuts.registry import Shortcut, ShortcutRegistry


class TestShortcutRegistration(unittest.TestCase):
    def setUp(self):
        self.reg = ShortcutRegistry()

    def test_register_returns_shortcut(self):
        s = self.reg.register(Shortcut("ctrl+s", "save"))
        self.assertEqual(s.keys, "ctrl+s")
        self.assertEqual(s.command, "save")

    def test_register_conflict_raises(self):
        self.reg.register(Shortcut("ctrl+s", "save"))
        with self.assertRaises(ValueError):
            self.reg.register(Shortcut("ctrl+s", "other"))

    def test_same_keys_different_context_ok(self):
        self.reg.register(Shortcut("ctrl+s", "save", context="editor"))
        s2 = self.reg.register(Shortcut("ctrl+s", "send", context="chat"))
        self.assertEqual(s2.command, "send")

    def test_get_existing(self):
        self.reg.register(Shortcut("ctrl+z", "undo"))
        s = self.reg.get("ctrl+z")
        self.assertIsNotNone(s)
        self.assertEqual(s.command, "undo")

    def test_get_missing(self):
        self.assertIsNone(self.reg.get("ctrl+z"))

    def test_unregister_existing(self):
        self.reg.register(Shortcut("ctrl+z", "undo"))
        self.assertTrue(self.reg.unregister("ctrl+z"))
        self.assertIsNone(self.reg.get("ctrl+z"))

    def test_unregister_missing(self):
        self.assertFalse(self.reg.unregister("ctrl+z"))

    def test_find_by_command(self):
        self.reg.register(Shortcut("ctrl+s", "save"))
        self.reg.register(Shortcut("ctrl+shift+s", "save"))
        found = self.reg.find_by_command("save")
        self.assertEqual(len(found), 2)

    def test_find_by_command_empty(self):
        self.assertEqual(self.reg.find_by_command("nope"), [])

    def test_conflicts(self):
        self.reg.register(Shortcut("ctrl+s", "save"))
        conflicts = self.reg.conflicts("ctrl+s")
        self.assertEqual(len(conflicts), 1)

    def test_conflicts_empty(self):
        self.assertEqual(self.reg.conflicts("ctrl+s"), [])

    def test_all_shortcuts_no_filter(self):
        self.reg.register(Shortcut("a", "cmd_a"))
        self.reg.register(Shortcut("b", "cmd_b", context="editor"))
        self.assertEqual(len(self.reg.all_shortcuts()), 2)

    def test_all_shortcuts_filter_context(self):
        self.reg.register(Shortcut("a", "cmd_a"))
        self.reg.register(Shortcut("b", "cmd_b", context="editor"))
        self.assertEqual(len(self.reg.all_shortcuts(context="editor")), 1)

    def test_enable_disable(self):
        self.reg.register(Shortcut("ctrl+s", "save"))
        self.assertTrue(self.reg.disable("ctrl+s"))
        self.assertFalse(self.reg.get("ctrl+s").enabled)
        self.assertTrue(self.reg.enable("ctrl+s"))
        self.assertTrue(self.reg.get("ctrl+s").enabled)

    def test_enable_missing(self):
        self.assertFalse(self.reg.enable("ctrl+s"))

    def test_disable_missing(self):
        self.assertFalse(self.reg.disable("ctrl+s"))

    def test_summary(self):
        self.reg.register(Shortcut("a", "cmd_a"))
        self.reg.register(Shortcut("b", "cmd_b", context="editor"))
        s = self.reg.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["enabled"], 2)
        self.assertIn("global", s["contexts"])

    def test_normalise_keys(self):
        self.reg.register(Shortcut("Ctrl+S", "save"))
        self.assertIsNotNone(self.reg.get("ctrl+s"))
        self.assertIsNotNone(self.reg.get("CTRL+S"))


if __name__ == "__main__":
    unittest.main()
