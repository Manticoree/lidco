"""Tests for codegraph.query — GraphQueryEngine."""
from __future__ import annotations

import unittest

from lidco.codegraph.builder import CodeGraphBuilder, GraphEdge, GraphNode
from lidco.codegraph.query import GraphQueryEngine


def _make_graph() -> CodeGraphBuilder:
    """A -> B -> C, A -> C, D (isolated)."""
    b = CodeGraphBuilder()
    b.add_node(GraphNode(name="A", kind="function", file="a.py"))
    b.add_node(GraphNode(name="B", kind="function", file="b.py"))
    b.add_node(GraphNode(name="C", kind="function", file="c.py"))
    b.add_node(GraphNode(name="D", kind="function", file="d.py"))
    b.add_edge(GraphEdge(source="A", target="B", kind="calls"))
    b.add_edge(GraphEdge(source="B", target="C", kind="calls"))
    b.add_edge(GraphEdge(source="A", target="C", kind="calls"))
    return b


class TestCallers(unittest.TestCase):
    def test_callers_of(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(sorted(engine.callers_of("C")), ["A", "B"])

    def test_callers_none(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.callers_of("A"), [])

    def test_callers_isolated(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.callers_of("D"), [])


class TestCallees(unittest.TestCase):
    def test_callees_of(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(sorted(engine.callees_of("A")), ["B", "C"])

    def test_callees_leaf(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.callees_of("C"), [])


class TestDependsOn(unittest.TestCase):
    def test_transitive(self):
        engine = GraphQueryEngine(_make_graph())
        deps = engine.depends_on("A")
        self.assertEqual(deps, ["B", "C"])

    def test_leaf(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.depends_on("C"), [])

    def test_isolated(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.depends_on("D"), [])


class TestPath(unittest.TestCase):
    def test_direct_path(self):
        engine = GraphQueryEngine(_make_graph())
        p = engine.path("A", "B")
        self.assertEqual(p, ["A", "B"])

    def test_indirect_path(self):
        engine = GraphQueryEngine(_make_graph())
        p = engine.path("A", "C")
        # A->C is direct, so shortest is length 2
        self.assertEqual(len(p), 2)
        self.assertEqual(p[0], "A")
        self.assertEqual(p[-1], "C")

    def test_no_path(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertIsNone(engine.path("D", "A"))

    def test_same_node(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.path("A", "A"), ["A"])

    def test_reverse_no_path(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertIsNone(engine.path("C", "A"))


class TestSearch(unittest.TestCase):
    def test_exact(self):
        engine = GraphQueryEngine(_make_graph())
        results = engine.search("^A$")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "A")

    def test_partial(self):
        engine = GraphQueryEngine(_make_graph())
        results = engine.search("[AB]")
        self.assertEqual(len(results), 2)

    def test_no_match(self):
        engine = GraphQueryEngine(_make_graph())
        self.assertEqual(engine.search("zzz"), [])

    def test_dot_star(self):
        engine = GraphQueryEngine(_make_graph())
        results = engine.search(".*")
        self.assertEqual(len(results), 4)


if __name__ == "__main__":
    unittest.main()
