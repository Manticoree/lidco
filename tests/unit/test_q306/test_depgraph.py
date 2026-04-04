"""Tests for DependencyGraphV2."""

import unittest

from lidco.monorepo.depgraph import DependencyGraphV2, Inconsistency


class TestDependencyGraphV2(unittest.TestCase):
    def _make_graph(self) -> DependencyGraphV2:
        g = DependencyGraphV2()
        g.add_package("core", [])
        g.add_package("utils", ["core"])
        g.add_package("web", ["utils", "core"])
        g.add_package("docs", [])
        return g

    # -- detect_circular ----------------------------------------------

    def test_no_cycles(self):
        g = self._make_graph()
        self.assertEqual(g.detect_circular(), [])

    def test_detects_cycle(self):
        g = DependencyGraphV2()
        g.add_package("a", ["b"])
        g.add_package("b", ["a"])
        cycles = g.detect_circular()
        self.assertTrue(len(cycles) > 0)

    def test_self_cycle(self):
        g = DependencyGraphV2()
        g.add_package("x", ["x"])
        cycles = g.detect_circular()
        self.assertTrue(len(cycles) > 0)

    # -- version_consistency ------------------------------------------

    def test_consistent_versions(self):
        g = DependencyGraphV2()
        g.add_package("a", ["lodash"], dep_versions={"lodash": "^4.17.0"})
        g.add_package("b", ["lodash"], dep_versions={"lodash": "^4.17.0"})
        self.assertEqual(g.version_consistency(), [])

    def test_inconsistent_versions(self):
        g = DependencyGraphV2()
        g.add_package("a", ["lodash"], dep_versions={"lodash": "^4.17.0"})
        g.add_package("b", ["lodash"], dep_versions={"lodash": "^3.10.0"})
        issues = g.version_consistency()
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].dependency, "lodash")
        self.assertIn("a", issues[0].versions)
        self.assertIn("b", issues[0].versions)

    # -- unused_deps --------------------------------------------------

    def test_unused_deps_found(self):
        g = DependencyGraphV2()
        g.add_package("app", ["core", "utils", "lodash"], used_deps=["core"])
        unused = g.unused_deps("app")
        self.assertIn("lodash", unused)
        self.assertIn("utils", unused)
        self.assertNotIn("core", unused)

    def test_unused_deps_none_tracked(self):
        g = DependencyGraphV2()
        g.add_package("app", ["core"])
        self.assertEqual(g.unused_deps("app"), [])

    def test_unused_deps_all_used(self):
        g = DependencyGraphV2()
        g.add_package("app", ["core"], used_deps=["core"])
        self.assertEqual(g.unused_deps("app"), [])

    # -- as_mermaid ---------------------------------------------------

    def test_mermaid_output(self):
        g = self._make_graph()
        mermaid = g.as_mermaid()
        self.assertIn("graph TD", mermaid)
        self.assertIn("web --> utils", mermaid)
        self.assertIn("web --> core", mermaid)

    def test_mermaid_empty(self):
        g = DependencyGraphV2()
        mermaid = g.as_mermaid()
        self.assertIn("(empty)", mermaid)

    # -- topological_order --------------------------------------------

    def test_topo_order(self):
        g = self._make_graph()
        order = g.topological_order()
        self.assertLess(order.index("core"), order.index("utils"))
        self.assertLess(order.index("utils"), order.index("web"))

    def test_topo_order_with_cycle(self):
        g = DependencyGraphV2()
        g.add_package("a", ["b"])
        g.add_package("b", ["a"])
        order = g.topological_order()
        self.assertEqual(sorted(order), ["a", "b"])

    # -- add_package --------------------------------------------------

    def test_add_package_basic(self):
        g = DependencyGraphV2()
        g.add_package("pkg", ["dep1", "dep2"])
        order = g.topological_order()
        self.assertIn("pkg", order)

    # -- Inconsistency dataclass --------------------------------------

    def test_inconsistency_dataclass(self):
        i = Inconsistency(dependency="react", versions={"a": "^18.0", "b": "^17.0"})
        self.assertEqual(i.dependency, "react")
        self.assertEqual(len(i.versions), 2)


if __name__ == "__main__":
    unittest.main()
