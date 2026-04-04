"""Tests for ToolPlanner."""
from __future__ import annotations

import unittest

from lidco.tool_opt.planner import OptimizedPlan, PlannedCall, ToolPlanner


class TestPlannedCall(unittest.TestCase):
    def test_defaults(self):
        c = PlannedCall(tool="Read")
        self.assertEqual(c.tool, "Read")
        self.assertEqual(c.args, {})
        self.assertEqual(c.depends_on, [])


class TestToolPlanner(unittest.TestCase):
    def setUp(self):
        self.p = ToolPlanner()

    def test_add_call(self):
        idx = self.p.add_call("Read", {"path": "a.py"})
        self.assertEqual(idx, 0)
        self.assertEqual(len(self.p.calls), 1)

    def test_add_call_with_deps(self):
        self.p.add_call("Read")
        idx = self.p.add_call("Edit", depends_on=[0])
        self.assertEqual(idx, 1)
        self.assertEqual(self.p.calls[1].depends_on, [0])

    def test_plan_empty(self):
        self.assertEqual(self.p.plan(), [])

    def test_plan_topo_order(self):
        self.p.add_call("Read")        # 0
        self.p.add_call("Edit", depends_on=[0])  # 1
        self.p.add_call("Bash", depends_on=[1])  # 2
        ordered = self.p.plan()
        names = [c.tool for c in ordered]
        self.assertEqual(names, ["Read", "Edit", "Bash"])

    def test_plan_diamond_deps(self):
        self.p.add_call("Read")        # 0
        self.p.add_call("Grep")        # 1
        self.p.add_call("Edit", depends_on=[0, 1])  # 2
        ordered = self.p.plan()
        # Edit must come after both Read and Grep
        idx_of = {c.tool: i for i, c in enumerate(ordered)}
        self.assertLess(idx_of["Read"], idx_of["Edit"])
        self.assertLess(idx_of["Grep"], idx_of["Edit"])

    def test_batch_reads(self):
        self.p.add_call("Read")
        self.p.add_call("Read")
        self.p.add_call("Edit")
        self.p.add_call("Glob")
        batches = self.p.batch_reads()
        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0]), 2)
        self.assertEqual(len(batches[1]), 1)

    def test_batch_reads_empty(self):
        self.p.add_call("Edit")
        self.assertEqual(self.p.batch_reads(), [])

    def test_parallelizable_independent(self):
        self.p.add_call("Read")
        self.p.add_call("Grep")
        self.p.add_call("Glob")
        groups = self.p.parallelizable()
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_parallelizable_chain(self):
        self.p.add_call("Read")                    # 0
        self.p.add_call("Edit", depends_on=[0])    # 1
        self.p.add_call("Bash", depends_on=[1])    # 2
        groups = self.p.parallelizable()
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(groups[0]), 1)

    def test_optimize_returns_plan(self):
        self.p.add_call("Read")
        self.p.add_call("Edit", depends_on=[0])
        result = self.p.optimize()
        self.assertIsInstance(result, OptimizedPlan)
        self.assertEqual(len(result.ordered), 2)
        self.assertIsInstance(result.parallel_groups, list)
        self.assertIsInstance(result.batched_reads, list)


if __name__ == "__main__":
    unittest.main()
