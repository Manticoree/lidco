"""Tests for lidco.testing.coverage_gap — Task 979."""

import json
import os
import tempfile
import unittest

from lidco.testing.coverage_gap import (
    CoverageGap,
    CoverageGapAnalyzer,
    CoverageReport,
)


class TestCoverageGapAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CoverageGapAnalyzer()

    def test_analyze_empty_coverage(self):
        data = {"files": {}}
        report = self.analyzer.analyze_coverage_json(data)
        self.assertEqual(report.total_statements, 0)
        self.assertEqual(report.files_analyzed, 0)
        self.assertEqual(len(report.gaps), 0)

    def test_analyze_full_coverage(self):
        data = {
            "files": {
                "module.py": {
                    "summary": {"num_statements": 20, "covered_lines": 20},
                    "missing_lines": [],
                }
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        self.assertEqual(report.coverage_percent, 100.0)
        self.assertEqual(len(report.gaps), 0)

    def test_analyze_with_gaps(self):
        data = {
            "files": {
                "module.py": {
                    "summary": {"num_statements": 20, "covered_lines": 10},
                    "missing_lines": [5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
                }
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        self.assertEqual(report.coverage_percent, 50.0)
        self.assertTrue(len(report.gaps) > 0)

    def test_gaps_sorted_by_risk(self):
        data = {
            "files": {
                "a.py": {
                    "summary": {"num_statements": 50, "covered_lines": 30},
                    "missing_lines": [1, 2],
                },
                "b.py": {
                    "summary": {"num_statements": 20, "covered_lines": 5},
                    "missing_lines": list(range(6, 21)),
                },
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        if len(report.gaps) >= 2:
            self.assertGreaterEqual(report.gaps[0].risk_score, report.gaps[1].risk_score)

    def test_min_risk_filter(self):
        analyzer = CoverageGapAnalyzer(min_risk=0.9)
        data = {
            "files": {
                "module.py": {
                    "summary": {"num_statements": 100, "covered_lines": 99},
                    "missing_lines": [50],
                }
            }
        }
        report = analyzer.analyze_coverage_json(data)
        # Single missing line = low risk, should be filtered
        self.assertEqual(len(report.gaps), 0)

    def test_group_consecutive_basic(self):
        groups = self.analyzer._group_consecutive([1, 2, 3, 5, 6, 10])
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0], [1, 2, 3])
        self.assertEqual(groups[1], [5, 6])
        self.assertEqual(groups[2], [10])

    def test_group_consecutive_single(self):
        groups = self.analyzer._group_consecutive([42])
        self.assertEqual(groups, [[42]])

    def test_group_consecutive_empty(self):
        groups = self.analyzer._group_consecutive([])
        self.assertEqual(groups, [])

    def test_risk_calculation(self):
        risk = self.analyzer._calculate_risk(10, 20)
        self.assertGreater(risk, 0.0)
        self.assertLessEqual(risk, 1.0)

    def test_risk_calculation_zero_statements(self):
        risk = self.analyzer._calculate_risk(5, 0)
        self.assertEqual(risk, 0.0)

    def test_get_top_gaps(self):
        data = {
            "files": {
                f"f{i}.py": {
                    "summary": {"num_statements": 10, "covered_lines": 2},
                    "missing_lines": list(range(3, 11)),
                }
                for i in range(5)
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        top = self.analyzer.get_top_gaps(report, n=3)
        self.assertLessEqual(len(top), 3)

    def test_format_report(self):
        data = {
            "files": {
                "module.py": {
                    "summary": {"num_statements": 50, "covered_lines": 40},
                    "missing_lines": [10, 11, 12, 13, 14],
                }
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        text = self.analyzer.format_report(report)
        self.assertIn("Coverage:", text)
        self.assertIn("Files analyzed:", text)
        self.assertIn("Gaps found:", text)

    def test_coverage_percent_calculation(self):
        data = {
            "files": {
                "a.py": {
                    "summary": {"num_statements": 100, "covered_lines": 75},
                    "missing_lines": list(range(76, 101)),
                }
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        self.assertAlmostEqual(report.coverage_percent, 75.0)

    def test_analyze_multiple_files(self):
        data = {
            "files": {
                "a.py": {
                    "summary": {"num_statements": 30, "covered_lines": 20},
                    "missing_lines": [21, 22, 23, 24, 25],
                },
                "b.py": {
                    "summary": {"num_statements": 20, "covered_lines": 15},
                    "missing_lines": [16, 17, 18],
                },
            }
        }
        report = self.analyzer.analyze_coverage_json(data)
        self.assertEqual(report.files_analyzed, 2)
        self.assertEqual(report.total_statements, 50)
        self.assertEqual(report.covered_statements, 35)

    def test_min_risk_property(self):
        analyzer = CoverageGapAnalyzer(min_risk=0.5)
        self.assertEqual(analyzer.min_risk, 0.5)

    def test_analyze_from_file(self):
        data = {
            "files": {
                "module.py": {
                    "summary": {"num_statements": 10, "covered_lines": 8},
                    "missing_lines": [9, 10],
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            tmp_path = f.name
        try:
            report = self.analyzer.analyze_from_file(tmp_path)
            self.assertEqual(report.files_analyzed, 1)
            self.assertEqual(report.total_statements, 10)
        finally:
            os.unlink(tmp_path)

    def test_coverage_gap_dataclass(self):
        gap = CoverageGap(
            file_path="x.py", line_numbers=[1, 2], gap_type="block",
            name="lines 1-2", risk_score=0.5, suggestion="test it",
        )
        self.assertEqual(gap.file_path, "x.py")
        self.assertEqual(gap.gap_type, "block")

    def test_gap_name_single_line(self):
        # Use low min_risk to ensure single-line gap is included
        analyzer = CoverageGapAnalyzer(min_risk=0.0)
        data = {
            "files": {
                "module.py": {
                    "summary": {"num_statements": 5, "covered_lines": 0},
                    "missing_lines": [3],
                }
            }
        }
        report = analyzer.analyze_coverage_json(data)
        single_gaps = [g for g in report.gaps if "line 3" in g.name]
        self.assertTrue(len(single_gaps) > 0)

    def test_group_consecutive_unsorted(self):
        groups = self.analyzer._group_consecutive([5, 3, 4, 1])
        self.assertEqual(groups, [[1], [3, 4, 5]])


if __name__ == "__main__":
    unittest.main()
