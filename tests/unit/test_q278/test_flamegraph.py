"""Tests for lidco.profiler.flamegraph."""
from __future__ import annotations

import json
import unittest

from lidco.profiler.flamegraph import FlameGraphGenerator, FlameNode
from lidco.profiler.runner import ProfileResult, ProfileRunner


class TestFlameNode(unittest.TestCase):
    def test_defaults(self):
        n = FlameNode(name="root")
        self.assertEqual(n.name, "root")
        self.assertEqual(n.value, 0.0)
        self.assertEqual(n.children, [])
        self.assertEqual(n.self_time, 0.0)


class TestFlameGraphGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = FlameGraphGenerator()
        self.runner = ProfileRunner()

    def test_from_profile(self):
        result = self.runner.profile("a = 1\nb = 2")
        root = self.gen.from_profile(result)
        self.assertEqual(root.name, result.name)
        self.assertEqual(len(root.children), 2)

    def test_add_node(self):
        root = FlameNode(name="root", value=10.0)
        child = self.gen.add_node(root, "child", 3.0)
        self.assertEqual(child.name, "child")
        self.assertEqual(len(root.children), 1)

    def test_flatten(self):
        root = FlameNode(name="root", value=10.0)
        self.gen.add_node(root, "child1", 3.0)
        self.gen.add_node(root, "child2", 5.0)
        flat = self.gen.flatten(root)
        self.assertEqual(len(flat), 3)
        self.assertEqual(flat[0]["depth"], 0)
        self.assertEqual(flat[1]["depth"], 1)

    def test_search(self):
        root = FlameNode(name="root")
        self.gen.add_node(root, "foo_bar", 1.0)
        self.gen.add_node(root, "baz_qux", 2.0)
        matches = self.gen.search(root, "foo")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].name, "foo_bar")

    def test_search_case_insensitive(self):
        root = FlameNode(name="ROOT_NODE")
        matches = self.gen.search(root, "root")
        self.assertEqual(len(matches), 1)

    def test_filter_threshold(self):
        root = FlameNode(name="root", value=10.0)
        self.gen.add_node(root, "big", 5.0)
        self.gen.add_node(root, "small", 0.1)
        filtered = self.gen.filter_threshold(root, 1.0)
        self.assertEqual(len(filtered.children), 1)
        self.assertEqual(filtered.children[0].name, "big")

    def test_render_text(self):
        root = FlameNode(name="root", value=10.0)
        self.gen.add_node(root, "child", 3.0)
        text = self.gen.render_text(root)
        self.assertIn("root", text)
        self.assertIn("child", text)

    def test_export_json(self):
        root = FlameNode(name="root", value=5.0)
        self.gen.add_node(root, "c", 2.0)
        data = json.loads(self.gen.export_json(root))
        self.assertEqual(data["name"], "root")
        self.assertEqual(len(data["children"]), 1)

    def test_summary(self):
        result = self.runner.profile("x = 1")
        self.gen.from_profile(result)
        s = self.gen.summary()
        self.assertEqual(s["generated"], 1)


if __name__ == "__main__":
    unittest.main()
