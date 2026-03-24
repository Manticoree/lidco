# src/lidco/analytics/health_dashboard.py
"""Project health dashboard — aggregate code metrics."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HealthReport:
    source_files: int
    test_files: int
    test_count: int
    total_lines: int
    avg_file_lines: float
    large_files: list[str]  # files > threshold lines
    score: float  # 0.0–1.0 composite health score
    details: dict[str, object] = field(default_factory=dict)

    def format_table(self) -> str:
        """Return a human-readable summary table."""
        lines = [
            "Project Health Report",
            "=" * 36,
            f"  Source files  : {self.source_files}",
            f"  Test files    : {self.test_files}",
            f"  Test count    : {self.test_count} (est.)",
            f"  Total lines   : {self.total_lines:,}",
            f"  Avg file size : {self.avg_file_lines:.0f} lines",
            f"  Large files   : {len(self.large_files)}",
            f"  Health score  : {self.score:.0%}",
        ]
        if self.large_files:
            lines.append("\nLarge files (>400 lines):")
            for f in self.large_files[:5]:
                lines.append(f"  {f}")
            if len(self.large_files) > 5:
                lines.append(f"  ... and {len(self.large_files) - 5} more")
        return "\n".join(lines)


class ProjectHealthDashboard:
    """Collect and report project health metrics."""

    _LARGE_FILE_THRESHOLD = 400  # lines
    _SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build"}

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()

    def _iter_py_files(self) -> list[Path]:
        result: list[Path] = []
        for p in self.root.rglob("*.py"):
            if not any(part in self._SKIP_DIRS for part in p.parts):
                result.append(p)
        return result

    def _count_tests_in_file(self, path: Path) -> int:
        """Count `def test_` occurrences as a proxy for test count."""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return text.count("def test_")
        except OSError:
            return 0

    def _line_count(self, path: Path) -> int:
        try:
            return path.read_text(encoding="utf-8", errors="replace").count("\n")
        except OSError:
            return 0

    def collect(self) -> HealthReport:
        """Walk the project and compute health metrics."""
        all_files = self._iter_py_files()
        test_files: list[Path] = []
        source_files: list[Path] = []

        for p in all_files:
            rel_parts = p.relative_to(self.root).parts
            parts_lower = [part.lower() for part in rel_parts]
            if any("test" in part for part in parts_lower):
                test_files.append(p)
            else:
                source_files.append(p)

        total_lines = sum(self._line_count(p) for p in source_files)
        avg_lines = total_lines / max(len(source_files), 1)
        large_files = [
            str(p.relative_to(self.root))
            for p in source_files
            if self._line_count(p) > self._LARGE_FILE_THRESHOLD
        ]
        test_count = sum(self._count_tests_in_file(p) for p in test_files)

        # Health score heuristic
        # - test ratio: test_files / (source_files + test_files) → want >= 0.3
        # - large file ratio: large_files / source_files → want <= 0.05
        # - avg size: want <= 200 lines
        total = len(source_files) + len(test_files)
        test_ratio = len(test_files) / max(total, 1)
        large_ratio = len(large_files) / max(len(source_files), 1)
        size_score = max(0.0, 1.0 - (avg_lines - 200) / 600) if avg_lines > 200 else 1.0

        score = (
            min(test_ratio / 0.3, 1.0) * 0.4
            + max(0.0, 1.0 - large_ratio / 0.05) * 0.3
            + size_score * 0.3
        )

        return HealthReport(
            source_files=len(source_files),
            test_files=len(test_files),
            test_count=test_count,
            total_lines=total_lines,
            avg_file_lines=avg_lines,
            large_files=large_files,
            score=min(score, 1.0),
            details={
                "test_ratio": test_ratio,
                "large_ratio": large_ratio,
                "size_score": size_score,
            },
        )
