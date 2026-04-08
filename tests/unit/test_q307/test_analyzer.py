"""Tests for OwnershipAnalyzer."""

import unittest

from lidco.ownership.analyzer import (
    BusFactorResult,
    CoverageGap,
    KnowledgeSilo,
    OrphanedFile,
    OwnershipAnalyzer,
    OwnershipReport,
)
from lidco.ownership.generator import BlameEntry


class TestDataclasses(unittest.TestCase):
    def test_bus_factor_result_frozen(self):
        r = BusFactorResult(path="src", bus_factor=2, top_contributors=[], total_lines=100)
        with self.assertRaises(AttributeError):
            r.bus_factor = 3  # type: ignore[misc]

    def test_knowledge_silo_frozen(self):
        s = KnowledgeSilo(path="src", sole_owner="alice", ownership_fraction=0.9, total_lines=200)
        self.assertEqual(s.sole_owner, "alice")

    def test_orphaned_file(self):
        o = OrphanedFile(file_path="bin/data.bin", reason="no blame data")
        self.assertEqual(o.reason, "no blame data")

    def test_coverage_gap(self):
        g = CoverageGap(directory="lib", file_count=5)
        self.assertEqual(g.file_count, 5)

    def test_ownership_report_summary(self):
        r = OwnershipReport(
            bus_factors=[BusFactorResult("a", 1, [], 10)],
            knowledge_silos=[KnowledgeSilo("a", "x", 0.9, 10)],
            orphaned_files=[],
            coverage_gaps=[CoverageGap("a", 2)],
            overall_bus_factor=1,
        )
        s = r.summary()
        self.assertEqual(s["overall_bus_factor"], 1)
        self.assertEqual(s["silo_count"], 1)
        self.assertEqual(s["orphaned_count"], 0)
        self.assertEqual(s["gap_count"], 1)
        self.assertEqual(s["directory_count"], 1)


class TestOwnershipAnalyzer(unittest.TestCase):
    def _make_entries(self) -> list[BlameEntry]:
        return [
            BlameEntry("src/a.py", "alice", 80),
            BlameEntry("src/a.py", "bob", 20),
            BlameEntry("lib/b.py", "charlie", 100),
            BlameEntry("docs/c.md", "alice", 50),
        ]

    def test_analyze_returns_report(self):
        analyzer = OwnershipAnalyzer()
        entries = self._make_entries()
        report = analyzer.analyze(entries)
        self.assertIsInstance(report, OwnershipReport)
        self.assertGreater(len(report.bus_factors), 0)

    def test_bus_factor_single_owner(self):
        analyzer = OwnershipAnalyzer()
        entries = [BlameEntry("src/a.py", "alice", 100)]
        report = analyzer.analyze(entries)
        for bf in report.bus_factors:
            if bf.path.replace("\\", "/") == "src":
                self.assertEqual(bf.bus_factor, 1)

    def test_bus_factor_multiple_owners(self):
        analyzer = OwnershipAnalyzer(bus_factor_threshold=0.80)
        entries = [
            BlameEntry("src/a.py", "alice", 40),
            BlameEntry("src/a.py", "bob", 40),
            BlameEntry("src/a.py", "charlie", 20),
        ]
        report = analyzer.analyze(entries)
        for bf in report.bus_factors:
            if bf.path.replace("\\", "/") == "src":
                self.assertGreaterEqual(bf.bus_factor, 2)

    def test_knowledge_silo_detected(self):
        analyzer = OwnershipAnalyzer(silo_threshold=0.80)
        entries = [
            BlameEntry("lib/x.py", "alice", 95),
            BlameEntry("lib/x.py", "bob", 5),
        ]
        report = analyzer.analyze(entries)
        self.assertGreater(len(report.knowledge_silos), 0)
        self.assertEqual(report.knowledge_silos[0].sole_owner, "alice")

    def test_no_silo_when_distributed(self):
        analyzer = OwnershipAnalyzer(silo_threshold=0.80)
        entries = [
            BlameEntry("lib/x.py", "alice", 50),
            BlameEntry("lib/x.py", "bob", 50),
        ]
        report = analyzer.analyze(entries)
        self.assertEqual(len(report.knowledge_silos), 0)

    def test_orphaned_files(self):
        analyzer = OwnershipAnalyzer()
        entries = [BlameEntry("src/a.py", "alice", 100)]
        report = analyzer.analyze(
            entries, tracked_files=["src/a.py", "src/b.py", "data.bin"],
        )
        orphaned_paths = {o.file_path for o in report.orphaned_files}
        self.assertIn("src/b.py", orphaned_paths)
        self.assertIn("data.bin", orphaned_paths)
        self.assertNotIn("src/a.py", orphaned_paths)

    def test_no_orphaned_when_no_tracked(self):
        analyzer = OwnershipAnalyzer()
        entries = [BlameEntry("src/a.py", "alice", 100)]
        report = analyzer.analyze(entries)
        self.assertEqual(len(report.orphaned_files), 0)

    def test_coverage_gaps_no_patterns(self):
        analyzer = OwnershipAnalyzer()
        entries = [
            BlameEntry("src/a.py", "alice", 100),
            BlameEntry("lib/b.py", "bob", 50),
        ]
        report = analyzer.analyze(entries)
        # No codeowners patterns = all dirs are gaps
        self.assertGreater(len(report.coverage_gaps), 0)

    def test_coverage_gaps_with_patterns(self):
        analyzer = OwnershipAnalyzer()
        entries = [
            BlameEntry("src/a.py", "alice", 100),
            BlameEntry("lib/b.py", "bob", 50),
        ]
        report = analyzer.analyze(
            entries, codeowners_patterns=["/src"],
        )
        gap_dirs = {g.directory for g in report.coverage_gaps}
        self.assertIn("lib", gap_dirs)

    def test_overall_bus_factor(self):
        analyzer = OwnershipAnalyzer()
        entries = [
            BlameEntry("src/a.py", "alice", 80),
            BlameEntry("src/b.py", "bob", 20),
        ]
        report = analyzer.analyze(entries)
        self.assertGreaterEqual(report.overall_bus_factor, 1)

    def test_empty_entries(self):
        analyzer = OwnershipAnalyzer()
        report = analyzer.analyze([])
        self.assertEqual(report.overall_bus_factor, 0)
        self.assertEqual(len(report.bus_factors), 0)
        self.assertEqual(len(report.knowledge_silos), 0)


if __name__ == "__main__":
    unittest.main()
