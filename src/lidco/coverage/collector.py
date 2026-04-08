"""
Coverage Collector — collect coverage data: line, branch, function;
per-file and aggregate; delta coverage.

Pure stdlib. Parses coverage.py JSON output or raw hit data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineCoverage:
    """Coverage info for a single line."""

    line_number: int
    hits: int


@dataclass(frozen=True)
class FunctionCoverage:
    """Coverage info for a single function."""

    name: str
    start_line: int
    end_line: int
    hits: int


@dataclass(frozen=True)
class BranchCoverage:
    """Coverage info for a single branch point."""

    line_number: int
    branch_id: int
    hits: int


@dataclass(frozen=True)
class FileCoverage:
    """Aggregated coverage for one source file."""

    path: str
    lines: tuple[LineCoverage, ...] = ()
    functions: tuple[FunctionCoverage, ...] = ()
    branches: tuple[BranchCoverage, ...] = ()

    @property
    def total_lines(self) -> int:
        return len(self.lines)

    @property
    def covered_lines(self) -> int:
        return sum(1 for ln in self.lines if ln.hits > 0)

    @property
    def line_rate(self) -> float:
        if not self.lines:
            return 0.0
        return self.covered_lines / self.total_lines

    @property
    def total_functions(self) -> int:
        return len(self.functions)

    @property
    def covered_functions(self) -> int:
        return sum(1 for fn in self.functions if fn.hits > 0)

    @property
    def function_rate(self) -> float:
        if not self.functions:
            return 0.0
        return self.covered_functions / self.total_functions

    @property
    def total_branches(self) -> int:
        return len(self.branches)

    @property
    def covered_branches(self) -> int:
        return sum(1 for br in self.branches if br.hits > 0)

    @property
    def branch_rate(self) -> float:
        if not self.branches:
            return 0.0
        return self.covered_branches / self.total_branches


@dataclass(frozen=True)
class CoverageSnapshot:
    """Complete coverage snapshot across all files."""

    files: tuple[FileCoverage, ...] = ()
    timestamp: str = ""

    @property
    def total_lines(self) -> int:
        return sum(f.total_lines for f in self.files)

    @property
    def covered_lines(self) -> int:
        return sum(f.covered_lines for f in self.files)

    @property
    def line_rate(self) -> float:
        total = self.total_lines
        if total == 0:
            return 0.0
        return self.covered_lines / total

    @property
    def total_functions(self) -> int:
        return sum(f.total_functions for f in self.files)

    @property
    def covered_functions(self) -> int:
        return sum(f.covered_functions for f in self.files)

    @property
    def total_branches(self) -> int:
        return sum(f.total_branches for f in self.files)

    @property
    def covered_branches(self) -> int:
        return sum(f.covered_branches for f in self.files)


@dataclass(frozen=True)
class DeltaCoverage:
    """Coverage change between two snapshots."""

    before: CoverageSnapshot
    after: CoverageSnapshot
    new_files: tuple[str, ...] = ()
    removed_files: tuple[str, ...] = ()

    @property
    def line_rate_delta(self) -> float:
        return self.after.line_rate - self.before.line_rate

    @property
    def lines_added(self) -> int:
        return self.after.total_lines - self.before.total_lines

    @property
    def covered_lines_added(self) -> int:
        return self.after.covered_lines - self.before.covered_lines


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class CoverageCollector:
    """Collect coverage data from various sources."""

    def __init__(self, root: str = ".") -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def collect_from_json(self, json_path: str) -> CoverageSnapshot:
        """Parse a coverage.py JSON report into a CoverageSnapshot."""
        path = Path(json_path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return self._parse_coverage_json(raw)

    def collect_from_dict(self, data: dict[str, Any]) -> CoverageSnapshot:
        """Build a CoverageSnapshot from a pre-loaded dict."""
        return self._parse_coverage_json(data)

    def delta(
        self, before: CoverageSnapshot, after: CoverageSnapshot
    ) -> DeltaCoverage:
        """Compute delta between two snapshots."""
        before_paths = {f.path for f in before.files}
        after_paths = {f.path for f in after.files}
        new_files = tuple(sorted(after_paths - before_paths))
        removed_files = tuple(sorted(before_paths - after_paths))
        return DeltaCoverage(
            before=before,
            after=after,
            new_files=new_files,
            removed_files=removed_files,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_coverage_json(self, data: dict[str, Any]) -> CoverageSnapshot:
        """Parse coverage.py JSON structure.

        Expected layout::

            {
              "meta": {"timestamp": "..."},
              "files": {
                "path/to/file.py": {
                  "executed_lines": [1, 2, 5],
                  "missing_lines": [3, 4],
                  "functions": [
                    {"name": "foo", "start": 1, "end": 10, "hits": 2}
                  ],
                  "branches": [
                    {"line": 5, "branch": 0, "hits": 1}
                  ]
                }
              }
            }
        """
        meta = data.get("meta", {})
        timestamp = str(meta.get("timestamp", ""))
        files_raw: dict[str, Any] = data.get("files", {})

        file_coverages: list[FileCoverage] = []
        for fpath, fdata in sorted(files_raw.items()):
            executed: Sequence[int] = fdata.get("executed_lines", [])
            missing: Sequence[int] = fdata.get("missing_lines", [])

            lines: list[LineCoverage] = []
            for ln in sorted(set(executed) | set(missing)):
                hits = 1 if ln in set(executed) else 0
                lines.append(LineCoverage(line_number=ln, hits=hits))

            functions: list[FunctionCoverage] = []
            for fd in fdata.get("functions", []):
                functions.append(
                    FunctionCoverage(
                        name=fd["name"],
                        start_line=fd["start"],
                        end_line=fd["end"],
                        hits=fd.get("hits", 0),
                    )
                )

            branches: list[BranchCoverage] = []
            for bd in fdata.get("branches", []):
                branches.append(
                    BranchCoverage(
                        line_number=bd["line"],
                        branch_id=bd["branch"],
                        hits=bd.get("hits", 0),
                    )
                )

            file_coverages.append(
                FileCoverage(
                    path=fpath,
                    lines=tuple(lines),
                    functions=tuple(functions),
                    branches=tuple(branches),
                )
            )

        return CoverageSnapshot(files=tuple(file_coverages), timestamp=timestamp)
