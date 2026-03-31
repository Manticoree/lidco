"""Tests for lidco.testing.mutation_runner — Task 977."""

import unittest

from lidco.testing.mutation_runner import (
    Mutation,
    MutationConfig,
    MutationReport,
    MutationRunner,
)


class TestMutationConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = MutationConfig()
        self.assertEqual(cfg.max_mutants, 50)
        self.assertEqual(cfg.timeout_per_mutant, 30.0)
        self.assertEqual(cfg.test_command, "python -m pytest -x -q")
        self.assertIn("boundary", cfg.mutation_types)
        self.assertIn("negate", cfg.mutation_types)
        self.assertIn("arithmetic", cfg.mutation_types)
        self.assertIn("comparison", cfg.mutation_types)

    def test_custom_config(self):
        cfg = MutationConfig(max_mutants=10, timeout_per_mutant=5.0, mutation_types=["boundary"])
        self.assertEqual(cfg.max_mutants, 10)
        self.assertEqual(cfg.timeout_per_mutant, 5.0)
        self.assertEqual(cfg.mutation_types, ["boundary"])


class TestMutationRunner(unittest.TestCase):
    def setUp(self):
        self.runner = MutationRunner()

    def test_config_property(self):
        self.assertIsInstance(self.runner.config, MutationConfig)

    def test_generate_mutations_boundary(self):
        source = "if x < 10:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        boundary_muts = [m for m in muts if m.mutation_type == "boundary"]
        self.assertTrue(len(boundary_muts) > 0)
        self.assertIn("<=", boundary_muts[0].mutated)

    def test_generate_mutations_negate_true(self):
        source = "flag = True"
        muts = self.runner.generate_mutations("test.py", source)
        negate_muts = [m for m in muts if m.mutation_type == "negate"]
        self.assertTrue(len(negate_muts) > 0)
        self.assertIn("False", negate_muts[0].mutated)

    def test_generate_mutations_negate_false(self):
        source = "flag = False"
        muts = self.runner.generate_mutations("test.py", source)
        negate_muts = [m for m in muts if m.mutation_type == "negate"]
        self.assertTrue(len(negate_muts) > 0)
        self.assertIn("True", negate_muts[0].mutated)

    def test_generate_mutations_negate_not(self):
        source = "if not valid:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        negate_muts = [m for m in muts if m.mutation_type == "negate"]
        self.assertTrue(len(negate_muts) > 0)
        # "not " should be removed
        self.assertNotIn("not ", negate_muts[0].mutated)

    def test_generate_mutations_arithmetic_plus(self):
        source = "result = a + b"
        muts = self.runner.generate_mutations("test.py", source)
        arith = [m for m in muts if m.mutation_type == "arithmetic"]
        self.assertTrue(len(arith) > 0)
        self.assertIn(" - ", arith[0].mutated)

    def test_generate_mutations_arithmetic_minus(self):
        source = "result = a - b"
        muts = self.runner.generate_mutations("test.py", source)
        arith = [m for m in muts if m.mutation_type == "arithmetic"]
        self.assertTrue(len(arith) > 0)
        self.assertIn(" + ", arith[0].mutated)

    def test_generate_mutations_arithmetic_multiply(self):
        source = "result = a * b"
        muts = self.runner.generate_mutations("test.py", source)
        arith = [m for m in muts if m.mutation_type == "arithmetic"]
        self.assertTrue(len(arith) > 0)
        self.assertIn(" / ", arith[0].mutated)

    def test_generate_mutations_arithmetic_divide(self):
        source = "result = a / b"
        muts = self.runner.generate_mutations("test.py", source)
        arith = [m for m in muts if m.mutation_type == "arithmetic"]
        self.assertTrue(len(arith) > 0)
        self.assertIn(" * ", arith[0].mutated)

    def test_generate_mutations_comparison_eq(self):
        source = "if x == y:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        comp = [m for m in muts if m.mutation_type == "comparison"]
        self.assertTrue(len(comp) > 0)
        self.assertIn(" != ", comp[0].mutated)

    def test_generate_mutations_comparison_neq(self):
        source = "if x != y:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        comp = [m for m in muts if m.mutation_type == "comparison"]
        self.assertTrue(len(comp) > 0)
        self.assertIn(" == ", comp[0].mutated)

    def test_generate_mutations_skips_comments(self):
        source = "# this is a comment with x < 10"
        muts = self.runner.generate_mutations("test.py", source)
        self.assertEqual(len(muts), 0)

    def test_generate_mutations_skips_empty_lines(self):
        source = "\n\n\n"
        muts = self.runner.generate_mutations("test.py", source)
        self.assertEqual(len(muts), 0)

    def test_generate_mutations_skips_docstrings(self):
        source = '"""This has x < 10"""'
        muts = self.runner.generate_mutations("test.py", source)
        self.assertEqual(len(muts), 0)

    def test_generate_mutations_respects_max_mutants(self):
        cfg = MutationConfig(max_mutants=2, mutation_types=["comparison"])
        runner = MutationRunner(config=cfg)
        source = "\n".join(f"if a{i} == b{i}:" for i in range(20))
        muts = runner.generate_mutations("test.py", source)
        self.assertEqual(len(muts), 2)

    def test_run_mutation_returns_mutation(self):
        source = "if x == y:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        self.assertTrue(len(muts) > 0)
        result = self.runner.run_mutation(muts[0], source)
        self.assertIsInstance(result, Mutation)
        self.assertEqual(result.status, "killed")

    def test_run_mutation_invalid_line(self):
        mut = Mutation(
            id="mut_1", file_path="test.py", line_number=999,
            original="x", mutated="y", mutation_type="boundary",
        )
        result = self.runner.run_mutation(mut, "short source")
        self.assertEqual(result.status, "error")

    def test_run_all_returns_report(self):
        source = "if x < 10:\n    result = a + b\n    flag = True"
        report = self.runner.run_all("test.py", source)
        self.assertIsInstance(report, MutationReport)
        self.assertGreater(report.total, 0)
        self.assertGreaterEqual(report.duration, 0.0)

    def test_report_score_calculation(self):
        source = "if x == y:\n    pass"
        report = self.runner.run_all("test.py", source)
        # All dry-run => killed, score = 1.0
        if report.total > 0:
            self.assertEqual(report.score, 1.0)

    def test_report_zero_testable(self):
        source = "# nothing to mutate"
        report = self.runner.run_all("test.py", source)
        self.assertEqual(report.total, 0)
        self.assertEqual(report.score, 0.0)

    def test_mutation_dataclass_fields(self):
        m = Mutation(
            id="m1", file_path="f.py", line_number=1,
            original="a", mutated="b", mutation_type="negate",
        )
        self.assertEqual(m.id, "m1")
        self.assertEqual(m.status, "pending")
        self.assertEqual(m.mutation_type, "negate")

    def test_no_mutations_for_clean_code(self):
        source = "x = 42\ny = 'hello'"
        muts = self.runner.generate_mutations("test.py", source)
        # No boundary/negate/arithmetic/comparison patterns
        self.assertEqual(len(muts), 0)

    def test_run_mutation_preserves_id(self):
        mut = Mutation(
            id="custom_id", file_path="test.py", line_number=1,
            original="if x < 10:", mutated="if x <= 10:", mutation_type="boundary",
        )
        result = self.runner.run_mutation(mut, "if x < 10:\n    pass")
        self.assertEqual(result.id, "custom_id")

    def test_boundary_lte_to_lt(self):
        source = "if x <= 10:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        boundary_muts = [m for m in muts if m.mutation_type == "boundary"]
        self.assertTrue(len(boundary_muts) > 0)
        self.assertIn("< ", boundary_muts[0].mutated)

    def test_boundary_gte_to_gt(self):
        source = "if x >= 10:\n    pass"
        muts = self.runner.generate_mutations("test.py", source)
        boundary_muts = [m for m in muts if m.mutation_type == "boundary"]
        self.assertTrue(len(boundary_muts) > 0)
        self.assertIn("> ", boundary_muts[0].mutated)


if __name__ == "__main__":
    unittest.main()
