"""Tests for lidco.coverage.optimizer — CoverageOptimizer."""

from __future__ import annotations

import unittest

from lidco.coverage.analyzer import CoverageAnalyzer, RiskLevel
from lidco.coverage.collector import (
    BranchCoverage,
    CoverageSnapshot,
    FileCoverage,
    FunctionCoverage,
    LineCoverage,
)
from lidco.coverage.optimizer import (
    CoverageOptimizer,
    OptimizationPlan,
    TestSuggestion,
)


def _make_analysis():
    f1 = FileCoverage(
        path="src/a.py",
        lines=tuple(LineCoverage(i, 1 if i <= 5 else 0) for i in range(1, 11)),
        functions=(
            FunctionCoverage("good_fn", 1, 5, 3),
            FunctionCoverage("bad_fn", 6, 10, 0),
        ),
        branches=(
            BranchCoverage(3, 0, 1),
            BranchCoverage(3, 1, 0),
        ),
    )
    f2 = FileCoverage(
        path="src/b.py",
        lines=tuple(LineCoverage(i, 1 if i <= 2 else 0) for i in range(1, 11)),
        functions=(
            FunctionCoverage("b_fn", 1, 10, 0),
        ),
        branches=(),
    )
    snap = CoverageSnapshot(files=(f1, f2))
    analyzer = CoverageAnalyzer()
    return analyzer.analyze(snap)


class TestTestSuggestion(unittest.TestCase):
    def test_frozen(self) -> None:
        ts = TestSuggestion("f.py", "fn", "desc", 1, "low", 5)
        self.assertEqual(ts.file_path, "f.py")
        with self.assertRaises(AttributeError):
            ts.priority = 2  # type: ignore[misc]


class TestOptimizationPlan(unittest.TestCase):
    def test_suggestion_count(self) -> None:
        plan = OptimizationPlan(
            suggestions=(
                TestSuggestion("a", "t", "d", 1, "low", 3),
                TestSuggestion("b", "t", "d", 2, "medium", 5),
            ),
            total_expected_gain=8,
        )
        self.assertEqual(plan.suggestion_count, 2)

    def test_empty_plan(self) -> None:
        plan = OptimizationPlan()
        self.assertEqual(plan.suggestion_count, 0)
        self.assertEqual(plan.total_expected_gain, 0)


class TestCoverageOptimizer(unittest.TestCase):
    def test_optimize_basic(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        self.assertGreater(plan.suggestion_count, 0)
        self.assertGreater(plan.total_expected_gain, 0)
        self.assertGreaterEqual(plan.projected_line_rate, plan.current_line_rate)

    def test_suggestions_sorted_by_priority(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        priorities = [s.priority for s in plan.suggestions]
        self.assertEqual(priorities, sorted(priorities))

    def test_uncovered_function_suggested(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        targets = [s.target for s in plan.suggestions]
        self.assertIn("bad_fn", targets)
        self.assertIn("b_fn", targets)

    def test_gap_suggested(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        gap_suggestions = [
            s for s in plan.suggestions if s.target.startswith("lines")
        ]
        self.assertGreater(len(gap_suggestions), 0)

    def test_partial_branch_suggested(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        branch_suggestions = [
            s for s in plan.suggestions if "branch" in s.target
        ]
        self.assertGreater(len(branch_suggestions), 0)

    def test_max_suggestions(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer(max_suggestions=2)
        plan = optimizer.optimize(analysis)
        self.assertLessEqual(plan.suggestion_count, 2)

    def test_effort_estimation(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)

        efforts = {s.estimated_effort for s in plan.suggestions}
        # Should have at least one effort level
        self.assertTrue(efforts.issubset({"low", "medium", "high"}))

    def test_prioritize_files(self) -> None:
        analysis = _make_analysis()
        optimizer = CoverageOptimizer()
        ranked = optimizer.prioritize_files(analysis, top_n=5)

        self.assertGreater(len(ranked), 0)
        # First file should be worst coverage / highest risk
        self.assertLessEqual(ranked[0].line_rate, ranked[-1].line_rate + 0.01)

    def test_empty_analysis(self) -> None:
        snap = CoverageSnapshot()
        analyzer = CoverageAnalyzer()
        analysis = analyzer.analyze(snap)
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)
        self.assertEqual(plan.suggestion_count, 0)

    def test_full_coverage_no_suggestions(self) -> None:
        fc = FileCoverage(
            path="perfect.py",
            lines=tuple(LineCoverage(i, 1) for i in range(1, 11)),
            functions=(FunctionCoverage("f", 1, 10, 5),),
            branches=(
                BranchCoverage(3, 0, 1),
                BranchCoverage(3, 1, 1),
            ),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        analysis = analyzer.analyze(snap)
        optimizer = CoverageOptimizer()
        plan = optimizer.optimize(analysis)
        self.assertEqual(plan.suggestion_count, 0)

    def test_estimate_effort_static(self) -> None:
        self.assertEqual(CoverageOptimizer._estimate_effort(3), "low")
        self.assertEqual(CoverageOptimizer._estimate_effort(5), "low")
        self.assertEqual(CoverageOptimizer._estimate_effort(10), "medium")
        self.assertEqual(CoverageOptimizer._estimate_effort(20), "medium")
        self.assertEqual(CoverageOptimizer._estimate_effort(25), "high")


if __name__ == "__main__":
    unittest.main()
