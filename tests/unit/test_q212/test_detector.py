"""Tests for smart_refactor.detector."""
from __future__ import annotations

import unittest

from lidco.smart_refactor.detector import (
    RefactoringDetector,
    RefactoringOpportunity,
    SmellType,
)


class TestSmellType(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(SmellType.LONG_METHOD, "long_method")
        self.assertEqual(SmellType.DEEP_NESTING, "deep_nesting")
        self.assertEqual(SmellType.DEAD_CODE, "dead_code")


class TestRefactoringOpportunity(unittest.TestCase):
    def test_frozen(self):
        opp = RefactoringOpportunity(smell=SmellType.LONG_METHOD, file="a.py", name="foo")
        with self.assertRaises(AttributeError):
            opp.name = "bar"  # type: ignore[misc]

    def test_defaults(self):
        opp = RefactoringOpportunity(smell=SmellType.DEAD_CODE, file="x.py", name="f")
        self.assertEqual(opp.line, 0)
        self.assertAlmostEqual(opp.confidence, 0.5)
        self.assertEqual(opp.estimated_impact, "medium")
        self.assertEqual(opp.suggestion, "")


class TestDetectLongMethods(unittest.TestCase):
    def test_short_method_no_smell(self):
        src = "def foo():\n    pass\n"
        d = RefactoringDetector(max_method_lines=5)
        self.assertEqual(d.detect_long_methods(src), [])

    def test_long_method_detected(self):
        body = "\n".join(f"    x = {i}" for i in range(60))
        src = f"def big():\n{body}\n"
        d = RefactoringDetector(max_method_lines=10)
        results = d.detect_long_methods(src, file="big.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].smell, SmellType.LONG_METHOD)
        self.assertEqual(results[0].name, "big")
        self.assertEqual(results[0].file, "big.py")
        self.assertIn("big", results[0].suggestion)

    def test_syntax_error_returns_empty(self):
        d = RefactoringDetector()
        self.assertEqual(d.detect_long_methods("def (broken"), [])


class TestDetectDeepNesting(unittest.TestCase):
    def test_shallow_no_smell(self):
        src = "def f():\n    if True:\n        pass\n"
        d = RefactoringDetector(max_nesting=4)
        self.assertEqual(d.detect_deep_nesting(src), [])

    def test_deep_nesting_detected(self):
        indent = ""
        lines = ["def deep():"]
        for i in range(6):
            indent += "    "
            lines.append(f"{indent}if True:")
        lines.append(f"{indent}    pass")
        src = "\n".join(lines) + "\n"
        d = RefactoringDetector(max_nesting=3)
        results = d.detect_deep_nesting(src, file="nest.py")
        self.assertGreater(len(results), 0)
        self.assertTrue(all(r.smell == SmellType.DEEP_NESTING for r in results))


class TestDetectAll(unittest.TestCase):
    def test_combines_detectors(self):
        body = "\n".join(f"    x = {i}" for i in range(60))
        src = f"def big():\n{body}\n"
        d = RefactoringDetector(max_method_lines=10)
        all_results = d.detect_all(src)
        self.assertGreater(len(all_results), 0)


class TestConfigure(unittest.TestCase):
    def test_configure_updates_thresholds(self):
        d = RefactoringDetector()
        d.configure(max_method_lines=10, max_nesting=2)
        self.assertEqual(d.max_method_lines, 10)
        self.assertEqual(d.max_nesting, 2)

    def test_configure_partial(self):
        d = RefactoringDetector(max_method_lines=50, max_nesting=4)
        d.configure(max_nesting=2)
        self.assertEqual(d.max_method_lines, 50)
        self.assertEqual(d.max_nesting, 2)


class TestSummary(unittest.TestCase):
    def test_empty(self):
        d = RefactoringDetector()
        self.assertIn("No refactoring", d.summary([]))

    def test_with_items(self):
        opps = [
            RefactoringOpportunity(smell=SmellType.LONG_METHOD, file="a.py", name="f"),
            RefactoringOpportunity(smell=SmellType.DEEP_NESTING, file="a.py", name="g"),
        ]
        d = RefactoringDetector()
        text = d.summary(opps)
        self.assertIn("2", text)
        self.assertIn("long_method", text)
        self.assertIn("deep_nesting", text)


if __name__ == "__main__":
    unittest.main()
