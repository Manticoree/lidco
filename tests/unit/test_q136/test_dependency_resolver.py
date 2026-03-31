"""Tests for TaskDependencyResolver."""
from __future__ import annotations

import unittest
from lidco.scheduling.dependency_resolver import (
    DependencyNode,
    DependencyResolver,
    ResolutionResult,
)


class TestDependencyNode(unittest.TestCase):
    def test_defaults(self):
        n = DependencyNode(task_id="a")
        self.assertEqual(n.task_id, "a")
        self.assertEqual(n.depends_on, [])

    def test_with_deps(self):
        n = DependencyNode(task_id="b", depends_on=["a"])
        self.assertEqual(n.depends_on, ["a"])


class TestResolutionResult(unittest.TestCase):
    def test_no_cycle(self):
        r = ResolutionResult(order=["a", "b"], has_cycle=False)
        self.assertFalse(r.has_cycle)
        self.assertIsNone(r.cycle_path)

    def test_with_cycle(self):
        r = ResolutionResult(order=[], has_cycle=True, cycle_path=["a", "b", "a"])
        self.assertTrue(r.has_cycle)
        self.assertEqual(len(r.cycle_path), 3)


class TestDependencyResolver(unittest.TestCase):
    def setUp(self):
        self.dr = DependencyResolver()

    def test_add_single_task(self):
        self.dr.add_task("a")
        result = self.dr.resolve()
        self.assertEqual(result.order, ["a"])
        self.assertFalse(result.has_cycle)

    def test_linear_chain(self):
        self.dr.add_task("a")
        self.dr.add_task("b", depends_on=["a"])
        self.dr.add_task("c", depends_on=["b"])
        result = self.dr.resolve()
        self.assertEqual(result.order, ["a", "b", "c"])

    def test_diamond_dependency(self):
        self.dr.add_task("a")
        self.dr.add_task("b", depends_on=["a"])
        self.dr.add_task("c", depends_on=["a"])
        self.dr.add_task("d", depends_on=["b", "c"])
        result = self.dr.resolve()
        self.assertFalse(result.has_cycle)
        self.assertEqual(result.order.index("a"), 0)
        self.assertGreater(result.order.index("d"), result.order.index("b"))
        self.assertGreater(result.order.index("d"), result.order.index("c"))

    def test_simple_cycle(self):
        self.dr.add_task("a", depends_on=["b"])
        self.dr.add_task("b", depends_on=["a"])
        result = self.dr.resolve()
        self.assertTrue(result.has_cycle)
        self.assertIsNotNone(result.cycle_path)

    def test_three_node_cycle(self):
        self.dr.add_task("a", depends_on=["c"])
        self.dr.add_task("b", depends_on=["a"])
        self.dr.add_task("c", depends_on=["b"])
        self.assertTrue(self.dr.has_cycle())

    def test_no_cycle_parallel(self):
        self.dr.add_task("a")
        self.dr.add_task("b")
        self.dr.add_task("c")
        result = self.dr.resolve()
        self.assertFalse(result.has_cycle)
        self.assertEqual(len(result.order), 3)

    def test_has_cycle_false(self):
        self.dr.add_task("a")
        self.dr.add_task("b", depends_on=["a"])
        self.assertFalse(self.dr.has_cycle())

    def test_get_ready_no_deps(self):
        self.dr.add_task("a")
        self.dr.add_task("b")
        ready = self.dr.get_ready()
        self.assertIn("a", ready)
        self.assertIn("b", ready)

    def test_get_ready_with_deps(self):
        self.dr.add_task("a")
        self.dr.add_task("b", depends_on=["a"])
        ready = self.dr.get_ready()
        self.assertEqual(ready, ["a"])

    def test_mark_done_unlocks_dependents(self):
        self.dr.add_task("a")
        self.dr.add_task("b", depends_on=["a"])
        self.dr.mark_done("a")
        ready = self.dr.get_ready()
        self.assertIn("b", ready)

    def test_mark_done_excludes_done_tasks(self):
        self.dr.add_task("a")
        self.dr.mark_done("a")
        ready = self.dr.get_ready()
        self.assertNotIn("a", ready)

    def test_get_ready_partial_deps(self):
        self.dr.add_task("a")
        self.dr.add_task("b")
        self.dr.add_task("c", depends_on=["a", "b"])
        self.dr.mark_done("a")
        ready = self.dr.get_ready()
        self.assertIn("b", ready)
        self.assertNotIn("c", ready)  # b not done yet

    def test_get_ready_all_deps_satisfied(self):
        self.dr.add_task("a")
        self.dr.add_task("b")
        self.dr.add_task("c", depends_on=["a", "b"])
        self.dr.mark_done("a")
        self.dr.mark_done("b")
        ready = self.dr.get_ready()
        self.assertIn("c", ready)

    def test_external_dep_treated_as_satisfied(self):
        # dependency on a task not in the graph is ignored (treated as satisfied)
        self.dr.add_task("b", depends_on=["external"])
        ready = self.dr.get_ready()
        self.assertIn("b", ready)

    def test_resolve_empty(self):
        result = self.dr.resolve()
        self.assertEqual(result.order, [])
        self.assertFalse(result.has_cycle)

    def test_overwrite_task(self):
        self.dr.add_task("a")
        self.dr.add_task("a", depends_on=["b"])
        self.dr.add_task("b")
        result = self.dr.resolve()
        self.assertFalse(result.has_cycle)
        self.assertGreater(result.order.index("a"), result.order.index("b"))

    def test_self_cycle(self):
        self.dr.add_task("a", depends_on=["a"])
        self.assertTrue(self.dr.has_cycle())

    def test_incremental_workflow(self):
        self.dr.add_task("a")
        self.dr.add_task("b", depends_on=["a"])
        self.dr.add_task("c", depends_on=["b"])
        # step 1
        ready = self.dr.get_ready()
        self.assertEqual(ready, ["a"])
        self.dr.mark_done("a")
        # step 2
        ready = self.dr.get_ready()
        self.assertEqual(ready, ["b"])
        self.dr.mark_done("b")
        # step 3
        ready = self.dr.get_ready()
        self.assertEqual(ready, ["c"])

    def test_resolve_result_cycle_path_nonempty(self):
        self.dr.add_task("x", depends_on=["y"])
        self.dr.add_task("y", depends_on=["x"])
        result = self.dr.resolve()
        self.assertTrue(result.has_cycle)
        self.assertTrue(len(result.cycle_path) >= 2)


if __name__ == "__main__":
    unittest.main()
