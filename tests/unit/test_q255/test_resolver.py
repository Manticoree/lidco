"""Tests for VersionResolver (Q255)."""
from __future__ import annotations

import unittest

from lidco.depgraph.builder import DepEdge, DepGraphBuilder, DepNode
from lidco.depgraph.resolver import VersionResolver


class TestFindConflicts(unittest.TestCase):
    def test_no_conflicts(self):
        b = DepGraphBuilder()
        b.add_node(DepNode(name="a"))
        b.add_edge(DepEdge(source="root", target="a", version_constraint=">=1.0"))
        resolver = VersionResolver(b)
        self.assertEqual(resolver.find_conflicts(), [])

    def test_single_conflict(self):
        b = DepGraphBuilder()
        b.add_node(DepNode(name="a"))
        b.add_edge(DepEdge(source="x", target="a", version_constraint=">=1.0"))
        b.add_edge(DepEdge(source="y", target="a", version_constraint=">=2.0"))
        resolver = VersionResolver(b)
        conflicts = resolver.find_conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["name"], "a")
        self.assertIn(">=1.0", conflicts[0]["constraints"])
        self.assertIn(">=2.0", conflicts[0]["constraints"])

    def test_same_constraint_no_conflict(self):
        b = DepGraphBuilder()
        b.add_edge(DepEdge(source="x", target="a", version_constraint=">=1.0"))
        b.add_edge(DepEdge(source="y", target="a", version_constraint=">=1.0"))
        resolver = VersionResolver(b)
        self.assertEqual(resolver.find_conflicts(), [])

    def test_edges_without_constraints_ignored(self):
        b = DepGraphBuilder()
        b.add_edge(DepEdge(source="x", target="a"))
        b.add_edge(DepEdge(source="y", target="a"))
        resolver = VersionResolver(b)
        self.assertEqual(resolver.find_conflicts(), [])


class TestFindDiamond(unittest.TestCase):
    def test_no_diamond(self):
        b = DepGraphBuilder()
        b.add_edge(DepEdge(source="root", target="a"))
        b.add_edge(DepEdge(source="root", target="b"))
        resolver = VersionResolver(b)
        self.assertEqual(resolver.find_diamond(), [])

    def test_diamond_detected(self):
        b = DepGraphBuilder()
        # root -> a -> c, root -> b -> c
        b.add_edge(DepEdge(source="root", target="a"))
        b.add_edge(DepEdge(source="root", target="b"))
        b.add_edge(DepEdge(source="a", target="c"))
        b.add_edge(DepEdge(source="b", target="c"))
        resolver = VersionResolver(b)
        diamonds = resolver.find_diamond()
        self.assertEqual(len(diamonds), 1)
        self.assertEqual(diamonds[0]["top"], "root")
        self.assertEqual(diamonds[0]["bottom"], "c")
        self.assertIn("a", diamonds[0]["middle"])
        self.assertIn("b", diamonds[0]["middle"])


class TestSuggestUpgrades(unittest.TestCase):
    def test_suggests_patch_bump(self):
        b = DepGraphBuilder()
        b.add_node(DepNode(name="foo", version="1.2.3"))
        resolver = VersionResolver(b)
        suggestions = resolver.suggest_upgrades()
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["suggested"], "1.2.4")

    def test_no_version_skipped(self):
        b = DepGraphBuilder()
        b.add_node(DepNode(name="bar"))
        resolver = VersionResolver(b)
        self.assertEqual(resolver.suggest_upgrades(), [])

    def test_two_part_version(self):
        b = DepGraphBuilder()
        b.add_node(DepNode(name="pkg", version="2.5"))
        resolver = VersionResolver(b)
        suggestions = resolver.suggest_upgrades()
        self.assertEqual(suggestions[0]["suggested"], "2.5.1")

    def test_single_part_version(self):
        b = DepGraphBuilder()
        b.add_node(DepNode(name="pkg", version="3"))
        resolver = VersionResolver(b)
        suggestions = resolver.suggest_upgrades()
        self.assertEqual(suggestions[0]["suggested"], "3.0.1")


class TestResolve(unittest.TestCase):
    def test_latest_wins(self):
        b = DepGraphBuilder()
        resolver = VersionResolver(b)
        result = resolver.resolve([
            {"name": "a", "version": "1.0.0"},
            {"name": "a", "version": "2.0.0"},
        ])
        self.assertEqual(result["a"], "2.0.0")

    def test_keeps_higher(self):
        b = DepGraphBuilder()
        resolver = VersionResolver(b)
        result = resolver.resolve([
            {"name": "a", "version": "3.0.0"},
            {"name": "a", "version": "1.0.0"},
        ])
        self.assertEqual(result["a"], "3.0.0")

    def test_multiple_packages(self):
        b = DepGraphBuilder()
        resolver = VersionResolver(b)
        result = resolver.resolve([
            {"name": "a", "version": "1.0"},
            {"name": "b", "version": "2.0"},
        ])
        self.assertEqual(result["a"], "1.0")
        self.assertEqual(result["b"], "2.0")

    def test_empty(self):
        b = DepGraphBuilder()
        resolver = VersionResolver(b)
        self.assertEqual(resolver.resolve([]), {})


if __name__ == "__main__":
    unittest.main()
