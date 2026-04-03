"""Tests for DepGraphBuilder (Q255)."""
from __future__ import annotations

import unittest

from lidco.depgraph.builder import DepEdge, DepGraphBuilder, DepNode


class TestDepNode(unittest.TestCase):
    def test_frozen(self):
        node = DepNode(name="requests")
        with self.assertRaises(AttributeError):
            node.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        node = DepNode(name="foo")
        self.assertEqual(node.version, "")
        self.assertTrue(node.direct)
        self.assertEqual(node.platform, "any")

    def test_fields(self):
        node = DepNode(name="bar", version="1.2.3", direct=False, platform="linux")
        self.assertEqual(node.name, "bar")
        self.assertEqual(node.version, "1.2.3")
        self.assertFalse(node.direct)
        self.assertEqual(node.platform, "linux")


class TestDepEdge(unittest.TestCase):
    def test_frozen(self):
        edge = DepEdge(source="a", target="b")
        with self.assertRaises(AttributeError):
            edge.source = "c"  # type: ignore[misc]

    def test_defaults(self):
        edge = DepEdge(source="a", target="b")
        self.assertEqual(edge.version_constraint, "")


class TestDepGraphBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = DepGraphBuilder()

    def test_add_node_and_all_nodes(self):
        self.builder.add_node(DepNode(name="a", version="1.0"))
        self.builder.add_node(DepNode(name="b", version="2.0", direct=False))
        nodes = self.builder.all_nodes()
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].name, "a")
        self.assertEqual(nodes[1].name, "b")

    def test_add_node_overwrites_same_name(self):
        self.builder.add_node(DepNode(name="a", version="1.0"))
        self.builder.add_node(DepNode(name="a", version="2.0"))
        nodes = self.builder.all_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].version, "2.0")

    def test_add_edge_and_all_edges(self):
        self.builder.add_edge(DepEdge(source="a", target="b"))
        self.builder.add_edge(DepEdge(source="b", target="c", version_constraint=">=1.0"))
        edges = self.builder.all_edges()
        self.assertEqual(len(edges), 2)
        self.assertEqual(edges[1].version_constraint, ">=1.0")

    def test_direct_deps(self):
        self.builder.add_node(DepNode(name="d1", direct=True))
        self.builder.add_node(DepNode(name="t1", direct=False))
        self.builder.add_node(DepNode(name="d2", direct=True))
        direct = self.builder.direct_deps()
        self.assertEqual(len(direct), 2)
        self.assertTrue(all(n.direct for n in direct))

    def test_transitive_deps(self):
        self.builder.add_node(DepNode(name="d1", direct=True))
        self.builder.add_node(DepNode(name="t1", direct=False))
        trans = self.builder.transitive_deps()
        self.assertEqual(len(trans), 1)
        self.assertEqual(trans[0].name, "t1")

    def test_to_dict_structure(self):
        self.builder.add_node(DepNode(name="x", version="1.0"))
        self.builder.add_edge(DepEdge(source="x", target="y"))
        d = self.builder.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("edges", d)
        self.assertEqual(len(d["nodes"]), 1)
        self.assertEqual(len(d["edges"]), 1)
        self.assertEqual(d["nodes"][0]["name"], "x")
        self.assertEqual(d["edges"][0]["source"], "x")

    def test_to_dict_node_fields(self):
        self.builder.add_node(DepNode(name="p", version="3.0", direct=False, platform="win"))
        node_d = self.builder.to_dict()["nodes"][0]
        self.assertEqual(node_d["name"], "p")
        self.assertEqual(node_d["version"], "3.0")
        self.assertFalse(node_d["direct"])
        self.assertEqual(node_d["platform"], "win")

    def test_empty_graph(self):
        self.assertEqual(self.builder.all_nodes(), [])
        self.assertEqual(self.builder.all_edges(), [])
        self.assertEqual(self.builder.direct_deps(), [])
        self.assertEqual(self.builder.transitive_deps(), [])
        d = self.builder.to_dict()
        self.assertEqual(d["nodes"], [])
        self.assertEqual(d["edges"], [])


if __name__ == "__main__":
    unittest.main()
