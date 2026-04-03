"""Tests for VoiceControl (Q272)."""
from __future__ import annotations

import unittest

from lidco.a11y.voice_control import VoiceCommand, VoiceControl


class TestVoiceCommandFrozen(unittest.TestCase):
    def test_frozen(self):
        vc = VoiceCommand(phrase="go", action="navigate")
        with self.assertRaises(AttributeError):
            vc.phrase = "x"  # type: ignore[misc]

    def test_default_category(self):
        vc = VoiceCommand(phrase="go", action="navigate")
        self.assertEqual(vc.category, "navigation")


class TestRegisterUnregister(unittest.TestCase):
    def test_register(self):
        vc = VoiceControl()
        cmd = vc.register_command("open file", "file_open", "editing")
        self.assertEqual(cmd.phrase, "open file")
        self.assertEqual(cmd.action, "file_open")
        self.assertEqual(cmd.category, "editing")

    def test_unregister_existing(self):
        vc = VoiceControl()
        vc.register_command("quit", "exit")
        self.assertTrue(vc.unregister_command("quit"))
        self.assertEqual(vc.commands(), [])

    def test_unregister_missing(self):
        vc = VoiceControl()
        self.assertFalse(vc.unregister_command("nope"))


class TestMatch(unittest.TestCase):
    def test_exact_match(self):
        vc = VoiceControl()
        vc.register_command("save file", "save")
        result = vc.match("save file")
        self.assertIsNotNone(result)
        self.assertEqual(result.action, "save")

    def test_substring_match(self):
        vc = VoiceControl()
        vc.register_command("open", "open_file")
        result = vc.match("please open something")
        self.assertIsNotNone(result)
        self.assertEqual(result.action, "open_file")

    def test_wake_word_stripped(self):
        vc = VoiceControl(wake_word="hey lidco")
        vc.register_command("save", "do_save")
        result = vc.match("hey lidco save")
        self.assertIsNotNone(result)
        self.assertEqual(result.action, "do_save")

    def test_no_match(self):
        vc = VoiceControl()
        vc.register_command("open", "open_file")
        result = vc.match("xyz abc")
        self.assertIsNone(result)

    def test_word_overlap_match(self):
        vc = VoiceControl()
        vc.register_command("run all tests", "run_tests")
        result = vc.match("tests run")
        self.assertIsNotNone(result)
        self.assertEqual(result.action, "run_tests")


class TestCommands(unittest.TestCase):
    def test_filter_by_category(self):
        vc = VoiceControl()
        vc.register_command("go", "nav", "navigation")
        vc.register_command("edit", "ed", "editing")
        nav = vc.commands(category="navigation")
        self.assertEqual(len(nav), 1)
        self.assertEqual(nav[0].action, "nav")


class TestCategories(unittest.TestCase):
    def test_unique_sorted(self):
        vc = VoiceControl()
        vc.register_command("a", "1", "z_cat")
        vc.register_command("b", "2", "a_cat")
        vc.register_command("c", "3", "a_cat")
        self.assertEqual(vc.categories(), ["a_cat", "z_cat"])


class TestSetWakeWord(unittest.TestCase):
    def test_new_wake_word(self):
        vc = VoiceControl()
        vc.set_wake_word("ok computer")
        vc.register_command("help", "show_help")
        result = vc.match("ok computer help")
        self.assertIsNotNone(result)


class TestSummary(unittest.TestCase):
    def test_summary_keys(self):
        vc = VoiceControl()
        s = vc.summary()
        self.assertIn("enabled", s)
        self.assertIn("wake_word", s)
        self.assertIn("commands", s)
        self.assertIn("categories", s)


if __name__ == "__main__":
    unittest.main()
