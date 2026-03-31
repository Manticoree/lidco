"""Tests for smell_detector — Q126."""
from __future__ import annotations
import unittest
from lidco.proactive.smell_detector import Smell, SmellDetector


class TestSmell(unittest.TestCase):
    def test_creation(self):
        s = Smell(kind="long_method", location="foo.py:10", description="Too long", severity="medium")
        self.assertEqual(s.kind, "long_method")
        self.assertEqual(s.severity, "medium")


class TestSmellDetector(unittest.TestCase):
    def setUp(self):
        self.d = SmellDetector()

    def test_empty_source(self):
        smells = self.d.detect("")
        self.assertEqual(smells, [])

    def test_syntax_error_returns_empty(self):
        smells = self.d.detect("def f(")
        self.assertEqual(smells, [])

    def test_long_method(self):
        body = "\n".join(["    x = 1"] * 35)
        src = f"def big_fn():\n{body}"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertIn("long_method", kinds)

    def test_short_function_no_long_method(self):
        src = "def f():\n    pass"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertNotIn("long_method", kinds)

    def test_god_object(self):
        methods = "\n".join([f"    def m{i}(self): pass" for i in range(11)])
        src = f"class BigClass:\n{methods}"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertIn("god_object", kinds)

    def test_small_class_no_god_object(self):
        src = "class Small:\n    def m1(self): pass\n    def m2(self): pass"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertNotIn("god_object", kinds)

    def test_dead_code_private_function(self):
        src = "def _private_unused(): pass"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertIn("dead_code", kinds)

    def test_no_dead_code_if_called(self):
        src = "def _helper(): pass\ndef main():\n    _helper()"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertNotIn("dead_code", kinds)

    def test_detect_duplicates_across_files(self):
        block = "\n".join([f"x_{i} = {i}" for i in range(5)])
        sources = {
            "a.py": block + "\n# end a",
            "b.py": block + "\n# end b",
        }
        smells = self.d.detect_duplicates(sources)
        kinds = [s.kind for s in smells]
        self.assertIn("duplicate_code", kinds)

    def test_no_duplicates_unique_files(self):
        sources = {"a.py": "x = 1\ny = 2", "b.py": "a = 10\nb = 20"}
        smells = self.d.detect_duplicates(sources)
        self.assertEqual(smells, [])

    def test_summary_empty(self):
        s = self.d.summary([])
        self.assertEqual(s, {})

    def test_summary_by_severity(self):
        smells = [
            Smell("long_method", "f:1", "d", "medium"),
            Smell("god_object", "f:5", "d", "high"),
            Smell("dead_code", "f:10", "d", "low"),
            Smell("long_method", "f:20", "d", "medium"),
        ]
        s = self.d.summary(smells)
        self.assertEqual(s["medium"], 2)
        self.assertEqual(s["high"], 1)
        self.assertEqual(s["low"], 1)

    def test_detect_returns_list(self):
        self.assertIsInstance(self.d.detect("x = 1"), list)

    def test_detect_duplicates_returns_list(self):
        self.assertIsInstance(self.d.detect_duplicates({}), list)

    def test_large_class(self):
        body = "\n".join([f"    x_{i} = {i}" for i in range(210)])
        src = f"class Big:\n{body}"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertIn("large_class", kinds)

    def test_dunder_not_dead_code(self):
        src = "def __init__(self): pass"
        smells = self.d.detect(src)
        kinds = [s.kind for s in smells]
        self.assertNotIn("dead_code", kinds)

    def test_severity_medium_for_moderate_long_method(self):
        body = "\n".join(["    x = 1"] * 35)
        src = f"def medium_fn():\n{body}"
        smells = self.d.detect(src)
        long_methods = [s for s in smells if s.kind == "long_method"]
        self.assertTrue(len(long_methods) > 0)
        self.assertEqual(long_methods[0].severity, "medium")


if __name__ == "__main__":
    unittest.main()
