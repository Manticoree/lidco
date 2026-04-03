"""Tests for CodeActionsProvider."""
from __future__ import annotations

import unittest

from lidco.actions.code_provider import CodeAction, CodeActionsProvider


class TestCodeAction(unittest.TestCase):
    def test_defaults(self):
        a = CodeAction("test", "rename", "Rename")
        self.assertEqual(a.applicable_languages, ["python", "javascript"])

    def test_frozen(self):
        a = CodeAction("test", "rename", "Rename")
        with self.assertRaises(AttributeError):
            a.name = "other"  # type: ignore[misc]


class TestCodeActionsProvider(unittest.TestCase):
    def setUp(self):
        self.prov = CodeActionsProvider()

    def test_available_actions_python(self):
        actions = self.prov.available_actions("python")
        self.assertTrue(len(actions) >= 7)
        types = {a.type for a in actions}
        self.assertIn("extract_function", types)
        self.assertIn("wrap_try", types)

    def test_available_actions_unknown_lang(self):
        actions = self.prov.available_actions("rust")
        self.assertEqual(actions, [])

    def test_extract_function(self):
        code = "a = 1\nb = 2\nc = a + b\n"
        result = self.prov.extract_function(code, 1, 2, "compute")
        self.assertIn("def compute():", result)
        self.assertIn("compute()", result)

    def test_rename_symbol(self):
        code = "x = 1\nprint(x)\n"
        result = self.prov.rename_symbol(code, "x", "value")
        self.assertIn("value = 1", result)
        self.assertIn("print(value)", result)
        self.assertNotIn("x", result)

    def test_wrap_try(self):
        code = "a = 1\nrisky()\nb = 2\n"
        result = self.prov.wrap_try(code, 1, 2)
        self.assertIn("try:", result)
        self.assertIn("except Exception:", result)

    def test_add_import(self):
        code = "x = 1\n"
        result = self.prov.add_import(code, "import os")
        self.assertTrue(result.startswith("import os\n"))

    def test_toggle_comment_on(self):
        code = "a = 1\nb = 2\nc = 3\n"
        result = self.prov.toggle_comment(code, 0, 2)
        lines = result.splitlines()
        self.assertTrue(lines[0].startswith("# "))
        self.assertTrue(lines[1].startswith("# "))
        self.assertFalse(lines[2].startswith("#"))

    def test_toggle_comment_off(self):
        code = "# a = 1\n# b = 2\nc = 3\n"
        result = self.prov.toggle_comment(code, 0, 2)
        lines = result.splitlines()
        self.assertFalse(lines[0].startswith("#"))
        self.assertFalse(lines[1].startswith("#"))

    def test_summary(self):
        s = self.prov.summary()
        self.assertIn("total_actions", s)
        self.assertIn("types", s)
        self.assertEqual(s["total_actions"], 7)


if __name__ == "__main__":
    unittest.main()
