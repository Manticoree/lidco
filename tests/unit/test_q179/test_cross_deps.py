"""Tests for CrossRepoDeps and DepGraph."""

from __future__ import annotations

import unittest

from lidco.workspace.cross_deps import CrossRepoDeps, DepGraph
from lidco.workspace.detector import PackageInfo


class TestDepGraph(unittest.TestCase):
    """Tests for DepGraph data structure."""

    def test_empty_graph(self) -> None:
        g = DepGraph()
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.edges, [])

    def test_find_circular_no_cycle(self) -> None:
        g = DepGraph(nodes=["a", "b", "c"], edges=[("a", "b"), ("b", "c")])
        cycles = g.find_circular()
        self.assertEqual(cycles, [])

    def test_find_circular_simple(self) -> None:
        g = DepGraph(nodes=["a", "b"], edges=[("a", "b"), ("b", "a")])
        cycles = g.find_circular()
        self.assertEqual(len(cycles), 1)
        self.assertIn("a", cycles[0])
        self.assertIn("b", cycles[0])

    def test_find_circular_three_nodes(self) -> None:
        g = DepGraph(nodes=["a", "b", "c"], edges=[("a", "b"), ("b", "c"), ("c", "a")])
        cycles = g.find_circular()
        self.assertEqual(len(cycles), 1)
        self.assertEqual(len(cycles[0]), 3)

    def test_affected_by_direct(self) -> None:
        g = DepGraph(nodes=["a", "b", "c"], edges=[("a", "b"), ("c", "b")])
        affected = g.affected_by("b")
        self.assertIn("a", affected)
        self.assertIn("c", affected)

    def test_affected_by_transitive(self) -> None:
        g = DepGraph(nodes=["a", "b", "c"], edges=[("a", "b"), ("b", "c")])
        affected = g.affected_by("c")
        self.assertIn("b", affected)
        self.assertIn("a", affected)

    def test_affected_by_no_dependents(self) -> None:
        g = DepGraph(nodes=["a", "b"], edges=[("a", "b")])
        affected = g.affected_by("a")
        self.assertEqual(affected, [])

    def test_affected_by_unknown_package(self) -> None:
        g = DepGraph(nodes=["a"], edges=[])
        affected = g.affected_by("nonexistent")
        self.assertEqual(affected, [])

    def test_affected_by_sorted(self) -> None:
        g = DepGraph(nodes=["a", "b", "c", "d"], edges=[("b", "a"), ("c", "a"), ("d", "a")])
        affected = g.affected_by("a")
        self.assertEqual(affected, sorted(affected))

    def test_render_empty(self) -> None:
        g = DepGraph()
        result = g.render()
        self.assertEqual(result, "(empty graph)")

    def test_render_single_node(self) -> None:
        g = DepGraph(nodes=["root"], edges=[])
        result = g.render()
        self.assertIn("root", result)

    def test_render_linear_chain(self) -> None:
        g = DepGraph(nodes=["a", "b", "c"], edges=[("a", "b"), ("b", "c")])
        result = g.render()
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)

    def test_render_cycle_label(self) -> None:
        g = DepGraph(nodes=["a", "b"], edges=[("a", "b"), ("b", "a")])
        result = g.render()
        self.assertIn("cycle", result)

    def test_render_returns_string(self) -> None:
        g = DepGraph(nodes=["x"], edges=[])
        self.assertIsInstance(g.render(), str)

    def test_normalise_cycle(self) -> None:
        result = DepGraph._normalise_cycle(["c", "a", "b"])
        self.assertEqual(result[0], "a")

    def test_normalise_cycle_empty(self) -> None:
        result = DepGraph._normalise_cycle([])
        self.assertEqual(result, [])


class TestCrossRepoDeps(unittest.TestCase):
    """Tests for CrossRepoDeps.build_graph."""

    def setUp(self) -> None:
        self.builder = CrossRepoDeps()

    def test_build_empty(self) -> None:
        g = self.builder.build_graph([])
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.edges, [])

    def test_build_no_deps(self) -> None:
        pkgs = [PackageInfo("a", "/a"), PackageInfo("b", "/b")]
        g = self.builder.build_graph(pkgs)
        self.assertEqual(sorted(g.nodes), ["a", "b"])
        self.assertEqual(g.edges, [])

    def test_build_with_internal_dep(self) -> None:
        pkgs = [
            PackageInfo("a", "/a", deps=["b"]),
            PackageInfo("b", "/b"),
        ]
        g = self.builder.build_graph(pkgs)
        self.assertIn(("a", "b"), g.edges)

    def test_build_ignores_external_deps(self) -> None:
        pkgs = [PackageInfo("a", "/a", deps=["react", "b"]), PackageInfo("b", "/b")]
        g = self.builder.build_graph(pkgs)
        self.assertNotIn(("a", "react"), g.edges)
        self.assertIn(("a", "b"), g.edges)

    def test_build_deduplicates_edges(self) -> None:
        pkgs = [
            PackageInfo("a", "/a", deps=["b", "b"]),
            PackageInfo("b", "/b"),
        ]
        g = self.builder.build_graph(pkgs)
        count = sum(1 for e in g.edges if e == ("a", "b"))
        self.assertEqual(count, 1)

    def test_build_nodes_sorted(self) -> None:
        pkgs = [PackageInfo("z", "/z"), PackageInfo("a", "/a"), PackageInfo("m", "/m")]
        g = self.builder.build_graph(pkgs)
        self.assertEqual(g.nodes, ["a", "m", "z"])


if __name__ == "__main__":
    unittest.main()
