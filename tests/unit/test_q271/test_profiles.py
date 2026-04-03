"""Tests for ShortcutProfiles — Q271."""
from __future__ import annotations

import unittest

from lidco.shortcuts.registry import Shortcut, ShortcutRegistry
from lidco.shortcuts.profiles import Profile, ShortcutProfiles


class TestShortcutProfiles(unittest.TestCase):
    def setUp(self):
        self.reg = ShortcutRegistry()
        self.profiles = ShortcutProfiles(self.reg)

    def test_default_profile_active(self):
        self.assertEqual(self.profiles.active(), "default")

    def test_builtin_names(self):
        names = self.profiles.builtin_names()
        self.assertIn("default", names)
        self.assertIn("vim", names)
        self.assertIn("emacs", names)
        self.assertIn("vscode", names)

    def test_activate_vim(self):
        self.assertTrue(self.profiles.activate("vim"))
        self.assertEqual(self.profiles.active(), "vim")
        # registry should have vim shortcuts
        shortcuts = self.reg.all_shortcuts()
        commands = {s.command for s in shortcuts}
        self.assertIn("insert_mode", commands)

    def test_activate_nonexistent(self):
        self.assertFalse(self.profiles.activate("nope"))

    def test_create_custom(self):
        p = self.profiles.create("custom", [Shortcut("ctrl+m", "my_cmd")], "My profile")
        self.assertEqual(p.name, "custom")
        self.assertEqual(len(p.shortcuts), 1)

    def test_get_builtin(self):
        p = self.profiles.get("emacs")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "emacs")

    def test_get_missing(self):
        self.assertIsNone(self.profiles.get("nope"))

    def test_merge(self):
        merged = self.profiles.merge("default", "vim", "merged")
        self.assertIsInstance(merged, Profile)
        self.assertEqual(merged.name, "merged")
        # merged should have shortcuts from both
        self.assertGreater(len(merged.shortcuts), 0)

    def test_merge_missing_base(self):
        with self.assertRaises(ValueError):
            self.profiles.merge("nope", "vim", "m")

    def test_merge_missing_overlay(self):
        with self.assertRaises(ValueError):
            self.profiles.merge("default", "nope", "m")

    def test_all_profiles(self):
        all_p = self.profiles.all_profiles()
        self.assertGreaterEqual(len(all_p), 4)

    def test_summary(self):
        s = self.profiles.summary()
        self.assertEqual(s["active"], "default")
        self.assertGreaterEqual(s["total"], 4)
        self.assertIn("default", s["builtin"])

    def test_activate_loads_shortcuts_into_registry(self):
        self.profiles.activate("vscode")
        shortcuts = self.reg.all_shortcuts()
        commands = {s.command for s in shortcuts}
        self.assertIn("palette", commands)


if __name__ == "__main__":
    unittest.main()
