"""Tests for codegraph.visualizer — GraphVisualizer."""
from __future__ import annotations

import unittest

from lidco.codegraph.builder import CodeGraphBuilder, GraphEdge, GraphNode
from lidco.codegraph.visualizer import GraphVisualizer


def _make_graph() -> CodeGraphBuilder:
    b = CodeGraphBuilder()
    b.add_node(GraphNode(name="foo", kind="function", file="a.py"))
    b.add_node(GraphNode(name="bar", kind="class", file="a.py"))
    b.add_node(GraphNode(name="baz", kind="function", file="b.py"))
    b.add_edge(GraphEdge(source="foo", target="bar", kind="calls"))
    b.add_edge(GraphEdge(source="bar", target="baz", kind="inherits"))
    return b


class TestToDot(unittest.TestCase):
    def test_contains_digraph(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.to_dot()
        self.assertIn("digraph codegraph", dot)

    def test_contains_nodes(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.to_dot()
        self.assertIn('"foo"', dot)
        self.assertIn('"bar"', dot)
        self.assertIn('"baz"', dot)

    def test_contains_edges(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.to_dot()
        self.assertIn('"foo" -> "bar"', dot)
        self.assertIn('label="calls"', dot)

    def test_empty_graph(self):
        viz = GraphVisualizer(CodeGraphBuilder())
        dot = viz.to_dot()
        self.assertIn("digraph codegraph", dot)
        self.assertIn("}", dot)


class TestToMermaid(unittest.TestCase):
    def test_contains_header(self):
        viz = GraphVisualizer(_make_graph())
        m = viz.to_mermaid()
        self.assertIn("flowchart TD", m)

    def test_contains_nodes(self):
        viz = GraphVisualizer(_make_graph())
        m = viz.to_mermaid()
        self.assertIn("foo[foo]", m)
        self.assertIn("bar[bar]", m)

    def test_contains_edges(self):
        viz = GraphVisualizer(_make_graph())
        m = viz.to_mermaid()
        self.assertIn("foo -->|calls| bar", m)
        self.assertIn("bar -->|inherits| baz", m)


class TestHighlightPath(unittest.TestCase):
    def test_highlighted_nodes(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.highlight_path(["foo", "bar"])
        self.assertIn("fillcolor=yellow", dot)
        # baz is not highlighted
        lines = dot.split("\n")
        baz_lines = [l for l in lines if '"baz"' in l and "label=" in l]
        for line in baz_lines:
            self.assertNotIn("fillcolor", line)

    def test_empty_path(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.highlight_path([])
        # No yellow highlights
        self.assertNotIn("fillcolor=yellow", dot)


class TestFilterByFile(unittest.TestCase):
    def test_filter(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.filter_by_file("a.py")
        self.assertIn('"foo"', dot)
        self.assertIn('"bar"', dot)
        # baz is in b.py, should not appear
        self.assertNotIn('"baz"', dot)

    def test_filter_no_match(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.filter_by_file("nonexistent.py")
        self.assertIn("digraph codegraph", dot)
        self.assertNotIn('"foo"', dot)

    def test_filter_edges_only_within_file(self):
        viz = GraphVisualizer(_make_graph())
        dot = viz.filter_by_file("a.py")
        # foo->bar is within a.py
        self.assertIn('"foo" -> "bar"', dot)
        # bar->baz crosses files, should not appear
        self.assertNotIn('"bar" -> "baz"', dot)


if __name__ == "__main__":
    unittest.main()
