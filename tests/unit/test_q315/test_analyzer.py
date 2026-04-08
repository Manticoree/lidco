"""Tests for lidco.coverage.analyzer — CoverageAnalyzer."""

from __future__ import annotations

import unittest

from lidco.coverage.analyzer import (
    AnalysisResult,
    CoverageAnalyzer,
    CoverageGap,
    FileRiskAssessment,
    PartiallyCoveredBranch,
    RiskLevel,
    UncoveredFunction,
)
from lidco.coverage.collector import (
    BranchCoverage,
    CoverageSnapshot,
    FileCoverage,
    FunctionCoverage,
    LineCoverage,
)


def _make_snapshot() -> CoverageSnapshot:
    """Snapshot with mixed coverage."""
    f1 = FileCoverage(
        path="src/a.py",
        lines=tuple(
            LineCoverage(i, 1 if i <= 7 else 0) for i in range(1, 11)
        ),
        functions=(
            FunctionCoverage("covered_fn", 1, 5, 3),
            FunctionCoverage("uncovered_fn", 6, 10, 0),
        ),
        branches=(
            BranchCoverage(3, 0, 1),
            BranchCoverage(3, 1, 0),
            BranchCoverage(8, 0, 0),
            BranchCoverage(8, 1, 0),
        ),
    )
    f2 = FileCoverage(
        path="src/b.py",
        lines=tuple(LineCoverage(i, 1) for i in range(1, 6)),
        functions=(FunctionCoverage("all_good", 1, 5, 2),),
        branches=(BranchCoverage(2, 0, 1), BranchCoverage(2, 1, 1)),
    )
    return CoverageSnapshot(files=(f1, f2))


class TestRiskLevel(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(RiskLevel.LOW, "low")
        self.assertEqual(RiskLevel.MEDIUM, "medium")
        self.assertEqual(RiskLevel.HIGH, "high")
        self.assertEqual(RiskLevel.CRITICAL, "critical")


class TestCoverageAnalyzer(unittest.TestCase):
    def test_analyze_basic(self) -> None:
        snap = _make_snapshot()
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)

        self.assertEqual(len(result.file_assessments), 2)
        self.assertAlmostEqual(result.overall_line_rate, 12 / 15)
        self.assertGreater(result.overall_function_rate, 0)
        self.assertGreater(result.overall_branch_rate, 0)

    def test_uncovered_functions(self) -> None:
        snap = _make_snapshot()
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)

        self.assertEqual(len(result.uncovered_functions), 1)
        uf = result.uncovered_functions[0]
        self.assertEqual(uf.name, "uncovered_fn")
        self.assertEqual(uf.file_path, "src/a.py")

    def test_coverage_gaps(self) -> None:
        snap = _make_snapshot()
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)

        # src/a.py has lines 8,9,10 uncovered — one gap
        gaps_a = [g for g in result.gaps if g.file_path == "src/a.py"]
        self.assertEqual(len(gaps_a), 1)
        self.assertEqual(gaps_a[0].start_line, 8)
        self.assertEqual(gaps_a[0].end_line, 10)
        self.assertEqual(gaps_a[0].line_count, 3)

    def test_partial_branches(self) -> None:
        snap = _make_snapshot()
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)

        # line 3 in a.py has 1/2 branches covered
        partial_a = [
            p for p in result.partial_branches if p.file_path == "src/a.py"
        ]
        self.assertEqual(len(partial_a), 1)
        self.assertEqual(partial_a[0].line_number, 3)
        self.assertEqual(partial_a[0].covered_branches, 1)
        self.assertEqual(partial_a[0].total_branches, 2)

    def test_risk_critical(self) -> None:
        # File with very low coverage
        fc = FileCoverage(
            path="low.py",
            lines=tuple(
                LineCoverage(i, 1 if i == 1 else 0) for i in range(1, 11)
            ),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        self.assertEqual(result.overall_risk, RiskLevel.CRITICAL)

    def test_risk_low(self) -> None:
        fc = FileCoverage(
            path="good.py",
            lines=tuple(LineCoverage(i, 1) for i in range(1, 11)),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        self.assertEqual(result.overall_risk, RiskLevel.LOW)

    def test_custom_thresholds(self) -> None:
        fc = FileCoverage(
            path="mid.py",
            lines=tuple(
                LineCoverage(i, 1 if i <= 6 else 0) for i in range(1, 11)
            ),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer(risk_thresholds={
            "critical": 0.5,
            "high": 0.7,
            "medium": 0.9,
        })
        result = analyzer.analyze(snap)
        # 60% < 0.7 → high
        self.assertEqual(result.overall_risk, RiskLevel.HIGH)

    def test_empty_snapshot(self) -> None:
        snap = CoverageSnapshot()
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        self.assertEqual(len(result.file_assessments), 0)
        self.assertAlmostEqual(result.overall_line_rate, 0.0)

    def test_uncovered_function_risk_large(self) -> None:
        """Large uncovered functions get HIGH risk."""
        fc = FileCoverage(
            path="big.py",
            lines=tuple(LineCoverage(i, 0) for i in range(1, 30)),
            functions=(FunctionCoverage("big_fn", 1, 25, 0),),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        self.assertEqual(result.uncovered_functions[0].risk, RiskLevel.HIGH)

    def test_multiple_gaps(self) -> None:
        """Non-contiguous uncovered lines produce multiple gaps."""
        lines = []
        for i in range(1, 11):
            hits = 1 if i in (1, 2, 5, 6) else 0
            lines.append(LineCoverage(i, hits))
        fc = FileCoverage(path="gaps.py", lines=tuple(lines))
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        gaps = result.gaps
        self.assertEqual(len(gaps), 2)  # 3-4 and 7-10

    def test_no_partial_when_all_covered(self) -> None:
        fc = FileCoverage(
            path="x.py",
            branches=(
                BranchCoverage(1, 0, 1),
                BranchCoverage(1, 1, 1),
            ),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        self.assertEqual(len(result.partial_branches), 0)

    def test_no_partial_when_all_uncovered(self) -> None:
        """All-uncovered is not 'partial' — it's fully uncovered."""
        fc = FileCoverage(
            path="x.py",
            branches=(
                BranchCoverage(1, 0, 0),
                BranchCoverage(1, 1, 0),
            ),
        )
        snap = CoverageSnapshot(files=(fc,))
        analyzer = CoverageAnalyzer()
        result = analyzer.analyze(snap)
        self.assertEqual(len(result.partial_branches), 0)


class TestDataclassesFrozen(unittest.TestCase):
    def test_uncovered_function_frozen(self) -> None:
        uf = UncoveredFunction("f.py", "fn", 1, 5)
        with self.assertRaises(AttributeError):
            uf.name = "x"  # type: ignore[misc]

    def test_coverage_gap_frozen(self) -> None:
        g = CoverageGap("f.py", 1, 5, 5)
        with self.assertRaises(AttributeError):
            g.start_line = 0  # type: ignore[misc]

    def test_file_risk_assessment_frozen(self) -> None:
        fa = FileRiskAssessment("f.py", 0.5, 0.5, 0.5, "medium")
        with self.assertRaises(AttributeError):
            fa.risk = "low"  # type: ignore[misc]

    def test_analysis_result_frozen(self) -> None:
        ar = AnalysisResult(0.5, 0.5, 0.5, "medium")
        with self.assertRaises(AttributeError):
            ar.overall_risk = "low"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
