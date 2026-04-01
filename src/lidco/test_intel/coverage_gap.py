"""Find coverage gaps and suggest tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CoverageGap:
    """A single uncovered region in source code."""

    file: str
    line: int
    branch: str = ""
    complexity: int = 0
    suggested_test: str = ""


class CoverageGapFinder:
    """Analyze coverage data and find untested code."""

    def __init__(self) -> None:
        pass

    def parse_coverage(self, data: dict[str, Any]) -> list[CoverageGap]:
        """Parse coverage.py JSON format and return gaps.

        Expected *data* shape::

            {
                "files": {
                    "path/to/file.py": {
                        "missing_lines": [10, 11, 25],
                        "missing_branches": [[10, 12]],
                        "complexity": {"10": 3, "25": 1}
                    }
                }
            }
        """
        gaps: list[CoverageGap] = []
        files = data.get("files", {})
        for filepath, info in files.items():
            missing = info.get("missing_lines", [])
            branches = info.get("missing_branches", [])
            complexity_map = info.get("complexity", {})

            branch_set: dict[int, str] = {}
            for br in branches:
                if isinstance(br, (list, tuple)) and len(br) >= 2:
                    branch_set[br[0]] = f"{br[0]}->{br[1]}"

            for line in missing:
                branch = branch_set.get(line, "")
                cpx = complexity_map.get(str(line), 0)
                gaps.append(CoverageGap(
                    file=filepath,
                    line=line,
                    branch=branch,
                    complexity=cpx,
                ))
        return gaps

    def find_gaps(
        self,
        covered_lines: set[int],
        total_lines: set[int],
        file: str = "",
    ) -> list[CoverageGap]:
        """Return gaps for lines in *total_lines* not in *covered_lines*."""
        missing = sorted(total_lines - covered_lines)
        return [CoverageGap(file=file, line=ln) for ln in missing]

    def prioritize(self, gaps: list[CoverageGap]) -> list[CoverageGap]:
        """Sort gaps by complexity descending (highest priority first)."""
        return sorted(gaps, key=lambda g: g.complexity, reverse=True)

    def suggest_test(self, gap: CoverageGap, source: str = "") -> str:
        """Generate a test suggestion string for *gap*."""
        parts: list[str] = [f"# Cover {gap.file}:{gap.line}"]
        if gap.branch:
            parts.append(f"# Branch: {gap.branch}")
        if source:
            lines = source.splitlines()
            if 0 < gap.line <= len(lines):
                parts.append(f"# Line: {lines[gap.line - 1].strip()}")
        parts.append(f"def test_cover_line_{gap.line}():")
        parts.append("    # TODO: write test to cover this line")
        parts.append("    pass")
        return "\n".join(parts)

    def summary(self, gaps: list[CoverageGap]) -> str:
        """Return a human-readable summary of *gaps*."""
        if not gaps:
            return "No coverage gaps found."
        files: dict[str, int] = {}
        for g in gaps:
            files[g.file] = files.get(g.file, 0) + 1

        total = len(gaps)
        lines: list[str] = [f"Coverage Gaps: {total} uncovered lines"]
        for f, count in sorted(files.items()):
            lines.append(f"  {f}: {count} gaps")

        high_complexity = [g for g in gaps if g.complexity > 0]
        if high_complexity:
            lines.append(f"High priority (complex): {len(high_complexity)}")
        return "\n".join(lines)
