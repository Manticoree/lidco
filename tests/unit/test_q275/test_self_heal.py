"""Tests for lidco.recovery.self_heal."""
from __future__ import annotations

import unittest

from lidco.recovery.self_heal import HealResult, SelfHealEngine


class TestSelfHealEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SelfHealEngine()

    def test_heal_missing_import(self):
        code = "x = json.dumps({})"
        result = self.engine.heal("ModuleNotFoundError: No module named 'json'", code)
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn("import json", result.fixed)

    def test_heal_missing_import_already_present(self):
        code = "import json\nx = json.dumps({})"
        result = self.engine.heal("ModuleNotFoundError: No module named 'json'", code)
        self.assertIsNotNone(result)
        self.assertFalse(result.success)  # no change needed

    def test_heal_syntax_missing_colon(self):
        code = "def foo()\n    pass"
        result = self.engine.heal("SyntaxError: expected ':' at line 1", code)
        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertIn("def foo():", result.fixed)

    def test_heal_indentation(self):
        code = "def foo():\n   x = 1\n      y = 2"
        result = self.engine.heal("IndentationError: unexpected indent", code)
        self.assertIsNotNone(result)
        self.assertEqual(result.error_type, "indentation")

    def test_heal_no_fix(self):
        result = self.engine.heal("some random error we cannot fix")
        self.assertIsNone(result)

    def test_fix_missing_import_inserts_after_existing(self):
        code = "import os\n\nx = sys.argv"
        fixed = self.engine.fix_missing_import(code, "sys")
        lines = fixed.split("\n")
        self.assertEqual(lines[1], "import sys")

    def test_fix_syntax_error_unmatched_paren(self):
        code = "x = foo(bar(1, 2)"
        fixed = self.engine.fix_syntax_error(code, 1)
        self.assertTrue(fixed.rstrip().endswith(")"))

    def test_fix_indentation_normalizes(self):
        code = "def f():\n  x = 1\n      y = 2"
        fixed = self.engine.fix_indentation(code)
        for line in fixed.split("\n"):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                self.assertEqual(indent % 4, 0)

    def test_preview_no_record(self):
        code = "x = json.dumps({})"
        preview = self.engine.preview("ModuleNotFoundError: No module named 'json'", code)
        self.assertIn("import json", preview)
        # preview should not record in history
        self.assertEqual(len(self.engine.history()), 0)

    def test_history_and_success_rate(self):
        self.engine.heal("ModuleNotFoundError: No module named 'os'", "x = os.path")
        self.assertEqual(len(self.engine.history()), 1)
        self.assertGreaterEqual(self.engine.success_rate(), 0.0)

    def test_summary(self):
        s = self.engine.summary()
        self.assertIn("total_heals", s)
        self.assertIn("success_rate", s)

    def test_heal_result_frozen(self):
        r = HealResult(error_type="x", fix_applied="y", original="a", fixed="b", success=True)
        with self.assertRaises(AttributeError):
            r.success = False  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
