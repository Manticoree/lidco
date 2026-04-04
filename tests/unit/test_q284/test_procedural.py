"""Tests for lidco.agent_memory.procedural."""
from __future__ import annotations

import unittest

from lidco.agent_memory.procedural import ProceduralMemory, Procedure


class TestProceduralMemory(unittest.TestCase):
    def setUp(self):
        self.mem = ProceduralMemory()

    def test_record_returns_procedure(self):
        proc = self.mem.record({
            "task_type": "refactor",
            "name": "extract method",
            "steps": ["identify code", "create function", "replace"],
        })
        self.assertIsInstance(proc, Procedure)
        self.assertEqual(proc.task_type, "refactor")
        self.assertEqual(proc.name, "extract method")
        self.assertEqual(len(proc.steps), 3)

    def test_record_with_preconditions(self):
        proc = self.mem.record({
            "task_type": "deploy",
            "name": "deploy app",
            "steps": ["build", "push"],
            "preconditions": ["tests pass", "branch is clean"],
        })
        self.assertEqual(proc.preconditions, ["tests pass", "branch is clean"])

    def test_record_missing_task_type_raises(self):
        with self.assertRaises(ValueError):
            self.mem.record({"name": "x", "steps": ["a"]})

    def test_record_missing_name_raises(self):
        with self.assertRaises(ValueError):
            self.mem.record({"task_type": "t", "steps": ["a"]})

    def test_record_missing_steps_raises(self):
        with self.assertRaises(ValueError):
            self.mem.record({"task_type": "t", "name": "n"})

    def test_find_by_task_type(self):
        self.mem.record({"task_type": "refactor", "name": "a", "steps": ["s"]})
        self.mem.record({"task_type": "bugfix", "name": "b", "steps": ["s"]})
        results = self.mem.find("refactor")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "a")

    def test_find_case_insensitive(self):
        self.mem.record({"task_type": "Refactor", "name": "a", "steps": ["s"]})
        self.assertEqual(len(self.mem.find("refactor")), 1)

    def test_update_success_rate(self):
        proc = self.mem.record({"task_type": "t", "name": "n", "steps": ["s"]})
        self.mem.update_success_rate(proc.id, True)
        self.mem.update_success_rate(proc.id, True)
        self.mem.update_success_rate(proc.id, False)
        updated = self.mem.all()[0]
        self.assertAlmostEqual(updated.success_rate, 2 / 3)

    def test_update_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            self.mem.update_success_rate("nonexistent", True)

    def test_generalize_returns_reliable(self):
        proc = self.mem.record({"task_type": "t", "name": "good", "steps": ["s"]})
        self.mem.update_success_rate(proc.id, True)
        self.mem.update_success_rate(proc.id, True)
        # 2 attempts, 100% success rate
        gen = self.mem.generalize()
        self.assertEqual(len(gen), 1)
        self.assertEqual(gen[0].name, "good")

    def test_generalize_excludes_low_rate(self):
        proc = self.mem.record({"task_type": "t", "name": "bad", "steps": ["s"]})
        self.mem.update_success_rate(proc.id, True)
        self.mem.update_success_rate(proc.id, False)
        self.mem.update_success_rate(proc.id, False)
        # 3 attempts, 33% rate
        self.assertEqual(len(self.mem.generalize()), 0)

    def test_generalize_excludes_few_attempts(self):
        proc = self.mem.record({"task_type": "t", "name": "new", "steps": ["s"]})
        self.mem.update_success_rate(proc.id, True)
        # Only 1 attempt
        self.assertEqual(len(self.mem.generalize()), 0)

    def test_success_rate_zero_when_no_attempts(self):
        proc = self.mem.record({"task_type": "t", "name": "n", "steps": ["s"]})
        self.assertAlmostEqual(proc.success_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
