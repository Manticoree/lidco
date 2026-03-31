"""Tests for Q140 InputSanitizer."""
from __future__ import annotations

import unittest

from lidco.input.sanitizer import InputSanitizer, SanitizeResult


class TestSanitizeResult(unittest.TestCase):
    def test_defaults(self):
        r = SanitizeResult(original="x", sanitized="x")
        self.assertEqual(r.warnings, [])
        self.assertFalse(r.was_modified)


class TestInputSanitizer(unittest.TestCase):
    def setUp(self):
        self.s = InputSanitizer()

    # -- sanitize --

    def test_clean_text_unchanged(self):
        r = self.s.sanitize("hello world")
        self.assertEqual(r.sanitized, "hello world")
        self.assertFalse(r.was_modified)

    def test_control_chars_removed(self):
        r = self.s.sanitize("hello\x00world")
        self.assertEqual(r.sanitized, "helloworld")
        self.assertTrue(r.was_modified)
        self.assertIn("Control characters removed", r.warnings)

    def test_whitespace_normalized(self):
        r = self.s.sanitize("  hello   world  ")
        self.assertEqual(r.sanitized, "hello world")
        self.assertTrue(r.was_modified)

    def test_shell_injection_warning(self):
        r = self.s.sanitize("hello; rm -rf /")
        self.assertTrue(any("shell" in w.lower() for w in r.warnings))

    def test_traversal_warning(self):
        r = self.s.sanitize("../../etc/passwd")
        self.assertTrue(any("traversal" in w.lower() for w in r.warnings))

    def test_tab_normalized(self):
        r = self.s.sanitize("a\tb")
        self.assertEqual(r.sanitized, "a b")

    # -- sanitize_path --

    def test_path_backslash_normalized(self):
        r = self.s.sanitize_path("src\\lib\\file.py")
        self.assertEqual(r.sanitized, "src/lib/file.py")
        self.assertTrue(r.was_modified)

    def test_path_traversal_blocked(self):
        r = self.s.sanitize_path("../../etc/passwd")
        self.assertNotIn("..", r.sanitized)
        self.assertIn("Path traversal blocked", r.warnings)

    def test_path_double_slash(self):
        r = self.s.sanitize_path("src//lib//file.py")
        self.assertEqual(r.sanitized, "src/lib/file.py")

    def test_clean_path_unchanged(self):
        r = self.s.sanitize_path("src/lib/file.py")
        self.assertEqual(r.sanitized, "src/lib/file.py")
        self.assertFalse(r.was_modified)

    # -- sanitize_identifier --

    def test_valid_identifier_unchanged(self):
        r = self.s.sanitize_identifier("my_var")
        self.assertEqual(r.sanitized, "my_var")
        self.assertFalse(r.was_modified)

    def test_spaces_replaced(self):
        r = self.s.sanitize_identifier("my var")
        self.assertEqual(r.sanitized, "my_var")
        self.assertTrue(r.was_modified)

    def test_digit_start_prefixed(self):
        r = self.s.sanitize_identifier("3name")
        self.assertEqual(r.sanitized, "_3name")
        self.assertIn("digit", r.warnings[0].lower())

    def test_special_chars_replaced(self):
        r = self.s.sanitize_identifier("my-var.name")
        self.assertEqual(r.sanitized, "my_var_name")

    def test_empty_identifier(self):
        r = self.s.sanitize_identifier("")
        self.assertEqual(r.sanitized, "_")
        self.assertTrue(r.was_modified)

    # -- is_safe --

    def test_safe_text(self):
        self.assertTrue(self.s.is_safe("hello world"))

    def test_not_safe_control_char(self):
        self.assertFalse(self.s.is_safe("hello\x00"))

    def test_not_safe_traversal(self):
        self.assertFalse(self.s.is_safe("../../etc"))

    def test_not_safe_shell_injection(self):
        self.assertFalse(self.s.is_safe("cmd; rm -rf"))

    def test_not_safe_pipe(self):
        self.assertFalse(self.s.is_safe("cat file | grep"))

    def test_not_safe_backtick(self):
        self.assertFalse(self.s.is_safe("hello `whoami`"))

    # -- escape_for_shell --

    def test_escape_simple(self):
        result = self.s.escape_for_shell("hello")
        self.assertIn("hello", result)

    def test_escape_special_chars(self):
        result = self.s.escape_for_shell("hello; rm -rf /")
        # shlex.quote wraps in single quotes
        self.assertIn("'", result)


if __name__ == "__main__":
    unittest.main()
