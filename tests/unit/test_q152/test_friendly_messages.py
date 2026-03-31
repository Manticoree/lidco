"""Tests for Q152 FriendlyMessages."""
from __future__ import annotations

import unittest

from lidco.errors.friendly_messages import FriendlyMessages, FriendlyError


class TestFriendlyError(unittest.TestCase):
    def test_fields(self):
        fe = FriendlyError(technical="T", friendly="F", suggestions=["a"], docs_hint="url")
        self.assertEqual(fe.technical, "T")
        self.assertEqual(fe.friendly, "F")
        self.assertEqual(fe.suggestions, ["a"])
        self.assertEqual(fe.docs_hint, "url")

    def test_defaults(self):
        fe = FriendlyError(technical="T", friendly="F")
        self.assertEqual(fe.suggestions, [])
        self.assertIsNone(fe.docs_hint)


class TestFriendlyMessages(unittest.TestCase):
    def setUp(self):
        self.fm = FriendlyMessages()

    def test_translate_unregistered(self):
        fe = self.fm.translate(RuntimeError("boom"))
        self.assertIn("boom", fe.friendly)
        self.assertIn("RuntimeError", fe.technical)

    def test_register_and_translate(self):
        self.fm.register("RuntimeError", "Something went wrong.", ["Try again."])
        fe = self.fm.translate(RuntimeError("boom"))
        self.assertEqual(fe.friendly, "Something went wrong.")
        self.assertEqual(fe.suggestions, ["Try again."])

    def test_register_with_docs_hint(self):
        self.fm.register("ValueError", "Bad value.", [], "https://docs.example.com")
        fe = self.fm.translate(ValueError("x"))
        self.assertEqual(fe.docs_hint, "https://docs.example.com")

    def test_translate_preserves_technical(self):
        self.fm.register("KeyError", "Missing key.", [])
        fe = self.fm.translate(KeyError("foo"))
        self.assertIn("KeyError", fe.technical)

    def test_translate_copies_suggestions(self):
        original = ["step 1", "step 2"]
        self.fm.register("RuntimeError", "err", original)
        fe = self.fm.translate(RuntimeError("x"))
        fe.suggestions.append("step 3")
        fe2 = self.fm.translate(RuntimeError("y"))
        self.assertEqual(len(fe2.suggestions), 2)

    def test_format_basic(self):
        fe = FriendlyError(technical="T: msg", friendly="Oops", suggestions=["Fix it."])
        out = self.fm.format(fe)
        self.assertIn("Oops", out)
        self.assertIn("T: msg", out)
        self.assertIn("1. Fix it.", out)

    def test_format_with_docs(self):
        fe = FriendlyError(technical="T", friendly="F", suggestions=[], docs_hint="http://x")
        out = self.fm.format(fe)
        self.assertIn("http://x", out)

    def test_format_no_docs(self):
        fe = FriendlyError(technical="T", friendly="F", suggestions=[])
        out = self.fm.format(fe)
        self.assertNotIn("Docs:", out)

    def test_format_multiple_suggestions(self):
        fe = FriendlyError(technical="T", friendly="F", suggestions=["a", "b", "c"])
        out = self.fm.format(fe)
        self.assertIn("1. a", out)
        self.assertIn("2. b", out)
        self.assertIn("3. c", out)

    def test_format_contains_error_label(self):
        fe = FriendlyError(technical="T", friendly="F")
        out = self.fm.format(fe)
        self.assertIn("Error:", out)


class TestWithDefaults(unittest.TestCase):
    def setUp(self):
        self.fm = FriendlyMessages.with_defaults()

    def test_module_not_found(self):
        fe = self.fm.translate(ModuleNotFoundError("No module named foo"))
        self.assertIn("missing", fe.friendly.lower())

    def test_file_not_found(self):
        fe = self.fm.translate(FileNotFoundError("x.py"))
        self.assertIn("not exist", fe.friendly.lower())

    def test_permission_error(self):
        fe = self.fm.translate(PermissionError("denied"))
        self.assertIn("permission", fe.friendly.lower())

    def test_syntax_error(self):
        try:
            compile("x(", "<test>", "exec")
        except SyntaxError as e:
            fe = self.fm.translate(e)
            self.assertIn("syntax", fe.friendly.lower())

    def test_value_error(self):
        fe = self.fm.translate(ValueError("bad"))
        self.assertIn("invalid", fe.friendly.lower())

    def test_type_error(self):
        fe = self.fm.translate(TypeError("wrong type"))
        self.assertIn("wrong type", fe.friendly.lower())

    def test_key_error(self):
        fe = self.fm.translate(KeyError("k"))
        self.assertIn("key", fe.friendly.lower())

    def test_connection_error(self):
        fe = self.fm.translate(ConnectionError("refused"))
        self.assertIn("connect", fe.friendly.lower())

    def test_timeout_error(self):
        fe = self.fm.translate(TimeoutError("timed out"))
        self.assertIn("too long", fe.friendly.lower())


if __name__ == "__main__":
    unittest.main()
