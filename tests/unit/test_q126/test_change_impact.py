"""Tests for change_impact2 — Q126."""
from __future__ import annotations
import unittest
from lidco.proactive.change_impact2 import ChangeImpactAnalyzer, ImpactReport


class TestImpactReport(unittest.TestCase):
    def test_total_affected(self):
        r = ImpactReport(
            changed_file="a",
            directly_affected=["b", "c"],
            transitively_affected=["d"],
        )
        self.assertEqual(r.total_affected, 3)

    def test_empty(self):
        r = ImpactReport(changed_file="x")
        self.assertEqual(r.total_affected, 0)


class TestChangeImpactAnalyzer(unittest.TestCase):
    def setUp(self):
        # b imports a, c imports a, d imports b
        self.analyzer = ChangeImpactAnalyzer(
            import_graph={
                "a": [],
                "b": ["a"],
                "c": ["a"],
                "d": ["b"],
            }
        )

    def test_analyze_direct(self):
        report = self.analyzer.analyze("a")
        self.assertIn("b", report.directly_affected)
        self.assertIn("c", report.directly_affected)

    def test_analyze_transitive(self):
        report = self.analyzer.analyze("a")
        self.assertIn("d", report.transitively_affected)

    def test_analyze_no_dependents(self):
        report = self.analyzer.analyze("d")
        self.assertEqual(report.directly_affected, [])
        self.assertEqual(report.transitively_affected, [])

    def test_changed_file_in_report(self):
        report = self.analyzer.analyze("a")
        self.assertEqual(report.changed_file, "a")

    def test_add_import(self):
        analyzer = ChangeImpactAnalyzer()
        analyzer.add_import("x", "y")
        report = analyzer.analyze("y")
        self.assertIn("x", report.directly_affected)

    def test_add_import_multiple(self):
        analyzer = ChangeImpactAnalyzer()
        analyzer.add_import("x", "shared")
        analyzer.add_import("y", "shared")
        report = analyzer.analyze("shared")
        self.assertIn("x", report.directly_affected)
        self.assertIn("y", report.directly_affected)

    def test_build_from_extractor(self):
        from lidco.analysis.python_extractor import ExtractionResult
        results = [
            ExtractionResult(module="a", imports=["base"]),
            ExtractionResult(module="b", imports=["base"]),
        ]
        analyzer = ChangeImpactAnalyzer()
        analyzer.build_from_extractor(results)
        report = analyzer.analyze("base")
        self.assertIn("a", report.directly_affected)
        self.assertIn("b", report.directly_affected)

    def test_reverse_graph(self):
        rev = self.analyzer.reverse_graph()
        self.assertIn("a", rev)
        self.assertIn("b", rev["a"])
        self.assertIn("c", rev["a"])

    def test_total_affected(self):
        report = self.analyzer.analyze("a")
        self.assertEqual(report.total_affected, len(report.directly_affected) + len(report.transitively_affected))

    def test_empty_graph(self):
        analyzer = ChangeImpactAnalyzer()
        report = analyzer.analyze("anything")
        self.assertEqual(report.directly_affected, [])
        self.assertEqual(report.transitively_affected, [])

    def test_no_double_count(self):
        # d imports b which imports a; changing a should not have d in directly_affected
        report = self.analyzer.analyze("a")
        self.assertNotIn("d", report.directly_affected)
        self.assertIn("d", report.transitively_affected)

    def test_chain_impact(self):
        analyzer = ChangeImpactAnalyzer(import_graph={
            "base": [],
            "mid": ["base"],
            "top": ["mid"],
        })
        report = analyzer.analyze("base")
        self.assertIn("mid", report.directly_affected)
        self.assertIn("top", report.transitively_affected)

    def test_init_with_none(self):
        analyzer = ChangeImpactAnalyzer(import_graph=None)
        report = analyzer.analyze("x")
        self.assertEqual(report.total_affected, 0)

    def test_reverse_graph_empty(self):
        analyzer = ChangeImpactAnalyzer()
        self.assertEqual(analyzer.reverse_graph(), {})

    def test_add_import_no_duplicate(self):
        analyzer = ChangeImpactAnalyzer()
        analyzer.add_import("x", "y")
        analyzer.add_import("x", "y")  # duplicate
        report = analyzer.analyze("y")
        self.assertEqual(len(report.directly_affected), 1)


if __name__ == "__main__":
    unittest.main()
