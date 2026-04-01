"""Tests for test_intel.mutation_runner — MutationType, Mutant, MutationRunner."""
from __future__ import annotations

import unittest

from lidco.test_intel.mutation_runner import Mutant, MutationRunner, MutationType


class TestMutationType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(MutationType.NEGATE_CONDITION, "NEGATE_CONDITION")
        self.assertEqual(MutationType.SWAP_OPERATOR, "SWAP_OPERATOR")
        self.assertEqual(MutationType.DELETE_STATEMENT, "DELETE_STATEMENT")
        self.assertEqual(MutationType.CHANGE_CONSTANT, "CHANGE_CONSTANT")
        self.assertEqual(MutationType.BOUNDARY_CHANGE, "BOUNDARY_CHANGE")


class TestMutant(unittest.TestCase):
    def test_frozen(self):
        m = Mutant(id="a", type=MutationType.SWAP_OPERATOR)
        with self.assertRaises(AttributeError):
            m.id = "b"  # type: ignore[misc]

    def test_defaults(self):
        m = Mutant(id="a", type=MutationType.NEGATE_CONDITION)
        self.assertEqual(m.file, "")
        self.assertEqual(m.line, 0)
        self.assertEqual(m.original, "")
        self.assertEqual(m.mutated, "")
        self.assertFalse(m.killed)

    def test_fields(self):
        m = Mutant(
            id="m1", type=MutationType.CHANGE_CONSTANT,
            file="f.py", line=10, original="x = 0", mutated="x = 1", killed=True,
        )
        self.assertEqual(m.id, "m1")
        self.assertEqual(m.type, MutationType.CHANGE_CONSTANT)
        self.assertEqual(m.file, "f.py")
        self.assertTrue(m.killed)


class TestMutationRunner(unittest.TestCase):
    def test_generate_mutants_basic(self):
        src = "def foo(x):\n    if x > 0:\n        return x + 1\n    return 0\n"
        runner = MutationRunner()
        mutants = runner.generate_mutants(src, "foo.py")
        self.assertGreater(len(mutants), 0)
        self.assertTrue(all(isinstance(m, Mutant) for m in mutants))

    def test_negate_conditions(self):
        src = "if x > 0:\n    pass\n"
        runner = MutationRunner()
        results = runner._negate_conditions(src)
        self.assertGreater(len(results), 0)
        self.assertIn("not", results[0][2])

    def test_swap_operators(self):
        src = "y = a + b\n"
        runner = MutationRunner()
        results = runner._swap_operators(src)
        self.assertGreater(len(results), 0)
        self.assertIn("-", results[0][2])

    def test_mark_killed(self):
        runner = MutationRunner()
        runner.mark_killed("m1")
        self.assertIn("m1", runner._killed)

    def test_mutation_score_all_killed(self):
        runner = MutationRunner()
        mutants = [
            Mutant(id="a", type=MutationType.SWAP_OPERATOR, killed=True),
            Mutant(id="b", type=MutationType.SWAP_OPERATOR, killed=True),
        ]
        self.assertEqual(runner.mutation_score(mutants), 1.0)

    def test_mutation_score_none_killed(self):
        runner = MutationRunner()
        mutants = [
            Mutant(id="a", type=MutationType.SWAP_OPERATOR),
            Mutant(id="b", type=MutationType.SWAP_OPERATOR),
        ]
        self.assertEqual(runner.mutation_score(mutants), 0.0)

    def test_mutation_score_empty(self):
        runner = MutationRunner()
        self.assertEqual(runner.mutation_score([]), 1.0)

    def test_mutation_score_partial(self):
        runner = MutationRunner()
        m1 = Mutant(id="a", type=MutationType.SWAP_OPERATOR)
        m2 = Mutant(id="b", type=MutationType.SWAP_OPERATOR)
        runner.mark_killed("a")
        self.assertAlmostEqual(runner.mutation_score([m1, m2]), 0.5)

    def test_survival_report_all_killed(self):
        runner = MutationRunner()
        mutants = [Mutant(id="a", type=MutationType.SWAP_OPERATOR, killed=True)]
        report = runner.survival_report(mutants)
        self.assertIn("All mutants killed", report)

    def test_survival_report_surviving(self):
        runner = MutationRunner()
        mutants = [Mutant(id="a", type=MutationType.SWAP_OPERATOR, original="x+y", mutated="x-y")]
        report = runner.survival_report(mutants)
        self.assertIn("Surviving mutants", report)
        self.assertIn("SWAP_OPERATOR", report)

    def test_generate_empty_source(self):
        runner = MutationRunner()
        mutants = runner.generate_mutants("")
        self.assertEqual(mutants, [])


if __name__ == "__main__":
    unittest.main()
