"""Structural refactoring suggestions — extract method, inline variable, split long functions."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RefactorSuggestion:
    kind: str           # "extract_method" | "inline_variable" | "split_function" | "rename_ambiguous"
    file: str
    line: int
    description: str
    severity: str = "info"   # "info" | "warning" | "hint"
    snippet: str = ""        # relevant code snippet


@dataclass
class RefactorReport:
    file: str
    suggestions: list[RefactorSuggestion]
    total: int

    def format_summary(self) -> str:
        if not self.suggestions:
            return f"{self.file}: No refactoring suggestions."
        lines = [f"{self.file}: {self.total} suggestion(s)"]
        for s in self.suggestions[:10]:
            lines.append(f"  [{s.severity.upper()}] line {s.line}: {s.description}")
        return "\n".join(lines)


_MAX_FUNCTION_LINES = 40
_MAX_FUNCTION_ARGS = 5
_MAX_NESTING_DEPTH = 3


def _nesting_depth(node: ast.AST) -> int:
    """Compute maximum nesting depth of if/for/while/try inside a node."""
    max_depth = [0]

    def _walk(n: ast.AST, depth: int) -> None:
        if isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.AsyncFor, ast.AsyncWith)):
            depth += 1
            max_depth[0] = max(max_depth[0], depth)
        for child in ast.iter_child_nodes(n):
            _walk(child, depth)

    _walk(node, 0)
    return max_depth[0]


class RefactorSuggestor:
    """Analyse Python source and suggest structural refactoring opportunities."""

    def analyse_source(self, source: str, file: str = "<source>") -> RefactorReport:
        """Analyse source code string and return suggestions."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return RefactorReport(file=file, suggestions=[], total=0)

        lines = source.splitlines()
        suggestions: list[RefactorSuggestion] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Skip private / test functions
            if node.name.startswith("_") or node.name.startswith("test_"):
                continue

            start = node.lineno
            end = node.end_lineno or start
            func_lines = end - start + 1

            # Too long → suggest split
            if func_lines > _MAX_FUNCTION_LINES:
                suggestions.append(RefactorSuggestion(
                    kind="split_function", file=file, line=start,
                    description=f"Function '{node.name}' is {func_lines} lines — consider splitting",
                    severity="warning",
                    snippet=lines[start - 1] if start <= len(lines) else "",
                ))

            # Too many args → suggest object parameter
            n_args = len(node.args.args)
            if n_args > _MAX_FUNCTION_ARGS:
                suggestions.append(RefactorSuggestion(
                    kind="extract_method", file=file, line=start,
                    description=f"Function '{node.name}' has {n_args} parameters — consider a config object",
                    severity="hint",
                    snippet=lines[start - 1] if start <= len(lines) else "",
                ))

            # Deep nesting → suggest extract
            depth = _nesting_depth(node)
            if depth > _MAX_NESTING_DEPTH:
                suggestions.append(RefactorSuggestion(
                    kind="extract_method", file=file, line=start,
                    description=f"Function '{node.name}' has nesting depth {depth} — extract inner logic",
                    severity="warning",
                    snippet=lines[start - 1] if start <= len(lines) else "",
                ))

            # Single-use variables (assigned once, used once) → inline hint
            assigned: dict[str, int] = {}
            used: dict[str, int] = {}
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for t in child.targets:
                        if isinstance(t, ast.Name):
                            assigned[t.id] = assigned.get(t.id, 0) + 1
                elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    used[child.id] = used.get(child.id, 0) + 1
            for var, count in assigned.items():
                if count == 1 and used.get(var, 0) == 1 and not var.startswith("_"):
                    suggestions.append(RefactorSuggestion(
                        kind="inline_variable", file=file, line=start,
                        description=f"Variable '{var}' in '{node.name}' assigned+used once — consider inlining",
                        severity="info",
                    ))

        return RefactorReport(file=file, suggestions=suggestions, total=len(suggestions))

    def analyse_file(self, file_path: str) -> RefactorReport:
        p = Path(file_path)
        if not p.exists():
            return RefactorReport(file=file_path, suggestions=[], total=0)
        try:
            source = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return RefactorReport(file=file_path, suggestions=[], total=0)
        return self.analyse_source(source, file=file_path)
