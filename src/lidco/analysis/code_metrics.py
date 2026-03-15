"""Aggregate code metrics dashboard — Task 351."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileMetrics:
    file: str
    loc: int              # lines of code (non-blank, non-comment)
    blank_lines: int
    comment_lines: int
    total_lines: int
    functions: int
    classes: int
    avg_function_length: float
    max_function_length: int


@dataclass
class ProjectMetrics:
    files: list[FileMetrics] = field(default_factory=list)

    @property
    def total_loc(self) -> int:
        return sum(f.loc for f in self.files)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def total_functions(self) -> int:
        return sum(f.functions for f in self.files)

    @property
    def total_classes(self) -> int:
        return sum(f.classes for f in self.files)

    @property
    def avg_file_loc(self) -> float:
        if not self.files:
            return 0.0
        return self.total_loc / len(self.files)

    def largest_files(self, n: int = 5) -> list[FileMetrics]:
        return sorted(self.files, key=lambda f: f.loc, reverse=True)[:n]

    def most_complex_files(self, n: int = 5) -> list[FileMetrics]:
        return sorted(self.files, key=lambda f: f.functions, reverse=True)[:n]


class CodeMetricsCollector:
    """Collect code metrics for individual files and projects."""

    def analyze_source(self, source: str, file_path: str = "") -> FileMetrics:
        """Compute metrics for a single source string."""
        lines = source.splitlines()
        total_lines = len(lines)
        blank_lines = sum(1 for ln in lines if not ln.strip())
        comment_lines = sum(1 for ln in lines if ln.strip().startswith("#"))
        loc = total_lines - blank_lines - comment_lines

        fn_lengths: list[int] = []
        classes = 0

        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    fn_lengths.append(end - node.lineno + 1)
                elif isinstance(node, ast.ClassDef):
                    classes += 1
        except SyntaxError:
            pass

        avg_fn_len = sum(fn_lengths) / len(fn_lengths) if fn_lengths else 0.0
        max_fn_len = max(fn_lengths) if fn_lengths else 0

        return FileMetrics(
            file=file_path,
            loc=max(0, loc),
            blank_lines=blank_lines,
            comment_lines=comment_lines,
            total_lines=total_lines,
            functions=len(fn_lengths),
            classes=classes,
            avg_function_length=round(avg_fn_len, 2),
            max_function_length=max_fn_len,
        )

    def analyze_project(self, sources: dict[str, str]) -> ProjectMetrics:
        """Compute metrics for all files in *sources*."""
        project = ProjectMetrics()
        for file_path, source in sources.items():
            project.files.append(self.analyze_source(source, file_path))
        return project
