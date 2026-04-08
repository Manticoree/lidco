"""Tests for lidco.coverage.collector — CoverageCollector."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from lidco.coverage.collector import (
    BranchCoverage,
    CoverageCollector,
    CoverageSnapshot,
    DeltaCoverage,
    FileCoverage,
    FunctionCoverage,
    LineCoverage,
)


def _sample_data() -> dict:
    return {
        "meta": {"timestamp": "2026-04-01T10:00:00"},
        "files": {
            "src/foo.py": {
                "executed_lines": [1, 2, 5],
                "missing_lines": [3, 4],
                "functions": [
                    {"name": "foo", "start": 1, "end": 5, "hits": 2},
                    {"name": "bar", "start": 6, "end": 10, "hits": 0},
                ],
                "branches": [
                    {"line": 2, "branch": 0, "hits": 1},
                    {"line": 2, "branch": 1, "hits": 0},
                ],
            },
            "src/bar.py": {
                "executed_lines": [1, 2, 3],
                "missing_lines": [],
                "functions": [
                    {"name": "baz", "start": 1, "end": 3, "hits": 5},
                ],
                "branches": [],
            },
        },
    }


class TestLineCoverage(unittest.TestCase):
    def test_frozen(self) -> None:
        lc = LineCoverage(line_number=1, hits=3)
        self.assertEqual(lc.line_number, 1)
        self.assertEqual(lc.hits, 3)
        with self.assertRaises(AttributeError):
            lc.hits = 0  # type: ignore[misc]


class TestFunctionCoverage(unittest.TestCase):
    def test_attrs(self) -> None:
        fc = FunctionCoverage(name="f", start_line=1, end_line=10, hits=2)
        self.assertEqual(fc.name, "f")
        self.assertEqual(fc.start_line, 1)
        self.assertEqual(fc.end_line, 10)
        self.assertEqual(fc.hits, 2)


class TestBranchCoverage(unittest.TestCase):
    def test_attrs(self) -> None:
        bc = BranchCoverage(line_number=5, branch_id=0, hits=1)
        self.assertEqual(bc.line_number, 5)
        self.assertEqual(bc.branch_id, 0)


class TestFileCoverage(unittest.TestCase):
    def test_line_rate_full(self) -> None:
        lines = (LineCoverage(1, 1), LineCoverage(2, 1))
        fc = FileCoverage(path="a.py", lines=lines)
        self.assertAlmostEqual(fc.line_rate, 1.0)
        self.assertEqual(fc.total_lines, 2)
        self.assertEqual(fc.covered_lines, 2)

    def test_line_rate_partial(self) -> None:
        lines = (LineCoverage(1, 1), LineCoverage(2, 0))
        fc = FileCoverage(path="a.py", lines=lines)
        self.assertAlmostEqual(fc.line_rate, 0.5)

    def test_line_rate_empty(self) -> None:
        fc = FileCoverage(path="a.py")
        self.assertAlmostEqual(fc.line_rate, 0.0)

    def test_function_rate(self) -> None:
        fns = (
            FunctionCoverage("a", 1, 5, 1),
            FunctionCoverage("b", 6, 10, 0),
        )
        fc = FileCoverage(path="a.py", functions=fns)
        self.assertAlmostEqual(fc.function_rate, 0.5)

    def test_function_rate_empty(self) -> None:
        fc = FileCoverage(path="a.py")
        self.assertAlmostEqual(fc.function_rate, 0.0)

    def test_branch_rate(self) -> None:
        brs = (
            BranchCoverage(1, 0, 1),
            BranchCoverage(1, 1, 0),
            BranchCoverage(1, 2, 1),
        )
        fc = FileCoverage(path="a.py", branches=brs)
        self.assertAlmostEqual(fc.branch_rate, 2 / 3)
        self.assertEqual(fc.total_branches, 3)
        self.assertEqual(fc.covered_branches, 2)

    def test_branch_rate_empty(self) -> None:
        fc = FileCoverage(path="a.py")
        self.assertAlmostEqual(fc.branch_rate, 0.0)


class TestCoverageSnapshot(unittest.TestCase):
    def test_aggregate(self) -> None:
        f1 = FileCoverage(
            path="a.py",
            lines=(LineCoverage(1, 1), LineCoverage(2, 0)),
            functions=(FunctionCoverage("f", 1, 2, 1),),
            branches=(BranchCoverage(1, 0, 1),),
        )
        f2 = FileCoverage(
            path="b.py",
            lines=(LineCoverage(1, 1),),
        )
        snap = CoverageSnapshot(files=(f1, f2), timestamp="t1")
        self.assertEqual(snap.total_lines, 3)
        self.assertEqual(snap.covered_lines, 2)
        self.assertAlmostEqual(snap.line_rate, 2 / 3)
        self.assertEqual(snap.total_functions, 1)
        self.assertEqual(snap.covered_functions, 1)
        self.assertEqual(snap.total_branches, 1)
        self.assertEqual(snap.covered_branches, 1)

    def test_empty(self) -> None:
        snap = CoverageSnapshot()
        self.assertAlmostEqual(snap.line_rate, 0.0)


class TestCoverageCollector(unittest.TestCase):
    def test_collect_from_dict(self) -> None:
        collector = CoverageCollector()
        snap = collector.collect_from_dict(_sample_data())
        self.assertEqual(len(snap.files), 2)
        self.assertEqual(snap.timestamp, "2026-04-01T10:00:00")

        foo = snap.files[1]  # src/foo.py sorted after src/bar.py
        self.assertEqual(foo.path, "src/foo.py")
        self.assertEqual(foo.total_lines, 5)
        self.assertEqual(foo.covered_lines, 3)
        self.assertEqual(len(foo.functions), 2)
        self.assertEqual(len(foo.branches), 2)

    def test_collect_from_json(self) -> None:
        collector = CoverageCollector()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(_sample_data(), f)
            f.flush()
            path = f.name

        try:
            snap = collector.collect_from_json(path)
            self.assertEqual(len(snap.files), 2)
        finally:
            os.unlink(path)

    def test_root(self) -> None:
        c = CoverageCollector("/tmp")
        from pathlib import Path
        self.assertEqual(c.root, Path("/tmp"))

    def test_delta(self) -> None:
        collector = CoverageCollector()
        before = CoverageSnapshot(
            files=(
                FileCoverage(
                    path="a.py",
                    lines=(LineCoverage(1, 1), LineCoverage(2, 0)),
                ),
            ),
            timestamp="t1",
        )
        after = CoverageSnapshot(
            files=(
                FileCoverage(
                    path="a.py",
                    lines=(LineCoverage(1, 1), LineCoverage(2, 1)),
                ),
                FileCoverage(
                    path="b.py",
                    lines=(LineCoverage(1, 1),),
                ),
            ),
            timestamp="t2",
        )
        delta = collector.delta(before, after)
        self.assertAlmostEqual(delta.line_rate_delta, after.line_rate - before.line_rate)
        self.assertEqual(delta.new_files, ("b.py",))
        self.assertEqual(delta.removed_files, ())
        self.assertEqual(delta.lines_added, 1)
        self.assertEqual(delta.covered_lines_added, 2)

    def test_delta_removed_files(self) -> None:
        collector = CoverageCollector()
        before = CoverageSnapshot(
            files=(FileCoverage(path="old.py", lines=(LineCoverage(1, 1),)),),
        )
        after = CoverageSnapshot(files=())
        delta = collector.delta(before, after)
        self.assertEqual(delta.removed_files, ("old.py",))
        self.assertEqual(delta.new_files, ())

    def test_missing_meta(self) -> None:
        collector = CoverageCollector()
        snap = collector.collect_from_dict({"files": {}})
        self.assertEqual(snap.timestamp, "")
        self.assertEqual(len(snap.files), 0)


if __name__ == "__main__":
    unittest.main()
