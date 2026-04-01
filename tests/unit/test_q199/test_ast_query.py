"""Tests for lidco.query.ast_query (Q199)."""
from __future__ import annotations

import unittest

from lidco.query.ast_query import ASTNode, ASTPattern, ASTQueryEngine, ASTQueryError


def _tree() -> ASTNode:
    """Build a small AST for testing."""
    leaf1 = ASTNode(type="variable", name="x", line=3)
    leaf2 = ASTNode(type="variable", name="y", line=4)
    func = ASTNode(type="function", name="foo", children=[leaf1, leaf2], line=1)
    cls_method = ASTNode(type="function", name="bar_method", line=10)
    cls = ASTNode(type="class", name="MyClass", children=[cls_method], line=8)
    root = ASTNode(type="module", name="mod", children=[func, cls], line=0)
    return root


class TestASTQueryEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ASTQueryEngine()
        self.root = _tree()

    def test_find_by_pattern_type(self):
        pattern = ASTPattern(node_type="function")
        results = self.engine.find(self.root, pattern)
        self.assertEqual(len(results), 2)
        names = {n.name for n in results}
        self.assertEqual(names, {"foo", "bar_method"})

    def test_find_by_type(self):
        results = self.engine.find_by_type(self.root, "class")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "MyClass")

    def test_find_by_name_regex(self):
        results = self.engine.find_by_name(self.root, "bar.*")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "bar_method")

    def test_find_by_name_exact(self):
        results = self.engine.find_by_name(self.root, "x")
        self.assertEqual(len(results), 1)

    def test_ancestors(self):
        # find the leaf "x"
        target = self.root.children[0].children[0]  # func -> leaf1
        path = self.engine.ancestors(self.root, target)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0].name, "mod")
        self.assertEqual(path[1].name, "foo")
        self.assertEqual(path[2].name, "x")

    def test_ancestors_not_found(self):
        orphan = ASTNode(type="orphan", name="z")
        path = self.engine.ancestors(self.root, orphan)
        self.assertEqual(path, [])

    def test_depth(self):
        d = self.engine.depth(self.root)
        self.assertEqual(d, 3)  # module -> function -> variable

    def test_depth_single_node(self):
        single = ASTNode(type="leaf", name="alone")
        self.assertEqual(self.engine.depth(single), 1)

    def test_no_match(self):
        pattern = ASTPattern(node_type="nonexistent")
        results = self.engine.find(self.root, pattern)
        self.assertEqual(results, [])

    def test_pattern_has_children(self):
        pattern = ASTPattern(has_children=True)
        results = self.engine.find(self.root, pattern)
        names = {n.name for n in results}
        self.assertIn("mod", names)
        self.assertIn("foo", names)
        self.assertIn("MyClass", names)

    def test_pattern_min_children(self):
        pattern = ASTPattern(min_children=2)
        results = self.engine.find(self.root, pattern)
        names = {n.name for n in results}
        self.assertIn("mod", names)
        self.assertIn("foo", names)
        self.assertNotIn("MyClass", names)  # only 1 child


if __name__ == "__main__":
    unittest.main()
