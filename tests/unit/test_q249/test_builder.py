"""Tests for codegraph.builder — CodeGraphBuilder, GraphNode, GraphEdge."""
from __future__ import annotations

import unittest

from lidco.codegraph.builder import CodeGraphBuilder, GraphEdge, GraphNode


class TestGraphNode(unittest.TestCase):
    def test_creation(self):
        node = GraphNode(name="foo", kind="function", file="a.py", line=10)
        self.assertEqual(node.name, "foo")
        self.assertEqual(node.kind, "function")
        self.assertEqual(node.file, "a.py")
        self.assertEqual(node.line, 10)

    def test_defaults(self):
        node = GraphNode(name="bar", kind="class", file="b.py")
        self.assertEqual(node.line, 0)
        self.assertEqual(node.metadata, {})

    def test_frozen(self):
        node = GraphNode(name="x", kind="function", file="c.py")
        with self.assertRaises(AttributeError):
            node.name = "y"  # type: ignore[misc]


class TestGraphEdge(unittest.TestCase):
    def test_creation(self):
        edge = GraphEdge(source="a", target="b", kind="calls")
        self.assertEqual(edge.source, "a")
        self.assertEqual(edge.target, "b")
        self.assertEqual(edge.kind, "calls")

    def test_frozen(self):
        edge = GraphEdge(source="a", target="b", kind="calls")
        with self.assertRaises(AttributeError):
            edge.kind = "imports"  # type: ignore[misc]


class TestCodeGraphBuilder(unittest.TestCase):
    def _make_builder(self) -> CodeGraphBuilder:
        b = CodeGraphBuilder()
        b.add_node(GraphNode(name="foo", kind="function", file="a.py"))
        b.add_node(GraphNode(name="bar", kind="class", file="b.py"))
        b.add_edge(GraphEdge(source="foo", target="bar", kind="calls"))
        return b

    def test_add_node_and_get(self):
        b = self._make_builder()
        self.assertIsNotNone(b.get_node("foo"))
        self.assertIsNone(b.get_node("nonexistent"))

    def test_nodes_list(self):
        b = self._make_builder()
        names = {n.name for n in b.nodes()}
        self.assertEqual(names, {"foo", "bar"})

    def test_edges_list(self):
        b = self._make_builder()
        self.assertEqual(len(b.edges()), 1)
        self.assertEqual(b.edges()[0].kind, "calls")

    def test_get_edges_by_source(self):
        b = self._make_builder()
        edges = b.get_edges("foo")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].target, "bar")

    def test_get_edges_empty(self):
        b = self._make_builder()
        self.assertEqual(b.get_edges("bar"), [])

    def test_build_from_symbols(self):
        b = CodeGraphBuilder()
        symbols = [
            {"name": "A", "kind": "class", "file": "m.py", "calls": ["B"]},
            {"name": "B", "kind": "function", "file": "m.py"},
        ]
        b.build_from_symbols(symbols)
        self.assertEqual(len(b.nodes()), 2)
        self.assertEqual(len(b.edges()), 1)
        self.assertEqual(b.edges()[0].source, "A")
        self.assertEqual(b.edges()[0].target, "B")

    def test_build_from_symbols_no_calls(self):
        b = CodeGraphBuilder()
        b.build_from_symbols([{"name": "X", "kind": "var", "file": "x.py"}])
        self.assertEqual(len(b.nodes()), 1)
        self.assertEqual(len(b.edges()), 0)

    def test_to_dict(self):
        b = self._make_builder()
        d = b.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("edges", d)
        self.assertEqual(len(d["nodes"]), 2)
        self.assertEqual(len(d["edges"]), 1)
        self.assertEqual(d["edges"][0]["kind"], "calls")

    def test_to_dict_node_fields(self):
        b = CodeGraphBuilder()
        b.add_node(GraphNode(name="z", kind="module", file="z.py", line=5, metadata={"key": "val"}))
        d = b.to_dict()
        node = d["nodes"][0]
        self.assertEqual(node["name"], "z")
        self.assertEqual(node["line"], 5)
        self.assertEqual(node["metadata"], {"key": "val"})

    def test_overwrite_node(self):
        b = CodeGraphBuilder()
        b.add_node(GraphNode(name="a", kind="function", file="x.py"))
        b.add_node(GraphNode(name="a", kind="class", file="y.py"))
        self.assertEqual(b.get_node("a").kind, "class")
        self.assertEqual(len(b.nodes()), 1)


if __name__ == "__main__":
    unittest.main()
