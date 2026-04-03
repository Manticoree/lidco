"""Tests for DocCoverageAnalyzer (Q258)."""
from __future__ import annotations

import unittest

from lidco.docgen.coverage import DocCoverageAnalyzer, CoverageResult


class TestCoverageResult(unittest.TestCase):
    def test_dataclass_fields(self):
        r = CoverageResult(total_symbols=5, documented=3, undocumented=["a", "b"], coverage_pct=60.0)
        self.assertEqual(r.total_symbols, 5)
        self.assertEqual(r.documented, 3)
        self.assertEqual(r.undocumented, ["a", "b"])
        self.assertEqual(r.coverage_pct, 60.0)

    def test_frozen(self):
        r = CoverageResult(total_symbols=1, documented=1, undocumented=[], coverage_pct=100.0)
        with self.assertRaises(AttributeError):
            r.total_symbols = 99  # type: ignore[misc]


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.analyzer = DocCoverageAnalyzer()

    def test_all_documented(self):
        src = 'def foo():\n    """Doc."""\n    pass\n'
        result = self.analyzer.analyze(src)
        self.assertEqual(result.total_symbols, 1)
        self.assertEqual(result.documented, 1)
        self.assertEqual(result.undocumented, [])
        self.assertEqual(result.coverage_pct, 100.0)

    def test_none_documented(self):
        src = "def foo():\n    pass\ndef bar():\n    pass\n"
        result = self.analyzer.analyze(src)
        self.assertEqual(result.total_symbols, 2)
        self.assertEqual(result.documented, 0)
        self.assertEqual(result.undocumented, ["foo", "bar"])
        self.assertEqual(result.coverage_pct, 0.0)

    def test_partial_documented(self):
        src = 'def foo():\n    """Yes."""\n    pass\ndef bar():\n    pass\n'
        result = self.analyzer.analyze(src)
        self.assertEqual(result.total_symbols, 2)
        self.assertEqual(result.documented, 1)
        self.assertEqual(result.coverage_pct, 50.0)

    def test_class_counted(self):
        src = 'class Foo:\n    """Doc."""\n    pass\n'
        result = self.analyzer.analyze(src)
        self.assertEqual(result.total_symbols, 1)
        self.assertEqual(result.documented, 1)

    def test_empty_source(self):
        result = self.analyzer.analyze("")
        self.assertEqual(result.total_symbols, 0)
        self.assertEqual(result.coverage_pct, 100.0)

    def test_syntax_error_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.analyze("def (broken")

    def test_async_function(self):
        src = 'async def fetch():\n    """Fetch data."""\n    pass\n'
        result = self.analyzer.analyze(src)
        self.assertEqual(result.documented, 1)

    def test_class_with_methods(self):
        src = (
            'class Foo:\n'
            '    """A class."""\n'
            '    def bar(self):\n'
            '        pass\n'
        )
        result = self.analyzer.analyze(src)
        # Foo (documented) + bar (undocumented)
        self.assertEqual(result.total_symbols, 2)
        self.assertEqual(result.documented, 1)
        self.assertIn("bar", result.undocumented)


class TestFindMissingParams(unittest.TestCase):
    def setUp(self):
        self.analyzer = DocCoverageAnalyzer()

    def test_no_missing(self):
        src = 'def foo(x):\n    """Do thing.\n\n    x is used.\n    """\n    pass\n'
        result = self.analyzer.find_missing_params(src)
        self.assertEqual(result, [])

    def test_missing_param(self):
        src = 'def foo(x, y):\n    """Do thing.\n\n    x: the first value\n    """\n    pass\n'
        result = self.analyzer.find_missing_params(src)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "foo")
        self.assertIn("y", result[0]["missing"])

    def test_no_docstring_skipped(self):
        src = "def foo(x):\n    pass\n"
        result = self.analyzer.find_missing_params(src)
        self.assertEqual(result, [])

    def test_self_excluded(self):
        src = (
            'class C:\n'
            '    def bar(self, z):\n'
            '        """Does bar with z."""\n'
            '        pass\n'
        )
        result = self.analyzer.find_missing_params(src)
        self.assertEqual(result, [])


class TestFindStale(unittest.TestCase):
    def setUp(self):
        self.analyzer = DocCoverageAnalyzer()

    def test_no_change(self):
        src = 'def foo():\n    """Doc."""\n    return 1\n'
        result = self.analyzer.find_stale(src, src)
        self.assertEqual(result, [])

    def test_stale_detected(self):
        old = 'def foo():\n    """Doc."""\n    return 1\n'
        new = 'def foo():\n    """Doc."""\n    return 2\n'
        result = self.analyzer.find_stale(new, old)
        self.assertIn("foo", result)

    def test_new_function_not_stale(self):
        old = 'def foo():\n    """Doc."""\n    return 1\n'
        new = old + 'def bar():\n    """New."""\n    return 2\n'
        result = self.analyzer.find_stale(new, old)
        self.assertNotIn("bar", result)

    def test_doc_updated_not_stale(self):
        old = 'def foo():\n    """Old doc."""\n    return 1\n'
        new = 'def foo():\n    """New doc."""\n    return 2\n'
        result = self.analyzer.find_stale(new, old)
        self.assertNotIn("foo", result)


class TestSummary(unittest.TestCase):
    def setUp(self):
        self.analyzer = DocCoverageAnalyzer()

    def test_full_coverage(self):
        r = CoverageResult(total_symbols=3, documented=3, undocumented=[], coverage_pct=100.0)
        s = self.analyzer.summary(r)
        self.assertIn("100.0%", s)
        self.assertIn("3/3", s)

    def test_partial_coverage(self):
        r = CoverageResult(total_symbols=2, documented=1, undocumented=["bar"], coverage_pct=50.0)
        s = self.analyzer.summary(r)
        self.assertIn("bar", s)
        self.assertIn("50.0%", s)


if __name__ == "__main__":
    unittest.main()
