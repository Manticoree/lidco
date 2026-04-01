"""Tests for DeepLinkHandler — Q189, task 1060."""
from __future__ import annotations

import unittest

from lidco.remote.deep_links import DeepLinkHandler, DeepLink


class TestDeepLink(unittest.TestCase):
    def test_frozen(self):
        dl = DeepLink(scheme="lidco", action="open", params={})
        with self.assertRaises(AttributeError):
            dl.scheme = "x"  # type: ignore[misc]

    def test_fields(self):
        dl = DeepLink(scheme="s", action="a", params={"k": "v"})
        self.assertEqual(dl.scheme, "s")
        self.assertEqual(dl.action, "a")
        self.assertEqual(dl.params, {"k": "v"})


class TestDeepLinkHandler(unittest.TestCase):
    def setUp(self):
        self.h = DeepLinkHandler()

    def test_parse_basic(self):
        link = self.h.parse("lidco://open?file=main.py")
        self.assertEqual(link.scheme, "lidco")
        self.assertEqual(link.action, "open")
        self.assertEqual(link.params["file"], "main.py")

    def test_parse_no_params(self):
        link = self.h.parse("lidco://session")
        self.assertEqual(link.action, "session")
        self.assertEqual(link.params, {})

    def test_parse_missing_scheme(self):
        with self.assertRaises(ValueError):
            self.h.parse("://open")

    def test_parse_missing_action(self):
        with self.assertRaises(ValueError):
            self.h.parse("lidco://")

    def test_generate_basic(self):
        uri = self.h.generate("open")
        self.assertEqual(uri, "lidco://open")

    def test_generate_with_params(self):
        uri = self.h.generate("file", {"path": "/tmp/x"})
        self.assertIn("lidco://file", uri)
        self.assertIn("path=", uri)

    def test_generate_empty_action_raises(self):
        with self.assertRaises(ValueError):
            self.h.generate("")

    def test_validate_valid(self):
        self.assertTrue(self.h.validate("lidco://open"))

    def test_validate_wrong_scheme(self):
        self.assertFalse(self.h.validate("http://open"))

    def test_validate_invalid_action(self):
        self.assertFalse(self.h.validate("lidco://nonexistent"))

    def test_validate_malformed(self):
        self.assertFalse(self.h.validate("not a uri at all"))

    def test_validate_all_actions(self):
        for action in ("open", "session", "command", "file", "pair", "settings"):
            self.assertTrue(self.h.validate(f"lidco://{action}"), msg=action)

    def test_roundtrip(self):
        uri = self.h.generate("command", {"cmd": "test"})
        link = self.h.parse(uri)
        self.assertEqual(link.action, "command")
        self.assertEqual(link.params["cmd"], "test")

    def test_parse_multiple_params(self):
        link = self.h.parse("lidco://open?a=1&b=2")
        self.assertEqual(link.params["a"], "1")
        self.assertEqual(link.params["b"], "2")

    def test_generate_none_params(self):
        uri = self.h.generate("session", None)
        self.assertEqual(uri, "lidco://session")

    def test_validate_empty_string(self):
        self.assertFalse(self.h.validate(""))


if __name__ == "__main__":
    unittest.main()
