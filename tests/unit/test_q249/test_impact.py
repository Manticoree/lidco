"""Tests for codegraph.impact — ImpactAnalyzer."""
from __future__ import annotations

import unittest

from lidco.codegraph.builder import CodeGraphBuilder, GraphEdge, GraphNode
from lidco.codegraph.impact import ImpactAnalyzer, ImpactResult


def _make_graph() -> CodeGraphBuilder:
    """test_foo -> helper -> core, app -> helper."""
    b = CodeGraphBuilder()
    b.add_node(GraphNode(name="core", kind="function", file="core.py"))
    b.add_node(GraphNode(name="helper", kind="function", file="helper.py"))
    b.add_node(GraphNode(name="app", kind="function", file="app.py"))
    b.add_node(GraphNode(name="test_foo", kind="function", file="test_foo.py"))
    b.add_edge(GraphEdge(source="helper", target="core", kind="calls"))
    b.add_edge(GraphEdge(source="app", target="helper", kind="calls"))
    b.add_edge(GraphEdge(source="test_foo", target="helper", kind="calls"))
    return b


class TestImpactResult(unittest.TestCase):
    def test_frozen(self):
        r = ImpactResult(affected=["a"], confidence=0.9, transitive_count=1)
        with self.assertRaises(AttributeError):
            r.confidence = 0.5  # type: ignore[misc]

    def test_fields(self):
        r = ImpactResult(affected=["x", "y"], confidence=0.75, transitive_count=2)
        self.assertEqual(r.affected, ["x", "y"])
        self.assertEqual(r.transitive_count, 2)


class TestAnalyze(unittest.TestCase):
    def test_analyze_core_change(self):
        analyzer = ImpactAnalyzer(_make_graph())
        result = analyzer.analyze(["core"])
        # core is called by helper; helper is called by app and test_foo
        self.assertIn("helper", result.affected)
        self.assertIn("app", result.affected)
        self.assertIn("test_foo", result.affected)
        self.assertEqual(result.transitive_count, len(result.affected))

    def test_analyze_leaf(self):
        analyzer = ImpactAnalyzer(_make_graph())
        result = analyzer.analyze(["app"])
        # Nothing calls app
        self.assertEqual(result.affected, [])
        self.assertEqual(result.confidence, 1.0)

    def test_confidence_range(self):
        analyzer = ImpactAnalyzer(_make_graph())
        result = analyzer.analyze(["core"])
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_analyze_multiple(self):
        analyzer = ImpactAnalyzer(_make_graph())
        result = analyzer.analyze(["core", "helper"])
        # app and test_foo call helper
        self.assertIn("app", result.affected)
        self.assertIn("test_foo", result.affected)


class TestAffectedFiles(unittest.TestCase):
    def test_affected_files(self):
        analyzer = ImpactAnalyzer(_make_graph())
        files = analyzer.affected_files(["core"])
        self.assertIn("helper.py", files)
        self.assertIn("app.py", files)
        self.assertIn("test_foo.py", files)

    def test_no_affected_files(self):
        analyzer = ImpactAnalyzer(_make_graph())
        files = analyzer.affected_files(["app"])
        self.assertEqual(files, set())


class TestAffectedTests(unittest.TestCase):
    def test_affected_tests(self):
        analyzer = ImpactAnalyzer(_make_graph())
        tests = analyzer.affected_tests(["core"])
        self.assertEqual(tests, ["test_foo"])

    def test_custom_prefix(self):
        analyzer = ImpactAnalyzer(_make_graph())
        tests = analyzer.affected_tests(["core"], test_prefix="app")
        self.assertEqual(tests, ["app"])

    def test_no_tests_affected(self):
        analyzer = ImpactAnalyzer(_make_graph())
        tests = analyzer.affected_tests(["test_foo"])
        self.assertEqual(tests, [])


if __name__ == "__main__":
    unittest.main()
